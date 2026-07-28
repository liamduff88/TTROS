"""Revenue Operations Pilot v1 importer and event-state contracts.

Revisit: when handoff V3.1, outreach events, review cards, or CRM fields change.
· Last touched: 2026-07-23.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from workflows.prospecting_daily_run.outreach_handoff import (
    EMAIL_NOT_INTERESTED_FOOTER,
    EMAIL_SIGNATURE_LINES,
    HandoffValidationError,
    OutreachEventError,
    append_required_email_footer,
    add_business_days,
    import_handoff,
    parse_handoff,
    record_event,
    validate_handoff,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "workflows/prospecting_daily_run/input/TTR_ICP_A_OUTREACH_HANDOFF_2026-07-22_METRO_VANCOUVER_MSP_RECRUITMENT.md"


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
        key = f"fake-key-{values['message_identity']}"
        self.store.states[key] = {"provider_draft_id": "r-live-proof-draft"}
        return {
            "status": "draft-created",
            "safe_draft_reference": "gmail-draft:fake-safe-reference",
            "idempotency_key": key,
        }


def rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_root() -> tuple[tempfile.TemporaryDirectory, Path]:
    holder = tempfile.TemporaryDirectory()
    root = Path(holder.name)
    (root / "queue/locks").mkdir(parents=True)
    (root / "queue/receipts").mkdir(parents=True)
    (root / "queue/work_items.jsonl").write_text("", encoding="utf-8")
    (root / "queue/prospects.jsonl").write_text("", encoding="utf-8")
    return holder, root


class HandoffValidationTests(unittest.TestCase):
    def test_fixture_validates_complete_v31_contract(self):
        header, prospects, digest = parse_handoff(FIXTURE)
        validate_handoff(header, prospects)
        self.assertEqual(header["handoff_version"], "3.1")
        self.assertEqual(len(prospects), 2)
        self.assertEqual(len(digest), 64)

    def test_invalid_block_is_quarantined_before_active_state(self):
        holder, root = build_root()
        self.addCleanup(holder.cleanup)
        invalid = root / "invalid.md"
        invalid.write_text("```yaml\nhandoff_version: '2'\nworkflow: wrong\nrun_date: nope\nicp: A\nscope: x\nprospect_count: 0\n```\n", encoding="utf-8")
        result = import_handoff(invalid, root=root, adapter=FakeDraftAdapter())
        self.assertEqual(result["status"], "quarantined")
        self.assertEqual(rows(root / "queue/prospects.jsonl"), [])
        self.assertEqual(rows(root / "queue/work_items.jsonl"), [])
        receipt = (root / result["receipt"]).read_text(encoding="utf-8")
        self.assertIn("No prospect, draft, review card, reminder, history event, or CRM dry-run record was activated.", receipt)

    def test_business_day_delay_is_deterministic_across_weekend(self):
        self.assertEqual(add_business_days("2026-07-23", 5), "2026-07-30")
        self.assertEqual(add_business_days("2026-07-23", 6), "2026-07-31")

    def test_email_footer_has_signature_and_exact_not_interested_stop_text(self):
        body = append_required_email_footer(
            "Hi Evan,\n\nUseful question.\n\nLiam Duff\n\n"
            "If you would prefer no further contact from me, reply and I will not follow up.\n\n"
            "Manual CASL and role-relevance review required before sending."
        )
        self.assertTrue(body.endswith(EMAIL_NOT_INTERESTED_FOOTER))
        self.assertIn("\n".join(EMAIL_SIGNATURE_LINES), body)
        self.assertNotIn("If you would prefer no further contact", body)
        self.assertNotIn("Manual CASL", body)


class HandoffImportAndEventTests(unittest.TestCase):
    def setUp(self):
        self.holder, self.root = build_root()
        self.adapter = FakeDraftAdapter()
        self.result = import_handoff(
            FIXTURE,
            root=self.root,
            adapter=self.adapter,
            clock=lambda: "2026-07-23T09:00:00Z",
        )

    def tearDown(self):
        self.holder.cleanup()

    def queue_items(self):
        return rows(self.root / "queue/work_items.jsonl")

    def snapshots(self):
        return rows(self.root / "queue/prospects.jsonl")

    def item_for(self, person):
        return next(item for item in self.queue_items() if item["outreach_review"]["prospect"]["person_name"] == person)

    def test_two_prospects_one_draft_and_one_card_each_with_inactive_later_copy(self):
        self.assertEqual(self.result["status"], "PASS")
        self.assertEqual(self.result["imported"], 2)
        self.assertEqual(self.result["created_review_cards"], 2)
        self.assertEqual(len(self.adapter.calls), 1)
        self.assertEqual(self.adapter.calls[0]["recipient"], "info@hwy99.tech")
        self.assertNotIn("Manual CASL and role-relevance review required before sending.", self.adapter.calls[0]["body"])
        self.assertTrue(self.adapter.calls[0]["body"].endswith(EMAIL_NOT_INTERESTED_FOOTER))
        self.assertIn("\n".join(EMAIL_SIGNATURE_LINES), self.adapter.calls[0]["body"])

        evan = self.item_for("Evan Thompson")["outreach_review"]
        loretta = self.item_for("Loretta Davis")["outreach_review"]
        self.assertEqual(evan["stage"], "draft_ready")
        self.assertIn("/mail/u/liam%40timetorevenue.com/", evan["gmail_draft_url"])
        self.assertNotIn("/mail/u/0/", evan["gmail_draft_url"])
        self.assertEqual(evan["gmail_draft_mailbox"], "liam@timetorevenue.com")
        self.assertTrue(evan["copy"]["email_1"]["active"])
        self.assertFalse(evan["copy"]["email_2"]["active"])
        self.assertFalse(evan["copy"]["linkedin_invitation"]["active"])
        self.assertEqual(loretta["profile_url"], "https://ca.linkedin.com/in/loretta-davis-72268312")
        self.assertTrue(loretta["copy"]["linkedin_invitation"]["active"])
        self.assertFalse(loretta["copy"]["linkedin_first_message"]["active"])
        self.assertFalse(loretta["copy"]["linkedin_follow_up"]["active"])
        self.assertFalse(loretta["copy"]["linkedin_soft_close"]["active"])

        for snapshot in self.snapshots():
            crm = snapshot["crm_dry_run"]
            self.assertEqual(crm["mode"], "dry_run")
            self.assertFalse(crm["mutation_performed"])
            self.assertEqual(crm["record"]["agentic_os_prospect_id"], snapshot["prospect_id"])

    def test_replay_creates_zero_duplicates(self):
        replay = import_handoff(
            FIXTURE,
            root=self.root,
            adapter=self.adapter,
            clock=lambda: "2026-07-23T09:05:00Z",
        )
        self.assertEqual(replay["imported"], 0)
        self.assertEqual(replay["created_review_cards"], 0)
        self.assertEqual(len(replay["duplicate_replay_prospects"]), 2)
        self.assertEqual(len(self.queue_items()), 2)
        self.assertEqual(len(self.snapshots()), 2)
        self.assertEqual(len(self.adapter.calls), 1)

    def test_actual_events_advance_only_target_and_prerequisites_gate_linkedin(self):
        loretta = self.item_for("Loretta Davis")
        evan_id = self.item_for("Evan Thompson")["id"]
        record_event(loretta["id"], "invitation_sent", occurred_on="2026-07-23", root=self.root, clock=lambda: "2026-07-23T10:00:00Z")
        after_invite = self.item_for("Loretta Davis")["outreach_review"]
        self.assertEqual(after_invite["stage"], "waiting_for_connection")
        self.assertIsNone(after_invite["due_date"])
        self.assertFalse(after_invite["copy"]["linkedin_first_message"]["active"])
        self.assertEqual(len([row for row in self.snapshots() if row["review_item_id"] == evan_id]), 1)

        record_event(loretta["id"], "connection_accepted", occurred_on="2026-07-24", root=self.root, clock=lambda: "2026-07-24T10:00:00Z")
        accepted = self.item_for("Loretta Davis")["outreach_review"]
        self.assertEqual(accepted["stage"], "linkedin_first_message_ready")
        self.assertTrue(accepted["copy"]["linkedin_first_message"]["active"])

        record_event(loretta["id"], "linkedin_message_sent", occurred_on="2026-07-24", root=self.root, clock=lambda: "2026-07-24T11:00:00Z")
        waiting = self.item_for("Loretta Davis")["outreach_review"]
        self.assertEqual(waiting["due_date"], "2026-08-03")
        with self.assertRaises(OutreachEventError):
            record_event(loretta["id"], "linkedin_message_sent", occurred_on="2026-07-31", root=self.root)

    def test_send_calculates_one_reminder_and_reply_or_optout_cancels_future(self):
        evan = self.item_for("Evan Thompson")
        sent = record_event(evan["id"], "email_1_sent", occurred_on="2026-07-23", root=self.root, clock=lambda: "2026-07-23T12:00:00Z")
        self.assertEqual(sent["snapshot"]["next_touch_due"], "2026-07-30")
        self.assertEqual(sent["snapshot"]["next_reminder"]["condition"], "only if no stop event is recorded")
        stopped = record_event(evan["id"], "reply_received", occurred_on="2026-07-24", root=self.root, clock=lambda: "2026-07-24T12:00:00Z")
        self.assertTrue(stopped["snapshot"]["future_activity_cancelled"])
        self.assertIsNone(stopped["snapshot"]["next_touch_due"])
        self.assertEqual(self.item_for("Evan Thompson")["status"], "cancelled")
        later_stop = record_event(evan["id"], "opt_out", occurred_on="2026-07-25", root=self.root, clock=lambda: "2026-07-25T12:00:00Z")
        self.assertEqual(later_stop["snapshot"]["outreach_history"][-2]["event"], "reply_received")
        self.assertEqual(later_stop["snapshot"]["outreach_history"][-1]["event"], "opt_out")
        self.assertIsNone(later_stop["snapshot"]["next_reminder"])

    def test_optout_is_preserved_in_crm_projection_and_event_replay_is_idempotent(self):
        evan = self.item_for("Evan Thompson")
        first = record_event(evan["id"], "opt_out", occurred_on="2026-07-23", root=self.root, clock=lambda: "2026-07-23T13:00:00Z")
        replay = record_event(evan["id"], "opt_out", occurred_on="2026-07-23", root=self.root, clock=lambda: "2026-07-23T13:05:00Z")
        self.assertEqual(replay["status"], "duplicate_replay")
        self.assertTrue(first["snapshot"]["crm_dry_run"]["record"]["opt_out"])
        self.assertTrue(first["snapshot"]["crm_dry_run"]["record"]["do_not_contact"])

    def test_not_interested_reply_creates_do_not_contact_no_resend_state(self):
        evan = self.item_for("Evan Thompson")
        stopped = record_event(evan["id"], "not_interested", occurred_on="2026-07-23", root=self.root, clock=lambda: "2026-07-23T13:30:00Z")
        snapshot = stopped["snapshot"]
        self.assertEqual(snapshot["status"], "do_not_contact")
        self.assertEqual(snapshot["reply_status"], "not_interested")
        self.assertTrue(snapshot["do_not_contact"])
        self.assertTrue(snapshot["future_activity_cancelled"])
        self.assertIsNone(snapshot["next_reminder"])
        self.assertTrue(snapshot["crm_dry_run"]["record"]["do_not_contact"])
        self.assertEqual(self.item_for("Evan Thompson")["status"], "cancelled")

    def test_generated_snapshots_validate_against_canonical_schema_and_validator(self):
        validator_path = ROOT / "tools/validate-prospect-ledger.py"
        spec = importlib.util.spec_from_file_location("validate_prospect_ledger_pilot", validator_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.validate_ledger(self.root / "queue/prospects.jsonl", ROOT / "queue/prospects_schema.json")
        self.assertEqual(result["status"], "PASS", result["errors"])


if __name__ == "__main__":
    unittest.main()
