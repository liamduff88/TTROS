import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

from src.command_router import CommandRouter
from src.local_store import LocalJsonlStore, LocalStateStore
from src.message_router import (
    LOG_SAVED,
    SAFE_HELP,
    SAFE_SCOPE_REJECTION,
    SALESPERSON_START,
    UNREGISTERED_START,
    MessageRouter,
)
from src.natural_language_router import NaturalLanguageRouter
from src.north_shore_bot_runner import main
from src.role_store import RoleStore
from src.sheets_manual_sync import SheetsManualSyncError, SheetsManualSyncResult


ROOT = Path(__file__).resolve().parents[1]


def update(text=None, *, user_id=1, chat_id=100, chat_type="private", media=False, **profile):
    message = {"from": {"id": user_id, **profile}, "chat": {"id": chat_id, "type": chat_type}}
    if media:
        message["photo"] = [{"file_id": "example"}]
    else:
        message["text"] = text
    return {"update_id": 1, "message": message}


class MessageRouterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        roles_path = root / "roles.json"
        roles_path.write_text(
            json.dumps(
                {
                    "users": {
                        "1": {"role": "salesperson", "active": True},
                        "2": {"role": "admin", "active": True},
                        "3": {"role": "manager", "active": True},
                    }
                }
            ),
            encoding="utf-8",
        )
        self.llm_fallback = Mock()
        self.router = MessageRouter(
            RoleStore(roles_path),
            CommandRouter.from_file(ROOT / "config" / "commands.json"),
            NaturalLanguageRouter(llm_enabled=False, llm_fallback=self.llm_fallback),
            LocalStateStore(root / "data" / "local_state.json"),
            LocalJsonlStore(root / "data" / "events.jsonl"),
            LocalJsonlStore(root / "data" / "sales_logs.jsonl"),
        )
        self.root = root

    def tearDown(self):
        self.temporary.cleanup()

    def test_start_from_fake_dm(self):
        self.assertEqual(self.router.handle_update(update("/start", user_id=99)), UNREGISTERED_START)
        self.assertEqual(self.router.handle_update(update("/start", user_id=1)), SALESPERSON_START)

    def test_start_updates_local_telegram_display_profile(self):
        self.router.handle_update(
            update("/start", user_id=1, first_name="Casey", last_name="Morgan", username="casey_m")
        )
        state = self.router.state_store.read()
        self.assertEqual(
            state["users"]["1"],
            {
                "telegram_user_id": "1",
                "first_name": "Casey",
                "last_name": "Morgan",
                "username": "casey_m",
            },
        )
        self.assertEqual(self.router.state_store.user_display_names()["1"], "Casey Morgan")

    def test_username_is_used_when_telegram_name_is_unavailable(self):
        self.router.handle_update(update("/start", user_id=99, username="casey_only"))
        self.assertEqual(self.router.state_store.user_display_names()["99"], "@casey_only")

    def test_register_admin_group_stores_package_local_state(self):
        reply = self.router.handle_update(update("/register_admin_group", user_id=2, chat_id=-1001, chat_type="supergroup"))
        state = json.loads((self.root / "data" / "local_state.json").read_text(encoding="utf-8"))
        self.assertEqual(state, {"groups": {"admin_group_chat_id": "-1001"}})
        self.assertIn("registered", reply.lower())

    def test_register_broadcast_group_stores_package_local_state(self):
        self.router.handle_update(update("/register_broadcast_group", user_id=3, chat_id=-1002, chat_type="group"))
        state = json.loads((self.root / "data" / "local_state.json").read_text(encoding="utf-8"))
        self.assertEqual(state, {"groups": {"broadcast_group_chat_id": "-1002"}})

    def test_today_command_and_natural_language_use_same_local_report(self):
        slash = self.router.handle_update(update("/today", user_id=2, chat_type="group"))
        natural = self.router.handle_update(update("How did the team do today?", user_id=2, chat_type="group"))
        self.assertEqual(slash, natural)
        self.assertIn("Manager briefing", slash)
        self.assertIn("Key numbers: 0 update(s)", slash)

    def test_salesperson_update_is_saved_locally(self):
        text = "Just had a walk-in looking at a CR-V and booked a follow-up tomorrow."
        reply = self.router.handle_update(
            update(text, user_id=1)
        )
        records = list(LocalJsonlStore(self.root / "data" / "sales_logs.jsonl").records())
        self.assertTrue(reply.startswith(LOG_SAVED))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["raw_text"], text)
        self.assertEqual(records[0]["source"], "telegram_dm")

    def test_unknown_is_safe_and_adapters_are_not_called(self):
        reply = self.router.handle_update(update("Run /work through Hermes and edit files", user_id=2, chat_type="group"))
        self.assertEqual(reply, SAFE_SCOPE_REJECTION)
        self.llm_fallback.assert_not_called()
        self.assertFalse((self.root / "data" / "local_state.json").exists())
        self.assertFalse((self.root / "data" / "events.jsonl").exists())
        self.assertFalse((self.root / "data" / "sales_logs.jsonl").exists())

    def test_admin_general_requests_are_rejected_before_valid_keyword_matches(self):
        examples = (
            "Ask Codex to generate a report",
            "Use Claude to show the dashboard",
            "Search the web for follow-ups due today",
            "Run a Composio tool for the team scorecard",
        )
        for text in examples:
            with self.subTest(text=text):
                self.assertEqual(
                    self.router.handle_update(update(text, user_id=2, chat_type="group")),
                    SAFE_SCOPE_REJECTION,
                )
        self.llm_fallback.assert_not_called()

    def test_salesperson_dm_cannot_trigger_admin_or_general_actions(self):
        for text in ("/report", "/work", "Generate a report", "Run an agent to edit files"):
            with self.subTest(text=text):
                reply = self.router.handle_update(update(text, user_id=1))
                self.assertIn(reply, {SAFE_HELP, SAFE_SCOPE_REJECTION})
        self.assertFalse((self.root / "data" / "sales_logs.jsonl").exists())

    def test_dashboard_link_is_local_and_token_free(self):
        self.router.dashboard_url = "https://example.invalid/north-shore"
        slash = self.router.handle_update(update("/dashboard", user_id=2, chat_type="group"))
        natural = self.router.handle_update(update("Show the North Shore dashboard link", user_id=2, chat_type="group"))
        self.assertEqual(slash, natural)
        self.assertEqual(slash, "North Shore dashboard: https://example.invalid/north-shore")
        self.llm_fallback.assert_not_called()

    def test_admin_sync_sheets_command_runs_injected_manual_sync(self):
        self.router.sheets_sync_runner = Mock(
            return_value=SheetsManualSyncResult(
                provider="apps_script_webapp",
                tabs=("Raw_Logs", "Report_Archive"),
                row_count=3,
                post_count=2,
            )
        )
        reply = self.router.handle_update(update("/sync_sheets", user_id=2, chat_type="group"))
        self.assertEqual(
            reply,
            "Sheets sync completed: 3 row(s) across 2 tab(s): Raw_Logs, Report_Archive.\n"
            "Note: this sync is append-only, so running it again may duplicate rows.",
        )
        self.assertIn("append-only", reply)
        self.assertIn("duplicate rows", reply)
        self.router.sheets_sync_runner.assert_called_once_with()

    def test_salesperson_sync_sheets_command_is_rejected(self):
        self.router.sheets_sync_runner = Mock()
        reply = self.router.handle_update(update("/sync_sheets", user_id=1, chat_type="group"))
        self.assertEqual(reply, SAFE_HELP)
        self.router.sheets_sync_runner.assert_not_called()

    def test_sync_sheets_failure_is_closed(self):
        self.router.sheets_sync_runner = Mock(side_effect=SheetsManualSyncError("writes are disabled"))
        reply = self.router.handle_update(update("/sync_sheets", user_id=3, chat_type="group"))
        self.assertEqual(reply, "Sheets sync not completed: writes are disabled")

    def _invite_code_from_reply(self, reply):
        return next(part for part in reply.split() if part.startswith("NS-"))

    def test_admin_creates_manager_invite(self):
        reply = self.router.handle_update(update("/invite manager Ryan McVeigh", user_id=2, chat_type="group"))
        self.assertIn("Invite ready for Ryan McVeigh (manager).", reply)
        self.assertIn("/start NS-", reply)
        invite = self.router.state_store.pending_invites()[0]
        self.assertEqual(invite["role"], "manager")
        self.assertEqual(invite["display_name"], "Ryan McVeigh")
        self.assertEqual(invite["created_by"], "2")
        self.assertIsNone(invite["used_at"])
        self.assertIsNone(invite["used_by"])
        self.assertIsNone(invite["revoked_at"])

    def test_admin_creates_salesperson_invite(self):
        reply = self.router.handle_update(update("/create_invite salesperson Sarah Jones", user_id=2))
        self.assertIn("Invite ready for Sarah Jones (salesperson).", reply)

    def test_manager_creates_salesperson_invite(self):
        reply = self.router.handle_update(update("/invite salesperson Sarah Jones", user_id=3, chat_type="group"))
        self.assertIn("Invite ready for Sarah Jones (salesperson).", reply)

    def test_manager_cannot_create_manager_or_admin_invite(self):
        self.assertEqual(
            self.router.handle_update(update("/invite manager Ryan McVeigh", user_id=3, chat_type="group")),
            "Managers can only invite salespeople.",
        )
        self.assertEqual(
            self.router.handle_update(update("/invite admin Pat Lee", user_id=3, chat_type="group")),
            "Managers can invite salespeople. Admin invites are not available here.",
        )

    def test_salesperson_and_unregistered_users_cannot_create_invite(self):
        self.assertEqual(self.router.handle_update(update("/invite salesperson Sarah Jones", user_id=1)), SAFE_HELP)
        self.assertEqual(self.router.handle_update(update("/invite salesperson Sarah Jones", user_id=99)), SAFE_HELP)
        self.assertEqual(self.router.state_store.pending_invites(), [])

    def test_start_code_in_dm_redeems_once_and_links_salesperson(self):
        created = self.router.handle_update(update("/invite salesperson Sarah Jones", user_id=2))
        code = self._invite_code_from_reply(created)
        reply = self.router.handle_update(update(f"/start {code}", user_id=44, first_name="Sarah"))
        self.assertEqual(reply, "Welcome, Sarah Jones. You are set up as a salesperson.")
        self.assertEqual(self.router.handle_update(update("/my_status", user_id=44)), "You are registered as Sarah Jones (salesperson).")
        state = self.router.state_store.read()
        self.assertEqual(state["users"]["44"]["role"], "salesperson")
        self.assertEqual(state["users"]["44"]["salesperson_id"], "sarah-jones")
        self.assertEqual(state["salespeople"]["sarah-jones"]["telegram_user_id"], "44")
        self.assertEqual(state["invites"][code]["used_by"], "44")
        self.assertIsNotNone(state["invites"][code]["used_at"])
        self.assertNotIn("redeemed_by", state["invites"][code])
        self.assertNotIn("redeemed_at", state["invites"][code])
        self.assertEqual(
            self.router.handle_update(update(f"/start {code}", user_id=45)),
            "That invite code has already been used.",
        )

    def test_start_code_in_group_is_rejected_with_dm_instruction(self):
        created = self.router.handle_update(update("/invite salesperson Sarah Jones", user_id=2))
        code = self._invite_code_from_reply(created)
        reply = self.router.handle_update(update(f"/start {code}", user_id=44, chat_type="group"))
        self.assertIn("redeem invite codes in a DM", reply)
        self.assertIsNone(self.router.state_store.role_for(44))

    def test_invite_expiry(self):
        created = self.router.handle_update(update("/invite salesperson Sarah Jones", user_id=2))
        code = self._invite_code_from_reply(created)
        state = self.router.state_store.read()
        state["invites"][code]["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        self.router.state_store._write(state)
        self.assertEqual(
            self.router.handle_update(update(f"/start {code}", user_id=44)),
            "That invite code has expired. Ask your manager for a new one.",
        )

    def test_invite_revoke(self):
        created = self.router.handle_update(update("/invite salesperson Sarah Jones", user_id=2))
        code = self._invite_code_from_reply(created)
        self.assertEqual(
            self.router.handle_update(update(f"/revoke_invite {code}", user_id=2)),
            "Invite revoked for Sarah Jones.",
        )
        self.assertIsNotNone(self.router.state_store.read()["invites"][code]["revoked_at"])
        self.assertEqual(self.router.handle_update(update(f"/start {code}", user_id=44)), "That invite code is no longer active.")

    def test_manager_redemption_creates_manager_user_only(self):
        created = self.router.handle_update(update("/invite manager Ryan McVeigh", user_id=2))
        code = self._invite_code_from_reply(created)
        reply = self.router.handle_update(update(f"/start {code}", user_id=55))
        self.assertEqual(reply, "Welcome, Ryan McVeigh. You are set up as a manager.")
        state = self.router.state_store.read()
        self.assertEqual(state["users"]["55"]["role"], "manager")
        self.assertNotIn("salesperson_id", state["users"]["55"])
        self.assertNotIn("ryan-mcveigh", state.get("salespeople", {}))

    def test_natural_language_invite_creation_defaults_to_salesperson(self):
        reply = self.router.handle_update(update("create invite for Sarah Jones", user_id=2, chat_type="group"))
        self.assertIn("Invite ready for Sarah Jones (salesperson).", reply)
        manager_reply = self.router.handle_update(update("create invite for Ryan McVeigh as manager", user_id=2, chat_type="group"))
        self.assertIn("Invite ready for Ryan McVeigh (manager).", manager_reply)

    def test_invites_output(self):
        self.router.handle_update(update("/invite salesperson Sarah Jones", user_id=2))
        reply = self.router.handle_update(update("/invites", user_id=3))
        self.assertIn("Pending invites:", reply)
        self.assertIn("Sarah Jones (salesperson): NS-", reply)
        self.assertNotIn("created_by", reply)
        self.assertNotIn("user_id", reply)

    def test_salesperson_invite_collision_gets_stable_new_id(self):
        self.router.state_store.register_salesperson("Sarah Jones", telegram_user_id=99)
        created = self.router.handle_update(update("/invite salesperson Sarah Jones", user_id=2))
        code = self._invite_code_from_reply(created)
        self.router.handle_update(update(f"/start {code}", user_id=44))
        state = self.router.state_store.read()
        self.assertIn("sarah-jones-2", state["salespeople"])
        self.assertEqual(state["users"]["44"]["salesperson_id"], "sarah-jones-2")


class RunnerSafetyTests(unittest.TestCase):
    def test_missing_token_exits_safely(self):
        stdout = StringIO()
        stderr = StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(stdout), redirect_stderr(stderr):
            result = main()
        self.assertEqual(result, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("required", stderr.getvalue())
        self.assertIn("not started", stderr.getvalue())

    def test_runner_source_does_not_print_token_or_import_bridge(self):
        source = (ROOT / "src" / "north_shore_bot_runner.py").read_text(encoding="utf-8")
        self.assertNotIn("print(token", source)
        forbidden_modules = ("connec" + "tors", "telegram" + "_bridge")
        for module in forbidden_modules:
            self.assertNotIn("from " + module, source)
            self.assertNotIn("import " + module, source)


if __name__ == "__main__":
    unittest.main()
