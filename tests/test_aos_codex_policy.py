"""Focused regression contract for bounded supervised Codex launches.

Revisit: when an Agentic OS route gains a Codex subprocess constructor. · Last touched: 2026-07-18.
"""

from __future__ import annotations

import inspect
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tools import aos_codex_policy as policy


ROOT = Path(__file__).resolve().parents[1]


class AosCodexPolicyTest(unittest.TestCase):
    def test_authoritative_command_sets_the_compaction_limit(self):
        command = policy.build_exec_command()
        self.assertEqual(
            "model_auto_compact_token_limit=75000",
            command[command.index("--config") + 1],
        )
        parameters = inspect.signature(policy.build_exec_command).parameters
        self.assertNotIn("root", parameters)

    def test_runtime_validation_rejects_an_alternate_root(self):
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
            self.assertEqual(str(root), policy.validate_runtime(root, fixture)["cwd"])
            with self.assertRaisesRegex(policy.CodexPolicyError, "cwd must be"):
                policy.validate_runtime(root / "other", fixture)

    def test_active_python_constructors_use_the_shared_builder(self):
        for path, marker in (
            (ROOT / "dashboard/backend/main.py", "def _run_codex_local"),
            (ROOT / "tools/aos-queue.py", "def run_codex_work_item"),
        ):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIn(marker, text)
                self.assertIn("build_codex_exec_command(", text)
                self.assertIn("validate_codex_runtime", text)


if __name__ == "__main__":
    unittest.main()
