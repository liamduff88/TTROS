"""Focused tests for the thin prospecting operational entry point.

Revisit: when prospector.py or the V3.1 handoff contract changes. · Last touched: 2026-07-31.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import prospector
from tools.business_brain_context import BrainContextUsed, BrainRead, ScopedRetrievalResult


class FakeContextLoader:
    def retrieve(self, **_kwargs):
        return ScopedRetrievalResult(reads=[BrainRead(
            content="fixture",
            provenance=BrainContextUsed(
                note_id="fixture-note",
                path="business_brain:memory/ideal_clients.md",
                client_scope="global",
                retrieval_route="pointer",
                content_sha256="a" * 64,
            ),
        )])


class FakeStore:
    def __init__(self):
        self.states = {}

    def read_state(self, key):
        return self.states.get(key)


class FakeDraftAdapter:
    def __init__(self):
        self.calls = []
        self.store = FakeStore()

    def create_draft(self, **values):
        self.calls.append(values)
        key = f"key-{values['message_identity']}"
        self.store.states[key] = {"provider_draft_id": "fixture-draft"}
        return {"status": "draft-created", "safe_draft_reference": "gmail-draft:fixture", "idempotency_key": key}


class ProspectorTests(unittest.TestCase):
    def setUp(self):
        self.holder = tempfile.TemporaryDirectory()
        self.root = Path(self.holder.name)
        (self.root / "queue/locks").mkdir(parents=True)
        (self.root / "queue/receipts").mkdir(parents=True)
        (self.root / "queue/work_items.jsonl").write_text("", encoding="utf-8")
        (self.root / "queue/prospects.jsonl").write_text("", encoding="utf-8")

    def tearDown(self):
        self.holder.cleanup()

    def test_run_reuses_engine_and_produces_draft_linkedin_review_packages(self):
        adapter = FakeDraftAdapter()
        with patch.object(prospector, "_verify_url", return_value={"url": "https://example.invalid/signal", "reachable": True, "http_status": 200}):
            result = prospector.run(
                work_item_id="AOS-2026-0998",
                handoff=prospector.DEFAULT_HANDOFF,
                root=self.root,
                adapter=adapter,
                context_loader=FakeContextLoader(),
            )
        self.assertEqual("PASS", result["status"])
        self.assertEqual("aos-revenue", result["profile_used"])
        self.assertEqual("human_review", result["queue_status"])
        self.assertEqual(2, len(result["prospect_packages"]))
        self.assertEqual(1, len(adapter.calls))
        self.assertEqual(0, result["external_actions"]["emails_sent"])
        self.assertEqual(0, result["external_actions"]["linkedin_actions"])
        self.assertTrue((self.root / result["artifact_path"]).is_file())
        self.assertTrue((self.root / result["receipt_path"]).is_file())
        receipt = (self.root / result["receipt_path"]).read_text(encoding="utf-8")
        self.assertIn("Gmail draft-only", receipt)
        self.assertIn("Token usage: unavailable from current CLI output.", receipt)

    def test_replay_is_duplicate_safe_and_creates_no_second_draft(self):
        adapter = FakeDraftAdapter()
        kwargs = dict(
            work_item_id="AOS-2026-0999",
            handoff=prospector.DEFAULT_HANDOFF,
            root=self.root,
            adapter=adapter,
            context_loader=FakeContextLoader(),
        )
        with patch.object(prospector, "_verify_url", return_value={"url": "https://example.invalid/signal", "reachable": True, "http_status": 200}):
            first = prospector.run(**kwargs)
            replay = prospector.run(**kwargs)
        self.assertEqual(1, len(adapter.calls))
        self.assertEqual(0, replay["engine_result"]["imported"])
        self.assertEqual(2, len(replay["engine_result"]["duplicate_replay_prospects"]))
        self.assertEqual(first["prospect_packages"], replay["prospect_packages"])

    def test_unreachable_public_signal_fails_closed_for_operational_pass(self):
        with patch.object(prospector, "_verify_url", return_value={"url": "https://example.invalid/signal", "reachable": False, "http_status": 404}):
            result = prospector.run(
                work_item_id="AOS-2026-0997",
                handoff=prospector.DEFAULT_HANDOFF,
                root=self.root,
                adapter=FakeDraftAdapter(),
                context_loader=FakeContextLoader(),
            )
        self.assertEqual("NEEDS ATTENTION", result["status"])


if __name__ == "__main__":
    unittest.main()
