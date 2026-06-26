import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "reset_demo_data_pre_ryan.py"
SPEC = importlib.util.spec_from_file_location("reset_demo_data_pre_ryan", SCRIPT_PATH)
resetter = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(resetter)


class PreRyanResetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "data").mkdir()
        self.state_path = self.root / "data" / "local_state.json"
        self.sales_path = self.root / "data" / "sales_logs.jsonl"
        self.report_path = self.root / "data" / "report_archive.jsonl"
        self.events_path = self.root / "data" / "events.jsonl"
        self.invite_path = self.root / "data" / "invites.json"
        self.roster_path = self.root / "data" / "roster_state.json"
        self.state = {
            "groups": {"admin_group_chat_id": "admin-group", "broadcast_group_chat_id": "broadcast-group"},
            "users": {
                "admin-user": {
                    "telegram_user_id": "admin-user",
                    "display_name": "Liam Admin",
                    "role": "admin",
                    "active": True,
                },
                "local_dummy_dashboard_test": {
                    "telegram_user_id": "local_dummy_dashboard_test",
                    "display_name": "Dashboard Test Rep",
                },
            },
            "invites": {
                "NS-REAL-0001": {
                    "code": "NS-REAL-0001",
                    "role": "salesperson",
                    "display_name": "Ryan Ready Rep",
                    "status": "pending",
                }
            },
            "onboarding": {"last_invite_role": "salesperson"},
            "salespeople": {
                "dashboard_test_rep": {
                    "salesperson_id": "dashboard_test_rep",
                    "display_name": "Dashboard Test Rep",
                    "source": "local_visual_dashboard_dummy_test",
                },
                "demo-rep": {
                    "salesperson_id": "demo-rep",
                    "display_name": "Demo Rep",
                    "active": False,
                },
                "real-rep": {
                    "salesperson_id": "real-rep",
                    "display_name": "Ryan Ready Rep",
                    "active": True,
                },
            },
            "pending_sales_logs": {
                "admin-user": {"log_id": "old-demo-log", "field": "outcome"},
                "local_dummy_dashboard_test": {"log_id": "dashboard-test", "field": "next_step"},
            },
            "sync_counters": {
                "last_customer_ref": "DASHBOARD_TEST_CUSTOMER",
                "real_counter": 3,
            },
        }
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        self.sales_path.write_text(
            "\n".join(
                [
                    json.dumps({"log_id": "old-demo-log", "customer_ref": "OLD_LOCAL_TEST"}),
                    json.dumps(
                        {
                            "log_id": "dashboard-test",
                            "telegram_user_id": "local_dummy_dashboard_test",
                            "customer_ref": "DASHBOARD_TEST_CUSTOMER",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        self.report_path.write_text(json.dumps({"report_id": "demo-report"}) + "\n", encoding="utf-8")
        self.events_path.write_text(json.dumps({"event": "demo-event"}) + "\n", encoding="utf-8")
        self.invite_path.write_text(json.dumps({"pending": ["NS-REAL-0001"]}), encoding="utf-8")
        self.roster_path.write_text(json.dumps({"active": ["real-rep"]}), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def run_main(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = resetter.main([*args, "--root", str(self.root)])
        return result, output.getvalue()

    def read_state(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def test_dry_run_does_not_mutate_files_or_print_secrets(self):
        before = {path: path.read_text(encoding="utf-8") for path in (self.state_path, self.sales_path, self.report_path, self.events_path)}
        result, output = self.run_main("--dry-run")
        self.assertEqual(result, 0)
        self.assertEqual({path: path.read_text(encoding="utf-8") for path in before}, before)
        self.assertFalse((self.root / "data" / "backups").exists())
        for forbidden in ("token", "oauth", "credential", "web app url", "sheet id", "admin-user"):
            self.assertNotIn(forbidden, output.lower())

    def test_execute_creates_timestamped_backup_and_archives_runtime_files(self):
        result, output = self.run_main("--execute")
        self.assertEqual(result, 0)
        backups = list((self.root / "data" / "backups").glob("pre_ryan_reset_*"))
        self.assertEqual(len(backups), 1)
        self.assertRegex(backups[0].name, r"pre_ryan_reset_\d{8}_\d{6}")
        archived = {path.name for path in backups[0].iterdir()}
        self.assertEqual(
            archived,
            {"sales_logs.jsonl", "report_archive.jsonl", "events.jsonl", "local_state.json", "invites.json", "roster_state.json"},
        )
        self.assertIn("backup folder created:", output)

    def test_execute_clears_sales_report_and_event_jsonl_files(self):
        self.run_main("--execute")
        self.assertEqual(self.sales_path.read_text(encoding="utf-8"), "")
        self.assertEqual(self.report_path.read_text(encoding="utf-8"), "")
        self.assertEqual(self.events_path.read_text(encoding="utf-8"), "")

    def test_local_state_preserves_admin_group_admin_user_and_invites(self):
        self.run_main("--execute")
        state = self.read_state()
        self.assertEqual(state["groups"], self.state["groups"])
        self.assertEqual(state["users"]["admin-user"], self.state["users"]["admin-user"])
        self.assertEqual(state["invites"], self.state["invites"])
        self.assertEqual(state["onboarding"], self.state["onboarding"])

    def test_demo_roster_customer_markers_and_pending_flows_are_removed(self):
        self.run_main("--execute")
        state = self.read_state()
        self.assertEqual(set(state["salespeople"]), {"real-rep"})
        rendered = json.dumps(state)
        for marker in ("Dashboard Test Rep", "dashboard_test_rep", "DASHBOARD_TEST_CUSTOMER", "local_dummy_dashboard_test"):
            self.assertNotIn(marker, rendered)
        self.assertNotIn("pending_sales_logs", state)
        self.assertEqual(state["sync_counters"], {"real_counter": 3})

    def test_visual_dashboard_only_preserves_non_dummy_sales_logs(self):
        self.run_main("--execute", "--visual-dashboard-only")
        self.assertIn("old-demo-log", self.sales_path.read_text(encoding="utf-8"))
        self.assertNotIn("DASHBOARD_TEST_CUSTOMER", self.sales_path.read_text(encoding="utf-8"))
        self.assertEqual(self.report_path.read_text(encoding="utf-8"), json.dumps({"report_id": "demo-report"}) + "\n")

    def test_script_refuses_to_run_without_mode(self):
        with self.assertRaises(SystemExit) as raised:
            resetter.main(["--root", str(self.root)])
        self.assertNotEqual(raised.exception.code, 0)
        self.assertFalse((self.root / "data" / "backups").exists())

    def test_script_has_no_live_external_or_agent_integrations(self):
        source = SCRIPT_PATH.read_text(encoding="utf-8").lower()
        forbidden = (
            "requests",
            "urllib",
            "polling",
            "apps " + "script",
            "open" + "ai.",
            "anth" + "ropic.",
            "com" + "posio",
            "her" + "mes",
            "agentic " + "os",
            "../" + "..",
        )
        for value in forbidden:
            self.assertNotIn(value, source)


if __name__ == "__main__":
    unittest.main()
