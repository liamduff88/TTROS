import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src import sheets_sync_adapter
from src.local_store import LocalJsonlStore, LocalStateStore


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "seed_visual_dashboard_dummy_test.py"
SPEC = importlib.util.spec_from_file_location("seed_visual_dashboard_dummy_test", SCRIPT_PATH)
seeder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(seeder)


class VisualDashboardDummySeederTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "data").mkdir()
        (self.root / "config").mkdir()
        (self.root / "config" / "roles.json").write_text(
            json.dumps(
                {
                    "users": {
                        "admin-local": {
                            "display_name": "Admin User",
                            "role": "admin",
                            "active": True,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        self.initial_state = {
            "groups": {
                "admin_group_chat_id": "admin-group",
                "broadcast_group_chat_id": "broadcast-group",
            },
            "users": {
                "admin-local": {
                    "telegram_user_id": "admin-local",
                    "display_name": "Admin User",
                    "role": "admin",
                    "active": True,
                },
                "invite-user": {
                    "telegram_user_id": "invite-user",
                    "display_name": "Invite User",
                    "role": "salesperson",
                    "active": True,
                    "salesperson_id": "invite-user",
                },
            },
            "invites": {
                "NS-TEST-0001": {
                    "code": "NS-TEST-0001",
                    "role": "salesperson",
                    "display_name": "Pending Rep",
                    "status": "pending",
                }
            },
            "pending_sales_logs": {"invite-user": {"log_id": "pending-log", "field": "outcome"}},
            "salespeople": {
                "existing_rep": {
                    "salesperson_id": "existing_rep",
                    "display_name": "Existing Rep",
                    "active": True,
                }
            },
        }
        self.state_path = self.root / "data" / "local_state.json"
        self.state_path.write_text(json.dumps(self.initial_state, indent=2), encoding="utf-8")
        self.sales_path = self.root / "data" / "sales_logs.jsonl"
        LocalJsonlStore(self.sales_path).append(
            {
                "log_id": "real-log",
                "submitted_at": date.today().isoformat() + "T12:00:00Z",
                "telegram_user_id": "real-user",
                "salesperson_id": "existing_rep",
                "source": "telegram_dm",
                "raw_text": "Real local test fixture",
                "parsed": {"customer_name_or_ref": "REAL_CUSTOMER"},
                "missing_fields": [],
                "coaching_flags": [],
                "confidence": 1.0,
                "status": "complete",
                "llm_used": False,
                "llm_tokens_estimate": None,
            }
        )

    def tearDown(self):
        self.temporary.cleanup()

    def state(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def logs(self):
        return list(LocalJsonlStore(self.sales_path).records())

    def run_main(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = seeder.main([*args, "--root", str(self.root)])
        return result, output.getvalue()

    def test_dry_run_does_not_mutate_files_or_print_secrets(self):
        state_before = self.state_path.read_text(encoding="utf-8")
        logs_before = self.sales_path.read_text(encoding="utf-8")
        result, output = self.run_main("--dry-run")
        self.assertEqual(result, 0)
        self.assertEqual(self.state_path.read_text(encoding="utf-8"), state_before)
        self.assertEqual(self.sales_path.read_text(encoding="utf-8"), logs_before)
        self.assertIn("DRY RUN: dummy salesperson created", output)
        forbidden = ("token", "secret", "oauth", "credential", "web app url", "sheet id")
        for value in forbidden:
            self.assertNotIn(value, output.lower())

    def test_execute_creates_or_updates_dashboard_test_rep_only(self):
        self.run_main("--execute")
        state = self.state()
        self.assertEqual(set(state["salespeople"]), {"existing_rep", seeder.DUMMY_SALESPERSON_ID})
        rep = state["salespeople"][seeder.DUMMY_SALESPERSON_ID]
        self.assertEqual(rep["display_name"], seeder.DUMMY_DISPLAY_NAME)
        self.assertIs(rep["active"], True)
        self.assertEqual(state["salespeople"]["existing_rep"], self.initial_state["salespeople"]["existing_rep"])

        self.run_main("--execute")
        state = self.state()
        self.assertEqual(set(state["salespeople"]), {"existing_rep", seeder.DUMMY_SALESPERSON_ID})
        self.assertEqual(state["salespeople"][seeder.DUMMY_SALESPERSON_ID]["display_name"], seeder.DUMMY_DISPLAY_NAME)

    def test_execute_appends_exactly_one_dummy_log_unless_force_is_used(self):
        self.run_main("--execute")
        self.run_main("--execute")
        dummy_logs = [record for record in self.logs() if seeder.is_dummy_log(record)]
        self.assertEqual(len(dummy_logs), 1)
        self.assertEqual(dummy_logs[0]["parsed"]["customer_name_or_ref"], seeder.DUMMY_CUSTOMER_REF)
        self.assertEqual(dummy_logs[0]["parsed"]["people_spoken_to"], 3)
        self.assertEqual(dummy_logs[0]["status"], "complete")

        self.run_main("--execute", "--force")
        dummy_logs = [record for record in self.logs() if seeder.is_dummy_log(record)]
        self.assertEqual(len(dummy_logs), 2)

    def test_cleanup_removes_only_dummy_rep_and_logs(self):
        self.run_main("--execute")
        self.run_main("--execute", "--force")
        self.run_main("--execute", "--cleanup")
        state = self.state()
        self.assertEqual(set(state["salespeople"]), {"existing_rep"})
        self.assertEqual(len(self.logs()), 1)
        self.assertEqual(self.logs()[0]["log_id"], "real-log")

    def test_admin_group_admin_user_invite_and_onboarding_state_are_preserved(self):
        self.run_main("--execute")
        self.run_main("--execute", "--cleanup")
        state = self.state()
        for key in ("groups", "users", "invites", "pending_sales_logs"):
            self.assertEqual(state[key], self.initial_state[key])

    def test_generated_sync_payload_includes_dashboard_rep_and_dummy_raw_log(self):
        self.run_main("--execute")
        state = self.state()
        payload = sheets_sync_adapter.build_sync_payloads(
            roles=json.loads((self.root / "config" / "roles.json").read_text(encoding="utf-8")),
            state=state,
            sales_logs=self.logs(),
            daily_reports=[],
            report_archive=[],
        )
        people = {row["salesperson_id"]: row for row in payload["Salespeople"]}
        self.assertIn(seeder.DUMMY_SALESPERSON_ID, people)
        self.assertEqual(people[seeder.DUMMY_SALESPERSON_ID]["display_name"], seeder.DUMMY_DISPLAY_NAME)

        dummy_rows = [
            row
            for row in payload["Raw_Logs"]
            if row["source"] == seeder.DUMMY_SOURCE and row["customer_name_or_ref"] == seeder.DUMMY_CUSTOMER_REF
        ]
        self.assertEqual(len(dummy_rows), 1)
        self.assertEqual(dummy_rows[0]["vehicle_interest"], "CR-V")

    def test_submitted_at_date_lands_inside_today_dashboard_range(self):
        self.run_main("--execute")
        dummy = next(record for record in self.logs() if seeder.is_dummy_log(record))
        self.assertTrue(dummy["submitted_at"].startswith(seeder.today_local()))
        self.assertEqual(dummy["submitted_at"][:10], seeder.today_local())
        self.assertEqual(dummy["parsed"]["followup_date"], seeder.normalize_followup_date("tomorrow", dummy["submitted_at"]))

    def test_script_has_no_live_external_or_agent_integrations(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8").lower()
        forbidden = (
            "requests",
            "urllib",
            "polling",
            "apps script",
            "openai.",
            "anthropic.",
            "openai",
            "anthropic",
            "composio",
            "hermes",
            "agentic os",
            "../" + "..",
        )
        for value in forbidden:
            self.assertNotIn(value, source)


if __name__ == "__main__":
    unittest.main()
