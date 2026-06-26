import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from src.command_router import CommandRouter
from src.local_store import LocalJsonlStore, LocalStateStore
from src.message_router import MessageRouter
from src.natural_language_router import NaturalLanguageRouter
from src.report_generator import coaching_flags, format_coaching, format_daily, format_missing, format_team, generate_daily_report
from src.role_store import RoleStore


ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 6, 23)


def record(log_id, person, parsed, *, missing=None, submitted_at="2026-06-23T18:00:00Z"):
    return {
        "log_id": log_id,
        "submitted_at": submitted_at,
        "telegram_user_id": person,
        "salesperson_id": person,
        "parsed": parsed,
        "missing_fields": missing or [],
        "status": "needs_followup" if missing else "complete",
        "llm_used": False,
    }


def activity(**overrides):
    result = {
        "people_spoken_to": 0,
        "appointment_count": 0,
        "test_drive": False,
        "worksheet_or_offer_presented": False,
        "asked_for_business": False,
        "outcome": None,
        "next_step": "Call tomorrow",
        "followup_date": None,
    }
    result.update(overrides)
    return result


class ReportGeneratorTests(unittest.TestCase):
    def test_empty_logs_are_graceful(self):
        report = generate_daily_report([], DAY)
        self.assertEqual(report["metrics"]["total_updates"], 0)
        self.assertEqual(report["team"], [])
        self.assertIn("Roster data unavailable", report["missing"]["note"])

    def test_multi_salesperson_daily_metrics_and_scorecard(self):
        records = [
            record("a", "rep-a", activity(people_spoken_to=4, appointment_count=1, test_drive=True, outcome="Follow-up")),
            record("b", "rep-b", activity(people_spoken_to=3, worksheet_or_offer_presented=True, asked_for_business=True, outcome="Sold")),
        ]
        report = generate_daily_report(records, DAY, {"rep-a": "Alex", "rep-b": "Blair"})
        self.assertEqual(report["metrics"]["total_updates"], 2)
        self.assertEqual(report["metrics"]["active_salespeople"], 2)
        self.assertEqual(report["metrics"]["people_spoken_to"], 7)
        self.assertEqual(report["metrics"]["appointments"], 1)
        self.assertEqual([row["name"] for row in report["team"]], ["Alex", "Blair"])

    def test_followups_are_classified(self):
        records = [
            record("past", "rep-a", activity(followup_date="2026-06-22")),
            record("due", "rep-a", activity(followup_date="today")),
            record("next", "rep-b", activity(followup_date="tomorrow")),
        ]
        followups = generate_daily_report(records, DAY)["followups"]
        self.assertEqual([item["log_id"] for item in followups["overdue"]], ["past"])
        self.assertEqual([item["log_id"] for item in followups["due"]], ["due"])
        self.assertEqual([item["log_id"] for item in followups["upcoming"]], ["next"])

    def test_missing_fields_and_missing_roster_member(self):
        report = generate_daily_report(
            [record("a", "rep-a", activity(next_step=None), missing=["next_step"])],
            DAY,
            {"rep-a": "Alex", "rep-b": "Blair"},
        )
        self.assertEqual(
            {item["salesperson_id"] for item in report["missing"]["not_updated"]},
            {"rep-a", "rep-b"},
        )
        self.assertIn("next_step", report["missing"]["incomplete_logs"][0]["fields"])

    def test_coaching_flags_are_deterministic(self):
        records = [
            record("a", "rep-a", activity(people_spoken_to=6, worksheet_or_offer_presented=True, next_step=None), missing=["next_step"]),
            record("b", "rep-a", activity(next_step=None), missing=["next_step"]),
            record("c", "rep-b", activity(people_spoken_to=5, test_drive=True, worksheet_or_offer_presented=True, asked_for_business=True)),
            record("d", "rep-b", activity(test_drive=True)),
        ]
        flags = coaching_flags(records)
        pairs = {(flag["salesperson_id"], flag["code"]) for flag in flags}
        self.assertIn(("rep-a", "high_traffic_low_test_drives"), pairs)
        self.assertIn(("rep-a", "offer_without_followup_date"), pairs)
        self.assertIn(("rep-a", "repeated_incomplete_update"), pairs)
        self.assertIn(("rep-b", "strong_performance"), pairs)
        self.assertEqual(flags, coaching_flags(records))

    def test_today_text_reads_like_manager_briefing(self):
        report = generate_daily_report(
            [
                record("a", "rep-a", activity(people_spoken_to=6, next_step=None, followup_date="2026-06-22"), missing=["next_step"]),
                record("b", "rep-b", activity(people_spoken_to=2, test_drive=True, asked_for_business=True, outcome="Sold")),
            ],
            DAY,
            {"rep-a": "Alex", "rep-b": "Blair", "rep-c": "Casey"},
        )
        rendered = format_daily(report)
        self.assertIn("Manager briefing", rendered)
        self.assertIn("Key numbers:", rendered)
        self.assertIn("Update status:", rendered)
        self.assertIn("Missing updates: Alex, Casey.", rendered)
        self.assertIn("Follow-up priority: 1 overdue, 0 due today.", rendered)
        self.assertIn("Coaching note:", rendered)
        self.assertIn("Next action: Check overdue follow-ups first.", rendered)

    def test_team_text_reads_like_scorecard(self):
        report = generate_daily_report(
            [
                record("a", "rep-a", activity(people_spoken_to=4, appointment_count=1, test_drive=True, outcome="Follow-up")),
                record("b", "rep-b", activity(people_spoken_to=3, worksheet_or_offer_presented=True, asked_for_business=True, outcome="Sold")),
            ],
            DAY,
            {"rep-a": "Alex", "rep-b": "Blair"},
        )
        rendered = format_team(report)
        self.assertIn("Team scorecard", rendered)
        self.assertIn("Name | Activity | Progression | Update status", rendered)
        self.assertIn("Alex | 1 update(s), 4 people, 1 appt(s) | 1 drive(s), 0 offer(s), 0 ask(s), 1 outcome(s) | Complete", rendered)
        self.assertIn("Blair", rendered)
        self.assertIn("progress: outcome logged", rendered)

    def test_coaching_text_reads_like_support(self):
        report = generate_daily_report(
            [record("a", "rep-a", activity(people_spoken_to=6, next_step=None), missing=["next_step"])],
            DAY,
            {"rep-a": "Alex"},
        )
        rendered = format_coaching(report)
        self.assertIn("Coaching support", rendered)
        self.assertIn("Alex: Ask what kept conversations from moving to test drives", rendered)
        self.assertIn("Alex: Ask for the next step", rendered)
        self.assertNotIn("high_traffic_low_test_drives", rendered)
        self.assertNotIn("flags", rendered.lower())

    def test_report_text_uses_name_resolved_from_existing_log_telegram_id(self):
        raw_id = "987654321"
        records = [
            record(
                "legacy",
                "legacy-sales-key",
                activity(people_spoken_to=6, next_step=None),
                missing=["next_step"],
            )
        ]
        records[0]["telegram_user_id"] = raw_id
        report = generate_daily_report(records, DAY, names={raw_id: "Casey Morgan"})
        rendered = "\n".join((format_team(report), format_missing(report), format_coaching(report)))
        self.assertIn("Casey Morgan", rendered)
        self.assertNotIn(raw_id, rendered)
        self.assertNotIn("legacy-sales-key", rendered)

    def test_report_text_uses_safe_name_fallback_instead_of_id(self):
        raw_id = "123456789"
        report = generate_daily_report(
            [record("a", raw_id, activity(people_spoken_to=6, next_step=None), missing=["next_step"])],
            DAY,
        )
        rendered = "\n".join((format_team(report), format_missing(report), format_coaching(report)))
        self.assertIn("Unregistered salesperson", rendered)
        self.assertNotIn(raw_id, rendered)


class ReportRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        roles = root / "roles.json"
        roles.write_text(
            json.dumps(
                {
                    "users": {
                        "2": {"role": "admin", "active": True},
                        "10": {"role": "salesperson", "active": True, "display_name": "Configured Rep"},
                    }
                }
            ),
            encoding="utf-8",
        )
        self.sales = LocalJsonlStore(root / "data" / "sales_logs.jsonl")
        self.archive = LocalJsonlStore(root / "data" / "report_archive.jsonl")
        self.llm = Mock()
        self.router = MessageRouter(
            RoleStore(roles),
            CommandRouter.from_file(ROOT / "config" / "commands.json"),
            NaturalLanguageRouter(llm_enabled=False, llm_fallback=self.llm),
            LocalStateStore(root / "data" / "local_state.json"),
            LocalJsonlStore(root / "data" / "events.jsonl"),
            self.sales,
            self.archive,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_report_appends_local_archive_without_llm(self):
        today = date.today().isoformat()
        self.sales.append(record("a", "rep-a", activity(people_spoken_to=2), submitted_at=today + "T12:00:00Z"))
        update = {"message": {"from": {"id": 2}, "chat": {"id": -1, "type": "group"}, "text": "/report"}}
        reply = self.router.handle_update(update)
        archived = list(self.archive.records())
        self.assertIn("Archived locally", reply)
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0]["report_type"], "daily")
        self.assertEqual(archived[0]["date"], today)
        self.assertEqual(archived[0]["summary_metrics"]["total_updates"], 1)
        self.assertFalse(archived[0]["llm_used"])
        self.llm.assert_not_called()

    def test_team_command_prefers_configured_display_name_and_hides_id(self):
        today = date.today().isoformat()
        self.router.state_store.update_user_profile("10", {"first_name": "Telegram", "last_name": "Name"})
        self.sales.append(record("a", "10", activity(people_spoken_to=2), submitted_at=today + "T12:00:00Z"))
        update = {"message": {"from": {"id": 2}, "chat": {"id": -1, "type": "group"}, "text": "/team"}}
        reply = self.router.handle_update(update)
        self.assertIn("Configured Rep", reply)
        self.assertNotIn("Telegram Name", reply)
        self.assertNotIn("10 |", reply)
        self.llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
