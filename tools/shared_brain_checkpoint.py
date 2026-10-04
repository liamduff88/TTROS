"""Bounded, versioned working-continuity notes in the canonical Brain.

These notes never enter durable Git closure. Last touched: 2026-10-03.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

import yaml

try:
    from brain_memory import VAULT_ROOT
except ModuleNotFoundError:
    from tools.brain_memory import VAULT_ROOT

WORKSTREAM_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,63}\Z")
RECORD_RE = re.compile(r"record:[a-z0-9][a-z0-9_-]{2,127}\Z")
FIELDS = ("goal", "done", "decisions", "work_product_reference", "next_action", "open_questions")
ATTRIBUTION = ("authenticated_identity", "surface", "actor_class", "surface_source")
MAX_NOTE_CHARS = 2500
MAX_FIELD_CHARS = 1200
MAX_LIST = 20
LOCK_TIMEOUT_SECONDS = 2.0
DRIVE_PROJECTION = Path("/mnt/g/My Drive/TTROS Memory Exchange/06_WORKSTREAMS_READ")


def _error(message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "error": message, **extra}


def _id(value: Any) -> str | None:
    return value if isinstance(value, str) and WORKSTREAM_RE.fullmatch(value) else None


def _paths(workstream_id: str, root: Path) -> tuple[Path, Path, Path]:
    folder = root / "sessions" / "workstreams"
    return folder / f"{workstream_id}.md", folder / f"{workstream_id}.prev.md", root / ".git" / f"workstream-{workstream_id}.lock"


def _safe_path(path: Path, root: Path) -> bool:
    return (not path.is_symlink() and not path.parent.is_symlink()
            and path.resolve().is_relative_to(root.resolve()))


def _load(path: Path, root: Path) -> dict[str, Any] | None:
    if not _safe_path(path, root):
        raise ValueError("workstream storage is unsafe")
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    if len(text) > MAX_NOTE_CHARS:
        raise ValueError("workstream note is malformed")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("workstream note is malformed")
    raw = text[4:text.index("\n---\n", 4)]
    note = yaml.safe_load(raw)
    expected_id = path.name.removesuffix(".prev.md").removesuffix(".md")
    expected_keys = {"id", "workstream_id", "version", "updated", *FIELDS, *ATTRIBUTION}
    if (not isinstance(note, dict) or set(note) != expected_keys
            or note.get("id") != f"workstream:{expected_id}:v{note.get('version')}"
            or note.get("workstream_id") != expected_id
            or type(note.get("version")) is not int or note["version"] < 1
            or any(not isinstance(note.get(key), str) for key in expected_keys - {"version"})
            or any(_host_path(note[key]) for key in FIELDS)):
        raise ValueError("workstream note is malformed")
    return note


def _render(note: Mapping[str, Any]) -> str:
    front = yaml.safe_dump(dict(note), allow_unicode=True, sort_keys=False, width=1000)
    return "---\n" + front + "---\n\n# Workstream " + note["workstream_id"] + "\n"


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(raw, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(raw).unlink(missing_ok=True)


def _mirror(workstream_id: str, brain: Path) -> str:
    """Best-effort read projection; the Brain note remains the only authority."""
    if brain.resolve() != VAULT_ROOT.resolve():
        return "test_only"
    target_root = Path(os.environ.get("TTROS_SHARED_BRAIN_DRIVE_PROJECTION", str(DRIVE_PROJECTION)))
    if not target_root.parent.is_dir() or target_root.parent.is_symlink() or target_root.is_symlink():
        return "unavailable"
    current_path, _, _ = _paths(workstream_id, brain)
    try:
        target_root.mkdir(parents=True, exist_ok=True)
        with (brain / ".git" / f"workstream-{workstream_id}.projection.lock").open("a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                # Read after taking the projection lock so a slower earlier writer
                # cannot replace the newer version in Drive.
                latest = current_path.read_text(encoding="utf-8")
                _atomic(target_root / f"{workstream_id}.md", latest)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return "synced"
    except (OSError, UnicodeError):
        return "unavailable"


def _host_path(value: str) -> bool:
    if re.search(r"(?i)(?:file:|(?<![a-z0-9])[a-z]:[\\/]|localhost(?::\d+)?|127\.0\.0\.1(?::\d+)?)", value):
        return True
    without_urls = re.sub(r"https://\S+", "", value)
    return bool(re.search(r"(?:^|\s|[(])/[a-zA-Z0-9_.-]", without_urls))


def _reference(value: str, brain: Path) -> bool:
    if not value:
        return True
    if _host_path(value) or re.search(r"(?i)(?:^[/\\]|\\|(?:^|/)\.\.?/)", value):
        return False
    if value.startswith("https://"):
        return len(value) <= 300 and not any(ch.isspace() for ch in value)
    if value.startswith("business_brain:"):
        relative = value.removeprefix("business_brain:")
        valid = (len(relative) <= 300 and relative.endswith(".md")
                 and all(part not in {"", ".", ".."} for part in relative.split("/"))
                 and not relative.startswith("sessions/"))
        if not valid:
            return False
        if brain.resolve() == VAULT_ROOT.resolve():
            try:
                import shared_brain_read
            except ModuleNotFoundError:
                from tools import shared_brain_read
            try:
                return shared_brain_read._indexed_target(value) is not None
            except (OSError, ValueError):
                return False
        return True
    return bool(RECORD_RE.fullmatch(value))


def checkpoint(workstream_id: str, fields: Mapping[str, Any], expected_version: int,
               *, attribution: Mapping[str, str], root: Path | None = None,
               validate_only: bool = False) -> dict[str, Any]:
    """Write one complete note with optimistic version check under its own file lock."""
    if _id(workstream_id) is None:
        return _error("workstream_id must match [a-z0-9][a-z0-9-]{2,63}")
    if type(expected_version) is not int or expected_version < 0:
        return _error("expected_version must be a non-negative integer")
    if not isinstance(fields, Mapping):
        return _error("fields must be an object")
    supplied = {key: fields[key] for key in FIELDS if key in fields}
    if set(fields) - set(FIELDS) - set(ATTRIBUTION) - {"actor", "identity", "surface"}:
        return _error("unknown checkpoint field")
    if set(supplied) != set(FIELDS) or any(not isinstance(value, str) for value in supplied.values()):
        return _error("all six checkpoint fields must be strings")
    if any(len(value) > MAX_FIELD_CHARS for value in supplied.values()):
        return _error("each checkpoint field is limited to 1200 characters")
    brain = root or VAULT_ROOT
    if any(_host_path(value) for value in supplied.values()):
        return _error("checkpoint fields cannot contain host paths or loopback addresses")
    if not _reference(supplied["work_product_reference"], brain):
        return _error("work_product_reference must be a Brain reference, record ID or https URL")
    if not supplied["goal"].strip() or not supplied["next_action"].strip():
        return _error("goal and next_action must be non-empty")
    if not isinstance(attribution, Mapping) or any(not attribution.get(key) for key in ATTRIBUTION):
        return _error("server attribution is unavailable")
    if validate_only:
        candidate = {"id": f"workstream:{workstream_id}:v{expected_version + 1}",
                     "workstream_id": workstream_id, **supplied,
                     **{key: attribution[key] for key in ATTRIBUTION},
                     "version": expected_version + 1,
                     "updated": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")}
        if len(_render(candidate)) > MAX_NOTE_CHARS:
            return _error("workstream note exceeds 2500 characters")
        return {"success": True, "validated": True}
    current_path, previous_path, lock_path = _paths(workstream_id, brain)
    if not (brain / ".git").is_dir() or not _safe_path(current_path, brain) or not _safe_path(previous_path, brain):
        return _error("workstream storage is unavailable")
    current_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    return _error("workstream is busy; resume and retry")
                time.sleep(0.02)
        try:
            current = _load(current_path, brain)
            version = current["version"] if current else 0
            if expected_version != version:
                return _error("stale checkpoint version; resume and retry", current=current)
            note = {
                "id": f"workstream:{workstream_id}:v{version + 1}", "workstream_id": workstream_id,
                **supplied, **{key: attribution[key] for key in ATTRIBUTION},
                "version": version + 1,
                "updated": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            rendered = _render(note)
            if len(rendered) > MAX_NOTE_CHARS:
                return _error("workstream note exceeds 2500 characters")
            if current is not None:
                _atomic(previous_path, current_path.read_text(encoding="utf-8"))
            _atomic(current_path, rendered)
        except (OSError, UnicodeError, ValueError, yaml.YAMLError):
            return _error("workstream storage is unavailable")
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {"success": True, "note": note, "drive_projection": _mirror(workstream_id, brain)}


def resume(workstream_id: str | None = None, version: int | None = None,
           *, root: Path | None = None) -> dict[str, Any]:
    brain = root or VAULT_ROOT
    if workstream_id is None:
        if version is not None:
            return _error("version requires workstream_id")
        folder = brain / "sessions" / "workstreams"
        if not folder.is_dir() or folder.is_symlink():
            return {"success": True, "workstreams": []}
        notes = []
        for path in folder.glob("*.md"):
            if path.name.endswith(".prev.md") or _id(path.stem) is None:
                continue
            try:
                note = _load(path, brain)
            except (OSError, UnicodeError, ValueError, yaml.YAMLError):
                continue
            if note and note.get("workstream_id") == path.stem:
                notes.append({"workstream_id": path.stem, "goal": str(note.get("goal", ""))[:MAX_FIELD_CHARS],
                              "last_surface": note.get("surface"), "updated": note.get("updated")})
        notes.sort(key=lambda row: row["updated"] or "", reverse=True)
        return {"success": True, "workstreams": notes[:MAX_LIST]}
    if _id(workstream_id) is None:
        return _error("workstream_id must match [a-z0-9][a-z0-9-]{2,63}")
    if version is not None and (type(version) is not int or version < 1):
        return _error("version must be a positive integer")
    current_path, previous_path, _ = _paths(workstream_id, brain)
    try:
        current = _load(current_path, brain)
        if current is None:
            return _error("unknown workstream_id")
        if version is None or current["version"] == version:
            return {"success": True, "note": current}
        previous = _load(previous_path, brain)
        if previous and previous["version"] == version:
            return {"success": True, "note": previous}
        return _error("requested version is unavailable")
    except (OSError, UnicodeError, ValueError, yaml.YAMLError):
        return _error("workstream storage is unavailable")
