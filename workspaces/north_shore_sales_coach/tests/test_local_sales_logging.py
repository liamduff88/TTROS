import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.command_router import CommandRouter
from src.local_store import LocalJsonlStore, LocalStateStore
from src.message_router import LOG_COMPLETED, LOG_SAVED, SAFE_HELP, MessageRouter
from src.natural_language_router import NaturalLanguageRouter
from src.role_store import RoleStore
from src.sales_log_parser import parse_sales_log


ROOT = Path(__file__).resolve().parents[1]


def telegram_update(text, *, user_id=10, chat_type="private"):
    return {
        "update_id": 1,
        "message": {
            "from": {"id": user_id},
            "chat": {"id": 500, "type": chat_type},
            "text": text,
        },
    }


class LocalSalesLoggingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        roles = root / "roles.json"
        roles.write_text(
            json.dumps(
                {
                    "users": {
                        "10": {"role": "salesperson", "active": True},
                        "20": {"role": "admin", "active": True},
                        "30": {"role": "manager", "active": True},
                    }
                }
            ),
            encoding="utf-8",
        )
        self.sales_path = root / "data" / "sales_logs.jsonl"
        self.llm_fallback = Mock()
        self.router = MessageRouter(
            RoleStore(roles),
            CommandRouter.from_file(ROOT / "config" / "commands.json"),
            NaturalLanguageRouter(llm_enabled=False, llm_fallback=self.llm_fallback),
            LocalStateStore(root / "data" / "local_state.json"),
            LocalJsonlStore(root / "data" / "events.jsonl"),
            LocalJsonlStore(self.sales_path),
        )

    def tearDown(self):
        self.temporary.cleanup()

    def records(self):
        return list(LocalJsonlStore(self.sales_path).records())

    def test_natural_language_update_appends_one_jsonl_record(self):
        text = "Had a walk-in for a Civic, test drove it, follow-up next week."
        reply = self.router.handle_update(telegram_update(text))
        records = self.records()
        self.assertTrue(reply.startswith(LOG_SAVED))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["raw_text"], text)
        self.assertEqual(records[0]["parsed"]["vehicle_interest"], "Civic")
        self.assertTrue(records[0]["parsed"]["test_drive"])
        self.assertRegex(records[0]["parsed"]["followup_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertFalse(records[0]["llm_used"])
        self.assertIsNone(records[0]["llm_tokens_estimate"])

    def test_log_command_appends_one_jsonl_record(self):
        text = "Spoke to 3 people about an Accord and presented numbers"
        reply = self.router.handle_update(telegram_update(f"/log {text}"))
        records = self.records()
        self.assertTrue(reply.startswith(LOG_SAVED))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["raw_text"], text)
        self.assertEqual(records[0]["parsed"]["people_spoken_to"], 3)

    def test_admin_test_user_can_log_in_dm(self):
        reply = self.router.handle_update(telegram_update("/log Walk-in for a Pilot", user_id=20))
        self.assertTrue(reply.startswith(LOG_SAVED))
        self.assertEqual(len(self.records()), 1)

    def test_group_sales_text_does_not_save_private_log(self):
        reply = self.router.handle_update(telegram_update("Walk-in for a Passport", chat_type="group"))
        self.assertEqual(reply, SAFE_HELP)
        self.assertFalse(self.sales_path.exists())

    def test_unknown_user_cannot_save_log(self):
        slash_reply = self.router.handle_update(telegram_update("/log Walk-in for an Odyssey", user_id=999))
        natural_reply = self.router.handle_update(telegram_update("Walk-in for an Odyssey", user_id=999))
        self.assertEqual(slash_reply, SAFE_HELP)
        self.assertEqual(natural_reply, SAFE_HELP)
        self.assertFalse(self.sales_path.exists())

    def test_no_llm_or_sheets_adapter_is_called(self):
        self.router.handle_update(telegram_update("Walk-in for a Ridgeline"))
        self.llm_fallback.assert_not_called()
        self.assertEqual(len(self.records()), 1)

    def test_pending_answer_updates_correct_log_and_clears_state(self):
        text = (
            "Had a CR-V walk-in today. Spoke to 2 people, did a test drive, "
            "presented numbers, asked for the business, following up tomorrow."
        )
        first_reply = self.router.handle_update(telegram_update(f"/log {text}"))
        original = self.records()[0]
        self.assertIn("What was the outcome?", first_reply)
        pending = self.router.state_store.pending_sales_log(10)
        self.assertEqual(pending, {"log_id": original["log_id"], "field": "outcome"})

        answer = "They will come back next week"
        second_reply = self.router.handle_update(telegram_update(answer))
        records = self.records()
        self.assertEqual(second_reply, LOG_COMPLETED)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["log_id"], original["log_id"])
        self.assertEqual(records[0]["parsed"]["outcome"], answer)
        self.assertEqual(records[0]["parsed"]["next_step"], answer)
        self.assertRegex(records[0]["parsed"]["followup_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(records[0]["missing_fields"], [])
        self.assertEqual(records[0]["status"], "complete")
        self.assertIsNone(self.router.state_store.pending_sales_log(10))
        self.llm_fallback.assert_not_called()

    def test_answer_only_replaces_log_named_by_pending_state(self):
        self.router.handle_update(telegram_update("/log Walk-in for a Civic"))
        first = self.records()[0]
        unrelated = parse_sales_log("Walk-in for an Accord", "20")
        LocalJsonlStore(self.sales_path).append(unrelated)
        self.router.handle_update(telegram_update("walk-in"))
        records = self.records()
        self.assertEqual(records[0]["log_id"], first["log_id"])
        self.assertEqual(records[0]["parsed"]["interaction_type"], "walk_in")
        self.assertEqual(records[1], unrelated)

    def test_unknown_private_message_without_pending_state_uses_safe_fallback(self):
        reply = self.router.handle_update(telegram_update("Hello there"))
        self.assertEqual(reply, SAFE_HELP)
        self.assertFalse(self.sales_path.exists())
        self.llm_fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
