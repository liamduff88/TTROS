import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.command_router import CommandRouter, Route
from src.natural_language_router import MessageRouter, NaturalLanguageRouter


ROOT = Path(__file__).resolve().parents[1]


class NaturalLanguageRouterTests(unittest.TestCase):
    def setUp(self):
        self.llm_fallback = Mock()
        self.router = NaturalLanguageRouter(llm_enabled=False, llm_fallback=self.llm_fallback)

    def test_salesperson_updates_map_to_sales_activity(self):
        examples = (
            "I just had a walk-in for a CR-V and booked a follow-up tomorrow",
            "Had a couple come in, test drove a Civic, numbers were high",
            "Spoke to 3 people today, one test drive, no worksheet yet",
        )
        for message in examples:
            with self.subTest(message=message):
                route = self.router.route(message, "salesperson", "dm")
                self.assertEqual(route.intent, "log_sales_activity")
                self.assertEqual(route.handler, "log")
                self.assertTrue(route.token_free_route)
                self.assertTrue(route.llm_allowed_for_parse_only)

    def test_manager_and_admin_intents(self):
        examples = {
            "How did the team do today?": "today",
            "Show me today's summary": "today",
            "Who hasn't updated?": "missing",
            "What follow-ups are due?": "followups",
            "Any coaching flags?": "coaching",
            "Give me the team scorecard": "team",
            "Generate a report": "report",
            "Show the North Shore dashboard link": "dashboard",
        }
        for message, expected in examples.items():
            with self.subTest(message=message):
                route = self.router.route(message, "admin", "group")
                self.assertEqual(route.intent, expected)
                self.assertTrue(route.token_free_route)

    def test_general_capability_requests_are_locally_rejected(self):
        unsafe_requests = (
            "Send this to Hermes /work",
            "Ask Codex to edit files",
            "Run Claude with Composio and control the OS dashboard",
            "Generate a report by searching the internet",
            "Use web search for follow-ups due today",
            "Run an agent to create files",
            "Execute a connector tool",
        )
        for message in unsafe_requests:
            with self.subTest(message=message):
                route = self.router.route(message, "admin", "group")
                self.assertEqual(route.intent, "scope_rejected")
                self.assertEqual(route.handler, "help")
                self.assertTrue(route.token_free_route)
                self.assertFalse(route.llm_allowed_for_parse_only)
        self.llm_fallback.assert_not_called()

    def test_unknown_remains_local_even_if_llm_metadata_is_enabled(self):
        fallback = Mock(return_value="report")
        router = NaturalLanguageRouter(llm_enabled=True, llm_fallback=fallback)
        route = router.route("Do something unrelated", "admin", "group")
        self.assertEqual(route.intent, "unknown_help")
        self.assertTrue(route.token_free_route)
        fallback.assert_not_called()

    def test_salesperson_cannot_route_admin_or_os_intents(self):
        for message in ("Generate a report", "Who hasn't updated?", "Ask Claude for a report"):
            with self.subTest(message=message):
                route = self.router.route(message, "salesperson", "dm")
                self.assertIn(route.intent, {"unknown_help", "scope_rejected"})
                self.assertTrue(route.token_free_route)

    def test_slash_commands_delegate_to_command_router(self):
        command_router = Mock(spec=CommandRouter)
        command_router.route.return_value = Route(command="today", handler="today", arguments="")
        message_router = MessageRouter(command_router, self.router)
        result = message_router.route("/today", "admin", "group")
        command_router.route.assert_called_once_with("/today", "admin", "group")
        self.assertEqual(result.command, "today")

    def test_non_slash_messages_delegate_to_natural_language_router(self):
        command_router = Mock(spec=CommandRouter)
        natural_router = Mock(spec=NaturalLanguageRouter)
        natural_router.route.return_value = self.router.route("Who hasn't updated?", "admin", "group")
        message_router = MessageRouter(command_router, natural_router)
        result = message_router.route("Who hasn't updated?", "admin", "group")
        command_router.route.assert_not_called()
        natural_router.route.assert_called_once()
        self.assertEqual(result.intent, "missing")

    def test_no_bridge_imports_in_package(self):
        forbidden_modules = ("connec" + "tors", "telegram" + "_bridge")
        for path in [*sorted((ROOT / "src").glob("*.py")), *sorted((ROOT / "tests").glob("*.py"))]:
            content = path.read_text(encoding="utf-8")
            for module in forbidden_modules:
                self.assertNotIn("from " + module, content)
                self.assertNotIn("import " + module, content)


if __name__ == "__main__":
    unittest.main()
