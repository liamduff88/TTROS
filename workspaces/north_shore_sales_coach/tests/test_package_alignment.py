import json
import unittest
from pathlib import Path

from src.local_store import RUNTIME_DATA_FILES


ROOT = Path(__file__).resolve().parents[1]


class PackageAlignmentTests(unittest.TestCase):
    def test_all_config_and_schema_json_loads(self):
        paths = [ROOT / "bot_manifest.json", *sorted((ROOT / "config").glob("*.json")), *sorted((ROOT / "schemas").glob("*.json"))]
        for path in paths:
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))

    def test_runtime_data_paths_are_declared(self):
        self.assertEqual(
            {str(path) for path in RUNTIME_DATA_FILES.values()},
            {
                "data/sales_logs.jsonl",
                "data/events.jsonl",
                "data/report_archive.jsonl",
                "data/local_state.json",
            },
        )

    def test_no_agentic_os_telegram_bridge_imports(self):
        forbidden = ("connectors", "telegram_bridge")
        for path in [*sorted((ROOT / "src").glob("*.py")), *sorted((ROOT / "tests").glob("*.py"))]:
            content = path.read_text(encoding="utf-8")
            for name in forbidden:
                self.assertNotIn(f"import {name}", content)
                self.assertNotIn(f"from {name}", content)

    def test_core_has_no_provider_sdk_or_general_agent_imports(self):
        core_paths = [
            ROOT / "src" / "sheets_adapter.py",
            ROOT / "src" / "sheets_sync_adapter.py",
            ROOT / "src" / "message_router.py",
            ROOT / "src" / "natural_language_router.py",
        ]
        forbidden = (
            "import composio", "from composio", "import google", "from google",
            "import openai", "from openai", "import anthropic", "from anthropic",
            "telegram_bridge", "agentic_os",
        )
        for path in core_paths:
            content = path.read_text(encoding="utf-8").lower()
            for value in forbidden:
                with self.subTest(path=path.name, value=value):
                    self.assertNotIn(value, content)


if __name__ == "__main__":
    unittest.main()
