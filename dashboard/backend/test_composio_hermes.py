import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


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


class _HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


class _BaseModel:
    def __init__(self, **values):
        for key, value in values.items():
            setattr(self, key, value)


if importlib.util.find_spec("fastapi") is None:
    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI = _FastAPI
    fastapi.HTTPException = _HTTPException
    middleware = types.ModuleType("fastapi.middleware")
    cors = types.ModuleType("fastapi.middleware.cors")
    cors.CORSMiddleware = object
    sys.modules.update({"fastapi": fastapi, "fastapi.middleware": middleware, "fastapi.middleware.cors": cors})

if importlib.util.find_spec("pydantic") is None:
    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = _BaseModel
    sys.modules["pydantic"] = pydantic


MAIN = Path(__file__).with_name("main.py")
SPEC = importlib.util.spec_from_file_location("agentic_os_backend", MAIN)
backend = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backend)


class HermesComposioTests(unittest.TestCase):
    RUN_RESULT = {"success": True, "output": "PASS", "stdout": "PASS", "stderr": "", "returncode": 0}

    def route(self, task):
        with patch.object(backend, "_run_wsl", return_value=self.RUN_RESULT) as run, \
             patch.object(backend, "_log_token_usage"):
            result = backend.wsl_hermes(backend.TaskRun(task=task))
        return run.call_args.args[0], result

    def test_normal_task_uses_hermes_coordinator(self):
        command, result = self.route("quick search for local micro cement plasterers")
        self.assertIn("aos-hermes-coordinator.sh", command)
        self.assertIn("'quick search for local micro cement plasterers'", command)
        self.assertEqual(result["selected_route"], "hermes_coordinator")

    def test_explicit_hermes_uses_coordinator(self):
        for task in (
            "get Hermes to quick search for local micro cement plasterers",
            "/work hermes quick search for local micro cement plasterers",
        ):
            command, result = self.route(task)
            self.assertIn("aos-hermes-coordinator.sh", command)
            self.assertNotIn("aos-hermes codex", command)
            self.assertEqual(result["selected_route"], "hermes_coordinator")

    def test_codex_forbidden_forces_hermes(self):
        for task in ("quick search, do not use Codex", "I don't want Codex to do it"):
            command, result = self.route(task)
            self.assertIn("aos-hermes-coordinator.sh", command)
            self.assertEqual(result["codex_forbidden"], "yes")
            self.assertEqual(result["delegation_reason"], "Codex forbidden by operator")

    def test_explicit_codex_is_direct(self):
        command, result = self.route("get Codex to inspect dashboard files")
        self.assertTrue(command.startswith("aos-codex '"))
        self.assertEqual(result["selected_route"], "direct_codex")

    def test_explicit_claude_is_direct(self):
        command, result = self.route("get Claude to polish the dashboard UI")
        self.assertTrue(command.startswith("aos-hermes claude '"))
        self.assertEqual(result["selected_route"], "direct_claude")

    def test_search_firecrawl_and_composio_decisions_stay_with_hermes(self):
        for task in ("search the web", "scrape this page", "use Firecrawl", "use Composio to check mail"):
            command, result = self.route(task)
            self.assertIn("aos-hermes-coordinator.sh", command, task)
            self.assertEqual(result["selected_route"], "hermes_coordinator")

    def test_backend_action_route_reuses_shared_helper(self):
        with patch.object(backend, "_run_composio_adapter", return_value={"ok": True, "result": {}}) as adapter:
            result = backend.composio_action(backend.ComposioAction(tool_slug="gmail_fetch_emails", json_args={"max_results": 1}))
        adapter.assert_called_once_with("tool-run", "GMAIL_FETCH_EMAILS", {"max_results": 1})
        self.assertEqual(result["tool_slug"], "GMAIL_FETCH_EMAILS")

    def test_direct_api_routes_are_preserved(self):
        with patch.object(backend, "_run_wsl", return_value=self.RUN_RESULT) as run, \
             patch.object(backend, "_log_token_usage"):
            codex = backend.wsl_codex(backend.TaskRun(task="inspect files"))
            codex_command = run.call_args.args[0]
            claude = backend.wsl_claude(backend.TaskRun(task="polish UI"))
            claude_command = run.call_args.args[0]
        self.assertEqual(codex_command, "aos-codex 'inspect files'")
        self.assertEqual(claude_command, "aos-hermes claude 'polish UI'")
        self.assertEqual(codex["selected_route"], "direct_codex")
        self.assertEqual(claude["selected_route"], "direct_claude")

    def test_hermes_useful_answer_is_displayed_and_saved(self):
        useful = "Local plasterers found:\n- North Shore Microcement\n- Metro Finish"
        run_result = {
            "success": True,
            "output": useful,
            "stdout": useful,
            "stderr": "Hermes diagnostic detail",
            "returncode": 0,
        }
        with patch.object(backend, "_run_wsl", return_value=run_result), \
             patch.object(backend, "_log_token_usage"), \
             patch.object(backend, "_write_hermes_result", return_value="hermes_20260623_123456.md") as writer:
            result = backend.wsl_hermes(backend.TaskRun(task="find local plasterers"))

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
        with patch.object(backend, "_run_wsl", return_value=long_result), \
             patch.object(backend, "_log_token_usage"), \
             patch.object(backend, "_write_hermes_result", return_value="hermes_long.md"):
            closeout = backend.wsl_hermes(backend.TaskRun(task="summarize this"))
        answer_line = closeout["output"].split("\nResult file:", 1)[0].removeprefix("PASS\nAnswer: ")
        self.assertLessEqual(len(answer_line), backend._HERMES_ANSWER_LIMIT)
        self.assertTrue(answer_line.endswith("…"))

        with patch.object(backend, "_run_wsl", return_value=self.RUN_RESULT), \
             patch.object(backend, "_log_token_usage"), \
             patch.object(backend, "_write_hermes_result") as writer:
            pass_only = backend.wsl_hermes(backend.TaskRun(task="health check"))
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


if __name__ == "__main__":
    unittest.main()
