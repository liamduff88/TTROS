import builtins
import concurrent.futures
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import aos_queue_storage as storage


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "aos-queue.py"
ROLLUP = ROOT / "scripts" / "token_rollup.py"
RUNNER_TOOL = ROOT / "tools" / "aos-orchestration-runner.py"


def load_tool_module():
    spec = importlib.util.spec_from_file_location("aos_queue", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_rollup_module():
    spec = importlib.util.spec_from_file_location("token_rollup", ROLLUP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_runner_module():
    spec = importlib.util.spec_from_file_location("aos_orchestration_runner", RUNNER_TOOL)
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
    def _write_codex_reconcile_fixture(
        self, root, item_id="AOS-2026-0001", *, status="human_review",
        session_id="session-implementation", receipt_placeholder=False,
    ):
        (root / "queue/receipts").mkdir(parents=True)
        shutil.copy(ROOT / "queue/token_ledger_schema.json", root / "queue/token_ledger_schema.json")
        receipt = f"queue/receipts/{item_id}.md"
        receipt_text = (
            "PASS\n\nToken usage: unavailable from current CLI output.\nToken usage: no agent invocation\n"
            if receipt_placeholder else
            f"PASS\n\n<!-- token_usage:{item_id} -->\n## token_usage\n```json\n{{\"token_usage\":{{}}}}\n```\n"
        )
        (root / receipt).write_text(receipt_text, encoding="utf-8")
        item = {
            "id": item_id,
            "title": "Codex capture fixture",
            "status": status,
            "owner": "codex",
            "receipts": [{"path": receipt, "created_at": "2026-07-12T00:00:00Z", "status": status}],
        }
        (root / "queue/work_items.jsonl").write_text(json.dumps(item) + "\n", encoding="utf-8")
        unavailable = {
            "orchestrator": {"input": 0, "output": 0},
            "subagents": [],
            "workbenches": [],
            "totals": {"input": 0, "output": 0},
            "est_cost_usd": 0.0,
            "unavailable": ["workbench session totals"],
        }
        ledger = {
            "item_id": item_id,
            "session_id": session_id,
            "invocation_id": session_id,
            "lane": "codex",
            "profile": "default",
            "timestamp": "2026-07-12T00:00:00Z",
            "escalated": False,
            "model_requested": "Codex workbench session",
            "model_confirmed": "unavailable",
            "budget_class": "standard",
            "token_usage": unavailable,
            "effect_id": f"codex:{item_id}:{session_id}:tokens",
        }
        (root / "queue/token_ledger.jsonl").write_text(json.dumps(ledger) + "\n", encoding="utf-8")
        (root / f"queue/receipts/{item_id}.token_usage.json").write_text(
            json.dumps({"token_usage": unavailable, "profile_invocation": {"invoked": True, "session_id": session_id}}) + "\n",
            encoding="utf-8",
        )
        return receipt

    def test_codex_summary_parser_uses_final_exact_summary_and_checks_total(self):
        module = load_tool_module()
        output = "Token usage: total=3 input=2 output=1\nnoise\nToken usage: total=445,969 input=407,724 (+ 11,271,424 cached) output=38,245 (reasoning 12,856)\n"
        parsed = module.parse_codex_token_summary(output)
        self.assertEqual(445_969, parsed["total"])
        self.assertEqual(407_724, parsed["input"])
        self.assertEqual(38_245, parsed["output"])
        self.assertEqual(11_271_424, parsed["cached"])
        self.assertEqual(12_856, parsed["reasoning"])
        with self.assertRaisesRegex(module.QueueError, "input \\+ output"):
            module.parse_codex_token_summary("Token usage: total=4 input=2 output=1")

        json_parsed = module.parse_codex_token_summary(
            '{"type":"turn.completed","usage":{"input_tokens":12477,"cached_input_tokens":9984,'
            '"output_tokens":9,"reasoning_output_tokens":0}}\n'
        )
        self.assertEqual(12_486, json_parsed["total"])
        self.assertEqual("turn.completed JSONL", json_parsed["summary_format"])
        preferred = module.parse_codex_token_summary(
            "Token usage: total=13 input=8 output=5\n"
            '{"type":"turn.completed","usage":{"input_tokens":8,"output_tokens":5}}\n'
        )
        self.assertEqual(13, preferred["total"])
        self.assertEqual("turn.completed JSONL", preferred["summary_format"])
        self.assertEqual("Token usage: total=13 input=8 output=5", preferred["terminal_summary_cross_check"])
        with self.assertRaisesRegex(module.QueueError, "conflicts"):
            module.parse_codex_token_summary(
                "Token usage: total=3 input=2 output=1\n"
                '{"type":"turn.completed","usage":{"input_tokens":8,"output_tokens":5}}\n'
            )
        with self.assertRaisesRegex(module.QueueError, "subset"):
            module.parse_codex_token_summary(
                "Token usage: total=3 input=2 output=1 (reasoning 2)"
            )

    def test_codex_reconciliation_replaces_one_row_and_receipt_block_idempotently(self):
        module = load_tool_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt = self._write_codex_reconcile_fixture(root)
            summary = module.parse_codex_token_summary(
                "Token usage: total=445,969 input=407,724 (+ 11,271,424 cached) output=38,245 (reasoning 12,856)"
            )
            first = module.reconcile_codex_usage(
                root, "AOS-2026-0001", summary, "codex-cli 0.144.1", "session-implementation"
            )
            second = module.reconcile_codex_usage(
                root, "AOS-2026-0001", summary, "codex-cli 0.144.1", "session-implementation"
            )
            rows = [json.loads(line) for line in (root / "queue/token_ledger.jsonl").read_text().splitlines()]
            sidecar = json.loads((root / "queue/receipts/AOS-2026-0001.token_usage.json").read_text())
            receipt_text = (root / receipt).read_text()

            self.assertEqual(first, second)
            self.assertEqual(1, len(rows))
            self.assertEqual({"input": 407_724, "output": 38_245}, rows[0]["token_usage"]["totals"])
            self.assertEqual(rows[0]["token_usage"], sidecar["token_usage"])
            self.assertEqual(11_271_424, sidecar["capture_evidence"]["cached_input_tokens"])
            self.assertEqual(445_969, sidecar["capture_evidence"]["total_tokens"])
            self.assertEqual(12_856, rows[0]["capture_evidence"]["reasoning_output_tokens"])
            self.assertEqual("unavailable", rows[0]["model_confirmed"])
            self.assertEqual(1, receipt_text.count("<!-- token_usage:AOS-2026-0001 -->"))
            self.assertEqual(1, receipt_text.count("## token_usage"))
            self.assertEqual(1, receipt_text.count("## token_usage"))

    def test_codex_reconciliation_is_status_independent_and_preserves_status(self):
        module = load_tool_module()
        summary = module.parse_codex_token_summary("Token usage: total=30 input=20 output=10")
        for status in ("human_review", "done", "needs_input", "blocked"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self._write_codex_reconcile_fixture(root, status=status)
                result = module.reconcile_codex_usage(
                    root, "AOS-2026-0001", summary, "codex-cli test", "session-implementation"
                )
                self.assertEqual(status, result["queue_status"])
                item = json.loads((root / "queue/work_items.jsonl").read_text())
                self.assertEqual(status, item["status"])

    def test_done_review_sidecar_cannot_downgrade_existing_exact_usage(self):
        module = load_tool_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue/receipts").mkdir(parents=True)
            receipt = root / "queue/receipts/AOS-2026-0001-review.md"
            receipt.write_text("PASS\n", encoding="utf-8")
            exact = {
                "orchestrator": {"input": 0, "output": 0},
                "subagents": [],
                "workbenches": [{"tool": "codex", "input": 20, "output": 10, "source": "reported"}],
                "totals": {"input": 20, "output": 10},
                "est_cost_usd": 0.0,
                "unavailable": ["Codex model identity"],
            }
            unavailable = {
                "orchestrator": {"input": 0, "output": 0},
                "subagents": [], "workbenches": [],
                "totals": {"input": 0, "output": 0},
                "est_cost_usd": 0.0,
                "unavailable": ["workbench session totals"],
            }
            module._write_receipt_token_usage(root, "AOS-2026-0001", None, exact, {"invoked": True})
            module._write_receipt_token_usage(
                root, "AOS-2026-0001", "queue/receipts/AOS-2026-0001-review.md",
                unavailable, {"invoked": False},
            )
            sidecar = json.loads((root / "queue/receipts/AOS-2026-0001.token_usage.json").read_text())
            self.assertEqual({"input": 20, "output": 10}, sidecar["token_usage"]["totals"])
            self.assertEqual(1, receipt.read_text().count("<!-- token_usage:AOS-2026-0001 -->"))

    def test_codex_unavailable_exact_and_conflict_reconciliation_rules(self):
        module = load_tool_module()
        exact = module.parse_codex_token_summary(
            "Token usage: total=30 input=20 (+ 100 cached) output=10 (reasoning 4)"
        )
        conflict = module.parse_codex_token_summary("Token usage: total=31 input=20 output=11")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_codex_reconcile_fixture(root, receipt_placeholder=True)
            module.reconcile_codex_usage(root, "AOS-2026-0001", None, "codex-cli test", "session-implementation")
            upgraded = module.reconcile_codex_usage(root, "AOS-2026-0001", exact, "codex-cli test", "session-implementation")
            retained = module.reconcile_codex_usage(root, "AOS-2026-0001", None, "codex-cli test", "session-implementation")
            self.assertEqual({"input": 20, "output": 10}, upgraded["token_usage"]["totals"])
            self.assertEqual(upgraded["token_usage"], retained["token_usage"])
            with self.assertRaisesRegex(module.QueueError, "Conflicting exact"):
                module.reconcile_codex_usage(root, "AOS-2026-0001", conflict, "codex-cli test", "session-implementation")
            receipt_text = (root / upgraded["receipt"]).read_text()
            self.assertNotIn("unavailable from current CLI output", receipt_text)
            self.assertEqual(1, receipt_text.count("<!-- token_usage:AOS-2026-0001 -->"))

    def test_codex_sessions_remain_separate_and_do_not_merge(self):
        module = load_tool_module()
        implementation = module.parse_codex_token_summary("Token usage: total=30 input=20 output=10")
        repair = module.parse_codex_token_summary("Token usage: total=12 input=7 output=5")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_codex_reconcile_fixture(root)
            module.reconcile_codex_usage(root, "AOS-2026-0001", implementation, "codex-cli test", "session-implementation")
            module.reconcile_codex_usage(root, "AOS-2026-0001", repair, "codex-cli test", "session-repair")
            rows = [json.loads(line) for line in (root / "queue/token_ledger.jsonl").read_text().splitlines()]
            identities = [(row["item_id"], row.get("session_id")) for row in rows]
            self.assertEqual(1, identities.count(("AOS-2026-0001", "session-implementation")))
            self.assertEqual(1, identities.count(("AOS-2026-0001", "session-repair")))
            self.assertEqual([30, 12], [row["token_usage"]["totals"]["input"] + row["token_usage"]["totals"]["output"] for row in rows])
            sidecar = json.loads((root / "queue/receipts/AOS-2026-0001.token_usage.json").read_text())
            self.assertEqual("session-repair", sidecar["profile_invocation"]["session_id"])

    def test_codex_runner_waits_for_fake_process_exit_then_reconciles_explicit_item(self):
        module = load_tool_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_codex_reconcile_fixture(root)
            fake = root / "fake-codex"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "if '--version' in sys.argv:\n"
                "    print('codex-cli 0.144.1')\n"
                "else:\n"
                "    sys.stdin.read()\n"
                "    print('worker closeout')\n"
                "    print('Token usage: total=30 input=20 (+ 100 cached) output=10 (reasoning 4)')\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            result = module.run_codex_work_item(
                root, "AOS-2026-0001", "bounded fixture prompt", codex_bin=str(fake)
            )
            self.assertEqual({"input": 20, "output": 10}, result["token_usage"]["totals"])
            self.assertTrue(result["capture_evidence"]["captured_after_process_exit"])
            self.assertEqual("codex-cli 0.144.1", result["capture_evidence"]["cli_version"])

    def test_codex_runner_reconciles_process_exit_usage_before_nonzero_failure(self):
        module = load_tool_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_codex_reconcile_fixture(root)
            fake = root / "fake-codex"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "if '--version' in sys.argv:\n"
                "    print('codex-cli test')\n"
                "else:\n"
                "    sys.stdin.read()\n"
                "    print('{\"type\":\"thread.started\",\"thread_id\":\"session-failed\"}')\n"
                "    print('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":9,\"output_tokens\":2}}')\n"
                "    raise SystemExit(2)\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            with self.assertRaisesRegex(module.QueueError, "usage was reconciled"):
                module.run_codex_work_item(root, "AOS-2026-0001", "bounded fixture prompt", codex_bin=str(fake))
            rows = [json.loads(line) for line in (root / "queue/token_ledger.jsonl").read_text().splitlines()]
            failed = next(row for row in rows if row.get("session_id") == "session-failed")
            self.assertEqual({"input": 9, "output": 2}, failed["token_usage"]["totals"])

    def test_queue_release_requires_exact_complete_acquired_owner(self):
        changes = {
            "token": "replacement-token",
            "pid": 99999999,
            "process_start_id": "replacement-start",
            "host": "replacement-host",
            "runtime": "replacement-runtime",
            "lock_version": storage.LOCK_VERSION + 1,
        }
        for field, replacement in changes.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                lock = root / storage.LOCK_RELATIVE
                with self.assertRaises(storage.QueueStorageError):
                    with storage.queue_write_lock(root):
                        owner = storage.read_lock_owner(lock)
                        owner[field] = replacement
                        storage.durable_replace_text(
                            lock / storage.OWNER_FILE, json.dumps(owner, sort_keys=True) + "\n"
                        )
                self.assertTrue(lock.exists(), field)
                shutil.rmtree(lock)

    def test_queue_release_fails_closed_on_incomplete_owner_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / storage.LOCK_RELATIVE
            with self.assertRaises(storage.QueueStorageError):
                with storage.queue_write_lock(root):
                    owner = storage.read_lock_owner(lock)
                    owner.pop("process_start_id")
                    storage.durable_replace_text(
                        lock / storage.OWNER_FILE, json.dumps(owner, sort_keys=True) + "\n"
                    )
            self.assertTrue(lock.exists())

    def test_queue_exact_owner_release_remains_normal_and_durable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / storage.LOCK_RELATIVE
            with storage.queue_write_lock(root):
                self.assertTrue(lock.exists())
            self.assertFalse(lock.exists())
            self.assertEqual([], list(lock.parent.glob(f".{lock.name}.release-*")))

    def test_fresh_queue_lock_parent_namespace_fsync_failure_surfaces_before_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / storage.LOCK_RELATIVE
            real_sync = storage.fsync_directory

            def fail_locks_parent(path):
                if Path(path) == root / "queue":
                    raise OSError("injected locks-parent sync failure")
                return real_sync(path)

            with patch.object(storage, "fsync_directory", side_effect=fail_locks_parent):
                with self.assertRaisesRegex(OSError, "locks-parent sync failure"):
                    with storage.queue_write_lock(root):
                        self.fail("lock yielded before parent durability")
            self.assertFalse(lock.exists())

    def test_queue_publication_sync_failure_quarantines_canonical_and_retains_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / storage.LOCK_RELATIVE
            real_sync = storage.fsync_directory
            lock_parent_syncs = 0

            def fail_publication_once(path):
                nonlocal lock_parent_syncs
                if Path(path) == lock.parent:
                    lock_parent_syncs += 1
                    if lock_parent_syncs == 2:
                        raise OSError("injected canonical publication sync failure")
                return real_sync(path)

            with patch.object(storage, "fsync_directory", side_effect=fail_publication_once):
                with self.assertRaisesRegex(storage.QueueStorageError, "publication durability failed"):
                    with storage.queue_write_lock(root):
                        self.fail("lock yielded before canonical publication was durable")
            self.assertFalse(lock.exists())
            self.assertEqual(1, len(list(lock.parent.glob(f".{lock.name}.publication-failed-*"))))

    def test_queue_release_does_not_succeed_before_removal_directory_fsync(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / storage.LOCK_RELATIVE
            manager = storage.queue_write_lock(root)
            manager.__enter__()
            real_sync = storage.fsync_directory
            release_syncs = 0

            def fail_final_release_sync(path):
                nonlocal release_syncs
                if Path(path) == lock.parent:
                    release_syncs += 1
                    if release_syncs == 2:
                        raise OSError("injected release removal sync failure")
                return real_sync(path)

            with patch.object(storage, "fsync_directory", side_effect=fail_final_release_sync):
                with self.assertRaisesRegex(OSError, "release removal sync failure"):
                    manager.__exit__(None, None, None)
            self.assertFalse(lock.exists())

    def test_concurrent_durable_append_has_no_lost_records(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            target = root / "queue" / "concurrent-ledger.jsonl"
            code = (
                "from pathlib import Path; from tools.aos_queue_storage import durable_append_text; "
                "import sys; r=Path(sys.argv[1]); durable_append_text(r, r/'queue/concurrent-ledger.jsonl', sys.argv[2]+'\\n')"
            )

            def append(index):
                return subprocess.run(
                    [sys.executable, "-c", code, str(root), json.dumps({"writer": index})],
                    cwd=ROOT, text=True, capture_output=True, check=False,
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(append, range(24)))
            self.assertTrue(all(result.returncode == 0 for result in results), [result.stderr for result in results])
            rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(set(range(24)), {row["writer"] for row in rows})
            self.assertEqual(24, len(rows))

    def test_read_only_list_on_empty_root_creates_no_state(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            root = Path(tmp)
            result = run_cli(root, "list", "--json")
            self.assertNotEqual(0, result.returncode)
            self.assertEqual([], list(root.iterdir()))

    def test_stale_quarantine_never_deletes_replacement_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / storage.LOCK_RELATIVE
            lock.mkdir(parents=True)
            stale = storage._owner_payload("dead")
            stale.update(pid=99999999, process_start_id="dead")
            (lock / storage.OWNER_FILE).write_text(json.dumps(stale), encoding="utf-8")
            replacement = storage._owner_payload("replacement")
            real_rename = storage.os.rename

            def publish_replacement(source, target):
                real_rename(source, target)
                lock.mkdir()
                (lock / storage.OWNER_FILE).write_text(json.dumps(replacement), encoding="utf-8")

            with patch.object(storage.os, "rename", side_effect=publish_replacement):
                storage._remove_proven_stale(lock, stale)
            self.assertEqual("replacement", storage.read_lock_owner(lock)["token"])

    def test_quarantined_mismatch_and_malformed_metadata_fail_closed(self):
        for malformed in (False, True):
            with self.subTest(malformed=malformed), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                lock = root / storage.LOCK_RELATIVE
                lock.mkdir(parents=True)
                stale = storage._owner_payload("dead")
                stale.update(pid=99999999, process_start_id="dead")
                (lock / storage.OWNER_FILE).write_text(json.dumps(stale), encoding="utf-8")
                real_rename = storage.os.rename

                def alter_quarantine(source, target):
                    real_rename(source, target)
                    payload = "{}" if malformed else json.dumps({**stale, "token": "different"})
                    (Path(target) / storage.OWNER_FILE).write_text(payload, encoding="utf-8")

                with patch.object(storage.os, "rename", side_effect=alter_quarantine):
                    with self.assertRaises(storage.QueueStorageError):
                        storage._remove_proven_stale(lock, stale)
                self.assertTrue(lock.exists() or list(lock.parent.glob(f".{lock.name}.stale-*")))

    def test_two_stale_recoverers_do_not_remove_new_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / storage.LOCK_RELATIVE
            lock.mkdir(parents=True)
            stale = storage._owner_payload("dead")
            stale.update(pid=99999999, process_start_id="dead")
            (lock / storage.OWNER_FILE).write_text(json.dumps(stale), encoding="utf-8")
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: self._try_lock(root), range(2)))
            self.assertEqual(2, len(results))
            self.assertFalse(lock.exists())

    @staticmethod
    def _try_lock(root):
        try:
            with storage.queue_write_lock(root, wait_seconds=0.5):
                return "acquired"
        except storage.QueueStorageError:
            return "blocked"

    def test_eacces_retry_paths_are_bounded_and_honest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attempts = 0

            def denied(*_args):
                nonlocal attempts
                attempts += 1
                raise PermissionError(storage.errno.EACCES, "denied")

            started = time.monotonic()
            with patch.object(storage.os, "rename", side_effect=denied):
                with self.assertRaises(PermissionError):
                    with storage.queue_write_lock(root, wait_seconds=0):
                        pass
            self.assertEqual(1, attempts)
            self.assertLess(time.monotonic() - started, 0.5)

            for owner_kind in ("live", "malformed"):
                lock = root / storage.LOCK_RELATIVE
                lock.mkdir(parents=True, exist_ok=True)
                (lock / storage.OWNER_FILE).write_text(
                    json.dumps(storage._owner_payload("live")) if owner_kind == "live" else "{}",
                    encoding="utf-8",
                )
                attempts = 0
                started = time.monotonic()
                with patch.object(storage.os, "rename", side_effect=denied):
                    with self.assertRaises(storage.QueueStorageError):
                        with storage.queue_write_lock(root, wait_seconds=0):
                            pass
                self.assertLessEqual(attempts, 1)
                self.assertLess(time.monotonic() - started, 0.5)
                if lock.exists():
                    import shutil
                    shutil.rmtree(lock)

    def test_done_effects_reconcile_without_duplicates_across_save_ambiguity(self):
        for mode in ("intent_before", "intent_after", "ack_before", "ack_after"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                module = load_tool_module()
                item = parse_json(run_cli(root, "create", "--title", "Fault done", "--owner", "codex").stdout)
                real_replace = module.durable_replace_text
                calls = 0

                def fault(path, text):
                    nonlocal calls
                    if Path(path).name == "work_items.jsonl":
                        target = 0 if mode.startswith("intent") else 1
                        current = calls
                        calls += 1
                        if current != target:
                            return real_replace(path, text)
                        if mode.endswith("after"):
                            real_replace(path, text)
                        raise OSError(f"{mode} failure")
                    return real_replace(path, text)

                with patch.object(module, "durable_replace_text", side_effect=fault):
                    with self.assertRaises(OSError):
                        module.update_status(root, item["id"], "done")
                module.update_status(root, item["id"], "done")
                module.update_status(root, item["id"], "done")
                rows = module.load_items(root)
                self.assertEqual("done", rows[0]["status"])
                for name in ("run_ledger.jsonl", "token_ledger.jsonl"):
                    lines = (root / "queue" / name).read_text(encoding="utf-8").splitlines()
                    self.assertEqual(1, len(lines), (mode, name))

    def test_standalone_runner_and_concurrent_creator_both_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = parse_json(run_cli(root, "create", "--title", "Runner target").stdout)
            runner_module = load_runner_module()
            loaded = threading.Event()
            release = threading.Event()

            def paused_attempt(_root, item, recipient, message, **_kwargs):
                loaded.set()
                release.wait(3)
                return {
                    "event": "telegram_escalation", "item_id": item["id"], "key": "manual_validation",
                    "recipient": recipient, "result": "blocked", "sent": False,
                    "effect_id": "runner-concurrency-result", "created_at": "2026-07-10T00:00:00Z",
                }

            with patch.object(runner_module, "attempt_telegram_send", side_effect=paused_attempt):
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    manual = pool.submit(runner_module.run_manual_attempt, root, first["id"], "", "test")
                    self.assertTrue(loaded.wait(2))
                    creator = pool.submit(run_cli, root, "create", "--title", "Concurrent creator")
                    release.set()
                    manual.result(timeout=5)
                    created = creator.result(timeout=5)
            self.assertEqual(0, created.returncode, created.stderr)
            rows = [json.loads(line) for line in (root / "queue/work_items.jsonl").read_text().splitlines()]
            self.assertEqual(2, len(rows))
            self.assertEqual({first["id"], parse_json(created.stdout)["id"]}, {row["id"] for row in rows})
    def test_two_simultaneous_creates_are_unique_and_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda n: run_cli(root, "create", "--title", f"Concurrent {n}"), range(2)))
            self.assertTrue(all(result.returncode == 0 for result in results), [r.stderr for r in results])
            rows = [json.loads(line) for line in (root / "queue/work_items.jsonl").read_text().splitlines()]
            self.assertEqual(2, len(rows))
            self.assertEqual(2, len({row["id"] for row in rows}))

    def test_many_concurrent_creators_have_no_lost_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda n: run_cli(root, "create", "--title", f"Burst {n}"), range(12)))
            self.assertTrue(all(result.returncode == 0 for result in results), [r.stderr for r in results])
            rows = [json.loads(line) for line in (root / "queue/work_items.jsonl").read_text().splitlines()]
            self.assertEqual(12, len(rows))
            self.assertEqual(12, len({row["id"] for row in rows}))

    def test_concurrent_readers_never_observe_partial_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stop = threading.Event()
            failures = []
            observations = []

            def reader():
                while not stop.is_set():
                    path = root / "queue/work_items.jsonl"
                    if path.exists():
                        try:
                            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
                            observations.append(len(rows))
                        except (OSError, json.JSONDecodeError) as exc:
                            failures.append(str(exc))

            thread = threading.Thread(target=reader)
            thread.start()
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                    results = list(pool.map(
                        lambda n: run_cli(root, "create", "--title", f"Reader burst {n}"), range(12)
                    ))
            finally:
                stop.set()
                thread.join(5)
            self.assertTrue(all(result.returncode == 0 for result in results), [r.stderr for r in results])
            self.assertEqual([], failures)
            self.assertTrue(observations)
            rows = [json.loads(line) for line in (root / "queue/work_items.jsonl").read_text().splitlines()]
            self.assertEqual(12, len(rows))
            self.assertEqual(12, len({row["id"] for row in rows}))

    def test_second_owner_cannot_enter_critical_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entered = threading.Event()
            release = threading.Event()

            def holder():
                with storage.queue_write_lock(root):
                    entered.set()
                    release.wait(5)

            thread = threading.Thread(target=holder)
            thread.start()
            self.assertTrue(entered.wait(2))
            try:
                with self.assertRaises(storage.QueueStorageError):
                    with storage.queue_write_lock(root, wait_seconds=0):
                        self.fail("second owner entered")
            finally:
                release.set()
                thread.join(5)

    def test_malformed_lock_metadata_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / storage.LOCK_RELATIVE
            lock.mkdir(parents=True)
            (lock / storage.OWNER_FILE).write_text("{}\n", encoding="utf-8")
            with self.assertRaises(storage.QueueStorageError):
                with storage.queue_write_lock(root, wait_seconds=0):
                    pass
            self.assertTrue(lock.exists())

    def test_proven_stale_lock_is_recovered_but_age_alone_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = root / storage.LOCK_RELATIVE
            lock.mkdir(parents=True)
            stale = storage._owner_payload("stale")
            stale["pid"] = 99999999
            stale["process_start_id"] = "definitely-dead"
            stale["acquired_at"] = "2000-01-01T00:00:00Z"
            (lock / storage.OWNER_FILE).write_text(json.dumps(stale), encoding="utf-8")
            with storage.queue_write_lock(root, wait_seconds=0):
                self.assertTrue(lock.exists())
            self.assertFalse(lock.exists())

            lock.mkdir(parents=True)
            live = storage._owner_payload("live-old")
            live["acquired_at"] = "2000-01-01T00:00:00Z"
            (lock / storage.OWNER_FILE).write_text(json.dumps(live), encoding="utf-8")
            with self.assertRaises(storage.QueueStorageError):
                with storage.queue_write_lock(root, wait_seconds=0):
                    pass
            self.assertTrue(lock.exists())

    def test_atomic_replace_failure_preserves_previous_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue/work_items.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text('{"id":"old"}\n', encoding="utf-8")
            with patch.object(storage.os, "replace", side_effect=OSError("injected replace failure")):
                with self.assertRaises(OSError):
                    storage.durable_replace_text(path, '{"id":"new"}\n')
            self.assertEqual('{"id":"old"}\n', path.read_text(encoding="utf-8"))
            self.assertEqual([], list(path.parent.glob(".work_items.jsonl.*.tmp")))

    def test_posix_temp_is_flushed_and_fsynced_before_atomic_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "work_items.jsonl"
            events = []
            real_fdopen = storage.os.fdopen
            real_fsync = storage.os.fsync

            class TrackedFile:
                def __init__(self, handle):
                    self.handle = handle

                def __enter__(self):
                    self.handle.__enter__()
                    return self

                def __exit__(self, *args):
                    return self.handle.__exit__(*args)

                def write(self, value):
                    return self.handle.write(value)

                def flush(self):
                    events.append("flush")
                    return self.handle.flush()

                def fileno(self):
                    return self.handle.fileno()

            def fdopen(*args, **kwargs):
                return TrackedFile(real_fdopen(*args, **kwargs))

            def fsync(fd):
                events.append("fsync")
                return real_fsync(fd)

            real_replace = storage.os.replace

            def replace(source, target):
                events.append("replace")
                self.assertEqual('{"id":"new"}\n', Path(source).read_text(encoding="utf-8"))
                real_replace(source, target)

            with (
                patch.object(storage.os, "fdopen", side_effect=fdopen),
                patch.object(storage.os, "fsync", side_effect=fsync),
                patch.object(storage.os, "replace", side_effect=replace),
                patch.object(storage, "fsync_directory", side_effect=lambda unused: events.append("dir_fsync")),
            ):
                storage.durable_replace_text(path, '{"id":"new"}\n')
            self.assertEqual(["flush", "fsync", "replace", "dir_fsync"], events)
            self.assertEqual('{"id":"new"}\n', path.read_text(encoding="utf-8"))
            self.assertEqual([], list(path.parent.glob(".work_items.jsonl.*.tmp")))

    def test_native_windows_is_rejected_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "work_items.jsonl"
            with (
                patch("tools.aos_paths.os.name", "nt"),
                patch("tools.aos_paths.sys.platform", "win32"),
            ):
                with self.assertRaisesRegex(RuntimeError, "requires Linux/POSIX"):
                    storage.durable_replace_text(path, "new\n")
            self.assertFalse(path.exists())

    def test_windows_mounted_root_is_rejected_before_lock_or_temp_creation(self):
        root = Path("/mnt/c/ttros-authority-rejection-proof")
        self.assertFalse(root.exists())
        with self.assertRaisesRegex(RuntimeError, "Windows-mounted roots"):
            with storage.queue_write_lock(root):
                pass
        self.assertFalse(root.exists())

    def test_retired_windows_mutation_helpers_are_absent(self):
        self.assertFalse(hasattr(storage, "_windows_move_file_ex"))
        self.assertFalse(hasattr(storage, "_windows_write_through_move"))
        self.assertFalse(hasattr(storage, "MOVEFILE_WRITE_THROUGH"))

    def test_posix_replace_still_fsyncs_containing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "work_items.jsonl"
            with patch.object(storage, "fsync_directory") as sync_directory:
                storage.durable_replace_text(path, "new\n")
            sync_directory.assert_called_once_with(path.parent)
            self.assertEqual("new\n", path.read_text(encoding="utf-8"))

    def test_directory_durability_failure_is_surfaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue/work_items.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text('{"id":"old"}\n', encoding="utf-8")
            with patch.object(storage, "fsync_directory", side_effect=OSError("injected directory sync failure")):
                with self.assertRaisesRegex(OSError, "directory sync"):
                    storage.durable_replace_text(path, '{"id":"new"}\n')
            self.assertEqual('{"id":"new"}\n', path.read_text(encoding="utf-8"))

    def test_create_preserves_every_supported_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_cli(
                root, "create", "--title", "All fields", "--requested-by", "liam",
                "--owner-type", "agent", "--owner", "unassigned", "--status", "agent_todo",
                "--priority", "7", "--source", "unit:marker", "--tags", "a,b",
                "--context", "context", "--sources", "one.md,two.md",
                "--allowed-actions", "read,test", "--stop-conditions", "external,destructive",
                "--definition-of-done", "verified", "--parent-id", "AOS-2026-0001",
                "--step-index", "2", "--depends-on", "AOS-2026-0001", "--on-complete", "human_review",
                "--workbench", "codex",
            )
            self.assertEqual(0, result.returncode, result.stderr)
            item = parse_json(result.stdout)
            self.assertEqual(["a", "b"], item["tags"])
            self.assertEqual(["one.md", "two.md"], item["sources"])
            self.assertEqual("AOS-2026-0001", item["parent_id"])
            self.assertEqual(["AOS-2026-0001"], item["depends_on"])
            self.assertEqual("human_review", item["on_complete"])

    def test_workflow_parent_is_never_next_or_claimable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            created = run_cli(
                root, "create", "--title", "Aggregate", "--owner-type", "workflow",
                "--owner", "hermes", "--status", "inbox",
            )
            self.assertEqual(0, created.returncode, created.stderr)
            parent = parse_json(created.stdout)
            for agent in ("hermes", "codex", "claude", "revenue", "marketing", "delivery", "operations"):
                nxt = run_cli(root, "next", agent)
                self.assertEqual({}, parse_json(nxt.stdout), agent)
            claimed = run_cli(root, "claim", parent["id"], "hermes")
            self.assertNotEqual(0, claimed.returncode)
            self.assertIn("workflow aggregate", claimed.stderr)

            invalid = run_cli(root, "create", "--title", "Bad type", "--owner-type", "worker")
            self.assertNotEqual(0, invalid.returncode)
            self.assertIn("Invalid owner_type", invalid.stderr)

    def test_queue_json_files_and_schemas_load(self):
        json.loads((ROOT / "queue" / "agent_registry.json").read_text(encoding="utf-8"))
        json.loads((ROOT / "queue" / "schemas" / "work_item.schema.json").read_text(encoding="utf-8"))
        json.loads((ROOT / "queue" / "schemas" / "receipt.schema.json").read_text(encoding="utf-8"))
        work_items = ROOT / "queue" / "work_items.jsonl"
        if not work_items.exists():
            self.assertIn("*.jsonl", (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())
            return
        for line in work_items.read_text(encoding="utf-8").splitlines():
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

    def test_status_and_receipt_help_show_exact_syntax(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status_help = run_cli(root, "status", "--help")
            receipt_help = run_cli(root, "receipt", "--help")

        self.assertEqual(status_help.returncode, 0, status_help.stderr)
        self.assertIn("ITEM_ID STATUS", status_help.stdout)
        self.assertIn("Approved status value", status_help.stdout)
        self.assertEqual(receipt_help.returncode, 0, receipt_help.stderr)
        self.assertIn("ITEM_ID RECEIPT_PATH", receipt_help.stdout)
        self.assertIn("--status STATUS", receipt_help.stdout)
        self.assertIn("Optional approved status", receipt_help.stdout)

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

    def test_jsonschema_absence_blocks_module_load(self):
        original_import = builtins.__import__
        original_jsonschema = sys.modules.pop("jsonschema", None)

        def blocked_import(name, *args, **kwargs):
            if name == "jsonschema":
                raise ModuleNotFoundError("No module named 'jsonschema'")
            return original_import(name, *args, **kwargs)

        try:
            builtins.__import__ = blocked_import
            with self.assertRaises(ModuleNotFoundError):
                load_tool_module()
        finally:
            builtins.__import__ = original_import
            if original_jsonschema is not None:
                sys.modules["jsonschema"] = original_jsonschema

    def test_receipt_and_rollup_cost_use_model_confirmed_for_orchestrator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            module = load_tool_module()
            rollup = load_rollup_module()
            item = parse_json(run_cli(root, "create", "--title", "Price confirmed model", "--owner", "codex").stdout)
            usage = {
                "orchestrator": {"input": 1_000_000, "output": 0},
                "subagents": [
                    {"role": "codex/oneshot", "model": "claude-haiku-4-5", "input": 1_000_000, "output": 0}
                ],
                "workbenches": [],
                "unavailable": [],
            }

            record = module.finalize_done(
                root,
                item,
                token_usage_json=usage,
                model_confirmed="claude-sonnet-5",
            )
            receipt_usage = json.loads((root / record["token_usage_sidecar"]).read_text(encoding="utf-8"))["token_usage"]
            ledger_line = json.loads((root / "queue" / "token_ledger.jsonl").read_text(encoding="utf-8"))
            prices = rollup.load_prices()
            week = rollup.iso_week_key(ledger_line["timestamp"])
            rolled = rollup.rollup_week(week, [ledger_line], prices)

            self.assertEqual(ledger_line["model_confirmed"], "claude-sonnet-5")
            self.assertEqual(receipt_usage["est_cost_usd"], 3.8)
            self.assertEqual(ledger_line["token_usage"]["est_cost_usd"], 3.8)
            self.assertEqual(rolled["totals"]["est_cost_usd"], 3.8)
            self.assertEqual(rolled["by_model"]["claude-sonnet-5"]["est_cost_usd"], 3.0)

    def test_rollup_exact_invocation_outranks_same_item_placeholders(self):
        rollup = load_rollup_module()
        usage = {
            "orchestrator": {"input": 0, "output": 0}, "subagents": [],
            "workbenches": [{"tool": "codex", "input": 0, "output": 0, "source": "unavailable"}],
            "totals": {"input": 0, "output": 0}, "unavailable": ["Codex token usage"],
        }
        unavailable = {
            "item_id": "AOS-2026-0001", "session_id": "session-proof", "timestamp": "2026-07-12T00:00:00Z",
            "lane": "codex", "profile": "default", "budget_class": "light", "escalated": False,
            "token_usage": usage,
        }
        placeholder = {
            **unavailable, "session_id": None,
            "token_usage": {**usage, "workbenches": [], "unavailable": ["no agent invocation"]},
        }
        exact = {
            **unavailable,
            "token_usage": {
                **usage,
                "workbenches": [{"tool": "codex", "input": 20, "output": 10, "source": "reported"}],
                "totals": {"input": 20, "output": 10},
                "unavailable": ["Codex model identity"],
            },
        }
        rolled = rollup.rollup_week("2026-W28", [unavailable, placeholder, exact], {})
        self.assertEqual(1, rolled["line_count"])
        self.assertEqual({"input": 20, "output": 10, "est_cost_usd": 0.0}, rolled["totals"])
        self.assertNotIn("no agent invocation", rolled["unavailable_components"])


if __name__ == "__main__":
    unittest.main()
