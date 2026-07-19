"""Regression contract for mandatory Agentic OS Codex full-access execution.

Revisit: when an Agentic OS route gains a new Codex subprocess constructor. · Last touched: 2026-07-17.
"""

from __future__ import annotations

import inspect
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tools import aos_codex_policy as policy


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = Path("/home/liam/.local/bin/aos-codex")
HERMES_LAUNCHER = Path("/home/liam/.local/bin/aos-hermes")


class AosCodexPolicyTest(unittest.TestCase):
    def test_authoritative_command_is_explicit_and_not_caller_downgradable(self):
        command = policy.build_exec_command()
        self.assertEqual("/home/liam/.local/npm/bin/codex", command[0])
        self.assertEqual("danger-full-access", command[command.index("--sandbox") + 1])
        self.assertEqual("never", command[command.index("--ask-for-approval") + 1])
        self.assertEqual("/home/liam/agentic-os-live", command[command.index("-C") + 1])
        self.assertIn("exec", command)
        self.assertIn("--ephemeral", command)
        self.assertNotIn("resume", command)
        self.assertNotIn("--last", command)
        self.assertNotIn("workspace-write", command)
        self.assertNotIn("/mnt/c", " ".join(command))
        parameters = inspect.signature(policy.build_exec_command).parameters
        self.assertNotIn("sandbox", parameters)
        self.assertNotIn("approval_policy", parameters)
        self.assertNotIn("root", parameters)
        prompt = policy.prepare_fresh_prompt("bounded task sentinel")
        self.assertTrue(prompt.startswith("PERMISSION MODE — SCOPED LOCAL TASK APPROVED"))
        self.assertIn("new, independently scoped ephemeral Codex session", prompt)
        self.assertIn("bounded task sentinel", prompt)

    def test_clean_session_identity_is_required_and_never_synthesized(self):
        self.assertEqual(
            "fresh-session-id",
            policy.require_clean_session_id('{"type":"thread.started","thread_id":"fresh-session-id"}\n'),
        )
        with self.assertRaisesRegex(policy.CodexPolicyError, "clean-session creation failed"):
            policy.require_clean_session_id('{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\n')
        with self.assertRaisesRegex(policy.CodexPolicyError, "ambiguous"):
            policy.require_clean_session_id(
                '{"type":"thread.started","thread_id":"one"}\n'
                '{"type":"thread.started","thread_id":"two"}\n'
            )
        with self.assertRaisesRegex(policy.CodexPolicyError, "ambiguous"):
            policy.require_clean_session_id(
                '{"type":"thread.started","thread_id":"same"}\n'
                '{"type":"thread.started","thread_id":"same"}\n'
            )

    def test_runtime_validation_rejects_alternate_root_user_and_missing_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "codex"
            binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            binary.chmod(0o755)
            fixture = replace(
                policy.CODEX_TARGET,
                root=root,
                executable=binary,
                codex_home=root / ".codex",
                linux_user=policy.effective_linux_user(),
            )
            metadata = policy.validate_runtime(root, fixture)
            self.assertEqual("danger-full-access", metadata["sandbox"])
            self.assertEqual("never", metadata["approval_policy"])
            with self.assertRaisesRegex(policy.CodexPolicyError, "cwd must be"):
                policy.validate_runtime(root / "downgraded-route", fixture)
            with self.assertRaisesRegex(policy.CodexPolicyError, "Linux user must be"):
                policy.validate_runtime(root, replace(fixture, linux_user="not-liam"))
            with self.assertRaisesRegex(policy.CodexPolicyError, "missing or not executable"):
                policy.validate_runtime(root, replace(fixture, executable=root / "missing-codex"))

    def test_every_active_python_constructor_uses_the_shared_builder(self):
        active_constructors = {
            ROOT / "dashboard/backend/main.py": "def _run_codex_local",
            ROOT / "tools/aos-queue.py": "def run_codex_work_item",
        }
        for path, function_marker in active_constructors.items():
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIn(function_marker, text)
                self.assertIn("build_codex_exec_command(CODEX_TARGET)", text)
                self.assertIn("validate_codex_runtime", text)
                self.assertNotIn("workspace-write", text)

    def test_all_active_entry_routes_converge_on_the_two_guarded_constructors(self):
        backend = (ROOT / "dashboard/backend/main.py").read_text(encoding="utf-8")
        queue = (ROOT / "tools/aos-queue.py").read_text(encoding="utf-8")
        workflow = (ROOT / "workflows/prompt_templates/codex_workflow_runner.md").read_text(encoding="utf-8")
        frontend = (ROOT / "dashboard/frontend/src/launcherPrompts.js").read_text(encoding="utf-8")

        self.assertIn("result = _run_codex_local(prompt, item)", backend)  # queue/dashboard/workflow owner
        self.assertIn("_run_codex_local(body.task)", backend)  # direct backend API
        self.assertIn("continued = run_codex_work_item(", queue)
        self.assertIn("_handoff_depth=_handoff_depth + 1", queue)
        for text in (workflow, frontend):
            self.assertIn("/home/liam/.local/bin/aos-codex", text)
            self.assertNotIn("/home/liam/.local/npm/bin/codex", text)
            self.assertNotIn("workspace-write", text)
            self.assertNotIn("/mnt/c", text)
        self.assertNotIn("resume", frontend.lower())
        self.assertNotIn("--last", frontend.lower())

    def test_installed_launcher_is_a_no_fallback_backend_forwarder(self):
        text = LAUNCHER.read_text(encoding="utf-8")
        self.assertTrue(os.access(LAUNCHER, os.X_OK))
        self.assertIn('WORKSPACE="/home/liam/agentic-os-live"', text)
        self.assertIn("http://127.0.0.1:8010/api/wsl/codex", text)
        self.assertIn("no direct Codex fallback", text)
        self.assertIn('if [[ -z "$TASK" && ! -t 0 ]]', text)
        self.assertNotIn("codex exec", text)
        self.assertNotIn("workspace-write", text)
        self.assertNotIn("/mnt/c", text)

        hermes = HERMES_LAUNCHER.read_text(encoding="utf-8")
        self.assertIn('if [[ "${1:-}" == "codex" ]]', hermes)
        self.assertIn('exec "/home/liam/.local/bin/aos-codex" "$@"', hermes)

    def test_active_production_surface_has_no_workspace_write_or_obsolete_root(self):
        active_files = (
            ROOT / "tools/aos_codex_policy.py",
            ROOT / "dashboard/backend/main.py",
            ROOT / "tools/aos-queue.py",
            ROOT / "tools/aos-orchestration-runner.py",
            ROOT / "tools/aos-linux-runtime.sh",
            ROOT / "dashboard/frontend/src/launcherPrompts.js",
            ROOT / "workflows/prompt_templates/codex_workflow_runner.md",
            LAUNCHER,
        )
        for path in active_files:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("workspace-write", text)
                if path.name != "aos-linux-runtime.sh":
                    self.assertNotIn("/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live", text)


if __name__ == "__main__":
    unittest.main()
