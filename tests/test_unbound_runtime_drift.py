import tempfile
import unittest
from pathlib import Path

from tools.validate_unbound_runtime import (
    ASSEMBLER,
    BRAIN_MCP,
    PLUGIN_NAME,
    PLUGIN_SOURCE,
    SCOPED_PROFILES,
    audit_runtime,
)


class UnboundRuntimeDriftTest(unittest.TestCase):
    def test_owned_runtime_contract_passes_and_never_reads_default_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime = root / "runtime"
            profiles = root / "profiles"
            runtime.mkdir()
            turn = runtime / "turn_context.py"
            turn.write_text(
                '"TTROS model call blocked: mandatory assembled context is absent"\n'
                '"TTROS_ASSEMBLED_CONTEXT_V1" not in _piece\n'
                + "\n".join(f'"{profile}"' for profile in SCOPED_PROFILES),
                encoding="utf-8",
            )
            router = runtime / "hermes.py"
            router.write_text(
                'from context_assembler import assemble\nassembled.render()\nstartswith("PERMISSION MODE — SCOPED LOCAL TASK APPROVED")\n',
                encoding="utf-8",
            )
            claude = runtime / "aos-claude"
            claude.write_text(
                'CANONICAL_AOS_ROOT="/home/liam/agentic-os-live"\nhttp://127.0.0.1:8010/api/wsl/claude\n',
                encoding="utf-8",
            )
            for profile in SCOPED_PROFILES:
                path = profiles / profile / "config.yaml"
                path.parent.mkdir(parents=True)
                if profile == "david":
                    config = f"memory_enabled: true\nuser_profile_enabled: true\n{BRAIN_MCP}\n{PLUGIN_NAME}\n"
                else:
                    config = f"memory_enabled: false\nuser_profile_enabled: false\n{ASSEMBLER}\n{ASSEMBLER}\n{BRAIN_MCP}\n{PLUGIN_NAME}\n"
                path.write_text(config, encoding="utf-8")
                plugin_path = profiles / profile / "plugins" / PLUGIN_NAME
                plugin_path.parent.mkdir(parents=True)
                plugin_path.symlink_to(PLUGIN_SOURCE, target_is_directory=True)
            forbidden = profiles / "default" / "config.yaml"
            forbidden.parent.mkdir(parents=True)
            forbidden.write_text("THIS MUST NOT BE READ", encoding="utf-8")

            result = audit_runtime(
                runtime_paths={"turn_context": turn, "router": router, "aos_claude": claude},
                profile_root=profiles,
            )
            self.assertEqual(result["status"], "PASS")
            self.assertFalse(result["global_default_profile_inspected"])
            self.assertNotIn("default", result["profiles_checked"])

    def test_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            missing = Path(temp) / "missing"
            result = audit_runtime(
                runtime_paths={"turn_context": missing, "router": missing, "aos_claude": missing},
                profile_root=missing,
            )
            self.assertEqual(result["status"], "NEEDS ATTENTION")
            self.assertTrue(any(not row["passed"] for row in result["checks"]))


if __name__ == "__main__":
    unittest.main()
