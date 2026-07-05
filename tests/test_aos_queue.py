import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "aos-queue.py"


def load_tool_module():
    spec = importlib.util.spec_from_file_location("aos_queue", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(root, *args):
    return subprocess.run(
        [sys.executable, str(TOOL), "--root", str(root), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def parse_json(stdout):
    return json.loads(stdout)


class AosQueueTest(unittest.TestCase):
    def test_queue_json_files_and_schemas_load(self):
        json.loads((ROOT / "queue" / "agent_registry.json").read_text(encoding="utf-8"))
        json.loads((ROOT / "queue" / "schemas" / "work_item.schema.json").read_text(encoding="utf-8"))
        json.loads((ROOT / "queue" / "schemas" / "receipt.schema.json").read_text(encoding="utf-8"))
        for line in (ROOT / "queue" / "work_items.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)

    def test_create_list_and_show_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            default_owner = run_cli(root, "create", "--title", "Unassigned default")
            self.assertEqual(default_owner.returncode, 0, default_owner.stderr)
            self.assertEqual(parse_json(default_owner.stdout)["owner"], "unassigned")

            created = run_cli(
                root,
                "create",
                "--title",
                "Draft local queue",
                "--requested-by",
                "liam",
                "--owner",
                "codex",
                "--priority",
                "8",
                "--tags",
                "queue,local",
            )

            self.assertEqual(created.returncode, 0, created.stderr)
            item = parse_json(created.stdout)
            self.assertRegex(item["id"], r"^AOS-\d{4}-0002$")
            self.assertEqual(item["status"], "inbox")
            self.assertEqual(item["claim"], {"claimed_by": None, "claimed_at": None})
            self.assertEqual(item["tags"], ["queue", "local"])

            listed = run_cli(root, "list", "--json")
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertEqual(parse_json(listed.stdout)[0]["id"], item["id"])

            shown = run_cli(root, "show", item["id"])
            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertEqual(parse_json(shown.stdout)["title"], "Draft local queue")

    def test_claim_release_status_and_receipt_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = parse_json(run_cli(root, "create", "--title", "Move work", "--owner", "codex").stdout)

            claimed = run_cli(root, "claim", item["id"], "codex")
            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            claimed_item = parse_json(claimed.stdout)
            self.assertEqual(claimed_item["status"], "agent_working")
            self.assertEqual(claimed_item["claim"]["claimed_by"], "codex")
            self.assertIsNotNone(claimed_item["claim"]["claimed_at"])

            released = run_cli(root, "release", item["id"])
            self.assertEqual(released.returncode, 0, released.stderr)
            released_item = parse_json(released.stdout)
            self.assertEqual(released_item["status"], "agent_todo")
            self.assertEqual(released_item["claim"], {"claimed_by": None, "claimed_at": None})

            status = run_cli(root, "status", item["id"], "human_review")
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(parse_json(status.stdout)["status"], "human_review")

            receipt = run_cli(root, "receipt", item["id"], "queue/receipts/unit.md", "--status", "done")
            self.assertEqual(receipt.returncode, 0, receipt.stderr)
            receipt_item = parse_json(receipt.stdout)
            self.assertEqual(receipt_item["status"], "done")
            self.assertEqual(receipt_item["receipts"][0]["path"], "queue/receipts/unit.md")

    def test_next_returns_highest_priority_available_item_for_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            low = parse_json(
                run_cli(root, "create", "--title", "Low", "--owner", "codex", "--priority", "1").stdout
            )
            high = parse_json(
                run_cli(root, "create", "--title", "High", "--owner", "codex", "--priority", "9").stdout
            )
            other = parse_json(
                run_cli(root, "create", "--title", "Other", "--owner", "marketing", "--priority", "99").stdout
            )

            next_result = run_cli(root, "next", "codex")
            self.assertEqual(next_result.returncode, 0, next_result.stderr)
            self.assertEqual(parse_json(next_result.stdout)["id"], high["id"])

            self.assertEqual(run_cli(root, "claim", high["id"], "codex").returncode, 0)
            next_after_claim = run_cli(root, "next", "codex")
            self.assertEqual(parse_json(next_after_claim.stdout)["id"], low["id"])
            self.assertNotEqual(parse_json(next_after_claim.stdout)["id"], other["id"])

    def test_status_and_agent_validation_reject_bad_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = parse_json(run_cli(root, "create", "--title", "Validate", "--owner", "codex").stdout)

            bad_status = run_cli(root, "status", item["id"], "waiting")
            self.assertNotEqual(bad_status.returncode, 0)
            self.assertIn("Invalid status", bad_status.stderr)

            bad_agent = run_cli(root, "claim", item["id"], "unknown")
            self.assertNotEqual(bad_agent.returncode, 0)
            self.assertIn("Unknown agent", bad_agent.stderr)

    def test_module_helpers_keep_ids_stable_and_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = load_tool_module()
            first = parse_json(run_cli(root, "create", "--title", "One", "--owner", "codex").stdout)
            second = parse_json(run_cli(root, "create", "--title", "Two", "--owner", "codex").stdout)

            self.assertEqual(second["id"][-4:], "0002")
            self.assertEqual(module.find_item(module.load_items(root), first["id"])["title"], "One")


if __name__ == "__main__":
    unittest.main()
