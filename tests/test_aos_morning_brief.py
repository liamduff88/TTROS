"""Focused complete-path tests for the local David morning brief.

Revisit: when the morning detector, Ask David response, or delivery contract changes. · Last touched: 2026-08-17.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools import aos_morning_brief


class MorningBriefPathTests(unittest.TestCase):
    def detector(self, root: Path, **_kwargs):
        target = root / aos_morning_brief.FINDINGS_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({
            "observed_at": "2026-08-17T15:00:00Z",
            "finding_count": 1,
            "findings": [{"finding_id": "morning-fixture"}],
            "token_usage": dict(aos_morning_brief.DETECTOR_USAGE),
        }), encoding="utf-8")
        return SimpleNamespace(exit_code=0, reason="")

    @staticmethod
    def response(*, queue_unchanged: bool = True) -> dict:
        return {
            "success": True,
            "kind": "david_reply",
            "response": "\n".join((
                "## What matters today",
                "- Resolve the one supported priority.",
                "## Why it matters and current evidence",
                "- Current queue evidence shows it is unresolved.",
                "## Liam decisions / next focus",
                "- Choose the supported next focus.",
            )),
            "invocation_id": "invocation-fixture",
            "queue_effect": {"unchanged": queue_unchanged, "items_created": 0},
            "context": {"total_bytes": 1234, "total_tokens": 321},
            "token_usage": {
                "available": True,
                "completed": True,
                "failed": False,
                "provider": "fixture",
                "model": "fixture-model",
                "input_tokens": 100,
                "cache_read_tokens": 20,
                "output_tokens": 30,
                "reasoning_tokens": 4,
                "total_tokens": 130,
            },
        }

    def test_complete_path_writes_one_local_interpreted_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = aos_morning_brief.run(
                root=root,
                refresh_fn=self.detector,
                post_json=lambda _endpoint, _payload: self.response(),
                now=dt.datetime(2026, 8, 17, 15, 0, tzinfo=dt.timezone.utc),
            )
            content = (root / aos_morning_brief.OUTPUT_REL).read_text(encoding="utf-8")
        self.assertTrue(result["success"])
        self.assertEqual("local_generated_artifact", result["delivery"]["type"])
        self.assertIn("Detector token usage: 0 model invocations, 0 input, 0 output", content)
        self.assertIn("## What matters today", content)
        self.assertIn("Actual usage: input 100, cached input 20, output 30, reasoning 4, total 130", content)

    def test_dry_run_reaches_delivery_boundary_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = aos_morning_brief.run(
                root=root,
                dry_run=True,
                refresh_fn=self.detector,
                post_json=lambda _endpoint, _payload: self.response(),
            )
            self.assertFalse((root / aos_morning_brief.OUTPUT_REL).exists())
        self.assertFalse(result["delivery"]["written"])

    def test_queue_mutation_fails_before_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(aos_morning_brief.MorningBriefRunError, "zero-queue"):
                aos_morning_brief.run(
                    root=root,
                    refresh_fn=self.detector,
                    post_json=lambda _endpoint, _payload: self.response(queue_unchanged=False),
                )
            self.assertFalse((root / aos_morning_brief.OUTPUT_REL).exists())

    def test_authorized_delivery_sends_the_exact_artifact_once_to_both_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            emails = []
            telegrams = []
            david_calls = []

            def email(delivery_root, recipient, subject, body):
                emails.append((delivery_root, recipient, subject, body))
                return {"provider": "agentmail-fixture", "provider_message_id": "agentmail-1", "acknowledged": True}

            def telegram(delivery_root, body):
                telegrams.append((delivery_root, body))
                return {"provider": "telegram-fixture", "provider_message_id": "telegram-1", "acknowledged": True}

            run_time = dt.datetime(2026, 8, 17, 19, 0, tzinfo=dt.timezone.utc)
            first = aos_morning_brief.run(
                root=root,
                deliver=True,
                refresh_fn=self.detector,
                post_json=lambda _endpoint, _payload: david_calls.append(True) or self.response(),
                email_sender=email,
                telegram_sender=telegram,
                now=run_time,
            )
            second = aos_morning_brief.run(
                root=root,
                deliver=True,
                refresh_fn=self.detector,
                post_json=lambda _endpoint, _payload: david_calls.append(True) or self.response(),
                email_sender=email,
                telegram_sender=telegram,
                now=run_time,
            )
            artifact = (root / aos_morning_brief.OUTPUT_REL).read_text(encoding="utf-8")
            receipt = (root / first["delivery"]["receipt_path"]).read_text(encoding="utf-8")

        self.assertEqual([(root, aos_morning_brief.EMAIL_RECIPIENT, "David Morning Brief — 2026-08-17", artifact)], emails)
        self.assertEqual([(root, artifact)], telegrams)
        self.assertEqual([True], david_calls)
        self.assertTrue(second["idempotent_skip"])
        self.assertEqual(hashlib.sha256(artifact.encode("utf-8")).hexdigest(), first["delivery"]["artifact_sha256"])
        self.assertEqual(["sent", "sent"], [row["status"] for row in first["delivery"]["authorized_external_deliveries"]])
        self.assertEqual(["already_sent", "already_sent"], [row["status"] for row in second["delivery"]["authorized_external_deliveries"]])
        self.assertIn('"input_tokens": 100', receipt)
        self.assertIn("agentmail-1", receipt)
        self.assertIn("telegram-1", receipt)


if __name__ == "__main__":
    unittest.main()
