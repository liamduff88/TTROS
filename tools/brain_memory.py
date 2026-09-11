#!/usr/bin/env python3
"""Atomic, provenance-bearing writes to the canonical TTROS Business Brain.

The Obsidian vault is the only durable knowledge authority.  This module never
uses Hermes profile memory, never pushes, and stages/commits only the exact
vault paths in the completed transaction.

Revisit: when the One Brain write transaction or vault Git contract changes. · Last touched: 2026-08-04.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping

import yaml


VAULT_ROOT = Path(
    os.environ.get(
        "TTROS_BRAIN_ROOT",
        "/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain",
    )
).resolve()
HERMES_AUTHOR_NAME = "Hermes"
HERMES_AUTHOR_EMAIL = "hermes@local.ttros"
MANAGED_BEGIN = "<!-- TTROS:HERMES:{section}:BEGIN -->"
MANAGED_END = "<!-- TTROS:HERMES:{section}:END -->"
SAFE_SECTION_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
PROVENANCE_KEY = "hermes_last_write"
ORDINARY_KNOWLEDGE_RE = re.compile(
    r"^(?:memory/company\.md|prospects/[a-z0-9][a-z0-9_-]*\.md|"
    r"operating_context/(?:current_priorities|executive_view|open_loops)\.md|"
    r"inbox/contradictions\.md)$"
)
ORDINARY_KNOWLEDGE_ALIASES = {
    "company": "memory/company.md",
    "current_priorities": "operating_context/current_priorities.md",
    "executive_view": "operating_context/executive_view.md",
    "open_loops": "operating_context/open_loops.md",
    "contradictions": "inbox/contradictions.md",
}


class BrainMemoryError(RuntimeError):
    """The vault transaction could not complete safely."""


class ConcurrentEditError(BrainMemoryError):
    """The source changed after it was read, so no overwrite was attempted."""


@dataclass(frozen=True)
class BrainWriteResult:
    changed_paths: tuple[str, ...]
    commit: str | None
    session_id: str
    source: str
    validation: str = "markdown/frontmatter/git-index validated"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except FileNotFoundError:
        return None


def _safe_relative(value: str) -> str:
    raw = str(value or "")
    pure = PurePosixPath(raw)
    if (
        not raw
        or raw != raw.strip()
        or pure.is_absolute()
        or any(part in {"", ".", ".."} for part in pure.parts)
        or "\\" in raw
        or "\x00" in raw
        or pure.parts[0] in {".git", ".obsidian", "_backups"}
    ):
        raise BrainMemoryError(f"unsafe or non-canonical Brain path: {raw!r}")
    if pure.suffix.lower() != ".md":
        raise BrainMemoryError("Hermes durable knowledge writes must target Markdown")
    return pure.as_posix()


def _target(relative: str) -> Path:
    canonical = _safe_relative(relative)
    target = (VAULT_ROOT / canonical).resolve()
    try:
        target.relative_to(VAULT_ROOT)
    except ValueError as exc:
        raise BrainMemoryError("Brain write escaped the canonical vault") from exc
    return target


def resolve_ordinary_knowledge_pointer(pointer: str) -> str:
    """Normalize only supported ordinary-memory forms to one contained note."""
    raw = str(pointer or "")
    if not raw or raw != raw.strip() or "\\" in raw or "\x00" in raw:
        raise BrainMemoryError("pointer is outside ordinary Hermes knowledge placement")
    if raw.startswith("business_brain:"):
        raw = raw.removeprefix("business_brain:")
    elif Path(raw).is_absolute():
        try:
            raw = Path(raw).resolve().relative_to(VAULT_ROOT.resolve()).as_posix()
        except (OSError, ValueError) as exc:
            raise BrainMemoryError("pointer is outside ordinary Hermes knowledge placement") from exc
    raw = ORDINARY_KNOWLEDGE_ALIASES.get(raw, raw)
    try:
        relative = _safe_relative(raw)
        target = _target(relative)
    except BrainMemoryError as exc:
        raise BrainMemoryError("pointer is outside ordinary Hermes knowledge placement") from exc
    if not ORDINARY_KNOWLEDGE_RE.fullmatch(relative) or not target.is_file():
        raise BrainMemoryError("pointer is outside ordinary Hermes knowledge placement")
    return relative


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise BrainMemoryError("managed Brain notes require YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise BrainMemoryError("unterminated YAML frontmatter")
    raw = text[4:end]
    try:
        fields = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise BrainMemoryError(f"invalid YAML frontmatter: {exc}") from exc
    if not isinstance(fields, dict):
        raise BrainMemoryError("frontmatter must be a mapping")
    return fields, text[end + 5 :]


def validate_markdown(text: str, *, relative: str) -> None:
    fields, body = parse_frontmatter(text)
    if not str(fields.get("id") or "").strip():
        raise BrainMemoryError(f"{relative} requires a stable frontmatter id")
    if body.count("[[") != body.count("]]" ):
        raise BrainMemoryError(f"{relative} contains unbalanced wiki links")
    for marker in re.findall(r"<!-- TTROS:HERMES:([^:>]+):(BEGIN|END) -->", body):
        if not SAFE_SECTION_RE.fullmatch(marker[0]):
            raise BrainMemoryError(f"{relative} contains an invalid Hermes section marker")
    section_names = set(re.findall(r"<!-- TTROS:HERMES:([^:>]+):BEGIN -->", body))
    end_names = set(re.findall(r"<!-- TTROS:HERMES:([^:>]+):END -->", body))
    if section_names != end_names:
        raise BrainMemoryError(f"{relative} contains an incomplete Hermes managed section")


def apply_provenance(text: str, *, source: str, session_id: str, timestamp: str | None = None) -> str:
    """Update only Hermes's small frontmatter submapping; preserve all other bytes."""
    if not str(source or "").strip() or not str(session_id or "").strip():
        raise BrainMemoryError("Hermes writes require source and session provenance")
    parse_frontmatter(text)
    stamp = timestamp or utc_now()
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise BrainMemoryError("frontmatter opener missing")
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if closing is None:
        raise BrainMemoryError("frontmatter closer missing")
    start = next((i for i in range(1, closing) if lines[i].rstrip("\r\n") == f"{PROVENANCE_KEY}:"), None)
    if start is not None:
        end = start + 1
        while end < closing and (lines[end].startswith("  ") or not lines[end].strip()):
            end += 1
        del lines[start:end]
        closing -= end - start
    block = [
        f"{PROVENANCE_KEY}:\n",
        "  author: hermes\n",
        f"  source: {json.dumps(str(source), ensure_ascii=False)}\n",
        f"  session: {json.dumps(str(session_id), ensure_ascii=False)}\n",
        f"  at: {json.dumps(stamp)}\n",
    ]
    lines[closing:closing] = block
    return "".join(lines)


def managed_section(
    existing: str,
    *,
    section_id: str,
    title: str,
    content: str,
    source: str,
    session_id: str,
) -> str:
    if not SAFE_SECTION_RE.fullmatch(section_id):
        raise BrainMemoryError("managed section id must be a safe lowercase slug")
    begin = MANAGED_BEGIN.format(section=section_id)
    end = MANAGED_END.format(section=section_id)
    block = "\n".join(
        (
            begin,
            f"## {title.strip()}",
            "",
            f"> Provenance: `author: hermes` · `source: {source}` · `session: {session_id}`",
            "",
            content.strip(),
            end,
        )
    )
    if begin in existing or end in existing:
        pattern = re.compile(re.escape(begin) + r"[\s\S]*?" + re.escape(end))
        if len(pattern.findall(existing)) != 1:
            raise BrainMemoryError("managed section markers are duplicated or incomplete")
        updated = pattern.sub(block, existing)
    else:
        updated = existing.rstrip() + "\n\n" + block + "\n"
    return apply_provenance(updated, source=source, session_id=session_id)


@contextmanager
def _transaction_lock():
    lock_path = VAULT_ROOT / ".git" / "hermes-memory.lock"
    if not (VAULT_ROOT / ".git").is_dir():
        raise BrainMemoryError("canonical Business Brain is not a Git worktree")
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(VAULT_ROOT), *args],
        text=True,
        capture_output=True,
        check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if check and result.returncode:
        detail = (result.stderr or result.stdout or "git command failed").strip()[-2000:]
        raise BrainMemoryError(detail)
    return result


def write_transaction(
    documents: Mapping[str, str],
    *,
    source: str,
    session_id: str,
    expected_hashes: Mapping[str, str | None] | None = None,
    commit: bool = True,
    post_write_validator: Callable[[tuple[str, ...]], None] | None = None,
    failure_injection: str | None = None,
) -> BrainWriteResult:
    """Validate, atomically replace, verify, and commit exactly these notes."""
    if not documents:
        raise BrainMemoryError("empty Brain transaction")
    canonical = {_safe_relative(path): content for path, content in documents.items()}
    if len(canonical) != len(documents):
        raise BrainMemoryError("duplicate canonical Brain paths")
    stamped = {
        relative: apply_provenance(content, source=source, session_id=session_id)
        for relative, content in canonical.items()
    }
    for relative, content in stamped.items():
        validate_markdown(content, relative=relative)

    with _transaction_lock():
        staged_before = [line for line in _git("diff", "--cached", "--name-only").stdout.splitlines() if line]
        if staged_before:
            if commit:
                raise BrainMemoryError("vault index already contains staged human changes; transaction refused")
            # Uncommitted continuity writes must not depend on unrelated staged work, but they
            # still refuse to overwrite a file the operator has staged themselves.
            overlap = sorted(set(staged_before) & set(canonical))
            if overlap:
                raise BrainMemoryError(f"transaction targets are staged in the vault index: {', '.join(overlap)}")

        originals: dict[str, bytes | None] = {}
        current_hashes: dict[str, str | None] = {}
        changed: list[str] = []
        for relative, content in stamped.items():
            path = _target(relative)
            original = path.read_bytes() if path.exists() else None
            originals[relative] = original
            current_hashes[relative] = sha256_bytes(original) if original is not None else None
            expected = (expected_hashes or {}).get(relative, current_hashes[relative])
            if current_hashes[relative] != expected:
                raise ConcurrentEditError(f"concurrent edit detected before write: {relative}")
            if original != content.encode("utf-8"):
                changed.append(relative)
        if not changed:
            return BrainWriteResult((), None, session_id, source)

        temp_paths: dict[str, Path] = {}
        new_hashes: dict[str, str] = {}
        replaced: list[str] = []
        try:
            for relative in changed:
                path = _target(relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.hermes-", suffix=".tmp", dir=path.parent)
                tmp = Path(raw_tmp)
                temp_paths[relative] = tmp
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(stamped[relative])
                    handle.flush()
                    os.fsync(handle.fileno())
                validate_markdown(tmp.read_text(encoding="utf-8"), relative=relative)
                new_hashes[relative] = file_sha256(tmp) or ""

            for relative in changed:
                path = _target(relative)
                if file_sha256(path) != current_hashes[relative]:
                    raise ConcurrentEditError(f"concurrent edit detected during write: {relative}")
                os.replace(temp_paths[relative], path)
                replaced.append(relative)
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                if failure_injection == "after_first_replace" and len(replaced) == 1:
                    raise BrainMemoryError("injected Brain write failure after first atomic replace")

            for relative in changed:
                path = _target(relative)
                validate_markdown(path.read_text(encoding="utf-8"), relative=relative)
                if file_sha256(path) != new_hashes[relative]:
                    raise ConcurrentEditError(f"concurrent edit detected after write: {relative}")

            if failure_injection == "provenance":
                raise BrainMemoryError("injected provenance validation failure")
            if post_write_validator is not None:
                post_write_validator(tuple(changed))

            if commit:
                _git("add", "--", *changed)
                indexed = [line for line in _git("diff", "--cached", "--name-only").stdout.splitlines() if line]
                if sorted(indexed) != sorted(changed):
                    raise BrainMemoryError("vault Git staged paths do not match the memory transaction")
                _git("diff", "--cached", "--check")
                for relative in changed:
                    indexed_bytes = _git("show", f":{relative}").stdout.encode("utf-8")
                    if sha256_bytes(indexed_bytes) != new_hashes[relative] or file_sha256(_target(relative)) != new_hashes[relative]:
                        raise ConcurrentEditError(f"concurrent edit detected before commit: {relative}")
                _git(
                    "-c", f"user.name={HERMES_AUTHOR_NAME}",
                    "-c", f"user.email={HERMES_AUTHOR_EMAIL}",
                    "commit", "-m", f"hermes: {session_id}", "--", *changed,
                )
                commit_hash = _git("rev-parse", "HEAD").stdout.strip()
            else:
                commit_hash = None
            return BrainWriteResult(tuple(changed), commit_hash, session_id, source)
        except Exception:
            # Restore only files still containing our candidate.  If another
            # writer won after replacement, preserve that writer's bytes.
            for relative in reversed(replaced):
                path = _target(relative)
                if file_sha256(path) != new_hashes.get(relative):
                    continue
                original = originals[relative]
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.rollback-", suffix=".tmp", dir=path.parent)
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(original)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(raw_tmp, path)
            _git("restore", "--staged", "--", *changed, check=False)
            raise
        finally:
            for path in temp_paths.values():
                path.unlink(missing_ok=True)


def update_note_section(
    relative: str,
    *,
    section_id: str,
    title: str,
    content: str,
    source: str,
    session_id: str,
) -> BrainWriteResult:
    path = _target(relative)
    if not path.is_file():
        raise BrainMemoryError(f"canonical note does not exist: {relative}")
    original = path.read_text(encoding="utf-8")
    expected = file_sha256(path)
    updated = managed_section(
        original,
        section_id=section_id,
        title=title,
        content=content,
        source=source,
        session_id=session_id,
    )
    return write_transaction(
        {relative: updated},
        source=source,
        session_id=session_id,
        expected_hashes={relative: expected},
    )


def session_relative(surface: str, session_key: str, *, date: str | None = None) -> str:
    safe_surface = re.sub(r"[^a-z0-9_-]+", "-", str(surface).lower()).strip("-") or "hermes"
    digest = hashlib.sha256(f"{safe_surface}\0{session_key}".encode("utf-8")).hexdigest()[:12]
    day = date or dt.datetime.now(dt.timezone.utc).date().isoformat()
    return f"sessions/{day}_{safe_surface}_{digest}.md"


def read_session(surface: str, session_key: str) -> tuple[str, str | None]:
    relative = session_relative(surface, session_key)
    path = _target(relative)
    if not path.exists():
        return "", None
    return path.read_text(encoding="utf-8"), file_sha256(path)


THREAD_MAX_CHARS = 2500


def thread_relative(identity: str) -> str:
    safe = re.sub(r"[^a-z0-9_-]+", "-", str(identity).lower()).strip("-") or "hermes"
    return f"sessions/thread_{safe}.md"


def read_thread(identity: str) -> tuple[str, str | None]:
    path = _target(thread_relative(identity))
    if not path.exists():
        return "", None
    return path.read_text(encoding="utf-8"), file_sha256(path)


def write_thread(*, identity: str, body: str, session_id: str, source: str) -> BrainWriteResult:
    """Supersede one rolling continuity thread. Never appends, never commits."""
    text = str(body or "").strip()
    if not text:
        raise BrainMemoryError("empty continuity thread body")
    if len(text) > THREAD_MAX_CHARS:
        raise BrainMemoryError(f"continuity thread exceeds {THREAD_MAX_CHARS} characters")
    relative = thread_relative(identity)
    expected = file_sha256(_target(relative))
    document = "\n".join((
        "---",
        f"id: hermes-thread-{Path(relative).stem}",
        "type: thread",
        "status: active",
        "author: hermes",
        f"source: {json.dumps(source)}",
        "---",
        f"# {identity} — working thread",
        "",
        "> Superseded every turn. Edit freely: David reads exactly what is left here.",
        "",
        text,
        "",
    ))
    return write_transaction(
        {relative: document},
        source=source,
        session_id=session_id,
        expected_hashes={relative: expected},
        commit=False,
    )


def append_session_turn(
    *,
    surface: str,
    session_key: str,
    session_id: str,
    user_message: str,
    assistant_response: str,
    token_usage: str = "unavailable from current CLI output",
    source: str,
) -> BrainWriteResult:
    relative = session_relative(surface, session_key)
    path = _target(relative)
    expected = file_sha256(path)
    stamp = utc_now()
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    else:
        note_id = f"hermes-session-{Path(relative).stem}"
        existing = "\n".join((
            "---",
            f"id: {note_id}",
            "type: session",
            "status: active",
            "author: hermes",
            f"source: {json.dumps(source)}",
            f"started_at: {json.dumps(stamp)}",
            "---",
            f"# Hermes session — {surface}",
            "",
            "> Revisit: on explicit reset or when its durable conclusions are reconciled. · Last touched: 2026-08-04.",
            "",
            "## Conversation",
            "",
        )) + "\n"
    turn = "\n".join((
        f"### Turn · {stamp}",
        "",
        "**Operator**",
        "",
        user_message.strip(),
        "",
        "**Hermes**",
        "",
        assistant_response.strip(),
        "",
        f"Token usage: {token_usage}",
        "",
    ))
    updated = existing.rstrip() + "\n\n" + turn
    return write_transaction(
        {relative: updated},
        source=source,
        session_id=session_id,
        expected_hashes={relative: expected},
    )


HISTORICAL_CALLS_DIR = "sources/historical_calls"


def normalize_vault_pointer(raw: str) -> str:
    """Validate and normalize a vault-relative Business Brain note path for a
    direct read. Does not check that the note exists."""
    return _safe_relative(str(raw or ""))


def read_vault_note(relative: str) -> tuple[str, str]:
    """Direct, read-only access to one canonical Business Brain note's raw
    text. Returns (normalized_relative_path, text). This is a vault read, not
    a transaction: no lock, no commit, no provenance stamp -- Step 6 corpus/
    vault tools are read-only by design."""
    canonical = normalize_vault_pointer(relative)
    target = _target(canonical)
    if not target.is_file():
        raise BrainMemoryError(f"no such vault note: {canonical}")
    return canonical, target.read_text(encoding="utf-8")


def reset_session(*, surface: str, session_key: str, session_id: str, source: str) -> BrainWriteResult | None:
    relative = session_relative(surface, session_key)
    path = _target(relative)
    if not path.exists():
        return None
    expected = file_sha256(path)
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^status:\s*active\s*$", "status: reset", text, count=1)
    text = text.rstrip() + f"\n\n## Reset\n\nExplicit reset at {utc_now()}.\n"
    return write_transaction(
        {relative: text}, source=source, session_id=session_id,
        expected_hashes={relative: expected},
    )
