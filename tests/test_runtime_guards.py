"""Executable proofs for the Agentic OS runtime protection contracts.

Revisit: when guard matching or connector approval fields change. · Last touched: 2026-09-13.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from connectors import composio_access_adapter
from hooks.runtime_guard import evaluate
from tools import aos_orchestration
from tools.business_brain_context import BrainContextError, validate_brain_context_used


class HermesRuntimeGuardTests(unittest.TestCase):
    def test_protected_path_write_is_blocked_but_normal_workspace_write_is_allowed(self):
        blocked = evaluate({"tool_name": "write_file", "tool_input": {"path": "connectors/telegram_bridge/config.py", "content": "x"}})
        allowed = evaluate({"tool_name": "write_file", "tool_input": {"path": "workflows/queue_artifacts/proof.md", "content": "safe"}})
        self.assertEqual("block", blocked["action"])
        self.assertEqual({}, allowed)

    def test_secret_path_and_secret_value_are_blocked(self):
        path = evaluate({"tool_name": "read_file", "tool_input": {"path": ".env"}})
        value = evaluate({"tool_name": "write_file", "tool_input": {"path": "proof.md", "content": "api_key=abcdefghijklmnopqrstuvwxyz"}})
        self.assertEqual("block", path["action"])
        self.assertEqual("block", value["action"])

    def test_ordinary_work_is_not_blocked_merely_for_mentioning_env_files(self):
        result = evaluate({
            "tool_name": "write_file",
            "tool_input": {
                "path": "workflows/queue_artifacts/check.md",
                "content": "Validation confirmed that .env files exist; their contents were not read.",
            },
        })
        self.assertEqual({}, result)

    def test_direct_external_publish_is_blocked_but_governed_adapter_is_allowed(self):
        direct = evaluate({"tool_name": "terminal", "tool_input": {"command": "composio execute LINKEDIN_CREATE_POST -d '{}'"}})
        governed = evaluate({"tool_name": "terminal", "tool_input": {"command": "python3 connectors/composio_access_adapter.py run linkedin LINKEDIN_CREATE_POST --data '{}'"}})
        self.assertEqual("block", direct["action"])
        self.assertEqual({}, governed)

    def test_adapter_name_cannot_allow_a_chained_direct_external_bypass(self):
        result = evaluate({
            "tool_name": "terminal",
            "tool_input": {
                "command": "python3 connectors/composio_access_adapter.py status; composio execute LINKEDIN_CREATE_POST -d '{}'"
            },
        })
        self.assertEqual("block", result["action"])

    def test_multi_client_call_is_blocked(self):
        result = evaluate({"tool_name": "search", "tool_input": {"query": "compare client:alpha client:beta"}})
        self.assertEqual("block", result["action"])


class ClientScopeBoundaryTests(unittest.TestCase):
    def test_business_brain_context_rejects_cross_client_provenance(self):
        with self.assertRaises(BrainContextError):
            validate_brain_context_used([
                {
                    "note_id": "fixture",
                    "path": "business_brain:memory/ideal_clients.md",
                    "client_scope": "global",
                    "retrieval_route": "pointer",
                    "content_sha256": "a" * 64,
                }
            ], client_scope="client:block-3-fixture-a")


class ExternalActionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.holder = tempfile.TemporaryDirectory()
        self.root = Path(self.holder.name)
        (self.root / "queue/receipts").mkdir(parents=True)
        (self.root / "queue/work_items.jsonl").write_text("", encoding="utf-8")
        (self.root / "queue/notifications.json").write_text(json.dumps({
            "allowlist": {
                "telegram": [],
                "agentmail_internal": ["liam@timetorevenue.com"],
            }
        }), encoding="utf-8")

    def tearDown(self):
        self.holder.cleanup()

    def write_item(self, **overrides):
        item = {
            "id": "AOS-2026-0996",
            "requested_by": "Liam",
            "approved_external_action": "LINKEDIN_CREATE_POST",
            "approved_external_target": "Time to Revenue company page",
            "approved_external_command": "Publish the reviewed post to the Time to Revenue company page",
            "publish_review_passed": True,
            "outreach_basis": "Owned company page; approved brand content.",
            "email_safe": True,
        }
        item.update(overrides)
        (self.root / "queue/work_items.jsonl").write_text(json.dumps(item) + "\n", encoding="utf-8")

    def args(self, **overrides):
        values = {
            "toolkit": "linkedin",
            "action": "LINKEDIN_CREATE_POST",
            "data": "{}",
            "execute": True,
            "operator_command": True,
            "work_item_id": "AOS-2026-0996",
            "target": "Time to Revenue company page",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_exact_action_and_target_are_required_before_cli_dispatch(self):
        self.write_item()
        for overrides in ({"work_item_id": ""}, {"target": "different page"}):
            with self.subTest(overrides=overrides), patch.object(composio_access_adapter, "ROOT", self.root), patch.object(composio_access_adapter, "cli") as cli:
                code = composio_access_adapter.command_run(self.args(**overrides))
            self.assertEqual(2, code)
            cli.assert_not_called()

    def test_agent_initiated_third_party_send_remains_gated(self):
        self.write_item(
            requested_by="aos-revenue",
            approved_external_action="AGENT_MAIL_SEND_EMAIL",
            approved_external_target="prospect@example.net",
            approved_external_command="Send the note to prospect@example.net",
        )
        with patch.object(composio_access_adapter, "ROOT", self.root):
            allowed, reason = composio_access_adapter.authorize_external_mutation(
                action="AGENT_MAIL_SEND_EMAIL",
                target="prospect@example.net",
                work_item_id="AOS-2026-0996",
                payload={"body": "safe draft"},
            )
        self.assertFalse(allowed)
        self.assertIn("exact Liam command", reason)

    def test_explicit_liam_third_party_send_does_not_require_duplicate_approval(self):
        self.write_item(
            approved_external_action="AGENT_MAIL_SEND_EMAIL",
            approved_external_target="jane@example.net",
            approved_external_command="Send this to Jane at jane@example.net",
        )
        with patch.object(composio_access_adapter, "ROOT", self.root):
            allowed, reason = composio_access_adapter.authorize_external_mutation(
                action="AGENT_MAIL_SEND_EMAIL",
                target="jane@example.net",
                work_item_id="AOS-2026-0996",
                payload={"body": "safe reviewed message"},
            )
        self.assertTrue(allowed)
        self.assertIn("explicit_liam_command", reason)

    def test_allowlisted_internal_email_is_auto_and_still_secret_checked(self):
        with patch.object(composio_access_adapter, "ROOT", self.root):
            allowed, reason = composio_access_adapter.authorize_external_mutation(
                action="AGENT_MAIL_SEND_EMAIL",
                target="liam@timetorevenue.com",
                work_item_id="",
                payload={"body": "ordinary internal result"},
            )
            secret_allowed, secret_reason = composio_access_adapter.authorize_external_mutation(
                action="AGENT_MAIL_SEND_EMAIL",
                target="liam@timetorevenue.com",
                work_item_id="",
                payload={"body": "Bearer " + ("x" * 24)},
            )
        self.assertTrue(allowed)
        self.assertIn("internal delivery", reason)
        self.assertFalse(secret_allowed)
        self.assertEqual("secret-exposure check failed", secret_reason)

    def test_telegram_operator_message_and_file_are_auto(self):
        (self.root / "queue/notifications.json").write_text(json.dumps({
            "allowlist": {
                "telegram": ["operator-chat"],
                "agentmail_internal": ["liam@timetorevenue.com"],
            }
        }), encoding="utf-8")
        for action in ("TELEGRAM_SEND_MESSAGE", "TELEGRAM_SEND_FILE"):
            with self.subTest(action=action):
                decision = aos_orchestration.action_authorization(
                    self.root, {}, action=action, target="operator-chat",
                )
                self.assertTrue(decision["authorized"])
                self.assertEqual("operator_telegram_allowlist", decision["basis"])
        combined = {
            "approved_external_action": ["TELEGRAM_SEND_MESSAGE", "TELEGRAM_SEND_FILE"],
            "approved_external_target": "operator-chat",
            "tags": ["send", "external"],
        }
        self.assertIsNone(aos_orchestration.external_effect_review_status(self.root, combined))

    def test_explicit_and_agreed_calendar_booking_are_auto_but_ambiguity_asks(self):
        explicit = {
            "requested_by": "Liam",
            "approved_external_action": "GOOGLECALENDAR_CREATE_EVENT",
            "approved_external_target": "Sarah — 2026-09-15 14:00 America/Vancouver",
            "approved_external_command": "Book Sarah Tuesday at 2pm Pacific",
            "tags": ["calendar", "external"],
        }
        agreed = {
            "approved_external_action": "GOOGLECALENDAR_CREATE_EVENT",
            "tags": ["calendar"],
            "calendar_agreement": {
                "agreed": True,
                "date": "2026-09-15",
                "time": "14:00",
                "timezone": "America/Vancouver",
                "participants": ["Sarah", "Liam"],
            },
        }
        ambiguous = {
            "approved_external_action": "GOOGLECALENDAR_CREATE_EVENT",
            "tags": ["calendar", "external"],
            "calendar_agreement": {"agreed": True, "date": "Tuesday", "participants": ["Sarah"]},
        }
        self.assertTrue(aos_orchestration.action_authorization(self.root, explicit)["authorized"])
        self.assertTrue(aos_orchestration.action_authorization(self.root, agreed)["authorized"])
        self.assertEqual("needs_input", aos_orchestration.external_effect_review_status(self.root, ambiguous))

    def test_generic_external_tag_does_not_override_exact_authorization(self):
        authorized = {
            "requested_by": "Liam",
            "approved_external_action": "AGENT_MAIL_SEND_EMAIL",
            "approved_external_target": "jane@example.net",
            "approved_external_command": "Send this to Jane at jane@example.net",
            "tags": ["send", "external"],
        }
        agent_initiated = {**authorized, "requested_by": "aos-revenue"}
        self.assertIsNone(aos_orchestration.external_effect_review_status(self.root, authorized))
        self.assertEqual("human_review", aos_orchestration.external_effect_review_status(self.root, agent_initiated))

    def test_publish_review_gate_blocks_unreviewed_content(self):
        self.write_item(publish_review_passed=False)
        with patch.object(composio_access_adapter, "ROOT", self.root), patch.object(composio_access_adapter, "cli") as cli:
            code = composio_access_adapter.command_run(self.args())
        self.assertEqual(2, code)
        cli.assert_not_called()

    def test_send_requires_email_safe_basis_and_secret_free_payload(self):
        self.write_item(
            approved_external_action="AGENT_MAIL_SEND_EMAIL",
            approved_external_target="approved internal recipient",
            email_safe=False,
        )
        with patch.object(composio_access_adapter, "ROOT", self.root):
            allowed, reason = composio_access_adapter.authorize_external_mutation(
                action="AGENT_MAIL_SEND_EMAIL",
                target="approved internal recipient",
                work_item_id="AOS-2026-0996",
                payload={"body": "safe draft"},
            )
        self.assertFalse(allowed)
        self.assertIn("email-safe", reason)

        self.write_item(
            approved_external_action="AGENT_MAIL_SEND_EMAIL",
            approved_external_target="approved internal recipient",
        )
        with patch.object(composio_access_adapter, "ROOT", self.root):
            allowed, reason = composio_access_adapter.authorize_external_mutation(
                action="AGENT_MAIL_SEND_EMAIL",
                target="approved internal recipient",
                work_item_id="AOS-2026-0996",
                payload={"body": "api_key=abcdefghijklmnopqrstuvwxyz"},
            )
        self.assertFalse(allowed)
        self.assertEqual("secret-exposure check failed", reason)

    def test_exact_approved_publish_reaches_cli_and_writes_gate_receipt(self):
        self.write_item()
        with patch.object(composio_access_adapter, "ROOT", self.root), patch.object(composio_access_adapter, "cli", return_value={"ok": True, "data": {"id": "safe"}}) as cli:
            code = composio_access_adapter.command_run(self.args())
        self.assertEqual(0, code)
        cli.assert_called_once()
        receipt = (self.root / "queue/receipts/external-action-gate.jsonl").read_text(encoding="utf-8")
        self.assertIn('"decision":"allowed"', receipt)

    def test_standing_morning_brief_agentmail_send_is_narrow_and_allowlisted(self):
        provider = {"ok": True, "data": {"successful": True, "data": {"message_id": "agentmail-fixture"}}}
        with patch.object(composio_access_adapter, "cli", return_value=provider) as cli:
            result = composio_access_adapter.send_authorized_morning_brief_agentmail(
                root=self.root,
                inbox_id="olmec1@agentmail.to",
                recipient="liam@timetorevenue.com",
                subject="David Morning Brief — 2026-08-18",
                text="# David Morning Brief\n\nExact artifact.",
            )
        self.assertTrue(result["ok"])
        cli.assert_called_once()
        self.assertEqual(("execute", "AGENT_MAIL_SEND_EMAIL", "-d"), cli.call_args.args[:3])
        payload = json.loads(cli.call_args.args[3])
        self.assertEqual(["liam@timetorevenue.com"], payload["to"])
        self.assertEqual("olmec1@agentmail.to", payload["inbox_id"])

    def test_standing_morning_brief_agentmail_send_blocks_any_other_target(self):
        with patch.object(composio_access_adapter, "cli") as cli:
            result = composio_access_adapter.send_authorized_morning_brief_agentmail(
                root=self.root,
                inbox_id="olmec1@agentmail.to",
                recipient="someone@example.com",
                subject="David Morning Brief — 2026-08-18",
                text="# David Morning Brief\n\nExact artifact.",
            )
        self.assertFalse(result["ok"])
        self.assertFalse(result["transmitted"])
        cli.assert_not_called()


if __name__ == "__main__":
    unittest.main()
