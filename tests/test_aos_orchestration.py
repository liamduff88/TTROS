import builtins
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from tools import aos_orchestration as runner
from tools import aos_queue_storage as storage


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_items(root, items):
    queue = root / "queue"
    queue.mkdir(parents=True, exist_ok=True)
    (queue / "work_items.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in items),
        encoding="utf-8",
    )


def read_items(root):
    return [json.loads(line) for line in (root / "queue" / "work_items.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def item(item_id, status, **extra):
    base = {
        "id": item_id,
        "title": item_id,
        "status": status,
        "priority": 5,
        "requested_by": "Liam",
        "owner_type": "agent",
        "owner": "operations",
        "source": "unit",
        "tags": [],
        "context": "",
        "sources": [],
        "source_refs": [],
        "allowed_actions": ["local_read"],
        "stop_conditions": ["external_send"],
        "definition_of_done": "done",
        "claim": {"claimed_by": None, "claimed_at": None},
        "receipts": [],
        "created_at": "2026-07-09T00:00:00Z",
        "updated_at": "2026-07-09T00:00:00Z",
    }
    base.update(extra)
    return base


class AosOrchestrationTests(unittest.TestCase):
    def test_completion_event_persists_successful_canonical_attachment_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "queue" / "notifications.json", {
                "escalation": {"unanswered_minutes": 10},
                "allowlist": {"telegram": ["123"], "agentmail_internal": []},
            })
            receipt = root / "queue" / "receipts" / "AOS-2026-0207.md"
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text("PASS\n", encoding="utf-8")
            work = item("AOS-2026-0207", "human_review", source="telegram")

            def sender(recipient, message, document_paths=None):
                return {
                    "message_sent": True,
                    "documents": [{"path": path, "sent": True} for path in document_paths or []],
                }

            result = runner.attempt_telegram_send(
                root, work, "123", "completion", send_telegram=sender,
                key="async_completion:human_review", document_paths=[str(receipt)],
            )

        self.assertTrue(result["sent"])
        self.assertEqual(result["attachments"], [{
            "path": "queue/receipts/AOS-2026-0207.md", "sent": True,
        }])

    def test_operator_notification_format_covers_required_status_fixtures(self):
        cases = [
            ("agent_todo", "queued"),
            ("needs_input", "needs input"),
            ("human_review", "ready for review"),
            ("done", "done"),
            ("blocked", "failed"),
            ("agent_working", "running"),
        ]
        for status, label in cases:
            with self.subTest(status=status):
                work = item("AOS-2026-0139", status, title="Receipt delivery improvement")
                message = runner.format_operator_work_item_notification(
                    work,
                    status,
                    summary="Receipt delivery improvement was validated locally.",
                    receipt_path="queue/receipts/AOS-2026-0139.md" if status in {"done", "human_review", "blocked"} else None,
                )
                self.assertTrue(message.startswith("[AOS-2026-0139 — Receipt delivery improvement]\nWork item: AOS-2026-0139"))
                self.assertIn(f"Status: {label}", message)
                self.assertIn("Summary: Receipt delivery improvement was validated locally.", message)
                self.assertNotIn("[AOS-2026-0139]", message)

    def test_multiple_pending_item_labels_show_id_before_title(self):
        rows = [
            runner.operator_item_label(item("AOS-2026-0131", "agent_todo", title="Gmail draft capability")),
            runner.operator_item_label(item("AOS-2026-0136", "human_review", title="Telegram approval-routing test")),
            runner.operator_item_label(item("AOS-2026-0139", "needs_input", title="Receipt delivery improvement")),
        ]
        self.assertEqual(rows, [
            "AOS-2026-0131 — Gmail draft capability",
            "AOS-2026-0136 — Telegram approval-routing test",
            "AOS-2026-0139 — Receipt delivery improvement",
        ])

    def test_generic_work_command_title_uses_specific_context_heading(self):
        work = item("AOS-2026-0161", "human_review", title="/work claude PERMISSION MODE — SCOPED LOCAL TASK APPROVED")
        work["context"] = "\n".join((
            "/work claude PERMISSION MODE — SCOPED LOCAL TASK APPROVED",
            "Do not ask for permission during this scoped local task.",
            "NEEDS ME AND TASK-LABEL UX REPAIR — COMPLETE BOUNDED OUTCOME",
        ))
        self.assertEqual(
            runner.operator_item_label(work),
            "AOS-2026-0161 — NEEDS ME AND TASK-LABEL UX REPAIR — COMPLETE BOUNDED OUTCOME",
        )

    def test_generic_work_command_title_uses_inline_heading(self):
        work = item(
            "AOS-2026-0160",
            "done",
            title="/work claude CANONICAL CLAUDE AND TELEGRAM ATTACHMENT PROOF. Work only...",
        )
        work["context"] = (
            "/work claude CANONICAL CLAUDE AND TELEGRAM ATTACHMENT PROOF. "
            "Work only in /home/liam/agentic-os-live."
        )
        self.assertEqual(
            runner.operator_item_label(work),
            "AOS-2026-0160 — CANONICAL CLAUDE AND TELEGRAM ATTACHMENT PROOF",
        )

    def test_running_and_recovered_notifications_are_title_first(self):
        running = item("AOS-2026-0136", "agent_working", title="Telegram approval-routing test")
        running_message = runner.format_operator_work_item_notification(
            running,
            "agent_working",
            summary="Telegram approval-routing test is now running through the assigned worker.",
        )
        self.assertTrue(running_message.startswith("[AOS-2026-0136 — Telegram approval-routing test]\nWork item: AOS-2026-0136"))
        self.assertIn("Status: running", running_message)

        recovered = item("AOS-2026-0139", "blocked", title="Receipt delivery improvement")
        recovered_message = runner.format_operator_work_item_notification(
            recovered,
            "blocked",
            summary="Receipt delivery improvement recovered a stuck worker and is blocked for review.",
            receipt_path="queue/receipts/AOS-2026-0139-stuck.md",
            receipt_attached=True,
        )
        self.assertTrue(recovered_message.startswith("[AOS-2026-0139 — Receipt delivery improvement]\nWork item: AOS-2026-0139"))
        self.assertIn("Status: failed", recovered_message)
        self.assertIn("Receipt: attached", recovered_message)

    def test_dashboard_notification_and_approval_paths_use_title_first_helpers(self):
        source = (Path(__file__).resolve().parents[1] / "dashboard" / "backend" / "main.py").read_text(encoding="utf-8")
        self.assertIn("def _notify_queue_running", source)
        self.assertIn("running_notification = _notify_queue_running(item_id)", source)
        self.assertIn("aos_orchestration.format_operator_work_item_notification(\n            refreshed", source)
        self.assertIn("candidate_ids = sorted(aos_orchestration.operator_item_label(row) for row in candidates)", source)
        self.assertIn("Work item title: {aos_orchestration.operator_task_title(item)}", source)

    def test_attention_escalation_telegram_message_uses_title_first_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "queue/notifications.json", {
                "escalation": {"unanswered_minutes": 1},
                "allowlist": {"telegram": ["1320777128"], "agentmail_internal": []},
            })
            stale = (datetime.now(timezone.utc) - timedelta(minutes=3)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            write_items(root, [item("AOS-2026-0139", "needs_input", title="Receipt delivery improvement", updated_at=stale)])
            runner.tick(root, allow_telegram_escalation=False)
            events = runner.read_jsonl(root / runner.EVENTS_PATH)
            for event in events:
                if event.get("event") == "notification_logged":
                    event["created_at"] = stale
            (root / runner.EVENTS_PATH).write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in events), encoding="utf-8"
            )
            sends = []
            runner.tick(root, send_telegram=lambda chat, text: sends.append((chat, text)))

        self.assertEqual(1, len(sends))
        self.assertTrue(sends[0][1].startswith("[AOS-2026-0139 — Receipt delivery improvement]\nWork item: AOS-2026-0139"))
        self.assertIn("Status: needs input", sends[0][1])

    def test_generic_dependency_unlock_runs_work_before_human_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue/receipts").mkdir(parents=True)
            write_json(root / "queue/notifications.json", {"escalation": {}, "allowlist": {}})
            write_items(root, [
                item("AOS-2026-0201", "done", receipts=[{"path": "queue/receipts/one.md", "created_at": "2026-07-11T00:00:00Z", "status": "done"}]),
                item("AOS-2026-0202", "inbox", parent_id="AOS-2026-0200", step_index=2,
                     depends_on=["AOS-2026-0201"], on_complete="human_review"),
            ])
            runner.tick(root, allow_telegram_escalation=False)
            self.assertEqual("agent_todo", {row["id"]: row for row in read_items(root)}["AOS-2026-0202"]["status"])

    def test_workflow_parent_finalizes_with_correction_and_ticks_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue/receipts").mkdir(parents=True)
            write_json(root / "queue/notifications.json", {"escalation": {}, "allowlist": {}})
            tags = ["pkg:test", "pkgver:abc"]
            parent = item("AOS-2026-0200", "inbox", owner_type="workflow", owner="hermes", tags=tags + ["pass:parent"])
            child = item("AOS-2026-0201", "done", parent_id=parent["id"], step_index=1,
                         tags=tags + ["pass:1"], receipts=[{"path": "queue/receipts/one.md", "created_at": "2026-07-11T00:00:00Z", "status": "done"}])
            write_items(root, [parent, child])
            first = runner.tick(root, allow_telegram_escalation=False)
            second = runner.tick(root, allow_telegram_escalation=False)
            rows = {row["id"]: row for row in read_items(root)}
            self.assertEqual("human_review", rows[parent["id"]]["status"])
            self.assertEqual(1, sum(row["event"] == "workflow_parent_review_ready" for row in first["advanced"]))
            self.assertEqual([], second["advanced"])

            rows[parent["id"]]["status"] = "inbox"
            correction = item("AOS-2026-0202", "agent_todo", parent_id=parent["id"], step_index=2,
                              tags=tags + ["pass:correction-1"])
            write_items(root, list(rows.values()) + [correction])
            runner.tick(root, allow_telegram_escalation=False)
            self.assertEqual("inbox", {row["id"]: row for row in read_items(root)}[parent["id"]]["status"])
            correction["status"] = "done"
            correction["receipts"] = [{"path": "queue/receipts/correction.md", "created_at": "2026-07-11T00:01:00Z", "status": "done"}]
            current = {row["id"]: row for row in read_items(root)}
            current[correction["id"]] = correction
            write_items(root, list(current.values()))
            runner.tick(root, allow_telegram_escalation=False)
            self.assertEqual("human_review", {row["id"]: row for row in read_items(root)}[parent["id"]]["status"])
    def test_linux_launcher_uses_only_existing_runner_watch_mode(self):
        root = Path(__file__).resolve().parents[1]
        launcher = (root / "tools" / "aos-linux-runtime.sh").read_text(encoding="utf-8")
        self.assertIn('RUNNER_SCRIPT="${ROOT}/tools/aos-orchestration-runner.py"', launcher)
        self.assertIn("canonical_runner_pid", launcher)
        self.assertIn("--watch --interval", launcher)
        self.assertNotIn("while true", launcher)
        self.assertIn("desktop-start) desktop_start", launcher)
        self.assertIn("desktop_cleanup\n  preflight\n  start_backend\n  start_frontend", launcher)
        self.assertNotIn("desktop_cleanup\n  preflight\n  start_backend\n  start_frontend\n  start_runner", launcher)
        self.assertIn("if ! wait_http \"$BACKEND_URL\" backend; then\n    stop", launcher)
        self.assertIn("if ! wait_http \"$FRONTEND_URL\" frontend; then\n    stop", launcher)
        self.assertIn("grep -Ev 'grep|rg|codex|aos-linux-runtime\\.sh'", launcher)

    def test_existing_runner_watch_mode_is_bounded_for_validation(self):
        root_dir = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            (root / "queue").mkdir()
            (root / "queue" / "work_items.jsonl").write_text("", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(root_dir / "tools" / "aos-orchestration-runner.py"),
                 "--root", str(root), "--skip-telegram-escalation", "--watch", "--interval", "0.05", "--max-ticks", "2"],
                cwd=root_dir, text=True, capture_output=True, timeout=10,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(2, result.stdout.count('"success": true'))

    def test_tick_effects_reconcile_after_final_queue_save_failure(self):
        for mode in ("before_replace", "after_replace"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "queue/receipts").mkdir(parents=True)
                (root / "queue/receipts/step1.md").write_text("PASS\n", encoding="utf-8")
                write_json(root / "queue/notifications.json", {"escalation": {}, "allowlist": {}})
                write_items(root, [
                    item("AOS-2026-0001", "done", parent_id="AOS-2026-0000", step_index=1,
                         receipts=[{"path": "queue/receipts/step1.md", "created_at": "2026-07-09T00:00:00Z", "status": "done"}]),
                    item("AOS-2026-0002", "inbox", parent_id="AOS-2026-0000", step_index=2,
                         depends_on=["AOS-2026-0001"]),
                ])
                real_save = runner.save_items
                calls = 0

                def fail_final(save_root, items):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        if mode == "after_replace":
                            real_save(save_root, items)
                        raise OSError("injected final queue save failure")
                    return real_save(save_root, items)

                with patch.object(runner, "save_items", side_effect=fail_final):
                    with self.assertRaises(OSError):
                        runner.tick(root, allow_telegram_escalation=False)
                runner.tick(root, allow_telegram_escalation=False)
                runner.tick(root, allow_telegram_escalation=False)
                rows = {row["id"]: row for row in read_items(root)}
                self.assertEqual("agent_todo", rows["AOS-2026-0002"]["status"])
                events = runner.read_jsonl(root / runner.EVENTS_PATH)
                self.assertEqual(1, sum(row.get("event") == "step_advanced" for row in events))
                self.assertEqual(1, len(list((root / "queue/receipts").glob("AOS-2026-0002-runner-*.md"))))
                tokens = runner.read_jsonl(root / runner.TOKEN_LEDGER_PATH)
                self.assertEqual(1, sum(row.get("event") == "step_advanced" for row in tokens))

    def test_notification_send_attempt_is_suppressed_after_queue_save_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "queue/notifications.json", {
                "escalation": {"unanswered_minutes": 1},
                "allowlist": {"telegram": ["1320777128"], "agentmail_internal": []},
            })
            stale = (datetime.now(timezone.utc) - timedelta(minutes=3)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            write_items(root, [item("AOS-2026-0001", "needs_input", updated_at=stale)])
            runner.tick(root, send_telegram=lambda *_: None)
            events = runner.read_jsonl(root / runner.EVENTS_PATH)
            for event in events:
                if event.get("event") == "notification_logged":
                    event["created_at"] = stale
            (root / runner.EVENTS_PATH).write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in events), encoding="utf-8"
            )
            sends = []
            real_save = runner.save_items

            def fail_after_replace(save_root, items):
                real_save(save_root, items)
                raise OSError("directory sync ambiguity")

            with patch.object(runner, "save_items", side_effect=fail_after_replace):
                with self.assertRaises(OSError):
                    runner.tick(root, send_telegram=lambda chat, text: sends.append((chat, text)))
            runner.tick(root, send_telegram=lambda chat, text: sends.append((chat, text)))
            self.assertEqual(1, len(sends))
            events = runner.read_jsonl(root / runner.EVENTS_PATH)
            self.assertEqual(1, sum(row.get("event") == "telegram_escalation" and row.get("result") == "sent" for row in events))
            sent = next(row for row in events if row.get("event") == "telegram_escalation" and row.get("result") == "sent")
            reconciled = read_items(root)[0]
            self.assertEqual(1, sum(row.get("path") == sent["receipt_path"] for row in reconciled["receipts"]))

    def test_acceptance_artifact_receipt_and_ledgers_reconcile_after_save_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent_id, dep_id, final_id = "AOS-2026-0100", "AOS-2026-0102", "AOS-2026-0103"
            result_dir = root / "results/orchestration_acceptance" / parent_id
            result_dir.mkdir(parents=True)
            (root / "queue/receipts").mkdir(parents=True)
            source = f"results/orchestration_acceptance/{parent_id}/01_source_pack.md"
            brief = f"results/orchestration_acceptance/{parent_id}/02_speed_to_lead_micro_brief.md"
            review = f"queue/receipts/{dep_id}-review.md"
            (root / source).write_text("source", encoding="utf-8")
            (root / brief).write_text("brief", encoding="utf-8")
            (root / review).write_text("approved", encoding="utf-8")
            write_json(root / "queue/notifications.json", {"escalation": {}, "allowlist": {}})
            write_items(root, [
                item(parent_id, "agent_todo", owner="hermes"),
                item(dep_id, "done", receipts=[{"path": review, "created_at": "2026-07-10T00:00:00Z", "status": "done"}]),
                item(final_id, "agent_todo", parent_id=parent_id, step_index=3, depends_on=[dep_id],
                     owner="delivery", workbench="local", tags=["orchestration_acceptance"],
                     source_refs=[source, brief, review]),
            ])
            real_save = runner.save_items
            calls = 0

            def fail_final(save_root, items):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("queue acknowledgment failed")
                return real_save(save_root, items)

            with patch.object(runner, "save_items", side_effect=fail_final):
                with self.assertRaises(OSError):
                    runner.tick(root, allow_telegram_escalation=False)
            runner.tick(root, allow_telegram_escalation=False)
            runner.tick(root, allow_telegram_escalation=False)
            final_artifact = root / f"results/orchestration_acceptance/{parent_id}/03_final_review_package.md"
            self.assertTrue(final_artifact.exists())
            self.assertEqual(1, len(list((root / "queue/receipts").glob(f"{final_id}-final-closeout-*.md"))))
            events = runner.read_jsonl(root / runner.EVENTS_PATH)
            self.assertEqual(1, sum(row.get("event") == "acceptance_finalized" for row in events))
            tokens = runner.read_jsonl(root / runner.TOKEN_LEDGER_PATH)
            self.assertEqual(1, sum(row.get("event") == "acceptance_finalized" for row in tokens))
            rows = {row["id"]: row for row in read_items(root)}
            self.assertEqual("done", rows[final_id]["status"])
            self.assertEqual("done", rows[parent_id]["status"])
    def test_tick_holds_shared_write_lock_even_when_no_rewrite_is_needed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "queue" / "notifications.json", {"escalation": {}, "allowlist": {}})
            write_items(root, [item("AOS-2026-0001", "inbox")])
            real_lock = runner.queue_write_lock
            calls = []

            @runner.contextmanager
            def observed_lock(lock_root):
                calls.append(Path(lock_root))
                with real_lock(lock_root):
                    yield

            with patch.object(runner, "queue_write_lock", observed_lock):
                runner.tick(root, allow_telegram_escalation=False)
            self.assertGreaterEqual(len(calls), 1)
            self.assertTrue(all(call == root for call in calls))

    def test_idle_tick_preserves_queue_and_persistent_tick_lock_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "queue" / "notifications.json", {"escalation": {}, "allowlist": {}})
            write_items(root, [item("AOS-2026-0001", "inbox")])
            first = runner.tick(root, allow_telegram_escalation=False)
            self.assertEqual([], first["advanced"])
            self.assertEqual([], first["notifications"])
            queue_path = root / runner.WORK_ITEMS_PATH
            tick_path = root / runner.TICK_LOCK_PATH
            queue_before = (queue_path.read_bytes(), queue_path.stat().st_mtime_ns, queue_path.stat().st_ctime_ns)
            tick_before = (tick_path.read_bytes(), tick_path.stat().st_mtime_ns, tick_path.stat().st_ctime_ns)
            second = runner.tick(root, allow_telegram_escalation=False)
            self.assertEqual([], second["advanced"])
            self.assertEqual([], second["notifications"])
            self.assertEqual(queue_before, (queue_path.read_bytes(), queue_path.stat().st_mtime_ns, queue_path.stat().st_ctime_ns))
            self.assertEqual(tick_before, (tick_path.read_bytes(), tick_path.stat().st_mtime_ns, tick_path.stat().st_ctime_ns))

    def test_tick_lock_requires_linux_fcntl_before_creating_lock(self):
        real_import = builtins.__import__

        def import_without_fcntl(name, *args, **kwargs):
            if name == "fcntl":
                raise ModuleNotFoundError("No module named 'fcntl'")
            return real_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(builtins, "__import__", side_effect=import_without_fcntl):
                with self.assertRaises(ModuleNotFoundError):
                    with runner.tick_lock(root):
                        pass
            self.assertFalse((root / runner.TICK_LOCK_PATH).exists())

    def test_three_step_acceptance_chain_gate_and_resume_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent_id = "AOS-2026-0100"
            step1_id = "AOS-2026-0101"
            step2_id = "AOS-2026-0102"
            step3_id = "AOS-2026-0103"
            result_dir = root / "results" / "orchestration_acceptance" / parent_id
            receipt_dir = root / "queue" / "receipts"
            result_dir.mkdir(parents=True)
            receipt_dir.mkdir(parents=True)
            write_json(root / "queue" / "notifications.json", {
                "escalation": {"unanswered_minutes": 10},
                "allowlist": {"telegram": [], "agentmail_internal": []},
            })
            source_pack = "results/orchestration_acceptance/AOS-2026-0100/01_source_pack.md"
            brief = "results/orchestration_acceptance/AOS-2026-0100/02_speed_to_lead_micro_brief.md"
            final_package = "results/orchestration_acceptance/AOS-2026-0100/03_final_review_package.md"
            (root / source_pack).write_text("source pack", encoding="utf-8")
            (receipt_dir / "step1.md").write_text(
                f"PASS\nArtifacts:\n- {source_pack}\nToken usage: no agent invocation\n",
                encoding="utf-8",
            )
            write_items(root, [
                item(parent_id, "agent_todo", title="TTR Speed-to-Lead Micro-Brief Acceptance", owner="hermes", tags=["orchestration_acceptance"]),
                item(step1_id, "done", parent_id=parent_id, step_index=1, owner="operations", workbench="local", receipts=[{"path": "queue/receipts/step1.md", "created_at": "2026-07-09T00:00:00Z", "status": "done"}]),
                item(step2_id, "inbox", parent_id=parent_id, step_index=2, depends_on=[step1_id], owner="marketing", workbench="hermes", on_complete="human_review"),
                item(step3_id, "inbox", parent_id=parent_id, step_index=3, depends_on=[step2_id], owner="delivery", workbench="local", tags=["orchestration_acceptance"]),
            ])

            first = runner.tick(root)
            second = runner.tick(root)
            items = {row["id"]: row for row in read_items(root)}
            self.assertEqual(len(first["advanced"]), 1)
            self.assertEqual(second["advanced"], [])
            self.assertEqual(items[step2_id]["status"], "human_review")
            self.assertEqual(items[step2_id]["source_refs"].count(source_pack), 1)
            self.assertEqual(items[step3_id]["status"], "inbox")

            (root / brief).write_text("approved brief", encoding="utf-8")
            (receipt_dir / "step2_review.md").write_text(
                f"PASS\nReview note:\nApproved for packaging.\nArtifacts:\n- {brief}\nToken usage: unavailable from current CLI output\n",
                encoding="utf-8",
            )
            items[step2_id]["status"] = "done"
            items[step2_id]["receipts"].append({"path": "queue/receipts/step2_review.md", "created_at": "2026-07-09T00:01:00Z", "status": "done"})
            write_items(root, list(items.values()))

            resume = runner.tick(root)
            repeated = runner.tick(root)
            items = {row["id"]: row for row in read_items(root)}
            self.assertEqual(len(resume["advanced"]), 2)
            self.assertEqual(repeated["advanced"], [])
            self.assertEqual(items[step3_id]["status"], "done")
            self.assertEqual(items[parent_id]["status"], "done")
            self.assertEqual(items[step3_id]["source_refs"].count(source_pack), 1)
            self.assertEqual(items[step3_id]["source_refs"].count(brief), 1)
            self.assertTrue(any("step2_review.md" in ref for ref in items[step3_id]["source_refs"]))

            closeout_receipts = list((root / "queue" / "receipts").glob(f"{step3_id}-final-closeout-*.md"))
            self.assertEqual(len(closeout_receipts), 1)
            self.assertIn("Final status: done", (root / final_package).read_text(encoding="utf-8"))

    def test_tick_advances_next_step_with_artifact_refs_and_stops_at_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue" / "receipts").mkdir(parents=True)
            (root / "results").mkdir()
            (root / "queue" / "receipts" / "step1.md").write_text(
                "PASS\nArtifact: results/step1-output.md\n",
                encoding="utf-8",
            )
            (root / "results" / "step1-output.md").write_text("artifact", encoding="utf-8")
            write_json(root / "queue" / "notifications.json", {
                "escalation": {"unanswered_minutes": 10},
                "allowlist": {"telegram": ["1320777128"], "agentmail_internal": []},
            })
            write_items(root, [
                item("AOS-2026-0001", "done", parent_id="AOS-2026-0000", step_index=1, receipts=[{"path": "queue/receipts/step1.md", "created_at": "2026-07-09T00:00:00Z", "status": "done"}]),
                item("AOS-2026-0002", "inbox", parent_id="AOS-2026-0000", step_index=2, depends_on=["AOS-2026-0001"], owner="marketing", workbench="lane"),
                item("AOS-2026-0003", "inbox", parent_id="AOS-2026-0000", step_index=3, depends_on=["AOS-2026-0002"], on_complete="human_review"),
            ])

            first = runner.tick(root)
            items = {row["id"]: row for row in read_items(root)}
            self.assertEqual(items["AOS-2026-0002"]["status"], "agent_todo")
            self.assertIn("results/step1-output.md", items["AOS-2026-0002"]["source_refs"])
            self.assertEqual(items["AOS-2026-0003"]["status"], "inbox")
            self.assertEqual(len(first["advanced"]), 1)

            items["AOS-2026-0002"]["status"] = "done"
            items["AOS-2026-0002"]["receipts"].append({"path": "queue/receipts/step2.md", "created_at": "2026-07-09T00:01:00Z", "status": "done"})
            write_items(root, list(items.values()))
            second = runner.tick(root)
            items = {row["id"]: row for row in read_items(root)}
            self.assertEqual(items["AOS-2026-0003"]["status"], "agent_todo")
            self.assertFalse(any(row["event"] == "notification_logged" and row["item_id"] == "AOS-2026-0003" for row in second["notifications"]))

    def test_tick_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue" / "receipts").mkdir(parents=True)
            (root / "queue" / "receipts" / "step1.md").write_text("PASS\n", encoding="utf-8")
            write_json(root / "queue" / "notifications.json", {"escalation": {"unanswered_minutes": 10}, "allowlist": {"telegram": ["1320777128"]}})
            write_items(root, [
                item("AOS-2026-0001", "done", parent_id="AOS-2026-0000", step_index=1, receipts=[{"path": "queue/receipts/step1.md", "created_at": "2026-07-09T00:00:00Z", "status": "done"}]),
                item("AOS-2026-0002", "inbox", parent_id="AOS-2026-0000", step_index=2, depends_on=["AOS-2026-0001"]),
            ])
            first = runner.tick(root)
            second = runner.tick(root)
            self.assertEqual(len(first["advanced"]), 1)
            self.assertEqual(second["advanced"], [])
            events = [json.loads(line) for line in (root / "queue" / "orchestration_events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(sum(1 for row in events if row.get("event") == "step_advanced"), 1)

    def test_escalates_once_to_allowlisted_telegram_and_blocks_other_recipient(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "queue" / "notifications.json", {
                "escalation": {"unanswered_minutes": 1},
                "allowlist": {"telegram": ["1320777128"], "agentmail_internal": []},
            })
            stale = (datetime.now(timezone.utc) - timedelta(minutes=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            write_items(root, [item("AOS-2026-0001", "needs_input", updated_at=stale)])
            sends = []

            first = runner.tick(root, send_telegram=lambda chat, text: sends.append((chat, text)))
            self.assertEqual(sends, [])
            old = (datetime.now(timezone.utc) - timedelta(minutes=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            events_path = root / "queue" / "orchestration_events.jsonl"
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
            for event in events:
                if event.get("event") == "notification_logged":
                    event["created_at"] = old
            events_path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
            second = runner.tick(root, send_telegram=lambda chat, text: sends.append((chat, text)))
            third = runner.tick(root, send_telegram=lambda chat, text: sends.append((chat, text)))
            self.assertEqual(len(sends), 1)
            self.assertEqual(sends[0][0], "1320777128")
            self.assertFalse(any(row.get("event") == "telegram_escalation" for row in first["notifications"]))
            self.assertTrue(any(row.get("result") == "sent" for row in second["notifications"]))
            self.assertFalse(any(row.get("event") == "telegram_escalation" for row in third["notifications"]))

            items = read_items(root)
            blocked = runner.attempt_telegram_send(root, items[0], "999", "blocked validation", key="blocked_validation")
            self.assertEqual(blocked["result"], "blocked")
            self.assertEqual(blocked["reason"], "recipient_not_allowlisted")
            self.assertFalse(blocked["sent"])

    def test_direct_telegram_validation_send_is_idempotent_by_key_and_recipient(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "queue" / "notifications.json", {
                "escalation": {"unanswered_minutes": 1},
                "allowlist": {"telegram": ["1320777128"], "agentmail_internal": []},
            })
            write_items(root, [item("AOS-2026-0001", "needs_input")])
            queue_item = read_items(root)[0]
            sends = []

            first = runner.attempt_telegram_send(
                root,
                queue_item,
                "1320777128",
                "Agentic OS validation send",
                send_telegram=lambda chat, text: sends.append((chat, text)),
                key="api_validation",
            )
            runner.append_jsonl(root / runner.EVENTS_PATH, first)
            second = runner.attempt_telegram_send(
                root,
                queue_item,
                "1320777128",
                "Agentic OS validation send",
                send_telegram=lambda chat, text: sends.append((chat, text)),
                key="api_validation",
            )

            self.assertEqual(len(sends), 1)
            self.assertEqual(first["result"], "sent")
            self.assertTrue(first["sent"])
            self.assertFalse(first["duplicate_blocked"])
            self.assertEqual(second["result"], "already_sent")
            self.assertFalse(second["sent"])
            self.assertTrue(second["duplicate_blocked"])
            self.assertEqual(second["prior_receipt_path"], first["receipt_path"])
            self.assertEqual(
                first["idempotency_key"],
                "AOS-2026-0001|telegram_escalation|api_validation|1320777128",
            )
            self.assertEqual(first["idempotency_key"], second["idempotency_key"])
            self.assertFalse("receipt_path" in second)

    def test_repeated_tick_does_not_duplicate_after_prior_success_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "queue" / "notifications.json", {
                "escalation": {"unanswered_minutes": 1},
                "allowlist": {"telegram": ["1320777128"], "agentmail_internal": []},
            })
            stale = (datetime.now(timezone.utc) - timedelta(minutes=2)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            write_items(root, [item("AOS-2026-0001", "needs_input", updated_at=stale)])
            sends = []

            runner.tick(root, send_telegram=lambda chat, text: sends.append((chat, text)))
            events_path = root / "queue" / "orchestration_events.jsonl"
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
            for event in events:
                if event.get("event") == "notification_logged":
                    event["created_at"] = stale
            events_path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")

            second = runner.tick(root, send_telegram=lambda chat, text: sends.append((chat, text)))
            third = runner.tick(root, send_telegram=lambda chat, text: sends.append((chat, text)))

            self.assertEqual(len(sends), 1)
            self.assertTrue(any(row.get("result") == "sent" for row in second["notifications"]))
            self.assertFalse(any(row.get("event") == "telegram_escalation" for row in third["notifications"]))
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
            sent_events = [row for row in events if row.get("event") == "telegram_escalation" and row.get("result") == "sent"]
            self.assertEqual(len(sent_events), 1)


def prime_escalation_due(root):
    """Create a needs_input item whose Telegram escalation is due on next tick."""
    write_json(root / "queue" / "notifications.json", {
        "escalation": {"unanswered_minutes": 1},
        "allowlist": {"telegram": ["1320777128"], "agentmail_internal": []},
    })
    stale = (datetime.now(timezone.utc) - timedelta(minutes=3)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    write_items(root, [item("AOS-2026-0001", "needs_input", updated_at=stale)])
    runner.tick(root, allow_telegram_escalation=False)
    events = runner.read_jsonl(root / runner.EVENTS_PATH)
    for event in events:
        if event.get("event") == "notification_logged":
            event["created_at"] = stale
    (root / runner.EVENTS_PATH).write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in events), encoding="utf-8"
    )


class TickLockScopeTests(unittest.TestCase):
    """Review M2: Telegram delivery must run outside the queue write lock."""

    def test_queue_mutation_succeeds_while_telegram_send_is_in_flight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prime_escalation_due(root)
            send_started = threading.Event()
            mutation_done = threading.Event()
            mutation_errors = []

            def mutate():
                try:
                    if not send_started.wait(10):
                        raise TimeoutError("telegram send never started")
                    with storage.queue_write_lock(root, wait_seconds=1):
                        rows = runner.load_items(root)
                        rows.append(item("AOS-2026-0002", "inbox"))
                        runner.durable_replace_text(root / runner.WORK_ITEMS_PATH, runner._items_text(rows))
                except Exception as exc:
                    mutation_errors.append(exc)
                finally:
                    mutation_done.set()

            def sender(chat, text, document_paths=None):
                send_started.set()
                if not mutation_done.wait(10):
                    raise TimeoutError("concurrent queue mutation never finished")
                return {"message_sent": True, "documents": []}

            worker = threading.Thread(target=mutate)
            worker.start()
            try:
                result = runner.tick(root, send_telegram=sender)
            finally:
                send_started.set()
                worker.join(15)
            self.assertEqual([], mutation_errors)
            self.assertTrue(any(row.get("result") == "sent" for row in result["notifications"]))
            rows = {row["id"] for row in read_items(root)}
            self.assertIn("AOS-2026-0002", rows)
            self.assertIn("AOS-2026-0001", rows)

    def test_send_intent_is_durably_recorded_before_send_fires(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prime_escalation_due(root)
            events_at_send_time = []

            def sender(chat, text, document_paths=None):
                events_at_send_time.extend(runner.read_jsonl(root / runner.EVENTS_PATH))
                return {"message_sent": True, "documents": []}

            runner.tick(root, send_telegram=sender)
            intents = [row for row in events_at_send_time if row.get("event") == "telegram_send_intent"]
            self.assertEqual(1, len(intents))
            self.assertFalse(any(
                row.get("event") == "telegram_escalation" and row.get("result") == "sent"
                for row in events_at_send_time
            ))
            events = runner.read_jsonl(root / runner.EVENTS_PATH)
            self.assertEqual(1, sum(row.get("event") == "telegram_send_intent" for row in events))
            self.assertEqual(1, sum(
                row.get("event") == "telegram_escalation" and row.get("result") == "sent" for row in events
            ))

    def test_failed_send_is_recorded_and_never_auto_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prime_escalation_due(root)

            def failing(chat, text, document_paths=None):
                raise RuntimeError("bridge down")

            second = runner.tick(root, send_telegram=failing)
            failed = [row for row in second["notifications"] if row.get("event") == "telegram_escalation"]
            self.assertEqual(["send_failed"], [row.get("result") for row in failed])
            calls = []

            def counting(chat, text, document_paths=None):
                calls.append((chat, text))
                return {"message_sent": True, "documents": []}

            third = runner.tick(root, send_telegram=counting)
            self.assertEqual([], calls)
            ambiguous = [row for row in third["notifications"] if row.get("event") == "telegram_escalation"]
            self.assertEqual(["ambiguous_not_retried"], [row.get("result") for row in ambiguous])
            self.assertTrue(all(row.get("duplicate_blocked") for row in ambiguous))

    def test_crash_between_intent_and_result_is_ambiguous_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prime_escalation_due(root)

            def crashing(chat, text, document_paths=None):
                raise KeyboardInterrupt()

            with self.assertRaises(KeyboardInterrupt):
                runner.tick(root, send_telegram=crashing)
            events = runner.read_jsonl(root / runner.EVENTS_PATH)
            self.assertEqual(1, sum(row.get("event") == "telegram_send_intent" for row in events))
            self.assertEqual(0, sum(row.get("event") == "telegram_escalation" for row in events))
            calls = []

            def counting(chat, text, document_paths=None):
                calls.append((chat, text))
                return {"message_sent": True, "documents": []}

            resumed = runner.tick(root, send_telegram=counting)
            self.assertEqual([], calls)
            escalations = [row for row in resumed["notifications"] if row.get("event") == "telegram_escalation"]
            self.assertEqual(["ambiguous_not_retried"], [row.get("result") for row in escalations])

    def test_repeated_tick_after_completed_send_is_duplicate_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prime_escalation_due(root)
            calls = []

            def counting(chat, text, document_paths=None):
                calls.append((chat, text))
                return {"message_sent": True, "documents": []}

            runner.tick(root, send_telegram=counting)
            runner.tick(root, send_telegram=counting)
            self.assertEqual(1, len(calls))
            events = runner.read_jsonl(root / runner.EVENTS_PATH)
            self.assertEqual(1, sum(row.get("event") == "telegram_send_intent" for row in events))
            self.assertEqual(1, sum(
                row.get("event") == "telegram_escalation" and row.get("result") == "sent" for row in events
            ))
            receipts = list((root / "queue" / "receipts").glob("AOS-2026-0001-telegram-escalation-*.md"))
            self.assertEqual(1, len(receipts))
            sent = next(row for row in events if row.get("event") == "telegram_escalation" and row.get("result") == "sent")
            reconciled = {row["id"]: row for row in read_items(root)}["AOS-2026-0001"]
            self.assertEqual(1, sum(row.get("path") == sent["receipt_path"] for row in reconciled["receipts"]))

    def test_review_close_tick_with_escalation_disabled_never_touches_sender(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prime_escalation_due(root)
            calls = []

            def counting(chat, text, document_paths=None):
                calls.append((chat, text))
                return {"message_sent": True, "documents": []}

            result = runner.tick(root, send_telegram=counting, allow_telegram_escalation=False)
            self.assertEqual([], calls)
            self.assertFalse(any(row.get("event") == "telegram_escalation" for row in result["notifications"]))
            events = runner.read_jsonl(root / runner.EVENTS_PATH)
            self.assertEqual(0, sum(row.get("event") == "telegram_send_intent" for row in events))


if __name__ == "__main__":
    unittest.main()
