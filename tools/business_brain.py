"""Canonical logical-pointer resolution for the TTROS Business Brain.

Revisit: when the canonical vault moves or the pointer contract changes. · Last touched: 2026-07-15.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


BUSINESS_BRAIN_PREFIX = "business_brain:"
BUSINESS_BRAIN_ROOT = Path("/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:")


class BusinessBrainPointerError(ValueError):
    """Raised when a Business Brain pointer is absent, ambiguous, or unsafe."""


@dataclass(frozen=True)
class ResolvedBusinessBrainPointer:
    pointer: str
    relative_path: str
    resolved_path: Path


def _canonical_relative_path(value: str) -> str:
    raw = str(value or "")
    if raw != raw.strip() or not raw:
        raise BusinessBrainPointerError("Business Brain relative path must be non-empty and trimmed")
    if "\\" in raw or "\x00" in raw or any(ord(char) < 32 for char in raw):
        raise BusinessBrainPointerError("Business Brain paths must use safe POSIX separators")
    if raw.startswith(("/", "~")) or _WINDOWS_ABSOLUTE_RE.match(raw):
        raise BusinessBrainPointerError("absolute Business Brain paths are prohibited")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise BusinessBrainPointerError("Business Brain path traversal is prohibited")
    if any(part.lower() == "_backups" for part in pure.parts):
        raise BusinessBrainPointerError("Business Brain backups are not canonical retrieval targets")
    canonical = pure.as_posix()
    if canonical != raw:
        raise BusinessBrainPointerError("Business Brain path is not in canonical form")
    return canonical


def resolve_business_brain_pointer(
    pointer: str,
    *,
    require_exists: bool = True,
    root: Path | None = None,
) -> ResolvedBusinessBrainPointer:
    """Resolve one canonical logical pointer without basename lookup or fallback."""
    text = str(pointer or "")
    if not text.startswith(BUSINESS_BRAIN_PREFIX):
        raise BusinessBrainPointerError(f"pointer must start with {BUSINESS_BRAIN_PREFIX}")
    relative = _canonical_relative_path(text[len(BUSINESS_BRAIN_PREFIX) :])
    vault = Path(root) if root is not None else BUSINESS_BRAIN_ROOT
    vault_resolved = vault.resolve()
    candidate = (vault / PurePosixPath(relative)).resolve()
    try:
        candidate.relative_to(vault_resolved)
    except ValueError as exc:
        raise BusinessBrainPointerError("Business Brain pointer escaped the canonical vault") from exc
    if require_exists and not candidate.is_file():
        raise BusinessBrainPointerError(f"Business Brain target does not exist as a file: {relative}")
    return ResolvedBusinessBrainPointer(
        pointer=f"{BUSINESS_BRAIN_PREFIX}{relative}",
        relative_path=relative,
        resolved_path=candidate,
    )


def resolve_optional_business_brain_pointer(
    pointer: str | None,
    *,
    require_exists: bool = True,
    root: Path | None = None,
) -> ResolvedBusinessBrainPointer | None:
    """Return None for absent/non-Brain sources; validate every declared Brain pointer."""
    if pointer is None or not str(pointer).strip():
        return None
    if not str(pointer).startswith(BUSINESS_BRAIN_PREFIX):
        return None
    return resolve_business_brain_pointer(pointer, require_exists=require_exists, root=root)


def business_brain_pointer_for_path(path: Path, *, root: Path | None = None) -> str:
    """Project a canonical vault file to the logical pointer convention."""
    vault = Path(root) if root is not None else BUSINESS_BRAIN_ROOT
    vault_resolved = vault.resolve()
    resolved = Path(path).resolve()
    try:
        relative = resolved.relative_to(vault_resolved).as_posix()
    except ValueError as exc:
        raise BusinessBrainPointerError("path is outside the canonical Business Brain") from exc
    canonical = _canonical_relative_path(relative)
    if not resolved.is_file():
        raise BusinessBrainPointerError("Business Brain pointer targets must be files")
    return f"{BUSINESS_BRAIN_PREFIX}{canonical}"
