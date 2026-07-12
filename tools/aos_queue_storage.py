"""Shared Linux/POSIX locking and durable replacement for authoritative state.

Lock order is package-operation lock first, then this queue write lock.  Code
holding this lock must never acquire a package-operation lock.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import errno
import json
import os
import shutil
import socket
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    from aos_paths import assert_authoritative_root
except ModuleNotFoundError:  # package import in unittest/IDE contexts
    from tools.aos_paths import assert_authoritative_root

LOCK_RELATIVE = Path("queue/locks/work_items.write.lock")
OWNER_FILE = "owner.json"
LOCK_VERSION = 1
DEFAULT_WAIT_SECONDS = 5.0
_LOCAL = threading.local()


class QueueStorageError(RuntimeError):
    """The queue cannot be locked or durably replaced safely."""


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _runtime_id() -> str:
    return "linux-posix"


def _linux_start_id(pid: int) -> str | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
        return fields[21]
    except (OSError, IndexError):
        return None


def _process_start_id(pid: int) -> str | None:
    return _linux_start_id(pid)


def process_start_identity(pid: int | None = None) -> str:
    """Return the current Linux process-start identity or fail closed."""
    target_pid = os.getpid() if pid is None else pid
    start_id = _process_start_id(target_pid)
    if not start_id:
        raise QueueStorageError("cannot establish process start identity; lock refused")
    return start_id


def _process_exists(pid: int) -> bool | None:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return None


def _owner_payload(token: str) -> dict:
    pid = os.getpid()
    return {
        "lock_version": LOCK_VERSION,
        "token": token,
        "pid": pid,
        "process_start_id": process_start_identity(pid),
        "host": socket.gethostname(),
        "runtime": _runtime_id(),
        "acquired_at": _utc_now(),
    }


def _validate_owner(value: object) -> dict:
    required = {"lock_version", "token", "pid", "process_start_id", "host", "runtime", "acquired_at"}
    if not isinstance(value, dict) or set(value) != required:
        raise QueueStorageError("queue lock owner metadata is malformed; refusing to steal lock")
    if value["lock_version"] != LOCK_VERSION:
        raise QueueStorageError("queue lock owner version is unsupported; refusing to steal lock")
    if not isinstance(value["pid"], int) or value["pid"] <= 0:
        raise QueueStorageError("queue lock owner PID is malformed; refusing to steal lock")
    for key in required - {"lock_version", "pid"}:
        if not isinstance(value[key], str) or not value[key].strip():
            raise QueueStorageError(f"queue lock owner {key} is malformed; refusing to steal lock")
    try:
        parsed = dt.datetime.fromisoformat(value["acquired_at"].replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except ValueError as exc:
        raise QueueStorageError("queue lock acquired_at is malformed; refusing to steal lock") from exc
    return value


def read_lock_owner(lock_dir: Path) -> dict:
    try:
        value = json.loads((lock_dir / OWNER_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QueueStorageError("queue lock owner metadata is missing or malformed; refusing to steal lock") from exc
    return _validate_owner(value)


def _owner_alive(owner: dict) -> bool | None:
    # PIDs are meaningful only inside the same host/runtime namespace.
    if owner["host"] != socket.gethostname() or owner["runtime"] != _runtime_id():
        return None
    current_start = _process_start_id(owner["pid"])
    if current_start is None:
        exists = _process_exists(owner["pid"])
        return False if exists is False else None
    return current_start == owner["process_start_id"]


def fsync_directory(path: Path) -> None:
    """Durably commit Linux/POSIX directory metadata or raise."""
    assert_authoritative_root(path)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_create_directory(path: Path, *, parents: bool = False) -> None:
    """Create directory entries and fsync each containing directory."""
    path = Path(path)
    assert_authoritative_root(path.parent)
    if not parents:
        os.mkdir(path)
        fsync_directory(path.parent)
        return

    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        if cursor.parent == cursor:
            raise QueueStorageError(f"cannot find existing parent for durable directory creation: {path}")
        cursor = cursor.parent
    if not cursor.is_dir():
        raise QueueStorageError(f"durable directory parent is not a directory: {cursor}")
    for directory in reversed(missing):
        try:
            os.mkdir(directory)
        except FileExistsError:
            if not directory.is_dir():
                raise
        fsync_directory(directory.parent)


def durable_rename_directory(source: Path, target: Path) -> None:
    """Rename one namespace entry durably without replacing the target."""
    if source.parent != target.parent:
        raise QueueStorageError("durable namespace rename requires one containing directory")
    assert_authoritative_root(target.parent)
    os.rename(source, target)
    fsync_directory(target.parent)


def durable_publish_directory(candidate: Path, target: Path, token: str) -> None:
    """Publish a prepared lock directory, retaining evidence on sync failure."""
    if candidate.parent != target.parent:
        raise QueueStorageError("durable lock publication requires one containing directory")
    assert_authoritative_root(target.parent)
    os.rename(candidate, target)
    try:
        fsync_directory(target.parent)
    except OSError as sync_exc:
        evidence = target.with_name(f".{target.name.lstrip('.')}.publication-failed-{token}")
        try:
            os.rename(target, evidence)
        except OSError as cleanup_exc:
            raise QueueStorageError(
                f"lock publication durability failed and canonical cleanup was unsafe; retained at {target}"
            ) from cleanup_exc
        try:
            fsync_directory(target.parent)
        except OSError as cleanup_sync_exc:
            raise QueueStorageError(
                f"lock publication durability failed; canonical entry was quarantined as {evidence}, "
                "but quarantine durability also failed"
            ) from cleanup_sync_exc
        raise QueueStorageError(
            f"lock publication durability failed; canonical entry was quarantined as {evidence}"
        ) from sync_exc


def durable_remove_tree(path: Path) -> None:
    """Remove a noncanonical directory tree and durably commit its removal."""
    path = Path(path)
    shutil.rmtree(path)
    fsync_directory(path.parent)


def durable_replace_text(path: Path, text: str) -> None:
    """Flush a same-directory temp and durably replace the target."""
    assert_authoritative_root(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        fsync_directory(path.parent)
    except Exception:
        with contextlib.suppress(OSError):
            temp.unlink()
        raise


def durable_append_text(root: Path, path: Path, text: str) -> None:
    """Serialize a logical append, then commit it with POSIX durability.

    This deliberately uses the existing authoritative queue mutation lock so
    read-modify-replace cannot lose a concurrent writer's record.
    """
    root = assert_authoritative_root(root)
    path = Path(path)
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise QueueStorageError(f"append target is outside authoritative root: {path}") from exc
    with queue_write_lock(root):
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        durable_replace_text(path, existing + text)


def _prepare_candidate(lock_dir: Path, token: str) -> Path:
    parent = lock_dir.parent
    durable_create_directory(parent, parents=True)
    candidate = parent / f".{lock_dir.name}.candidate-{token}"
    durable_create_directory(candidate)
    try:
        durable_replace_text(candidate / OWNER_FILE, json.dumps(_owner_payload(token), sort_keys=True) + "\n")
        return candidate
    except Exception:
        if candidate.exists():
            with contextlib.suppress(OSError):
                durable_remove_tree(candidate)
        raise


def _remove_proven_stale(lock_dir: Path, owner: dict) -> None:
    if _owner_alive(owner) is not False:
        raise QueueStorageError("queue lock owner may still be live; refusing stale recovery")
    quarantine = lock_dir.with_name(f".{lock_dir.name}.stale-{uuid.uuid4().hex}")
    try:
        durable_rename_directory(lock_dir, quarantine)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise QueueStorageError(f"could not quarantine proven-stale queue lock: {exc}") from exc
    try:
        quarantined_owner = read_lock_owner(quarantine)
    except QueueStorageError as exc:
        # The namespace change may already be durable.  Never delete evidence
        # we cannot prove belongs to the dead owner, and never overwrite a
        # replacement owner that appeared at the canonical path.
        if not lock_dir.exists():
            with contextlib.suppress(OSError):
                durable_rename_directory(quarantine, lock_dir)
        raise QueueStorageError(
            f"quarantined queue lock metadata is malformed; retained for review: {quarantine}"
        ) from exc
    if quarantined_owner != owner:
        if not lock_dir.exists():
            try:
                durable_rename_directory(quarantine, lock_dir)
            except OSError as exc:
                raise QueueStorageError(
                    f"quarantined queue lock ownership changed and could not be restored; retained: {quarantine}"
                ) from exc
        raise QueueStorageError(
            f"quarantined queue lock ownership changed; refusing to delete it: {quarantine}"
        )
    durable_remove_tree(quarantine)


@contextmanager
def queue_write_lock(root: Path, *, wait_seconds: float = DEFAULT_WAIT_SECONDS) -> Iterator[None]:
    """Acquire the one live-ledger write lock, waiting at most five seconds."""
    root = assert_authoritative_root(root)
    lock_dir = root / LOCK_RELATIVE
    held = getattr(_LOCAL, "held", {})
    key = str(lock_dir.resolve())
    if held.get(key, 0):
        held[key] += 1
        _LOCAL.held = held
        try:
            yield
        finally:
            held[key] -= 1
        return
    token = uuid.uuid4().hex
    candidate = _prepare_candidate(lock_dir, token)
    expected_owner = read_lock_owner(candidate)
    deadline = time.monotonic() + max(0.0, wait_seconds)
    acquired = False
    missing_after_contention_at_deadline = False
    try:
        while True:
            try:
                durable_publish_directory(candidate, lock_dir, token)
                acquired = True
                held[key] = 1
                _LOCAL.held = held
                break
            except OSError as exc:
                if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY, errno.EACCES}:
                    raise
                try:
                    owner = read_lock_owner(lock_dir)
                except QueueStorageError:
                    if exc.errno == errno.EACCES and not lock_dir.exists():
                        raise exc
                    if not lock_dir.exists():
                        # The prior owner may have durably renamed the lock for
                        # release after our rename reported contention. Retry
                        # the still-prepared candidate, but remain bounded at
                        # a zero/expired deadline.
                        if time.monotonic() >= deadline:
                            if missing_after_contention_at_deadline:
                                raise QueueStorageError(
                                    f"queue write lock changed during release; timed out after {wait_seconds:.1f}s"
                                )
                            missing_after_contention_at_deadline = True
                        continue
                    # Access denied is contention only when a strict readable
                    # owner exists.  Missing/malformed metadata is either a
                    # genuine permission error or unsafe ambiguity; neither is
                    # retryable.
                    raise
                missing_after_contention_at_deadline = False
                alive = _owner_alive(owner)
                if alive is False:
                    _remove_proven_stale(lock_dir, owner)
                    if time.monotonic() >= deadline and lock_dir.exists():
                        raise QueueStorageError(
                            f"queue write lock recovery did not complete before {wait_seconds:.1f}s deadline"
                        )
                    continue
                if time.monotonic() >= deadline:
                    state = "live" if alive else "owned from another runtime"
                    raise QueueStorageError(f"queue write lock is {state}; timed out after {wait_seconds:.1f}s")
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
        yield
    finally:
        if not acquired:
            if candidate.exists():
                with contextlib.suppress(OSError):
                    durable_remove_tree(candidate)
        else:
            try:
                owner = read_lock_owner(lock_dir)
                if owner != expected_owner:
                    raise QueueStorageError("queue lock ownership changed; refusing to remove another owner's lock")
                releasing = lock_dir.with_name(f".{lock_dir.name}.release-{token}")
                durable_rename_directory(lock_dir, releasing)
                durable_remove_tree(releasing)
            finally:
                held.pop(key, None)
