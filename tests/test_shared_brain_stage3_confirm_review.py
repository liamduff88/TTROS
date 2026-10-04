"""S3-11: the queue review must not read a Shared Brain record path as a `packets/` artifact claim.

AOS-2026-0524 (2026-10-04): the worker cited `inbox/distilled_packets/shared-submit-<hex>.md` and
the review blocked on `packets/shared-submit-<hex>.md`, a substring of that Brain path.

Revisit: when the queue artifact-claim contract changes. Last touched: 2026-10-04.
"""
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RECORD = "inbox/distilled_packets/shared-submit-4aa6ab0fb5595f52032e5d4a8dd9087b.md"
REVIEW_PASS = {"success": True, "output": "PASS", "returncode": 0}


class SharedBrainConfirmReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = importlib.import_module("dashboard.backend.main")

    def test_brain_record_path_is_not_a_packets_claim_but_a_real_missing_claim_still_blocks(self):
        item = {"id": "AOS-2026-0524", "title": "Inspect Shared Brain record and run existing confirmation path only if unconfirmed",
                "owner": "operations", "claim": {"claimed_at": None}}
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(self.main, "BASE_DIR", Path(temp)):
            artifact = self.main._queue_default_artifact_path(item)
            (Path(temp) / artifact).parent.mkdir(parents=True)
            (Path(temp) / artifact).write_text("PASS\n", encoding="utf-8")
            output = (
                f"PASS\nFiles touched:\n- {artifact}\n"
                f"- /mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain/{RECORD}\n"
                f"Validation: confirmed business_brain:{RECORD} (status: confirmed)\n"
            )
            self.assertEqual(self.main._queue_artifact_candidates_from_text(output), [artifact])
            self.assertEqual(self.main._queue_review_decision(item, {"output": output}, REVIEW_PASS), ("PASS", "PASS"))
            missing = output + "Artifacts:\n- packets/shared-submit-missing.md\n"
            decision, reason = self.main._queue_review_decision(item, {"output": missing}, REVIEW_PASS)
        self.assertEqual(decision, "REVISE")
        self.assertIn("Claimed canonical artifact is genuinely absent: packets/shared-submit-missing.md", reason)
        # Absolute repo paths still yield their root-relative claim.
        self.assertEqual(
            self.main._queue_artifact_candidates_from_text("See /home/liam/agentic-os-live/logs/local_agent_route.jsonl."),
            ["logs/local_agent_route.jsonl"],
        )


if __name__ == "__main__":
    unittest.main()
