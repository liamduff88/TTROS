"""Focused Olmec/Hermes One Brain conversational routing proofs.

Revisit: when the frozen literal table, sticky context, escalation wire,
or small Codex prompt changes. · Last touched: 2026-08-04.
"""

import hashlib
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
from connectors.telegram_bridge import telegram_bridge
from tools import operator_lean_oneshot
from tools.step6_cost_control import Scope, fuse_status, preflight, record_unavailable_invocation


backend = backend_harness.backend
ROOT = Path(__file__).parents[1]


class TelegramConversationalRoutingTests(unittest.TestCase):
    FOUNDER_INTERVIEW_MESSAGE = """I want you to interview me properly so you can understand me, my life, my constraints, Time to Revenue, what I am trying to build, and how you should support me as my executive intelligence.

Ask one meaningful question at a time. Follow up naturally instead of reading a fixed questionnaire. Periodically summarize what you think you have learned and let me correct it.

Separate verified facts, my intentions, your interpretations, and uncertainties.

Remember durable information in the TTROS Business Brain by meaning, update the appropriate canonical notes, preserve provenance, and keep unresolved questions in open_loops. Do not create a queue task, invoke a worker, or take any external action.

Start by asking me about the life I am trying to create and the role I want Time to Revenue to play in it."""
    LIAM_RETRY_MESSAGE = """Continue from my last unanswered message.

Save this as my current priority: I need to choose a practical niche or target market for cold prospecting, develop a strong prospecting approach, and build visible specialization. I do not yet know which niche to choose.

Do not create a queue item or start execution. Briefly summarize what this means strategically, then ask me the single most useful question for narrowing the niche options.

Keep the response under 150 words."""

    def setUp(self):
        pass

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

    def test_B_and_C_use_operator_lean_no_queue_and_mandatory_context(self):
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
        self.assertIsNone(result_c["context_bounds"]["hard_conversation_byte_ceiling"])
        second_context = hermes.call_args_list[1].args[0]
        self.assertEqual(second_context.surface, "hermes:cli")
        self.assertIn("TTROS sticky session key:", second_context.request)
        self.assertTrue(second_context.total_bytes > 0)
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

    def test_founder_interview_with_pending_items_crosses_bridge_once_and_stays_conversation(self):
        reply = "What would a deeply satisfying ordinary week look like in the life you are trying to create?"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = [
                self.item("AOS-2026-0901", "human_review", title="Review one"),
                self.item("AOS-2026-0902", "needs_input", title="Input two"),
            ]
            for item in items:
                item["dispatch"]["reply_to"] = "123"
            self.write_items(root, items)
            queue_path = root / "queue" / "work_items.jsonl"
            before = queue_path.read_bytes()
            results = []

            def dispatch(chat_id, task, source="telegram", delivery_id="", reply_tag=""):
                self.assertEqual(task, self.FOUNDER_INTERVIEW_MESSAGE)
                result = backend.wsl_hermes(backend.TaskRun(
                    task=task,
                    source=source,
                    delivery_id=delivery_id,
                    reply_to=str(chat_id),
                ))
                results.append(result)
                telegram_bridge.deliver_agent_result(chat_id, result)
                return True

            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(telegram_bridge, "UPDATE_STATE_FILE", root / "logs" / "runtime" / "updates.json"), \
                 patch.object(telegram_bridge, "load_allowed", return_value={"operator_chat_ids": [123], "pilots": {}}), \
                 patch.object(telegram_bridge, "dispatch_agent_request", side_effect=dispatch) as bridge_dispatch, \
                 patch.object(telegram_bridge, "send") as send, \
                 patch.object(
                     backend,
                     "_run_hermes_message",
                     return_value={
                         **self.hermes_result(reply),
                         "profile_requested": "operator-lean",
                         "profile_used": "operator-lean",
                         "profile_fallback": False,
                     },
                 ) as hermes, \
                 patch.object(backend, "_accept_async_queue_runner") as worker:
                for _ in range(2):
                    if telegram_bridge.claim_update(4242):
                        telegram_bridge.handle_message(
                            {"chat": {"id": 123}, "text": self.FOUNDER_INTERVIEW_MESSAGE},
                            delivery_id="telegram-update-4242",
                        )
                after = queue_path.read_bytes()

        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["selected_route"], "hermes_operator_lean")
        self.assertEqual(result["profile_requested"], "operator-lean")
        self.assertEqual(result["profile_used"], "operator-lean")
        self.assertFalse(result["profile_fallback"])
        self.assertEqual(result["queue_delta"], 0)
        self.assertEqual(result["worker_process_count"], 0)
        self.assertEqual(result["output"], reply)
        self.assertTrue(result["context_manifest"]["provenance"])
        self.assertTrue(result["context_bounds"]["sticky_session_key"])
        self.assertEqual(hashlib.sha256(before).hexdigest(), hashlib.sha256(after).hexdigest())
        bridge_dispatch.assert_called_once()
        hermes.assert_called_once()
        worker.assert_not_called()
        send.assert_called_once_with(123, reply, preserve_format=True, document_paths=[])

    def test_ambiguous_item_directed_approval_still_requests_an_aos_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = [
                self.item("AOS-2026-0903", "human_review", title="Review one"),
                self.item("AOS-2026-0904", "needs_input", title="Input two"),
            ]
            self.write_items(root, items)
            before = (root / "queue" / "work_items.jsonl").read_bytes()
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message") as hermes, \
                 patch.object(backend, "_accept_async_queue_runner") as worker:
                result = backend.wsl_hermes(backend.TaskRun(
                    task="I approve that",
                    source="telegram",
                    delivery_id="ambiguous-approval",
                    reply_to="fixture-chat",
                ))
                after = (root / "queue" / "work_items.jsonl").read_bytes()

        self.assertEqual(result["state"], "approval-target-ambiguous")
        self.assertIn("AOS item ID", result["output"])
        self.assertEqual(before, after)
        hermes.assert_not_called()
        worker.assert_not_called()

    def test_unique_item_directed_approval_resumes_the_same_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = self.item("AOS-2026-0905", "needs_input", title="Only pending item")
            self.write_items(root, [item])
            runner = {"available": True, "accepted": True, "state": "accepted", "mode": "one_shot"}
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_accept_async_queue_runner", return_value=runner) as worker, \
                 patch.object(backend, "_run_hermes_message") as hermes:
                result = backend.wsl_hermes(backend.TaskRun(
                    task="I approve that",
                    source="telegram",
                    delivery_id="unique-approval",
                    reply_to="fixture-chat",
                ))
                rows = backend._read_queue_items()

        self.assertEqual(result["work_item_id"], item["id"])
        self.assertEqual(result["state"], "resumed")
        self.assertFalse(result["created"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], item["id"])
        self.assertEqual(rows[0]["status"], "agent_todo")
        worker.assert_called_once()
        hermes.assert_not_called()

    def test_conversation_timeout_is_bounded_above_real_operator_runtime(self):
        self.assertEqual(
            telegram_bridge._agent_request_timeout(self.FOUNDER_INTERVIEW_MESSAGE),
            120,
        )
        self.assertGreater(telegram_bridge.AGENT_RESPONSE_TIMEOUT_SECONDS, backend.OPERATOR_LEAN_TIMEOUT_SECONDS)
        self.assertLessEqual(telegram_bridge.AGENT_RESPONSE_TIMEOUT_SECONDS, 120)
        self.assertEqual(
            telegram_bridge._agent_request_timeout("/work codex run the focused test"),
            telegram_bridge.SUBMISSION_ACK_TIMEOUT_SECONDS,
        )

    def test_conversation_timeout_does_not_fabricate_a_work_item_closeout(self):
        with patch.object(telegram_bridge, "post_agent", side_effect=TimeoutError), \
             patch.object(telegram_bridge, "send") as send, \
             patch.object(telegram_bridge, "log") as log:
            telegram_bridge._run_agent_request(
                123,
                self.FOUNDER_INTERVIEW_MESSAGE,
                "telegram",
                "telegram-update-timeout-proof",
            )

        send.assert_called_once()
        args, kwargs = send.call_args
        self.assertEqual(args[0], 123)
        self.assertTrue(kwargs["preserve_format"])
        self.assertIn("local conversation route timed out", args[1])
        self.assertIn("No queue item or worker was created", args[1])
        self.assertNotIn("Work item:", args[1])
        self.assertNotIn("Final state:", args[1])
        self.assertNotIn("Files touched:", args[1])
        self.assertIn("route=conversation failure=TimeoutError", log.call_args.args[0])

    def test_exact_liam_retry_is_only_ordinary_conversation(self):
        answer = (
            "Strategically, niche selection is now the constraint upstream of prospecting quality "
            "and visible specialization. The goal is a practical first wedge, not a permanent identity. "
            "Which customer group can you reach fastest where missed follow-up or slow lead response "
            "already creates an obvious, costly problem?"
        )
        stale = self.item(
            "AOS-2026-0128",
            "human_review",
            title="Historical item that must not bind",
            delivery_id="exact-retry-stale-delivery",
        )
        body = backend.TaskRun(
            task=self.LIAM_RETRY_MESSAGE,
            source="telegram",
            delivery_id="exact-retry-stale-delivery",
            reply_to="fixture-chat",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [stale])
            before = (root / "queue/work_items.jsonl").read_bytes()
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message", return_value=self.hermes_result(answer)) as hermes, \
                 patch.object(backend, "_accept_async_queue_runner") as worker:
                self.assertIsNone(backend._telegram_approval_intent(self.LIAM_RETRY_MESSAGE))
                self.assertIsNone(backend._WORK_OVERRIDE_RE.fullmatch(self.LIAM_RETRY_MESSAGE))
                self.assertIsNone(backend._queue_create_text(self.LIAM_RETRY_MESSAGE))
                self.assertIsNone(backend._try_queue_read_task(self.LIAM_RETRY_MESSAGE))
                self.assertIsNone(backend._try_existing_item_read_task(self.LIAM_RETRY_MESSAGE, body))
                self.assertIsNone(backend._EXISTING_ITEM_READ_RE.search(self.LIAM_RETRY_MESSAGE))
                self.assertIsNone(backend._TELEGRAM_CORRECTION_RE.search(self.LIAM_RETRY_MESSAGE))
                self.assertIsNone(backend._TELEGRAM_CORRECTION_TARGET_RE.search(self.LIAM_RETRY_MESSAGE))
                self.assertIsNone(backend._TELEGRAM_ITEM_DIRECTED_READ_RE.search(self.LIAM_RETRY_MESSAGE))
                result = backend.wsl_hermes(body)
                after = (root / "queue/work_items.jsonl").read_bytes()

        self.assertEqual(before, after)
        self.assertEqual(result["selected_route"], "hermes_operator_lean")
        self.assertTrue(result["direct_reply"])
        self.assertFalse(result["created"])
        self.assertEqual(result["queue_delta"], 0)
        self.assertEqual(result["worker_process_count"], 0)
        self.assertFalse(result["hermes_orchestrator_invoked"])
        self.assertNotIn("work_item_id", result)
        self.assertNotIn("AOS-2026-0128", result["output"])
        self.assertLessEqual(len(result["output"].split()), 150)
        prompt = hermes.call_args.args[0].request
        self.assertIn("do not call create_task or escalate_to_executive", prompt)
        worker.assert_not_called()

    def test_negative_execution_language_cannot_create_intent_or_work(self):
        phrases = (
            "Do not create a queue item or start execution.",
            "Save this as my current priority; do not start execution.",
            "Continue the interview and ask the next question. Do not create work.",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIsNone(backend._WORK_OVERRIDE_RE.fullmatch(phrase))
                self.assertIsNone(backend._telegram_approval_intent(phrase))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [])
            queue_before = (root / "queue/work_items.jsonl").read_bytes()
            hermes_python = Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "python3"
            probe = subprocess.run(
                [
                    str(hermes_python),
                    "-c",
                    (
                        "import json; from tools import operator_lean_mcp as m; "
                        "print(json.dumps({'creation': m.create_task('research five prospects', "
                        "'revenue', 'negative-language', 'fixture-chat'), "
                        "'escalation': m.escalate_to_executive('Choose the priority.')}))"
                    ),
                ],
                cwd=ROOT,
                env={
                    **os.environ,
                    "AOS_ROOT": str(root),
                    "PYTHONPATH": f"{ROOT / 'tools'}{os.pathsep}{ROOT}",
                },
                text=True,
                capture_output=True,
                timeout=20,
                check=True,
            )
            payload = json.loads(probe.stdout)
            creation = payload["creation"]
            escalation = payload["escalation"]
            queue_after = (root / "queue/work_items.jsonl").read_bytes()

        self.assertFalse(creation["created"])
        self.assertIn("explicit /work", creation["error"])
        self.assertIn("already the active surface", escalation)
        self.assertEqual(queue_before, queue_after)

    def test_conversational_exception_cannot_bind_stale_delivery_item(self):
        stale = self.item(
            "AOS-2026-0128",
            "human_review",
            title="Historical stale delivery",
            delivery_id="reused-conversation-delivery",
        )
        failure = {
            "success": False,
            "output": "The local executive conversation failed before answering.",
            "stderr": "invocation timeout",
            "profile_used": "operator-lean",
            "token_usage": {"available": False},
            "token_usage_text": "Token usage: unavailable from current CLI output",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [stale])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message", return_value=failure), \
                 patch.object(backend, "_accept_async_queue_runner") as worker:
                result = backend.wsl_hermes(backend.TaskRun(
                    task="Continue our conversation.",
                    source="telegram",
                    delivery_id="reused-conversation-delivery",
                    reply_to="fixture-chat",
                ))

        summary = telegram_bridge.summarize_agent_result(result)
        self.assertTrue(result["direct_reply"])
        self.assertEqual(result["queue_delta"], 0)
        self.assertNotIn("work_item_id", result)
        self.assertNotIn("AOS-2026-0128", json.dumps(result, sort_keys=True))
        self.assertNotIn("AOS-2026-0128", summary)
        self.assertNotIn("Work item:", summary)
        worker.assert_not_called()

    def test_explicit_current_scope_fuse_reset_is_deterministic_and_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [])
            reply_to = "fixture-current-chat"
            scope = Scope("session", backend._operator_session_key(reply_to))
            other = Scope("session", "unrelated-session")
            record_unavailable_invocation(scope, invocation_id="unknown-current", reason="missing usage", root=root)
            record_unavailable_invocation(other, invocation_id="unknown-other", reason="missing usage", root=root)
            other_before = fuse_status(other, root=root)
            queue_before = (root / "queue/work_items.jsonl").read_bytes()
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message") as hermes, \
                 patch.object(backend, "_accept_async_queue_runner") as worker:
                result = backend.wsl_hermes(backend.TaskRun(
                    task="Reset the Step 6 fuse for only this Telegram executive scope.",
                    source="telegram",
                    delivery_id="fixture-fuse-reset",
                    reply_to=reply_to,
                ))

            self.assertTrue(result["success"])
            self.assertEqual(result["scope_key"], scope.key)
            self.assertEqual(result["selected_route"], "deterministic_scoped_fuse_recovery")
            self.assertEqual(result["model_process_count"], 0)
            self.assertEqual(result["worker_process_count"], 0)
            self.assertEqual(result["queue_delta"], 0)
            self.assertFalse(result["hermes_orchestrator_invoked"])
            self.assertEqual((root / "queue/work_items.jsonl").read_bytes(), queue_before)
            self.assertEqual(fuse_status(other, root=root), other_before)
            preflight(scope, root=root)
            hermes.assert_not_called()
            worker.assert_not_called()

    def test_required_conversations_return_substantive_direct_replies_without_queue(self):
        cases = (
            (
                "How much insight do you have on Time to Revenue which is my business?",
                "I have substantive current context: Time to Revenue is Liam's practical AI "
                "operations and workflow consultancy, focused on systems that move revenue and "
                "improve operator leverage. Its systems-led offers include speed-to-lead, voice "
                "agents, lead generation, client memory, workflow agents, and ongoing AI ops.",
                {
                    "business_brain:memory/company.md",
                    "business_brain:memory/offers.md",
                    "business_brain:memory/positioning.md",
                },
            ),
            (
                "What should I focus on next to start getting clients?",
                "Focus on the live draft-first prospecting engine: work the five-prospect weekday "
                "cadence, prioritize warm and semi-warm relationships plus the current ICP lane, "
                "and turn qualified research into approval-gated outreach drafts. Keep sends "
                "manual while the first three no-send runs harden the workflow.",
                {
                    "business_brain:operating_context/current_priorities.md",
                    "business_brain:memory/sales_and_revenue.md",
                    "business_brain:memory/prospecting_rotation_plan.md",
                },
            ),
        )
        for index, (message, answer, expected_sources) in enumerate(cases, start=1):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.write_items(root, [])
                before = (root / "queue" / "work_items.jsonl").read_bytes()
                with patch.object(backend, "BASE_DIR", root), \
                     patch.object(backend, "_run_hermes_message", return_value=self.hermes_result(answer)) as hermes, \
                     patch.object(backend, "_accept_async_queue_runner") as worker:
                    result = backend.wsl_hermes(
                        backend.TaskRun(
                            task=message,
                            delivery_id=f"required-conversation-{index}",
                            reply_to=f"required-chat-{index}",
                        )
                    )
                    after = (root / "queue" / "work_items.jsonl").read_bytes()

            self.assertEqual(before, after)
            self.assertEqual(result["selected_route"], "hermes_operator_lean")
            self.assertEqual(result["queue_delta"], 0)
            self.assertFalse(result["created"])
            self.assertTrue(result["direct_reply"])
            self.assertEqual(result["output"], answer)
            self.assertNotIn("did not create a task", result["output"].casefold())
            retrieved_sources = set(result["brain_context_used"])
            self.assertTrue(any(source.startswith("business_brain:") for source in retrieved_sources))
            supplied_prompt = hermes.call_args.args[0]
            self.assertTrue(any(
                source in value
                for source in expected_sources
                for value in supplied_prompt.provenance
            ))
            summary = telegram_bridge.summarize_agent_result(result)
            self.assertEqual(summary, answer)
            self.assertTrue(telegram_bridge.preserve_agent_result_format(result, summary))
            with patch.object(telegram_bridge, "send") as send:
                telegram_bridge.deliver_agent_result(123, result)
            send.assert_called_once_with(
                123,
                answer,
                preserve_format=True,
                document_paths=[],
            )
            hermes.assert_called_once()
            worker.assert_not_called()

    def test_generic_conversation_still_receives_required_one_brain_prefix(self):
        message = "What makes a conversation feel genuinely useful?"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend.business_brain_context, "ScopedBrainLoader") as loader, \
                 patch.object(
                     backend,
                     "_run_hermes_message",
                     return_value=self.hermes_result("Specificity, candour, and a useful next thought."),
                 ) as hermes:
                result = backend.wsl_hermes(
                    backend.TaskRun(
                        task=message,
                        delivery_id="required-generic",
                        reply_to="required-chat-generic",
                    )
                )

        self.assertEqual(result["queue_delta"], 0)
        self.assertTrue(any("memory/company.md" in source for source in result["brain_context_used"]))
        self.assertIn("identity/company", [block.name for block in hermes.call_args.args[0].blocks])
        loader.assert_not_called()

    def test_non_work_execution_language_cannot_create_a_task(self):
        instruction = "Create a task to research 5 prospects."
        delivery_id = "required-execution"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend.business_brain_context, "ScopedBrainLoader") as loader, \
                 patch.object(
                     backend,
                     "_run_hermes_message",
                     return_value=self.hermes_result("Use an explicit /work request when you want execution."),
                 ), \
                 patch.object(backend, "_accept_async_queue_runner") as worker:
                result = backend.wsl_hermes(
                    backend.TaskRun(task=instruction, delivery_id=delivery_id, reply_to="required-chat-3")
                )
                rows = backend._read_queue_items()

        self.assertEqual(rows, [])
        self.assertEqual(result["queue_delta"], 0)
        self.assertFalse(result["created"])
        self.assertNotIn("work_item_id", result)
        self.assertTrue(any(source.startswith("business_brain:") for source in result["brain_context_used"]))
        loader.assert_not_called()
        worker.assert_not_called()

    def test_operator_lean_failure_returns_direct_error_without_queue(self):
        failure = {
            "success": False,
            "output": "Hermes operator-lean failed before answering. No task was queued.",
            "reply": "",
            "stderr": "Hermes operator-lean failed before answering. No task was queued.",
            "token_usage": {"available": False, "failed": True},
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "elapsed_seconds": 0.1,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_items(root, [])
            before = (root / "queue" / "work_items.jsonl").read_bytes()
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message", return_value=failure), \
                 patch.object(backend, "_accept_async_queue_runner") as worker:
                result = backend.wsl_hermes(
                    backend.TaskRun(
                        task="How much do you know about Time to Revenue?",
                        delivery_id="required-failure",
                        reply_to="required-chat-failure",
                    )
                )
                after = (root / "queue" / "work_items.jsonl").read_bytes()

        self.assertEqual(before, after)
        self.assertFalse(result["success"])
        self.assertFalse(result["created"])
        self.assertEqual(result["queue_delta"], 0)
        self.assertTrue(result["direct_reply"])
        self.assertIn("No task was queued", result["output"])
        worker.assert_not_called()

    def test_operator_oneshot_waits_for_complete_tool_snapshot(self):
        events = []

        def discover():
            events.append("discovered")
            return list(operator_lean_oneshot.EXPECTED_TOOLS)

        def construct_agent(prompt, **kwargs):
            self.assertEqual(events, ["discovered"])
            events.append("constructed")
            self.assertEqual(kwargs["toolsets"], ["operator", "brain"])
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

    def test_live_loaded_operator_preamble_has_exact_bounded_tools_under_budget(self):
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
        self.assertEqual(len(preamble["tools"]), 9)
        create_task = next(
            row for row in preamble["tools"]
            if row["function"]["name"] == "mcp__operator__create_task"
        )
        self.assertEqual(
            set(create_task["function"]["parameters"]["properties"]["worker"]["enum"]),
            {"revenue", "marketing", "delivery", "operations", "codex", "claude"},
        )
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
        self.assertLess(system_tokens + tool_tokens, 3_500)

    def test_profile_launcher_and_tool_server_enforce_lean_surface(self):
        launcher = (ROOT / "tools" / "aos-hermes-operator-lean.sh").read_text(encoding="utf-8")
        profile = (ROOT / "queue" / "profiles" / "operator-lean.md").read_text(encoding="utf-8")
        server = (ROOT / "tools" / "operator_lean_mcp.py").read_text(encoding="utf-8")
        self.assertEqual(len(operator_lean_oneshot.EXPECTED_TOOLS), 9)
        self.assertIn('profile="operator-lean"', launcher)
        self.assertIn('cd "$profile_home"', launcher)
        self.assertIn("operator_lean_oneshot.py", launcher)
        self.assertNotIn("aos-orchestrator", launcher)
        self.assertIn("never call `escalate_to_executive`", profile)
        self.assertIn('export AOS_OPERATOR_CONTEXT_FILE="$prompt_file"', launcher)
        self.assertIn('export AOS_OPERATOR_ESCALATION_REPLY_FILE="$escalation_reply_file"', launcher)
        self.assertIn("Never call `create_task`", profile)
        self.assertEqual(server.count("@mcp.tool()"), 7)
        self.assertIn("brain_memory_mcp.py", (Path.home() / ".hermes" / "profiles" / "operator-lean" / "config.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("create_item(", server)
        self.assertNotIn("subprocess.run", server)
        self.assertNotIn('/home/liam/agentic-os/hermes/hermes.py', server)


if __name__ == "__main__":
    unittest.main()
