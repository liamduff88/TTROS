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

    def write_queue_items(self, root, items):
        queue = root / "queue"
        queue.mkdir(parents=True)
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
        (context / "ACCESS_MODEL.md").write_text((source_root / "context" / "ACCESS_MODEL.md").read_text(encoding="utf-8"), encoding="utf-8")

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
                context="Keep the workflow manual.",
                sources="dashboard/frontend/src/views/Queue.jsx\nqueue/templates/codex_task.prompt.md",
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
            self.assertEqual(created["item"]["source"], "dashboard")
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
        self.assertEqual(codex_command, "aos-codex 'inspect files'")
        self.assertEqual(claude_command, "aos-hermes claude 'polish UI'")
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
