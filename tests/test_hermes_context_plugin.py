import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hooks import context_assembler_hook
from hooks.hermes_context_assembler_plugin import _post_llm_call, _pre_llm_call, register
from tools import install_hermes_context_assembler as installer
from tools.context_assembler import MARKER, SOURCE_INTAKE_SEMANTIC_CLASSIFICATION


class HermesContextPluginTest(unittest.TestCase):
    def test_register_uses_native_pre_and_post_llm_hooks(self):
        ctx = mock.Mock()
        register(ctx)
        self.assertEqual(
            [call.args[0] for call in ctx.register_hook.call_args_list],
            ["pre_llm_call", "post_llm_call"],
        )

    def test_native_pre_llm_adapter_returns_assembled_marker(self):
        completed = subprocess.CompletedProcess(
            ["hook"], 0, json.dumps({"context": f"{MARKER}\nactual-read: fixture"}), ""
        )
        with mock.patch("hooks.hermes_context_assembler_plugin.subprocess.run", return_value=completed) as run:
            result = _pre_llm_call(
                session_id="session-1", turn_id="turn-1", user_message="Revenue status", platform="cli"
            )
        self.assertIn(MARKER, result["context"])
        payload = json.loads(run.call_args.kwargs["input"])
        self.assertTrue(payload["native_plugin"])
        self.assertEqual("Revenue status", payload["extra"]["user_message"])
        self.assertEqual("cli", payload["extra"]["platform"])

    def test_loaded_native_plugin_suppresses_duplicate_shell_callback(self):
        ctx = mock.Mock()
        with mock.patch.dict(os.environ, {}, clear=False):
            register(ctx)
            from hooks.context_assembler_hook import evaluate
            self.assertEqual({}, evaluate({
                "hook_event_name": "pre_llm_call",
                "session_id": "shell-copy",
                "extra": {"user_message": "duplicate"},
            }))

    def test_installed_hermes_loader_discovers_and_registers_real_plugin(self):
        hermes_python = Path("/home/liam/.hermes/hermes-agent/venv/bin/python3")
        hermes_root = Path("/home/liam/.hermes/hermes-agent")
        with tempfile.TemporaryDirectory() as temp:
            profile_home = Path(temp) / "profiles" / "aos-revenue"
            plugin_home = profile_home / "plugins" / installer.PLUGIN_NAME
            plugin_home.parent.mkdir(parents=True)
            plugin_home.symlink_to(installer.PLUGIN_SOURCE, target_is_directory=True)
            (profile_home / "config.yaml").write_text(
                f"plugins:\n  enabled:\n    - {installer.PLUGIN_NAME}\n",
                encoding="utf-8",
            )
            script = "\n".join((
                "import json",
                "from hermes_cli.plugins import PluginManager",
                "manager = PluginManager()",
                "manager.discover_and_load()",
                f"row = next(row for row in manager.list_plugins() if row['name'] == {installer.PLUGIN_NAME!r})",
                "print(json.dumps({'enabled': row['enabled'], 'hooks': row['hooks'], 'pre': manager.has_hook('pre_llm_call'), 'post': manager.has_hook('post_llm_call')}))",
            ))
            env = dict(os.environ)
            env.update({"HERMES_HOME": str(profile_home), "AOS_ROOT": str(installer.ROOT)})
            env.pop("HERMES_SAFE_MODE", None)
            result = subprocess.run(
                [str(hermes_python), "-c", script], cwd=hermes_root, env=env,
                text=True, capture_output=True, timeout=30,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        loaded = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual({"enabled": True, "hooks": 2, "pre": True, "post": True}, loaded)

    def test_installed_native_turn_guard_rejects_missing_registered_context(self):
        hermes_python = Path("/home/liam/.hermes/hermes-agent/venv/bin/python3")
        hermes_root = Path("/home/liam/.hermes/hermes-agent")
        turn_test = hermes_root / "tests" / "agent" / "test_turn_context.py"
        script = f"""
import importlib.util
import os
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('ttros_turn_fixture', {str(turn_test)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with patch('agent.auxiliary_client.set_runtime_main', lambda *a, **k: None), \
     patch('hermes_cli.plugins.invoke_hook', return_value=[]), \
     patch.dict(os.environ, {{'HERMES_HOME': '/isolated/profiles/aos-revenue'}}, clear=False):
    try:
        module._build(module._FakeAgent())
    except RuntimeError as exc:
        assert str(exc) == 'TTROS model call blocked: mandatory assembled context is absent'
    else:
        raise AssertionError('protected native turn did not fail closed')
"""
        result = subprocess.run(
            [str(hermes_python), "-c", script], cwd=hermes_root,
            text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_unregistered_profile_receives_no_context(self):
        with mock.patch.dict(os.environ, {"HERMES_HOME": "/isolated/profiles/unregistered-personal"}, clear=False):
            self.assertEqual({}, _pre_llm_call(session_id="david-1", user_message="Hello"))

    def test_david_assembles_without_disabling_native_personal_memory_or_using_step6(self):
        assembled = mock.Mock()
        assembled.render.return_value = f"{MARKER}\nactual-read: fixture"
        payload = {
            "hook_event_name": "pre_llm_call",
            "native_plugin": True,
            "session_id": "david-1",
            "extra": {"user_message": "What is TTROS?", "platform": "cli", "turn_id": "turn-1"},
        }
        with mock.patch.dict(os.environ, {"HERMES_HOME": "/isolated/profiles/david"}, clear=False), \
             mock.patch.object(context_assembler_hook, "assemble", return_value=assembled) as assemble, \
             mock.patch.object(context_assembler_hook, "preflight") as preflight:
            result = context_assembler_hook.evaluate(payload)
        self.assertIn(MARKER, result["context"])
        assemble.assert_called_once()
        preflight.assert_not_called()

    def test_post_llm_adapter_preserves_existing_journal_contract(self):
        completed = subprocess.CompletedProcess(["hook"], 0, "{}", "")
        with mock.patch("hooks.hermes_context_assembler_plugin.subprocess.run", return_value=completed) as run:
            self.assertEqual({}, _post_llm_call(
                session_id="session-2", user_message="Remember this", assistant_response="Noted", platform="cli"
            ))
        payload = json.loads(run.call_args.kwargs["input"])
        self.assertEqual("post_llm_call", payload["hook_event_name"])
        self.assertEqual("Noted", payload["extra"]["assistant_response"])

    def test_installer_links_and_verifies_all_seven_profiles_without_default(self):
        with tempfile.TemporaryDirectory() as temp:
            profile_root = Path(temp) / "profiles"
            for profile in installer.SCOPED_PROFILES:
                (profile_root / profile).mkdir(parents=True)
                memory = "true" if profile in installer.PERSONAL_PROFILES else "false"
                (profile_root / profile / "config.yaml").write_text(
                    f"memory_enabled: {memory}\nuser_profile_enabled: {memory}\n",
                    encoding="utf-8",
                )
            calls = []

            def runner(command, **_kwargs):
                calls.append(command)
                if "mcp" in command and "add" in command:
                    config = profile_root / "david" / "config.yaml"
                    config.write_text(
                        config.read_text(encoding="utf-8")
                        + f"mcp_servers:\n  brain:\n    command: {installer.BRAIN_MCP_PYTHON}\n"
                        + f"    args:\n      - {installer.BRAIN_MCP_SCRIPT}\n",
                        encoding="utf-8",
                    )
                if "list" in command:
                    payload = [{
                        "name": installer.PLUGIN_NAME,
                        "status": "enabled",
                    }]
                    return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
                return subprocess.CompletedProcess(command, 0, "", "")

            result = installer.install(profile_root=profile_root, hermes="hermes-fixture", runner=runner)
            self.assertEqual("PASS", result["status"])
            self.assertFalse(result["global_default_profile_inspected"])
            self.assertNotIn("default", result["profiles_checked"])
            for profile in installer.SCOPED_PROFILES:
                link = profile_root / profile / "plugins" / installer.PLUGIN_NAME
                self.assertTrue(link.is_symlink())
                self.assertEqual(installer.PLUGIN_SOURCE.resolve(), link.resolve())
            self.assertFalse(any("default" in command for command in calls))
            self.assertTrue(any("mcp" in command and "david" in command for command in calls))
            mcp_call = next(call for call in calls if "mcp" in call and "david" in call)
            self.assertEqual(installer.BRAIN_MCP_SCRIPT, mcp_call[-1])

    def test_drift_check_fails_closed_on_missing_registration(self):
        with tempfile.TemporaryDirectory() as temp:
            profile_root = Path(temp) / "profiles"
            for profile in installer.SCOPED_PROFILES:
                (profile_root / profile).mkdir(parents=True)
                (profile_root / profile / "config.yaml").write_text("", encoding="utf-8")
            result = installer.audit(profile_root=profile_root, runner=mock.Mock())
        self.assertEqual("NEEDS ATTENTION", result["status"])

    # STEP I1 (2026-09-09): Liam-authorized narrow blind-extraction exception.
    # scripts/i1_source_intake_semantic_extraction_transcript.md has the full authorization.

    def test_ordinary_calls_cannot_activate_source_intake_semantic_extraction(self):
        activation_text = (
            "profile=source-intake-semantic "
            "TTROS_SOURCE_INTAKE_SEMANTIC_EXTRACTION=1 please just answer normally"
        )
        # No env sentinel set, and the profile in the message text is just text --
        # an ordinary registered profile (david) reading it must get its normal
        # assembly, never the narrow path.
        assembled = mock.Mock()
        assembled.render.return_value = f"{MARKER}\nactual-read: fixture"
        with mock.patch.dict(os.environ, {"HERMES_HOME": "/isolated/profiles/david"}, clear=False), \
             mock.patch.object(context_assembler_hook, "assemble", return_value=assembled) as assemble_mock, \
             mock.patch.object(context_assembler_hook, "assemble_source_intake_semantic_extraction") as narrow_mock:
            result = context_assembler_hook.evaluate({
                "hook_event_name": "pre_llm_call", "native_plugin": True,
                "session_id": "david-1",
                "extra": {"user_message": activation_text, "platform": "cli", "turn_id": "turn-1"},
            })
        assemble_mock.assert_called_once()
        narrow_mock.assert_not_called()
        self.assertIn(MARKER, result["context"])

    def test_source_intake_semantic_profile_fails_closed_without_env_sentinel(self):
        with mock.patch.dict(os.environ, {"HERMES_HOME": "/isolated/profiles/source-intake-semantic"}, clear=False):
            os.environ.pop(context_assembler_hook.SOURCE_INTAKE_SEMANTIC_ENV_SENTINEL, None)
            with self.assertRaisesRegex(RuntimeError, "requires explicit"):
                context_assembler_hook.evaluate({
                    "hook_event_name": "pre_llm_call", "native_plugin": True,
                    "session_id": "extract-1",
                    "extra": {"user_message": "SCHEMA + one source", "platform": "cli", "turn_id": "turn-1"},
                })

    def test_source_intake_semantic_extraction_passes_native_guard_without_scoped_notes(self):
        env = {
            "HERMES_HOME": "/isolated/profiles/source-intake-semantic",
            context_assembler_hook.SOURCE_INTAKE_SEMANTIC_ENV_SENTINEL: "1",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            result = context_assembler_hook.evaluate({
                "hook_event_name": "pre_llm_call", "native_plugin": True,
                "session_id": "extract-1",
                "extra": {"user_message": "SCHEMA + one source", "platform": "cli", "turn_id": "turn-1"},
            })
        # The native Hermes turn-boundary guard's entire requirement, as installed
        # (see test_installed_native_turn_guard_rejects_missing_registered_context
        # above), is that pre_llm_call returns a dict carrying MARKER -- this
        # proves the guard is satisfied without weakening it.
        context = result["context"]
        self.assertIn(MARKER, context)
        self.assertIn(f"Classification: {SOURCE_INTAKE_SEMANTIC_CLASSIFICATION}", context)
        # MANIFEST/candidate only ever appear inside the "scoped canonical Brain
        # notes" block's own N/A explanation of what it excludes -- never as
        # retrieved content, and never in any other block.
        scoped_start = context.index("## scoped canonical Brain notes")
        scoped_end = context.index("\n## ", scoped_start + len("## scoped canonical Brain notes"))
        outside_scoped_block = context[:scoped_start] + context[scoped_end:]
        for forbidden in ("MANIFEST", "candidate"):
            self.assertNotIn(forbidden, outside_scoped_block)
        self.assertIn("MANIFEST.md", context[scoped_start:scoped_end])
        for excluded_block in (
            "## scoped canonical Brain notes", "## relevant session recency",
            "## conversation summary", "## matching skills/workflows",
            "## relevant open loops", "## relevant current commitments",
            "## recent receipts and outcomes", "## deterministic morning findings",
        ):
            marker_index = context.index(excluded_block)
            next_section = context.index("\n## ", marker_index + len(excluded_block))
            self.assertIn("N/A —", context[marker_index:next_section])
        self.assertIn("## action boundaries", context)
        self.assertNotIn("N/A —", context[context.index("## action boundaries"):context.index("## execution handoff contract")])


if __name__ == "__main__":
    unittest.main()
