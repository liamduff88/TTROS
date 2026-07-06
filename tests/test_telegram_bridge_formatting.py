import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BRIDGE = Path(__file__).parents[1] / "connectors" / "telegram_bridge" / "telegram_bridge.py"


def load_bridge():
    module_name = "telegram_bridge_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, BRIDGE)
    module = importlib.util.module_from_spec(spec)
    with patch.object(Path, "exists", return_value=True), \
         patch.object(Path, "read_text", return_value="TELEGRAM_BOT_TOKEN=fake-token\n"), \
         patch.object(Path, "mkdir"):
        spec.loader.exec_module(module)
    return module


class TelegramBridgeFormattingTests(unittest.TestCase):
    def test_queue_create_backend_output_is_preserved(self):
        bridge = load_bridge()
        output = "\n".join([
            "PASS",
            "",
            "Work item ID:",
            "- AOS-2026-0014",
            "",
            "Owner:",
            "- revenue",
            "",
            "Status:",
            "- agent_todo",
            "",
            "Next action:",
            "- Review or claim the local queue item.",
            "",
            "Token usage:",
            "- no agent invocation",
        ])
        result = {
            "success": True,
            "requested_target": "queue",
            "selected_route": "local_queue",
            "output": output,
        }

        summary = bridge.summarize_agent_result(result)
        self.assertEqual(summary, output)

        with patch.object(bridge, "api") as api:
            bridge.send(123, summary, preserve_format=bridge.is_queue_backend_result(result))

        api.assert_called_once()
        self.assertEqual(api.call_args.args[1]["text"], output)

    def test_non_queue_backend_output_still_uses_compact_closeout(self):
        bridge = load_bridge()
        result = {
            "success": True,
            "requested_target": "hermes",
            "selected_route": "hermes_coordinator",
            "output": "PASS\nVerbose backend output",
        }

        summary = bridge.summarize_agent_result(result)

        self.assertNotEqual(summary, result["output"])
        self.assertIn("Files touched:", summary)
        self.assertIn("Token usage:", summary)


if __name__ == "__main__":
    unittest.main()
