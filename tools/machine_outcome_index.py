"""Deterministic render of the machine-maintained Business Brain outcome index.

The registry is the single source for BOTH membership/order (`evidence_identities`)
and rendered text (`evidence_index_entries`). This module renders the FULL block on
every run and never appends a delta: the marker holds exactly one block, so a partial
render would ERASE previously promoted lines rather than duplicate them.

Adding an entry is a registry change and therefore review-tier. This module refuses
to write when the two registry lists disagree in membership or order.

Revisit: when the marker, the outcome-index contract, or promotion policy changes.
Last touched: 2026-08-14.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import brain_memory
    from business_brain_promotion import PromotionCandidate, PromotionWriter, render_marker_update, sha256_text
except ModuleNotFoundError:  # package import in unittest/IDE contexts
    from tools import brain_memory
    from tools.business_brain_promotion import PromotionCandidate, PromotionWriter, render_marker_update, sha256_text

MARKER = "block-2-outcome-index"
TARGET = "business_brain:index/MEMORY_INDEX.md"
HEADING = "## Machine-maintained verified outcomes"
RELATIVE = "index/MEMORY_INDEX.md"
CHANGE_CLASS = "generated_marker_section"
REASON = "nightly deterministic render of the registered machine outcome index"


class MachineOutcomeIndexError(RuntimeError):
    """The registered outcome index cannot be rendered safely."""


def render_block(registry_data: dict[str, Any], *, client_scope: str = "global") -> tuple[str | None, tuple[str, ...]]:
    """Return (content, provenance_refs). content is None when nothing is registered.

    Returning None is deliberate: rendering an empty block would replace the marker
    body with nothing, destroying existing approved lines.
    """
    scope = (registry_data.get("scopes") or {}).get(client_scope) or {}
    entries = scope.get("evidence_index_entries") or []
    registered = list(scope.get("evidence_identities") or [])
    if not entries:
        return None, tuple(registered)
    identities = [str(entry.get("identity", "")) for entry in entries]
    if identities != registered:
        raise MachineOutcomeIndexError(
            f"outcome index drift: entry identities {identities} != registered {registered}"
        )
    for entry in entries:
        line = str(entry.get("line", ""))
        if not line.startswith("- "):
            raise MachineOutcomeIndexError(f"outcome index entry is not a markdown bullet: {line!r}")
    return "\n".join([HEADING, ""] + [str(e["line"]) for e in entries]), tuple(registered)


def build_candidate(registry_data: dict[str, Any], *, brain_root: Path, client_scope: str = "global"):
    """Return (candidate, preimage, postimage, operation) or None when nothing is registered."""
    content, refs = render_block(registry_data, client_scope=client_scope)
    if content is None:
        return None
    target = Path(brain_root) / RELATIVE
    preimage = target.read_text(encoding="utf-8")
    candidate = PromotionCandidate(
        target=TARGET,
        client_scope=client_scope,
        change_class=CHANGE_CLASS,
        marker=MARKER,
        content=content,
        target_preimage_sha256=sha256_text(preimage),
        provenance_refs=refs,
        reason=REASON,
        # Hashes prove identity but cannot reconstruct historical bytes, and nothing
        # commits this file, so the .patch is the ONLY byte-level audit record.
        safe_for_broad_receipt=True,
    )
    postimage, _prefix, _suffix = render_marker_update(preimage, candidate)
    return candidate, preimage, postimage, ("noop" if postimage == preimage else "write")


def promote(registry, *, repo_root: Path, brain_root: Path, client_scope: str = "global") -> dict[str, Any] | None:
    """Apply the render under the EXISTING vault lock. Returns the writer result, or None.

    The lock is `brain_memory._transaction_lock()` - the same mutex every vault write
    already uses. It is acquired and RELEASED here: it must never be held while
    `brain_memory.write_transaction()` runs, because that re-acquires the same lock on a
    fresh handle and flock would block on the caller's own lock.
    """
    built = build_candidate(registry.data, brain_root=brain_root, client_scope=client_scope)
    if built is None:
        return None
    candidate, _preimage, _postimage, _operation = built
    writer = PromotionWriter(repo_root=Path(repo_root), vault_root=Path(brain_root), registry=registry)
    with brain_memory._transaction_lock():
        return writer.apply(candidate)


def close_refresh(registry, *, repo_root, brain_root, result, search_reference: str, graphify_reference: str):
    """Mark a successful promotion's derived indexes as current.

    Hygiene's freshness detectors are content-derived, so search and Graphify self-heal.
    The RECEIPT does not: without this call every receipt reads `search: pending,
    graphify: stale` forever, including long after hygiene has refreshed them.
    Only a real write needs closing - a noop declares `not_required` itself.
    """
    if not result or result.get("operation") != "write":
        return None
    reference = result.get("durable_reference")
    if not reference:
        return None
    writer = PromotionWriter(repo_root=Path(repo_root), vault_root=Path(brain_root), registry=registry)
    return writer.mark_refresh_complete(
        reference, search_reference=str(search_reference), graphify_reference=str(graphify_reference)
    )
