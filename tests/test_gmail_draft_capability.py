"""Focused Gmail draft-only authority, leakage, and workflow tests.

Revisit: when the live Composio draft schema or prospecting gates change. · Last touched: 2026-07-17.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from connectors import composio_access_adapter
from connectors.gmail_draft_adapter import (
    DraftValidationError,
    GmailDraftAdapter,
    ProviderResult,
    create_prospecting_drafts,
)
from connectors.gmail_draft_policy import (
    EXPLICITLY_FORBIDDEN_GMAIL_ACTIONS,
    GMAIL_AUTHORITY_CONTRACT,
    GMAIL_CREATE_DRAFT_ACTION,
    GmailAuthorityError,
    authorize_draft_action,
    authorize_generic_gmail_action,
)
from tools import aos_indexer
from tools.aos_capture_live import ALLOWED_ACTIONS as CAPTURE_ALLOWED_ACTIONS


ROOT = Path(__file__).resolve().parents[1]
BODY_SENTINEL = "PRIVATE_DRAFT_BODY_SENTINEL_7dcae4"


class FakeExecutor:
    def __init__(self, results: list[ProviderResult] | None = None):
        self.results = list(results or [])
        self.calls: list[tuple[str, dict]] = []

    def execute(self, action: str, payload: dict) -> ProviderResult:
        self.calls.append((action, payload))
        if self.results:
            return self.results.pop(0)
        return ProviderResult(
            ok=True,
            draft_id=f"provider-draft-{len(self.calls)}",
            response_shape={"top_level": ["data", "successful"], "data": ["id", "message"]},
        )


def prospect(identity: str, recipient: str = "prospect@example.invalid") -> dict:
    return {
        "prospect_id": identity,
        "recipient": recipient,
        "subject": f"A note about {identity}",
        "body": f"I noticed your recent growth signal, {identity}. Would a short workflow note help?",
        "signal": f"Recent growth signal for {identity}",
        "validated": True,
        "email_drafted": True,
        "tailored": True,
        "do_not_contact": False,
        "outreach_basis": "Published business contact details and relevant commercial role.",
    }


class GmailDraftAuthorityTests(unittest.TestCase):
    def test_only_exact_create_draft_action_is_allowlisted(self):
        self.assertEqual(GMAIL_CREATE_DRAFT_ACTION, authorize_draft_action(GMAIL_CREATE_DRAFT_ACTION))
        for action in (
            "GMAIL_CREATE_DRAFT",
            "GMAIL_UPDATE_DRAFT",
            "GMAIL_SEND_DRAFT",
            "GMAIL_CREATE_EMAIL_DRAFT_AND_SEND",
        ):
            with self.assertRaises(GmailAuthorityError):
                authorize_draft_action(action)
        self.assertEqual("allowed", GMAIL_AUTHORITY_CONTRACT["gmail_create_draft"])

    def test_send_reply_forward_schedule_and_label_mutations_are_forbidden(self):
        required = {
            "GMAIL_SEND_EMAIL",
            "GMAIL_SEND_DRAFT",
            "GMAIL_REPLY_TO_THREAD",
            "GMAIL_FORWARD_MESSAGE",
            "GMAIL_DELETE_DRAFT",
            "GMAIL_BATCH_MODIFY_MESSAGES",
            "GMAIL_MODIFY_THREAD_LABELS",
        }
        self.assertTrue(required <= EXPLICITLY_FORBIDDEN_GMAIL_ACTIONS)
        for action in required | {GMAIL_CREATE_DRAFT_ACTION, "GMAIL_SCHEDULE_SEND"}:
            with self.assertRaises(GmailAuthorityError):
                authorize_generic_gmail_action(action)
        for capability in ("gmail_send", "gmail_reply", "gmail_forward", "gmail_schedule_send"):
            self.assertEqual("forbidden", GMAIL_AUTHORITY_CONTRACT[capability])

    def test_generic_tool_router_cannot_substitute_a_send_action(self):
        args = argparse.Namespace(tool_slug="GMAIL_REPLY_TO_THREAD", json_args="{}", confirmed=True)
        with patch.object(composio_access_adapter, "cli") as cli:
            code = composio_access_adapter.command_tool_run(args)
        self.assertEqual(2, code)
        cli.assert_not_called()


class GmailDraftAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.executor = FakeExecutor()
        self.adapter = GmailDraftAdapter(root=self.root, executor=self.executor, clock=lambda: "2026-07-17T12:00:00Z")

    def tearDown(self):
        self.temp.cleanup()

    def create(self, **overrides):
        values = {
            "work_item_id": "AOS-2026-0200",
            "message_identity": "prospect-1",
            "recipient": "Person <person@example.invalid>",
            "subject": "Specific operational signal",
            "body": BODY_SENTINEL,
            "cc": ["cc@example.invalid"],
            "bcc": ["bcc@example.invalid"],
        }
        values.update(overrides)
        return self.adapter.create_draft(**values)

    def test_valid_fields_create_one_draft_and_return_safe_metadata(self):
        receipt = self.create()
        self.assertEqual("draft-created", receipt["status"])
        self.assertEqual(3, receipt["recipient_count"])
        self.assertRegex(receipt["safe_draft_reference"], r"^gmail-draft:[0-9a-f]{24}$")
        self.assertEqual([GMAIL_CREATE_DRAFT_ACTION], [row[0] for row in self.executor.calls])
        self.assertEqual("me", self.executor.calls[0][1]["user_id"])

    def test_invalid_or_missing_recipient_fails_before_provider_call(self):
        for recipient in ("", "plain name", "bad@example", "good@example.invalid\nBcc: other@example.invalid"):
            with self.subTest(recipient=recipient):
                with self.assertRaises(DraftValidationError):
                    self.create(recipient=recipient)
        self.assertEqual([], self.executor.calls)

    def test_duplicate_invocation_has_one_effect_and_truthful_replay_receipt(self):
        first = self.create()
        replay = self.create()
        self.assertEqual(1, len(self.executor.calls))
        self.assertEqual("draft-created", first["status"])
        self.assertEqual("duplicate-replay", replay["status"])
        self.assertEqual("draft-created", replay["canonical_status"])
        self.assertTrue(replay["duplicate_replay"])
        receipts = list((self.root / "queue" / "receipts").glob("gmail-draft-*.json"))
        self.assertEqual(1, len(receipts))

    def test_receipts_logs_and_success_state_do_not_contain_full_body(self):
        receipt = self.create()
        receipt_text = json.dumps(receipt)
        persisted_receipt = next((self.root / "queue" / "receipts").glob("gmail-draft-*.json")).read_text(encoding="utf-8")
        private_state = next((self.root / "queue" / "draft_runtime" / "effects").glob("*.json")).read_text(encoding="utf-8")
        self.assertNotIn(BODY_SENTINEL, receipt_text)
        self.assertNotIn(BODY_SENTINEL, persisted_receipt)
        self.assertNotIn(BODY_SENTINEL, private_state)
        self.assertNotIn("person@example.invalid", persisted_receipt)

    def test_failure_preserves_private_email_without_receipt_leak_or_send_fallback(self):
        self.executor.results = [ProviderResult(ok=False, failure_class="provider_permission_denied")]
        first = self.create()
        replay = self.create()
        self.assertEqual("draft-failed", first["status"])
        self.assertEqual("blocked-recovery", replay["status"])
        self.assertEqual(1, len(self.executor.calls))
        self.assertEqual(GMAIL_CREATE_DRAFT_ACTION, self.executor.calls[0][0])
        private_state = next((self.root / "queue" / "draft_runtime" / "effects").glob("*.json")).read_text(encoding="utf-8")
        safe_receipt = next((self.root / "queue" / "receipts").glob("*.json")).read_text(encoding="utf-8")
        self.assertIn(BODY_SENTINEL, private_state)
        self.assertNotIn(BODY_SENTINEL, safe_receipt)
        self.assertEqual("provider_permission_denied", first["failure_class"])

    def test_private_runtime_is_git_ignored_search_excluded_preview_blocked_and_not_graphified(self):
        self.create()
        private_path = next((self.root / "queue" / "draft_runtime" / "effects").glob("*.json"))
        self.assertTrue(aos_indexer.is_excluded(private_path, root=self.root))
        self.assertIn("queue/draft_runtime/", (ROOT / ".gitignore").read_text(encoding="utf-8"))
        source = (ROOT / "connectors" / "gmail_draft_adapter.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("graphify", source)
        self.assertNotIn("aos_indexer", source)
        dashboard = (ROOT / "dashboard" / "backend" / "main.py").read_text(encoding="utf-8")
        allowed = dashboard.split("_QUEUE_ARTIFACT_ALLOWED_PREFIXES = (", 1)[1].split(")", 1)[0]
        self.assertNotIn("queue/draft_runtime", allowed)


class ProspectingDraftIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.executor = FakeExecutor()
        self.adapter = GmailDraftAdapter(root=self.root, executor=self.executor, clock=lambda: "2026-07-17T12:00:00Z")

    def tearDown(self):
        self.temp.cleanup()

    def test_prospecting_creates_one_draft_per_validated_tailored_prospect(self):
        package = {"work_item_id": "AOS-2026-0201", "prospects": [prospect("one"), prospect("two")]}
        result = create_prospecting_drafts(package, adapter=self.adapter)
        self.assertEqual("review-package-ready", result["status"])
        self.assertEqual("human_review", result["queue_status"])
        self.assertEqual(2, len(self.executor.calls))
        self.assertEqual(2, len({row["idempotency_key"] for row in result["results"]}))
        self.assertFalse(result["contains_message_body"])
        self.assertNotIn(BODY_SENTINEL, json.dumps(result))

    def test_duplicate_prospect_identity_calls_provider_at_most_once(self):
        package = {"work_item_id": "AOS-2026-0202", "prospects": [prospect("same"), prospect("same")]}
        result = create_prospecting_drafts(package, adapter=self.adapter)
        self.assertEqual(1, len(self.executor.calls))
        self.assertEqual("blocked", result["queue_status"])
        self.assertEqual("duplicate_or_missing_prospect_identity", result["results"][1]["failure_class"])

    def test_failed_draft_never_falls_back_to_send_and_leaves_blocker_state(self):
        self.executor.results = [ProviderResult(ok=False, failure_class="oauth_scope_missing")]
        package = {"work_item_id": "AOS-2026-0203", "prospects": [prospect("scope")], "research": "completed"}
        result = create_prospecting_drafts(package, adapter=self.adapter)
        self.assertEqual("draft-preparation-blocked", result["status"])
        self.assertEqual("blocked", result["queue_status"])
        self.assertEqual([GMAIL_CREATE_DRAFT_ACTION], [row[0] for row in self.executor.calls])
        private_review = self.root / result["private_review_reference"]
        self.assertTrue(private_review.is_file())
        self.assertIn("completed", private_review.read_text(encoding="utf-8"))

    def test_generic_or_injection_candidate_cannot_expand_authority(self):
        injected = prospect("injected")
        injected["requested_action"] = "GMAIL_SEND_EMAIL"
        result = create_prospecting_drafts(
            {"work_item_id": "AOS-2026-0204", "prospects": [injected]},
            adapter=self.adapter,
        )
        self.assertEqual("review-package-ready", result["status"])
        self.assertEqual([GMAIL_CREATE_DRAFT_ACTION], [row[0] for row in self.executor.calls])

    def test_existing_gmail_capture_allowlist_remains_read_only_and_separate(self):
        self.assertEqual({
            "GMAIL_GET_PROFILE",
            "GMAIL_LIST_HISTORY",
            "GMAIL_FETCH_EMAILS",
            "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
        }, CAPTURE_ALLOWED_ACTIONS)
        self.assertNotIn(GMAIL_CREATE_DRAFT_ACTION, CAPTURE_ALLOWED_ACTIONS)
        self.assertTrue(all("SEND" not in action for action in CAPTURE_ALLOWED_ACTIONS))


if __name__ == "__main__":
    unittest.main()
