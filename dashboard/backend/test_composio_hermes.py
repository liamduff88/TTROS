import importlib.util
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path, PureWindowsPath
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

    def test_normal_task_uses_hermes_coordinator(self):
        command, result = self.route("quick search for local micro cement plasterers")
        self.assertIn("aos-hermes-coordinator.sh", command)
        self.assertIn("--prompt-file", command)
        self.assertNotIn("quick search for local micro cement plasterers", command)
        self.assertEqual(result["selected_route"], "hermes_coordinator")

    def test_explicit_hermes_uses_coordinator(self):
        for task in (
            "get Hermes to quick search for local micro cement plasterers",
            "/work hermes quick search for local micro cement plasterers",
        ):
            command, result = self.route(task)
            self.assertIn("aos-hermes-coordinator.sh", command)
            self.assertNotIn("aos-hermes codex", command)
            self.assertIn("--prompt-file", command)
            self.assertEqual(result["selected_route"], "hermes_coordinator")

    def test_codex_forbidden_forces_hermes(self):
        for task in ("quick search, do not use Codex", "I don't want Codex to do it"):
            command, result = self.route(task)
            self.assertIn("aos-hermes-coordinator.sh", command)
            self.assertEqual(result["codex_forbidden"], "yes")
            self.assertEqual(result["delegation_reason"], "Codex forbidden by operator")

    def test_explicit_codex_is_direct(self):
        command, result = self.route("get Codex to inspect dashboard files")
        self.assertTrue(command.startswith('aos-codex "$(<'))
        self.assertEqual(result["selected_route"], "direct_codex")

    def test_explicit_claude_is_direct(self):
        command, result = self.route("get Claude to polish the dashboard UI")
        self.assertTrue(command.startswith('aos-hermes claude "$(<'))
        self.assertEqual(result["selected_route"], "direct_claude")

    def test_adversarial_prompts_use_temp_file_not_shell_text(self):
        task = "\n".join((
            "Markdown with `backticks` and $(touch /tmp/bad)",
            "Use $VARS and \"quotes\" and 'single quotes'",
            r"Windows path: C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live",
            "```bash",
            "echo should not run",
            "```",
            "x" * 5000,
        ))
        seen, result = self.route_with_prompt_file(task)

        self.assertEqual(result["selected_route"], "hermes_coordinator")
        self.assertIn("aos-hermes-coordinator.sh", seen["command"])
        self.assertIn("--prompt-file", seen["command"])
        self.assertNotIn("$(touch /tmp/bad)", seen["command"])
        self.assertNotIn("$VARS", seen["command"])
        self.assertNotIn("`backticks`", seen["command"])
        self.assertEqual(seen["prompt"], task)
        self.assertTrue(seen["prompt_exists_during_run"])
        self.assertFalse(seen["prompt_exists_after_run"])

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

    def test_simple_token_ledger_writes_only_exact_reported_usage(self):
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
            self.assertEqual([row["task_id"] for row in rows], ["AOS-2026-0102", "AOS-2026-0103"])
            self.assertEqual([row["tokens"] for row in rows], [12, 1205])
            self.assertEqual([row["basis"] for row in rows], ["exact", "exact"])

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

            self.assertFalse(ledger.exists())

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
            }])
            self.write_queue_templates(root)
            self.write_queue_references(root)
            commands = []
            prompts = []
            token_tasks = []

            def run_capture(command, timeout=60):
                commands.append(command)
                match = re.search(r"(?:--prompt-file\s+|<)(?P<quote>['\"]?)(?P<path>[^'\")]+)(?P=quote)", command)
                if match:
                    prompts.append(Path(match.group("path")).read_text(encoding="utf-8"))
                if len(commands) == 1:
                    return {
                        "success": True,
                        "output": "PASS\nFiles touched: workflows/queue_artifacts/AOS-2026-0099_output.md\nValidation: local check\nBlockers: None\nNext action: Liam review\nToken usage: unavailable from current CLI output",
                        "stdout": "PASS\nFiles touched: workflows/queue_artifacts/AOS-2026-0099_output.md\nValidation: local check\nBlockers: None\nNext action: Liam review",
                        "stderr": "",
                        "returncode": 0,
                    }
                return {"success": True, "output": "PASS", "stdout": "PASS", "stderr": "", "returncode": 0}

            def log_capture(route, agent, task, token_usage, token_usage_text, route_metadata=None):
                token_tasks.append(task)
                return {}

            with patch.object(backend, "BASE_DIR", root), \
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
            self.assertEqual(token_tasks, [f"AOS-2026-0099 | codex | {adversarial_title[:160]}"])
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
            "hermes": "default",
            "revenue": "default",
            "marketing": "default",
            "delivery": "default",
            "operations": "default",
            "codex": "default",
            "claude": "default",
        }
        for lane, profile in expected_profiles.items():
            self.assertEqual(backend._queue_resolve_route_metadata(lane)["profile"], profile)

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
            self.assertIn("- Attempt 1 worker: unavailable from current CLI output", receipt)

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

    def test_search_firecrawl_and_composio_decisions_stay_with_hermes(self):
        for task in ("search the web", "scrape this page", "use Firecrawl", "use Composio to check mail"):
            command, result = self.route(task)
            self.assertIn("aos-hermes-coordinator.sh", command, task)
            self.assertEqual(result["selected_route"], "hermes_coordinator")

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

    def test_non_prefix_queue_language_falls_through_to_hermes(self):
        command, result = self.route("Please add this to the queue: have Codex inspect the route")
        self.assertIn("aos-hermes-coordinator.sh", command)
        self.assertEqual(result["selected_route"], "hermes_coordinator")

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
        self.assertEqual(result["activeCount"], 3)
        self.assertEqual([item["id"] for item in result["activeItems"]], ["AOS-2026-0002", "AOS-2026-0003", "AOS-2026-0001"])
        self.assertEqual(result["nextItem"]["id"], "AOS-2026-0002")
        self.assertNotIn("Finished old task", json.dumps(result))

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
                self.assertIn("## Launch from PowerShell", prompt)
                self.assertIn("Do not launch agents automatically.", prompt)
            codex_prompt = codex["prompt"]
            claude_prompt = claude["prompt"]
            self.assertIn("codex --sandbox workspace-write --ask-for-approval never", codex_prompt)
            self.assertNotIn("aos-codex", codex_prompt)
            self.assertIn("aos-claude", claude_prompt)
            self.assertNotIn("aos-hermes claude", claude_prompt)

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
                    backend.QueueReviewClose(review_note="Looks good after receipt review."),
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
                        backend.QueueReviewClose(status=review_status, review_note=f"Set {review_status} from dashboard."),
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

    def test_dashboard_queue_review_close_rejects_non_review_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl") as run:
                with self.assertRaises(backend.HTTPException) as raised:
                    backend.close_queue_item_review(
                        "AOS-2026-0002",
                        backend.QueueReviewClose(review_note="Not ready for review close."),
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
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl", return_value=worker_result) as run, \
                 patch.object(backend, "wsl_claude") as claude, \
                 patch.object(backend, "wsl_hermes") as hermes, \
                 patch.object(backend, "_queue_run_hermes_review", return_value=review_result):
                result = backend.run_queue_item("AOS-2026-0002")

        run.assert_called_once()
        self.assertIn("aos-codex", run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["timeout"], 300)
        claude.assert_not_called()
        hermes.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["assigned_worker"], "codex")
        self.assertEqual(result["attempts_used"], 1)
        self.assertEqual(result["worker_result"]["timeout_seconds"], 300)

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
                 patch.object(backend, "_queue_run_hermes_review", return_value=review_result):
                result = backend.run_queue_item("AOS-2026-0002")

            self.assertEqual(result["status"], "human_review")
            self.assertEqual(result["receipt_path"], "queue/receipts/AOS-2026-0002.md")
            receipt_file = root / result["receipt_path"]
            self.assertTrue(receipt_file.exists())
            receipt_text = receipt_file.read_text(encoding="utf-8")
            self.assertIn("PASS", receipt_text)
            self.assertIn("Work item ID: AOS-2026-0002", receipt_text)
            self.assertIn("Assigned worker: codex", receipt_text)
            self.assertIn("Hermes review result: PASS", receipt_text)
            self.assertEqual(result["item"]["receipts"][0]["path"], result["receipt_path"])
            self.assertEqual(result["item"]["receipts"][0]["status"], "human_review")

    def test_queue_item_run_revise_triggers_exactly_one_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_queue_items(root, self.sample_queue_items())
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
            self.write_queue_items(root, self.sample_queue_items())
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
                "output": "Command timed out after 300s",
                "stdout": "",
                "stderr": "Command timed out after 300s",
                "returncode": -1,
                "timed_out": True,
                "timeout_seconds": 300,
            }
            review_result = {
                "success": True,
                "output": "REVISE: worker timed out before producing the required receipt",
                "returncode": 0,
                "token_usage_text": "Token usage: unavailable from current CLI output",
                "token_usage": {"available": False},
            }
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "_run_wsl", return_value=timeout_result) as run, \
                 patch.object(backend, "_queue_run_hermes_review", return_value=review_result):
                result = backend.run_queue_item("AOS-2026-0002")

            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args_list[0].kwargs["timeout"], 300)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["attempts_used"], 1)
            self.assertTrue(result["worker_result"]["timed_out"])
            receipt_text = (root / result["receipt_path"]).read_text(encoding="utf-8")
            self.assertIn("Agent command timed out after 300s", receipt_text)
            self.assertIn("Worker timed out after 300s", receipt_text)

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

    def test_hermes_coordinator_uses_wsl_path_for_windows_backend_path(self):
        windows_script = PureWindowsPath(r"Z:\workspace\tools\aos-hermes-coordinator.sh")
        with patch.object(backend, "HERMES_COORDINATOR", windows_script), \
             patch.object(backend, "_run_wsl", return_value=self.RUN_RESULT) as run, \
             patch.object(backend, "_log_token_usage"):
            result = backend.wsl_hermes(backend.TaskRun(task="summarize the queue"))

        command = run.call_args.args[0]
        self.assertTrue(command.startswith("/mnt/z/workspace/tools/aos-hermes-coordinator.sh "))
        self.assertNotIn(r"Z:\workspace", command)
        self.assertEqual(result["selected_route"], "hermes_coordinator")

    def test_wsl_path_helper_preserves_posix_paths(self):
        self.assertEqual(
            backend._path_for_wsl_command("/mnt/c/workspace/tools/aos-hermes-coordinator.sh"),
            "/mnt/c/workspace/tools/aos-hermes-coordinator.sh",
        )
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
        with patch.object(backend, "_run_wsl", return_value=self.RUN_RESULT) as run, \
             patch.object(backend, "_log_token_usage"):
            codex = backend.wsl_codex(backend.TaskRun(task="inspect files"))
            codex_command = run.call_args.args[0]
            claude = backend.wsl_claude(backend.TaskRun(task="polish UI"))
            claude_command = run.call_args.args[0]
        self.assertTrue(codex_command.startswith('aos-codex "$(<'))
        self.assertTrue(claude_command.startswith('aos-hermes claude "$(<'))
        self.assertNotIn("inspect files", codex_command)
        self.assertNotIn("polish UI", claude_command)
        self.assertEqual(codex["selected_route"], "direct_codex")
        self.assertEqual(claude["selected_route"], "direct_claude")

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
