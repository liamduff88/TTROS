import json
import unittest
from pathlib import Path

from src.command_router import CommandRouter, CommandRoutingError


ROOT = Path(__file__).resolve().parents[1]


class CommandRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter.from_file(ROOT / "config" / "commands.json")

    def test_whitelisted_command_routes_without_tokens(self):
        route = self.router.route("/log spoke with a walk-in", "salesperson", "dm")
        self.assertEqual((route.handler, route.arguments), ("log", "spoke with a walk-in"))

    def test_unknown_command_is_rejected(self):
        with self.assertRaises(CommandRoutingError):
            self.router.route("/admin", "admin")

    def test_role_is_enforced(self):
        with self.assertRaises(CommandRoutingError):
            self.router.route("/report", "salesperson", "group")

    def test_chat_context_is_enforced(self):
        with self.assertRaises(CommandRoutingError):
            self.router.route("/today", "manager", "dm")

    def test_announce_is_draft_only_and_disabled(self):
        config = json.loads((ROOT / "config" / "commands.json").read_text(encoding="utf-8"))
        self.assertEqual(config["commands"]["announce"]["mode"], "draft_only")
        self.assertFalse(config["commands"]["announce"]["enabled"])
        with self.assertRaises(CommandRoutingError):
            self.router.route("/announce example", "admin", "group")

    def test_all_configured_commands_are_token_free(self):
        config = json.loads((ROOT / "config" / "commands.json").read_text(encoding="utf-8"))
        self.assertTrue(all(item["token_free"] is True for item in config["commands"].values()))

    def test_approved_commands_are_present(self):
        approved = {
            "start", "help", "log", "today", "team", "followups", "missing",
            "coaching", "dashboard", "report", "sync_sheets", "announce", "register_admin_group",
            "register_broadcast_group", "register_salesperson", "list_salespeople",
            "deactivate_salesperson", "invite", "create_invite", "invites", "revoke_invite", "my_status",
        }
        config = json.loads((ROOT / "config" / "commands.json").read_text(encoding="utf-8"))
        self.assertEqual(set(config["commands"]), approved)
        for command in ("register_admin_group", "register_broadcast_group"):
            self.assertTrue(config["commands"][command]["token_free"])
        for command in ("register_salesperson", "list_salespeople", "deactivate_salesperson"):
            self.assertEqual(config["commands"][command]["roles"], ["manager", "admin"])
            self.assertEqual(config["commands"][command]["context"], ["dm", "group"])
        self.assertEqual(config["commands"]["sync_sheets"]["roles"], ["manager", "admin"])
        self.assertEqual(config["commands"]["sync_sheets"]["context"], ["dm", "group"])
        self.assertEqual(config["commands"]["my_status"]["roles"], ["salesperson", "manager", "admin"])

    def test_roster_commands_route_for_authorized_live_contexts(self):
        for role in ("manager", "admin"):
            for context in ("dm", "group"):
                with self.subTest(role=role, context=context):
                    route = self.router.route("/list_salespeople", role, context)
                    self.assertEqual(route.handler, "list_salespeople")

    def test_salesperson_role_replaces_legacy_role(self):
        config = json.loads((ROOT / "config" / "commands.json").read_text(encoding="utf-8"))
        roles = {role for spec in config["commands"].values() for role in spec["roles"]}
        self.assertIn("salesperson", roles)
        legacy_role = "sales" + "_rep"
        self.assertNotIn(legacy_role, roles)


if __name__ == "__main__":
    unittest.main()
