"""Telegram bridge -> ask-david reply_context forwarding (Shared Brain reply routing, plan section 22).

The bridge forwards only a bounded view of the replied-to message: text, message_id, from_bot.
An ordinary (non-reply) message posts exactly {"text": ...}, as before.
"""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import dashboard.backend.test_composio_hermes as backend_harness

backend = backend_harness.backend
BRIDGE = Path(__file__).parents[1] / "connectors" / "telegram_bridge" / "telegram_bridge.py"


def load_bridge():
    """Load the bridge with a fake token so the real .env is never read (as test_telegram_bridge_formatting)."""
    module_name = "telegram_bridge_reply_context_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, BRIDGE)
    module = importlib.util.module_from_spec(spec)
    with patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value="TELEGRAM_BOT_TOKEN=fake-token\n"), \
         patch.object(Path, "mkdir"):
        spec.loader.exec_module(module)
    return module


telegram_bridge = load_bridge()

OPERATOR = 123
ALLOWED = {"operator_chat_ids": [OPERATOR], "pilots": {}}
MARKER_TEXT = "TTROS WORKSTREAM stream-a v2\nShared Brain workflow returned: stream-a\nReply to this message to answer; Claude continues stream-a with your answer."


def bot_reply(text=MARKER_TEXT, **extra):
    reply = {
        "message_id": 77,
        "from": {"id": 999, "is_bot": True, "first_name": "TTROS", "username": "ttros_bot"},
        "chat": {"id": OPERATOR, "type": "private"},
        "date": 1790000000,
        "text": text,
        "entities": [{"type": "bold", "offset": 0, "length": 5}],
    }
    reply.update(extra)
    return reply


class TelegramBridgeReplyContextTests(unittest.TestCase):
    def run_operator_message(self, message, mode=telegram_bridge.MODE_DAVID):
        """Drive handle_message synchronously; return (ask-david payloads, agent dispatches)."""
        posted = []

        def run_inline(target=None, args=(), **_kwargs):
            class Inline:
                def start(self_inner):
                    target(*args)
            return Inline()

        def post(route, payload, timeout=None):
            posted.append((route, payload))
            return {"success": True, "kind": "david_reply", "response": "ok"}

        with patch.object(telegram_bridge, "load_allowed", return_value=ALLOWED), \
             patch.object(telegram_bridge, "get_chat_mode", return_value=mode), \
             patch.object(telegram_bridge.threading, "Thread", side_effect=run_inline), \
             patch.object(telegram_bridge, "post_backend_json", side_effect=post), \
             patch.object(telegram_bridge, "dispatch_agent_request") as agent, \
             patch.object(telegram_bridge, "send"), \
             patch.object(telegram_bridge, "log"):
            telegram_bridge.handle_message(message, delivery_id=f"telegram-update-{len(str(message))}")
        return posted, agent

    def test_ordinary_david_message_posts_text_only_unchanged(self):
        posted, agent = self.run_operator_message({"chat": {"id": OPERATOR}, "message_id": 5, "text": "How is Acme going?"})
        self.assertEqual(posted, [(telegram_bridge.ASK_DAVID_ROUTE, {"text": "How is Acme going?"})])
        agent.assert_not_called()

    def test_reply_to_bot_marker_forwards_only_bounded_fields(self):
        posted, _ = self.run_operator_message(
            {"chat": {"id": OPERATOR}, "message_id": 6, "text": "US$29.", "reply_to_message": bot_reply()})
        self.assertEqual(len(posted), 1)
        route, payload = posted[0]
        self.assertEqual(route, telegram_bridge.ASK_DAVID_ROUTE)
        self.assertEqual(set(payload), {"text", "reply_context"})
        self.assertEqual(payload["text"], "US$29.")
        self.assertEqual(payload["reply_context"], {"text": MARKER_TEXT, "message_id": 77, "from_bot": True})

    def test_reply_context_is_bounded_and_strictly_typed(self):
        cases = [
            (bot_reply(text="x" * 5000), {"text": "x" * 4096, "message_id": 77, "from_bot": True}),
            (bot_reply(text=None, caption="TTROS WORKSTREAM stream-a v2"),
             {"text": "TTROS WORKSTREAM stream-a v2", "message_id": 77, "from_bot": True}),
            (bot_reply(**{"from": {"id": 5, "is_bot": False}}), {"text": MARKER_TEXT, "message_id": 77, "from_bot": False}),
            (bot_reply(**{"from": {"id": 5, "is_bot": "true"}}), {"text": MARKER_TEXT, "message_id": 77, "from_bot": False}),
            ({"message_id": "77", "text": MARKER_TEXT}, {"text": MARKER_TEXT, "message_id": None, "from_bot": False}),
            ({"message_id": True, "text": MARKER_TEXT, "from": "bot"}, {"text": MARKER_TEXT, "message_id": None, "from_bot": False}),
        ]
        for reply, expected in cases:
            with self.subTest(reply=reply):
                context = telegram_bridge.reply_context_for({"text": "US$29.", "reply_to_message": reply})
                self.assertEqual(context, expected)
                self.assertEqual(set(context), {"text", "message_id", "from_bot"})
        for message in ({"text": "hi"}, {"text": "hi", "reply_to_message": {}},
                        {"text": "hi", "reply_to_message": None}, {"text": "hi", "reply_to_message": "x"}):
            with self.subTest(message=message):
                self.assertIsNone(telegram_bridge.reply_context_for(message))

    def test_mode_switch_prefix_still_forwards_reply_context(self):
        with patch.object(telegram_bridge, "set_chat_mode"):
            posted, _ = self.run_operator_message(
                {"chat": {"id": OPERATOR}, "text": "David, US$29.", "reply_to_message": bot_reply()})
        self.assertEqual(posted[0][1], {"text": "US$29.", "reply_context": {"text": MARKER_TEXT, "message_id": 77, "from_bot": True}})

    def test_orchestrator_mode_is_unchanged(self):
        message = {"chat": {"id": OPERATOR}, "text": "US$29.", "reply_to_message": bot_reply()}
        posted, agent = self.run_operator_message(message, mode=telegram_bridge.MODE_ORCHESTRATOR)
        self.assertEqual(posted, [])
        agent.assert_called_once_with(OPERATOR, "US$29.", source="telegram",
                                      delivery_id=f"telegram-update-{len(str(message))}", reply_tag="[Orchestrator]")

    def test_non_operator_reply_is_not_forwarded(self):
        with patch.object(telegram_bridge, "load_allowed", return_value={"operator_chat_ids": [], "pilots": {}}), \
             patch.object(telegram_bridge, "post_backend_json") as post, \
             patch.object(telegram_bridge, "send"):
            telegram_bridge.handle_message({"chat": {"id": 555}, "text": "US$29.", "reply_to_message": bot_reply()})
        post.assert_not_called()

    def test_forwarded_payload_is_accepted_by_ask_david_and_rendered(self):
        posted, _ = self.run_operator_message(
            {"chat": {"id": OPERATOR}, "text": "US$29.", "reply_to_message": bot_reply()})
        request = backend.AskDavidRequest(**posted[0][1])
        self.assertEqual((request.reply_context.text, request.reply_context.message_id, request.reply_context.from_bot),
                         (MARKER_TEXT, 77, True))
        import shared_brain_workflow
        handled = {"handled": True, "success": True, "workstream_id": "stream-a", "version": 3,
                   "message": "Recorded your answer on stream-a (v2 -> v3)."}
        with patch.dict("os.environ", {"TTROS_SHARED_BRAIN_WRITE": "1"}), \
             patch.object(shared_brain_workflow, "answer", return_value=handled) as answered:
            result = backend._try_ask_david_workstream_answer(request.text, request.reply_context)
        answered.assert_called_once_with(MARKER_TEXT, "US$29.")
        self.assertEqual(telegram_bridge.format_david_reply(result), "[David] Recorded your answer on stream-a (v2 -> v3).")


if __name__ == "__main__":
    unittest.main()
