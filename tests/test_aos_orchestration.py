import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools import aos_orchestration as runner


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
            self.assertEqual(items["AOS-2026-0003"]["status"], "human_review")
            self.assertTrue(any(row["event"] == "notification_logged" and row["item_id"] == "AOS-2026-0003" for row in second["notifications"]))

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


if __name__ == "__main__":
    unittest.main()
