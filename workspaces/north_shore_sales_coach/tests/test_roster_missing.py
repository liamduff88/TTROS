import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.command_router import CommandRouter
from src.local_store import LocalJsonlStore, LocalStateStore
from src.message_router import EMPTY_ROSTER, SAFE_HELP, MessageRouter
from src.natural_language_router import NaturalLanguageRouter
from src.role_store import RoleStore


ROOT = Path(__file__).resolve().parents[1]


def group_update(text, user_id):
    return {
        "message": {
            "from": {"id": user_id},
            "chat": {"id": -100, "type": "group"},
            "text": text,
        }
    }


def dm_update(text, user_id):
    return {
        "message": {
            "from": {"id": user_id, "first_name": "Demo"},
            "chat": {"id": user_id, "type": "private"},
            "text": text,
        }
    }


def log_record(person, *, complete):
    parsed = {
        "people_spoken_to": 1,
        "test_drive": False,
        "worksheet_or_offer_presented": False,
        "asked_for_business": False,
        "outcome": "Follow-up",
        "next_step": "Call tomorrow" if complete else None,
    }
    return {
        "log_id": "log-" + person,
        "submitted_at": date.today().isoformat() + "T12:00:00Z",
        "telegram_user_id": person,
        "salesperson_id": person,
        "parsed": parsed,
        "missing_fields": [] if complete else ["next_step"],
        "status": "complete" if complete else "needs_followup",
        "llm_used": False,
    }


class RosterMissingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        roles_path = root / "roles.json"
        roles_path.write_text(
            json.dumps(
                {
                    "users": {
                        "1": {"role": "admin", "active": True},
                        "2": {"role": "manager", "active": True},
                        "3": {"role": "salesperson", "active": True, "display_name": "Demo Salesperson"},
                    }
                }
            ),
            encoding="utf-8",
        )
        self.state = LocalStateStore(root / "data" / "local_state.json")
        self.sales = LocalJsonlStore(root / "data" / "sales_logs.jsonl")
        self.router = MessageRouter(
            RoleStore(roles_path),
            CommandRouter.from_file(ROOT / "config" / "commands.json"),
            NaturalLanguageRouter(llm_enabled=False),
            self.state,
            LocalJsonlStore(root / "data" / "events.jsonl"),
            self.sales,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_admin_can_register_and_list_active_salespeople(self):
        reply = self.router.handle_update(group_update("/register_salesperson Demo Taylor", 1))
        listed = self.router.handle_update(group_update("/list_salespeople", 1))
        self.assertIn("demo-taylor", reply)
        self.assertIn("Demo Taylor (demo-taylor)", listed)
        self.assertEqual(self.state.salesperson_roster(), {"demo-taylor": "Demo Taylor"})

    def test_empty_roster_list_is_recognized_and_friendly(self):
        reply = self.router.handle_update(group_update("/list_salespeople", 1))
        self.assertEqual(reply, EMPTY_ROSTER)
        self.assertNotEqual(reply, SAFE_HELP)

    def test_manager_can_manage_roster_from_dm_or_group(self):
        registered = self.router.handle_update(dm_update("/register_salesperson Demo Rep", 2))
        listed = self.router.handle_update(group_update("/list_salespeople", 2))
        self.assertIn("Demo Rep", registered)
        self.assertIn("Demo Rep", listed)

    def test_non_admin_cannot_register_or_deactivate(self):
        for command in ("/register_salesperson Demo Taylor", "/deactivate_salesperson Demo Taylor"):
            with self.subTest(command=command):
                self.assertEqual(self.router.handle_update(group_update(command, 3)), SAFE_HELP)
        self.assertEqual(self.state.salespeople(), [])

    def test_deactivation_excludes_person_from_missing_without_deleting_history(self):
        self.state.register_salesperson("Demo Rep")
        self.router.handle_update(group_update("/deactivate_salesperson Demo Rep", 1))
        records = self.state.salespeople()
        self.assertEqual(len(records), 1)
        self.assertFalse(records[0]["active"])
        self.assertEqual(self.router.handle_update(group_update("/list_salespeople", 1)), EMPTY_ROSTER)
        missing = self.router.handle_update(group_update("/missing", 1))
        self.assertNotIn("Demo Rep", missing)

    def test_missing_includes_no_complete_update_and_incomplete_log(self):
        self.state.register_salesperson("Demo Taylor")
        self.state.register_salesperson("Sample Jordan")
        self.sales.append(log_record("demo-taylor", complete=False))
        missing = self.router.handle_update(group_update("/missing", 1))
        self.assertIn("Demo Taylor", missing)
        self.assertIn("Sample Jordan", missing)
        self.assertIn("Demo Taylor: next_step", missing)

    def test_natural_language_uses_same_roster_backed_missing_logic(self):
        self.state.register_salesperson("Demo Taylor")
        slash = self.router.handle_update(group_update("/missing", 1))
        natural = self.router.handle_update(group_update("Who hasn't updated?", 1))
        self.assertEqual(natural, slash)
        self.assertIn("Demo Taylor", natural)

    def test_unregistered_log_submitter_is_safe_fallback(self):
        self.state.register_salesperson("Demo Taylor")
        self.sales.append(log_record("external-demo-id", complete=True))
        missing = self.router.handle_update(group_update("/missing", 1))
        self.assertIn("Unregistered submitters: Unregistered salesperson", missing)
        self.assertNotIn("external-demo-id", missing)

    def test_missing_keeps_incomplete_logs_with_empty_roster(self):
        self.sales.append(log_record("external-demo-id", complete=False))
        missing = self.router.handle_update(group_update("/missing", 2))
        self.assertIn("Incomplete logs (1)", missing)
        self.assertIn("next_step", missing)


if __name__ == "__main__":
    unittest.main()
