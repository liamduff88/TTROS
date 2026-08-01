"""Focused Phase 6B live-capture safety tests.

Revisit: when the Gmail metadata schema, scheduler entry, or rollup contract changes. · Last touched: 2026-08-01.
"""

from __future__ import annotations

import tempfile
import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from tools import aos_capture_live
from tools.aos_capture import CaptureError, CaptureQueueWriter, CaptureStorage, TriageDecision
from tools.aos_capture_live import (
    ComposioReadOnlyExecutor,
    PollLock,
    _bounded_history_refs,
    _capture_metrics,
    _normalize_message,
    _route_captured_messages,
)


ROOT = Path(__file__).resolve().parents[1]


class LiveExecutorBoundaryTests(unittest.TestCase):
    def test_history_backlog_batch_does_not_split_a_checkpoint(self):
        refs = []
        for index in range(24):
            refs.append((str(100 + index), {"id": f"message-{index}"}))
        refs.extend(("200", {"id": f"group-{index}"}) for index in range(3))
        refs.append(("201", {"id": "after-group"}))

        selected, cursor, truncated = _bounded_history_refs(refs)

        self.assertEqual(24, len(selected))
        self.assertEqual("123", cursor)
        self.assertTrue(truncated)
        self.assertNotIn("200", {history_id for history_id, _row in selected})

    def test_only_exact_read_only_gmail_payloads_are_accepted(self):
        ComposioReadOnlyExecutor._validate("GMAIL_GET_PROFILE", {"user_id": "me"})
        ComposioReadOnlyExecutor._validate("GMAIL_LIST_HISTORY", {
            "user_id": "me",
            "start_history_id": "123",
            "history_types": ["messageAdded"],
            "label_id": "INBOX",
            "max_results": 100,
        })
        ComposioReadOnlyExecutor._validate("GMAIL_FETCH_EMAILS", {
            "user_id": "me",
            "label_ids": ["INBOX"],
            "include_payload": False,
            "include_spam_trash": False,
            "max_results": 100,
        })
        with self.assertRaises(CaptureError):
            ComposioReadOnlyExecutor._validate("GMAIL_SEND_EMAIL", {})
        with self.assertRaises(CaptureError):
            ComposioReadOnlyExecutor._validate("GMAIL_FETCH_EMAILS", {
                "label_ids": ["INBOX"],
                "include_payload": True,
                "include_spam_trash": False,
                "max_results": 100,
            })
        with self.assertRaises(CaptureError):
            ComposioReadOnlyExecutor._validate("GMAIL_LIST_HISTORY", {
                "start_history_id": "123",
                "history_types": ["labelRemoved"],
                "label_id": "INBOX",
                "max_results": 100,
            })

    def test_metadata_normalizer_excludes_non_inbox_sent_and_self_mail(self):
        value = {
            "id": "provider-message",
            "threadId": "provider-thread",
            "labelIds": ["INBOX"],
            "internalDate": "1784116800000",
            "payload": {"headers": [
                {"name": "From", "value": "Sender <sender@example.invalid>"},
                {"name": "Subject", "value": "Business question"},
            ]},
        }
        row = _normalize_message(value, history_id="123", mailbox_sender_sha256="0" * 64)
        self.assertIsNotNone(row)
        self.assertEqual("gmail_composio", row.provider)
        self.assertNotIn("sender@example.invalid", row.headers or {})
        self.assertIsNone(_normalize_message({**value, "labelIds": ["SENT"]}, history_id="123", mailbox_sender_sha256="0" * 64))
        from tools.aos_capture_live import _sha
        self.assertIsNone(_normalize_message(value, history_id="123", mailbox_sender_sha256=_sha("sender@example.invalid")))

    def test_large_cli_result_hydrates_only_from_bounded_composio_artifact_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "history.json"
            artifact.write_text(
                json.dumps({"successful": True, "data": {"history": [], "historyId": "123"}}),
                encoding="utf-8",
            )
            stub = {"storedInFile": True, "outputFilePath": str(artifact)}
            with patch.object(aos_capture_live, "COMPOSIO_ARTIFACT_ROOT", root):
                hydrated = ComposioReadOnlyExecutor._stored_result(stub)
            self.assertTrue(hydrated["successful"])
            self.assertEqual([], hydrated["data"]["history"])

            outside = root.parent / "outside-history.json"
            outside.write_text("{}", encoding="utf-8")
            with patch.object(aos_capture_live, "COMPOSIO_ARTIFACT_ROOT", root):
                with self.assertRaises(CaptureError):
                    ComposioReadOnlyExecutor._stored_result(
                        {"storedInFile": True, "outputFilePath": str(outside)}
                    )


class LiveRuntimeContractTests(unittest.TestCase):
    @staticmethod
    def _material_record(storage: CaptureStorage, index: int) -> TriageDecision:
        record_id = f"cap-{index:024x}"
        storage.append_raw(None, {
            "record_id": record_id,
            "evidence_reference": f"capture:_unresolved:{record_id}",
            "client_scope": None,
            "scope_state": "unresolved",
            "timestamp": f"2026-08-01T10:{index:02d}:00Z",
            "source_type": "gmail",
            "linked_item_id": "",
        })
        return TriageDecision(
            record_id=record_id,
            state="needs_input",
            route="unresolved_identity",
            client_scope=None,
            subject_classification="business_message",
        )

    def test_capture_run_routes_n_messages_to_one_digest_and_zero_to_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = CaptureStorage(root / "capture/runtime", repo_root=root)
            ledger = SimpleNamespace(token=lambda **_kwargs: True, run=lambda **_kwargs: True)
            writer = CaptureQueueWriter(root, ledger=ledger, capture_mode="live")
            decisions = [self._material_record(storage, index) for index in range(1, 6)]

            routed = _route_captured_messages(
                storage,
                decisions,
                queue_writer=writer,
                evidence_root=root / "capture/gmail",
            )
            items = [json.loads(line) for line in (root / "queue/work_items.jsonl").read_text().splitlines()]
            self.assertEqual(1, len(items))
            self.assertTrue(routed["created"])
            self.assertEqual("human_review", items[0]["status"])
            self.assertEqual(5, len(items[0]["sources"]))
            self.assertEqual(5, len(list((root / "capture/gmail/2026-08-01").rglob("*.json"))))

            replayed = _route_captured_messages(
                storage,
                decisions,
                queue_writer=writer,
                evidence_root=root / "capture/gmail",
            )
            items = [json.loads(line) for line in (root / "queue/work_items.jsonl").read_text().splitlines()]
            self.assertEqual(1, len(items))
            self.assertFalse(replayed["created"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = CaptureStorage(root / "capture/runtime", repo_root=root)
            ledger = SimpleNamespace(token=lambda **_kwargs: True, run=lambda **_kwargs: True)
            writer = CaptureQueueWriter(root, ledger=ledger, capture_mode="live")
            routed = _route_captured_messages(
                storage,
                [],
                queue_writer=writer,
                evidence_root=root / "capture/gmail",
            )
            self.assertFalse(routed["created"])
            self.assertFalse((root / "queue/work_items.jsonl").exists())

    def test_repository_launcher_exposes_bounded_production_entries(self):
        launcher = (ROOT / "tools" / "aos-linux-runtime.sh").read_text(encoding="utf-8")
        self.assertIn('CAPTURE_SCRIPT="${ROOT}/tools/aos_capture_live.py"', launcher)
        self.assertIn("CAPTURE_TIMEOUT_SECONDS=180", launcher)
        self.assertIn('exec "$CAPTURE_PYTHON" "$CAPTURE_SCRIPT" poll "$@"', launcher)
        self.assertIn("exec /usr/bin/timeout --signal=TERM", launcher)
        self.assertIn('"$CAPTURE_PYTHON" "$CAPTURE_SCRIPT" poll --scheduled "$@"', launcher)
        self.assertIn('capture-poll) shift; capture_poll "$@" ;;', launcher)
        self.assertIn('capture-scheduled) shift; capture_scheduled "$@" ;;', launcher)
        self.assertIn("capture-status) capture_status ;;", launcher)

    def test_poll_lock_is_non_overlapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "poll.lock"
            with PollLock(path):
                with self.assertRaises(Exception):
                    with PollLock(path):
                        pass

    def test_rollup_metrics_are_bounded_and_content_free(self):
        rows = [{
            "timestamp": "2026-07-15T12:00:00Z",
            "status": "success",
            "history_entries_received": 3,
            "records_deduplicated": 1,
            "deterministic_triage": {"discard": 2},
            "provider_actions": {"GMAIL_GET_PROFILE": 1},
            "needs_input_proposals": 1,
        }, {
            "timestamp": "2026-07-15T12:01:00Z",
            "status": "connection_check",
            "provider_actions": {"GMAIL_GET_PROFILE": 1},
        }, {
            "timestamp": "2026-07-15T12:02:00Z",
            "status": "correction",
            "history_entries_received": 1,
            "needs_input_proposals": 1,
        }]
        value = _capture_metrics(rows, "2026-W29")
        self.assertEqual(1, value["polls_attempted"])
        self.assertEqual(1, value["polls_completed"])
        self.assertEqual(4, value["history_entries_received"])
        self.assertEqual(2, value["needs_input_proposals"])
        self.assertFalse(value["contains_message_content"])
        self.assertEqual(0, value["whitelist_entries"])
        forbidden = {"body", "subject", "sender", "message_id", "thread_id", "attachment"}
        self.assertTrue(forbidden.isdisjoint(value))

    def test_live_poll_rollup_stays_in_ignored_capture_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "capture" / "runtime" / "control" / "poll_receipts.jsonl"
            receipts.parent.mkdir(parents=True)
            receipts.write_text(
                '{"timestamp":"2026-07-19T12:00:00Z","status":"success"}\n',
                encoding="utf-8",
            )
            runtime_rollups = root / "capture" / "runtime" / "rollups"
            with (
                patch.object(aos_capture_live, "POLL_RECEIPTS_PATH", receipts),
                patch.object(aos_capture_live, "CAPTURE_ROLLUPS", runtime_rollups),
            ):
                aos_capture_live._update_rollup()

            week = runtime_rollups / "week-2026-W29.json"
            self.assertTrue(week.is_file())
            self.assertTrue((runtime_rollups / "index.json").is_file())
            self.assertFalse((root / "queue" / "rollups").exists())
            self.assertNotIn("contains_message_content\": true", week.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
