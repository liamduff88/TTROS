"""Focused Phase 6B live-capture safety tests.

Revisit: when the Gmail metadata schema, scheduler entry, or rollup contract changes. · Last touched: 2026-07-16.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.aos_capture import CaptureError
from tools.aos_capture_live import (
    ComposioReadOnlyExecutor,
    PollLock,
    _capture_metrics,
    _normalize_message,
)


ROOT = Path(__file__).resolve().parents[1]


class LiveExecutorBoundaryTests(unittest.TestCase):
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


class LiveRuntimeContractTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
