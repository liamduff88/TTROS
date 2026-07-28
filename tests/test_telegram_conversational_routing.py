"""Focused Olmec/Hermes operator-lean routing proofs.

Revisit: when the frozen literal table, operator context cap, or small Codex
prompt changes. · Last touched: 2026-07-28.
"""

import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import dashboard.backend.test_composio_hermes as backend_harness
import tiktoken
from tools import operator_lean_oneshot


backend = backend_harness.backend
ROOT = Path(__file__).parents[1]


class TelegramConversationalRoutingTests(unittest.TestCase):
    def setUp(self):
        with backend._OPERATOR_CONTEXT_LOCK:
            backend._OPERATOR_RECENT_TURNS.clear()

    def write_items(self, root: Path, items: list[dict]) -> None:
        queue = root / "queue"
        queue.mkdir(parents=True, exist_ok=True)
        (queue / "work_items.jsonl").write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in items),
            encoding="utf-8",
        )

    def item(
        self,
        item_id: str,
        status: str,
        *,
        title: str = "Route proof",
        owner: str = "codex",
        delivery_id: str = "",
    ) -> dict:
        return {
            "id": item_id,
            "title": title,
            "status": status,
            "priority": 5,
            "requested_by": "Liam",
            "owner_type": "agent",
            "owner": owner,
            "source": "telegram",
            "tags": ["olmec"],
            "context": title,
            "sources": [],
            "allowed_actions": ["local_read", "local_edit", "local_test"],
            "stop_conditions": ["external_send"],
            "definition_of_done": "Return a truthful result.",
            "parent_id": None,
            "step_index": None,
            "depends_on": [],
            "on_complete": "human_review",
            "workbench": owner if owner in {"codex", "claude"} else "lane",
            "review": "none",
            "claim": {"claimed_by": None, "claimed_at": None},
            "receipts": [],
            "dispatch": {
                "delivery_id": delivery_id,
                "reply_to": "fixture-chat",
                "idempotency_key": f"fixture:{item_id}",
            },
            "created_at": "2026-07-28T10:00:00Z",
            "updated_at": "2026-07-28T10:00:00Z",
        }

    @staticmethod
    def hermes_result(output: str) -> dict:
        return {
            "success": True,
            "output": output,
            "reply": output,
            "token_usage": {
                "available": True,
                "input_tokens": 100,
                "cache_read_tokens": 20,
                "fresh_input": 80,
                "output_tokens": 12,
                "api_calls": 1,
            },
            "token_usage_text": "Token usage: input 100, cache read 20, output 12, api calls 1",
            "elapsed_seconds": 0.25,
        }

    def test_A_open_tasks_is_frozen_zero_token_clean_fast_path(self):
        items = [
            self.item("AOS-2026-0300", "agent_todo", title="First task"),
            self.item("AOS-2026-0301", "human_review", title="Second task", owner="claude"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, items)
            before = (root / "queue" / "work_items.jsonl").read_bytes()
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message") as hermes, \
                 patch.object(backend, "_accept_async_queue_runner") as worker:
                result = backend.wsl_hermes(backend.TaskRun(task="What tasks are open?"))
                after = (root / "queue" / "work_items.jsonl").read_bytes()
        self.assertEqual(result["selected_route"], "local_queue_list")
        self.assertEqual(result["queue_delta"], 0)
        self.assertTrue(result["token_usage"]["no_agent_invocation"])
        self.assertEqual(result["model_process_count"], 0)
        self.assertEqual(result["worker_process_count"], 0)
        self.assertEqual(before, after)
        self.assertEqual(result["output"].count("AOS-2026-0300"), 1)
        self.assertIn("AOS-2026-0300 | First task | agent_todo | codex", result["output"])
        hermes.assert_not_called()
        worker.assert_not_called()

    def test_literal_variant_falls_through_to_operator_lean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message", return_value=self.hermes_result("No tasks.")) as hermes:
                result = backend.wsl_hermes(
                    backend.TaskRun(task="Which tasks are open?", reply_to="fixture-chat")
                )
        self.assertEqual(result["selected_route"], "hermes_operator_lean")
        hermes.assert_called_once()

    def test_B_and_C_use_operator_lean_no_queue_and_bounded_recent_turn(self):
        item = self.item("AOS-2026-0184", "human_review", title="Route proof")
        first = "Why did AOS-2026-0184 use so many tokens?"
        followup = "Okay, but do you think Hermes would be better?"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [item])
            before = (root / "queue" / "work_items.jsonl").read_bytes()
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message", side_effect=[
                     self.hermes_result("The full Codex wrapper dominated the input."),
                     self.hermes_result("For conversation, yes; for repository edits, keep Codex."),
                 ]) as hermes, \
                 patch.object(backend, "_accept_async_queue_runner") as worker:
                result_b = backend.wsl_hermes(
                    backend.TaskRun(task=first, delivery_id="proof-b", reply_to="fixture-chat")
                )
                result_c = backend.wsl_hermes(
                    backend.TaskRun(task=followup, delivery_id="proof-c", reply_to="fixture-chat")
                )
                after = (root / "queue" / "work_items.jsonl").read_bytes()
        self.assertEqual(before, after)
        self.assertEqual(result_b["profile_used"], "operator-lean")
        self.assertEqual(result_c["profile_used"], "operator-lean")
        self.assertEqual(result_b["queue_delta"], 0)
        self.assertEqual(result_c["queue_delta"], 0)
        self.assertEqual(result_b["worker_process_count"], 0)
        self.assertEqual(result_c["worker_process_count"], 0)
        self.assertLessEqual(result_c["context_bounds"]["recent_turn_bytes"], backend.OPERATOR_RECENT_TURNS_MAX_BYTES)
        second_prompt = hermes.call_args_list[1].args[0]
        self.assertIn(first, second_prompt)
        self.assertIn('"id":"AOS-2026-0184"', second_prompt)
        self.assertNotIn("receipt body", second_prompt)
        worker.assert_not_called()

    def test_D_operator_task_creation_dispatches_exactly_one_codex_item(self):
        instruction = "Fix the duplicate metadata in the deterministic open-task response."
        delivery_id = "proof-d"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [])

            def create_once(*args, **kwargs):
                self.write_items(
                    root,
                    [self.item(
                        "AOS-2026-0400",
                        "agent_todo",
                        title=instruction,
                        owner="codex",
                        delivery_id=delivery_id,
                    ) | {"size": "small"}],
                )
                return self.hermes_result("Created AOS-2026-0400 for Codex.")

            runner = {"available": True, "accepted": True, "state": "accepted", "mode": "one_shot"}
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message", side_effect=create_once), \
                 patch.object(backend, "_accept_async_queue_runner", return_value=runner) as worker:
                result = backend.wsl_hermes(
                    backend.TaskRun(task=instruction, delivery_id=delivery_id, reply_to="fixture-chat")
                )
                rows = backend._read_queue_items()
        self.assertEqual(len(rows), 1)
        self.assertEqual(result["queue_delta"], 1)
        self.assertEqual(result["work_item_id"], "AOS-2026-0400")
        self.assertEqual(result["owner"], "codex")
        self.assertFalse(result["hermes_orchestrator_invoked"])
        worker.assert_called_once()

    def test_E_explicit_codex_small_route_strips_wrapper_and_uses_small_prompt(self):
        instruction = "Return exactly ROUTE_PROOF_PASS and do nothing else."
        task = f"/work codex {instruction}"
        runner = {"available": True, "accepted": True, "state": "accepted", "mode": "one_shot"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [])
            templates = root / "queue" / "templates"
            templates.mkdir(parents=True, exist_ok=True)
            (templates / "codex_task_small.prompt.md").write_text(
                (ROOT / "queue" / "templates" / "codex_task_small.prompt.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            body = backend.TaskRun(
                task=task,
                source="telegram",
                delivery_id="proof-e",
                reply_to="fixture-chat",
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_accept_async_queue_runner", return_value=runner) as worker, \
                 patch.object(backend, "_run_hermes_message") as hermes:
                first = backend.wsl_hermes(body)
                replay = backend.wsl_hermes(body)
                rows = backend._read_queue_items()
                prompt = backend._queue_actual_run_prompt(rows[0], "codex")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], instruction)
        self.assertEqual(rows[0]["context"], instruction)
        self.assertEqual(rows[0]["size"], "small")
        self.assertEqual(prompt.count(instruction), 1)
        self.assertNotIn("/work codex", prompt)
        self.assertNotIn("Required artifact", prompt)
        self.assertNotIn("Validation", prompt)
        self.assertEqual(first["work_item_id"], replay["work_item_id"])
        self.assertTrue(replay["duplicate"])
        worker.assert_called_once()
        hermes.assert_not_called()

    def test_F_wording_discussion_stays_conversation_only(self):
        message = "I don't like the wording. Can we figure out something better first?"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message", return_value=self.hermes_result("Yes. What tone do you want?")), \
                 patch.object(backend, "_accept_async_queue_runner") as worker:
                result = backend.wsl_hermes(
                    backend.TaskRun(task=message, delivery_id="proof-f", reply_to="fixture-chat")
                )
                rows = backend._read_queue_items()
        self.assertEqual(rows, [])
        self.assertFalse(result["created"])
        self.assertTrue(result["direct_reply"])
        self.assertEqual(result["queue_delta"], 0)
        self.assertEqual(result["worker_process_count"], 0)
        worker.assert_not_called()

    def test_operator_oneshot_waits_for_complete_six_tool_snapshot(self):
        events = []

        def discover():
            events.append("discovered")
            return list(operator_lean_oneshot.EXPECTED_TOOLS)

        def construct_agent(prompt, **kwargs):
            self.assertEqual(events, ["discovered"])
            events.append("constructed")
            self.assertEqual(kwargs["toolsets"], ["operator"])
            return 0

        result = operator_lean_oneshot.run_operator_oneshot(
            "hello",
            discover=discover,
            runner=construct_agent,
        )
        self.assertEqual(result, 0)
        self.assertEqual(events, ["discovered", "constructed"])

    def test_operator_oneshot_fails_closed_when_mcp_is_unavailable(self):
        runner = unittest.mock.Mock()
        stderr = StringIO()
        with redirect_stderr(stderr):
            result = operator_lean_oneshot.run_operator_oneshot(
                "queue this",
                discover=lambda: [],
                runner=runner,
            )
        self.assertEqual(result, operator_lean_oneshot.TOOL_UNAVAILABLE_EXIT)
        self.assertIn("TOOL_UNAVAILABLE", stderr.getvalue())
        self.assertIn("No model was called and no task was queued", stderr.getvalue())
        runner.assert_not_called()

    def test_operator_closeout_rejects_unverified_queue_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(
                     backend,
                     "_run_hermes_message",
                     return_value=self.hermes_result("Created AOS-2026-0999: Imaginary task"),
                 ), \
                 patch.object(backend, "_accept_async_queue_runner") as worker:
                result = backend.wsl_hermes(
                    backend.TaskRun(task="Please queue this.", delivery_id="proof-closed")
                )
        self.assertFalse(result["success"])
        self.assertFalse(result["created"])
        self.assertEqual(result["queue_delta"], 0)
        self.assertIn("No task was queued", result["output"])
        worker.assert_not_called()

    def test_live_loaded_operator_preamble_has_exactly_six_tools_under_budget(self):
        profile_home = Path.home() / ".hermes" / "profiles" / "operator-lean"
        hermes_python = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python3"
        env = dict(os.environ, HERMES_HOME=str(profile_home))
        result = subprocess.run(
            [
                str(hermes_python),
                str(ROOT / "tools" / "operator_lean_oneshot.py"),
                "--inspect-preamble",
            ],
            cwd=profile_home,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
            check=True,
        )
        preamble = json.loads(result.stdout)
        tool_names = {
            row["function"]["name"]
            for row in preamble["tools"]
        }
        self.assertEqual(tool_names, operator_lean_oneshot.EXPECTED_TOOLS)
        self.assertEqual(len(preamble["tools"]), 6)
        encoding = tiktoken.get_encoding("o200k_base")
        system_tokens = len(encoding.encode(preamble["system_prompt"]))
        tool_tokens = len(
            encoding.encode(
                json.dumps(
                    preamble["tools"],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        )
        self.assertLess(system_tokens + tool_tokens, 1_200)

    def test_profile_launcher_and_tool_server_enforce_lean_surface(self):
        launcher = (ROOT / "tools" / "aos-hermes-operator-lean.sh").read_text(encoding="utf-8")
        profile = (ROOT / "queue" / "profiles" / "operator-lean.md").read_text(encoding="utf-8")
        server = (ROOT / "tools" / "operator_lean_mcp.py").read_text(encoding="utf-8")
        self.assertEqual(len(operator_lean_oneshot.EXPECTED_TOOLS), 6)
        self.assertIn('profile="operator-lean"', launcher)
        self.assertIn('cd "$profile_home"', launcher)
        self.assertIn("operator_lean_oneshot.py", launcher)
        self.assertNotIn("aos-orchestrator", launcher)
        self.assertIn("Never delegate, orchestrate", profile)
        self.assertEqual(server.count("@mcp.tool()"), 6)
        self.assertIn("_task_created", server)


if __name__ == "__main__":
    unittest.main()
