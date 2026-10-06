"""AOS-2026-0528: queue/operator lifecycle repair, validated on local fixtures only.

No test here reaches Telegram: every send goes to an in-memory fake through
the existing prepare/record send path.
"""
import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import aos_orchestration as orchestration
from tests.test_aos_queue import load_tool_module, parse_json, run_cli

RECIPIENT = "telegram-test-recipient-0001"
COMPLETION_ARGS = (
    "--definition-of-done", "The requested local state is verified.",
    "--allowed-actions", "local reads,local writes,validation commands",
    "--stop-conditions", "external action required,validation fails",
)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def read_items(root):
    path = root / "queue" / "work_items.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def queue_item(item_id, status, **extra):
    base = {
        "id": item_id, "title": f"Fixture {item_id}", "status": status, "priority": 5,
        "requested_by": "Liam", "owner_type": "agent", "owner": "operations",
        "source": "dashboard/hermes_message", "tags": [], "context": "", "sources": [],
        "source_refs": [], "allowed_actions": ["local_read"], "stop_conditions": ["external_send"],
        "definition_of_done": "done", "claim": {"claimed_by": None, "claimed_at": None},
        "receipts": [], "created_at": "2026-10-04T04:38:46Z", "updated_at": "2026-10-04T04:38:46Z",
    }
    base.update(extra)
    return base


def seed_history(root):
    """Evidence of earlier items whose records left work_items.jsonl without tombstones."""
    write_jsonl(root / "queue" / "orchestration_events.jsonl", [
        {"event": "notification_logged", "item_id": "AOS-2026-0921", "key": "blocked:originating_channel",
         "created_at": "2026-09-12T01:45:54Z", "effect_id": "orchestration:history-0921"},
    ])
    receipt = root / "queue" / "receipts" / "AOS-2026-0950-notification-0000000000000000.md"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text("PASS\n", encoding="utf-8")


class DuplicateIdPreventionTests(unittest.TestCase):
    def test_allocator_reserves_ids_named_only_in_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_history(root)
            before = {p: p.read_bytes() for p in (root / "queue").rglob("*") if p.is_file()}
            created = run_cli(root, "create", "--title", "After history", "--owner", "codex", *COMPLETION_ARGS)
            self.assertEqual(0, created.returncode, created.stderr)
            self.assertEqual("AOS-2026-0951", parse_json(created.stdout)["id"])
            for path, content in before.items():
                self.assertEqual(content, path.read_bytes(), f"history rewritten: {path}")

    def test_save_refuses_duplicate_ids_in_both_writers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = load_tool_module()
            dupes = [queue_item("AOS-2026-0001", "inbox"), queue_item("AOS-2026-0001", "inbox")]
            # The tool modules import aos_queue_storage under its bare name, so
            # match the refusal by message rather than by class identity.
            with self.assertRaisesRegex(RuntimeError, "duplicate work item id refused: AOS-2026-0001"):
                module.save_items(root, dupes)
            with self.assertRaisesRegex(RuntimeError, "duplicate work item id refused: AOS-2026-0001"):
                orchestration.save_items(root, dupes)
            self.assertFalse((root / "queue" / "work_items.jsonl").exists())

    def test_queue_tool_loads_inside_a_process_holding_an_older_storage_module(self):
        # The live backend/executor re-load aos-queue.py per call but keep the
        # aos_queue_storage imported at start; a missing helper must not break it.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        import aos_queue_storage as current
        stale = types.ModuleType("aos_queue_storage")
        for name in ("QueueStorageError", "durable_replace_text", "fsync_directory", "queue_write_lock"):
            setattr(stale, name, getattr(current, name))
        with patch.dict(sys.modules, {"aos_queue_storage": stale}):
            module = load_tool_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_history(root)
            self.assertEqual("AOS-2026-0951", module.next_id([], "2026-10-04T00:00:00Z", root))
            with self.assertRaisesRegex(RuntimeError, "duplicate work item id refused"):
                module.save_items(root, [queue_item("AOS-2026-0001", "inbox")] * 2)

    def test_dashboard_fallback_allocator_reserves_history(self):
        backend = importlib.import_module("dashboard.backend.main")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_history(root)
            allocated = backend._QueueToolFallback._next_id(root, [queue_item("AOS-2026-0003", "done")], "2026-10-04T00:00:00Z")
            self.assertEqual("AOS-2026-0951", allocated)


class SupersessionLifecycleTests(unittest.TestCase):
    def _create(self, root, title, *extra):
        result = run_cli(root, "create", "--title", title, "--owner", "codex", *COMPLETION_ARGS, *extra)
        self.assertEqual(0, result.returncode, result.stderr)
        return parse_json(result.stdout)

    def _done(self, root, item_id):
        receipt = root / "queue" / "receipts" / f"{item_id}-fixture.md"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        rel = f"queue/receipts/{item_id}-fixture.md"
        receipt.write_text(f"PASS\n\nValidation:\n- Fixture passed.\n\nArtifacts:\n- {rel}\n", encoding="utf-8")
        result = run_cli(root, "receipt", item_id, rel, "--status", "done")
        self.assertEqual(0, result.returncode, result.stderr)
        return parse_json(result.stdout)

    def test_stale_blocked_parent_and_open_children_are_retired_without_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = self._create(root, "Blocked objective")
            child = self._create(root, "Never-run stage", "--parent-id", parent["id"])
            run_cli(root, "status", parent["id"], "blocked")
            before_count = len(read_items(root))

            result = run_cli(root, "supersede", parent["id"], "--reason", "Stage 2 accepted by Liam; objective obsolete.")

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual([parent["id"], child["id"]], parse_json(result.stdout)["closed"])
            items = {row["id"]: row for row in read_items(root)}
            self.assertEqual(before_count, len(items))
            for item_id, previous in ((parent["id"], "blocked"), (child["id"], "inbox")):
                row = items[item_id]
                self.assertEqual("cancelled", row["status"])
                self.assertEqual(previous, row["supersession"]["previous_status"])
                self.assertTrue((root / row["supersession"]["receipt_path"]).is_file())
            replay = run_cli(root, "supersede", parent["id"], "--reason", "again")
            self.assertEqual([], parse_json(replay.stdout)["closed"])

    def test_supersede_refuses_live_or_finished_work_and_unfinished_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            working = self._create(root, "Running")
            run_cli(root, "status", working["id"], "agent_working")
            blocked = self._create(root, "Blocked")
            run_cli(root, "status", blocked["id"], "blocked")
            pending = self._create(root, "Replacement not done")

            refused_live = run_cli(root, "supersede", working["id"], "--reason", "x")
            refused_replacement = run_cli(
                root, "supersede", blocked["id"], "--reason", "x", "--superseded-by", pending["id"],
            )

            self.assertNotEqual(0, refused_live.returncode)
            self.assertNotEqual(0, refused_replacement.returncode)
            items = {row["id"]: row for row in read_items(root)}
            self.assertEqual("agent_working", items[working["id"]]["status"])
            self.assertEqual("blocked", items[blocked["id"]]["status"])

    def test_completed_replacement_retires_the_blocker_it_declares(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_parent = self._create(root, "Old blocked objective")
            old_child = self._create(root, "Old blocked stage", "--parent-id", old_parent["id"])
            run_cli(root, "status", old_parent["id"], "blocked")
            run_cli(root, "status", old_child["id"], "blocked")
            replacement = self._create(root, "Replacement objective", "--supersedes", old_parent["id"])
            self.assertEqual([old_parent["id"]], replacement["supersedes"])

            items = {row["id"]: row for row in read_items(root)}
            self.assertEqual("blocked", items[old_parent["id"]]["status"], "must not close before replacement is done")
            self._done(root, replacement["id"])

            items = {row["id"]: row for row in read_items(root)}
            for item_id in (old_parent["id"], old_child["id"]):
                self.assertEqual("cancelled", items[item_id]["status"])
                self.assertEqual(replacement["id"], items[item_id]["supersession"]["superseded_by"])
            self.assertEqual("done", items[replacement["id"]]["status"])

    def test_supersedes_must_name_an_existing_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_cli(root, "create", "--title", "Bad", *COMPLETION_ARGS, "--supersedes", "AOS-2026-9999")
            self.assertNotEqual(0, result.returncode)
            self.assertFalse((root / "queue" / "work_items.jsonl").exists() and read_items(root))


class ReusedIdNotificationIdempotencyTests(unittest.TestCase):
    """An ID re-issued before the allocator fix must not inherit older send evidence."""

    def _root(self, tmp, item):
        root = Path(tmp)
        write_json(root / "queue" / "notifications.json", {
            "escalation": {"unanswered_minutes": 10},
            "allowlist": {"telegram": [RECIPIENT], "agentmail_internal": []},
        })
        write_jsonl(root / "queue" / "work_items.jsonl", [item])
        key = "async_completion:done"
        stable = orchestration.telegram_idempotency_key(item["id"], "telegram_escalation", key, RECIPIENT)
        effect = orchestration.effect_identity("telegram_escalation", item["id"], f"{key}|{RECIPIENT}")
        write_jsonl(root / orchestration.EVENTS_PATH, [
            {"event": "telegram_send_intent", "item_id": item["id"], "key": key, "recipient": RECIPIENT,
             "idempotency_key": stable, "effect_id": f"{effect}:intent", "created_at": "2026-09-12T01:00:00Z"},
            {"event": "telegram_escalation", "item_id": item["id"], "key": key, "recipient": RECIPIENT,
             "idempotency_key": stable, "result": "sent", "sent": True, "receipt_path": "queue/receipts/old.md",
             "effect_id": f"{effect}:result", "created_at": "2026-09-12T01:00:01Z"},
            {"event": "notification_logged", "item_id": item["id"], "key": "blocked:originating_channel",
             "receipt_path": "queue/receipts/old-n.md", "created_at": "2026-09-12T01:00:02Z",
             "effect_id": orchestration.effect_identity("notification_logged", item["id"], "blocked:originating_channel")},
        ])
        return root

    def test_reissued_id_sends_once_for_its_own_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            current = queue_item("AOS-2026-0525", "done")
            root = self._root(tmp, current)
            sends = []
            fake = lambda chat, text: sends.append((chat, text))

            first = orchestration.attempt_telegram_send(root, current, RECIPIENT, "done", send_telegram=fake, key="async_completion:done")
            orchestration.append_jsonl(root / orchestration.EVENTS_PATH, first)
            second = orchestration.attempt_telegram_send(root, current, RECIPIENT, "done", send_telegram=fake, key="async_completion:done")

            self.assertEqual("sent", first["result"])
            self.assertEqual("already_sent", second["result"])
            self.assertEqual(1, len(sends))

    def test_items_without_earlier_history_keep_their_existing_identities(self):
        events = [{"event": "notification_logged", "item_id": "AOS-2026-0001", "created_at": "2026-10-04T05:00:00Z"}]
        item = queue_item("AOS-2026-0001", "blocked")
        self.assertEqual("", orchestration.item_generation(events, item))
        self.assertEqual("k", orchestration.generation_key("k", ""))

    def test_reissued_blocked_item_gets_its_own_attention_notifications(self):
        with tempfile.TemporaryDirectory() as tmp:
            current = queue_item("AOS-2026-0523", "blocked")
            root = self._root(tmp, current)
            result = orchestration.tick(root, allow_telegram_escalation=False)
            logged = [row for row in result["notifications"] if row["event"] == "notification_logged"]
            self.assertEqual({"blocked:originating_channel", "blocked:needs_me_rail"}, {row["key"] for row in logged})
            again = orchestration.tick(root, allow_telegram_escalation=False)
            self.assertEqual([], again["notifications"])


class DashboardOperatorCallbackTests(unittest.TestCase):
    """Telegram completion/attention callback through the existing send path, fake sender only."""

    @classmethod
    def setUpClass(cls):
        cls.backend = importlib.import_module("dashboard.backend.main")

    def _fixture(self, tmp, items):
        root = Path(tmp)
        write_json(root / "queue" / "notifications.json", {
            "escalation": {"unanswered_minutes": 10},
            "allowlist": {"telegram": [RECIPIENT], "agentmail_internal": []},
        })
        write_jsonl(root / "queue" / "work_items.jsonl", items)
        return root

    def _patched(self, root):
        return [
            patch.object(self.backend, "BASE_DIR", root),
            patch.object(self.backend, "_record_telegram_binding", lambda *a, **k: None),
            patch.object(self.backend, "_telegram_configured_operator_chat", lambda: None),
            patch.object(orchestration, "default_bridge_send", side_effect=AssertionError("live bridge must not be used")),
        ]

    def _run(self, root, fn):
        patches = self._patched(root)
        for active in patches:
            active.start()
        try:
            return fn()
        finally:
            for active in reversed(patches):
                active.stop()

    def handoff(self, item_id, status, **extra):
        # Live David hand-offs carry a conversation id, not a chat id, in reply_to.
        return queue_item(item_id, status, dispatch={"reply_to": "dashboard-operator", "idempotency_key": f"k-{item_id}"}, **extra)

    def test_david_handoff_completion_reports_once_with_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = "queue/receipts/AOS-2026-0001-executive-objective.md"
            root = self._fixture(tmp, [self.handoff("AOS-2026-0001", "done", receipts=[{"path": receipt, "status": "done"}])])
            (root / receipt).parent.mkdir(parents=True, exist_ok=True)
            (root / receipt).write_text("PASS\n", encoding="utf-8")
            sends = []
            fake = lambda chat, text, document_paths=None: sends.append((chat, text, document_paths)) or {
                "documents": [{"sent": True} for _ in document_paths or []]}

            first = self._run(root, lambda: self.backend._notify_queue_completion("AOS-2026-0001", "done", receipt, send_telegram=fake))
            second = self._run(root, lambda: self.backend._notify_queue_completion("AOS-2026-0001", "done", receipt, send_telegram=fake))

            self.assertEqual("sent", first["result"])
            self.assertEqual("already_sent", second["result"])
            self.assertEqual(1, len(sends))
            chat, text, docs = sends[0]
            self.assertEqual(RECIPIENT, chat)
            self.assertIn("Status: done", text)
            self.assertIn("Next action: None; the result is attached.", text)
            self.assertEqual([str(root / receipt)], docs)

    def test_attention_states_report_promptly_and_local_items_stay_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fixture(tmp, [
                self.handoff("AOS-2026-0002", "blocked"),
                self.handoff("AOS-2026-0003", "needs_input"),
                self.handoff("AOS-2026-0004", "human_review"),
                queue_item("AOS-2026-0005", "blocked", source="local"),
            ])
            sends = []
            fake = lambda chat, text: sends.append(text)
            results = {
                item_id: self._run(root, lambda item_id=item_id, status=status: self.backend._notify_queue_completion(
                    item_id, status, "", send_telegram=fake))
                for item_id, status in (
                    ("AOS-2026-0002", "blocked"), ("AOS-2026-0003", "needs_input"),
                    ("AOS-2026-0004", "human_review"), ("AOS-2026-0005", "blocked"),
                )
            }
            self.assertEqual("sent", results["AOS-2026-0002"]["result"])
            self.assertEqual("sent", results["AOS-2026-0003"]["result"])
            self.assertEqual("sent", results["AOS-2026-0004"]["result"])
            self.assertIsNone(results["AOS-2026-0005"])
            self.assertEqual(3, len(sends))
            self.assertIn("Status: failed", sends[0])
            self.assertIn("Next action: Reply with the requested input.", sends[1])
            self.assertIn("Next action: Review the attached closeout.", sends[2])

    def test_objective_stage_reports_the_objective_outcome_not_each_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent_receipt = "queue/receipts/AOS-2026-0010-executive-objective-blocked.md"
            parent = self.handoff("AOS-2026-0010", "blocked", owner_type="workflow",
                                  receipts=[{"path": parent_receipt, "status": "blocked"}])
            child = self.handoff("AOS-2026-0011", "blocked", parent_id="AOS-2026-0010")
            root = self._fixture(tmp, [parent, child])
            sends = []
            fake = lambda chat, text: sends.append(text)

            silent = self._run(root, lambda: self.backend._notify_terminal_outcome(
                child, "done", "queue/receipts/AOS-2026-0011.md",
                parent={**parent, "status": "agent_working"}, objective_child=True, send_telegram=fake))
            blocked = self._run(root, lambda: self.backend._notify_terminal_outcome(
                child, "blocked", "queue/receipts/AOS-2026-0011.md",
                parent=parent, objective_child=True, send_telegram=fake))

            self.assertIsNone(silent)
            self.assertEqual("sent", blocked["result"])
            self.assertEqual("AOS-2026-0010", blocked["item_id"])
            self.assertEqual(1, len(sends))
            self.assertIn("[AOS-2026-0010", sends[0])


class RunnerStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = importlib.import_module("dashboard.backend.main")

    def _status(self, root, *, unit_pid, cmdlines):
        with patch.object(self.backend, "_systemd_unit_main_pid", lambda unit: unit_pid), \
                patch.object(self.backend, "_process_cmdline", lambda pid: cmdlines.get(pid)):
            return self.backend._queue_runner_status(root)

    def _root(self, tmp, pid):
        root = Path(tmp)
        if pid is not None:
            (root / "logs" / "runtime").mkdir(parents=True)
            (root / "logs" / "runtime" / "runner.pid").write_text(f"{pid}\n", encoding="utf-8")
        return root

    def runner_cmd(self, root):
        return f"python {root / 'tools' / 'aos-orchestration-runner.py'} --root {root} --skip-telegram-escalation --watch --interval 5 "

    def test_systemd_runner_is_healthy_even_with_stale_pid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, 30039)
            status = self._status(root, unit_pid=138240, cmdlines={138240: self.runner_cmd(root)})
            self.assertEqual(
                {"available": True, "state": "running", "pid": 138240, "source": "systemd",
                 "pid_file": {"pid": 30039, "state": "stale"}},
                status,
            )

    def test_dead_pid_without_systemd_runner_is_stale_not_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, 30039)
            status = self._status(root, unit_pid=None, cmdlines={})
            self.assertFalse(status["available"])
            self.assertEqual("stale_pid", status["state"])

    def test_one_shot_dispatch_process_is_not_the_recurring_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, 4242)
            one_shot = f"python {root / 'tools' / 'aos-orchestration-runner.py'} --dispatch-item AOS-2026-0001"
            status = self._status(root, unit_pid=None, cmdlines={4242: one_shot})
            self.assertFalse(status["available"])

    def test_live_pid_file_still_counts_without_systemd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp, 4242)
            status = self._status(root, unit_pid=None, cmdlines={4242: self.runner_cmd(root)})
            self.assertEqual(("running", "pid_file"), (status["state"], status["source"]))

    def test_missing_pid_file_and_no_runner_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = self._status(self._root(tmp, None), unit_pid=None, cmdlines={})
            self.assertEqual("unavailable", status["state"])

    def test_operator_status_reports_running_idle_and_names_the_stale_pid_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_jsonl(root / "queue" / "work_items.jsonl", [queue_item("AOS-2026-0001", "done")])
            runner = {"available": True, "state": "running", "pid": 1, "source": "systemd",
                      "pid_file": {"pid": 30039, "state": "stale"}}
            with patch.object(self.backend, "BASE_DIR", root), \
                    patch.object(self.backend, "_queue_runner_status", lambda root=None: runner):
                closeout = self.backend._operator_system_status_closeout()
            text = json.dumps(closeout)
            self.assertIn("Runner state: running_idle (logs/runtime/runner.pid is stale; systemd is authoritative)", text)


if __name__ == "__main__":
    unittest.main()
