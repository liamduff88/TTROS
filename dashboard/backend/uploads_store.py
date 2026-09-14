"""Shared local upload storage for the dashboard.

One mechanism, reused by Memory Intake, the Cockpit quick-drop card, and
David attachments: real bytes land under ``queue/uploads/<upload_id>/``,
never a bare filename string. ``<upload_id>`` is server-generated (uuid4
hex), so it is never attacker-controlled and never needs to resist path
traversal; the original filename is sanitized separately and used only as
the leaf name inside that already-safe directory.

Revisit: when the shared upload contract, its size cap, or its supported
content types change. · Created 2026-09-13.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MiB; a local operator tool, not a bulk import path.
UPLOADS_RELATIVE = "queue/uploads"
_UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{32}$")

# What tools/source_intake.py can actually ingest end-to-end today. Anything
# else is stored (so David or the operator can still look at it) but is
# marked unsupported rather than silently ingested as garbage.
INGESTABLE_SUFFIXES = frozenset({".txt", ".md", ".eml"})
KNOWN_UNSUPPORTED_SUFFIXES = frozenset({".pdf", ".docx"})


class UploadError(ValueError):
    pass


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize_filename(name: str) -> str:
    """Strip any directory component and disallowed characters; never used to
    build a path outside the upload's own uuid-named directory, so this only
    has to guard against unusable/confusing names, not traversal."""
    raw = str(name or "").replace("\x00", "")
    base = Path(raw.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .")
    return base[:200] or "upload"


def _uploads_root(base_dir: Path) -> Path:
    root = Path(base_dir) / UPLOADS_RELATIVE
    root.mkdir(parents=True, exist_ok=True)
    return root


def _content_type_status(filename: str) -> tuple[bool, str]:
    suffix = Path(filename).suffix.lower()
    if suffix in INGESTABLE_SUFFIXES:
        return True, "supported"
    if suffix in KNOWN_UNSUPPORTED_SUFFIXES:
        return False, f"{suffix} is stored but not yet supported end-to-end by source intake"
    return False, f"{suffix or 'extensionless'} is not a recognized ingestible type"


@dataclass(frozen=True)
class SavedUpload:
    upload_id: str
    filename: str
    size: int
    sha256: str
    supported: bool
    path: Path


def save_upload(base_dir: Path, filename: str, data: bytes) -> SavedUpload:
    if len(data) == 0:
        raise UploadError("uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError(f"uploaded file exceeds the {MAX_UPLOAD_BYTES} byte limit")
    safe_name = sanitize_filename(filename)
    supported, reason = _content_type_status(safe_name)
    upload_id = uuid.uuid4().hex
    upload_dir = _uploads_root(base_dir) / upload_id
    upload_dir.mkdir(parents=True, exist_ok=False)
    target = upload_dir / safe_name
    target.write_bytes(data)
    meta = {
        "upload_id": upload_id,
        "original_filename": str(filename or safe_name),
        "stored_filename": safe_name,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "supported": supported,
        "support_note": reason,
        "uploaded_at": _utc_now(),
        "status": "ready",
    }
    (upload_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return SavedUpload(upload_id, safe_name, len(data), meta["sha256"], supported, target)


def _upload_dir(base_dir: Path, upload_id: str) -> Path:
    if not _UPLOAD_ID_RE.fullmatch(str(upload_id or "")):
        raise UploadError("invalid upload id")
    root = _uploads_root(base_dir).resolve()
    candidate = (root / upload_id).resolve()
    if candidate.parent != root:
        raise UploadError("invalid upload id")
    return candidate


def read_meta(base_dir: Path, upload_id: str) -> dict:
    upload_dir = _upload_dir(base_dir, upload_id)
    meta_path = upload_dir / "meta.json"
    if not meta_path.is_file():
        raise UploadError(f"unknown upload: {upload_id}")
    return json.loads(meta_path.read_text(encoding="utf-8"))


def write_meta(base_dir: Path, upload_id: str, meta: dict) -> None:
    upload_dir = _upload_dir(base_dir, upload_id)
    (upload_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def upload_file_path(base_dir: Path, upload_id: str) -> Path:
    meta = read_meta(base_dir, upload_id)
    upload_dir = _upload_dir(base_dir, upload_id)
    path = (upload_dir / meta["stored_filename"]).resolve()
    if path.parent != upload_dir.resolve() or path.is_symlink() or not path.is_file():
        raise UploadError(f"upload payload is missing or unsafe: {upload_id}")
    return path


def list_uploads(base_dir: Path) -> list[dict]:
    root = _uploads_root(base_dir)
    rows = []
    for entry in sorted(root.iterdir()) if root.is_dir() else []:
        meta_path = entry / "meta.json"
        if not entry.is_dir() or entry.is_symlink() or not meta_path.is_file():
            continue
        try:
            rows.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    rows.sort(key=lambda row: str(row.get("uploaded_at") or ""), reverse=True)
    return rows
