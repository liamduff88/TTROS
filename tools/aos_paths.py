"""AOS root, path-safety, and Linux-authority helpers."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path, PureWindowsPath


DEFAULT_AOS_ROOT = Path(__file__).resolve().parents[1]


class AosPathError(ValueError):
    """Raised when a path cannot be resolved safely under AOS_ROOT."""


class AuthorityError(RuntimeError):
    """Raised before an authoritative mutation on an unsupported runtime/root."""


_WINDOWS_MOUNT_RE = re.compile(r"^/mnt/[a-z](?:/|$)", re.IGNORECASE)
_WINDOWS_FILESYSTEMS = {"drvfs", "9p", "ntfs", "ntfs3", "fuseblk"}


def aos_root() -> Path:
    """Return AOS_ROOT from the environment, or this repository root."""
    configured = os.environ.get("AOS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_AOS_ROOT


def _is_absolute_path_text(value: object) -> bool:
    text = str(value)
    return Path(text).is_absolute() or PureWindowsPath(text).is_absolute()


def resolve_root_relative(relative_path: str | Path, *, root: str | Path | None = None) -> Path:
    """Resolve a root-relative path and reject absolute or escaping paths."""
    path_text = str(relative_path or "").strip()
    if not path_text:
        raise AosPathError("path is required")
    if _is_absolute_path_text(path_text):
        raise AosPathError("path must be root-relative")

    root_path = Path(root).expanduser().resolve() if root is not None else aos_root()
    target = (root_path / path_text).resolve()
    try:
        target.relative_to(root_path)
    except ValueError as exc:
        raise AosPathError("path must stay under AOS_ROOT") from exc
    return target


def _unescape_mountinfo(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def filesystem_type(path: str | Path) -> tuple[str, str, str]:
    """Return ``(filesystem, mountpoint, source)`` for a Linux path."""
    target = Path(path).expanduser().resolve()
    best: tuple[int, str, str, str] | None = None
    try:
        lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AuthorityError("cannot inspect Linux mount table; authoritative mutation refused") from exc
    for line in lines:
        left, separator, right = line.partition(" - ")
        if not separator:
            continue
        left_fields = left.split()
        right_fields = right.split()
        if len(left_fields) < 5 or len(right_fields) < 2:
            continue
        mountpoint = Path(_unescape_mountinfo(left_fields[4]))
        try:
            target.relative_to(mountpoint)
        except ValueError:
            continue
        candidate = (len(mountpoint.parts), right_fields[0].lower(), str(mountpoint), _unescape_mountinfo(right_fields[1]))
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        raise AuthorityError(f"cannot identify filesystem for authoritative root: {target}")
    return best[1], best[2], best[3]


def assert_authoritative_root(root: str | Path) -> Path:
    """Fail closed unless *root* is hosted by a native Linux runtime/filesystem.

    The check intentionally does not require a particular distro name, so the
    same contract works in AgenticOSClean, a cloud VM, or a Linux container.
    """
    raw = str(root)
    if os.name != "posix" or not sys.platform.startswith("linux"):
        raise AuthorityError("authoritative Agentic OS mutation requires Linux/POSIX")
    if PureWindowsPath(raw).is_absolute():
        raise AuthorityError("native Windows paths cannot host authoritative Agentic OS state")
    resolved = Path(root).expanduser().resolve()
    normalized = resolved.as_posix()
    if _WINDOWS_MOUNT_RE.match(normalized):
        raise AuthorityError(f"Windows-mounted roots are not authoritative: {resolved}")
    fs_type, mountpoint, source = filesystem_type(resolved)
    source_lower = source.lower()
    if (
        fs_type in _WINDOWS_FILESYSTEMS
        or fs_type.startswith("fuseblk")
        or "drvfs" in source_lower
        or re.match(r"^[a-z]:", source_lower)
    ):
        raise AuthorityError(
            f"filesystem {fs_type!r} at {mountpoint!r} is Windows-backed; authoritative mutation refused"
        )
    return resolved
