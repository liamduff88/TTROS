import inspect
import json
import unittest
from pathlib import Path

from src import sheets_sync_adapter as adapter


ROOT = Path(__file__).resolve().parents[1]
HEADERS = json.loads((ROOT / "google_sheets" / "tab_headers.json").read_text(encoding="utf-8"))


def report_fixture():
    return {
        "report_date": "2026-06-23", "generated_at": "2026-06-23T23:00:00Z",
        "metrics": {name: index for index, name in enumerate(HEADERS["Daily_Team_Summary"][2:], 1)},
        "team": [{"salesperson_id": "demo-a", "name": "Demo A", **{name: 1 for name in HEADERS["Daily_Salesperson_Scorecard"][4:]}}],
        "followups": {"overdue": [], "due": [], "upcoming": [{"salesperson_id": "demo-a", "name": "Demo A", "date": "2026-06-24", "next_step": "Call at 14:00", "log_id": "demo-log"}]},
        "missing": {
            "not_updated": [{"salesperson_id": "demo-b", "name": "Demo B"}],
            "incomplete_logs": [{"salesperson_id": "demo-a", "name": "Demo A", "log_id": "demo-incomplete", "fields": ["next_step", "outcome"]}],
            "unregistered_submitters": [{"salesperson_id": "demo-x", "name": "Unregistered salesperson"}],
        },
        "coaching_flags": [{"salesperson_id": "demo-a", "name": "Demo A", "code": "missing_next_step", "detail": "Missing next step."}],
    }


class SheetsSyncAdapterTests(unittest.TestCase):
    def test_all_rows_have_exact_ordered_headers(self):
        state = {"salespeople": {"demo-a": {"salesperson_id": "demo-a", "display_name": "Demo A", "active": True}}}
        payloads = adapter.build_sync_payloads(
            roles={"users": {}}, state=state, sales_logs=[], daily_reports=[report_fixture()], report_archive=[]
        )
        self.assertEqual(list(payloads), list(adapter.SYNC_TABS))
        for tab, rows in payloads.items():
            for row in rows:
                self.assertEqual(list(row), HEADERS[tab])

    def test_raw_logs_mapping_flattens_and_compacts_arrays(self):
        record = {
            "log_id": "demo-log", "submitted_at": "2026-06-23T12:00:00Z", "telegram_user_id": "demo-user",
            "salesperson_id": "demo-a", "source": "local", "raw_text": "Synthetic note", "parsed": {"vehicle_interest": "Demo Car", "test_drive": False},
            "missing_fields": ["outcome"], "coaching_flags": [{"code": "demo"}], "confidence": 1.0,
            "status": "needs_followup", "llm_used": False, "llm_tokens_estimate": None,
        }
        row = adapter.build_raw_logs_rows([record])[0]
        self.assertEqual(row["vehicle_interest"], "Demo Car")
        self.assertIs(row["test_drive"], False)
        self.assertEqual(row["missing_fields_json"], '["outcome"]')
        self.assertEqual(row["coaching_flags_json"], '[{"code":"demo"}]')
        self.assertEqual(row["llm_tokens_estimate"], "")

    def test_users_display_name_precedence(self):
        roles = {"users": {"u1": {"display_name": " Role Name"}, "u2": {}, "u3": {}, "u4": {}, "u5": {}}}
        state = {"users": {
            "u1": {"display_name": "State Name", "first_name": "First", "username": "one"},
            "u2": {"display_name": " State Name ", "first_name": "First"},
            "u3": {"first_name": "Demo", "last_name": "Person", "username": "three"},
            "u4": {"username": "@four"}, "u5": {},
        }}
        rows = {row["telegram_user_id"]: row for row in adapter.build_users_rows(roles, state)}
        self.assertEqual([rows[f"u{i}"]["display_name"] for i in range(1, 6)], [
            "Role Name", "State Name", "Demo Person", "@four", "Unregistered salesperson"
        ])

    def test_users_rows_include_local_onboarding_roles(self):
        state = {"users": {"44": {
            "display_name": "Sarah Jones", "role": "salesperson", "active": True, "salesperson_id": "sarah-jones"
        }}}
        row = adapter.build_users_rows({"users": {}}, state)[0]
        self.assertEqual(row["display_name"], "Sarah Jones")
        self.assertEqual(row["role"], "salesperson")
        self.assertIs(row["active"], True)
        self.assertEqual(row["salesperson_id"], "sarah-jones")

    def test_followup_time_is_blank_unless_separately_emitted(self):
        report = report_fixture()
        row = adapter.build_followup_rows([report])[0]
        self.assertEqual(row["followup_time"], "")
        self.assertIn("14:00", row["next_step"])
        report["followups"]["upcoming"][0]["followup_time"] = "14:00"
        self.assertEqual(adapter.build_followup_rows([report])[0]["followup_time"], "14:00")

    def test_daily_summary_and_scorecard_are_flattened(self):
        report = report_fixture()
        summary = adapter.build_daily_team_summary_rows([report])[0]
        scorecard = adapter.build_scorecard_rows([report])[0]
        self.assertEqual(summary["total_updates"], 1)
        self.assertEqual(summary["coaching_flags"], 11)
        self.assertEqual(scorecard["display_name"], "Demo A")
        self.assertEqual(scorecard["updates"], 1)

    def test_missing_data_supports_all_three_sources(self):
        rows = adapter.build_missing_data_rows([report_fixture()], ["demo-a", "demo-b"])
        by_type = {row["missing_type"]: row for row in rows}
        self.assertEqual(set(by_type), {"roster_no_update", "incomplete_log", "unregistered_submitter"})
        self.assertEqual(by_type["roster_no_update"]["roster_status"], "roster_missing_update")
        self.assertEqual(by_type["incomplete_log"]["missing_fields_json"], '["next_step","outcome"]')
        self.assertEqual(by_type["incomplete_log"]["roster_status"], "active_roster")
        self.assertEqual(by_type["unregistered_submitter"]["roster_status"], "unregistered")

    def test_module_has_no_external_integration_imports_or_clients(self):
        source = inspect.getsource(adapter).lower()
        forbidden = ("import google", "from google", "import composio", "from composio", "requests.", "urllib.", ".execute(")
        for value in forbidden:
            self.assertNotIn(value, source)


if __name__ == "__main__":
    unittest.main()
