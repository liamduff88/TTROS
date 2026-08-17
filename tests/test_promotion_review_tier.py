"""Stage 2: review-tier Business Brain promotion - file, dedupe, read back, render.

Every test here asserts that NOTHING was written to the vault. The one test that
touches `PromotionWriter.apply()` asserts only that it REFUSES, and it is kept
separate from the consumer on purpose: the consumer must never call the writer,
so the refusal cannot be proven through it.

Revisit: when promotion authority tiers change. · Last touched: 2026-08-15.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

# `tests/business_brain_test_support.py` imports `business_brain_scope` bare, so it
# only resolves when tools/ is on sys.path. There is no conftest.py in this repo;
# the path is inserted as a SIDE EFFECT of importing
# dashboard/backend/business_brain_graph.py (lines 27-28), which is why
# test_aos_capture.py collects standalone and this file did not - it imports the
# graph service first and this one has no reason to.
#
# Stating the dependency here is deliberate. Importing a graph service purely for
# its side effect would work and would be invisible, which is exactly how the
# hygiene sys.path coupling already recorded in 00 came about.
_TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from tests.business_brain_test_support import make_registry, registry_data
from tools.aos_capture import stable_hash as capture_stable_hash
# PromotionError is taken from the canonical module, and the assertions below
# are exact. Both remaining Stage 2 failures were duplicate-module identity
# mismatches - business_brain_promotion.py loaded twice under two names, giving
# two distinct PromotionError classes. That was fixed in
# tools/promotion_review_queue.py by removing its bare-import fallback, not
# softened here. If the duplicate ever returns, these assertRaises calls fail
# again, which is the behaviour worth keeping.
from tools.business_brain_promotion import (
    PromotionCandidate,
    PromotionError,
    PromotionWriter,
    evaluate_promotion,
    sha256_text,
)
from tools.promotion_review_queue import (
    APPROVAL_STATE,
    PromotionReviewError,
    PromotionReviewQueue,
    build_proposal,
    list_proposals,
    load_promotion_prompt,
    proposal_key_for,
    render_for_review,
    review_view,
    stable_hash,
)


ROOT = Path(__file__).resolve().parents[1]

# The one automatic class that is enabled. Used as a known-negative: a candidate
# in this class must NOT be fileable as a review proposal.
AUTOMATIC_TARGET = "business_brain:index/MEMORY_INDEX.md"
AUTOMATIC_MARKER = "block-2-outcome-index"


class ReviewTierTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.repo = base / "repo"
        self.brain = base / "brain"
        (self.repo / "queue").mkdir(parents=True)
        (self.brain / "memory").mkdir(parents=True)
        (self.brain / "index").mkdir(parents=True)

        for relative in (
            "queue/run_ledger_schema.json",
            "queue/token_ledger_schema.json",
            "queue/schemas/work_item.schema.json",
            "queue/schemas/receipt.schema.json",
        ):
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        shutil.copyfile(ROOT / "queue/memory_promotion_prompt.md", self.repo / "queue/memory_promotion_prompt.md")

        self.target_path = self.brain / "memory" / "global.md"
        self.target_path.write_text("# Global\n\nExisting durable content.\n", encoding="utf-8")
        self.index_path = self.brain / "index" / "MEMORY_INDEX.md"
        self.index_path.write_text("# Memory index\n", encoding="utf-8")

        self.registry = make_registry(registry_data())
        self.queue = PromotionReviewQueue(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    # -- helpers ---------------------------------------------------------

    def candidate(self, *, content: str = "Rendered by the outcome index contract.") -> PromotionCandidate:
        preimage = self.target_path.read_text(encoding="utf-8")
        return PromotionCandidate(
            target="business_brain:memory/global.md",
            client_scope="global",
            change_class="architecture_change",
            marker="promotion-render-contract",
            content=content,
            target_preimage_sha256=sha256_text(preimage),
            provenance_refs=("proof:block-2:deterministic-write",),
            reason="review-tier architecture fact",
        )

    def proposal(self, **kwargs) -> dict:
        candidate = self.candidate(**kwargs)
        preimage = self.target_path.read_text(encoding="utf-8")
        return build_proposal(candidate, preimage=preimage, registry=self.registry)

    def vault_state(self) -> dict[str, str]:
        return {
            str(path.relative_to(self.brain)): sha256_text(path.read_text(encoding="utf-8"))
            for path in sorted(self.brain.rglob("*"))
            if path.is_file()
        }

    # -- 1 ---------------------------------------------------------------

    def test_filed_item_validates_against_the_work_item_schema(self):
        """The schema only bites because a test asserts it. Nothing in the runtime
        validates work items against work_item.schema.json - measured 2026-08-15."""
        item, created, receipt_path = self.queue.create_or_get(proposal=self.proposal())
        self.assertTrue(created)

        schema = json.loads((ROOT / "queue/schemas/work_item.schema.json").read_text(encoding="utf-8"))
        receipt_schema = json.loads((ROOT / "queue/schemas/receipt.schema.json").read_text(encoding="utf-8"))
        resolver = jsonschema.RefResolver.from_schema(schema, store={receipt_schema["$id"]: receipt_schema})
        jsonschema.Draft202012Validator(schema, resolver=resolver).validate(item)

        filed = item["promotion_proposal"]
        self.assertEqual(APPROVAL_STATE, filed["approval_state"])
        self.assertFalse(filed["auto_apply"])
        self.assertEqual(receipt_path, filed["receipt_reference"])
        self.assertEqual("human_review", item["status"])

        receipt = json.loads((self.repo / receipt_path).read_text(encoding="utf-8"))
        self.assertEqual(0, receipt["vault_bytes_written"])
        self.assertEqual("none", receipt["external_action"])

    def test_a_bare_object_would_have_passed_so_the_schema_block_is_load_bearing(self):
        """Rehearses the detector against a known-negative.

        Before Stage 2 `promotion_proposal` was `{"type": "object"}`, which accepts
        anything. If the schema block were still bare, garbage would validate. This
        asserts the new block actually rejects a malformed proposal - otherwise the
        test above passes for the wrong reason."""
        schema = json.loads((ROOT / "queue/schemas/work_item.schema.json").read_text(encoding="utf-8"))
        block = schema["properties"]["promotion_proposal"]
        self.assertNotEqual({"type": "object"}, block)

        validator = jsonschema.Draft202012Validator(block)
        with self.assertRaises(jsonschema.ValidationError):
            validator.validate({"nonsense": True})
        with self.assertRaises(jsonschema.ValidationError):
            bad = self.proposal()
            bad["approval_state"] = "approved"
            validator.validate(bad)
        validator.validate(self.proposal())

    # -- 2 ---------------------------------------------------------------

    def test_second_file_dedupes_and_writes_nothing_new(self):
        first, created_first, receipt_first = self.queue.create_or_get(proposal=self.proposal())
        items_after_first = json.loads(json.dumps(list_proposals(self.repo)))

        second, created_second, receipt_second = self.queue.create_or_get(proposal=self.proposal())
        items_after_second = list_proposals(self.repo)

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(receipt_first, receipt_second)
        self.assertEqual(1, len(items_after_second))
        self.assertEqual(items_after_first, items_after_second)

        receipts = sorted(p.name for p in (self.repo / "queue/receipts").glob("*.json"))
        self.assertEqual(1, len(receipts))

    def test_a_different_candidate_is_not_deduped(self):
        """The dedupe detector must be able to say NO as well as YES."""
        first, created_first, _ = self.queue.create_or_get(proposal=self.proposal())
        other = self.proposal(content="A materially different durable fact.")
        second, created_second, _ = self.queue.create_or_get(proposal=other)

        self.assertTrue(created_first)
        self.assertTrue(created_second)
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(
            first["promotion_proposal"]["proposal_key"],
            second["promotion_proposal"]["proposal_key"],
        )
        self.assertEqual(2, len(list_proposals(self.repo)))

    # -- 3 ---------------------------------------------------------------

    def test_apply_refuses_review_tier_without_an_approval_reference(self):
        """Proven directly, never through the consumer. The consumer must not call
        the writer at all, so this refusal cannot be demonstrated from there."""
        candidate = self.candidate()
        evaluation = evaluate_promotion(candidate, registry=self.registry)
        self.assertEqual("liam_review_required", evaluation["tier"])
        self.assertFalse(evaluation["writable"])

        writer = PromotionWriter(repo_root=self.repo, vault_root=self.brain, registry=self.registry)
        before = self.vault_state()
        with self.assertRaises(PromotionError) as raised:
            writer.apply(candidate)
        self.assertIn("no accepted human_review reference", str(raised.exception))
        self.assertEqual(before, self.vault_state())

    def test_an_automatic_class_candidate_cannot_be_filed_as_a_review_proposal(self):
        """build_proposal() delegates the tier decision to review_proposal(), which
        refuses anything that is not genuinely review-tier."""
        preimage = self.index_path.read_text(encoding="utf-8")
        automatic = PromotionCandidate(
            target=AUTOMATIC_TARGET,
            client_scope="global",
            change_class="generated_marker_section",
            marker=AUTOMATIC_MARKER,
            content="- machine rendered line",
            target_preimage_sha256=sha256_text(preimage),
            provenance_refs=("proof:block-2:deterministic-write",),
            reason="automatic render",
        )
        with self.assertRaises(PromotionError):
            build_proposal(automatic, preimage=preimage, registry=self.registry)

    def test_a_proposal_may_not_be_filed_pre_approved(self):
        tampered = self.proposal()
        tampered["approval_state"] = "approved"
        with self.assertRaises(PromotionReviewError):
            self.queue.create_or_get(proposal=tampered)

        auto = self.proposal()
        auto["auto_apply"] = True
        with self.assertRaises(PromotionReviewError):
            self.queue.create_or_get(proposal=auto)

        self.assertEqual([], list_proposals(self.repo))

    # -- 4 ---------------------------------------------------------------

    def test_consumer_reads_the_proposal_back_and_leaves_the_vault_untouched(self):
        item, _, _ = self.queue.create_or_get(proposal=self.proposal())
        before = self.vault_state()

        filed = next(row for row in list_proposals(self.repo) if row["id"] == item["id"])
        view = review_view(filed, brain_root=self.brain, registry=self.registry)

        self.assertEqual(item["id"], view["item_id"])
        self.assertEqual("liam_review_required", view["tier"])
        self.assertEqual(APPROVAL_STATE, view["approval_state"])
        self.assertEqual("business_brain:memory/global.md", view["canonical_target"])
        self.assertEqual(["proof:block-2:deterministic-write"], view["source_provenance_references"])
        self.assertTrue(view["proposal_key_consistent"])
        self.assertTrue(view["target_current"])
        self.assertIsNone(view["resolution_error"])
        self.assertIn("Rendered by the outcome index contract.", view["candidate_diff"])
        self.assertEqual(0, view["vault_bytes_written"])
        self.assertEqual(before, self.vault_state())

    # -- 5 ---------------------------------------------------------------

    def test_consumer_detects_a_moved_target(self):
        """The staleness detector must be able to return NO on the real path."""
        item, _, _ = self.queue.create_or_get(proposal=self.proposal())
        filed = next(row for row in list_proposals(self.repo) if row["id"] == item["id"])

        fresh = review_view(filed, brain_root=self.brain, registry=self.registry)
        self.assertTrue(fresh["target_current"])

        self.target_path.write_text("# Global\n\nSomething else entirely.\n", encoding="utf-8")
        stale = review_view(filed, brain_root=self.brain, registry=self.registry)

        self.assertFalse(stale["target_current"])
        self.assertNotEqual(stale["target_current_hash"], stale["target_preimage_hash"])
        self.assertIn("STALE", render_for_review(stale, root=self.repo))

    def test_consumer_detects_a_tampered_proposal_key(self):
        item, _, _ = self.queue.create_or_get(proposal=self.proposal())
        filed = next(row for row in list_proposals(self.repo) if row["id"] == item["id"])
        filed["promotion_proposal"]["proposal_key"] = "0" * 64

        view = review_view(filed, brain_root=self.brain, registry=self.registry)
        self.assertFalse(view["proposal_key_consistent"])
        self.assertIn("KEY MISMATCH", render_for_review(view, root=self.repo))

    # -- 6 ---------------------------------------------------------------

    def test_stable_hash_matches_capture_construction(self):
        """The four-line duplicate must not drift from the capture original."""
        for parts in (
            ("promotion-proposal", "abc", "business_brain:memory/global.md"),
            ("a",),
            ("", "b"),
        ):
            self.assertEqual(capture_stable_hash(*parts), stable_hash(*parts))

    def test_proposal_key_is_derived_not_stored_blindly(self):
        proposal = self.proposal()
        self.assertEqual(
            proposal_key_for(proposal["write_id"], proposal["canonical_target"]),
            proposal["proposal_key"],
        )

    # -- 7 ---------------------------------------------------------------

    def test_rendered_review_leaves_no_placeholder_unfilled(self):
        """Piece 4: the template had ZERO Python references before this loader."""
        template = load_promotion_prompt(self.repo)
        self.assertIn("{candidate_diff}", template)

        item, _, _ = self.queue.create_or_get(proposal=self.proposal())
        filed = next(row for row in list_proposals(self.repo) if row["id"] == item["id"])
        rendered = render_for_review(review_view(filed, brain_root=self.brain, registry=self.registry), root=self.repo)

        for placeholder in (
            "{item_id}", "{lane}", "{proposed_change}", "{target_memory_file}",
            "{source_pointer}", "{client_scope}", "{target_preimage_sha256}",
            "{candidate_diff}", "{provenance_references}", "{authority_tier_reason}",
        ):
            self.assertNotIn(placeholder, rendered)
        self.assertIn(item["id"], rendered)
        self.assertIn("business_brain:memory/global.md", rendered)
        self.assertIn("proof:block-2:deterministic-write", rendered)
        self.assertIn("liam_review_required", rendered)

    def test_prompt_loader_refuses_an_empty_template(self):
        (self.repo / "queue/memory_promotion_prompt.md").write_text("   \n", encoding="utf-8")
        with self.assertRaises(PromotionReviewError):
            load_promotion_prompt(self.repo)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
