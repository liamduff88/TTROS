"""Review-tier Business Brain promotion: file a proposal, dedupe it, read it back.

NOTHING IN THIS MODULE WRITES TO THE BUSINESS BRAIN, AND NOTHING HERE CALLS
`PromotionWriter.apply()`. A review-tier promotion is a proposal until Liam
accepts it. The Brain write, when it eventually happens, goes through the
already-proven `PromotionWriter` path with an approval reference that only a
human can supply.

Three halves of Stage 2 live here, and each one copies an existing precedent
rather than inventing a mechanism:

* `build_proposal()` derives the filed payload from
  `business_brain_promotion.review_proposal()`. The seven fields that function
  already returns are the schema; nothing is added that it does not know.
* `PromotionReviewQueue.create_or_get()` is `aos_capture.CaptureQueueWriter.
  create_or_get()` with `capture_proposal` swapped for `promotion_proposal`.
  The `proposal_key` dedupe runs inside `queue_write_lock`, so a concurrent
  filer cannot slip a duplicate between the read and the write.
* `list_proposals()` / `review_view()` / `render_for_review()` are the consumer
  that was missing. Before this module, `promotion_proposal` was a real work
  item field with a real `aos-queue.py create --promotion-proposal` flag and
  ZERO readers anywhere in the tree.

The consumer is deliberately pure. It reads the queue, reads the vault, and
returns a rendering. It does not call the writer even to demonstrate that the
writer refuses - that refusal is proven directly in
`tests/test_promotion_review_tier.py`. A reader that also attempts a write is a
third detector, and every recorded instrument failure in this project has come
from a third detector added for safety.

Revisit: when promotion authority tiers change or an automatic class is enabled.
Last touched: 2026-08-15.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from tools.aos_paths import aos_root
from tools.aos_queue_storage import durable_replace_text

# ONE canonical import, and both halves of it are deliberate.
#
# 1. No `try: from business_brain_promotion ... except ModuleNotFoundError:`
#    fallback. `tools/` is on sys.path at runtime, so the bare form SUCCEEDS and
#    Python loads business_brain_promotion.py a second time under a second name.
#    The two module objects define two distinct PromotionError classes, and an
#    `except PromotionError` written against the wrong one silently fails to
#    catch. That is not hypothetical: it produced both remaining Stage 2 test
#    failures, once in each direction. Nothing imports this module bare - it is
#    reached as `tools.promotion_review_queue` by its tests and by
#    `python -m tools.promotion_review_queue` - so the fallback bought nothing
#    and cost class identity.
#
# 2. ClientScopeError, ClientScopeRegistry and load_registry are taken from
#    business_brain_promotion rather than from business_brain_scope directly.
#    They are the same objects that module resolved for itself, so a registry
#    built here raises exactly the exception class `evaluate_promotion()` is
#    prepared to catch. Importing them from business_brain_scope would look
#    tidier and would hand evaluate_promotion() a registry whose ClientScopeError
#    it cannot catch, turning a clean `never_promote` verdict into an escaping
#    exception.
from tools.business_brain_promotion import (
    REVIEW_TIER,
    ClientScopeError,
    ClientScopeRegistry,
    PromotionCandidate,
    PromotionError,
    load_registry,
    review_proposal,
    sha256_text,
)


REPO_ROOT = aos_root()
PROPOSAL_SCHEMA_VERSION = 1

# A filed proposal has exactly one state. Approval is a separate act performed by
# Liam, not a field this module may flip - so there is no "approved" value to set.
APPROVAL_STATE = "awaiting_liam_review"

PROMPT_RELATIVE = Path("queue/memory_promotion_prompt.md")


class PromotionReviewError(RuntimeError):
    """A review-tier proposal cannot be filed or read back safely."""


def stable_hash(*parts: object) -> str:
    """Unit-separator joined sha256, byte-identical to `aos_capture.stable_hash`.

    Duplicated on purpose: promotion must not import the capture runtime just to
    borrow four lines. `test_stable_hash_matches_capture_construction` asserts the
    two stay equal, so the duplication cannot drift silently.
    """
    return hashlib.sha256("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()


_QUEUE_TOOL = None


def _queue_tool():
    """Load `tools/aos-queue.py`, whose hyphen makes it unimportable normally."""
    global _QUEUE_TOOL
    if _QUEUE_TOOL is None:
        path = REPO_ROOT / "tools" / "aos-queue.py"
        spec = importlib.util.spec_from_file_location("aos_queue_promotion_review", path)
        if spec is None or spec.loader is None:
            raise PromotionReviewError("existing queue tool could not be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _QUEUE_TOOL = module
    return _QUEUE_TOOL


# --------------------------------------------------------------------------- file

def build_proposal(
    candidate: PromotionCandidate,
    *,
    preimage: str,
    registry: ClientScopeRegistry | None = None,
) -> dict[str, Any]:
    """Derive the filed payload from `review_proposal()`. Adds no new authority.

    `review_proposal()` raises unless the candidate genuinely evaluates to the
    review tier, so an automatic-class or never-promote candidate cannot be
    filed as a review proposal by mistake.
    """
    review = review_proposal(candidate, preimage=preimage, registry=registry)
    return {
        "schema_version": PROPOSAL_SCHEMA_VERSION,
        "proposal_key": proposal_key_for(review["write_id"], review["canonical_target"]),
        "write_id": review["write_id"],
        "canonical_target": review["canonical_target"],
        "client_scope": review["client_scope"],
        "change_class": candidate.change_class,
        "marker": candidate.marker,
        "target_preimage_hash": review["target_preimage_hash"],
        "candidate_diff": review["candidate_diff"],
        "source_provenance_references": list(review["source_provenance_references"]),
        "reason_for_review_tier": review["reason_for_review_tier"],
        "approval_state": APPROVAL_STATE,
        "receipt_reference": "pending",
        "auto_apply": False,
        "external_actions_allowed": False,
    }


def proposal_key_for(write_id: str, canonical_target: str) -> str:
    """Dedupe identity. `write_id` already hashes the whole candidate, so two
    proposals collide only when they would produce the identical vault write."""
    return stable_hash("promotion-proposal", write_id, canonical_target)


class PromotionReviewQueue:
    def __init__(self, root: Path = REPO_ROOT):
        self.root = Path(root).resolve()

    def create_or_get(self, *, proposal: dict[str, Any]) -> tuple[dict[str, Any], bool, str]:
        """File one review-tier proposal, or return the one already filed.

        Returns (item, created, receipt_path). `created` is False on the dedupe
        path, and on that path nothing at all is written - no item, no receipt,
        no queue mutation.
        """
        if proposal.get("approval_state") != APPROVAL_STATE:
            raise PromotionReviewError(
                f"a proposal may only be filed in state {APPROVAL_STATE!r}"
            )
        if proposal.get("auto_apply") is not False:
            raise PromotionReviewError("a review-tier proposal may never be marked auto_apply")
        tool = _queue_tool()
        key = str(proposal["proposal_key"])
        with tool.queue_write_lock(self.root):
            tool.ensure_queue(self.root)
            items = tool.load_items(self.root)
            existing = next(
                (row for row in items if (row.get("promotion_proposal") or {}).get("proposal_key") == key),
                None,
            )
            if existing:
                latest = (existing.get("receipts") or [{}])[-1]
                reference = str(latest.get("path") or "") if isinstance(latest, dict) else str(latest)
                return existing, False, reference

            args = argparse.Namespace(
                title=f"Business Brain promotion needs review: {proposal['canonical_target']}",
                requested_by="Stage 2 review-tier promotion",
                owner_type="agent",
                owner="operations",
                status="human_review",
                priority=1,
                source="business_brain/promotion-review",
                tags="stage-2-review-tier,proposed_from_promotion",
                context=(
                    "A Business Brain change reached the Liam-review tier and is filed as a proposal. "
                    f"Reason: {proposal['reason_for_review_tier']}. "
                    "Nothing has been written to the vault and nothing will be until Liam approves."
                ),
                sources=",".join(proposal.get("source_provenance_references") or []),
                allowed_actions="local_read,local_review",
                stop_conditions="external_send,connector_action,brain_auto_promotion,vault_write",
                definition_of_done=(
                    "Liam accepts or rejects the proposed Business Brain change. "
                    "Acceptance is recorded as a human_review reference; only then may the promotion writer run."
                ),
                parent_id=None,
                step_index=None,
                depends_on="",
                on_complete=None,
                workbench=None,
                client_scope=proposal.get("client_scope") or "",
                context_classification="knowledge_sensitive",
                brain_context_status="used",
                # Shape is dictated by the work-item schema: note_id, path,
                # client_scope and retrieval_route are required and
                # additionalProperties is false. Do not add fields here.
                brain_context_used=json.dumps([
                    {
                        "note_id": proposal["canonical_target"].split(":", 1)[-1],
                        "path": proposal["canonical_target"],
                        "client_scope": proposal.get("client_scope") or "global",
                        "retrieval_route": "pointer",
                        "content_sha256": proposal["target_preimage_hash"],
                    }
                ]),
                degraded_context=None,
                promotion_proposal=json.dumps(proposal),
                capture_proposal=None,
            )
            item = tool.create_item(self.root, args)
            receipt_path = f"queue/receipts/{item['id']}-stage-2-promotion-review.json"
            receipt = {
                "schema_version": 1,
                "item_id": item["id"],
                "status": "human_review",
                "proposal_key": key,
                "write_id": proposal["write_id"],
                "canonical_target": proposal["canonical_target"],
                "client_scope": proposal.get("client_scope"),
                "change_class": proposal["change_class"],
                "reason_for_review_tier": proposal["reason_for_review_tier"],
                "source_provenance_references": proposal.get("source_provenance_references") or [],
                "approval_state": APPROVAL_STATE,
                "vault_bytes_written": 0,
                "external_action": "none",
                "token_usage_text": "Token usage: no agent invocation",
            }
            durable_replace_text(
                self.root / receipt_path,
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            )
            item = tool.attach_receipt(self.root, item["id"], receipt_path, "human_review")
            items = tool.load_items(self.root)
            item = tool.find_item(items, item["id"])
            item["promotion_proposal"]["receipt_reference"] = receipt_path
            item["updated_at"] = tool.now_iso()
            tool.save_items(self.root, items)
        return item, True, receipt_path


# ----------------------------------------------------------------------- consume

def list_proposals(root: Path = REPO_ROOT, *, status: str | None = None) -> list[dict[str, Any]]:
    """Every work item carrying a review-tier promotion proposal. Read-only."""
    tool = _queue_tool()
    root = Path(root).resolve()
    # `load_items()` raises QueueError when the ledger file does not exist. That is
    # correct for a mutator - refusing to write into a queue that was never created
    # is the safe behaviour - and wrong for a reader. "Nothing is filed" is an
    # answer, not an error, and a consumer that crashes on an empty queue would
    # fail on exactly the day it has nothing to report.
    if not (root / tool.WORK_ITEMS_PATH).exists():
        return []
    items = tool.load_items(root)
    found = [row for row in items if isinstance(row.get("promotion_proposal"), dict)]
    if status is not None:
        found = [row for row in found if row.get("status") == status]
    return found


def review_view(
    item: dict[str, Any],
    *,
    brain_root: Path,
    registry: ClientScopeRegistry | None = None,
) -> dict[str, Any]:
    """Everything Liam needs in order to decide, plus whether it is still current.

    Reads the queue item and the vault file. Writes nothing. Never calls the
    promotion writer.

    Two judgements are derived rather than trusted:

    * `proposal_key_consistent` recomputes the dedupe key from the stored
      `write_id` and target. A stored key that disagrees means the record was
      edited after filing.
    * `target_current` re-reads the Brain file and compares its sha256 to the
      preimage the diff was computed against. False means the vault moved under
      the proposal and the diff no longer describes the change that would be
      made. This is the detector that must be able to say NO, and
      `test_consumer_detects_a_moved_target` exercises exactly that path.
    """
    proposal = item.get("promotion_proposal")
    if not isinstance(proposal, dict):
        raise PromotionReviewError(f"work item {item.get('id')!r} carries no promotion_proposal")

    expected_key = proposal_key_for(proposal["write_id"], proposal["canonical_target"])
    key_consistent = expected_key == proposal.get("proposal_key")

    gate = registry or load_registry()
    scope = proposal.get("client_scope") or None
    target_current: bool | None
    current_hash: str | None
    resolution_error: str | None = None
    try:
        resolved = gate.resolve_brain_pointer(scope, proposal["canonical_target"], root=Path(brain_root))
        current_hash = sha256_text(resolved.resolved_path.read_text(encoding="utf-8"))
        target_current = current_hash == proposal["target_preimage_hash"]
    except (ClientScopeError, OSError) as exc:
        current_hash = None
        target_current = None
        resolution_error = str(exc)

    return {
        "item_id": item.get("id"),
        "status": item.get("status"),
        "tier": REVIEW_TIER,
        "approval_state": proposal.get("approval_state"),
        "canonical_target": proposal["canonical_target"],
        "client_scope": scope,
        "change_class": proposal["change_class"],
        "marker": proposal["marker"],
        "write_id": proposal["write_id"],
        "reason_for_review_tier": proposal["reason_for_review_tier"],
        "source_provenance_references": list(proposal.get("source_provenance_references") or []),
        "candidate_diff": proposal["candidate_diff"],
        "target_preimage_hash": proposal["target_preimage_hash"],
        "target_current_hash": current_hash,
        "target_current": target_current,
        "resolution_error": resolution_error,
        "proposal_key_consistent": key_consistent,
        "receipt_reference": proposal.get("receipt_reference"),
        "vault_bytes_written": 0,
    }


# ------------------------------------------------------------------ prompt loader

def load_promotion_prompt(root: Path = REPO_ROOT) -> str:
    """Read the memory-promotion template from where it actually lives.

    The template's own first line calls it `queue/templates/memory_promotion.prompt.md`
    while the file sits at `queue/memory_promotion_prompt.md`. Before this loader it
    had zero Python references anywhere, so correcting the path alone would have
    ignited nothing. The path is left as-is deliberately - moving the file and
    wiring the loader in the same step would change two things at once.
    """
    path = Path(root).resolve() / PROMPT_RELATIVE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PromotionReviewError(f"memory promotion template is unreadable at {path}: {exc}") from exc
    if not text.strip():
        raise PromotionReviewError(f"memory promotion template is empty at {path}")
    return text


def _added_lines(diff: str) -> str:
    added = [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    return "\n".join(added).strip() or "(no added lines)"


def render_for_review(view: dict[str, Any], *, root: Path = REPO_ROOT) -> str:
    """Fill the memory-promotion template from a filed proposal.

    Placeholders are replaced by explicit substitution rather than `str.format`,
    so an unknown field in the template cannot raise KeyError mid-render and a
    literal brace in the body cannot be mistaken for a placeholder.
    """
    template = load_promotion_prompt(root)
    provenance = ", ".join(view["source_provenance_references"]) or "(none)"
    substitutions = {
        "{item_id}": str(view["item_id"]),
        "{lane}": "business_brain_promotion / review tier",
        "{proposed_change}": _added_lines(view["candidate_diff"]),
        "{target_memory_file}": view["canonical_target"],
        "{source_pointer}": provenance,
        "{provenance_references}": provenance,
        "{client_scope}": str(view["client_scope"]),
        "{target_preimage_sha256}": view["target_preimage_hash"],
        "{candidate_diff}": view["candidate_diff"],
        "{authority_tier_reason}": f"{view['tier']} - {view['reason_for_review_tier']}",
    }
    rendered = template
    for placeholder, value in substitutions.items():
        rendered = rendered.replace(placeholder, value)

    if view["target_current"] is False:
        rendered += (
            "\n\n> STALE: the target file has changed since this proposal was filed.\n"
            f"> Filed against {view['target_preimage_hash'][:16]}…, "
            f"now {str(view['target_current_hash'])[:16]}…\n"
            "> The diff above no longer describes the change that would be made. "
            "Re-file before approving.\n"
        )
    elif view["target_current"] is None:
        rendered += (
            "\n\n> UNVERIFIED: the target could not be read, so staleness is unknown.\n"
            f"> {view['resolution_error']}\n"
        )
    if not view["proposal_key_consistent"]:
        rendered += (
            "\n\n> KEY MISMATCH: the stored proposal_key does not match the stored "
            "write_id and target. This record was altered after it was filed.\n"
        )
    return rendered


# ------------------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read filed review-tier Business Brain promotion proposals. Never writes."
    )
    parser.add_argument("command", choices=["list", "show"])
    parser.add_argument("item_id", nargs="?", default=None)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--brain-root", type=Path, default=None)
    args = parser.parse_args(argv)

    items = list_proposals(args.root)
    if args.command == "list":
        if not items:
            print("No review-tier promotion proposals are filed.")
            return 0
        for row in items:
            proposal = row["promotion_proposal"]
            print(f"{row['id']}  {row['status']:<13} {proposal['canonical_target']}  {proposal['reason_for_review_tier']}")
        return 0

    if not args.item_id:
        parser.error("show requires an item id")
    match = next((row for row in items if row.get("id") == args.item_id), None)
    if match is None:
        print(f"No filed promotion proposal for {args.item_id}")
        return 1
    brain_root = args.brain_root
    if brain_root is None:
        parser.error("show requires --brain-root")
    print(render_for_review(review_view(match, brain_root=brain_root), root=args.root))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
