import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from src.command_router import CommandRouter
from src.date_normalizer import normalize_followup_date
from src.local_store import LocalJsonlStore, LocalStateStore
from src.message_router import MessageRouter
from src.natural_language_router import NaturalLanguageRouter
from src.report_generator import format_followups, generate_daily_report
from src.role_store import RoleStore
from src.sales_log_parser import apply_missing_field_answer, parse_sales_log


ROOT = Path(__file__).resolve().parents[1]
ANCHOR = datetime(2026, 6, 23, 18, 0, tzinfo=timezone.utc)  # Tuesday in Vancouver.


class FollowupDateNormalizationTests(unittest.TestCase):
    def test_relative_and_iso_dates_use_submitted_at(self):
        cases = {
            "follow-up today": "2026-06-23",
            "follow-up tomorrow": "2026-06-24",
            "follow-up 2026-07-04": "2026-07-04",
            "follow-up Tuesday": "2026-06-30",
            "follow-up next Tuesday": "2026-06-30",
            "follow-up next week": "2026-06-29",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                record = parse_sales_log(text, "10", now=ANCHOR)
                self.assertEqual(record["parsed"]["followup_date"], expected)

    def test_all_weekday_forms_are_supported(self):
        self.assertEqual(normalize_followup_date("this Wednesday", ANCHOR), "2026-06-24")
        self.assertEqual(normalize_followup_date("next Sunday", ANCHOR), "2026-07-05")
        self.assertEqual(normalize_followup_date("Monday", ANCHOR), "2026-06-29")

    def test_weekday_time_normalizes_date_and_remains_in_next_step(self):
        record = parse_sales_log("They will come back next Wednesday at 2pm", "10", now=ANCHOR)
        self.assertEqual(record["parsed"]["followup_date"], "2026-07-01")
        self.assertIn("next Wednesday at 2pm", record["parsed"]["next_step"])

    def test_incidental_interaction_date_does_not_override_followup(self):
        record = parse_sales_log("Had a walk-in today and will follow up tomorrow", "10", now=ANCHOR)
        self.assertEqual(record["parsed"]["followup_date"], "2026-06-24")

    def test_pending_answer_populates_date_using_original_submission(self):
        record = parse_sales_log("Walk-in for a Civic", "10", now=ANCHOR)
        updated = apply_missing_field_answer(record, "outcome", "They will come back next Wednesday at 2pm")
        self.assertEqual(updated["parsed"]["followup_date"], "2026-07-01")
        self.assertEqual(updated["parsed"]["next_step"], "They will come back next Wednesday at 2pm")

    def test_bare_pending_next_step_date_is_normalized(self):
        record = parse_sales_log("Walk-in for a Civic", "10", now=ANCHOR)
        updated = apply_missing_field_answer(record, "next_step", "tomorrow")
        self.assertEqual(updated["parsed"]["followup_date"], "2026-06-24")

    def test_followups_report_displays_normalized_date_and_time(self):
        record = parse_sales_log("Civic appointment, follow-up next Wednesday at 2pm", "10", now=ANCHOR)
        report = generate_daily_report([record], date(2026, 6, 23), names={"10": "Casey Morgan"})
        rendered = format_followups(report)
        self.assertIn("2026-07-01 · Casey Morgan · follow-up next Wednesday at 2pm", rendered)


class FollowupsCommandTests(unittest.TestCase):
    def test_followups_command_shows_normalized_local_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            roles = root / "roles.json"
            roles.write_text(json.dumps({"users": {"2": {"role": "admin", "active": True}}}), encoding="utf-8")
            sales = LocalJsonlStore(root / "sales.jsonl")
            record = parse_sales_log("follow-up tomorrow", "10", now=datetime.now(timezone.utc))
            sales.append(record)
            router = MessageRouter(
                RoleStore(roles),
                CommandRouter.from_file(ROOT / "config" / "commands.json"),
                NaturalLanguageRouter(llm_enabled=False),
                LocalStateStore(root / "state.json"),
                LocalJsonlStore(root / "events.jsonl"),
                sales,
            )
            update = {"message": {"from": {"id": 2}, "chat": {"id": -1, "type": "group"}, "text": "/followups"}}
            rendered = router.handle_update(update)
            self.assertIn(record["parsed"]["followup_date"], rendered)
            self.assertIn("Upcoming (1)", rendered)


if __name__ == "__main__":
    unittest.main()
