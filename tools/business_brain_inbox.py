"""Safe append-only intake for the canonical Business Brain inbox.

Revisit: when the canonical inbox, capture metadata, or vault write contract changes. · Last touched: 2026-07-19.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import tempfile
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

try:
    import business_brain
except ModuleNotFoundError:  # package import in unittest/IDE contexts
    from tools import business_brain


INBOX_README_POINTER = "business_brain:inbox/README.md"
SOURCE_NOTES_RELATIVE = Path("inbox/source_notes")
ATTACHMENTS_DIRECTORY = "attachments"
MAX_TEXT_CHARS = 100_000
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024
SOURCE_PREFIXES = {"cockpit_capture": "capture", "telegram_bot": "tg"}


class InboxCaptureError(ValueError):
    """Raised when a capture cannot safely enter the canonical inbox."""


@dataclass(frozen=True)
class CaptureResult:
    path: Path
    pointer: str
    capture_id: str
    duplicate: bool
    attachment_path: Path | None = None
    attachment_pointer: str | None = None


def _utc_timestamp(value: dt.datetime | None = None) -> dt.datetime:
    stamp = value or dt.datetime.now(dt.timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    return stamp.astimezone(dt.timezone.utc)


def _iso_timestamp(value: dt.datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _yaml_string(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def sanitize_filename(value: str, *, fallback: str = "capture", max_length: int = 96) -> str:
    """Return a portable basename; separators and traversal never survive."""
    raw = unicodedata.normalize("NFKC", str(value or "")).replace("\x00", "")
    raw = raw.replace("/", "-").replace("\\", "-")
    raw = re.sub(r"[^\w. -]+", "-", raw, flags=re.UNICODE)
    raw = re.sub(r"[\s-]+", "-", raw).strip(" .-_")
    if not raw or raw in {".", ".."}:
        raw = fallback
    stem = Path(raw).stem.strip(" .-_") or fallback
    suffix = Path(raw).suffix.lower()
    suffix = suffix if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) else ""
    available = max(1, max_length - len(suffix))
    return f"{stem[:available].rstrip(' .-_') or fallback}{suffix}"


def resolve_canonical_inbox(*, root: Path | None = None) -> Path:
    """Resolve the one declared inbox through its stable README pointer."""
    vault = Path(root) if root is not None else business_brain.BUSINESS_BRAIN_ROOT
    try:
        readme = business_brain.resolve_business_brain_pointer(INBOX_README_POINTER, root=vault).resolved_path
    except business_brain.BusinessBrainPointerError as exc:
        raise InboxCaptureError(str(exc)) from exc
    expected = vault.resolve() / SOURCE_NOTES_RELATIVE
    inbox = (readme.parent / "source_notes").resolve()
    if inbox != expected or not inbox.is_dir():
        raise InboxCaptureError("canonical Business Brain source-notes inbox is unavailable")
    try:
        inbox.relative_to(vault.resolve())
    except ValueError as exc:
        raise InboxCaptureError("canonical inbox escaped the Business Brain") from exc
    return inbox


def _safe_child(parent: Path, name: str) -> Path:
    candidate = parent / sanitize_filename(name)
    try:
        candidate.resolve().relative_to(parent.resolve())
    except ValueError as exc:
        raise InboxCaptureError("capture filename escaped the canonical inbox") from exc
    if candidate.parent.resolve() != parent.resolve():
        raise InboxCaptureError("capture filename must be a basename")
    return candidate


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        # DrvFS may reject directory fsync. The file itself is still fully
        # flushed and publication is a same-directory atomic hard-link.
        pass


def _publish_once(path: Path, data: bytes) -> bool:
    """Publish bytes without overwriting; return False for an exact replay."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_file() and path.read_bytes() == data:
                return False
            raise InboxCaptureError("capture ID already exists with different content")
        _fsync_directory(path.parent)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _capture_token(source: str, capture_id: str) -> str:
    return hashlib.sha256(f"{source}\0{capture_id}".encode("utf-8")).hexdigest()[:16]


def _existing_capture(inbox: Path, prefix: str, token: str) -> Path | None:
    matches = []
    for path in inbox.glob(f"{prefix}_*_{token}.md"):
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(inbox.resolve())
        except (OSError, ValueError):
            continue
        if resolved.is_file():
            matches.append(resolved)
    if len(matches) > 1:
        raise InboxCaptureError("capture replay identity is ambiguous")
    return matches[0] if matches else None


def _frontmatter(
    *,
    source: str,
    captured: dt.datetime,
    capture_id: str,
    content_type: str,
    payload_sha256: str,
    metadata: dict[str, object] | None = None,
) -> str:
    token = _capture_token(source, capture_id)
    lines = [
        "---",
        f"id: inbox-capture-{token}",
        "type: intake",
        f"source: {source}",
        f"captured: {_yaml_string(_iso_timestamp(captured))}",
        f"capture_id: {_yaml_string(capture_id)}",
        f"content_type: {content_type}",
        f"payload_sha256: {payload_sha256}",
    ]
    for key, value in sorted((metadata or {}).items()):
        if value is None:
            continue
        safe_key = re.sub(r"[^a-z0-9_]", "_", str(key).lower())
        if not safe_key:
            continue
        rendered = str(value).lower() if isinstance(value, bool) else _yaml_string(value)
        lines.append(f"{safe_key}: {rendered}")
    return "\n".join(lines) + "\n---\n"


def capture_text(
    text: str,
    *,
    source: str,
    capture_id: str | None = None,
    captured_at: dt.datetime | None = None,
    content_type: str = "text",
    metadata: dict[str, object] | None = None,
    root: Path | None = None,
) -> CaptureResult:
    raw = str(text)
    if not raw.strip():
        raise InboxCaptureError("capture text must not be empty")
    if len(raw) > MAX_TEXT_CHARS:
        raise InboxCaptureError(f"capture text must be {MAX_TEXT_CHARS} characters or fewer")
    if source not in SOURCE_PREFIXES:
        raise InboxCaptureError("capture source is not allowed")
    identity = str(capture_id or uuid.uuid4())
    if len(identity) > 256 or any(ord(char) < 32 for char in identity):
        raise InboxCaptureError("capture ID is invalid")
    stamp = _utc_timestamp(captured_at)
    token = _capture_token(source, identity)
    inbox = resolve_canonical_inbox(root=root)
    existing = _existing_capture(inbox, SOURCE_PREFIXES[source], token)
    payload = raw.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    note = _frontmatter(
        source=source,
        captured=stamp,
        capture_id=identity,
        content_type=content_type,
        payload_sha256=digest,
        metadata=metadata,
    ) + raw + ("" if raw.endswith("\n") else "\n")
    data = note.encode("utf-8")
    if existing is not None:
        existing_text = existing.read_text(encoding="utf-8", errors="strict")
        if f"payload_sha256: {digest}\n" not in existing_text or f"source: {source}\n" not in existing_text:
            raise InboxCaptureError("capture ID already exists with different content")
        return CaptureResult(
            path=existing,
            pointer=business_brain.business_brain_pointer_for_path(existing, root=root),
            capture_id=identity,
            duplicate=True,
        )
    filename = f"{SOURCE_PREFIXES[source]}_{stamp.strftime('%Y-%m-%d_%H%M%S%f')}_{token}.md"
    target = _safe_child(inbox, filename)
    created = _publish_once(target, data)
    return CaptureResult(
        path=target,
        pointer=business_brain.business_brain_pointer_for_path(target, root=root),
        capture_id=identity,
        duplicate=not created,
    )


def capture_attachment(
    data: bytes,
    *,
    original_filename: str,
    mime_type: str,
    capture_id: str,
    captured_at: dt.datetime | None = None,
    body: str = "Attachment captured without transformation.",
    content_type: str = "file",
    metadata: dict[str, object] | None = None,
    root: Path | None = None,
) -> CaptureResult:
    if not data:
        raise InboxCaptureError("attachment must not be empty")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise InboxCaptureError(f"attachment exceeds the {MAX_ATTACHMENT_BYTES}-byte limit")
    identity = str(capture_id or "")
    if not identity:
        raise InboxCaptureError("attachment capture ID is required")
    stamp = _utc_timestamp(captured_at)
    inbox = resolve_canonical_inbox(root=root)
    attachments = (inbox / ATTACHMENTS_DIRECTORY).resolve()
    try:
        attachments.relative_to(inbox.resolve())
    except ValueError as exc:
        raise InboxCaptureError("attachment directory escaped the canonical inbox") from exc
    safe_original = sanitize_filename(original_filename, fallback="attachment.bin")
    token = _capture_token("telegram_bot", identity)
    attachment_name = f"tg_{stamp.strftime('%Y-%m-%d_%H%M%S%f')}_{token}_{safe_original}"
    attachment = _safe_child(attachments, attachment_name)
    created = _publish_once(attachment, data)
    digest = hashlib.sha256(data).hexdigest()
    attachment_pointer = business_brain.business_brain_pointer_for_path(attachment, root=root)
    note_metadata = {
        **(metadata or {}),
        "attachment": attachment_pointer,
        "attachment_filename": safe_original,
        "attachment_mime_type": mime_type or "application/octet-stream",
        "attachment_sha256": digest,
    }
    try:
        note = capture_text(
            body,
            source="telegram_bot",
            capture_id=identity,
            captured_at=stamp,
            content_type=content_type,
            metadata=note_metadata,
            root=root,
        )
    except Exception:
        if created:
            attachment.unlink(missing_ok=True)
            _fsync_directory(attachments)
        raise
    return CaptureResult(
        path=note.path,
        pointer=note.pointer,
        capture_id=note.capture_id,
        duplicate=note.duplicate and not created,
        attachment_path=attachment,
        attachment_pointer=attachment_pointer,
    )
