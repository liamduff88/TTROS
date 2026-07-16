import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from business_brain_promotion import (
    AUTOMATIC_TIER, NEVER_TIER, REVIEW_TIER, PromotionCandidate, PromotionError,
    PromotionWriter, evaluate_promotion, review_proposal, sha256_text,
)
from tests.business_brain_test_support import make_registry, write_note


class BusinessBrainPromotionTest(unittest.TestCase):
    def fixture(self, root: Path):
        repo, vault = root / "repo", root / "vault"
        (repo / "queue/receipts").mkdir(parents=True)
        (repo / "queue/locks").mkdir(parents=True)
        write_note(vault / "index/MEMORY_INDEX.md", "note-index", "Memory Index", "Human-authored navigation remains exact.")
        write_note(vault / "README.md", "note-root", "Root", "Root")
        write_note(vault / "memory/global.md", "note-global", "Global", "Global")
        write_note(vault / "memory/client-a.md", "note-a", "Client A", "Client A")
        write_note(vault / "memory/client-b.md", "note-b", "Client B", "Client B")
        target = vault / "index/MEMORY_INDEX.md"
        return repo, vault, target, PromotionWriter(repo_root=repo, vault_root=vault, registry=make_registry())

    def candidate(self, target_path: Path, **overrides):
        values = {
            "target": "business_brain:index/MEMORY_INDEX.md",
            "client_scope": "global",
            "change_class": "generated_marker_section",
            "marker": "block-2-outcome-index",
            "content": "## Verified outcomes\n\n- Block 2 fixture outcome.",
            "target_preimage_sha256": sha256_text(target_path.read_text(encoding="utf-8")),
            "provenance_refs": ("proof:block-2:accepted-block-1",),
            "reason": "fixture proof",
            "safe_for_broad_receipt": True,
        }
        values.update(overrides)
        return PromotionCandidate(**values)

    def test_success_duplicate_repeat_and_idempotent_noop_preserve_human_text(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, _vault, target, writer = self.fixture(Path(temp))
            before = target.read_text(encoding="utf-8")
            candidate = self.candidate(target)
            result = writer.apply(candidate)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["tier"], AUTOMATIC_TIER)
            after = target.read_text(encoding="utf-8")
            self.assertTrue(after.startswith(before))
            self.assertIn("TTROS:MACHINE:block-2-outcome-index:BEGIN", after)
            duplicate = writer.apply(candidate)
            self.assertTrue(duplicate["duplicate"])
            self.assertEqual(target.read_text(encoding="utf-8"), after)
            noop_candidate = self.candidate(target)
            noop = writer.apply(noop_candidate)
            self.assertEqual(noop["operation"], "noop")
            self.assertTrue(noop["idempotent"])
            self.assertEqual(target.read_text(encoding="utf-8"), after)
            self.assertTrue((repo / result["durable_reference"]).is_file())

    def test_stale_outside_backup_cross_client_and_unauthorised_marker_rejections(self):
        with tempfile.TemporaryDirectory() as temp:
            _repo, _vault, target, writer = self.fixture(Path(temp))
            before = target.read_bytes()
            with self.assertRaises(PromotionError):
                writer.apply(self.candidate(target, target_preimage_sha256="0" * 64))
            for pointer in ("business_brain:../outside.md", "business_brain:_backups/old.md"):
                with self.assertRaises(PromotionError):
                    writer.apply(self.candidate(target, target=pointer))
            cross = self.candidate(target, target="business_brain:memory/client-b.md", client_scope="client-a")
            self.assertEqual(evaluate_promotion(cross, registry=make_registry())["tier"], NEVER_TIER)
            with self.assertRaises(PromotionError):
                writer.apply(cross)
            unauthorised = self.candidate(target, marker="human-section")
            self.assertEqual(evaluate_promotion(unauthorised, registry=make_registry())["tier"], REVIEW_TIER)
            with self.assertRaises(PromotionError):
                writer.apply(unauthorised)
            self.assertEqual(target.read_bytes(), before)

    def test_review_tier_proposal_no_write_and_duplicate_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            _repo, _vault, target, writer = self.fixture(Path(temp))
            candidate = self.candidate(target, change_class="strategy", reason="synthetic review proof")
            preimage = target.read_text(encoding="utf-8")
            proposal = review_proposal(candidate, preimage=preimage, registry=make_registry())
            self.assertIn("candidate_diff", proposal)
            self.assertEqual(proposal["client_scope"], "global")
            with self.assertRaises(PromotionError):
                writer.apply(candidate)
            self.assertEqual(target.read_text(encoding="utf-8"), preimage)
            accepted = writer.apply(candidate, approval_reference="queue:AOS-TEST:ACCEPT")
            self.assertEqual(accepted["tier"], REVIEW_TIER)
            duplicate = writer.apply(candidate, approval_reference="queue:AOS-TEST:ACCEPT")
            self.assertTrue(duplicate["duplicate"])

    def test_never_and_unclassifiable_tiering(self):
        with tempfile.TemporaryDirectory() as temp:
            _repo, _vault, target, _writer = self.fixture(Path(temp))
            never = self.candidate(target, change_class="credentials")
            never_result = evaluate_promotion(never, registry=make_registry())
            self.assertEqual(never_result["tier"], NEVER_TIER)
            self.assertIsNone(never_result["candidate_diff"])
            unknown = self.candidate(target, change_class="new_unknown_class")
            self.assertEqual(evaluate_promotion(unknown, registry=make_registry())["tier"], REVIEW_TIER)

    def test_malformed_marker_refuses_text_outside_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            _repo, _vault, target, writer = self.fixture(Path(temp))
            with target.open("a", encoding="utf-8") as handle:
                handle.write("<!-- TTROS:MACHINE:block-2-outcome-index:BEGIN -->\nunterminated\n")
            candidate = self.candidate(target)
            before = target.read_bytes()
            with self.assertRaises(PromotionError):
                writer.apply(candidate)
            self.assertEqual(target.read_bytes(), before)

    def test_all_post_mutation_failures_rollback_exact_preimage(self):
        stages = ("partial_write", "post_write_validation", "provenance_write", "run_ledger_linkage")
        for stage in stages:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as temp:
                repo, _vault, target, writer = self.fixture(Path(temp))
                before = target.read_bytes()
                candidate = self.candidate(target)
                with self.assertRaises(PromotionError):
                    writer.apply(candidate, failure_injection=stage)
                self.assertEqual(target.read_bytes(), before)
                receipt = json.loads((repo / "queue/receipts" / f"brain-promotion-{candidate.write_id}.json").read_text())
                self.assertEqual(receipt["status"], "failed")
                self.assertTrue(receipt["rolled_back_to_exact_preimage"])
                self.assertEqual(list((repo / "queue/locks").glob(".brain-promotion-*.preimage.json")), [])

    def test_linker_failure_after_mutation_rolls_back_and_leaves_no_success(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, _vault, target, writer = self.fixture(Path(temp))
            before = target.read_bytes()
            candidate = self.candidate(target)
            with self.assertRaises(PromotionError):
                writer.apply(candidate, ledger_linker=lambda _ref: (_ for _ in ()).throw(RuntimeError("link failed")))
            self.assertEqual(target.read_bytes(), before)
            receipt = json.loads((repo / "queue/receipts" / f"brain-promotion-{candidate.write_id}.json").read_text())
            self.assertEqual(receipt["status"], "failed")

    def test_retry_preserves_failed_attempt_then_publishes_success(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, _vault, target, writer = self.fixture(Path(temp))
            candidate = self.candidate(target)
            with self.assertRaises(PromotionError):
                writer.apply(candidate, failure_injection="post_write_validation")
            success = writer.apply(candidate)
            self.assertEqual(success["status"], "success")
            archived = list((repo / "queue/receipts").glob(f"brain-promotion-{candidate.write_id}-failed-*.json"))
            self.assertEqual(len(archived), 1)
            self.assertEqual(json.loads(archived[0].read_text())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
