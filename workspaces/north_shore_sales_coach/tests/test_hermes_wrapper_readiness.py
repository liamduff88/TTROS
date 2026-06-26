import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "hermes_wrapper"


class HermesWrapperReadinessTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(
            (WRAPPER / "hermes_workspace_manifest.json").read_text(encoding="utf-8")
        )
        self.config = json.loads(
            (WRAPPER / "config.example.json").read_text(encoding="utf-8")
        )

    def test_required_contract_files_exist(self):
        expected = {
            "README.md",
            "hermes_workspace_manifest.json",
            "entrypoint_contract.md",
            "config.example.json",
            "install_plan.md",
        }
        self.assertTrue(expected.issubset({path.name for path in WRAPPER.iterdir()}))

    def test_workspace_is_isolated_from_host_and_bridge(self):
        workspace = self.manifest["workspace"]
        self.assertEqual(workspace["isolation"], "dedicated_workspace")
        self.assertFalse(workspace["inherits_host_sessions"])
        self.assertFalse(workspace["inherits_host_tools"])
        self.assertFalse(workspace["agentic_os_bridge"])
        self.assertEqual(self.manifest["transport"]["telegram"], "direct_package_owned")
        self.assertFalse(self.manifest["transport"]["live_polling_enabled"])

    def test_entrypoints_are_narrow_local_and_zero_token(self):
        self.assertEqual(
            set(self.manifest["entrypoints"]),
            {
                "route_north_shore_message",
                "route_north_shore_command",
                "generate_north_shore_report",
                "validate_north_shore_config",
            },
        )
        for spec in self.manifest["entrypoints"].values():
            self.assertTrue(spec["token_free"])
            self.assertFalse(spec["network"])

    def test_dangerous_and_external_capabilities_are_explicitly_blocked(self):
        required = {
            "work_command", "general_hermes_commands", "codex", "claude",
            "arbitrary_tools", "web", "search", "browser", "os_commands",
            "google_sheets_writes", "composio_execution",
            "live_telegram_polling", "agentic_os_backend_routes",
        }
        self.assertTrue(required.issubset(set(self.manifest["blocked_capabilities"])))

    def test_sheets_choice_is_provider_neutral_and_inactive(self):
        sheets = self.manifest["sheets"]
        self.assertEqual(
            set(sheets["allowed_provider_choices"]),
            {"none", "hermes_native", "google_sheets_api", "apps_script_webapp", "composio"},
        )
        self.assertEqual(sheets["default_provider"], "none")
        self.assertFalse(sheets["reads_enabled"])
        self.assertFalse(sheets["writes_enabled"])
        self.assertFalse(sheets["execution_enabled"])
        self.assertFalse(sheets["composio_required"])

    def test_example_config_contains_placeholders_not_secrets(self):
        serialized = json.dumps(self.config)
        env_names = re.findall(r'"[A-Z][A-Z0-9_]+"', serialized)
        self.assertTrue(env_names)
        self.assertNotRegex(serialized, r"(?i)(sk-[a-z0-9]{16,}|AIza[a-z0-9_-]{20,})")
        self.assertFalse(self.config["telegram"]["enabled"])
        self.assertFalse(self.config["telegram"]["live_polling_enabled"])
        self.assertFalse(self.config["llm"]["enabled"])
        self.assertFalse(self.config["sheets"]["reads_enabled"])
        self.assertFalse(self.config["sheets"]["writes_enabled"])
        self.assertFalse(self.config["sheets"]["execution_enabled"])

    def test_no_runtime_state_or_absolute_old_runtime_paths(self):
        forbidden_names = {".hermes", "sessions", "skills", "zpc", "mcp", "vault"}
        self.assertFalse(forbidden_names.intersection({p.name.lower() for p in WRAPPER.rglob("*")}))
        for path in WRAPPER.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                self.assertNotRegex(text, r"(?i)(/home/|/root/|[a-z]:\\\\|old[_ -]?runtime)")


if __name__ == "__main__":
    unittest.main()
