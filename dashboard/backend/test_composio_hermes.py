import importlib.util
import asyncio
import datetime
import json
import re
import sys
import tempfile
import threading
import time
import types
import unittest
from dataclasses import replace
from pathlib import Path, PureWindowsPath
from unittest.mock import Mock, patch


# The Linux static-validation shell does not carry the Windows backend venv.
# Minimal import stubs keep these tests focused on routing logic without adding
# or changing runtime dependencies.
class _FastAPI:
    def __init__(self, *args, **kwargs):
        pass

    def add_middleware(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        return lambda function: function

    post = get
    middleware = get


class _HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


class _Request:
    method = "GET"


class _JSONResponse(dict):
    def __init__(self, status_code, content):
        super().__init__(content)
        self.status_code = status_code


class _BaseModel:
    def __init__(self, **values):
        for key, value in values.items():
            setattr(self, key, value)


if importlib.util.find_spec("fastapi") is None:
    fastapi = types.ModuleType("fastapi")
    fastapi.__spec__ = importlib.util.spec_from_loader("fastapi", loader=None)
    fastapi.FastAPI = _FastAPI
    fastapi.HTTPException = _HTTPException
    fastapi.Request = _Request
    middleware = types.ModuleType("fastapi.middleware")
    cors = types.ModuleType("fastapi.middleware.cors")
    responses = types.ModuleType("fastapi.responses")
    middleware.__spec__ = importlib.util.spec_from_loader("fastapi.middleware", loader=None)
    cors.__spec__ = importlib.util.spec_from_loader("fastapi.middleware.cors", loader=None)
    responses.__spec__ = importlib.util.spec_from_loader("fastapi.responses", loader=None)
    cors.CORSMiddleware = object
    responses.JSONResponse = _JSONResponse
    sys.modules.update({"fastapi": fastapi, "fastapi.middleware": middleware, "fastapi.middleware.cors": cors, "fastapi.responses": responses})

if importlib.util.find_spec("pydantic") is None:
    pydantic = types.ModuleType("pydantic")
    pydantic.__spec__ = importlib.util.spec_from_loader("pydantic", loader=None)
    pydantic.BaseModel = _BaseModel
    sys.modules["pydantic"] = pydantic


MAIN = Path(__file__).with_name("main.py")
SPEC = importlib.util.spec_from_file_location("agentic_os_backend", MAIN)
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


class HermesComposioTests(unittest.TestCase):
    def test_dashboard_inbox_capture_writes_brain_note_without_queue_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "inbox/source_notes").mkdir(parents=True)
            (vault / "inbox/README.md").write_text(
                "---\nid: ttros-brain-inbox\ntype: intake\n---\n# Inbox\n",
                encoding="utf-8",
            )
            with patch.object(backend.business_brain, "BUSINESS_BRAIN_ROOT", vault), \
                 patch.object(backend, "_queue_create_dashboard_item") as create_queue:
                result = backend.dashboard_capture(backend.CockpitCaptureCreate(text="Dashboard note", capture_id="ui-1"))

            create_queue.assert_not_called()
            self.assertTrue(result["success"])
            self.assertFalse(result["queue_item_created"])
            self.assertFalse(result["promoted"])
            self.assertTrue(result["pointer"].startswith("business_brain:inbox/source_notes/capture_"))

    def test_claude_timeout_contract_is_exact_and_independent(self):
        self.assertEqual(backend.INLINE_COMMAND_TIMEOUT_SECONDS, 120)
        self.assertEqual(backend.AGENT_STARTUP_TIMEOUT_SECONDS, 60)
        self.assertEqual(backend.AGENT_TIMEOUT_SECONDS, 7800)
        self.assertEqual(backend.QUEUE_WORKER_TIMEOUT_SECONDS, 7800)
        self.assertEqual(backend.AGENT_GRACEFUL_TERMINATION_SECONDS, 10)
        self.assertEqual(backend.AGENT_PARENT_TIMEOUT_SECONDS, 7870)
        self.assertEqual(backend.QUEUE_HERMES_REVIEW_TIMEOUT_SECONDS, 120)
        self.assertEqual(backend.QUEUE_FINALIZATION_TIMEOUT_SECONDS, 120)
        self.assertNotEqual(backend.AGENT_STARTUP_TIMEOUT_SECONDS, backend.AGENT_TIMEOUT_SECONDS)

    def test_claude_worker_passes_separate_startup_and_execution_timeouts(self):
        item = {"id": "AOS-2026-0200", "title": "Claude timeout proof", "owner": "claude"}
        completed = {
            "success": True, "output": "PASS\nFiles touched: None\nValidation: fixture\nBlockers: None",
            "stdout": "PASS", "stderr": "", "returncode": 0,
        }
        with patch.object(backend, "_queue_resolve_route_metadata", return_value=self.route_metadata_fixture("claude")), \
             patch.object(backend, "_run_wsl_prompt_command", return_value=completed) as run, \
             patch.object(backend, "_local_agent_route_log", return_value="logs/local_agent_route.jsonl"), \
             patch.object(backend, "_log_token_usage"):
            result = backend._queue_run_worker("claude", "fixture prompt", item)
        self.assertTrue(result["success"])
        self.assertEqual(run.call_args.args[2], 7800)
        self.assertEqual(run.call_args.kwargs["startup_timeout"], 60)
        self.assertTrue(callable(run.call_args.kwargs["on_process_start"]))

    def test_supervised_claude_parent_preserves_partial_stdout_and_stderr_on_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            command = (
                "python3 -c \"import sys,time; "
                "print('claude stdout', flush=True); "
                "print('claude stderr', file=sys.stderr, flush=True); time.sleep(5)\""
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "AGENT_GRACEFUL_TERMINATION_SECONDS", 1):
                result = backend._run_wsl_supervised(command, timeout=0.1)
        self.assertTrue(result["timed_out"])
        self.assertIn("claude stdout", result["stdout"])
        self.assertIn("claude stderr", result["stderr"])
        self.assertEqual(result["graceful_termination_seconds"], 1)

    def test_installed_claude_wrapper_is_linux_root_bound(self):
        wrapper = Path("/home/liam/.local/bin/aos-claude").read_text(encoding="utf-8")
        self.assertIn('CANONICAL_AOS_ROOT="/home/liam/agentic-os-live"', wrapper)
        self.assertIn("/home/liam/.local/npm/bin/claude", wrapper)
        self.assertNotIn("/mnt/c/", wrapper)

    def test_installed_hermes_claude_router_is_linux_root_bound(self):
        router = Path("/home/liam/agentic-os/hermes/hermes.py").read_text(encoding="utf-8")
        self.assertIn('CANONICAL_LIVE = pathlib.Path("/home/liam/agentic-os-live")', router)
        self.assertIn('os.environ.get("AOS_ROOT"', router)
        self.assertNotIn("/mnt/c/", router)

    def test_hermes_coordinator_wrapper_pins_profile_per_invocation_without_sticky_mutation(self):
        wrapper = (MAIN.parents[2] / "tools" / "aos-hermes-coordinator.sh").read_text(encoding="utf-8")
        self.assertIn('profile="aos-orchestrator"', wrapper)
        self.assertIn('hermes -p "$profile"', wrapper)
        self.assertNotIn("hermes profile use", wrapper)
        self.assertIn("exit 78", wrapper)

    def test_inline_and_agent_timeout_configs_have_independent_defaults_and_overrides(self):
        with patch.dict(backend.os.environ, {}, clear=True):
            self.assertEqual(backend._timeout_seconds_from_env("AOS_INLINE_COMMAND_TIMEOUT_SECONDS", 120, 1), 120)
            self.assertEqual(backend._timeout_seconds_from_env("AOS_AGENT_TIMEOUT_SECONDS", 1800, 1), 1800)
        with patch.dict(backend.os.environ, {
            "AOS_INLINE_COMMAND_TIMEOUT_SECONDS": "45",
            "AOS_AGENT_TIMEOUT_SECONDS": "2400",
        }, clear=True):
            self.assertEqual(backend._timeout_seconds_from_env("AOS_INLINE_COMMAND_TIMEOUT_SECONDS", 120, 1), 45)
            self.assertEqual(backend._timeout_seconds_from_env("AOS_AGENT_TIMEOUT_SECONDS", 1800, 1), 2400)
        with patch.dict(backend.os.environ, {"AOS_AGENT_TIMEOUT_SECONDS": "invalid"}, clear=True):
            self.assertEqual(backend._timeout_seconds_from_env("AOS_AGENT_TIMEOUT_SECONDS", 1800, 1), 1800)

    def test_codex_supervisor_real_subprocess_captures_prompt_streams_completion_and_exact_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executable = root / "codex-fixture"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import json, pathlib, sys\n"
                "prompt = sys.stdin.read()\n"
                "root = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
                "if 'FULL_PROMPT_SENTINEL' not in prompt:\n"
                "    print('prompt missing', file=sys.stderr)\n"
                "    raise SystemExit(9)\n"
                "(root / 'codex_fixture.txt').write_text('LOCAL_CODEX_ROUTE_OK\\n', encoding='utf-8')\n"
                "print(json.dumps({'type':'thread.started','thread_id':'fixture-thread'}), flush=True)\n"
                "print('fixture stderr capture', file=sys.stderr, flush=True)\n"
                "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'PASS\\nFiles touched: codex_fixture.txt\\nValidation: deterministic subprocess\\nBlockers: None'}}), flush=True)\n"
                "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':21,'cached_input_tokens':5,'output_tokens':7}}), flush=True)\n",
                encoding="utf-8",
            )
            executable.chmod(0o755)
            target = replace(backend.CODEX_TARGET, root=root, executable=executable, codex_home=root / ".codex")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "CODEX_TARGET", target), \
                 patch.object(backend, "AGENT_STARTUP_TIMEOUT_SECONDS", 5), \
                 patch.object(backend, "AGENT_TIMEOUT_SECONDS", 5):
                result = backend._run_codex_local("full task FULL_PROMPT_SENTINEL")

            route_rows = [
                json.loads(line)
                for line in (root / "logs" / "local_agent_route.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            artifact_text = (root / "codex_fixture.txt").read_text(encoding="utf-8")

        self.assertTrue(result["success"])
        self.assertEqual(result["command_stage"], "completion")
        self.assertIn("PASS", result["output"])
        self.assertIn("fixture stderr capture", result["stderr"])
        self.assertEqual(result["token_usage"]["total_tokens"], 28)
        self.assertEqual(result["token_usage"]["input_tokens"], 21)
        self.assertEqual(result["token_usage"]["cached_input_tokens"], 5)
        self.assertEqual(result["token_usage"]["output_tokens"], 7)
        self.assertEqual(result["token_usage_text"], "Token usage: input 21, output 7, cached input 5, total 28")
        self.assertEqual(artifact_text, "LOCAL_CODEX_ROUTE_OK\n")
        self.assertEqual(route_rows[-1]["success"], True)
        self.assertEqual(route_rows[-1]["stage"], "completion")

    def test_codex_supervisor_separates_startup_and_execution_timeouts_with_partial_streams(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executable = root / "codex-timeout-fixture"

            def run_fixture(source: str):
                executable.write_text("#!/usr/bin/env python3\n" + source, encoding="utf-8")
                executable.chmod(0o755)
                target = replace(backend.CODEX_TARGET, root=root, executable=executable, codex_home=root / ".codex")
                with patch.object(backend, "BASE_DIR", root), \
                     patch.object(backend, "CODEX_TARGET", target), \
                     patch.object(backend, "AGENT_STARTUP_TIMEOUT_SECONDS", 0.15), \
                     patch.object(backend, "AGENT_TIMEOUT_SECONDS", 0.15):
                    return backend._run_codex_local("timeout fixture prompt")

            startup = run_fixture(
                "import sys, time\n"
                "print('still booting', file=sys.stderr, flush=True)\n"
                "time.sleep(5)\n"
            )
            execution = run_fixture(
                "import json, sys, time\n"
                "print(json.dumps({'type':'thread.started','thread_id':'timeout-thread'}), flush=True)\n"
                "print('working before timeout', file=sys.stderr, flush=True)\n"
                "time.sleep(5)\n"
            )

        self.assertTrue(startup["timed_out"])
        self.assertEqual(startup["failure_class"], "startup_timeout")
        self.assertEqual(startup["command_stage"], "startup")
        self.assertIn("still booting", startup["stderr"])
        self.assertTrue(execution["timed_out"])
        self.assertEqual(execution["failure_class"], "execution_timeout")
        self.assertEqual(execution["command_stage"], "execution")
        self.assertIn("thread.started", execution["stdout"])
        self.assertIn("working before timeout", execution["stderr"])

    def test_file_assessment_is_queued_immediately_with_real_id_and_duplicate_reused(self):
        task = r"Give this task to Codex: assess the files at C:\Users\Liam\Downloads\candidate-workflow and incorporate them if useful, then run tests."
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = {"available": True, "state": "running", "pid": 123}
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_runner_status", return_value=runner), \
                 patch.object(backend, "_run_wsl") as run, \
                 patch.object(backend, "run_queue_item") as worker:
                started = time.monotonic()
                first = backend.wsl_hermes(backend.TaskRun(task=task, delivery_id="telegram-update-44"))
                elapsed = time.monotonic() - started
                second = backend.wsl_hermes(backend.TaskRun(task=task, delivery_id="telegram-update-44"))
                rows = backend._read_queue_items()

        run.assert_not_called()
        worker.assert_not_called()
        self.assertLess(elapsed, 0.5)
        self.assertTrue(first["created"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["work_item_id"], second["work_item_id"])
        self.assertIn(first["work_item_id"], first["output"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "agent_todo")
        self.assertEqual(rows[0]["context"], task)
        self.assertEqual(rows[0]["sources"], [r"C:\Users\Liam\Downloads\candidate-workflow"])
        self.assertIn("file_assessment", first["routing_signals"])
        self.assertIn("validation_or_proof", first["routing_signals"])

    def test_short_allowlisted_queue_status_stays_inline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_create_async_dispatch_item") as create, \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.wsl_hermes(backend.TaskRun(task="Queue status"))
        create.assert_not_called()
        run.assert_not_called()
        self.assertEqual(result["selected_route"], "local_queue_status")
        self.assertEqual(result["timeout_contract"], "inline_command")
        self.assertEqual(result["timeout_seconds"], backend.INLINE_COMMAND_TIMEOUT_SECONDS)

    def test_system_status_reports_bridge_and_downstream_without_agent_or_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [])
            readiness = {
                "codex": {"available": True, "state": "ready", "executable": "/usr/bin/codex", "authenticated": True},
                "hermes": {"available": True, "state": "ready", "executable": "/usr/bin/hermes"},
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "codex_policy_readiness", return_value=readiness["codex"]), \
                 patch.object(backend, "_binary_readiness", side_effect=lambda name, **_: readiness[name]), \
                 patch.object(backend, "_process_marker_running", return_value=False), \
                 patch.object(backend, "_queue_runner_status", return_value={"available": False, "state": "unavailable", "pid": None}), \
                 patch.object(backend, "_create_async_dispatch_item") as create, \
                 patch.object(backend, "_run_hermes_message") as hermes:
                result = backend.wsl_hermes(backend.TaskRun(task="show status"))
        create.assert_not_called()
        hermes.assert_not_called()
        self.assertEqual(result["state"], "degraded")
        self.assertIn("Bridge health: not_running", result["output"])
        self.assertIn("Backend health: ready", result["output"])
        self.assertIn("Runner state: on_demand_idle", result["output"])
        self.assertIn("Codex availability: ready", result["output"])
        self.assertIn("Hermes availability: ready", result["output"])

    def test_process_marker_requires_real_process_argument_not_shell_text(self):
        shell = Mock()
        shell.read_bytes.return_value = b"/bin/bash\0-c\0inspect connectors/telegram_bridge/telegram_bridge.py\0"
        bridge = Mock()
        bridge.read_bytes.return_value = b"python3\0/home/liam/agentic-os-live/connectors/telegram_bridge/telegram_bridge.py\0"
        with patch.object(Path, "glob", return_value=[shell]):
            self.assertFalse(backend._process_marker_running("telegram_bridge.py"))
        with patch.object(Path, "glob", return_value=[shell, bridge]):
            self.assertTrue(backend._process_marker_running("telegram_bridge.py"))

    def test_system_status_degrades_for_latest_route_failure_and_recovers_after_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [])
            log = root / "logs" / "local_agent_route.jsonl"
            log.parent.mkdir(parents=True)
            failure = {
                "timestamp": "2026-07-17T10:00:00Z",
                "route": "codex",
                "success": False,
                "failure_class": "startup_timeout",
                "stage": "startup",
            }
            log.write_text(json.dumps(failure) + "\n", encoding="utf-8")
            readiness = {
                "codex": {"available": True, "state": "ready", "executable": "/usr/bin/codex"},
                "hermes": {"available": True, "state": "ready", "executable": "/usr/bin/hermes"},
            }
            patches = (
                patch.object(backend, "BASE_DIR", root),
                patch.object(backend, "codex_policy_readiness", return_value=readiness["codex"]),
                patch.object(backend, "_binary_readiness", side_effect=lambda name, **_: readiness[name]),
                patch.object(backend, "_process_marker_running", return_value=True),
                patch.object(backend, "_queue_runner_status", return_value={"available": True, "pid": 123}),
            )
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                degraded = backend._operator_system_status_closeout()
                log.write_text(
                    json.dumps(failure) + "\n" + json.dumps({
                        "timestamp": "2026-07-17T10:01:00Z",
                        "route": "codex",
                        "success": True,
                    }) + "\n",
                    encoding="utf-8",
                )
                recovered = backend._operator_system_status_closeout()

        self.assertEqual(degraded["state"], "degraded")
        self.assertEqual(degraded["last_route_failure"]["failure_class"], "startup_timeout")
        self.assertEqual(recovered["state"], "healthy")
        self.assertIsNone(recovered["last_route_failure"])

    def test_existing_receipt_read_is_inline_and_does_not_create_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = root / "queue" / "receipts" / "AOS-2026-0200.md"
            receipt.parent.mkdir(parents=True)
            receipt.write_text(
                "NEEDS ATTENTION\n\nFiles touched:\n- None reported\n\nValidation:\n- route failed\n\nBlockers:\n- execution_timeout at execution\n\nNext action:\n- repair route\n",
                encoding="utf-8",
            )
            notification = receipt.with_name("AOS-2026-0200-notification-later.md")
            notification.write_text("Notification only; no diagnostic sections.\n", encoding="utf-8")
            item = self.approval_item("AOS-2026-0200", "blocked", title="Repair Codex route")
            item["receipts"] = [
                {"path": "queue/receipts/AOS-2026-0200.md", "status": "blocked"},
                {"path": "queue/receipts/AOS-2026-0200-notification-later.md", "status": "blocked"},
            ]
            self.write_queue_items(root, [item])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_create_async_dispatch_item") as create, \
                 patch.object(backend, "_run_hermes_message") as hermes:
                result = backend.wsl_hermes(backend.TaskRun(task="Explain receipt AOS-2026-0200 and show why it was blocked"))
                rows = backend._read_queue_items()
        create.assert_not_called()
        hermes.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertEqual(result["selected_route"], "local_existing_item_read")
        self.assertFalse(result["created"])
        self.assertIn("execution_timeout at execution", result["output"])
        self.assertEqual(result["receipt_path"], "queue/receipts/AOS-2026-0200.md")
        self.assertEqual(len(result["document_paths"]), 1)

    def test_ordinary_conversation_uses_direct_hermes_without_queue(self):
        reply = {
            "success": True,
            "reply": "I can help with the current Agentic OS.",
            "output": "I can help with the current Agentic OS.",
            "stdout": "I can help with the current Agentic OS.",
            "stderr": "",
            "returncode": 0,
            "token_usage": {"available": False},
            "token_usage_text": "Token usage: unavailable from current CLI output",
        }
        with patch.object(backend, "_run_hermes_message", return_value=reply) as hermes, \
             patch.object(backend, "_hermes_coordinator_closeout", return_value={"success": True, "selected_route": "hermes_coordinator", "output": reply["reply"]}), \
             patch.object(backend, "_create_async_dispatch_item") as create:
            result = backend.wsl_hermes(backend.TaskRun(task="What can you help me with?"))
        create.assert_not_called()
        hermes.assert_called_once()
        self.assertEqual(result["selected_route"], "hermes_coordinator")

    def test_already_metered_hermes_result_is_not_aggregated_twice(self):
        result = {
            "success": True, "output": "Natural Hermes answer", "stdout": "Natural Hermes answer", "stderr": "",
            "returncode": 0, "token_usage_logged": True,
            "token_usage": {"available": True, "session_id": "hermes-session", "input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
            "token_usage_text": "Token usage: input 12, output 3, total 15",
        }
        route = {"requested_target": "hermes", "selected_route": "hermes_coordinator", "delegation_reason": "fixture", "codex_forbidden": "no"}
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(backend, "RESULTS_DIR", Path(tmp)), \
             patch.object(backend, "_log_token_usage") as log:
            closeout = backend._hermes_coordinator_closeout(result, "fixture question", route)
        log.assert_not_called()
        self.assertTrue(closeout["success"])

    def test_codex_json_summary_captures_exact_reported_usage_only(self):
        stream = "\n".join((
            json.dumps({"type": "thread.started", "thread_id": "fixture-session"}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "PASS\nValidation: fixture"}}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 5, "cached_input_tokens": 3}}),
        ))
        message, usage, token_text, started = backend._codex_json_summary(stream)
        self.assertTrue(started)
        self.assertEqual(message, "PASS\nValidation: fixture")
        self.assertEqual(usage["total_tokens"], 17)
        self.assertEqual(usage["session_id"], "fixture-session")
        self.assertEqual(usage["total_input"], 12)
        self.assertEqual(usage["cached_input"], 3)
        self.assertEqual(usage["non_cached_input"], 9)
        self.assertEqual(usage["input_plus_output"], 17)
        self.assertEqual(usage["fresh_input"], 9)
        self.assertEqual(usage["cache_ratio"], 0.333333)
        self.assertEqual(token_text, "Token usage: input 12, output 5, cached input 3, total 17")
        self.assertEqual(
            backend._queue_artifact_candidates_from_text("Diagnostics: logs/local_agent_route.jsonl."),
            ["logs/local_agent_route.jsonl"],
        )

    def test_natural_language_explicit_workbench_routes_bypass_hermes(self):
        cases = (
            ("give this task to Codex: inspect the local route", "codex", "direct_codex"),
            ("Use Claude Code for this: inspect the local route", "claude", "direct_claude"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_templates(root)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_runner_status", return_value={"available": True, "state": "running", "pid": 1}), \
                 patch.object(backend, "_run_hermes_message") as hermes:
                results = [backend.wsl_hermes(backend.TaskRun(task=task, source="local_fixture")) for task, _, _ in cases]
                rows = backend._read_queue_items()
        hermes.assert_not_called()
        self.assertEqual([row["owner"] for row in results], [case[1] for case in cases])
        self.assertEqual([row["selected_route"] for row in results], [case[2] for case in cases])
        self.assertEqual([row["owner"] for row in rows], ["codex", "claude"])

    def test_explicit_codex_review_request_uses_native_hermes_as_outer_coordinator(self):
        plan_reply = {
            "success": True,
            "reply": '```json\n{"title":"Coordinated fixture","tasks":[{"title":"Child one","context":"one","definition_of_done":"pass"}]}\n```',
            "output": '```json\n{"title":"Coordinated fixture","tasks":[{"title":"Child one","context":"one","definition_of_done":"pass"}]}\n```',
            "stdout": "", "stderr": "", "returncode": 0,
            "token_usage": {"session_id": "hermes-plan-session"},
            "token_usage_text": "Token usage: fixture",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [])
            self.write_queue_references(root)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message", return_value=plan_reply) as hermes, \
                 patch.object(backend, "_accept_async_queue_runner", return_value={"accepted": True}):
                result = backend.wsl_hermes(backend.TaskRun(
                    task="give this to Codex, review it and send it back if needed",
                    source="local_fixture",
                ))
                rows = backend._read_queue_items()
        hermes.assert_called_once()
        self.assertEqual(hermes.call_args.kwargs["role"], "coordinator")
        self.assertEqual(result["selected_route"], "hermes_orchestration")
        self.assertEqual(result["outer_coordinator"], "hermes")
        self.assertEqual(result["coordinator_profile"], "aos-orchestrator")
        parent = next(row for row in rows if "hermes_orchestration_parent" in row.get("tags", []))
        child = next(row for row in rows if "hermes_orchestration_child" in row.get("tags", []))
        self.assertEqual(parent["owner"], "hermes")
        self.assertEqual(child["owner"], "codex")
        self.assertEqual(child["orchestration"]["outer_coordinator"], "hermes")

    def test_structured_queue_question_is_read_only_and_ambiguous_question_uses_native_hermes(self):
        reply = {
            "success": True,
            "reply": "Hermes says the highest-leverage next step is to inspect the failing receipt first.",
            "output": "Hermes says the highest-leverage next step is to inspect the failing receipt first.",
            "stdout": "Hermes says the highest-leverage next step is to inspect the failing receipt first.",
            "stderr": "",
            "returncode": 0,
            "token_usage": {"available": False},
            "token_usage_text": "Token usage: unavailable from current CLI output",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = self.sample_queue_items()[2]
            self.write_queue_items(root, [item])
            before = (root / "queue/work_items.jsonl").read_bytes()
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_create_async_dispatch_item") as create, \
                 patch.object(backend, "_run_hermes_message", return_value=reply) as hermes:
                status = backend.wsl_hermes(backend.TaskRun(task="What is currently blocked?"))
                after_status = (root / "queue/work_items.jsonl").read_bytes()
                fallback = backend.wsl_hermes(backend.TaskRun(task="What is the wisest way to prioritise this situation?"))
                after_fallback = (root / "queue/work_items.jsonl").read_bytes()
        create.assert_not_called()
        hermes.assert_called_once()
        self.assertEqual(status["selected_route"], "local_queue_read")
        self.assertIn("Blocked connector decision", status["output"])
        self.assertEqual(before, after_status)
        self.assertEqual(after_status, after_fallback)
        self.assertEqual(fallback["selected_route"], "hermes_coordinator")
        self.assertIn("highest-leverage", fallback["output"])

    def test_hermes_orchestration_children_pass_after_zero_one_and_two_corrections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [])
            self.write_queue_templates(root)
            self.write_queue_references(root)
            plan = {
                "title": "Hermes fixture workflow",
                "children": [
                    {"title": "Pass first review", "context": "fixture one", "definition_of_done": "pass"},
                    {"title": "Pass correction one", "context": "fixture two", "definition_of_done": "pass"},
                    {"title": "Pass correction two", "context": "fixture three", "definition_of_done": "pass"},
                ],
            }
            queue_tool = backend._load_queue_tool()
            worker_calls = []
            review_calls = []
            pass_at = {"Pass first review": 1, "Pass correction one": 2, "Pass correction two": 3}

            def worker(owner, prompt, item, attempt=1):
                worker_calls.append((owner, item["title"], attempt))
                return {
                    "success": True, "output": "PASS\nFiles touched: None\nValidation: fixture passed\nBlockers: None",
                    "stdout": "PASS", "stderr": "", "returncode": 0,
                    "token_usage": {"session_id": f"codex-{item['step_index']}-{attempt}"},
                    "token_usage_text": f"Token usage: Codex fixture {attempt}",
                }

            def review(item, owner, attempt, worker_result):
                review_calls.append((item["title"], attempt))
                passing = attempt >= pass_at[item["title"]]
                return {
                    "success": True, "output": "PASS" if passing else f"REVISE: correction {attempt}",
                    "stdout": "", "stderr": "", "returncode": 0,
                    "token_usage": {"session_id": f"hermes-{item['step_index']}-{attempt}"},
                    "token_usage_text": f"Token usage: Hermes fixture {attempt}",
                }

            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_load_queue_tool", return_value=queue_tool), \
                 patch.object(queue_tool, "finalize_done", return_value={}), \
                 patch.object(backend, "_queue_run_worker", side_effect=worker), \
                 patch.object(backend, "_queue_run_hermes_review", side_effect=review), \
                 patch.object(backend, "_notify_queue_running", return_value=None), \
                 patch.object(backend, "_notify_queue_completion", return_value=None):
                parent, children = backend._create_hermes_orchestration_items(
                    backend.TaskRun(task="give this to Codex, review it and send it back if needed", source="local_fixture"),
                    plan,
                    "fixture-orchestration-pass",
                )
                results = [backend.run_queue_item(child["id"]) for child in children]
                final_parent = backend._queue_find_item(parent["id"])
                final_children = [backend._queue_find_item(child["id"]) for child in children]
                events_path = root / backend.aos_orchestration.EVENTS_PATH
                events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual([result["attempts_used"] for result in results], [1, 2, 3])
        self.assertTrue(all(result["success"] for result in results))
        self.assertTrue(all(result["outer_coordinator"] == "hermes" for result in results))
        self.assertTrue(all(owner == "codex" for owner, _, _ in worker_calls))
        self.assertEqual([row["status"] for row in final_children], ["done", "done", "done"])
        self.assertEqual(final_parent["status"], "done")
        self.assertEqual(sum(event.get("event") == "hermes_orchestration_completed" for event in events), 1)
        self.assertEqual(sum(event.get("event") == "hermes_review_escalated_to_liam" for event in events), 0)
        self.assertEqual(len(worker_calls), 6)
        self.assertEqual(len(review_calls), 6)

    def test_hermes_orchestration_third_failed_review_escalates_once_without_fourth_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [])
            self.write_queue_templates(root)
            self.write_queue_references(root)
            plan = {"title": "Failure fixture", "children": [{
                "title": "Fail all reviews", "context": "fixture", "definition_of_done": "pass review",
            }]}
            queue_tool = backend._load_queue_tool()
            worker_calls = []

            def worker(owner, prompt, item, attempt=1):
                worker_calls.append(attempt)
                return {
                    "success": True, "output": "PASS\nFiles touched: None\nValidation: fixture\nBlockers: None",
                    "stdout": "", "stderr": "", "returncode": 0,
                    "token_usage": {"session_id": f"codex-fail-{attempt}"},
                    "token_usage_text": "Token usage: fixture",
                }

            review = lambda item, owner, attempt, worker_result: {
                "success": True, "output": f"REVISE: failed review {attempt}", "stdout": "", "stderr": "", "returncode": 0,
                "token_usage": {"session_id": f"hermes-fail-{attempt}"}, "token_usage_text": "Token usage: fixture",
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_load_queue_tool", return_value=queue_tool), \
                 patch.object(queue_tool, "finalize_done", return_value={}), \
                 patch.object(backend, "_queue_run_worker", side_effect=worker), \
                 patch.object(backend, "_queue_run_hermes_review", side_effect=review), \
                 patch.object(backend, "_notify_queue_running", return_value=None), \
                 patch.object(backend, "_notify_queue_completion", return_value=None):
                parent, children = backend._create_hermes_orchestration_items(
                    backend.TaskRun(task="give this to Codex and review it", source="local_fixture"),
                    plan,
                    "fixture-orchestration-fail",
                )
                result = backend.run_queue_item(children[0]["id"])
                with self.assertRaises(backend.HTTPException) as fourth:
                    backend.run_queue_item(children[0]["id"])
                final_parent = backend._queue_find_item(parent["id"])
                events_path = root / backend.aos_orchestration.EVENTS_PATH
                events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(result["attempts_used"], 3)
        self.assertEqual(worker_calls, [1, 2, 3])
        self.assertEqual(fourth.exception.status_code, 409)
        self.assertEqual(final_parent["status"], "human_review")
        escalations = [event for event in events if event.get("event") == "hermes_review_escalated_to_liam"]
        self.assertEqual(len(escalations), 1)
        self.assertFalse(escalations[0]["fourth_attempt_allowed"])

    def test_queue_creation_failure_is_truthful_and_starts_no_agent(self):
        with patch.object(backend, "_create_async_dispatch_item", side_effect=OSError("fixture queue unavailable")), \
             patch.object(backend, "_run_wsl") as run:
            with self.assertRaises(backend.HTTPException) as raised:
                backend.wsl_hermes(backend.TaskRun(task="Give this task to Codex: assess the files and repair the implementation"))
        run.assert_not_called()
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail["state"], "queue_creation_failed")
        self.assertFalse(raised.exception.detail["accepted"])

    def test_runner_unavailable_ack_leaves_item_truthfully_queued(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_runner_status", return_value={"available": False, "state": "unavailable", "pid": None}), \
                 patch.object(backend.subprocess, "Popen", side_effect=OSError("runner unavailable")):
                result = backend.wsl_hermes(backend.TaskRun(task="Give this task to Codex: build and validate the local fixture"))
                item = backend._queue_find_item(result["work_item_id"])
        self.assertFalse(result["runner_available"])
        self.assertFalse(result["runner_accepted"])
        self.assertIn("runner unavailable", result["output"])
        self.assertEqual(item["status"], "agent_todo")

    def test_stopped_recurring_runner_accepts_item_through_same_runner_one_shot_mode(self):
        process = types.SimpleNamespace(pid=456)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_runner_status", return_value={"available": False, "state": "unavailable", "pid": None}), \
                 patch.object(backend.subprocess, "Popen", return_value=process) as popen:
                result = backend.wsl_hermes(backend.TaskRun(task="Give this task to Codex: assess and repair the repository files"))
        self.assertTrue(result["runner_accepted"])
        self.assertEqual(result["runner_mode"], "one_shot")
        self.assertEqual(result["runner_state"], "accepted")
        command = popen.call_args.args[0]
        self.assertIn("aos-orchestration-runner.py", command[1])
        self.assertEqual(command[-2:], ["--dispatch-item", result["work_item_id"]])

    def test_local_fixture_source_never_enters_telegram_notification_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            body = backend.TaskRun(
                task="Codex: build and validate a harmless local fixture",
                source="local_fixture",
                delivery_id="fixture-1",
            )
            send = Mock()
            with patch.object(backend, "BASE_DIR", root):
                item, created, _, _ = backend._create_async_dispatch_item(body)
                running = backend._notify_queue_running(item["id"], send_telegram=send)
                completion = backend._notify_queue_completion(
                    item["id"], "blocked", "queue/receipts/missing.md", send_telegram=send,
                )

        self.assertTrue(created)
        self.assertEqual(item["source"], "local_fixture")
        self.assertNotIn("telegram", item["tags"])
        self.assertIsNone(running)
        self.assertIsNone(completion)
        send.assert_not_called()

    def test_unavailable_all_zero_token_block_is_not_counted_as_exact_zero(self):
        unavailable = {
            "token_usage": {
                "orchestrator": {"input": 0, "output": 0},
                "subagents": [],
                "workbenches": [],
                "totals": {"input": 0, "output": 0},
                "unavailable": ["workbench session totals"],
            }
        }
        known_partial = {
            "token_usage": {
                "orchestrator": {"input": 12, "output": 3},
                "subagents": [],
                "workbenches": [],
                "totals": {"input": 12, "output": 3},
                "unavailable": ["workbench session totals"],
            }
        }
        self.assertEqual((None, "unavailable"), backend._ledger_tokens_basis(unavailable))
        self.assertEqual((15, "exact"), backend._ledger_tokens_basis(known_partial))

    def test_telegram_status_preserves_contract_without_inspecting_protected_runtime(self):
        result = backend.telegram_connector_status()
        expected = {
            "status", "running", "bridge_file", "env_file", "allowed_chats",
            "pilot_report_file", "pilot_report_count", "operator_chat_configured", "pilot_id",
        }
        self.assertTrue(expected.issubset(result))
        self.assertEqual("not_checked", result["status"])
        self.assertEqual("unknown", result["running"])

    RUN_RESULT = {"success": True, "output": "PASS", "stdout": "PASS", "stderr": "", "returncode": 0}

    def route(self, task):
        with patch.object(backend, "_run_wsl", return_value=self.RUN_RESULT) as run, \
             patch.object(backend, "_log_token_usage"):
            result = backend.wsl_hermes(backend.TaskRun(task=task))
        return run.call_args.args[0], result

    def test_dashboard_http_mutation_is_rejected_before_endpoint_dispatch(self):
        request = types.SimpleNamespace(method="POST")
        dispatched = []

        async def call_next(_request):
            dispatched.append(True)
            return {"unexpected": True}

        with patch.object(backend, "_require_authority", side_effect=backend.AuthorityError("unsupported root")):
            response = asyncio.run(backend.linux_authority_boundary(request, call_next))
        self.assertEqual(503, response.status_code)
        self.assertEqual([], dispatched)

    def test_dashboard_http_read_is_not_forced_to_mutate_or_initialize_state(self):
        request = types.SimpleNamespace(method="GET")

        async def call_next(_request):
            return {"success": True}

        with patch.object(backend, "_require_authority") as authority:
            response = asyncio.run(backend.linux_authority_boundary(request, call_next))
        authority.assert_not_called()
        self.assertEqual({"success": True}, response)

    def route_with_prompt_file(self, task):
        seen = {}

        def capture(command, timeout=60):
            seen["command"] = command
            match = re.search(r"(?:--prompt-file\s+|<)(?P<quote>['\"]?)(?P<path>[^'\")]+)(?P=quote)", command)
            if match:
                prompt_path = Path(match.group("path"))
                seen["prompt"] = prompt_path.read_text(encoding="utf-8")
                seen["prompt_exists_during_run"] = prompt_path.exists()
            return self.RUN_RESULT

        with patch.object(backend, "_run_wsl", side_effect=capture), \
             patch.object(backend, "_log_token_usage"):
            result = backend.wsl_hermes(backend.TaskRun(task=task))
        seen["prompt_exists_after_run"] = Path(match.group("path")).exists() if (match := re.search(r"(?:--prompt-file\s+|<)(?P<quote>['\"]?)(?P<path>[^'\")]+)(?P=quote)", seen["command"])) else None
        return seen, result

    def write_queue_items(self, root, items):
        queue = root / "queue"
        queue.mkdir(parents=True, exist_ok=True)
        (queue / "work_items.jsonl").write_text(
            "".join(json.dumps(item, sort_keys=True) + "\n" for item in items),
            encoding="utf-8",
        )

    def route_metadata_fixture(self, lane="hermes"):
        return {
            "route_config_version": "fixture",
            "lane": lane,
            "profile_requested": "default",
            "profile_used": "default",
            "profile": "default",
            "profile_fallback_reason": "fixture route",
            "provider_requested": "configured externally",
            "provider_used": "default",
            "provider_confirmed": "unavailable from current CLI output",
            "model_requested": "configured externally",
            "model_used": "default",
            "model_confirmed": "unavailable from current CLI output",
            "explicit_model_provider_route": False,
            "escalation_profile": "",
            "escalation_rule": "fixture escalation rule",
            "route_policy": "fixture",
        }

    def test_hermes_ui_status_reports_reachable_only_when_endpoint_answers(self):
        launcher = {"success": True, "stdout": "state=installed_stopped\nversion=Hermes Agent v0.18.0\nurl=http://127.0.0.1:8081/", "output": "", "returncode": 0}
        with patch.object(backend, "_http_endpoint_headers", return_value={"success": False, "headers": {}, "error": "connection refused"}), \
             patch.object(backend, "_run_agentic_os_clean_bash", return_value=launcher):
            stopped = backend.hermes_ui_status()

        self.assertEqual(stopped["state"], "installed_stopped")
        self.assertFalse(stopped["reachable"])
        self.assertFalse(stopped["http_reachable"])
        self.assertTrue(stopped["supported"])
        self.assertEqual(stopped["url"], "http://127.0.0.1:8081")
        self.assertEqual(stopped["root"], str(backend.BASE_DIR))
        self.assertNotIn("wsl", stopped["launch_command"])
        self.assertIn(str(backend.BASE_DIR), stopped["launch_command"])
        self.assertIn("bash tools/aos-hermes-dashboard.sh start", stopped["launch_command"])

        with patch.object(backend, "_http_endpoint_headers", return_value={"success": True, "headers": {}, "status_code": 200, "final_url": "http://127.0.0.1:8081/"}), \
             patch.object(backend, "_run_agentic_os_clean_bash", return_value=launcher):
            reachable = backend.hermes_ui_status()

        self.assertEqual(reachable["state"], "running_embedded")
        self.assertTrue(reachable["reachable"])
        self.assertTrue(reachable["http_reachable"])
        self.assertTrue(reachable["embeddable"])
        self.assertEqual(reachable["open_url"], "http://127.0.0.1:8081")

    def test_hermes_ui_status_reports_unsupported_without_fake_url(self):
        launcher = {"success": True, "stdout": "state=unsupported\nreason=hermes dashboard command is unavailable\nurl=http://127.0.0.1:8081/", "output": "", "returncode": 0}
        with patch.object(backend, "_http_endpoint_headers", return_value={"success": False, "headers": {}, "error": "connection refused"}), \
             patch.object(backend, "_run_agentic_os_clean_bash", return_value=launcher):
            status = backend.hermes_ui_status()

        self.assertEqual(status["state"], "unsupported")
        self.assertFalse(status["supported"])
        self.assertFalse(status["reachable"])
        self.assertEqual(status["open_url"], "")

    def test_hermes_ui_launch_does_not_duplicate_reachable_process(self):
        reachable = {
            "state": "reachable",
            "reachable": True,
            "http_reachable": True,
            "supported": True,
            "url": "http://127.0.0.1:8081",
        }
        with patch.object(backend, "_hermes_ui_status", return_value=reachable), \
             patch.object(backend, "_run_agentic_os_clean_bash") as run:
            result = backend.hermes_ui_launch()

        run.assert_not_called()
        self.assertFalse(result["launched"])
        self.assertTrue(result["reachable"])
        self.assertTrue(result["already_running"])

    def test_hermes_launcher_uses_one_current_install_dist_and_skip_build_contract(self):
        launcher = backend.HERMES_DASHBOARD_LAUNCHER.read_text(encoding="utf-8")
        self.assertIn('HERMES_AGENT_ROOT="${HERMES_AGENT_ROOT:-${HOME}/.hermes/hermes-agent}"', launcher)
        self.assertIn('HERMES_WEB_DIST="$WEB_DIST"', launcher)
        self.assertIn("--skip-build", launcher)
        self.assertIn("npm run typecheck --workspace web", launcher)
        self.assertNotIn("nohup npm", launcher)
        self.assertIn("dashboard_pid", launcher)

    def test_hermes_ui_launch_uses_current_linux_bash(self):
        with patch.object(backend.subprocess, "run") as run:
            run.return_value = types.SimpleNamespace(stdout="ok", stderr="", returncode=0)
            backend._run_wsl("cd /tmp && bash tools/aos-hermes-dashboard.sh start", timeout=20)

        args = run.call_args.args[0]
        self.assertEqual(args[:2], ["bash", "-lc"])
        self.assertNotIn("wsl", args)
        self.assertNotEqual(args[0], str(backend.HERMES_DASHBOARD_LAUNCHER))

    def test_hermes_ui_launch_does_not_execute_script_natively_on_windows(self):
        with patch.object(backend.os, "name", "nt"), \
             patch.object(backend, "_run_wsl", return_value=self.RUN_RESULT) as run:
            backend._run_agentic_os_clean_bash(backend._hermes_dashboard_launcher_command("start"), timeout=20)

        command = run.call_args.args[0]
        self.assertIn("bash tools/aos-hermes-dashboard.sh start", backend._hermes_dashboard_operator_command("start"))
        self.assertIn("aos-hermes-dashboard.sh", command)

    def test_hermes_ui_launch_reports_failure_when_readiness_never_arrives(self):
        before = {"supported": True, "http_reachable": False, "reachable": False, "url": "http://127.0.0.1:8081"}
        after = {**before, "state": "installed_stopped"}
        start = {"success": True, "stdout": "state=starting\nurl=http://127.0.0.1:8081/", "stderr": "", "returncode": 0}
        with patch.object(backend, "_hermes_ui_status", side_effect=[before, after]), \
             patch.object(backend, "_run_agentic_os_clean_bash", return_value=start), \
             patch.object(backend, "_poll_http_endpoint", return_value=False):
            result = backend.hermes_ui_launch()

        self.assertFalse(result["success"])
        self.assertTrue(result["launched"])
        self.assertIn("did not become reachable", result["message"])

    def test_hermes_ui_launch_reports_success_only_after_http_readiness(self):
        before = {"supported": True, "http_reachable": False, "reachable": False, "url": "http://127.0.0.1:8081"}
        after = {"supported": True, "http_reachable": True, "reachable": True, "url": "http://127.0.0.1:8081", "state": "running_embedded"}
        start = {"success": True, "stdout": "state=reachable\nurl=http://127.0.0.1:8081/", "stderr": "", "returncode": 0}
        with patch.object(backend, "_hermes_ui_status", side_effect=[before, after]), \
             patch.object(backend, "_run_agentic_os_clean_bash", return_value=start), \
             patch.object(backend, "_poll_http_endpoint", return_value=True):
            result = backend.hermes_ui_launch()

        self.assertTrue(result["success"])
        self.assertTrue(result["http_reachable"])
        self.assertEqual(result["message"], "Hermes dashboard reachable.")

    def test_hermes_ui_status_surfaces_x_frame_options_denial(self):
        launcher = {"success": True, "stdout": "state=reachable\nversion=Hermes Agent v0.18.0", "output": "", "returncode": 0}
        headers = {"success": True, "headers": {"x-frame-options": "DENY"}, "status_code": 200, "final_url": "http://127.0.0.1:8081/"}
        with patch.object(backend, "_http_endpoint_headers", return_value=headers), \
             patch.object(backend, "_run_agentic_os_clean_bash", return_value=launcher):
            status = backend.hermes_ui_status()

        self.assertTrue(status["http_reachable"])
        self.assertFalse(status["embeddable"])
        self.assertEqual(status["state"], "running_window_only")
        self.assertEqual(status["blocking_header"], "X-Frame-Options: DENY")

    def test_hermes_ui_status_surfaces_csp_frame_ancestors_denial(self):
        launcher = {"success": True, "stdout": "state=reachable\nversion=Hermes Agent v0.18.0", "output": "", "returncode": 0}
        headers = {
            "success": True,
            "headers": {"content-security-policy": "default-src 'self'; frame-ancestors 'none'"},
            "status_code": 200,
            "final_url": "http://127.0.0.1:8081/",
        }
        with patch.object(backend, "_http_endpoint_headers", return_value=headers), \
             patch.object(backend, "_run_agentic_os_clean_bash", return_value=launcher):
            status = backend.hermes_ui_status()

        self.assertFalse(status["embeddable"])
        self.assertIn("Content-Security-Policy: frame-ancestors", status["blocking_header"])

    def test_hermes_ui_status_allows_permissive_frame_headers(self):
        launcher = {"success": True, "stdout": "state=reachable\nversion=Hermes Agent v0.18.0", "output": "", "returncode": 0}
        headers = {"success": True, "headers": {"content-security-policy": "default-src 'self'"}, "status_code": 200, "final_url": "http://127.0.0.1:8081/"}
        with patch.object(backend, "_http_endpoint_headers", return_value=headers), \
             patch.object(backend, "_run_agentic_os_clean_bash", return_value=launcher):
            status = backend.hermes_ui_status()

        self.assertTrue(status["embeddable"])
        self.assertEqual(status["blocking_header"], "")

    def write_queue_templates(self, root):
        templates = root / "queue" / "templates"
        templates.mkdir(parents=True, exist_ok=True)
        source_templates = MAIN.parents[2] / "queue" / "templates"
        for name in ("codex_task.prompt.md", "claude_task.prompt.md", "department_task.prompt.md", "receipt.prompt.md"):
            (templates / name).write_text((source_templates / name).read_text(encoding="utf-8"), encoding="utf-8")

    def write_agent_cards(self, root):
        agents = root / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        source_agents = MAIN.parents[2] / "agents"
        for name in ("revenue.card.md", "marketing.card.md", "delivery.card.md", "operations.card.md"):
            (agents / name).write_text((source_agents / name).read_text(encoding="utf-8"), encoding="utf-8")

    def write_queue_references(self, root):
        queue = root / "queue"
        context = root / "context"
        queue.mkdir(parents=True, exist_ok=True)
        context.mkdir(parents=True, exist_ok=True)
        source_root = MAIN.parents[2]
        (queue / "agent_registry.json").write_text((source_root / "queue" / "agent_registry.json").read_text(encoding="utf-8"), encoding="utf-8")
        (queue / "model_routes.json").write_text((source_root / "queue" / "model_routes.json").read_text(encoding="utf-8"), encoding="utf-8")
        (queue / "lane_profiles.json").write_text((source_root / "queue" / "lane_profiles.json").read_text(encoding="utf-8"), encoding="utf-8")
        (context / "ACCESS_MODEL.md").write_text((source_root / "context" / "ACCESS_MODEL.md").read_text(encoding="utf-8"), encoding="utf-8")

    def write_model_routes(self, root, routes=None):
        queue = root / "queue"
        queue.mkdir(parents=True, exist_ok=True)
        data = routes or json.loads((MAIN.parents[2] / "queue" / "model_routes.json").read_text(encoding="utf-8"))
        (queue / "model_routes.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    def write_lane_profiles(self, root, lanes=None):
        queue = root / "queue"
        queue.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "unit",
            "fallback_profile": "default",
            "lanes": lanes or {
                "revenue": {
                    "lane": "revenue",
                    "profile_requested": "aos-revenue",
                    "fallback_profile": "default",
                    "enabled_only_when_model_configured": True,
                    "purpose": "unit revenue",
                    "escalation_note": "unit escalation",
                }
            },
        }
        (queue / "lane_profiles.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    def sample_queue_items(self):
        return [
            {
                "id": "AOS-2026-0001",
                "title": "Triage inbox lead",
                "status": "inbox",
                "owner": "unassigned",
                "priority": 1,
                "created_at": "2026-07-05T10:00:00Z",
            },
            {
                "id": "AOS-2026-0002",
                "title": "Codex route test",
                "status": "agent_todo",
                "owner": "codex",
                "priority": 9,
                "created_at": "2026-07-05T10:01:00Z",
            },
            {
                "id": "AOS-2026-0003",
                "title": "Blocked connector decision",
                "status": "blocked",
                "owner": "hermes",
                "priority": 4,
                "created_at": "2026-07-05T10:02:00Z",
            },
            {
                "id": "AOS-2026-0004",
                "title": "Finished old task",
                "status": "done",
                "owner": "claude",
                "priority": 99,
                "created_at": "2026-07-05T10:03:00Z",
            },
        ]

    def approval_item(self, item_id, status, *, title="Repair local routing", context="Local code and tests only"):
        return {
            "id": item_id,
            "title": title,
            "status": status,
            "owner_type": "agent",
            "owner": "codex",
            "priority": 5,
            "requested_by": "Liam",
            "source": "telegram",
            "tags": ["async_dispatch", "telegram"],
            "context": context,
            "client_scope": "global",
            "context_classification": "technical_only",
            "brain_context_status": "not_applicable",
            "sources": [],
            "allowed_actions": ["local_read", "local_edit", "local_test"],
            "stop_conditions": ["external_send", "destructive_action_outside_scope"],
            "definition_of_done": "Local repair validated with a durable receipt.",
            "claim": {"claimed_by": None, "claimed_at": None},
            "receipts": [],
            "dispatch": {
                "reply_to": "fixture-chat",
                "delivery_id": "original-task",
                "idempotency_key": f"fixture:{item_id}",
            },
            "created_at": "2026-07-17T10:00:00Z",
            "updated_at": "2026-07-17T10:00:00Z",
        }

    def test_telegram_approval_parser_accepts_bounded_phrase_family(self):
        for phrase in ("I approve", "approved", "accept", "continue", "resume", "go ahead", "yes, proceed"):
            with self.subTest(phrase=phrase):
                self.assertIsNotNone(backend._telegram_approval_intent(phrase))
        self.assertIsNone(backend._telegram_approval_intent("acceptance criteria need editing"))

    def test_needs_input_approval_resumes_same_item_and_replay_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = self.approval_item("AOS-2026-0200", "needs_input")
            self.write_queue_items(root, [item])
            runner = {"available": True, "accepted": True, "state": "accepted", "pid": 41, "mode": "one_shot"}
            body = backend.TaskRun(task="I approve", delivery_id="approval-event-1", reply_to="fixture-chat")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_accept_async_queue_runner", return_value=runner) as dispatch, \
                 patch.object(backend, "_create_async_dispatch_item") as create:
                first = backend.wsl_hermes(body)
                replay = backend.wsl_hermes(body)
                rows = backend._read_queue_items()

        create.assert_not_called()
        dispatch.assert_called_once()
        self.assertEqual(first["work_item_id"], item["id"])
        self.assertEqual(first["state"], "resumed")
        self.assertFalse(first["created"])
        self.assertTrue(replay["duplicate"])
        self.assertEqual(replay["state"], "approval-replay")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "agent_todo")
        self.assertEqual(len(rows[0]["receipts"]), 1)

    def test_pending_approval_effect_reconciles_after_transition_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = self.approval_item("AOS-2026-0205", "agent_todo")
            body = backend.TaskRun(task="resume", delivery_id="approval-event-pending", reply_to="fixture-chat")
            event_key = backend._telegram_approval_event_key(body, backend._telegram_approval_intent(body.task))
            item["approval_effects"] = {
                event_key: {"event": "telegram_approval", "status": "pending", "action": "resume"},
            }
            self.write_queue_items(root, [item])
            runner = {"available": True, "accepted": True, "state": "accepted", "pid": 42, "mode": "one_shot"}
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_accept_async_queue_runner", return_value=runner) as dispatch, \
                 patch.object(backend, "_create_async_dispatch_item") as create:
                result = backend.wsl_hermes(body)
                rows = backend._read_queue_items()

        create.assert_not_called()
        dispatch.assert_called_once()
        self.assertEqual(result["work_item_id"], item["id"])
        self.assertEqual(rows[0]["approval_effects"][event_key]["status"], "applied")
        self.assertEqual(len(rows), 1)

    def test_human_review_accept_closes_same_item_without_second_telegram_or_replay_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = self.approval_item("AOS-2026-0201", "human_review")
            self.write_queue_items(root, [item])
            body = backend.TaskRun(task="accept", delivery_id="approval-event-2", reply_to="fixture-chat")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend.aos_orchestration, "tick", return_value={"advanced": []}), \
                 patch.object(backend, "_telegram_reply_on_close") as telegram, \
                 patch.object(backend, "_create_async_dispatch_item") as create:
                first = backend.wsl_hermes(body)
                replay = backend.wsl_hermes(body)
                rows = backend._read_queue_items()
                receipts = list((root / "queue" / "receipts").glob(f"{item['id']}-*.md"))

        create.assert_not_called()
        telegram.assert_not_called()
        self.assertEqual(first["work_item_id"], item["id"])
        self.assertEqual(first["status"], "done")
        self.assertEqual(replay["state"], "approval-replay")
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(len(rows[0]["receipts"]), 1)

    def test_approval_with_two_pending_targets_fails_closed_with_candidate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = [
                self.approval_item("AOS-2026-0202", "needs_input"),
                self.approval_item("AOS-2026-0203", "human_review"),
            ]
            self.write_queue_items(root, items)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_create_async_dispatch_item") as create, \
                 patch.object(backend, "_accept_async_queue_runner") as dispatch:
                result = backend.wsl_hermes(backend.TaskRun(
                    task="go ahead", delivery_id="approval-event-3", reply_to="fixture-chat",
                ))
                rows = backend._read_queue_items()

        create.assert_not_called()
        dispatch.assert_not_called()
        self.assertEqual(result["state"], "approval-target-ambiguous")
        self.assertEqual(result["candidate_ids"], [
            "AOS-2026-0202 — Repair local routing",
            "AOS-2026-0203 — Repair local routing",
        ])
        self.assertEqual(rows, items)

    def test_approval_with_no_pending_target_does_not_create_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_create_async_dispatch_item") as create, \
                 patch.object(backend, "_accept_async_queue_runner") as dispatch:
                result = backend.wsl_hermes(backend.TaskRun(
                    task="yes, proceed", delivery_id="approval-event-4", reply_to="fixture-chat",
                ))
                rows = backend._read_queue_items()

        create.assert_not_called()
        dispatch.assert_not_called()
        self.assertEqual(result["state"], "approval-target-missing")
        self.assertEqual(rows, [])

    def test_late_explicit_approval_returns_existing_completed_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = self.approval_item("AOS-2026-0204", "done")
            self.write_queue_items(root, [item])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_create_async_dispatch_item") as create, \
                 patch.object(backend, "_accept_async_queue_runner") as dispatch:
                result = backend.wsl_hermes(backend.TaskRun(
                    task=f"approved {item['id']}", delivery_id="approval-event-5", reply_to="fixture-chat",
                ))
                rows = backend._read_queue_items()

        create.assert_not_called()
        dispatch.assert_not_called()
        self.assertEqual(result["state"], "already-completed")
        self.assertEqual(result["work_item_id"], item["id"])
        self.assertEqual(len(rows), 1)

    def test_generic_approval_cannot_authorize_external_or_destructive_action(self):
        cases = (
            ("Send the existing Gmail draft to the client", "Send email after review"),
            ("Deploy the release and git push", "Publish approved release"),
        )
        for index, (title, context) in enumerate(cases, start=1):
            with self.subTest(title=title), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                item = self.approval_item(f"AOS-2026-021{index}", "needs_input", title=title, context=context)
                self.write_queue_items(root, [item])
                with patch.object(backend, "BASE_DIR", root), \
                     patch.object(backend, "_create_async_dispatch_item") as create, \
                     patch.object(backend, "_accept_async_queue_runner") as dispatch:
                    result = backend.wsl_hermes(backend.TaskRun(
                        task=f"I approve {item['id']}", delivery_id=f"external-{index}", reply_to="fixture-chat",
                    ))
                    rows = backend._read_queue_items()
            create.assert_not_called()
            dispatch.assert_not_called()
            self.assertEqual(result["state"], "explicit-action-approval-required")
            self.assertEqual(rows[0]["status"], "needs_input")
            self.assertEqual(len(rows), 1)

    def test_backup_status_no_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt_path = Path(tmp) / "queue" / "receipts" / "backups.jsonl"
            with patch.object(backend, "BACKUP_RECEIPTS_FILE", receipt_path):
                result = backend._backup_status(now=datetime.datetime(2026, 7, 9, 12, 0, tzinfo=datetime.timezone.utc))
        self.assertEqual(result["state"], "no_receipts")
        self.assertFalse(result["needs_attention"])
        self.assertEqual(result["token_usage_text"], "Token usage: no agent invocation")

    def test_backups_status_endpoint_returns_no_agent_invocation(self):
        with patch.object(backend, "_backup_status", return_value={"state": "no_receipts", "token_usage_text": "Token usage: no agent invocation"}) as status:
            result = backend.backups_status()
        status.assert_called_once()
        self.assertEqual(result["state"], "no_receipts")
        self.assertEqual(result["token_usage_text"], "Token usage: no agent invocation")

    def test_backup_status_fresh_success(self):
        now = datetime.datetime(2026, 7, 9, 12, 0, tzinfo=datetime.timezone.utc)
        receipts = [{"ts": "2026-07-09T11:00:00Z", "status": "success", "target": "D:\\TTROS_Backups", "token_usage_text": "Token usage: no agent invocation"}]
        result = backend._backup_status(now=now, receipts=receipts)
        self.assertEqual(result["state"], "fresh_success")
        self.assertFalse(result["needs_attention"])
        self.assertEqual(result["latest"]["target"], "D:\\TTROS_Backups")
        self.assertEqual(result["token_usage_text"], "Token usage: no agent invocation")

    def test_backup_status_stale_success(self):
        now = datetime.datetime(2026, 7, 9, 12, 0, tzinfo=datetime.timezone.utc)
        receipts = [{"ts": "2026-07-06T11:00:00Z", "status": "success", "snapshot_path": "D:\\TTROS_Backups\\2026-07-06_1100"}]
        result = backend._backup_status(now=now, receipts=receipts)
        self.assertEqual(result["state"], "stale")
        self.assertTrue(result["needs_attention"])

    def test_backup_status_latest_fail(self):
        now = datetime.datetime(2026, 7, 9, 12, 0, tzinfo=datetime.timezone.utc)
        receipts = [
            {"ts": "2026-07-09T10:00:00Z", "status": "success"},
            {"ts": "2026-07-09T11:00:00Z", "status": "fail", "errors": ["Target drive is absent"]},
        ]
        result = backend._backup_status(now=now, receipts=receipts)
        self.assertEqual(result["state"], "failed")
        self.assertTrue(result["needs_attention"])
        self.assertEqual(result["latest"]["errors"], ["Target drive is absent"])

    def test_intelligent_fallback_uses_hermes_while_explicit_workbenches_queue_directly(self):
        cases = (
            ("quick search for local micro cement plasterers", "hermes"),
            ("get Hermes to quick search for local micro cement plasterers", "hermes"),
            ("get Codex to inspect dashboard files", "codex"),
            ("get Claude to polish the dashboard UI", "claude"),
            ("quick search, do not use Codex", "hermes"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_runner_status", return_value={"available": True, "state": "running", "pid": 1}), \
                 patch.object(backend, "_run_hermes_message", return_value={"success": True, "reply": "Hermes answer"}) as hermes, \
                 patch.object(backend, "_hermes_coordinator_closeout", side_effect=lambda result, task, route: {
                     "success": True, "selected_route": "hermes_coordinator", "output": result["reply"],
                 }):
                results = [backend.wsl_hermes(backend.TaskRun(task=task)) for task, _ in cases]
                rows = backend._read_queue_items()
        self.assertEqual(hermes.call_count, 3)
        self.assertEqual(
            [row["selected_route"] for row in results],
            ["hermes_coordinator", "hermes_coordinator", "direct_codex", "direct_claude", "hermes_coordinator"],
        )
        self.assertEqual([row["owner"] for row in rows], ["codex", "claude"])

    def test_adversarial_prompt_is_preserved_as_queue_context_not_shell_text(self):
        task = "\n".join((
            "Give this task to Codex:",
            "Markdown with `backticks` and $(touch /tmp/bad)",
            "Use $VARS and \"quotes\" and 'single quotes'",
            r"Windows path: C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live",
            "```bash",
            "echo should not run",
            "```",
            "x" * 5000,
        ))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_runner_status", return_value={"available": True, "state": "running", "pid": 1}), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.wsl_hermes(backend.TaskRun(task=task))
                item = backend._queue_find_item(result["work_item_id"])
        run.assert_not_called()
        self.assertEqual(result["selected_route"], "direct_codex")
        self.assertEqual(item["context"], task)
        self.assertIn(r"C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live", item["sources"])

    def test_hermes_message_uses_wrapper_prompt_file_and_usage_file(self):
        seen = {}

        def capture(command, timeout=60):
            seen["command"] = command
            prompt_match = re.search(r"--prompt-file\s+(?P<quote>['\"]?)(?P<path>[^'\")]+)(?P=quote)", command)
            usage_match = re.search(r"--usage-file\s+(?P<quote>['\"]?)(?P<path>[^'\")]+)(?P=quote)", command)
            self.assertIsNotNone(prompt_match)
            self.assertIsNotNone(usage_match)
            prompt_path = Path(prompt_match.group("path"))
            usage_path = Path(usage_match.group("path"))
            seen["prompt"] = prompt_path.read_text(encoding="utf-8")
            seen["prompt_exists_during_run"] = prompt_path.exists()
            usage_path.write_text(
                json.dumps({
                    "input_tokens": 11,
                    "output_tokens": 3,
                    "total_tokens": 14,
                    "api_calls": 1,
                    "model": "gpt-5.5",
                    "provider": "openai-codex",
                    "completed": True,
                    "failed": False,
                }),
                encoding="utf-8",
            )
            seen["usage_path"] = usage_path
            return {"success": True, "output": "ALIVE", "stdout": "ALIVE", "stderr": "", "returncode": 0}

        task = "reply with the word ALIVE and do not expose $(bad)"
        with patch.object(backend, "_run_agentic_os_clean_bash", side_effect=capture), \
             patch.object(backend, "_log_token_usage"):
            result = backend.hermes_message(backend.HermesMessage(text=task))

        self.assertIn("aos-hermes-coordinator.sh", seen["command"])
        self.assertIn("--usage-file", seen["command"])
        self.assertIn("--prompt-file", seen["command"])
        self.assertNotIn("$(bad)", seen["command"])
        self.assertEqual(seen["prompt"], task)
        self.assertTrue(seen["prompt_exists_during_run"])
        self.assertFalse(seen["usage_path"].exists())
        self.assertEqual(result["reply"], "ALIVE")
        self.assertEqual(result["token_usage"]["total_tokens"], 14)
        self.assertIn("total 14", result["token_usage_text"])

    def test_simple_token_ledger_writes_one_entry_per_run_with_exact_or_unavailable_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "token_ledger.jsonl"
            with patch.object(backend, "ROOT_TOKEN_LEDGER_FILE", ledger):
                backend._append_simple_token_ledger(
                    "AOS-2026-0101",
                    "codex",
                    {"available": False},
                )
                backend._append_simple_token_ledger(
                    "AOS-2026-0102",
                    "codex",
                    {"available": True, "input_tokens": "7", "output_tokens": "5"},
                )
                backend._append_simple_token_ledger(
                    "AOS-2026-0103",
                    "codex",
                    {"available": True, "total_tokens": "1,205"},
                )

            rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["task_id"] for row in rows], ["AOS-2026-0101", "AOS-2026-0102", "AOS-2026-0103"])
            self.assertNotIn("tokens", rows[0])
            self.assertEqual([row.get("tokens") for row in rows], [None, 12, 1205])
            self.assertEqual([row["basis"] for row in rows], ["unavailable", "exact", "exact"])
            self.assertEqual(set(backend.USAGE_COUNTER_FIELDS), set(rows[0]).intersection(backend.USAGE_COUNTER_FIELDS))
            self.assertTrue(all(rows[0][key] == "unavailable from current CLI output" for key in backend.USAGE_COUNTER_FIELDS))

    def test_simple_token_ledger_does_not_estimate_from_missing_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "token_ledger.jsonl"
            with patch.object(backend, "ROOT_TOKEN_LEDGER_FILE", ledger):
                backend._append_simple_token_ledger(
                    "AOS-2026-0104",
                    "codex",
                    {"available": True},
                )
                backend._append_simple_token_ledger(
                    "AOS-2026-0105",
                    "codex",
                    {"available": True, "input_tokens": "7"},
                )
                backend._append_simple_token_ledger(
                    "AOS-2026-0106",
                    "hermes",
                    {"available": False, "no_agent_invocation": True},
                )

            rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(["AOS-2026-0104", "AOS-2026-0105"], [row["task_id"] for row in rows])
            self.assertTrue(all(row["basis"] == "unavailable" and "tokens" not in row for row in rows))

    def test_review_close_writes_receipt_and_resumes_linked_step_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent_id = "AOS-2026-0200"
            step1_id = "AOS-2026-0201"
            step2_id = "AOS-2026-0202"
            step3_id = "AOS-2026-0203"
            queue = root / "queue"
            receipts = queue / "receipts"
            results = root / "results" / "orchestration_acceptance" / parent_id
            receipts.mkdir(parents=True)
            results.mkdir(parents=True)
            source_pack = "results/orchestration_acceptance/AOS-2026-0200/01_source_pack.md"
            brief = "results/orchestration_acceptance/AOS-2026-0200/02_speed_to_lead_micro_brief.md"
            (root / source_pack).write_text("source pack", encoding="utf-8")
            (root / brief).write_text("approved brief", encoding="utf-8")
            (receipts / "step1.md").write_text(f"PASS\n- {source_pack}\nToken usage: no agent invocation\n", encoding="utf-8")
            (receipts / "step2.md").write_text(f"PASS\n- {brief}\nToken usage: unavailable from current CLI output\n", encoding="utf-8")
            self.write_queue_items(root, [
                {
                    "id": parent_id,
                    "title": "TTR Speed-to-Lead Micro-Brief Acceptance",
                    "status": "agent_todo",
                    "owner": "hermes",
                    "priority": 5,
                    "created_at": "2026-07-10T00:00:00Z",
                    "updated_at": "2026-07-10T00:00:00Z",
                    "tags": ["orchestration_acceptance"],
                    "receipts": [],
                },
                {
                    "id": step1_id,
                    "title": "Operations source pack",
                    "status": "done",
                    "owner": "operations",
                    "priority": 5,
                    "tags": ["orchestration_acceptance"],
                    "parent_id": parent_id,
                    "step_index": 1,
                    "depends_on": [],
                    "source_refs": [],
                    "created_at": "2026-07-10T00:00:00Z",
                    "updated_at": "2026-07-10T00:00:00Z",
                    "receipts": [{"path": "queue/receipts/step1.md", "created_at": "2026-07-10T00:00:00Z", "status": "done"}],
                },
                {
                    "id": step2_id,
                    "title": "Marketing micro brief",
                    "status": "human_review",
                    "owner": "marketing",
                    "priority": 5,
                    "parent_id": parent_id,
                    "step_index": 2,
                    "depends_on": [step1_id],
                    "source_refs": [source_pack],
                    "on_complete": "human_review",
                    "created_at": "2026-07-10T00:00:00Z",
                    "updated_at": "2026-07-10T00:00:00Z",
                    "receipts": [{"path": "queue/receipts/step2.md", "created_at": "2026-07-10T00:01:00Z", "status": "human_review"}],
                },
                {
                    "id": step3_id,
                    "title": "Delivery final package",
                    "status": "inbox",
                    "owner": "delivery",
                    "priority": 5,
                    "tags": ["orchestration_acceptance"],
                    "parent_id": parent_id,
                    "step_index": 3,
                    "depends_on": [step2_id],
                    "source_refs": [],
                    "workbench": "local",
                    "created_at": "2026-07-10T00:00:00Z",
                    "updated_at": "2026-07-10T00:00:00Z",
                    "receipts": [],
                },
            ])
            (queue / "notifications.json").write_text(json.dumps({"escalation": {"unanswered_minutes": 10}, "allowlist": {"telegram": []}}), encoding="utf-8")

            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "QUEUE_TOOL", MAIN.parents[2] / "tools" / "aos-queue.py"), \
                 patch.object(backend.latitude_telemetry, "trace"):
                summary = backend.queue_summary()
                self.assertEqual(summary["needsMeCount"], 1)
                self.assertEqual(summary["needsMeItems"][0]["id"], step2_id)

                result = backend.close_queue_item_review(
                    step2_id,
                    backend.QueueReviewClose(status="done", action="approve", review_note="Approved for final packaging."),
                )
                repeated_review = backend.close_queue_item_review(
                    step2_id,
                    backend.QueueReviewClose(status="done", action="approve", review_note="This should not replace the original note."),
                )
                repeat = backend.orchestration_tick()
                summary_after = backend.queue_summary()
                parent_detail = backend.queue_item(parent_id)["item"]
                reviewed_detail = backend.queue_item(step2_id)["item"]
                final_detail = backend.queue_item(step3_id)["item"]

            self.assertEqual(result["status"], "done")
            self.assertEqual(len(result["resume_tick"]["advanced"]), 2)
            self.assertEqual(result["parent_id"], parent_id)
            self.assertEqual(result["reviewed_item_id"], step2_id)
            self.assertEqual(result["final_item_id"], step3_id)
            self.assertEqual(result["chain_status"], "done")
            self.assertEqual(result["final_item_status"], "done")
            self.assertEqual(result["advanced_item_ids"], [step3_id])
            self.assertIn(f"results/orchestration_acceptance/{parent_id}/03_final_review_package.md", result["final_artifact_paths"])
            self.assertTrue(any(path.startswith(f"queue/receipts/{step3_id}-final-closeout-") for path in result["final_receipt_paths"]))
            self.assertEqual(repeated_review["resume_tick"]["advanced"], [])
            self.assertEqual(repeat["advanced"], [])
            rows = [json.loads(line) for line in (queue / "work_items.jsonl").read_text(encoding="utf-8").splitlines()]
            by_id = {row["id"]: row for row in rows}
            self.assertEqual(by_id[step3_id]["status"], "done")
            self.assertEqual(by_id[parent_id]["status"], "done")
            self.assertEqual(by_id[step3_id]["source_refs"].count(brief), 1)
            self.assertTrue(any("queue/receipts" in ref and step2_id in ref for ref in by_id[step3_id]["source_refs"]))
            self.assertTrue((results / "03_final_review_package.md").is_file())
            final_receipts = list(receipts.glob(f"{step3_id}-final-closeout-*.md"))
            self.assertEqual(len(final_receipts), 1)
            review_receipts = [path for path in receipts.glob(f"{step2_id}-*.md") if "final-closeout" not in path.name]
            self.assertEqual(len(review_receipts), 1)
            review_receipt = (root / result["receipt_path"]).read_text(encoding="utf-8")
            self.assertIn("Approved for final packaging.", review_receipt)
            self.assertNotIn("This should not replace the original note.", review_receipt)
            self.assertEqual(summary_after["needsMeCount"], 0)
            for detail in (parent_detail, reviewed_detail, final_detail):
                self.assertEqual(detail["final_result"]["parent_id"], parent_id)
                self.assertEqual(detail["final_result"]["reviewed_item_id"], step2_id)
                self.assertEqual(detail["final_result"]["final_item_id"], step3_id)
                self.assertEqual(detail["final_result"]["chain_status"], "done")
                self.assertEqual(detail["final_result"]["final_item_status"], "done")
                self.assertTrue(detail["final_result"]["final_artifacts"][0]["available"])
                self.assertTrue(detail["final_result"]["final_receipts"][0]["available"])

    def test_dashboard_queue_review_close_retries_live_partial_close_without_duplicate_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            receipts = queue / "receipts"
            results = root / "results" / "orchestration_acceptance" / "AOS-2026-0071"
            receipts.mkdir(parents=True)
            results.mkdir(parents=True)
            source_pack = "results/orchestration_acceptance/AOS-2026-0071/01_source_pack.md"
            brief = "results/orchestration_acceptance/AOS-2026-0071/02_speed_to_lead_micro_brief.md"
            review_receipt = "queue/receipts/AOS-2026-0073-20260710T192427Z.md"
            (root / source_pack).write_text("source pack", encoding="utf-8")
            (root / brief).write_text("approved brief", encoding="utf-8")
            (root / review_receipt).write_text(
                "PASS\n\nReview closeout:\n- Reviewed by: Liam\n- Status: done\n\nReview note:\nApproved for final packaging.\n",
                encoding="utf-8",
            )
            self.write_queue_items(root, [
                {
                    "id": "AOS-2026-0071",
                    "title": "TTR Speed-to-Lead Micro-Brief Acceptance",
                    "status": "agent_todo",
                    "owner": "hermes",
                    "priority": 8,
                    "tags": ["orchestration_acceptance", "post_wp12_acceptance", "final_ux_repair"],
                    "created_at": "2026-07-10T18:49:46Z",
                    "updated_at": "2026-07-10T18:49:46Z",
                    "receipts": [],
                },
                {
                    "id": "AOS-2026-0072",
                    "title": "Step 1 - Operations/local source pack",
                    "status": "done",
                    "owner": "operations",
                    "priority": 8,
                    "parent_id": "AOS-2026-0071",
                    "step_index": 1,
                    "depends_on": [],
                    "source_refs": [],
                    "created_at": "2026-07-10T18:49:46Z",
                    "updated_at": "2026-07-10T18:49:46Z",
                    "receipts": [{"path": "queue/receipts/AOS-2026-0072-source-pack.md", "created_at": "2026-07-10T18:49:46Z", "status": "done"}],
                },
                {
                    "id": "AOS-2026-0073",
                    "title": "Step 2 - Marketing worker draft",
                    "status": "done",
                    "owner": "marketing",
                    "priority": 8,
                    "parent_id": "AOS-2026-0071",
                    "step_index": 2,
                    "depends_on": ["AOS-2026-0072"],
                    "source_refs": [source_pack],
                    "on_complete": "human_review",
                    "created_at": "2026-07-10T18:49:46Z",
                    "updated_at": "2026-07-10T19:24:27Z",
                    "receipts": [
                        {"path": "queue/receipts/AOS-2026-0073-draft-human-review.md", "created_at": "2026-07-10T18:49:46Z", "status": "human_review"},
                        {"path": review_receipt, "created_at": "2026-07-10T19:24:27Z", "status": "done"},
                    ],
                },
                {
                    "id": "AOS-2026-0074",
                    "title": "Step 3 - Delivery/local final package",
                    "status": "inbox",
                    "owner": "delivery",
                    "priority": 8,
                    "tags": ["orchestration_acceptance", "post_wp12_acceptance", "final_ux_repair"],
                    "parent_id": "AOS-2026-0071",
                    "step_index": 3,
                    "depends_on": ["AOS-2026-0073"],
                    "source_refs": [],
                    "workbench": "local",
                    "created_at": "2026-07-10T18:49:46Z",
                    "updated_at": "2026-07-10T18:49:46Z",
                    "receipts": [],
                },
            ])
            (receipts / "AOS-2026-0072-source-pack.md").write_text(f"PASS\nArtifact: {source_pack}\n", encoding="utf-8")
            (receipts / "AOS-2026-0073-draft-human-review.md").write_text(f"PASS\nArtifact: {brief}\n", encoding="utf-8")
            (queue / "notifications.json").write_text(json.dumps({"escalation": {"unanswered_minutes": 10}, "allowlist": {"telegram": []}}), encoding="utf-8")

            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "QUEUE_TOOL", MAIN.parents[2] / "tools" / "aos-queue.py"), \
                 patch.object(backend.latitude_telemetry, "trace"):
                result = backend.close_queue_item_review(
                    "AOS-2026-0073",
                    backend.QueueReviewClose(status="done", action="approve", review_note="Approved for final packaging."),
                )
                repeated = backend.close_queue_item_review(
                    "AOS-2026-0073",
                    backend.QueueReviewClose(status="done", action="approve", review_note="Approved for final packaging."),
                )

            json.dumps(result, sort_keys=True)
            json.dumps(repeated, sort_keys=True)
            self.assertTrue(result["ok"])
            self.assertTrue(result["final_result"]["complete"])
            self.assertEqual(result["parent_id"], "AOS-2026-0071")
            self.assertEqual(result["reviewed_item_id"], "AOS-2026-0073")
            self.assertEqual(result["final_item_id"], "AOS-2026-0074")
            self.assertEqual(result["advanced_item_ids"], ["AOS-2026-0074"])
            self.assertEqual(repeated["advanced_item_ids"], [])
            self.assertEqual(repeated["resume_tick"]["advanced"], [])
            rows = [json.loads(line) for line in (queue / "work_items.jsonl").read_text(encoding="utf-8").splitlines()]
            by_id = {row["id"]: row for row in rows}
            self.assertEqual(by_id["AOS-2026-0071"]["status"], "done")
            self.assertEqual(by_id["AOS-2026-0073"]["status"], "done")
            self.assertEqual(by_id["AOS-2026-0074"]["status"], "done")
            self.assertEqual(sum(1 for receipt in by_id["AOS-2026-0073"]["receipts"] if receipt.get("status") == "done"), 1)
            self.assertEqual(len(list(results.glob("03_final_review_package.md"))), 1)
            self.assertEqual(len(list(receipts.glob("AOS-2026-0074-final-closeout-*.md"))), 1)
            self.assertIn("Approved for final packaging.", (root / review_receipt).read_text(encoding="utf-8"))

    def test_queue_artifact_preview_and_folder_open_refuse_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "results" / "orchestration_acceptance" / "AOS-2026-0300" / "03_final_review_package.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("final package", encoding="utf-8")

            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend.subprocess, "Popen") as popen:
                opened = backend.queue_artifact_open_folder(
                    backend.QueueArtifactFolderOpen(path="results/orchestration_acceptance/AOS-2026-0300/03_final_review_package.md")
                )
                self.assertTrue(opened["success"])
                self.assertEqual(opened["path"], "results/orchestration_acceptance/AOS-2026-0300")
                popen.assert_called_once()

                artifact_absolute = backend.queue_artifact("/tmp/outside.md")
                self.assertFalse(artifact_absolute["success"])
                self.assertIn("root-relative", artifact_absolute["reason"])
                with self.assertRaises(ValueError):
                    backend._queue_read_artifact("/tmp/outside.md")

                with self.assertRaises(backend.HTTPException) as folder_absolute:
                    backend.queue_artifact_open_folder(backend.QueueArtifactFolderOpen(path="/tmp/outside.md"))
                self.assertEqual(folder_absolute.exception.status_code, 400)

                with self.assertRaises(backend.HTTPException) as blocked_secret:
                    backend.queue_artifact_open_folder(backend.QueueArtifactFolderOpen(path="results/.env.md"))
                self.assertEqual(blocked_secret.exception.status_code, 400)

    def test_queue_completion_card_frontend_contract_is_present(self):
        source = (MAIN.parents[1] / "frontend" / "src" / "views" / "Queue.jsx").read_text(encoding="utf-8")
        for text in (
            "Workflow complete",
            "Open Final Review Package",
            "Open Final Receipt",
            "Open Output Folder",
            "View Final Step",
            "openQueueArtifactFolder",
        ):
            self.assertIn(text, source)

    def test_queue_run_uses_prompt_files_and_redacted_token_task(self):
        adversarial_title = "Build output with `ticks`, $(bad), $VARS, quotes, and C:\\Users\\Admin\\A Time"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [{
                "id": "AOS-2026-0099",
                "title": adversarial_title,
                "status": "inbox",
                "owner": "codex",
                "priority": 5,
                "created_at": "2026-07-05T10:00:00Z",
                "updated_at": "2026-07-05T10:00:00Z",
                "claim": {"claimed_by": None, "claimed_at": None},
                "receipts": [],
                "context": "multi-line\nmarkdown with `code` and $(still bad)",
                "allowed_actions": ["local_read"],
                "stop_conditions": ["external_send"],
                "definition_of_done": "Write a concrete local artifact.",
                "review": "model",
            }])
            self.write_queue_templates(root)
            self.write_queue_references(root)
            commands = []
            prompts = []
            token_tasks = []

            def codex_capture(prompt, item=None):
                prompts.append(prompt)
                artifact = root / "workflows" / "queue_artifacts" / "AOS-2026-0099_output.md"
                artifact.parent.mkdir(parents=True, exist_ok=True)
                artifact.write_text("fixture output\n", encoding="utf-8")
                return {
                    "success": True,
                    "output": "PASS\nFiles touched: workflows/queue_artifacts/AOS-2026-0099_output.md\nValidation: local check\nBlockers: None\nNext action: Liam review",
                    "stdout": "",
                    "stderr": "",
                    "returncode": 0,
                    "command_stage": "execution",
                    "timeout_seconds": backend.AGENT_TIMEOUT_SECONDS,
                    "token_usage_text": "Token usage: unavailable from current CLI output",
                    "token_usage": {"available": False},
                }

            def run_capture(command, timeout=60):
                commands.append(command)
                match = re.search(r"(?:--prompt-file\s+|<)(?P<quote>['\"]?)(?P<path>[^'\")]+)(?P=quote)", command)
                if match:
                    prompts.append(Path(match.group("path")).read_text(encoding="utf-8"))
                return {"success": True, "output": "PASS", "stdout": "PASS", "stderr": "", "returncode": 0}

            def log_capture(route, agent, task, token_usage, token_usage_text, route_metadata=None):
                token_tasks.append(task)
                return {}

            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_codex_local", side_effect=codex_capture), \
                 patch.object(backend, "_run_wsl", side_effect=run_capture), \
                 patch.object(backend, "_log_token_usage", side_effect=log_capture):
                result = backend.run_queue_item("AOS-2026-0099")

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "human_review")
            prompt_commands = [command for command in commands if "--prompt-file" in command]
            self.assertGreaterEqual(len(prompt_commands), 1)
            for command in prompt_commands:
                self.assertNotIn("$(bad)", command)
                self.assertNotIn("$VARS", command)
                self.assertNotIn("`ticks`", command)
            self.assertIn(adversarial_title, prompts[0])
            self.assertIn("Required local artifact path:", prompts[0])
            self.assertEqual(token_tasks[0], f"AOS-2026-0099 | codex | {adversarial_title[:160]}")
            self.assertEqual(len(token_tasks), 2)
            self.assertIn("Review this Agentic OS queue worker result", token_tasks[1])
            self.assertNotIn("multi-line\nmarkdown", token_tasks[0])

            item = json.loads((root / "queue" / "work_items.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(item["status"], "human_review")
            self.assertEqual(item["claim"], {"claimed_by": None, "claimed_at": None})
            receipt_path = root / item["receipts"][-1]["path"]
            receipt = receipt_path.read_text(encoding="utf-8")
            self.assertIn("Work item ID: AOS-2026-0099", receipt)
            self.assertIn("Lane: codex", receipt)
            self.assertIn("Profile requested: default", receipt)
            self.assertIn("Profile used: default", receipt)
            self.assertIn("Profile fallback reason: explicit provider/model route missing or placeholder", receipt)
            self.assertIn("Model requested: configured externally", receipt)
            self.assertIn("Model used: default", receipt)
            self.assertIn("Provider requested: configured externally", receipt)
            self.assertIn("Provider used: default", receipt)
            self.assertIn("Model confirmed: unavailable from current CLI output", receipt)
            self.assertIn("Provider confirmed: unavailable from current CLI output", receipt)
            self.assertIn("Token usage:", receipt)
            self.assertIn("Artifacts:", receipt)

    def test_queue_model_routes_load_from_json_and_known_lanes_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_model_routes(root, {
                "version": "unit",
                "fallback": {
                    "lane": "fallback",
                        "profile_requested": "fallback_profile",
                        "provider": "configured externally",
                        "model": "configured externally",
                        "escalation_rule": "fallback rule",
                    },
                "routes": {
                    "revenue": {
                        "lane": "revenue",
                        "profile_requested": "aos-revenue",
                        "provider": "configured externally",
                        "model": "configured externally",
                        "escalation_rule": "unit revenue rule",
                    }
                },
            })
            with patch.object(backend, "BASE_DIR", root):
                loaded = backend._load_queue_model_routes()
                revenue = backend._queue_resolve_route_metadata("revenue")
                unknown = backend._queue_resolve_route_metadata("unknown")

            self.assertEqual(loaded["version"], "unit")
            self.assertEqual(revenue["profile_used"], "default")
            self.assertEqual(revenue["profile_requested"], "aos-revenue")
            self.assertEqual(revenue["model_requested"], "configured externally")
            self.assertEqual(revenue["model_used"], "default")
            self.assertEqual(revenue["provider_requested"], "configured externally")
            self.assertEqual(revenue["provider_used"], "default")
            self.assertFalse(revenue["explicit_model_provider_route"])
            self.assertEqual(revenue["escalation_rule"], "unit revenue rule")
            self.assertEqual(unknown["lane"], "unknown")
            self.assertEqual(unknown["profile"], "default")
            self.assertEqual(unknown["model_confirmed"], "unavailable from current CLI output")

        expected_profiles = {
            "hermes": "aos-orchestrator",
            "revenue": "default",
            "marketing": "default",
            "delivery": "default",
            "operations": "default",
            "codex": "default",
            "claude": "default",
        }
        for lane, profile in expected_profiles.items():
            self.assertEqual(backend._queue_resolve_route_metadata(lane)["profile"], profile)
        self.assertEqual(backend._queue_resolve_route_metadata("unknown")["profile"], "aos-orchestrator")

    def test_model_routes_source_profile_metadata_and_unknown_lane_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_model_routes(root, {
                "version": "unit",
                "fallback": {
                    "lane": "fallback",
                    "profile_requested": "default",
                    "provider": "configured externally",
                    "model": "configured externally",
                },
                "routes": {
                    "revenue": {
                        "lane": "revenue",
                        "profile_requested": "aos-revenue",
                        "provider": "configured externally",
                        "model": "configured externally",
                    }
                },
            })
            with patch.object(backend, "BASE_DIR", root):
                revenue = backend._queue_resolve_route_metadata("revenue")
                missing = backend._queue_resolve_route_metadata("unknown")

        self.assertEqual(revenue["profile_requested"], "aos-revenue")
        self.assertEqual(revenue["profile_used"], "default")
        self.assertEqual(revenue["profile_fallback_reason"], "explicit provider/model route missing or placeholder")
        self.assertEqual(missing["profile_requested"], "default")
        self.assertEqual(missing["profile_used"], "default")
        self.assertEqual(missing["profile_fallback_reason"], "explicit provider/model route missing or placeholder")

    def test_explicit_model_provider_route_builds_hermes_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_model_routes(root, {
                "version": "unit",
                "fallback": {"lane": "fallback", "profile_requested": "default", "provider": "configured externally", "model": "configured externally"},
                "routes": {
                    "revenue": {
                        "lane": "revenue",
                        "profile_requested": "aos-revenue",
                        "provider": "anthropic",
                        "model": "claude-sonnet-4",
                        "escalation_rule": "unit revenue rule",
                    }
                },
            })
            self.write_queue_items(root, [{
                "id": "AOS-2026-0101",
                "title": "Revenue explicit provider model command",
                "status": "inbox",
                "owner": "revenue",
                "priority": 5,
                "created_at": "2026-07-05T10:00:00Z",
                "updated_at": "2026-07-05T10:00:00Z",
                "claim": {"claimed_by": None, "claimed_at": None},
                "receipts": [],
            }])
            self.write_queue_templates(root)
            commands = []

            def run_capture(command, timeout=60):
                commands.append(command)
                return {
                    "success": True,
                    "output": "PASS\nFiles touched: None\nValidation: local check\nBlockers: None\nNext action: Review",
                    "stdout": "PASS",
                    "stderr": "",
                    "returncode": 0,
                }

            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl", side_effect=run_capture), \
                 patch.object(backend, "_queue_run_hermes_review", return_value={"success": True, "output": "PASS", "token_usage": {"available": False}, "token_usage_text": "Token usage: unavailable from current CLI output"}):
                result = backend.run_queue_item("AOS-2026-0101")

        self.assertTrue(result["success"])
        self.assertIn("--provider anthropic --model claude-sonnet-4 --prompt-file", commands[0])
        self.assertNotIn("--profile", commands[0])
        worker = result["worker_result"]
        self.assertEqual(worker["profile_requested"], "aos-revenue")
        self.assertEqual(worker["profile_used"], "explicit_model_provider_route")
        self.assertEqual(worker["profile_fallback_reason"], "")
        self.assertEqual(worker["model_requested"], "claude-sonnet-4")
        self.assertEqual(worker["model_used"], "claude-sonnet-4")
        self.assertEqual(worker["provider_requested"], "anthropic")
        self.assertEqual(worker["provider_used"], "anthropic")
        self.assertEqual(worker["model_confirmed"], "configured in queue/model_routes.json")
        self.assertEqual(worker["provider_confirmed"], "configured in queue/model_routes.json")

    def test_placeholder_model_provider_route_falls_back_without_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_model_routes(root, {
                "version": "unit",
                "fallback": {"lane": "fallback", "profile_requested": "default", "provider": "configured externally", "model": "configured externally"},
                "routes": {
                    "revenue": {
                        "lane": "revenue",
                        "profile_requested": "aos-revenue",
                        "provider": "configured externally",
                        "model": "TBD",
                    }
                },
            })
            with patch.object(backend, "BASE_DIR", root):
                metadata = backend._queue_resolve_route_metadata("revenue")

        self.assertEqual(metadata["profile_requested"], "aos-revenue")
        self.assertEqual(metadata["profile_used"], "default")
        self.assertEqual(metadata["profile_fallback_reason"], "explicit provider/model route missing or placeholder")
        self.assertEqual(metadata["model_requested"], "TBD")
        self.assertEqual(metadata["model_used"], "default")
        self.assertEqual(metadata["provider_requested"], "configured externally")
        self.assertEqual(metadata["provider_used"], "default")
        self.assertEqual(metadata["model_confirmed"], "unavailable from current CLI output")
        self.assertFalse(metadata["explicit_model_provider_route"])
        command = backend._hermes_coordinator_command_template(metadata)
        self.assertNotIn("--provider", command)
        self.assertNotIn("--model", command)

    def test_exact_and_fake_provider_values_fall_back_without_flags(self):
        cases = (
            ("<EXACT_PROVIDER>", "claude-sonnet-4"),
            ("fake-provider", "claude-sonnet-4"),
            ("unit-provider", "unit-model"),
            ("not-a-hermes-provider", "claude-sonnet-4"),
            ("anthropic", "<EXACT_MODEL>"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for provider, model in cases:
                self.write_model_routes(root, {
                    "version": "unit",
                    "fallback": {"lane": "fallback", "profile_requested": "default", "provider": "configured externally", "model": "configured externally"},
                    "routes": {"revenue": {"lane": "revenue", "profile_requested": "aos-revenue", "provider": provider, "model": model}},
                })
                with patch.object(backend, "BASE_DIR", root):
                    metadata = backend._queue_resolve_route_metadata("revenue")
                    command = backend._hermes_coordinator_command_template(metadata)
                self.assertFalse(metadata["explicit_model_provider_route"], provider)
                self.assertEqual(metadata["provider_used"], "default", provider)
                self.assertEqual(metadata["model_used"], "default", provider)
                self.assertNotIn("--provider", command, provider)
                self.assertNotIn("--model", command, provider)

    def test_queue_run_receipt_and_token_ledger_include_route_metadata_without_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [{
                "id": "AOS-2026-0100",
                "title": "Revenue route metadata",
                "status": "inbox",
                "owner": "revenue",
                "priority": 5,
                "created_at": "2026-07-05T10:00:00Z",
                "updated_at": "2026-07-05T10:00:00Z",
                "claim": {"claimed_by": None, "claimed_at": None},
                "receipts": [],
                "context": "FULL PROMPT SENTINEL should stay out of the token ledger metadata",
                "allowed_actions": ["local_read"],
                "stop_conditions": ["external_send"],
                "definition_of_done": "Write a concrete local artifact.",
            }])
            self.write_queue_templates(root)
            self.write_queue_references(root)
            token_file = root / "logs" / "token_usage.jsonl"

            def run_capture(command, timeout=60):
                if "aos-hermes-coordinator.sh" in command and "--prompt-file" in command:
                    if not hasattr(run_capture, "calls"):
                        run_capture.calls = 0
                    run_capture.calls += 1
                    if run_capture.calls == 1:
                        artifact = root / "workflows" / "queue_artifacts" / "AOS-2026-0100_output.md"
                        artifact.parent.mkdir(parents=True, exist_ok=True)
                        artifact.write_text("fixture output\n", encoding="utf-8")
                        return {
                            "success": True,
                            "output": "PASS\nFiles touched: workflows/queue_artifacts/AOS-2026-0100_output.md\nValidation: local check\nBlockers: None\nNext action: Liam review\nToken usage: unavailable from current CLI output",
                            "stdout": "PASS\nFiles touched: workflows/queue_artifacts/AOS-2026-0100_output.md\nValidation: local check\nBlockers: None\nNext action: Liam review",
                            "stderr": "",
                            "returncode": 0,
                        }
                    return {"success": True, "output": "PASS", "stdout": "PASS", "stderr": "", "returncode": 0}
                return {"success": True, "output": "PASS", "stdout": "PASS", "stderr": "", "returncode": 0}

            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "TOKEN_USAGE_FILE", token_file), \
                 patch.object(backend, "_run_wsl", side_effect=run_capture):
                result = backend.run_queue_item("AOS-2026-0100")

            self.assertTrue(result["success"])
            item = json.loads((root / "queue" / "work_items.jsonl").read_text(encoding="utf-8").splitlines()[0])
            receipt = (root / item["receipts"][-1]["path"]).read_text(encoding="utf-8")
            self.assertIn("Lane: revenue", receipt)
            self.assertIn("Profile requested: aos-revenue", receipt)
            self.assertIn("Profile used: default", receipt)
            self.assertIn("Profile fallback reason: explicit provider/model route missing or placeholder", receipt)
            self.assertIn("Model requested: configured externally", receipt)
            self.assertIn("Model used: default", receipt)
            self.assertIn("Provider requested: configured externally", receipt)
            self.assertIn("Provider used: default", receipt)
            self.assertIn("Model confirmed: unavailable from current CLI output", receipt)
            self.assertIn("Provider confirmed: unavailable from current CLI output", receipt)
            self.assertIn("Escalation rule: Escalate for direct prospect-facing copy", receipt)
            self.assertIn("Token usage:", receipt)
            self.assertIn("- Attempt 1 worker (role=implementer; session=unavailable): unavailable from current CLI output", receipt)

            records = [json.loads(line) for line in token_file.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(records), 1)
            record_text = json.dumps(records[0], sort_keys=True)
            self.assertEqual(records[0]["lane"], "revenue")
            self.assertEqual(records[0]["profile_requested"], "aos-revenue")
            self.assertEqual(records[0]["profile_used"], "default")
            self.assertEqual(records[0]["profile_fallback_reason"], "explicit provider/model route missing or placeholder")
            self.assertEqual(records[0]["profile"], "default")
            self.assertEqual(records[0]["model_requested"], "configured externally")
            self.assertEqual(records[0]["model_used"], "default")
            self.assertEqual(records[0]["provider_requested"], "configured externally")
            self.assertEqual(records[0]["provider_used"], "default")
            self.assertEqual(records[0]["model_confirmed"], "unavailable from current CLI output")
            self.assertNotIn("FULL PROMPT SENTINEL", record_text)

    def test_search_firecrawl_and_composio_work_uses_native_hermes_fallback(self):
        reply = {"success": True, "reply": "Hermes handled the intelligent request."}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_hermes_message", return_value=reply) as hermes, \
                 patch.object(backend, "_hermes_coordinator_closeout", side_effect=lambda result, task, route: {
                     "success": True, "selected_route": "hermes_coordinator", "output": result["reply"],
                 }):
                results = [
                    backend.wsl_hermes(backend.TaskRun(task=task))
                    for task in ("search the web", "scrape this page", "use Firecrawl", "use Composio to check mail")
                ]
                rows = backend._read_queue_items()
        self.assertEqual(hermes.call_count, 4)
        self.assertTrue(all(result["selected_route"] == "hermes_coordinator" for result in results))
        self.assertEqual(rows, [])

    def test_queue_intent_creates_local_queue_item_without_wsl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.wsl_hermes(backend.TaskRun(task="Add this to the queue: Have Codex inspect the dashboard route"))

            run.assert_not_called()
            self.assertEqual(result["selected_route"], "local_queue")
            self.assertEqual(result["owner"], "codex")
            self.assertEqual(result["status"], "inbox")
            self.assertIn("Work item ID: AOS-", result["output"])
            self.assertIn("Owner: codex", result["output"])
            self.assertIn("Status: inbox", result["output"])
            self.assertIn("Next action: Review or claim the local queue item", result["output"])

            lines = (root / "queue" / "work_items.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            item = json.loads(lines[0])
            self.assertEqual(item["id"], result["work_item_id"])
            self.assertEqual(item["owner"], "codex")
            self.assertEqual(item["title"], "Have Codex inspect the dashboard route")

    def test_queue_owner_inference_is_explicit_only(self):
        cases = (
            ("Add this to the queue: Claude should polish copy", "claude"),
            ("add this to the queue: revenue should review offer", "revenue"),
            ("ADD THIS TO THE QUEUE: marketing campaign brief", "marketing"),
            ("Add this to the queue: delivery handoff checklist", "delivery"),
            ("Add this to the queue: operations SOP cleanup", "operations"),
            ("Add this to the queue: review the plan", "unassigned"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                results = [backend.wsl_hermes(backend.TaskRun(task=task)) for task, _ in cases]

            run.assert_not_called()
            self.assertEqual([result["owner"] for result in results], [owner for _, owner in cases])

    def test_non_prefix_queue_language_uses_async_queue_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_runner_status", return_value={"available": True, "state": "running", "pid": 1}), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.wsl_hermes(backend.TaskRun(task="Please add this to the queue: have Codex inspect the route"))
        run.assert_not_called()
        self.assertEqual(result["selected_route"], "direct_codex")
        self.assertEqual(result["owner"], "codex")

    def test_queue_status_intent_returns_counts_without_wsl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.wsl_hermes(backend.TaskRun(task="  Queue status  "))

        run.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["selected_route"], "local_queue_status")
        self.assertIn("PASS\nQueue status:", result["output"])
        self.assertIn("  - inbox: 1", result["output"])
        self.assertIn("  - agent_todo: 1", result["output"])
        self.assertIn("  - blocked: 1", result["output"])
        self.assertIn("  - cancelled: 0", result["output"])
        self.assertIn("Needs Liam:\n  - 1", result["output"])
        self.assertIn("Next action:\n  - Review needs_input, human_review, or blocked items first.", result["output"])
        self.assertEqual(result["token_usage"], {"available": False, "no_agent_invocation": True})
        self.assertEqual(result["token_usage_text"], "Token usage: no agent invocation")

    def test_show_queue_status_and_summary_intents_return_counts_without_wsl(self):
        for task in ("Show queue status", "Show queue summary"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.write_queue_items(root, self.sample_queue_items())
                with patch.object(backend, "BASE_DIR", root), \
                     patch.object(backend, "_run_wsl") as run:
                    result = backend.wsl_hermes(backend.TaskRun(task=task))

            run.assert_not_called()
            self.assertTrue(result["success"], task)
            self.assertEqual(result["selected_route"], "local_queue_status")
            self.assertIn("PASS\nQueue status:", result["output"])
            self.assertIn("  - agent_todo: 1", result["output"])
            self.assertIn("  - blocked: 1", result["output"])
            self.assertEqual(result["token_usage"], {"available": False, "no_agent_invocation": True})
            self.assertEqual(result["token_usage_text"], "Token usage: no agent invocation")

    def test_blocked_queue_intent_returns_compact_items_without_wsl(self):
        items = self.sample_queue_items()
        items[2]["next_action"] = "Choose whether connector work remains in scope"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, items)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.wsl_hermes(backend.TaskRun(task="What is currently blocked?"))

        run.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["selected_route"], "local_queue_read")
        self.assertIn("Blocked queue items:\n  - blocked: 1", result["output"])
        self.assertIn(
            "AOS-2026-0003 | Blocked connector decision | hermes | blocked | Next action: Choose whether connector work remains in scope",
            result["output"],
        )
        self.assertNotIn("Codex route test", result["output"])
        self.assertEqual(result["token_usage"], {"available": False, "no_agent_invocation": True})
        self.assertEqual(result["token_usage_text"], "Token usage: no agent invocation")

    def test_review_queue_intent_returns_compact_items_without_wsl(self):
        items = self.sample_queue_items() + [
            {
                "id": "AOS-2026-0005",
                "title": "Review queue closeout",
                "status": "human_review",
                "owner": "codex",
                "priority": 8,
                "created_at": "2026-07-05T10:04:00Z",
                "next_action": "Approve or return notes",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, items)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.wsl_hermes(backend.TaskRun(task="Show queue items needing review"))

        run.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["selected_route"], "local_queue_read")
        self.assertIn("Queue items needing review:\n  - human_review: 1", result["output"])
        self.assertIn(
            "AOS-2026-0005 | Review queue closeout | codex | human_review | Next action: Approve or return notes",
            result["output"],
        )
        self.assertNotIn("Blocked connector decision", result["output"])
        self.assertEqual(result["token_usage"], {"available": False, "no_agent_invocation": True})
        self.assertEqual(result["token_usage_text"], "Token usage: no agent invocation")

    def test_list_queue_intent_returns_compact_rows_without_wsl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.wsl_hermes(backend.TaskRun(task="List queue"))

        run.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["selected_route"], "local_queue_list")
        self.assertIn("PASS\nQueue items:", result["output"])
        self.assertIn("AOS-2026-0002 | agent_todo | codex | Codex route test", result["output"])
        self.assertIn("AOS-2026-0001 | inbox | unassigned | Triage inbox lead", result["output"])
        self.assertIn("AOS-2026-0003 | blocked | hermes | Blocked connector decision", result["output"])
        self.assertNotIn("Finished old task", result["output"])
        self.assertIn("Next action:\n  - Review needs_input, human_review, or blocked items first.", result["output"])

    def test_queue_summary_endpoint_returns_dashboard_state_without_wsl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.queue_summary()

        run.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["counts"]["inbox"], 1)
        self.assertEqual(result["counts"]["agent_todo"], 1)
        self.assertEqual(result["counts"]["done"], 1)
        self.assertEqual(result["needsLiam"], 1)
        self.assertEqual(result["needsMeCount"], result["needsLiam"])
        self.assertEqual([item["id"] for item in result["needsMeItems"]], ["AOS-2026-0003"])
        self.assertEqual(result["activeCount"], 3)
        self.assertEqual(result["totalCount"], 4)
        self.assertEqual([item["id"] for item in result["activeItems"]], ["AOS-2026-0002", "AOS-2026-0003", "AOS-2026-0001"])
        self.assertEqual(result["nextItem"]["id"], "AOS-2026-0002")
        self.assertNotIn("Finished old task", json.dumps(result))

    def test_queue_items_supports_active_history_all_and_legacy_all_default(self):
        items = self.sample_queue_items() + [{
            "id": "AOS-2026-0005",
            "title": "Cancelled old task",
            "status": "cancelled",
            "owner": "unassigned",
            "priority": 2,
            "created_at": "2026-07-05T10:04:00Z",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, items)
            with patch.object(backend, "BASE_DIR", root):
                active = backend.queue_items("active")
                history = backend.queue_items("history")
                all_items = backend.queue_items("all")
                legacy = backend.queue_items()

        self.assertEqual({row["status"] for row in active["items"]}, {"inbox", "agent_todo", "blocked"})
        self.assertEqual({row["status"] for row in history["items"]}, {"done", "cancelled"})
        self.assertEqual(len(all_items["items"]), len(items))
        self.assertEqual(legacy["items"], all_items["items"])
        self.assertLess(active["itemCount"], all_items["itemCount"])
        self.assertEqual(all_items["totalCount"], len(items))

    def test_dashboard_cockpit_uses_queue_summary_needs_me_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = [
                *self.sample_queue_items(),
                {
                    "id": "AOS-2026-0005",
                    "title": "Operator input gate",
                    "status": "needs_input",
                    "owner": "hermes",
                    "priority": 8,
                    "created_at": "2026-07-05T10:04:00Z",
                },
                {
                    "id": "AOS-2026-0006",
                    "title": "Review closeout",
                    "status": "human_review",
                    "owner": "codex",
                    "priority": 7,
                    "created_at": "2026-07-05T10:05:00Z",
                },
            ]
            self.write_queue_items(root, items)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_dashboard_token_summary", return_value={"by_tool": [], "strip": {}, "records": []}), \
                 patch.object(backend, "_recent_file_items", return_value=[]), \
                 patch.object(backend, "_run_wsl") as run:
                summary = backend.queue_summary()
                cockpit = backend.dashboard_cockpit()

        run.assert_not_called()
        self.assertTrue(cockpit["success"])
        self.assertEqual(cockpit["needs_me_count"], summary["needsLiam"])
        self.assertEqual(cockpit["human_needed_count"], summary["humanNeededCount"])
        self.assertEqual(
            {item["id"] for item in cockpit["needs_me"]},
            {item["id"] for item in summary["needsMeItems"]},
        )
        self.assertEqual(
            {item["status"] for item in cockpit["needs_me"]},
            {"needs_input", "human_review", "blocked"},
        )

    def test_existing_human_needed_items_appear_without_notification_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [
                {
                    "id": "AOS-2026-0001",
                    "title": "Needs input now",
                    "status": "needs_input",
                    "owner": "hermes",
                    "priority": 3,
                    "created_at": "2026-07-05T10:00:00Z",
                },
                {
                    "id": "AOS-2026-0002",
                    "title": "Review now",
                    "status": "human_review",
                    "owner": "codex",
                    "priority": 2,
                    "created_at": "2026-07-05T10:01:00Z",
                },
                {
                    "id": "AOS-2026-0003",
                    "title": "Blocked now",
                    "status": "blocked",
                    "owner": "operations",
                    "priority": 1,
                    "created_at": "2026-07-05T10:02:00Z",
                },
            ])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_dashboard_token_summary", return_value={"by_tool": [], "strip": {}, "records": []}), \
                 patch.object(backend, "_recent_file_items", return_value=[]):
                cockpit = backend.dashboard_cockpit()

        self.assertFalse((root / "queue" / "orchestration_events.jsonl").exists())
        self.assertEqual(cockpit["needs_me_count"], 3)
        self.assertEqual(
            {item["id"] for item in cockpit["needs_me"]},
            {"AOS-2026-0001", "AOS-2026-0002", "AOS-2026-0003"},
        )

    def test_dashboard_cockpit_returns_every_human_needed_item_without_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = [{
                "id": f"AOS-2026-{index:04d}",
                "title": f"Human gate {index}",
                "status": ("needs_input", "human_review", "blocked")[index % 3],
                "owner": "codex",
                "priority": index,
                "created_at": f"2026-07-05T10:{index:02d}:00Z",
            } for index in range(1, 10)]
            self.write_queue_items(root, items)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_dashboard_token_summary", return_value={"by_tool": [], "strip": {}, "records": []}), \
                 patch.object(backend, "_recent_file_items", return_value=[]):
                cockpit = backend.dashboard_cockpit()

        self.assertEqual(cockpit["needs_me_count"], 9)
        self.assertEqual(len(cockpit["needs_me"]), cockpit["needs_me_count"])

    def test_model_turn_threshold_adds_needs_me_only_above_default(self):
        items = [
            {"id": "AOS-2026-0001", "title": "Above", "status": "done", "priority": 1, "created_at": "2026-07-05T10:00:00Z"},
            {"id": "AOS-2026-0002", "title": "At", "status": "done", "priority": 1, "created_at": "2026-07-05T10:01:00Z"},
            {"id": "AOS-2026-0003", "title": "Below", "status": "done", "priority": 1, "created_at": "2026-07-05T10:02:00Z"},
        ]
        records = [
            {"item_id": "AOS-2026-0001", "timestamp": "2026-07-05T11:00:00Z", "model_turns": 76},
            {"item_id": "AOS-2026-0002", "timestamp": "2026-07-05T11:00:00Z", "model_turns": 75},
            {"item_id": "AOS-2026-0003", "timestamp": "2026-07-05T11:00:00Z", "model_turns": 74},
        ]
        attributions = backend._queue_invocation_attributions(records)
        needs_me = backend._queue_human_needed_items(items, attributions)
        public = backend._queue_public_item(items[0], attributions)
        self.assertEqual(["AOS-2026-0001"], [item["id"] for item in needs_me])
        self.assertEqual(["excessive model turns"], public["needs_me"])
        self.assertEqual(backend.MODEL_TURNS_THRESHOLD_DEFAULT, 75)

    def test_telegram_send_test_endpoint_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue").mkdir(parents=True, exist_ok=True)
            (root / "queue" / "notifications.json").write_text(
                json.dumps({
                    "escalation": {"unanswered_minutes": 1},
                    "allowlist": {"telegram": ["1320777128"], "agentmail_internal": []},
                }),
                encoding="utf-8",
            )
            self.write_queue_items(root, [{
                "id": "AOS-2026-0001",
                "title": "Validation send",
                "status": "needs_input",
                "owner": "operations",
                "priority": 1,
                "created_at": "2026-07-09T00:00:00Z",
                "updated_at": "2026-07-09T00:00:00Z",
                "claim": {"claimed_by": None, "claimed_at": None},
                "receipts": [],
            }])
            sends = []

            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend.aos_orchestration, "default_bridge_send", side_effect=lambda chat, text: sends.append((chat, text))):
                body = backend.TelegramSendValidation(item_id="AOS-2026-0001", recipient="1320777128")
                first = backend.orchestration_telegram_send_test(body)
                second = backend.orchestration_telegram_send_test(body)

            self.assertTrue(first["success"])
            self.assertEqual(first["result"], "sent")
            self.assertTrue(first["sent"])
            self.assertTrue(second["success"])
            self.assertEqual(second["result"], "already_sent")
            self.assertFalse(second["sent"])
            self.assertTrue(second["duplicate_blocked"])
            self.assertEqual(len(sends), 1)
            self.assertEqual(sends[0], ("1320777128", "Agentic OS validation send"))

    def test_system_watch_labels_stalled_runs_separately_from_needs_me(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [
                {
                    "id": "AOS-2026-0001",
                    "title": "Old agent task",
                    "status": "agent_todo",
                    "owner": "codex",
                    "priority": 9,
                    "created_at": "2026-07-05T10:00:00Z",
                    "updated_at": "2026-07-05T10:00:00Z",
                },
                {
                    "id": "AOS-2026-0002",
                    "title": "Operator review",
                    "status": "human_review",
                    "owner": "hermes",
                    "priority": 1,
                    "created_at": "2026-07-05T10:01:00Z",
                },
            ])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "LOGS_DIR", root / "logs"), \
                 patch.object(backend, "QUEUE_TOOL", root / "tools" / "aos-queue.py"):
                watch = backend.dashboard_system_watch(stalled_minutes=15)

        self.assertEqual(watch["needs_me_count"], 1)
        self.assertEqual([item["id"] for item in watch["needs_me"]], ["AOS-2026-0002"])
        self.assertEqual([item["id"] for item in watch["stalled_needs_attention"]], ["AOS-2026-0001"])
        self.assertEqual(watch["stalled_count"], 1)

    def test_dashboard_queue_post_get_and_prompts_are_local_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_templates(root)
            body = backend.QueueItemCreate(
                title="Patch dashboard queue prompt copy",
                owner="codex",
                priority="high",
                tags="dashboard,queue",
                source="operator_daily_queue",
                context="Keep the workflow manual.",
                sources="dashboard/frontend/src/views/Queue.jsx\nqueue/templates/codex_task.prompt.md",
                source_refs="workflows/revenue_linkedin_outreach/output/AOS-2026-0021_ttr_sme_outreach_angle_pack.md\nqueue/receipts/AOS-2026-0002.md",
                definition_of_done="Queue item can be created and copied.",
                allowed_actions="local_read\nlocal_edit\nlocal_test",
                stop_conditions="external_send\nsecrets_exposure\ndestructive_action_outside_scope",
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                created = backend.create_queue_item(body)
                item_id = created["item"]["id"]
                shown = backend.queue_item(item_id)
                codex = backend.queue_item_prompt(item_id, "codex")
                claude = backend.queue_item_prompt(item_id, "claude")

            run.assert_not_called()
            self.assertTrue(created["success"])
            self.assertEqual(created["item"]["status"], "agent_todo")
            self.assertEqual(created["item"]["requested_by"], "Liam")
            self.assertEqual(created["item"]["source"], "operator_daily_queue")
            self.assertEqual(created["item"]["source_refs"], [
                "workflows/revenue_linkedin_outreach/output/AOS-2026-0021_ttr_sme_outreach_angle_pack.md",
                "queue/receipts/AOS-2026-0002.md",
            ])
            self.assertEqual(shown["item"]["id"], item_id)
            self.assertEqual(shown["item"]["title"], "Patch dashboard queue prompt copy")
            for prompt_response in (codex, claude):
                prompt = prompt_response["prompt"]
                self.assertIn("PERMISSION MODE — SCOPED LOCAL TASK APPROVED", prompt)
                self.assertIn(
                    "Do not ask for permission during this scoped local task. Assume approval for local reads, local edits, local file creation, dependency installation, validation commands, local dev-server startup, browser preview, and screenshot capture inside the stated scope.",
                    prompt,
                )
                self.assertIn(f"- ID: {item_id}", prompt)
                self.assertIn("- Title: Patch dashboard queue prompt copy", prompt)
                self.assertIn("## Launch from Linux", prompt)
                self.assertIn("Do not launch agents automatically.", prompt)
            codex_prompt = codex["prompt"]
            claude_prompt = claude["prompt"]
            self.assertIn(f"python3 tools/aos-queue.py codex-run {item_id} --prompt-file -", codex_prompt)
            self.assertIn("explicit work-item ID is retained through process exit", codex_prompt)
            self.assertNotIn("aos-codex", codex_prompt)
            self.assertIn("aos-claude", claude_prompt)
            self.assertNotIn("aos-hermes claude", claude_prompt)

    def test_cockpit_command_routes_to_local_queue_without_agent_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            route = {
                "matched": True,
                "confidence": "exact match",
                "pattern": "fit call",
                "work_order": {
                    "title": "fit_call_prep: Prep the fit call",
                    "owner": "revenue",
                    "priority": "high",
                    "tags": ["fit_call_prep", "message_board"],
                    "source_refs": [],
                    "allowed_actions": ["local_read"],
                    "stop_conditions": ["external_send"],
                    "definition_of_done": "Call brief is ready.",
                    "workbench": "lane",
                    "workflow": "fit_call_prep",
                    "steps": [{"id": "collect"}],
                },
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_match_command_route", return_value=route), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.dashboard_cockpit_command(backend.CockpitCommandCreate(command="Prep the fit call"))

            run.assert_not_called()
            self.assertTrue(result["success"])
            self.assertTrue(result["local_only"])
            self.assertEqual(result["token_usage_text"], "Token usage: no agent invocation")
            self.assertEqual(result["item"]["owner"], "revenue")
            self.assertEqual(result["item"]["status"], "agent_todo")
            self.assertEqual(result["item"]["source"], "dashboard/cockpit_command")
            self.assertEqual(result["item"]["context"], "Prep the fit call")
            self.assertIn("cockpit_command", result["item"]["tags"])
            self.assertEqual(result["route"]["workflow"], "fit_call_prep")

    def test_unmatched_cockpit_command_uses_existing_owner_inference_then_hermes_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unmatched = {"matched": False, "confidence": "unmatched"}
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_match_command_route", return_value=unmatched), \
                 patch.object(backend, "_run_wsl") as run:
                codex = backend.dashboard_cockpit_command(backend.CockpitCommandCreate(command="Get Codex to inspect the dashboard"))
                fallback = backend.dashboard_cockpit_command(backend.CockpitCommandCreate(command="Organize the new request"))

            run.assert_not_called()
            self.assertEqual(codex["item"]["owner"], "codex")
            self.assertEqual(codex["item"]["workbench"], "codex")
            self.assertEqual(fallback["item"]["owner"], "hermes")
            self.assertEqual(fallback["route"]["confidence"], "fallback")

    def test_verbose_cockpit_command_uses_readable_title_and_preserves_full_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unmatched = {"matched": False, "confidence": "unmatched"}
            multiline = "Audit the dashboard queue\n\nRead all relevant files first, then run the complete validation suite."
            long_single_line = "Review every relevant dashboard file and validation obligation " * 8
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_match_command_route", return_value=unmatched), \
                 patch.object(backend, "_run_wsl") as run:
                multiline_result = backend.dashboard_cockpit_command(backend.CockpitCommandCreate(command=multiline))
                long_result = backend.dashboard_cockpit_command(backend.CockpitCommandCreate(command=long_single_line))

            matched = {
                "matched": True,
                "confidence": "exact match",
                "pattern": "dashboard queue",
                "work_order": {
                    "title": f"dashboard_audit: {multiline[:90]}",
                    "owner": "operations",
                    "priority": "normal",
                    "tags": ["dashboard_audit", "message_board"],
                    "source_refs": [],
                    "allowed_actions": ["local_read"],
                    "stop_conditions": ["external_send"],
                    "definition_of_done": "Dashboard audit is complete.",
                    "workbench": "lane",
                    "workflow": "dashboard_audit",
                    "steps": [{"id": "audit"}],
                },
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_match_command_route", return_value=matched), \
                 patch.object(backend, "_run_wsl") as matched_run:
                matched_result = backend.dashboard_cockpit_command(backend.CockpitCommandCreate(command=multiline))

            run.assert_not_called()
            matched_run.assert_not_called()
            self.assertEqual(multiline_result["item"]["title"], "Audit the dashboard queue")
            self.assertEqual(multiline_result["item"]["context"], multiline)
            self.assertEqual(long_result["item"]["title"], f"{long_single_line.strip()[:117].rstrip()}...")
            self.assertLessEqual(len(long_result["item"]["title"]), 120)
            self.assertEqual(long_result["item"]["context"], long_single_line.strip())
            self.assertEqual(matched_result["item"]["title"], "dashboard_audit: Audit the dashboard queue")
            self.assertEqual(matched_result["item"]["context"], multiline)

    def test_dashboard_queue_hermes_and_department_prompts_are_local_only(self):
        owners = ("hermes", "revenue", "marketing", "delivery", "operations")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_templates(root)
            self.write_agent_cards(root)
            self.write_queue_references(root)
            created_ids = {}
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                for owner in owners:
                    created = backend.create_queue_item(backend.QueueItemCreate(
                        title=f"{owner.title()} prompt copy",
                        owner=owner,
                        context=f"Scoped {owner} context.",
                        sources=f"agents/{owner}.card.md" if owner != "hermes" else "queue/agent_registry.json",
                        allowed_actions="local_read\nlocal_edit\nlocal_test",
                        stop_conditions="external_send\nsecrets_exposure\nautomatic_launch",
                        definition_of_done=f"{owner} prompt can be copied.",
                    ))
                    created_ids[owner] = created["item"]["id"]
                prompts = {owner: backend.queue_item_prompt(created_ids[owner], owner)["prompt"] for owner in owners}

            run.assert_not_called()
            for owner, prompt in prompts.items():
                self.assertIn("PERMISSION MODE — SCOPED LOCAL TASK APPROVED", prompt)
                self.assertIn(f"- ID: {created_ids[owner]}", prompt)
                self.assertIn(f"- Title: {owner.title()} prompt copy", prompt)
                self.assertIn(f"- Owner: {owner}", prompt)
                self.assertIn("- Status: agent_todo", prompt)
                self.assertIn("queue/agent_registry.json", prompt)
                self.assertIn("context/ACCESS_MODEL.md", prompt)
                self.assertIn("queue/templates/receipt.prompt.md", prompt)
                self.assertIn("Operating Hermes", prompt)
                self.assertIn("Do not automatically launch", prompt)
                self.assertIn("Paste this prompt into Operating Hermes manually", prompt)
                self.assertIn("Token usage:", prompt)
                self.assertIn("available / unavailable from current CLI output", prompt)
            self.assertIn("coordinate directly", prompts["hermes"])
            expectations = {
                "revenue": ("agents/revenue.card.md", "Revenue Hermes Agent Card", "`revenue` department card as the scoped lane"),
                "marketing": ("agents/marketing.card.md", "Marketing Hermes Agent Card", "`marketing` department card as the scoped lane"),
                "delivery": ("agents/delivery.card.md", "Delivery Hermes Agent Card", "`delivery` department card as the scoped lane"),
                "operations": ("agents/operations.card.md", "Operations Hermes Agent Card", "`operations` department card as the scoped lane"),
            }
            for owner, expected in expectations.items():
                card_path, card_heading, lane_text = expected
                self.assertIn(card_path, prompts[owner])
                self.assertIn(card_heading, prompts[owner])
                self.assertIn(lane_text, prompts[owner])

    def test_dashboard_queue_invalid_prompt_target_returns_400_style_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                with self.assertRaises(backend.HTTPException) as raised:
                    backend.queue_item_prompt("AOS-2026-0002", "gpt")

            run.assert_not_called()
            self.assertEqual(raised.exception.status_code, 400)
            self.assertIn("invalid target", raised.exception.detail)

    def test_dashboard_queue_receipt_attach_writes_file_and_updates_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.attach_queue_item_receipt(
                    "AOS-2026-0002",
                    backend.QueueReceiptAttach(
                        receipt_text="PASS\n\nFiles touched:\n- dashboard/backend/main.py",
                        status="human_review",
                    ),
                )

            run.assert_not_called()
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "human_review")
            self.assertRegex(result["receipt_path"], r"^queue/receipts/AOS-2026-0002-\d{8}T\d{6}Z\.md$")
            self.assertFalse(Path(result["receipt_path"]).is_absolute())
            receipt_file = root / result["receipt_path"]
            self.assertTrue(receipt_file.exists())
            self.assertIn("PASS", receipt_file.read_text(encoding="utf-8"))
            item = result["item"]
            self.assertEqual(item["status"], "human_review")
            self.assertEqual(item["receipts"][0]["path"], result["receipt_path"])
            self.assertEqual(item["receipts"][0]["status"], "human_review")

    def test_dashboard_queue_review_close_marks_human_review_done_with_note_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = self.sample_queue_items()
            items[1]["status"] = "human_review"
            self.write_queue_items(root, items)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.close_queue_item_review(
                    "AOS-2026-0002",
                    backend.QueueReviewClose(action="approve", review_note="Looks good after receipt review."),
                )

            run.assert_not_called()
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "done")
            self.assertRegex(result["receipt_path"], r"^queue/receipts/AOS-2026-0002-\d{8}T\d{6}Z\.md$")
            self.assertFalse(Path(result["receipt_path"]).is_absolute())
            receipt_file = root / result["receipt_path"]
            self.assertTrue(receipt_file.exists())
            receipt_text = receipt_file.read_text(encoding="utf-8")
            self.assertIn("Review closeout:", receipt_text)
            self.assertIn("Looks good after receipt review.", receipt_text)
            item = result["item"]
            self.assertEqual(item["status"], "done")
            self.assertEqual(item["receipts"][0]["path"], result["receipt_path"])
            self.assertEqual(item["receipts"][0]["status"], "done")

    def test_human_review_detail_shows_substantive_receipt_and_note_save_cannot_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt_path = "queue/receipts/AOS-2026-0002-run.md"
            notification_path = "queue/receipts/AOS-2026-0002-notification-later.md"
            artifact_path = "workflows/queue_artifacts/AOS-2026-0002_result.md"
            (root / "queue/receipts").mkdir(parents=True)
            (root / "workflows/queue_artifacts").mkdir(parents=True)
            (root / receipt_path).write_text(
                "PASS\n\nAssigned worker: codex\nAttempts used: 2\n\nSummary for operator:\n- Actual repaired output.\n\nValidation:\n- Focused suite passed.\n\nArtifacts:\n- workflows/queue_artifacts/AOS-2026-0002_result.md\n\nBlockers:\n- None\n\nToken usage:\n- Total input: 100\n- Cached input: 80\n- Non-cached input: 20\n- Output: 10\n",
                encoding="utf-8",
            )
            (root / notification_path).write_text("Notification only\n", encoding="utf-8")
            (root / artifact_path).write_text("CONSOLIDATED ACTUAL ARTIFACT\n", encoding="utf-8")
            item = self.sample_queue_items()[1]
            item.update({
                "status": "human_review",
                "receipts": [
                    {"path": receipt_path, "status": "human_review"},
                    {"path": notification_path, "status": "human_review"},
                ],
            })
            self.write_queue_items(root, [item])
            queue_tool = backend._load_queue_tool()
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_load_queue_tool", return_value=queue_tool), \
                 patch.object(queue_tool, "finalize_done", return_value={}), \
                 patch.object(backend.aos_orchestration, "tick", return_value={"advanced": []}):
                detail = backend.queue_item(item["id"])["item"]
                note = backend.save_queue_item_review_note(
                    item["id"], backend.QueueReviewNote(review_note="Optional note only"),
                )
                after_note = backend._queue_find_item(item["id"])
                with self.assertRaises(backend.HTTPException) as generic_done:
                    backend.close_queue_item_review(
                        item["id"], backend.QueueReviewClose(status="done", review_note="No explicit action"),
                    )
                approved = backend.close_queue_item_review(
                    item["id"], backend.QueueReviewClose(status="done", action="approve", review_note="Explicit approval"),
                )

        self.assertEqual(detail["latest_receipt"]["path"], receipt_path)
        self.assertIn("Actual repaired output", detail["latest_receipt"]["content"])
        self.assertEqual(detail["review_details"]["worker"], "codex")
        self.assertEqual(detail["review_details"]["attempts"], 2)
        self.assertIn("Focused suite passed", detail["review_details"]["validation"])
        self.assertIn("Total input: 100", " ".join(detail["review_details"]["token_usage_lines"]))
        self.assertEqual(detail["primary_artifact"]["path"], artifact_path)
        self.assertIn("CONSOLIDATED ACTUAL ARTIFACT", detail["primary_artifact"]["content"])
        self.assertFalse(note["state_changed"])
        self.assertEqual(note["token_usage_text"], "Token usage: no agent invocation")
        self.assertEqual(after_note["status"], "human_review")
        self.assertEqual(generic_done.exception.status_code, 400)
        self.assertIn("explicit review action required", generic_done.exception.detail)
        self.assertEqual(approved["status"], "done")

    def test_dashboard_queue_review_close_can_mark_needs_input_or_blocked_with_note_receipt(self):
        for review_status in ("needs_input", "blocked"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                items = self.sample_queue_items()
                items[1]["status"] = "human_review"
                self.write_queue_items(root, items)
                with patch.object(backend, "BASE_DIR", root), \
                     patch.object(backend, "_run_wsl") as run:
                    result = backend.close_queue_item_review(
                        "AOS-2026-0002",
                        backend.QueueReviewClose(
                            status=review_status,
                            action="needs_changes" if review_status == "needs_input" else "block",
                            review_note=f"Set {review_status} from dashboard.",
                        ),
                    )

                run.assert_not_called()
                self.assertTrue(result["ok"])
                self.assertEqual(result["status"], review_status)
                receipt_file = root / result["receipt_path"]
                receipt_text = receipt_file.read_text(encoding="utf-8")
                self.assertIn(f"- Status: {review_status}", receipt_text)
                self.assertIn(f"Set {review_status} from dashboard.", receipt_text)
                self.assertEqual(result["item"]["status"], review_status)
                self.assertEqual(result["item"]["receipts"][0]["status"], review_status)

    def test_workflow_review_creates_one_bounded_correction_and_returns_to_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = self.sample_queue_items()[0]
            parent.update({
                "id": "AOS-2026-0200", "status": "human_review", "owner_type": "workflow",
                "owner": "hermes", "tags": ["pkg:test", "pkgver:abc", "pass:parent"],
                "sources": ["_buildout_package/workflow_definition.json"],
            })
            child = self.sample_queue_items()[1]
            child.update({
                "id": "AOS-2026-0201", "status": "done", "parent_id": parent["id"],
                "step_index": 9, "tags": ["pkg:test", "pkgver:abc", "pass:9"],
                "receipts": [{"path": "queue/receipts/pass9.md", "created_at": "2026-07-11T00:00:00Z", "status": "done"}],
            })
            self.write_queue_items(root, [parent, child])
            with patch.object(backend, "BASE_DIR", root), patch.object(backend, "_run_wsl"):
                result = backend.close_queue_item_review(
                    parent["id"], backend.QueueReviewClose(status="needs_input", action="needs_changes", review_note="Fix the final spacing and rerun everything."),
                )
                correction = result["correction_item"]
                self.assertEqual("inbox", result["status"])
                self.assertEqual("agent_todo", correction["status"])
                self.assertEqual("agent", correction["owner_type"])
                self.assertEqual("codex", correction["owner"])
                self.assertEqual("codex", correction["workbench"])
                self.assertEqual(parent["id"], correction["parent_id"])
                self.assertEqual(10, correction["step_index"])
                self.assertIn("pass:correction-1", correction["tags"])
                self.assertIn("Fix the final spacing", correction["context"])
                self.assertIn("complete validation obligation", correction["definition_of_done"])
                with self.assertRaises(backend.HTTPException) as second:
                    backend.close_queue_item_review(
                        parent["id"], backend.QueueReviewClose(status="needs_input", action="needs_changes", review_note="More changes."),
                    )
                self.assertIn("new work item or package definition version", second.exception.detail)
                rows = backend._read_queue_items()
                corr = next(row for row in rows if row["id"] == correction["id"])
                corr["status"] = "done"
                corr["receipts"] = [{"path": "queue/receipts/correction.md", "created_at": "2026-07-11T00:01:00Z", "status": "done"}]
                backend._load_queue_tool().save_items(root, rows)
                backend.aos_orchestration.tick(root, allow_telegram_escalation=False)
                self.assertEqual("human_review", backend._queue_find_item(parent["id"])["status"])
                approved = backend.close_queue_item_review(
                    parent["id"], backend.QueueReviewClose(status="done", action="approve", review_note="Approved."),
                )
                repeated = backend.close_queue_item_review(
                    parent["id"], backend.QueueReviewClose(status="done", action="approve", review_note="Approved again."),
                )
                self.assertEqual("done", approved["status"])
                self.assertEqual(approved["receipt_path"], repeated["receipt_path"])
                self.assertIn("-final-closeout-", approved["receipt_path"])
                self.assertEqual(
                    1, len(list((root / "queue/receipts").glob(f"{parent['id']}-final-closeout-*.md")))
                )

    def test_frontend_labels_workflow_correction_as_needs_changes(self):
        root = Path(__file__).resolve().parents[2]
        queue_view = (root / "dashboard/frontend/src/views/Queue.jsx").read_text(encoding="utf-8")
        review_card = (root / "dashboard/frontend/src/components/HumanReviewCard.jsx").read_text(encoding="utf-8")
        dashboard_view = (root / "dashboard/frontend/src/views/DashboardV1.jsx").read_text(encoding="utf-8")
        self.assertIn("HumanReviewCard", queue_view)
        self.assertIn("Needs changes", review_card)
        self.assertIn("needs_changes", review_card)
        self.assertIn("HumanReviewCard", dashboard_view)

    def test_dashboard_queue_review_close_rejects_non_review_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                with self.assertRaises(backend.HTTPException) as raised:
                    backend.close_queue_item_review(
                        "AOS-2026-0002",
                        backend.QueueReviewClose(action="approve", review_note="Not ready for review close."),
                    )

            run.assert_not_called()
            self.assertEqual(raised.exception.status_code, 400)
            self.assertIn("only human_review items", raised.exception.detail)
            self.assertFalse((root / "queue" / "receipts").exists())

    def test_dashboard_queue_receipt_rejects_empty_text_and_invalid_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                with self.assertRaises(backend.HTTPException) as empty:
                    backend.attach_queue_item_receipt(
                        "AOS-2026-0002",
                        backend.QueueReceiptAttach(receipt_text="  \n", status="done"),
                    )
                with self.assertRaises(backend.HTTPException) as invalid:
                    backend.attach_queue_item_receipt(
                        "AOS-2026-0002",
                        backend.QueueReceiptAttach(receipt_text="PASS", status="waiting"),
                    )

            run.assert_not_called()
            self.assertEqual(empty.exception.status_code, 400)
            self.assertIn("receipt_text must not be empty", empty.exception.detail)
            self.assertEqual(invalid.exception.status_code, 400)
            self.assertIn("invalid status", invalid.exception.detail)
            self.assertFalse((root / "queue" / "receipts").exists())

    def test_dashboard_queue_fallback_refuses_done_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            fallback = backend._QueueToolFallback()

            with patch.object(backend, "BASE_DIR", root):
                updated = fallback.update_status(root, "AOS-2026-0002", "human_review")
                with self.assertRaises(ValueError) as status_done:
                    fallback.update_status(root, "AOS-2026-0002", "done")
                with self.assertRaises(ValueError) as receipt_done:
                    fallback.attach_receipt(root, "AOS-2026-0002", "queue/receipts/unit.md", "done")

            self.assertEqual(updated["status"], "human_review")
            self.assertIn("finalize_done", str(status_done.exception))
            self.assertIn("finalize_done", str(receipt_done.exception))
            items = [json.loads(line) for line in (root / "queue" / "work_items.jsonl").read_text(encoding="utf-8").splitlines()]
            item = next(item for item in items if item["id"] == "AOS-2026-0002")
            self.assertEqual(item["status"], "human_review")
            self.assertEqual(item.get("receipts"), None)

    def test_dashboard_queue_receipt_view_reads_only_receipt_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt_dir = root / "queue" / "receipts"
            receipt_dir.mkdir(parents=True)
            (receipt_dir / "unit.md").write_text("PASS\n\nReceipt body.\n", encoding="utf-8")
            (root / "queue" / "outside.md").write_text("outside\n", encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.queue_receipt("queue/receipts/unit.md")
                with self.assertRaises(backend.HTTPException) as traversal:
                    backend.queue_receipt("queue/receipts/../outside.md")
                with self.assertRaises(backend.HTTPException) as absolute:
                    backend.queue_receipt(str(receipt_dir / "unit.md"))

            run.assert_not_called()
            self.assertEqual(result["path"], "queue/receipts/unit.md")
            self.assertIn("Receipt body.", result["content"])
            self.assertEqual(traversal.exception.status_code, 400)
            self.assertIn("queue/receipts", traversal.exception.detail)
            self.assertEqual(absolute.exception.status_code, 400)
            self.assertIn("root-relative", absolute.exception.detail)

    def test_dashboard_queue_item_includes_latest_receipt_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = self.sample_queue_items()
            items[1]["status"] = "done"
            items[1]["receipts"] = [
                {"path": "queue/receipts/old.md", "status": "human_review", "created_at": "2026-07-05T10:05:00Z"},
                {"path": "queue/receipts/latest.md", "status": "done", "created_at": "2026-07-05T10:06:00Z"},
            ]
            self.write_queue_items(root, items)
            receipt_dir = root / "queue" / "receipts"
            receipt_dir.mkdir(parents=True)
            (receipt_dir / "latest.md").write_text(
                "PASS\n\nFiles touched:\n- dashboard/frontend/src/views/Queue.jsx\n\nValidation:\n- unit tests\n",
                encoding="utf-8",
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.queue_item("AOS-2026-0002")

            run.assert_not_called()
            latest = result["item"]["latest_receipt"]
            self.assertEqual(latest["path"], "queue/receipts/latest.md")
            self.assertEqual(latest["status"], "done")
            self.assertIn("PASS", latest["summary"])
            self.assertIn("dashboard/frontend/src/views/Queue.jsx", latest["summary"])

    def test_dashboard_queue_exact_sidecar_outranks_receipt_unavailable_and_no_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = self.sample_queue_items()
            items[1]["status"] = "human_review"
            items[1]["receipts"] = [
                {"path": "queue/receipts/latest.md", "status": "human_review", "created_at": "2026-07-12T00:00:00Z"},
            ]
            self.write_queue_items(root, items)
            receipt_dir = root / "queue" / "receipts"
            receipt_dir.mkdir(parents=True)
            (receipt_dir / "latest.md").write_text(
                "PASS\n\nToken usage: unavailable from current CLI output.\nToken usage: no agent invocation\n",
                encoding="utf-8",
            )
            exact = {
                "token_usage": {
                    "orchestrator": {"input": 0, "output": 0},
                    "subagents": [],
                    "workbenches": [{"tool": "codex", "session_id": "session-proof", "input": 20, "output": 10, "source": "reported"}],
                    "totals": {"input": 20, "output": 10},
                    "est_cost_usd": 0.0,
                    "unavailable": ["Codex model identity"],
                },
                "profile_invocation": {"invoked": True, "session_id": "session-proof"},
                "capture_evidence": {
                    "input_tokens": 20, "output_tokens": 10, "total_tokens": 30,
                    "cached_input_tokens": 100, "reasoning_output_tokens": 4,
                    "model_identity": "unavailable",
                },
            }
            (receipt_dir / "AOS-2026-0002.token_usage.json").write_text(json.dumps(exact), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), patch.object(backend, "_run_wsl") as run:
                result = backend.queue_item("AOS-2026-0002")

            run.assert_not_called()
            latest = result["item"]["latest_receipt"]
            self.assertEqual("exact", latest["token_usage_precedence"])
            self.assertEqual([
                "Token usage: exact", "Input: 20", "Output: 10", "Total: 30",
                "Cached input: 100", "Reasoning output (subset of output): 4", "Model: unavailable",
            ], latest["token_usage_lines"])

    def test_dashboard_ledger_exact_precedence_deduplicates_identity_and_suppresses_placeholder(self):
        unavailable = {
            "item_id": "AOS-2026-0002", "session_id": "session-proof",
            "token_usage": {"workbenches": [{"tool": "codex", "source": "unavailable", "input": 0, "output": 0}], "totals": {"input": 0, "output": 0}, "unavailable": ["Codex token usage"]},
        }
        exact = {
            "item_id": "AOS-2026-0002", "session_id": "session-proof",
            "token_usage": {"workbenches": [{"tool": "codex", "source": "reported", "input": 20, "output": 10}], "totals": {"input": 20, "output": 10}, "unavailable": []},
        }
        no_agent = {
            "item_id": "AOS-2026-0002",
            "token_usage": {"workbenches": [], "totals": {"input": 0, "output": 0}, "unavailable": ["no agent invocation"]},
        }
        effective = backend._effective_token_ledger_records([unavailable, no_agent, exact])
        self.assertEqual([exact], effective)

    def test_dashboard_queue_artifact_reads_safe_local_text_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "workflows" / "revenue_linkedin_outreach" / "output"
            output.mkdir(parents=True)
            artifact_file = output / "unit.md"
            artifact_file.write_text("PASS\n\nToken usage:\n- unavailable from current CLI output\n", encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.queue_artifact("workflows/revenue_linkedin_outreach/output/unit.md")

            run.assert_not_called()
            self.assertTrue(result["success"])
            self.assertTrue(result["available"])
            self.assertEqual(result["path"], "workflows/revenue_linkedin_outreach/output/unit.md")
            self.assertIn("PASS", result["content"])
            self.assertIn("Token usage:", result["token_usage_lines"])
            self.assertIn("- unavailable from current CLI output", result["token_usage_lines"])
            self.assertFalse(Path(result["path"]).is_absolute())

    def test_dashboard_queue_artifact_blocks_secret_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            (root / "logs" / "unit.log").write_text("wrong extension\n", encoding="utf-8")
            (root / "workflows").mkdir()
            (root / "workflows" / ".env").write_text("SECRET=value\n", encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                secret = backend.queue_artifact("workflows/.env")
                traversal = backend.queue_artifact("workflows/../logs/unit.log")
                missing = backend.queue_artifact("results/missing.md")

            run.assert_not_called()
            self.assertFalse(secret["success"])
            self.assertIn("secret", secret["reason"])
            self.assertFalse(traversal["success"])
            self.assertTrue("only .md" in traversal["reason"] or "must stay" in traversal["reason"])
            self.assertFalse(missing["success"])
            self.assertIn("not found", missing["reason"])

    def test_dashboard_queue_item_exposes_run_artifact_refs_from_latest_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = self.sample_queue_items()
            items[1]["status"] = "human_review"
            items[1]["receipts"] = [
                {"path": "queue/receipts/latest.md", "status": "human_review", "created_at": "2026-07-05T10:06:00Z"},
            ]
            self.write_queue_items(root, items)
            receipt_dir = root / "queue" / "receipts"
            receipt_dir.mkdir(parents=True)
            artifact_dir = root / "workflows" / "revenue_linkedin_outreach" / "output"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "angles.md").write_text("Draft artifact\n", encoding="utf-8")
            (receipt_dir / "latest.md").write_text(
                "PASS\n\nFiles touched:\n- workflows/revenue_linkedin_outreach/output/angles.md\n\nToken usage:\n- unavailable from current CLI output\n",
                encoding="utf-8",
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.queue_item("AOS-2026-0002")

            run.assert_not_called()
            item = result["item"]
            self.assertEqual(item["latest_receipt"]["path"], "queue/receipts/latest.md")
            self.assertIn("PASS", item["latest_receipt"]["content"])
            self.assertIn("- unavailable from current CLI output", item["latest_receipt"]["token_usage_lines"])
            artifact_paths = [artifact["path"] for artifact in item["run_artifacts"]]
            self.assertIn("queue/receipts/latest.md", artifact_paths)
            self.assertIn("workflows/revenue_linkedin_outreach/output/angles.md", artifact_paths)
            output_ref = next(artifact for artifact in item["run_artifacts"] if artifact["path"].endswith("angles.md"))
            self.assertTrue(output_ref["available"])

    def test_dashboard_skills_parse_frontmatter_name_description_and_clean_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / "skills" / "aoa_working_session"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: aoa_working_session\n"
                "description: Prep and follow up one working session.\n"
                "lane: delivery\n"
                "status: watch\n"
                "source: aos-delivery\n"
                "trust: watch\n"
                "version: v1\n"
                "---\n"
                "# /aoa-working-session\n\nBody text.\n",
                encoding="utf-8",
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "SKILLS_DIR", root / "skills"), \
                 patch.object(backend, "SKILL_TRUST_FILE", root / "queue" / "skill_trust.jsonl"), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.dashboard_skills()

            run.assert_not_called()
            self.assertEqual(len(result["skills"]), 1)
            skill = result["skills"][0]
            self.assertEqual(skill["name"], "aoa_working_session")
            self.assertEqual(skill["description"], "Prep and follow up one working session.")
            self.assertEqual(skill["lane"], "delivery")
            self.assertEqual(skill["status"], "watch")
            self.assertEqual(skill["source"], "aos-delivery")
            self.assertEqual(skill["trust"], "watch")
            self.assertEqual(skill["version"], "v1")
            self.assertNotEqual(skill["name"], "---")
            self.assertNotIn("---", skill["content"].splitlines()[:2])
            self.assertIn("Body text.", skill["preview"])

    def test_token_rows_sort_by_real_time_and_keep_invalid_timestamps_last_stably(self):
        rows = [
            {"item_id": "Z", "timestamp": "bad", "event": "malformed"},
            {"item_id": "A", "timestamp": "2026-07-12T10:00:00-07:00", "event": "same-b"},
            {"item_id": "B", "timestamp": "2026-07-12T17:00:00Z", "event": "same-a"},
            {"item_id": "C", "timestamp": "2026-07-12T18:00:00Z", "event": "newest"},
            {"item_id": "D", "event": "missing"},
        ]
        first = backend._sort_token_records_newest(rows)
        second = backend._sort_token_records_newest(list(reversed(rows)))
        self.assertEqual(["C", "B", "A", "Z", "D"], [row["item_id"] for row in first])
        self.assertEqual([row["item_id"] for row in first], [row["item_id"] for row in second])
        self.assertEqual(
            backend._parse_record_timestamp(first[1]["timestamp"]),
            backend._parse_record_timestamp(first[2]["timestamp"]),
        )

    def test_token_source_requires_explicit_invocation_evidence(self):
        owner_only = {"item_id": "owner", "owner": "codex", "lane": "codex", "workbench": "codex", "token_usage": {"totals": {"input": 4, "output": 2}, "unavailable": []}}
        reported = {"item_id": "reported", "token_usage": {"totals": {"input": 4, "output": 2}, "workbenches": [{"tool": "codex", "source": "reported", "input": 4, "output": 2}], "unavailable": []}}
        deterministic = {"item_id": "local", "token_usage": {"totals": {"input": 0, "output": 0}, "unavailable": ["no agent invocation"]}}
        unavailable = {"item_id": "gap", "token_usage": {"unavailable": ["usage unavailable"]}}
        self.assertEqual(("Unattributed", "no authoritative invocation source"), backend._token_invocation_source(owner_only))
        self.assertEqual("Codex", backend._token_invocation_source(reported)[0])
        self.assertEqual("No agent invocation", backend._token_invocation_source(deterministic)[0])
        views = [backend._token_record_view(row) for row in (owner_only, reported, deterministic, unavailable)]
        self.assertEqual(["exact", "exact", "no_agent_invocation", "unavailable"], [row["availability_state"] for row in views])

    def test_queue_color_attribution_uses_invocation_evidence_not_routing_metadata(self):
        records = [
            {
                "item_id": "AOS-2026-0085",
                "timestamp": "2026-07-13T01:08:22Z",
                "owner": "hermes",
                "lane": "operations",
                "workbench": "hermes",
                "token_usage": {
                    "totals": {"input": 12, "output": 3},
                    "workbenches": [{"tool": "codex", "source": "reported", "input": 12, "output": 3}],
                    "unavailable": [],
                },
            },
            {
                "item_id": "owner-only",
                "timestamp": "2026-07-13T01:09:22Z",
                "owner": "codex",
                "lane": "codex",
                "workbench": "codex",
                "token_usage": {"totals": {"input": 0, "output": 0}, "unavailable": ["usage unavailable"]},
            },
        ]
        attributions = backend._queue_invocation_attributions(records)
        self.assertEqual("Codex", attributions["AOS-2026-0085"]["invocation_source"])
        self.assertEqual("reported workbench invocation", attributions["AOS-2026-0085"]["invocation_source_evidence"])
        self.assertNotIn("owner-only", attributions)
        public = backend._queue_public_item(
            {"id": "AOS-2026-0085", "owner": "hermes", "workbench": "hermes", "status": "done"},
            attributions,
        )
        self.assertEqual("Codex", public["invocation_source"])

    def test_token_source_summary_preserves_cached_and_reasoning_semantics(self):
        row = {
            "item_id": "AOS-2026-0078", "session_id": "session-proof", "timestamp": "2026-07-12T21:42:32Z",
            "capture_evidence": {"cached_input_tokens": 100, "reasoning_output_tokens": 4},
            "token_usage": {"totals": {"input": 20, "output": 10}, "workbenches": [{"tool": "codex", "source": "reported", "input": 20, "output": 10}], "unavailable": []},
        }
        codex = next(group for group in backend._token_source_summary([row]) if group["source"] == "Codex")
        self.assertEqual((20, 10, 30), (codex["input"], codex["output"], codex["total"]))
        self.assertEqual(100, codex["cached_input"])
        self.assertEqual(4, codex["reasoning_output"])

    def test_token_source_summary_tolerates_unavailable_cached_input_component(self):
        row = {
            "item_id": "AOS-2026-0079", "session_id": "session-cached-gap", "timestamp": "2026-07-19T21:42:32Z",
            "capture_evidence": {"cached_input_tokens": backend.UNAVAILABLE_CLI_VALUE, "reasoning_output_tokens": 4},
            "token_usage": {"totals": {"input": 20, "output": 10}, "workbenches": [{"tool": "codex", "source": "reported", "input": 20, "output": 10}], "unavailable": []},
        }
        codex = next(group for group in backend._token_source_summary([row]) if group["source"] == "Codex")
        self.assertEqual(0, codex["cached_input"])
        self.assertEqual(4, codex["reasoning_output"])
        self.assertEqual(1, codex["exact_rows"])

    def test_token_source_summary_tolerates_unavailable_reasoning_output_component(self):
        row = {
            "item_id": "AOS-2026-0080", "session_id": "session-reasoning-gap", "timestamp": "2026-07-19T21:43:32Z",
            "capture_evidence": {"cached_input_tokens": 100, "reasoning_output_tokens": backend.UNAVAILABLE_CLI_VALUE},
            "token_usage": {"totals": {"input": 20, "output": 10}, "workbenches": [{"tool": "codex", "source": "reported", "input": 20, "output": 10}], "unavailable": []},
        }
        codex = next(group for group in backend._token_source_summary([row]) if group["source"] == "Codex")
        self.assertEqual(100, codex["cached_input"])
        self.assertEqual(0, codex["reasoning_output"])
        self.assertEqual(1, codex["exact_rows"])

    def test_token_source_summary_aggregates_mixed_exact_and_unavailable_rows(self):
        exact_row = {
            "item_id": "AOS-2026-0081", "session_id": "session-exact", "timestamp": "2026-07-19T21:44:32Z",
            "capture_evidence": {"cached_input_tokens": 50, "reasoning_output_tokens": 6},
            "token_usage": {"totals": {"input": 20, "output": 10}, "workbenches": [{"tool": "codex", "source": "reported", "input": 20, "output": 10}], "unavailable": []},
        }
        gap_row = {
            "item_id": "AOS-2026-0082", "session_id": "session-gap", "timestamp": "2026-07-19T21:45:32Z",
            "capture_evidence": {"cached_input_tokens": backend.UNAVAILABLE_CLI_VALUE, "reasoning_output_tokens": backend.UNAVAILABLE_CLI_VALUE},
            "token_usage": {"totals": {"input": 30, "output": 15}, "workbenches": [{"tool": "codex", "source": "reported", "input": 30, "output": 15}], "unavailable": []},
        }
        codex = next(group for group in backend._token_source_summary([exact_row, gap_row]) if group["source"] == "Codex")
        self.assertEqual(2, codex["exact_rows"])
        self.assertEqual(50, codex["cached_input"])
        self.assertEqual(6, codex["reasoning_output"])
        self.assertEqual(50, codex["input"])
        self.assertEqual(25, codex["output"])
        self.assertEqual(75, codex["total"])

    def test_dashboard_tokens_endpoint_returns_200_with_unavailable_cached_component_row(self):
        gap_row = {
            "item_id": "AOS-2026-0083", "session_id": "session-endpoint-gap", "timestamp": "2026-07-19T21:46:32Z",
            "capture_evidence": {"cached_input_tokens": backend.UNAVAILABLE_CLI_VALUE, "reasoning_output_tokens": backend.UNAVAILABLE_CLI_VALUE},
            "token_usage": {"totals": {"input": 20, "output": 10}, "workbenches": [{"tool": "codex", "source": "reported", "input": 20, "output": 10}], "unavailable": []},
        }
        with patch.object(backend, "_read_token_ledger_records", return_value=[gap_row]):
            result = backend.dashboard_tokens()
        codex = next(group for group in result["source_summary"] if group["source"] == "Codex")
        self.assertEqual(0, codex["cached_input"])
        self.assertEqual(0, codex["reasoning_output"])
        record = next(item for item in result["records"] if item["item_id"] == "AOS-2026-0083")
        self.assertEqual(backend.UNAVAILABLE_CLI_VALUE, record["cached_input_tokens"])
        self.assertEqual(backend.UNAVAILABLE_CLI_VALUE, record["reasoning_output_tokens"])

    def test_workflow_name_fallback_chain_ignores_frontmatter_delimiters(self):
        path = Path("workflows/unit/workflow.md")
        cases = [
            ("---\ntitle: Explicit title\nname: Other\n---\n# Heading", "opaque-123456789012345678901234", {}, "Explicit title"),
            ("---\nname: Explicit name\n---\n# Heading", "opaque-123456789012345678901234", {}, "Explicit name"),
            ("# Heading", "revenue_sales_prep", {}, "Revenue Sales Prep"),
            ("# Heading fallback", "0123456789abcdef0123456789abcdef", {}, "Heading fallback"),
            ("---\nbad metadata\n---\n", "0123456789abcdef0123456789abcdef", {}, "Unit"),
            ("", "0123456789abcdef0123456789abcdef", {}, "Unit"),
        ]
        for text, workflow_id, metadata, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(expected, backend._workflow_display_name(path, text, workflow_id, metadata))
                self.assertEqual(expected, backend._workflow_display_name(path, text, workflow_id, metadata))
                self.assertNotEqual("---", expected)
        duplicate_text = "---\ntitle: Shared operator name\n---\n# One\n"
        self.assertEqual(
            backend._workflow_display_name(Path("workflows/one/workflow.md"), duplicate_text, "one"),
            backend._workflow_display_name(Path("workflows/two/workflow.md"), duplicate_text, "two"),
        )

    def test_workflow_editor_disposable_save_reload_stale_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "workflows" / "fixture" / "workflow.md"
            target.parent.mkdir(parents=True)
            original = "---\ntitle: Fixture workflow\n---\n# Fixture\n\nOriginal.\n"
            target.write_text(original, encoding="utf-8")
            target.chmod(0o640)
            with patch.object(backend, "BASE_DIR", root), patch.object(backend, "_run_wsl") as run:
                loaded = backend.dashboard_workflow("fixture")
                edited = original.replace("Original.", "Edited safely.")
                saved = backend.dashboard_save_workflow(backend.DashboardWorkflowSave(workflow_id="fixture", content=edited, expected_revision=loaded["revision"]))
                reloaded = backend.dashboard_workflow("fixture")
                with self.assertRaises(backend.HTTPException) as stale:
                    backend.dashboard_save_workflow(backend.DashboardWorkflowSave(workflow_id="fixture", content=original, expected_revision=loaded["revision"]))
                before_invalid = target.read_bytes()
                with self.assertRaises(backend.HTTPException) as invalid:
                    backend.dashboard_save_workflow(backend.DashboardWorkflowSave(workflow_id="fixture", content="   ", expected_revision=reloaded["revision"]))
            run.assert_not_called()
            self.assertFalse(saved["executed"])
            self.assertEqual(edited, reloaded["content"])
            self.assertEqual(before_invalid, target.read_bytes())
            self.assertEqual(0o640, target.stat().st_mode & 0o777)
            self.assertEqual(409, stale.exception.status_code)
            self.assertEqual(400, invalid.exception.status_code)

    def test_workflow_bench_uses_shared_names_and_marks_noncanonical_sources_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / "workflows" / "canonical" / "workflow.md"
            canonical.parent.mkdir(parents=True)
            canonical.write_text("---\ntitle: Canonical title\n---\n# Ignored heading\n", encoding="utf-8")
            readme = root / "workflows" / "reference" / "README.md"
            readme.parent.mkdir(parents=True)
            readme.write_text("# Reference workflow\n", encoding="utf-8")
            (root / "workflows" / "workflow_registry.json").write_text(json.dumps({"workflows": [
                {"id": "canonical", "name": "Registry name", "source_path": "workflows/canonical/workflow.md", "owner_agent": "Operations"},
                {"id": "reference", "name": "Reference from registry", "source_path": "workflows/reference/README.md", "owner_agent": "Delivery"},
            ]}), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), patch.object(backend, "_run_wsl") as run:
                result = backend.dashboard_workflows()
            run.assert_not_called()
            by_id = {row["id"]: row for row in result["workflows"]}
            self.assertEqual("Canonical title", by_id["canonical"]["name"])
            self.assertTrue(by_id["canonical"]["editable"])
            self.assertEqual("Reference from registry", by_id["reference"]["name"])
            self.assertFalse(by_id["reference"]["editable"])
            self.assertIn("canonical", by_id["reference"]["read_only_reason"].lower())
            self.assertNotIn("---", [row["name"] for row in result["workflows"]])

    def test_workflow_editor_rejects_unsafe_identifiers_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workflows").mkdir()
            outside = root / "outside.md"
            outside.write_text("# Outside\n", encoding="utf-8")
            link_dir = root / "workflows" / "linked"
            link_dir.mkdir()
            (link_dir / "workflow.md").symlink_to(outside)
            directory_target = root / "workflows" / "directory" / "workflow.md"
            directory_target.mkdir(parents=True)
            with patch.object(backend, "BASE_DIR", root), patch.object(backend, "_run_wsl") as run:
                for workflow_id in ("../outside", str(outside), "fixture.txt", "tokens"):
                    with self.subTest(workflow_id=workflow_id):
                        with self.assertRaises((ValueError, FileNotFoundError)):
                            backend._workflow_path_for_id(workflow_id, writable=True)
                with self.assertRaises(ValueError):
                    backend._workflow_path_for_id("linked", writable=True)
                with self.assertRaises(ValueError):
                    backend._workflow_path_for_id("directory", writable=True)
            run.assert_not_called()
            self.assertEqual("# Outside\n", outside.read_text(encoding="utf-8"))

    def test_dashboard_skill_save_preserves_frontmatter_and_updates_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_file = root / "skills" / "unit_skill" / "SKILL.md"
            skill_file.parent.mkdir(parents=True)
            skill_file.write_text(
                "---\n"
                "name: unit_skill\n"
                "description: Old description.\n"
                "lane: operations\n"
                "trust: watch\n"
                "---\n"
                "# Old body\n",
                encoding="utf-8",
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.dashboard_save_skill(backend.DashboardSkillSave(
                    path="skills/unit_skill/SKILL.md",
                    name="unit_skill_updated",
                    description="New description.",
                    body="# New body\n\nEdited from dashboard.",
                ))

            run.assert_not_called()
            saved = skill_file.read_text(encoding="utf-8")
            self.assertTrue(result["success"])
            self.assertEqual(result["name"], "unit_skill_updated")
            self.assertIn("---\nname: unit_skill_updated\n", saved)
            self.assertIn("description: New description.", saved)
            self.assertIn("lane: operations", saved)
            self.assertIn("trust: watch", saved)
            self.assertIn("# New body", saved)
            self.assertEqual(saved.count("---"), 2)

    def test_dashboard_skill_save_refuses_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blocked_paths = [
                "../outside/SKILL.md",
                "skills/.env",
                "connectors/telegram_bridge/secret.md",
                "pilots/northshore_honda_sales_demo/SKILL.md",
                "old_runtime/skills/unit/SKILL.md",
                str(root / "skills" / "absolute" / "SKILL.md"),
            ]
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                for path in blocked_paths:
                    with self.subTest(path=path):
                        with self.assertRaises(backend.HTTPException) as raised:
                            backend.dashboard_save_skill(backend.DashboardSkillSave(
                                path=path,
                                name="blocked",
                                description="blocked",
                                body="blocked",
                            ))
                        self.assertEqual(raised.exception.status_code, 400)

            run.assert_not_called()

    def test_hermes_review_prompt_uses_dashboard_artifact_path_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = {
                "id": "AOS-2026-0021",
                "title": "Revenue artifact path check",
                "owner": "revenue",
                "context": "Verify output exists before review.",
                "definition_of_done": "Produce the artifact.",
                "stop_conditions": ["external_send"],
            }
            artifact_path = root / "workflows" / "revenue_linkedin_outreach" / "output"
            artifact_path.mkdir(parents=True)
            (artifact_path / "AOS-2026-0021_ttr_sme_outreach_angle_pack.md").write_text("Revenue artifact body\n", encoding="utf-8")
            worker_result = {
                "output": "PASS\nFiles touched: workflows/revenue_linkedin_outreach/output/AOS-2026-0021_ttr_sme_outreach_angle_pack.md\nValidation: local check\nBlockers: None\nNext action: Liam review",
            }
            with patch.object(backend, "BASE_DIR", root):
                prompt = backend._queue_hermes_review_prompt(item, "revenue", 1, worker_result)

        self.assertIn("Local artifact verification from repo root", prompt)
        self.assertIn("AVAILABLE: workflows/revenue_linkedin_outreach/output/AOS-2026-0021_ttr_sme_outreach_angle_pack.md", prompt)
        self.assertIn("Revenue artifact body", prompt)
        self.assertIn("Do not claim an artifact is missing", prompt)

    def test_reviewer_receives_final_artifact_instead_of_worker_transcript(self):
        item = {
            "id": "AOS-2026-0206", "title": "Reviewer input regression", "owner": "claude",
            "context": "Require exact route evidence.", "definition_of_done": "Produce proof.",
            "stop_conditions": ["external_send"],
        }
        full = "\n".join((
            "PASS",
            "Files touched: workflows/queue_artifacts/AOS-2026-0206_proof.md",
            "Validation: pwd -> /home/liam/agentic-os-live",
            "git rev-parse --show-toplevel -> /home/liam/agentic-os-live",
            "/home/liam/.local/npm/bin/claude --version -> 2.1.207 (Claude Code)",
            "Artifacts: workflows/queue_artifacts/AOS-2026-0206_proof.md",
            "Blockers: None",
        ))
        worker_result = {
            "output": "PASS\nFiles touched: workflows/queue_artifacts/AOS-2026-0206_proof.md\nValidation: pwd only",
            "review_output": full,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "workflows" / "queue_artifacts" / "AOS-2026-0206_proof.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("proof\n", encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root):
                prompt = backend._queue_hermes_review_prompt(item, "claude", 1, worker_result)
        self.assertIn("Final artifact: workflows/queue_artifacts/AOS-2026-0206_proof.md", prompt)
        self.assertIn("proof", prompt)
        self.assertNotIn("git rev-parse --show-toplevel", prompt)
        self.assertNotIn("2.1.207 (Claude Code)", prompt)

    def test_canonical_artifact_normalization_containment_resolution_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "workflows" / "queue_artifacts" / "proof.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("CANONICAL_ARTIFACT_OK\n", encoding="utf-8")
            outside = root.parent / f"{root.name}-outside.md"
            outside.write_text("outside\n", encoding="utf-8")
            escape = artifact.parent / "escape.md"
            escape.symlink_to(outside)
            try:
                with patch.object(backend, "BASE_DIR", root):
                    self.assertEqual(
                        backend._queue_normalize_artifact_path("./workflows/queue_artifacts/proof.md"),
                        "workflows/queue_artifacts/proof.md",
                    )
                    self.assertEqual(
                        backend._queue_normalize_artifact_path(r"workflows\queue_artifacts\proof.md"),
                        "workflows/queue_artifacts/proof.md",
                    )
                    resolved = backend._queue_read_artifact("workflows/queue_artifacts/proof.md")
                    with self.assertRaisesRegex(ValueError, "authoritative Linux workspace"):
                        backend._queue_normalize_artifact_path("../outside.md")
                    with self.assertRaisesRegex(ValueError, "authoritative Linux workspace"):
                        backend._queue_normalize_artifact_path(str(artifact))
                    with self.assertRaisesRegex(ValueError, "authoritative Linux workspace"):
                        backend._queue_read_artifact("workflows/queue_artifacts/escape.md")
            finally:
                outside.unlink(missing_ok=True)
        self.assertEqual(resolved["path"], "workflows/queue_artifacts/proof.md")
        self.assertEqual(resolved["sha256"], "8cf5278a792e55b3d24b94e71f31f63e6089469951cd1e7cfdbaa308c25a800c")

    def test_aos_0156_regression_canonical_artifact_overrules_false_path_revise_without_retry(self):
        work = self.approval_item("AOS-2026-0201", "agent_todo", title="Claude canonical artifact regression")
        work.update({"owner": "claude", "source": "unit", "tags": ["async_dispatch"]})
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [work])
            self.write_queue_templates(root)
            with patch.object(backend, "BASE_DIR", root):
                artifact_path = backend._queue_default_artifact_path(work)

                def worker(*args):
                    calls.append(args)
                    target = root / artifact_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("CLAUDE_CANONICAL_REGRESSION_OK\n", encoding="utf-8")
                    return {
                        "success": True,
                        "output": f"PASS\nFiles touched: {artifact_path}\nValidation: canonical fixture\nBlockers: None\nNext action: Review",
                        "returncode": 0,
                        "token_usage_text": "Token usage: unavailable from current CLI output",
                        "token_usage": {"available": False},
                    }

                review = {
                    "success": True,
                    "output": f"REVISE: artifact not found at an old workspace path: {artifact_path}",
                    "returncode": 0,
                    "token_usage_text": "Token usage: unavailable from current CLI output",
                    "token_usage": {"available": False},
                }
                with patch.object(backend, "_queue_run_worker", side_effect=worker), \
                     patch.object(backend, "_queue_run_hermes_review", return_value=review), \
                     patch.object(backend, "_queue_resolve_route_metadata", return_value=self.route_metadata_fixture("claude")), \
                     patch.object(backend, "_notify_queue_completion", return_value=None):
                    result = backend.run_queue_item(work["id"])
                    saved = backend._queue_find_item(work["id"])
                    receipt = (root / result["receipt_path"]).read_text(encoding="utf-8")
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["attempts_used"], 1)
        self.assertTrue(result["success"])
        self.assertEqual(result["hermes_review"]["decision"], "PASS")
        self.assertEqual(saved["status"], "human_review")
        self.assertIn("AVAILABLE:", receipt)
        self.assertIn("sha256", receipt)

    def test_claimed_but_genuinely_absent_artifact_is_rejected_without_retry(self):
        work = self.approval_item("AOS-2026-0202", "agent_todo", title="Missing artifact regression")
        work.update({"owner": "claude", "source": "unit", "tags": ["async_dispatch"]})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [work])
            self.write_queue_templates(root)
            with patch.object(backend, "BASE_DIR", root):
                artifact_path = backend._queue_default_artifact_path(work)
                worker_result = {
                    "success": True,
                    "output": f"PASS\nFiles touched: {artifact_path}\nValidation: claimed only\nBlockers: None",
                    "returncode": 0,
                    "token_usage_text": "Token usage: unavailable from current CLI output",
                    "token_usage": {"available": False},
                }
                review = {
                    "success": True, "output": "PASS", "returncode": 0,
                    "token_usage_text": "Token usage: unavailable from current CLI output",
                    "token_usage": {"available": False},
                }
                with patch.object(backend, "_queue_run_worker", return_value=worker_result) as worker, \
                     patch.object(backend, "_queue_run_hermes_review", return_value=review), \
                     patch.object(backend, "_queue_resolve_route_metadata", return_value=self.route_metadata_fixture("claude")), \
                     patch.object(backend, "_notify_queue_completion", return_value=None):
                    result = backend.run_queue_item(work["id"])
                    receipt = (root / result["receipt_path"]).read_text(encoding="utf-8")
        self.assertEqual(worker.call_count, 1)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "needs_input")
        self.assertIn("Claimed canonical artifact is genuinely absent", receipt)

    def test_status_read_remains_responsive_while_controlled_worker_is_active(self):
        work = self.approval_item("AOS-2026-0203", "agent_todo", title="Active status fixture")
        work.update({"owner": "claude", "source": "unit", "tags": ["async_dispatch"]})
        entered = threading.Event()
        release = threading.Event()
        result_holder = {}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [work])
            self.write_queue_templates(root)
            with patch.object(backend, "BASE_DIR", root):
                artifact_path = backend._queue_default_artifact_path(work)

                def worker(*args):
                    entered.set()
                    release.wait(2)
                    target = root / artifact_path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("STATUS_ACTIVE_OK\n", encoding="utf-8")
                    return {
                        "success": True,
                        "output": f"PASS\nFiles touched: {artifact_path}\nValidation: status active\nBlockers: None",
                        "returncode": 0,
                        "token_usage_text": "Token usage: unavailable from current CLI output",
                        "token_usage": {"available": False},
                    }

                review = {
                    "success": True, "output": "PASS", "returncode": 0,
                    "token_usage_text": "Token usage: unavailable from current CLI output",
                    "token_usage": {"available": False},
                }
                with patch.object(backend, "_queue_run_worker", side_effect=worker), \
                     patch.object(backend, "_queue_run_hermes_review", return_value=review), \
                     patch.object(backend, "_queue_resolve_route_metadata", return_value=self.route_metadata_fixture("claude")), \
                     patch.object(backend, "_notify_queue_completion", return_value=None):
                    thread = threading.Thread(target=lambda: result_holder.setdefault("result", backend.run_queue_item(work["id"])))
                    thread.start()
                    self.assertTrue(entered.wait(1))
                    started = time.monotonic()
                    status = backend._queue_status_closeout()
                    elapsed = time.monotonic() - started
                    release.set()
                    thread.join(timeout=3)
        self.assertLess(elapsed, 0.2)
        self.assertIn("agent_working", status["output"])
        self.assertFalse(thread.is_alive())
        self.assertTrue(result_holder["result"]["success"])

    def test_dashboard_queue_status_endpoint_updates_item_and_rejects_invalid_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.update_queue_item_status(
                    "AOS-2026-0001",
                    backend.QueueStatusUpdate(status="agent_working"),
                )
                shown = backend.queue_item("AOS-2026-0001")
                with self.assertRaises(backend.HTTPException) as invalid:
                    backend.update_queue_item_status(
                        "AOS-2026-0001",
                        backend.QueueStatusUpdate(status="waiting"),
                    )

            run.assert_not_called()
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "agent_working")
            self.assertEqual(shown["item"]["status"], "agent_working")
            self.assertEqual(invalid.exception.status_code, 400)
            self.assertIn("invalid status", invalid.exception.detail)

    def test_queue_item_run_calls_assigned_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            self.write_queue_templates(root)
            worker_result = {
                "success": True,
                "output": "PASS\nFiles touched: dashboard/backend/main.py\nValidation: unit tests\nBlockers: None\nNext action: Review",
                "returncode": 0,
                "token_usage_text": "Token usage: total 12",
                "token_usage": {"available": True, "total_tokens": "12"},
            }
            review_result = {
                "success": True,
                "output": "PASS",
                "returncode": 0,
                "token_usage_text": "Token usage: unavailable from current CLI output",
                "token_usage": {"available": False},
                "invocation": {
                    "executable": "/home/liam/.local/npm/bin/codex",
                    "linux_user": "liam",
                    "effective_uid": 1002,
                    "cwd": "/home/liam/agentic-os-live",
                    "sandbox": "danger-full-access",
                    "approval_policy": "never",
                },
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_codex_local", return_value=worker_result) as run, \
                 patch.object(backend, "wsl_claude") as claude, \
                 patch.object(backend, "wsl_hermes") as hermes, \
                 patch.object(backend, "_queue_run_hermes_review", return_value=review_result):
                result = backend.run_queue_item("AOS-2026-0002")

        run.assert_called_once()
        self.assertIn("Required local artifact path", run.call_args.args[0])
        self.assertEqual(run.call_args.args[1]["id"], "AOS-2026-0002")
        claude.assert_not_called()
        hermes.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["assigned_worker"], "codex")
        self.assertEqual(result["attempts_used"], 1)
        self.assertEqual(result["worker_result"]["command_stage"], "completion")

    def test_healthy_heartbeat_beyond_120_seconds_is_not_stuck(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        item = self.sample_queue_items()[1]
        item.update({
            "status": "agent_working",
            "claim": {"claimed_by": "codex", "claimed_at": (now - datetime.timedelta(seconds=300)).isoformat()},
            "worker_heartbeat_at": (now - datetime.timedelta(seconds=2)).isoformat(),
            "updated_at": (now - datetime.timedelta(seconds=2)).isoformat(),
        })
        recovery = backend._queue_stuck_recovery(item, now=now)
        self.assertFalse(recovery["stuck"])
        self.assertLess(recovery["age_seconds"], backend.QUEUE_STUCK_TIMEOUT_SECONDS)

    def test_stale_heartbeat_with_exact_live_worker_runtime_is_not_recovered(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        item = self.sample_queue_items()[1]
        item.update({
            "status": "agent_working",
            "claim": {"claimed_by": "claude", "claimed_at": (now - datetime.timedelta(seconds=300)).isoformat()},
            "worker_heartbeat_at": (now - datetime.timedelta(seconds=backend.QUEUE_STUCK_TIMEOUT_SECONDS + 1)).isoformat(),
            "updated_at": (now - datetime.timedelta(seconds=backend.QUEUE_STUCK_TIMEOUT_SECONDS + 1)).isoformat(),
            "worker_runtime": {"pid": 4242, "process_start_id": "exact-start", "route": "aos-claude"},
        })
        with patch.object(backend, "_linux_process_start_id", return_value="exact-start"):
            recovery = backend._queue_stuck_recovery(item, now=now)
        self.assertFalse(recovery["stuck"])
        self.assertTrue(recovery["runtime_live"])
        self.assertIn("exact worker process is still live", recovery["reason"])

    def test_dead_worker_is_recovered_to_blocked_with_receipt_and_clear_claim(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        item = self.sample_queue_items()[1]
        item.update({
            "status": "agent_working",
            "claim": {"claimed_by": "codex", "claimed_at": (now - datetime.timedelta(seconds=300)).isoformat()},
            "worker_heartbeat_at": (now - datetime.timedelta(seconds=backend.QUEUE_STUCK_TIMEOUT_SECONDS + 1)).isoformat(),
            "updated_at": (now - datetime.timedelta(seconds=backend.QUEUE_STUCK_TIMEOUT_SECONDS + 1)).isoformat(),
        })
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [item])
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_resolve_route_metadata", return_value=self.route_metadata_fixture("codex")), \
                 patch.object(backend, "_notify_queue_completion", return_value=None), \
                 patch.object(backend, "_queue_run_worker") as worker:
                result = backend.run_queue_item(item["id"])
                saved = backend._queue_find_item(item["id"])
                receipt = (root / result["receipt_path"]).read_text(encoding="utf-8")
        worker.assert_not_called()
        self.assertTrue(result["recovered_stuck"])
        self.assertEqual(saved["status"], "blocked")
        self.assertEqual(saved["claim"], {"claimed_by": None, "claimed_at": None})
        self.assertIn("NEEDS ATTENTION", receipt)
        self.assertIn("last worker heartbeat", receipt)

    def test_agent_exit_failure_writes_blocked_receipt_and_releases_claim(self):
        worker_result = {
            "success": False,
            "output": "Agent process exited before completion",
            "returncode": 7,
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "token_usage": {"available": False},
        }
        review_result = {
            "success": True,
            "output": "PASS",
            "returncode": 0,
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "token_usage": {"available": False},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [self.sample_queue_items()[1]])
            self.write_queue_templates(root)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_run_worker", return_value=worker_result), \
                 patch.object(backend, "_queue_run_hermes_review", return_value=review_result) as model_review, \
                 patch.object(backend, "_queue_resolve_route_metadata", return_value=self.route_metadata_fixture("codex")), \
                 patch.object(backend, "_notify_queue_completion", return_value=None):
                result = backend.run_queue_item("AOS-2026-0002")
                saved = backend._queue_find_item("AOS-2026-0002")
                receipt = (root / result["receipt_path"]).read_text(encoding="utf-8")
        self.assertFalse(result["success"])
        self.assertEqual(saved["status"], "blocked")
        self.assertEqual(saved["claim"], {"claimed_by": None, "claimed_at": None})
        self.assertIn("worker exited with status 7", receipt)

    def test_agent_reported_failure_is_classified_and_skips_hermes_review(self):
        worker_result = {
            "success": False,
            "output": "NEEDS ATTENTION\nFiles touched: None\nValidation: local route ran\nBlockers: protected_boundary_stop\nNext action: review boundary",
            "returncode": 0,
            "failure_class": "agent_reported_task_failure",
            "command_stage": "completion",
            "diagnostic_log": "logs/local_agent_route.jsonl",
            "captured_stdout_tail": "NEEDS ATTENTION",
            "captured_stderr_tail": "",
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "token_usage": {"available": False},
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [self.sample_queue_items()[1]])
            self.write_queue_templates(root)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_run_worker", return_value=worker_result), \
                 patch.object(backend, "_queue_run_hermes_review") as review, \
                 patch.object(backend, "_queue_resolve_route_metadata", return_value=self.route_metadata_fixture("codex")), \
                 patch.object(backend, "_notify_queue_completion", return_value=None):
                result = backend.run_queue_item("AOS-2026-0002")
                receipt = (root / result["receipt_path"]).read_text(encoding="utf-8")
        review.assert_not_called()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("agent_reported_task_failure", receipt)
        self.assertNotIn("exited with status 0", receipt)

    def test_telegram_style_dispatch_runs_once_after_ack_and_produces_receipt(self):
        runner_path = MAIN.parents[2] / "tools" / "aos-orchestration-runner.py"
        spec = importlib.util.spec_from_file_location("aos_async_runner_fixture", runner_path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        task = r"Give this task to Codex: assess a candidate workflow at C:\Users\Liam\Downloads\candidate-workflow and incorporate it if useful, then validate end-to-end."
        worker_calls = []
        worker_result = {
            "success": True,
            "output": "PASS\nFiles touched: None\nValidation: disposable end-to-end proof\nBlockers: None\nNext action: Liam review",
            "returncode": 0,
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "token_usage": {"available": False},
        }
        review_result = {
            "success": True,
            "output": "PASS",
            "returncode": 0,
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "token_usage": {"available": False},
        }

        def delayed_worker(*args):
            worker_calls.append(args)
            time.sleep(0.15)
            return worker_result

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_templates(root)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "INLINE_COMMAND_TIMEOUT_SECONDS", 0.05), \
                 patch.object(backend, "_queue_runner_status", return_value={"available": True, "state": "running", "pid": 123}), \
                 patch.object(backend, "_queue_run_worker", side_effect=delayed_worker), \
                 patch.object(backend, "_queue_run_hermes_review", return_value=review_result) as model_review, \
                 patch.object(backend, "_queue_resolve_route_metadata", return_value=self.route_metadata_fixture("hermes")), \
                 patch.object(backend, "_notify_queue_completion", return_value={"result": "sent", "sent": True}):
                acknowledgement = backend.wsl_hermes(backend.TaskRun(task=task, delivery_id="proof-update-1", reply_to="fixture-chat"))
                duplicate = backend.wsl_hermes(backend.TaskRun(task=task, delivery_id="proof-update-1", reply_to="fixture-chat"))
                result_holder = {}
                thread = threading.Thread(
                    target=lambda: result_holder.setdefault(
                        "result", runner.dispatch_next(root, dispatch=lambda item_id: backend.run_queue_item(item_id))
                    )
                )
                thread.start()
                self.assertTrue(acknowledgement["request_returned_before_completion"])
                self.assertTrue(thread.is_alive())
                thread.join(timeout=3)
                final_item = backend._queue_find_item(acknowledgement["work_item_id"])
                receipt_path = result_holder["result"]["receipt_path"]
                receipt = (root / receipt_path).read_text(encoding="utf-8")

        self.assertFalse(thread.is_alive())
        self.assertEqual(acknowledgement["work_item_id"], duplicate["work_item_id"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(len(worker_calls), 1)
        self.assertEqual(final_item["status"], "human_review")
        self.assertEqual(final_item["claim"], {"claimed_by": None, "claimed_at": None})
        self.assertIn("PASS", receipt)
        self.assertIn("disposable end-to-end proof", receipt)

    def test_split_telegram_work_request_creates_one_item_and_invokes_one_worker(self):
        runner_path = MAIN.parents[2] / "tools" / "aos-orchestration-runner.py"
        spec = importlib.util.spec_from_file_location("aos_split_runner_fixture", runner_path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        first_part = "/work claude " + ("bounded dashboard repair details " * 140) + "\n\n4. Preserve architecture:"
        second_part = "* Linux queue authority remains queue/work_items.jsonl.\n* Run the complete validation suite."
        worker_result = {
            "success": True,
            "output": "PASS\nSummary for operator: Split intake proof completed locally; approval sends nothing externally.\nFiles touched: None\nValidation: one worker fixture\nBlockers: None\nNext action: Review",
            "returncode": 0,
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "token_usage": {"available": False},
        }
        review_result = {
            "success": True,
            "output": "PASS",
            "returncode": 0,
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "token_usage": {"available": False},
        }
        runner_state = {"available": True, "accepted": True, "state": "running", "pid": 123, "mode": "recurring"}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_templates(root)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_runner_status", return_value=runner_state), \
                 patch.object(backend, "_queue_run_worker", return_value=worker_result) as worker, \
                 patch.object(backend, "_queue_run_hermes_review", return_value=review_result) as model_review, \
                 patch.object(backend, "_queue_resolve_route_metadata", return_value=self.route_metadata_fixture("claude")), \
                 patch.object(backend, "_notify_queue_completion", return_value=None):
                first = backend.wsl_hermes(backend.TaskRun(task=first_part, source="telegram"))
                second = backend.wsl_hermes(backend.TaskRun(task=second_part, source="telegram"))
                completed = runner.dispatch_next(root, dispatch=lambda item_id: backend.run_queue_item(item_id))
                rows = backend._read_queue_items()
                prompt_files = list((root / "queue/run_prompts").glob("*.md"))
                prompt_text = (root / rows[0]["run_prompt_path"]).read_text(encoding="utf-8")

        self.assertTrue(first["created"])
        self.assertEqual(second["state"], "split-work-request-merged")
        self.assertFalse(second["created"])
        self.assertFalse(second["runner_accepted"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(prompt_files), 1)
        self.assertIn(first_part, prompt_text)
        self.assertIn(second_part, prompt_text)
        self.assertEqual(["consider decomposing"], rows[0]["needs_me"])
        self.assertEqual(worker.call_count, 1)
        model_review.assert_not_called()
        self.assertEqual(completed["attempts_used"], 1)
        self.assertEqual(rows[0]["status"], "human_review")

    def test_explicit_model_review_uses_existing_path_with_final_artifact_only(self):
        item = {
            "id": "AOS-2026-0201",
            "title": "Explicit model review proof",
            "status": "agent_todo",
            "priority": 5,
            "requested_by": "Liam",
            "owner_type": "agent",
            "owner": "codex",
            "source": "dashboard",
            "tags": [],
            "context": "Produce the bounded proof.",
            "sources": [],
            "allowed_actions": ["local_read", "local_test"],
            "stop_conditions": ["external_send"],
            "definition_of_done": "Final artifact exists.",
            "claim": {"claimed_by": None, "claimed_at": None},
            "receipts": [],
            "review": "model",
            "created_at": "2026-07-18T10:00:00Z",
            "updated_at": "2026-07-18T10:00:00Z",
        }
        worker_result = {
            "success": True,
            "output": "PASS\nArtifacts: workflows/queue_artifacts/AOS-2026-0201_Explicit_model_review_proof.md\nValidation: deterministic proof",
            "stdout": "RAW WORKER TRANSCRIPT AND RAW TEST LOGS",
            "returncode": 0,
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "token_usage": {"available": False},
        }
        review_result = {
            "success": True,
            "output": "PASS",
            "returncode": 0,
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "token_usage": {"available": False},
        }
        captured = {}

        def review(item_arg, owner, attempt, result):
            captured["prompt"] = backend._queue_hermes_review_prompt(item_arg, owner, attempt, result)
            return review_result

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_templates(root)
            self.write_queue_items(root, [item])
            artifact = root / "workflows/queue_artifacts/AOS-2026-0201_Explicit_model_review_proof.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("FINAL ARTIFACT ONLY\n", encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_run_worker", return_value=worker_result), \
                 patch.object(backend, "_queue_run_hermes_review", side_effect=review) as model_review, \
                 patch.object(backend, "_queue_resolve_route_metadata", return_value=self.route_metadata_fixture("codex")), \
                 patch.object(backend, "_notify_queue_completion", return_value=None):
                result = backend.run_queue_item(item["id"])

        self.assertEqual(result["status"], "human_review")
        model_review.assert_called_once()
        self.assertIn("FINAL ARTIFACT ONLY", captured["prompt"])
        self.assertNotIn("RAW WORKER TRANSCRIPT", captured["prompt"])
        self.assertNotIn("RAW TEST LOGS", captured["prompt"])

    def test_async_completion_notification_uses_existing_idempotent_send_path(self):
        item = self.sample_queue_items()[1]
        item.update({
            "source": "telegram",
            "status": "human_review",
            "dispatch": {"reply_to": "fixture-chat", "idempotency_key": "fixture-key"},
        })
        sends = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, [item])
            (root / "queue" / "notifications.json").write_text(json.dumps({
                "escalation": {"unanswered_minutes": 10},
                "allowlist": {"telegram": ["fixture-chat"], "agentmail_internal": []},
            }), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root):
                first = backend._notify_queue_completion(
                    item["id"], "human_review", "queue/receipts/fixture.md",
                    send_telegram=lambda recipient, message: sends.append((recipient, message)),
                )
                second = backend._notify_queue_completion(
                    item["id"], "human_review", "queue/receipts/fixture.md",
                    send_telegram=lambda recipient, message: sends.append((recipient, message)),
                )
        self.assertEqual(first["result"], "sent")
        self.assertEqual(second["result"], "already_sent")
        self.assertEqual(len(sends), 1)
        self.assertIn(item["id"], sends[0][1])

    def test_queue_item_run_pass_sets_human_review_and_attaches_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            self.write_queue_templates(root)
            worker_result = {
                "success": True,
                "output": "PASS\nFiles touched: dashboard/backend/main.py\nValidation: python tests passed\nBlockers: None\nNext action: Liam review",
                "returncode": 0,
                "token_usage_text": "Token usage: unavailable from current CLI output",
                "token_usage": {"available": False},
                "invocation": {
                    "executable": "/home/liam/.local/npm/bin/codex",
                    "linux_user": "liam",
                    "effective_uid": 1002,
                    "cwd": "/home/liam/agentic-os-live",
                    "sandbox": "danger-full-access",
                    "approval_policy": "never",
                },
            }
            review_result = {
                "success": True,
                "output": "PASS",
                "returncode": 0,
                "token_usage_text": "Token usage: unavailable from current CLI output",
                "token_usage": {"available": False},
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_run_worker", return_value=worker_result), \
                 patch.object(backend, "_queue_run_hermes_review", return_value=review_result) as review:
                result = backend.run_queue_item("AOS-2026-0002")

            self.assertEqual(result["status"], "human_review")
            self.assertEqual(result["receipt_path"], "queue/receipts/AOS-2026-0002.md")
            receipt_file = root / result["receipt_path"]
            self.assertTrue(receipt_file.exists())
            receipt_text = receipt_file.read_text(encoding="utf-8")
            self.assertIn("PASS", receipt_text)
            self.assertIn("Work item ID: AOS-2026-0002", receipt_text)
            self.assertIn("Assigned worker: codex", receipt_text)
            self.assertIn("Review mode: none (deterministic proof)", receipt_text)
            self.assertIn("Review result: PASS", receipt_text)
            review.assert_not_called()
            self.assertIn("Codex executable: /home/liam/.local/npm/bin/codex", receipt_text)
            self.assertIn("Effective Linux user: liam", receipt_text)
            self.assertIn("Working directory: /home/liam/agentic-os-live", receipt_text)
            self.assertIn("Sandbox: danger-full-access", receipt_text)
            self.assertIn("Approval policy: never", receipt_text)
            self.assertEqual(result["item"]["receipts"][0]["path"], result["receipt_path"])
            self.assertEqual(result["item"]["receipts"][0]["status"], "human_review")

    def test_queue_item_run_revise_triggers_exactly_one_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = self.sample_queue_items()
            next(item for item in items if item["id"] == "AOS-2026-0002")["review"] = "model"
            self.write_queue_items(root, items)
            self.write_queue_templates(root)
            worker_result = {
                "success": True,
                "output": "PASS\nFiles touched: None\nValidation: local check\nBlockers: None\nNext action: Review",
                "returncode": 0,
                "token_usage_text": "Token usage: unavailable from current CLI output",
                "token_usage": {"available": False},
            }
            review_results = [
                {
                    "success": True,
                    "output": "REVISE: include validation evidence",
                    "returncode": 0,
                    "token_usage_text": "Token usage: unavailable from current CLI output",
                    "token_usage": {"available": False},
                },
                {
                    "success": True,
                    "output": "PASS",
                    "returncode": 0,
                    "token_usage_text": "Token usage: unavailable from current CLI output",
                    "token_usage": {"available": False},
                },
            ]
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_run_worker", return_value=worker_result) as worker, \
                 patch.object(backend, "_queue_run_hermes_review", side_effect=review_results) as review:
                result = backend.run_queue_item("AOS-2026-0002")

        self.assertEqual(worker.call_count, 2)
        self.assertEqual(review.call_count, 2)
        self.assertTrue(result["success"])
        self.assertEqual(result["attempts_used"], 2)
        second_prompt = worker.call_args_list[1].args[1]
        self.assertIn("Hermes Revision Instructions", second_prompt)
        self.assertIn("include validation evidence", second_prompt)

    def test_queue_item_run_repeated_revise_stops_after_two_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = self.sample_queue_items()
            next(item for item in items if item["id"] == "AOS-2026-0002")["review"] = "model"
            self.write_queue_items(root, items)
            self.write_queue_templates(root)
            worker_result = {
                "success": True,
                "output": "PASS\nFiles touched: None\nValidation: incomplete\nBlockers: Needs detail\nNext action: Revise",
                "returncode": 0,
                "token_usage_text": "Token usage: unavailable from current CLI output",
                "token_usage": {"available": False},
            }
            review_result = {
                "success": True,
                "output": "REVISE: definition of done is not satisfied",
                "returncode": 0,
                "token_usage_text": "Token usage: unavailable from current CLI output",
                "token_usage": {"available": False},
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_run_worker", return_value=worker_result) as worker, \
                 patch.object(backend, "_queue_run_hermes_review", return_value=review_result) as review:
                result = backend.run_queue_item("AOS-2026-0002")

            self.assertEqual(worker.call_count, 2)
            self.assertEqual(review.call_count, 2)
            self.assertFalse(result["success"])
            self.assertEqual(result["status"], "needs_input")
            self.assertEqual(result["attempts_used"], 2)
            receipt_text = (root / result["receipt_path"]).read_text(encoding="utf-8")
            self.assertIn("NEEDS ATTENTION", receipt_text)
            self.assertIn("definition of done is not satisfied", receipt_text)

    def test_queue_item_run_timeout_receipt_names_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            self.write_queue_templates(root)
            timeout_result = {
                "success": False,
                "output": f"Command timed out after {backend.QUEUE_WORKER_TIMEOUT_SECONDS}s",
                "stdout": "",
                "stderr": f"Command timed out after {backend.QUEUE_WORKER_TIMEOUT_SECONDS}s",
                "returncode": -1,
                "timed_out": True,
                "timeout_seconds": backend.QUEUE_WORKER_TIMEOUT_SECONDS,
                "startup_timeout_seconds": 60,
                "execution_timeout_seconds": backend.QUEUE_WORKER_TIMEOUT_SECONDS,
                "elapsed_seconds": backend.QUEUE_WORKER_TIMEOUT_SECONDS,
                "failure_class": "execution_timeout",
                "command_stage": "execution",
                "log_path": "logs/local_agent_route.jsonl",
            }
            review_result = {
                "success": True,
                "output": "REVISE: worker timed out before producing the required receipt",
                "returncode": 0,
                "token_usage_text": "Token usage: unavailable from current CLI output",
                "token_usage": {"available": False},
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_codex_local", return_value=timeout_result) as run, \
                 patch.object(backend, "_queue_run_hermes_review", return_value=review_result) as review:
                result = backend.run_queue_item("AOS-2026-0002")

            self.assertEqual(run.call_count, 1)
            review.assert_not_called()
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["attempts_used"], 1)
            self.assertTrue(result["worker_result"]["timed_out"])
            receipt_text = (root / result["receipt_path"]).read_text(encoding="utf-8")
            self.assertIn("execution_timeout during execution", receipt_text)
            self.assertIn("Diagnostic log: logs/local_agent_route.jsonl", receipt_text)

    def test_department_queue_runtime_prompt_is_compact(self):
        item = {
            "id": "AOS-2026-0019",
            "title": "Prepare LinkedIn outreach angles for TTR prospects",
            "owner": "revenue",
            "context": "Draft three concise angles.",
            "sources": ["queue/work_items.jsonl"],
            "allowed_actions": ["Read local files", "Write receipt"],
            "stop_conditions": ["Do not call connectors"],
            "definition_of_done": "Return outreach angles and receipt.",
        }

        prompt = backend._queue_actual_run_prompt(item, "revenue", attempt=2)

        self.assertIn("- ID: AOS-2026-0019", prompt)
        self.assertIn("- Title: Prepare LinkedIn outreach angles for TTR prospects", prompt)
        self.assertIn("- Owner: revenue", prompt)
        self.assertIn("- Current attempt: 2/2", prompt)
        self.assertIn("Required artifact/receipt shape:", prompt)
        self.assertNotIn("Department card", prompt)
        self.assertNotIn("Manual launch", prompt)

    def test_queue_item_run_does_not_touch_connector_or_forbidden_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            self.write_queue_templates(root)
            worker_result = {
                "success": True,
                "output": "PASS\nFiles touched: None\nValidation: local only\nBlockers: None\nNext action: Review",
                "returncode": 0,
                "token_usage_text": "Token usage: unavailable from current CLI output",
                "token_usage": {"available": False},
            }
            review_result = {
                "success": True,
                "output": "PASS",
                "returncode": 0,
                "token_usage_text": "Token usage: unavailable from current CLI output",
                "token_usage": {"available": False},
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_queue_run_worker", return_value=worker_result), \
                 patch.object(backend, "_queue_run_hermes_review", return_value=review_result), \
                 patch.object(backend, "_run_composio_adapter") as composio, \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.run_queue_item("AOS-2026-0002")

            composio.assert_not_called()
            run.assert_not_called()
            self.assertTrue(result["success"])
            forbidden = [
                root / "connectors" / "telegram_bridge",
                root / "workspaces" / "north_shore_sales_coach",
                root / ".env",
                root / "old",
                root / "ZPC",
                root / "vault",
            ]
            for path in forbidden:
                self.assertFalse(path.exists(), path)

    def test_list_queue_status_filters_by_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.wsl_hermes(backend.TaskRun(task="List queue: agent_todo"))

        run.assert_not_called()
        self.assertTrue(result["success"])
        self.assertIn("AOS-2026-0002 | agent_todo | codex | Codex route test", result["output"])
        self.assertNotIn("Triage inbox lead", result["output"])
        self.assertNotIn("Blocked connector decision", result["output"])

    def test_invalid_list_queue_status_returns_attention_without_wsl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.wsl_hermes(backend.TaskRun(task="List queue: waiting"))

        run.assert_not_called()
        self.assertFalse(result["success"])
        self.assertEqual(result["selected_route"], "local_queue_list")
        self.assertIn("NEEDS ATTENTION", result["output"])
        self.assertIn("Invalid queue status: waiting", result["output"])

    def test_empty_list_queue_returns_none_and_root_relative_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                result = backend.wsl_hermes(backend.TaskRun(task="LIST QUEUE"))

        run.assert_not_called()
        self.assertTrue(result["success"])
        self.assertIn("Queue items:\n  - None", result["output"])
        self.assertIn("Next action:\n  - Add a queue item or continue normal Hermes work.", result["output"])
        self.assertEqual(backend._queue_items_path(), backend.BASE_DIR / "queue" / "work_items.jsonl")

    def test_backend_queue_endpoints_read_authoritative_file_and_summary_is_meaningful(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = root / "queue" / "receipts" / "AOS-2026-9010.md"
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text(
                "PASS\n\nRoot cause / behavior changed:\n- Queue refresh now keeps prior counts after failures.\n\nValidation:\n- Browser proof exercised initial queue load.\n",
                encoding="utf-8",
            )
            item = {
                "id": "AOS-2026-9010",
                "title": "Queue refresh repair",
                "status": "human_review",
                "owner": "hermes",
                "priority": 5,
                "receipts": [{"path": "queue/receipts/AOS-2026-9010.md", "status": "human_review"}],
            }
            self.write_queue_items(root, [item])
            with patch.object(backend, "BASE_DIR", root):
                status = backend.queue_status()
                listed = backend.queue_items()

        self.assertTrue(status["success"])
        self.assertEqual(1, status["counts"]["human_review"])
        self.assertEqual(root / "queue" / "work_items.jsonl", root / "queue" / "work_items.jsonl")
        detail = listed["items"][0]
        self.assertIn("prior counts", detail["summary_for_operator"])
        self.assertIn("review-close", detail["summary_for_operator"])
        self.assertNotEqual("Queue refresh repair", detail["summary_for_operator"])

    def test_compacted_worker_closeout_gets_meaningful_safe_operator_summary(self):
        item = {"id": "AOS-2026-0165", "title": "Dashboard recovery proof"}
        result = {
            "output": "PASS\nFiles touched: proof.md\nValidation: green\nBlockers: None",
            "review_output": "Verification complete — dashboard and worker repairs are green.\n\nPASS",
        }

        summary = backend._queue_operator_summary_from_result(item, result)

        self.assertIn("dashboard and worker repairs are green", summary)
        self.assertIn("Approving closes this local review", summary)
        self.assertIn("sends nothing externally", summary)

    def test_human_review_close_uses_existing_review_close_and_correction_paths(self):
        for status in ("done", "needs_input"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                item = {
                    "id": "AOS-2026-9011",
                    "title": "Workflow review",
                    "status": "human_review",
                    "owner": "hermes",
                    "owner_type": "workflow",
                    "priority": 5,
                    "tags": ["pkg:fixture", "pkgver:v1"],
                    "receipts": [],
                }
                self.write_queue_items(root, [item])
                with patch.object(backend, "BASE_DIR", root), \
                     patch.object(backend.aos_orchestration, "tick", return_value={"advanced": []}) as tick:
                    body = backend.QueueReviewClose(
                        status=status,
                        action="approve" if status == "done" else "needs_changes",
                        review_note="operator note",
                    )
                    result = backend._close_queue_item_review("AOS-2026-9011", body, notify_telegram=False)
                rows = [json.loads(line) for line in (root / "queue" / "work_items.jsonl").read_text(encoding="utf-8").splitlines()]
                if status == "done":
                    self.assertEqual("done", rows[0]["status"])
                    tick.assert_called_once()
                    self.assertIn("final-closeout", result["receipt_path"])
                else:
                    self.assertEqual("inbox", rows[0]["status"])
                    self.assertIsNotNone(result["correction_item"])
                    self.assertEqual("AOS-2026-9011", result["correction_item"]["parent_id"])

    def test_queue_read_skips_one_malformed_record_and_keeps_valid_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            queue.mkdir(parents=True)
            queue_path = queue / "work_items.jsonl"
            original = '{"id":"AOS-2026-9012","status":"inbox"}\n{broken\n{"id":"AOS-2026-9013","status":"done"}\n'
            queue_path.write_text(original, encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root):
                result = backend.queue_items("all")
                summary = backend.queue_summary()
            preserved = queue_path.read_text(encoding="utf-8")
        self.assertTrue(result["success"])
        self.assertEqual(["AOS-2026-9012", "AOS-2026-9013"], [row["id"] for row in result["items"]])
        self.assertEqual({"invalidRecordCount": 1}, result["diagnostics"])
        self.assertEqual({"invalidRecordCount": 1}, summary["diagnostics"])
        self.assertNotIn("broken", json.dumps(result))
        self.assertEqual(original, preserved)

    def test_hermes_coordinator_rejects_windows_backend_path(self):
        windows_script = PureWindowsPath(r"Z:\workspace\tools\aos-hermes-coordinator.sh")
        with patch.object(backend, "HERMES_COORDINATOR", windows_script):
            with self.assertRaisesRegex(RuntimeError, "Windows and Windows-mounted paths"):
                backend._hermes_coordinator_command_template()

    def test_runtime_path_helper_rejects_windows_mount_and_preserves_linux(self):
        with self.assertRaisesRegex(RuntimeError, "Windows and Windows-mounted paths"):
            backend._path_for_wsl_command("/mnt/c/workspace/tools/aos-hermes-coordinator.sh")
        self.assertEqual(
            backend._path_for_wsl_command("/home/liam/workspace/tools/aos-hermes-coordinator.sh"),
            "/home/liam/workspace/tools/aos-hermes-coordinator.sh",
        )

    def test_no_new_absolute_workspace_literal_in_backend_patch(self):
        backend_source = MAIN.read_text(encoding="utf-8")
        windows_workspace = "\\".join(("C:", "Users", "Admin", "Documents", "A-Time to revenue", "Agentic OS Live", "tools", "aos-hermes-coordinator.sh"))
        wsl_workspace = "/".join(("", "mnt", "c", "Users", "Admin", "Documents", "A-Time to revenue", "Agentic OS Live", "tools", "aos-hermes-coordinator.sh"))
        self.assertNotIn(windows_workspace, backend_source)
        self.assertNotIn(wsl_workspace, backend_source)

    def test_queue_closeout_has_required_fields_and_no_secret_like_values(self):
        secret_patterns = (
            r"(?i)\b(?:token|secret|oauth|api[_-]?key|telegram|customer)\b",
            r"\b[A-Za-z]:\\",
            "/" + r"mnt/[a-z]/",
            "/" + r"home/[^/\s]+",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(backend, "BASE_DIR", Path(tmp)), \
                 patch.object(backend, "_run_wsl"):
                result = backend.wsl_hermes(backend.TaskRun(task="Add this to the queue: review the plan"))

        self.assertRegex(result["output"], r"Work item ID: AOS-\d{4}-\d{4}")
        self.assertIn("Owner: unassigned", result["output"])
        self.assertIn("Status: inbox", result["output"])
        self.assertIn("Next action: Review or claim the local queue item", result["output"])
        for pattern in secret_patterns:
            self.assertIsNone(re.search(pattern, result["output"]))

    def test_backend_action_route_reuses_shared_helper(self):
        with patch.object(backend, "_run_composio_adapter", return_value={"ok": True, "result": {}}) as adapter:
            result = backend.composio_action(backend.ComposioAction(tool_slug="gmail_fetch_emails", json_args={"max_results": 1}))
        adapter.assert_called_once_with("tool-run", "GMAIL_FETCH_EMAILS", {"max_results": 1})
        self.assertEqual(result["tool_slug"], "GMAIL_FETCH_EMAILS")

    def test_direct_api_routes_are_preserved(self):
        with patch.object(backend, "_run_codex_local", return_value=self.RUN_RESULT) as codex_run, \
             patch.object(backend, "_run_wsl", return_value=self.RUN_RESULT) as startup, \
             patch.object(backend, "_run_wsl_supervised", return_value=self.RUN_RESULT) as run, \
             patch.object(backend, "_log_token_usage"):
            codex = backend.wsl_codex(backend.TaskRun(task="inspect files"))
            claude = backend.wsl_claude(backend.TaskRun(task="polish UI"))
            claude_command = run.call_args.args[0]
        codex_run.assert_called_once_with("inspect files")
        startup.assert_called_once()
        self.assertTrue(claude_command.startswith('aos-hermes claude "$(<'))
        self.assertNotIn("polish UI", claude_command)
        self.assertEqual(codex["selected_route"], "direct_codex")
        self.assertEqual(claude["selected_route"], "direct_claude")

    def test_direct_codex_request_permission_fields_cannot_downgrade_policy(self):
        run_result = {
            **self.RUN_RESULT,
            "invocation": {
                "executable": "/home/liam/.local/npm/bin/codex",
                "linux_user": "liam",
                "effective_uid": 1002,
                "cwd": "/home/liam/agentic-os-live",
                "sandbox": "danger-full-access",
                "sandbox_mode": "danger-full-access",
                "approval_policy": "never",
                "ask_for_approval": "never",
            },
        }
        body = backend.TaskRun(
            task="inspect files",
            sandbox_mode="workspace-write",
            approval_policy="on-request",
        )
        with patch.object(backend, "_run_codex_local", return_value=run_result) as run, \
             patch.object(backend, "_log_token_usage"):
            result = backend.wsl_codex(body)
        run.assert_called_once_with("inspect files")
        self.assertEqual("danger-full-access", result["invocation"]["sandbox"])
        self.assertEqual("never", result["invocation"]["approval_policy"])

    def test_token_rollup_exposes_per_route_last_known_usage(self):
        records = [
            {
                "timestamp": "2026-07-06T01:00:00Z",
                "route": "codex",
                "agent": "codex",
                "token_usage_text": "Token usage: total 1,205",
                "token_usage": {"available": True, "total_tokens": "1,205"},
                "unavailable": False,
            },
            {
                "timestamp": "2026-07-06T02:00:00Z",
                "route": "claude",
                "agent": "claude",
                "token_usage_text": "Token usage: unavailable from current CLI output",
                "token_usage": {"available": False},
                "unavailable": True,
            },
            {
                "timestamp": "2026-07-06T03:00:00Z",
                "route": "hermes",
                "agent": "hermes",
                "token_usage_text": "Token usage: no agent invocation",
                "token_usage": {"available": False, "no_agent_invocation": True},
            },
        ]
        with patch.object(backend, "_read_claude_local_usage", return_value={"available": False}):
            rollup = backend._token_usage_rollup(records=records)

        self.assertEqual(rollup["by_route"]["codex"]["token_usage_text"], "Token usage: total 1,205")
        self.assertEqual(rollup["by_route"]["codex"]["status"], "completed")
        self.assertEqual(rollup["by_route"]["claude"]["token_usage_text"], "Token usage: unavailable from current CLI output")
        self.assertEqual(rollup["by_route"]["claude"]["status"], "unavailable")
        self.assertEqual(rollup["by_route"]["hermes"]["token_usage_text"], "Token usage: no agent invocation")
        self.assertEqual(rollup["by_route"]["hermes"]["status"], "no agent invocation")

    def test_hermes_useful_answer_is_displayed_and_saved(self):
        useful = "Local plasterers found:\n- North Shore Microcement\n- Metro Finish"
        run_result = {
            "success": True,
            "output": useful,
            "stdout": useful,
            "stderr": "Hermes diagnostic detail",
            "returncode": 0,
        }
        metadata = {**backend._select_hermes_entry_route("find local plasterers"), **backend._queue_resolve_route_metadata("hermes")}
        with patch.object(backend, "_log_token_usage"), \
             patch.object(backend, "_write_hermes_result", return_value="hermes_20260623_123456.md") as writer:
            result = backend._hermes_coordinator_closeout(run_result, "find local plasterers", metadata)

        self.assertIn(f"Answer: {useful}", result["output"])
        self.assertIn("Result file: hermes_20260623_123456.md", result["output"])
        self.assertIn("Files touched: results/hermes_20260623_123456.md", result["output"])
        self.assertIn("Validation: Answer: Local plasterers found: - North Shore Microcement - Metro Finish", result["output"])
        self.assertEqual(result["result_file"], "hermes_20260623_123456.md")
        saved = writer.call_args.args[0]
        self.assertIn("## Hermes stdout", saved)
        self.assertIn(useful, saved)
        self.assertIn("## Hermes stderr", saved)
        self.assertIn("Hermes diagnostic detail", saved)
        self.assertEqual(result["token_usage_text"], "Token usage: unavailable from current CLI output")

    def test_hermes_answer_is_capped_and_pass_only_is_not_saved(self):
        long_answer = "x" * 2000
        long_result = {"success": True, "output": long_answer, "stdout": long_answer, "stderr": "", "returncode": 0}
        metadata = {**backend._select_hermes_entry_route("summarize this"), **backend._queue_resolve_route_metadata("hermes")}
        with patch.object(backend, "_log_token_usage"), \
             patch.object(backend, "_write_hermes_result", return_value="hermes_long.md"):
            closeout = backend._hermes_coordinator_closeout(long_result, "summarize this", metadata)
        answer_line = closeout["output"].split("\nResult file:", 1)[0].removeprefix("PASS\nAnswer: ")
        self.assertLessEqual(len(answer_line), backend._HERMES_ANSWER_LIMIT)
        self.assertTrue(answer_line.endswith("…"))

        with patch.object(backend, "_log_token_usage"), \
             patch.object(backend, "_write_hermes_result") as writer:
            pass_only = backend._hermes_coordinator_closeout(self.RUN_RESULT, "health check", metadata)
        writer.assert_not_called()
        self.assertNotIn("Answer:", pass_only["output"])
        self.assertNotIn("Result file:", pass_only["output"])

    def test_subprocess_is_forced_to_utf8_with_replacement(self):
        completed = types.SimpleNamespace(stdout="café — done", stderr="", returncode=0)
        with patch.object(backend.subprocess, "run", return_value=completed) as run:
            result = backend._run_wsl("printf test")
        self.assertTrue(result["success"])
        self.assertEqual(result["output"], "café — done")
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_latitude_status_degrades_without_endpoint(self):
        with patch.object(backend.latitude_telemetry, "_env_values", return_value={"LATITUDE_API_KEY": "redacted"}):
            status = backend._public_latitude_status()
        self.assertFalse(status["configured"])
        self.assertEqual(status["connected"], "unknown")
        self.assertEqual(status["required_env_vars_present"], ["LATITUDE_API_KEY"])
        self.assertEqual(status["required_env_vars_missing"], ["LATITUDE_PROJECT_SLUG_OR_ID", "LATITUDE_ENDPOINT"])
        self.assertIn("LATITUDE_PROJECT_SLUG_OR_ID, LATITUDE_ENDPOINT", status["degraded_reason"])
        self.assertNotIn("redacted", json.dumps(status))

    def test_latitude_heartbeat_degrades_without_endpoint_and_hides_key(self):
        with patch.object(backend.latitude_telemetry, "_env_values", return_value={"LATITUDE_API_KEY": "redacted"}), \
             patch.object(backend.latitude_telemetry.urllib.request, "urlopen") as urlopen:
            result = backend.dashboard_latitude_heartbeat()
        urlopen.assert_not_called()
        self.assertFalse(result["success"])
        self.assertEqual(result["event_sending"], "degraded")
        self.assertFalse(result["configured"])
        self.assertEqual(result["required_env_vars_present"], ["LATITUDE_API_KEY"])
        self.assertEqual(result["required_env_vars_missing"], ["LATITUDE_PROJECT_SLUG_OR_ID", "LATITUDE_ENDPOINT"])
        self.assertIn("LATITUDE_PROJECT_SLUG_OR_ID, LATITUDE_ENDPOINT", result["degraded_reason"])
        self.assertNotIn("redacted", json.dumps(result))

    def test_latitude_send_uses_project_slug_header_and_hides_config(self):
        class FakeLatitudeResponse:
            status = 202
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return b'{"id":"evt_test"}'

        env = {
            "LATITUDE_API_KEY": "redacted-key",
            "LATITUDE_PROJECT_SLUG": "agentic-os",
            "LATITUDE_ENDPOINT": "https://latitude.example.test/events",
        }
        event = backend.latitude_telemetry.event_payload("backend.heartbeat", "dashboard_backend")
        with patch.dict(backend.latitude_telemetry.os.environ, {"AOS_DISABLE_TELEMETRY": ""}), \
             patch.object(backend.latitude_telemetry, "_env_values", return_value=env), \
             patch.object(backend.latitude_telemetry, "_write_state"), \
             patch.object(backend.latitude_telemetry.urllib.request, "urlopen", return_value=FakeLatitudeResponse()) as urlopen:
            result = backend.latitude_telemetry.send_event(event)

        request = urlopen.call_args.args[0]
        headers = dict(request.header_items())
        self.assertTrue(result["sent"])
        self.assertEqual(headers["X-project-slug"], "agentic-os")
        self.assertNotIn("X-project-id", headers)
        self.assertNotIn("redacted-key", json.dumps(result))
        self.assertNotIn("agentic-os", json.dumps(result))

    def test_external_send_dry_run_writes_noop_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipts = root / "queue" / "receipts"
            receipts.mkdir(parents=True)
            body = backend.ExternalSendDryRun(
                item_id=None,
                recipient="lead@example.com",
                action="Would send email",
                payload="Hello from a dry run.",
                confirmation="SEND lead@example.com",
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", root / "queue"), \
                 patch.object(backend.urllib.request, "urlopen") as urlopen, \
                 patch.object(backend.subprocess, "run") as subprocess_run:
                result = backend._write_external_dry_run_receipt(body)
                receipt = root / result["receipt_path"]
                content = receipt.read_text(encoding="utf-8")
        urlopen.assert_not_called()
        subprocess_run.assert_not_called()
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["transmitted"])
        self.assertIn("dry_run: true", content)
        self.assertIn("transmitted: false", content)
        self.assertIn("Token usage: no agent invocation", content)

    def test_external_send_dry_run_requires_exact_typed_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue" / "receipts").mkdir(parents=True)
            body = backend.ExternalSendDryRun(
                item_id=None,
                recipient="lead@example.com",
                action="Would send email",
                payload="Hello from a dry run.",
                confirmation="I approve",
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", root / "queue"), \
                 patch.object(backend.urllib.request, "urlopen") as urlopen, \
                 patch.object(backend.subprocess, "run") as subprocess_run:
                with self.assertRaises(ValueError):
                    backend._write_external_dry_run_receipt(body)
                receipts = list((root / "queue" / "receipts").glob("*.md"))
        urlopen.assert_not_called()
        subprocess_run.assert_not_called()
        self.assertEqual(receipts, [])

    def test_agentmail_digest_preview_accepts_allowlisted_internal_recipient(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            queue.mkdir(parents=True)
            (queue / "work_items.jsonl").write_text(
                json.dumps({
                    "id": "AOS-2026-9001",
                    "title": "Completed yesterday",
                    "status": "done",
                    "owner": "ops",
                    "priority": 1,
                    "updated_at": "2026-07-08T12:00:00Z",
                    "created_at": "2026-07-08T11:00:00Z",
                }) + "\n",
                encoding="utf-8",
            )
            (queue / "notifications.json").write_text(json.dumps({"allowlist": {"agentmail_internal": ["revenue-agent@internal"]}}), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "NOTIFICATIONS_FILE", queue / "notifications.json"), \
                 patch.object(backend, "TOKEN_LEDGER_FILE", queue / "token_ledger.jsonl"), \
                 patch.object(backend, "ROOT_TOKEN_LEDGER_FILE", root / "token_ledger.jsonl"), \
                 patch.object(backend, "BACKUP_RECEIPTS_FILE", queue / "receipts" / "backups.jsonl"), \
                 patch.object(backend, "_run_agentmail_composio_send") as provider:
                result = backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "revenue-agent@internal")
        provider.assert_not_called()
        self.assertTrue(result["digest_generated"])
        self.assertTrue(result["preview"])
        self.assertFalse(result["send_attempted"])
        self.assertFalse(result["sent"])
        self.assertEqual(result["recipient"], "revenue-agent@internal")
        self.assertEqual(result["digest"]["completed_items"][0]["id"], "AOS-2026-9001")
        self.assertEqual(result["provider"], "composio")
        self.assertEqual(result["toolkit"], "agent_mail")
        self.assertEqual(result["action"], "AGENT_MAIL_SEND_EMAIL")
        self.assertEqual(result["inbox_id"], "olmec1@agentmail.to")
        self.assertEqual(result["provider_payload"]["inbox_id"], "olmec1@agentmail.to")
        self.assertEqual(result["provider_payload"]["to"], ["revenue-agent@internal"])
        self.assertEqual(result["provider_payload"]["subject"], result["subject"])
        self.assertEqual(result["provider_payload"]["text"], result["body"])
        self.assertEqual(result["provider_payload"]["html"], "")
        self.assertEqual(result["provider_payload"]["cc"], [])
        self.assertEqual(result["provider_payload"]["bcc"], [])
        self.assertEqual(result["provider_payload"]["labels"], [])
        self.assertEqual(result["provider_payload"]["reply_to"], [])

    def test_agentmail_digest_preview_accepts_liam_verified_internal_recipient(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            queue.mkdir(parents=True)
            (queue / "notifications.json").write_text(json.dumps({"allowlist": {"agentmail_internal": ["liam@timetorevenue.com"]}}), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "NOTIFICATIONS_FILE", queue / "notifications.json"), \
                 patch.object(backend, "TOKEN_LEDGER_FILE", queue / "token_ledger.jsonl"), \
                 patch.object(backend, "ROOT_TOKEN_LEDGER_FILE", root / "token_ledger.jsonl"), \
                 patch.object(backend, "BACKUP_RECEIPTS_FILE", queue / "receipts" / "backups.jsonl"), \
                 patch.object(backend, "_run_agentmail_composio_send") as provider:
                result = backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "liam@timetorevenue.com")
        provider.assert_not_called()
        self.assertTrue(result["allowlist_result"]["allowed"])
        self.assertEqual(result["recipient"], "liam@timetorevenue.com")
        self.assertEqual(result["provider_payload"]["to"], ["liam@timetorevenue.com"])

    def test_agentmail_non_allowlisted_recipient_rejected_before_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            queue.mkdir(parents=True)
            (queue / "notifications.json").write_text(json.dumps({"allowlist": {"agentmail_internal": ["ops-agent@internal"]}}), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "NOTIFICATIONS_FILE", queue / "notifications.json"), \
                 patch.object(backend, "_run_agentmail_composio_send") as provider:
                with self.assertRaises(ValueError):
                    backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "outside@timetorevenue.com", send=True, dry_run=False)
        provider.assert_not_called()

    def test_agentmail_placeholder_recipient_rejected_before_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            queue.mkdir(parents=True)
            (queue / "notifications.json").write_text(json.dumps({"allowlist": {"agentmail_internal": ["liam@timetorevenue.example"]}}), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "NOTIFICATIONS_FILE", queue / "notifications.json"), \
                 patch.object(backend, "_run_agentmail_composio_send") as provider:
                with self.assertRaises(ValueError):
                    backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "liam@timetorevenue.example", send=True, dry_run=False)
        provider.assert_not_called()

    def test_agentmail_malformed_recipient_rejected_before_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            queue.mkdir(parents=True)
            (queue / "notifications.json").write_text(json.dumps({"allowlist": {"agentmail_internal": ["not-an-address"]}}), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "NOTIFICATIONS_FILE", queue / "notifications.json"), \
                 patch.object(backend, "_run_agentmail_composio_send") as provider:
                with self.assertRaisesRegex(ValueError, "malformed"):
                    backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "not-an-address", send=True, dry_run=False)
        provider.assert_not_called()

    def test_agentmail_text_or_html_required_before_provider_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            (queue / "receipts").mkdir(parents=True)
            (queue / "notifications.json").write_text(json.dumps({"allowlist": {"agentmail_internal": ["ops-agent@internal"]}}), encoding="utf-8")
            empty_digest = {
                "digest_date": "2026-07-08",
                "recipient": "ops-agent@internal",
                "subject": "Subject",
                "body": "",
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "NOTIFICATIONS_FILE", queue / "notifications.json"), \
                 patch.object(backend, "_build_agentmail_digest", return_value=empty_digest), \
                 patch.object(backend, "_run_agentmail_composio_send") as provider:
                result = backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "ops-agent@internal", send=True, dry_run=False)
                payload = json.loads((root / result["receipt_path"]).read_text(encoding="utf-8"))
        provider.assert_not_called()
        self.assertFalse(result["sent"])
        self.assertFalse(payload["send_attempted"])
        self.assertIn("requires text or html", payload["blocker"])

    def test_agentmail_dry_run_writes_receipt_without_provider_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            (queue / "receipts").mkdir(parents=True)
            (queue / "notifications.json").write_text(json.dumps({"allowlist": {"agentmail_internal": ["ops-agent@internal"]}}), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "NOTIFICATIONS_FILE", queue / "notifications.json"), \
                 patch.object(backend, "_run_agentmail_composio_send") as provider:
                result = backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "ops-agent@internal", send=True, dry_run=True)
                payload = json.loads((root / result["receipt_path"]).read_text(encoding="utf-8"))
        provider.assert_not_called()
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["send_attempted"])
        self.assertFalse(payload["sent"])
        self.assertFalse(payload["transmitted"])
        self.assertEqual(payload["provider_action"], "AGENT_MAIL_SEND_EMAIL")
        self.assertEqual(payload["inbox_id"], "olmec1@agentmail.to")
        self.assertEqual(payload["token_usage_text"], "Token usage: no agent invocation")

    def test_agentmail_provider_success_writes_sent_true_and_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            (queue / "receipts").mkdir(parents=True)
            (queue / "notifications.json").write_text(json.dumps({"allowlist": {"agentmail_internal": ["ops-agent@internal"]}}), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "NOTIFICATIONS_FILE", queue / "notifications.json"), \
                 patch.object(backend, "_run_agentmail_composio_send", return_value={"ok": True, "result": {"message_id": "msg_123"}}) as provider:
                result = backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "ops-agent@internal", send=True, dry_run=False)
                payload = json.loads((root / result["receipt_path"]).read_text(encoding="utf-8"))
        provider.assert_called_once()
        action, provider_payload = provider.call_args.args
        self.assertEqual(action, "AGENT_MAIL_SEND_EMAIL")
        self.assertEqual(provider_payload["inbox_id"], "olmec1@agentmail.to")
        self.assertEqual(provider_payload["to"], ["ops-agent@internal"])
        self.assertEqual(provider_payload["cc"], [])
        self.assertEqual(provider_payload["bcc"], [])
        self.assertEqual(provider_payload["labels"], [])
        self.assertEqual(provider_payload["reply_to"], [])
        self.assertTrue(payload["send_attempted"])
        self.assertTrue(payload["sent"])
        self.assertTrue(payload["transmitted"])
        self.assertEqual(payload["provider_reference"], "msg_123")
        self.assertEqual(payload["token_usage_text"], "Token usage: no agent invocation")

    def test_agentmail_provider_success_reference_supports_thread_id(self):
        response = {"ok": True, "result": {"thread_id": "thr_123"}}
        self.assertEqual(backend._agentmail_provider_reference(response), "thr_123")

    def test_agentmail_provider_failure_writes_retryable_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            (queue / "receipts").mkdir(parents=True)
            (queue / "notifications.json").write_text(json.dumps({"allowlist": {"agentmail_internal": ["ops-agent@internal"]}}), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "NOTIFICATIONS_FILE", queue / "notifications.json"), \
                 patch.object(backend, "_run_agentmail_composio_send", return_value={"ok": False, "error": "auth unavailable"}) as provider:
                result = backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "ops-agent@internal", send=True, dry_run=False)
                payload = json.loads((root / result["receipt_path"]).read_text(encoding="utf-8"))
        provider.assert_called_once()
        self.assertFalse(payload["sent"])
        self.assertTrue(payload["retryable"])
        self.assertIn("auth unavailable", payload["failure"])

    def test_agentmail_duplicate_success_does_not_call_provider_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            (queue / "receipts").mkdir(parents=True)
            (queue / "notifications.json").write_text(json.dumps({"allowlist": {"agentmail_internal": ["ops-agent@internal"]}}), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "NOTIFICATIONS_FILE", queue / "notifications.json"), \
                 patch.object(backend, "_run_agentmail_composio_send", return_value={"ok": True, "result": {"message_id": "msg_123"}}) as provider:
                first = backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "ops-agent@internal", send=True, dry_run=False)
                second = backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "ops-agent@internal", send=True, dry_run=False)
                second_payload = json.loads((root / second["receipt_path"]).read_text(encoding="utf-8"))
        self.assertTrue(first["sent"])
        self.assertFalse(second["sent"])
        self.assertTrue(second["already_sent"])
        provider.assert_called_once()
        self.assertEqual(second_payload["status"], "duplicate_suppressed")

    def test_agentmail_failed_attempt_may_be_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue = root / "queue"
            (queue / "receipts").mkdir(parents=True)
            (queue / "notifications.json").write_text(json.dumps({"allowlist": {"agentmail_internal": ["ops-agent@internal"]}}), encoding="utf-8")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", queue), \
                 patch.object(backend, "NOTIFICATIONS_FILE", queue / "notifications.json"), \
                 patch.object(backend, "_run_agentmail_composio_send", side_effect=[{"ok": False, "error": "temporary"}, {"ok": True, "result": {"message_id": "msg_2"}}]) as provider:
                first = backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "ops-agent@internal", send=True, dry_run=False)
                second = backend._agentmail_digest_attempt(datetime.date(2026, 7, 8), "ops-agent@internal", send=True, dry_run=False)
        self.assertFalse(first["sent"])
        self.assertTrue(second["sent"])
        self.assertEqual(provider.call_count, 2)

    def test_no_generic_unrestricted_send_email_endpoint_exists(self):
        source = MAIN.read_text(encoding="utf-8")
        route_paths = re.findall(r"@app\.(?:post|get|put|delete)\(\"([^\"]+)\"", source)
        generic_paths = [path for path in route_paths if "send-email" in path or path.endswith("/send") or path.endswith("/email")]
        self.assertEqual(generic_paths, [])

    def test_external_send_path_remains_dry_run_only_after_agentmail_live_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue" / "receipts").mkdir(parents=True)
            body = backend.ExternalSendDryRun(
                item_id=None,
                recipient="lead@example.com",
                action="Would send email",
                payload="Hello from a dry run.",
                confirmation="SEND lead@example.com",
            )
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "QUEUE_DIR", root / "queue"), \
                 patch.object(backend.urllib.request, "urlopen") as urlopen, \
                 patch.object(backend.subprocess, "run") as subprocess_run:
                result = backend._write_external_dry_run_receipt(body)
                receipt = root / result["receipt_path"]
                content = receipt.read_text(encoding="utf-8")
        urlopen.assert_not_called()
        subprocess_run.assert_not_called()
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["transmitted"])
        self.assertIn("dry_run: true", content)
        self.assertIn("transmitted: false", content)

    def test_workflow_runner_contracts_follow_command_routes(self):
        routes = {
            "path": "queue/command_routes.json",
            "routes": [
                {
                    "id": "linkedin_carousel",
                    "workflow": "linkedin_carousel_from_md",
                    "skill": "linkedin_carousel_from_md_SKILL",
                    "owner": "marketing",
                    "workbench": "lane",
                    "patterns": ["carousel"],
                },
                {
                    "id": "fit_call_prep",
                    "workflow": "fit_call_prep",
                    "skill": "fit_call_prep_SKILL",
                    "owner": "revenue",
                    "workbench": "lane",
                    "patterns": ["fit call"],
                },
            ],
        }
        with patch.object(backend, "_load_command_routes", return_value=routes):
            contracts = backend._workflow_runner_contracts()["contracts"]
        ids = {contract["workflow_id"] for contract in contracts}
        self.assertEqual(ids, {"linkedin_carousel_from_md", "fit_call_prep"})
        for contract in contracts:
            self.assertIn("ordered_steps", contract)
            self.assertIn("stop_conditions", contract)
            self.assertIn("artifact_expectations", contract)
            self.assertIn("human_review", contract["review_gate"])

    def test_real_workflow_runner_contracts_are_registered_and_runner_consumable(self):
        contracts = backend._workflow_runner_contracts()
        self.assertTrue(contracts["runner_consumable"])
        self.assertEqual(len(contracts["contracts"]), 14)
        ids = {contract["workflow_id"] for contract in contracts["contracts"]}
        self.assertIn("linkedin_carousel_from_md", ids)
        self.assertIn("fit_call_prep", ids)
        for workflow_id in ("linkedin_carousel_from_md", "fit_call_prep"):
            contract = next(item for item in contracts["contracts"] if item["workflow_id"] == workflow_id)
            self.assertTrue(contract["ordered_steps"])
            self.assertTrue(contract["artifact_expectations"])
            self.assertIn("human_review", contract["review_gate"])
            self.assertIn("No live third-party", contract["external_action_policy"])

    def test_static_runner_contracts_match_command_routes(self):
        source_root = MAIN.parents[2]
        routes = json.loads((source_root / "queue" / "command_routes.json").read_text(encoding="utf-8"))
        registry = json.loads((source_root / "workflows" / "runner_contracts.json").read_text(encoding="utf-8"))
        route_workflows = [route["workflow"] for route in routes["routes"]]
        contract_workflows = [contract["workflow_id"] for contract in registry["contracts"]]
        self.assertEqual(len(contract_workflows), 14)
        self.assertEqual(contract_workflows, route_workflows)
        self.assertTrue(registry["runner_consumable"])
        for workflow_id in ("linkedin_carousel_from_md", "fit_call_prep"):
            contract = next(item for item in registry["contracts"] if item["workflow_id"] == workflow_id)
            self.assertIn("contract_path", contract)
            self.assertIn("review_gate", contract)
            self.assertIn("artifact_expectations", contract)

    def test_command_intent_metadata_uses_live_backend_selected_route_names(self):
        source_root = MAIN.parents[2]
        routes = json.loads((source_root / "queue" / "command_routes.json").read_text(encoding="utf-8"))
        intents = routes["intent_routes"]
        self.assertEqual(routes["on_no_match"]["route"], "hermes_coordinator")
        self.assertEqual(intents["explicit_codex"]["route"], "direct_codex")
        self.assertEqual(intents["explicit_claude"]["route"], "direct_claude")
        self.assertEqual(intents["codex_with_coordination_review"]["route"], "hermes_orchestration")
        self.assertEqual(intents["fallback"]["route"], "hermes_coordinator")


if __name__ == "__main__":
    unittest.main()
