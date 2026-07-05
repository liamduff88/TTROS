"""AOS root and root-relative path helpers."""

from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath


DEFAULT_AOS_ROOT = Path(__file__).resolve().parents[1]


class AosPathError(ValueError):
    """Raised when a path cannot be resolved safely under AOS_ROOT."""


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
