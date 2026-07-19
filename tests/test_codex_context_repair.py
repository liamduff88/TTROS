"""Focused regression proof for fresh Codex sessions and cache accounting.

Revisit: when Codex JSONL, session launch, or correction prompt contracts change. · Last touched: 2026-07-19.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from dashboard.backend import main as backend
from tools import aos_codex_policy as policy


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CodexContextRepairTest(unittest.TestCase):
    def _fake_codex(self, root: Path, *, with_session: bool = True, large_output: bool = False) -> Path:
        executable = root / "codex-fixture"
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, sys\n"
            "root = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
            "prompt = sys.stdin.read()\n"
            "if '--ephemeral' not in sys.argv or 'resume' in sys.argv or '--last' in sys.argv:\n"
            "    raise SystemExit(9)\n"
            "counter = root / 'fixture-counter.txt'\n"
            "number = int(counter.read_text() if counter.exists() else '0') + 1\n"
            "counter.write_text(str(number), encoding='utf-8')\n"
            "(root / f'prompt-{number}.txt').write_text(prompt, encoding='utf-8')\n"
            + ("print(json.dumps({'type':'thread.started','thread_id':f'fresh-{number}'}), flush=True)\n" if with_session else "")
            + ("print(json.dumps({'type':'item.completed','item':{'type':'command_execution','aggregated_output':'LARGE_OUTPUT_SENTINEL_' + ('x' * 30000)}}), flush=True)\n" if large_output else "")
            + "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'PASS\\nFiles touched: None\\nValidation: fixture\\nBlockers: None'}}), flush=True)\n"
            "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'cached_input_tokens':2,'output_tokens':3,'reasoning_output_tokens':1}}), flush=True)\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
        return executable

    def _fake_threshold_codex(self, root: Path) -> Path:
        executable = root / "codex-threshold-fixture"
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, sys, time\n"
            "root = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
            "prompt = sys.stdin.read()\n"
            "if '--ephemeral' not in sys.argv or 'resume' in sys.argv or '--last' in sys.argv:\n"
            "    raise SystemExit(9)\n"
            "counter = root / 'threshold-counter.txt'\n"
            "number = int(counter.read_text() if counter.exists() else '0') + 1\n"
            "counter.write_text(str(number), encoding='utf-8')\n"
            "(root / f'threshold-prompt-{number}.txt').write_text(prompt, encoding='utf-8')\n"
            "print(json.dumps({'type':'thread.started','thread_id':f'threshold-fresh-{number}'}), flush=True)\n"
            "if number == 1:\n"
            "    print(json.dumps({'type':'turn.completed','usage':{'input_tokens':30,'cached_input_tokens':10,'output_tokens':5,'reasoning_output_tokens':2}}), flush=True)\n"
            "    print(json.dumps({'type':'item.completed','item':{'type':'command_execution','aggregated_output':'LARGE_THRESHOLD_LOG_SENTINEL_' + ('z' * 12000)}}), flush=True)\n"
            "    print(json.dumps({'type':'turn.completed','usage':{'input_tokens':55,'cached_input_tokens':20,'output_tokens':5,'reasoning_output_tokens':2}}), flush=True)\n"
            "    time.sleep(10)\n"
            "else:\n"
            "    print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'PASS\\nFiles touched: None\\nValidation: fresh continuation\\nBlockers: None'}}), flush=True)\n"
            "    print(json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'cached_input_tokens':2,'output_tokens':3,'reasoning_output_tokens':1}}), flush=True)\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
        return executable

    def _fake_queue_threshold_codex(self, root: Path) -> Path:
        executable = root / "codex-queue-threshold-fixture"
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, sys\n"
            "if '--version' in sys.argv:\n"
            "    print('codex-cli threshold-fixture')\n"
            "    raise SystemExit(0)\n"
            "root = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
            "prompt = sys.stdin.read()\n"
            "if '--ephemeral' not in sys.argv or 'resume' in sys.argv or '--last' in sys.argv:\n"
            "    raise SystemExit(9)\n"
            "counter = root / 'queue-threshold-counter.txt'\n"
            "number = int(counter.read_text() if counter.exists() else '0') + 1\n"
            "counter.write_text(str(number), encoding='utf-8')\n"
            "(root / f'queue-threshold-prompt-{number}.txt').write_text(prompt, encoding='utf-8')\n"
            "print(json.dumps({'type':'thread.started','thread_id':f'queue-threshold-fresh-{number}'}))\n"
            "usage = {'input_tokens':55,'cached_input_tokens':20,'output_tokens':5,'reasoning_output_tokens':2} if number == 1 else {'input_tokens':12,'cached_input_tokens':2,'output_tokens':3,'reasoning_output_tokens':1}\n"
            "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'PASS'}}))\n"
            "print(json.dumps({'type':'turn.completed','usage':usage}))\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
        return executable

    def test_unrelated_direct_tasks_are_fresh_and_sentinel_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executable = self._fake_codex(root)
            target = replace(policy.CODEX_TARGET, root=root, executable=executable, codex_home=root / ".codex")
            with patch.object(backend, "BASE_DIR", root), patch.object(backend, "CODEX_TARGET", target):
                first = backend._run_codex_local("DIRECT_ALPHA_SENTINEL")
                second = backend._run_codex_local("DIRECT_BETA_SENTINEL")

            first_prompt = (root / "prompt-1.txt").read_text(encoding="utf-8")
            second_prompt = (root / "prompt-2.txt").read_text(encoding="utf-8")
            self.assertEqual((first["session_id"], second["session_id"]), ("fresh-1", "fresh-2"))
            self.assertNotEqual(first["session_id"], second["session_id"])
            self.assertIn("DIRECT_ALPHA_SENTINEL", first_prompt)
            self.assertNotIn("DIRECT_BETA_SENTINEL", first_prompt)
            self.assertIn("DIRECT_BETA_SENTINEL", second_prompt)
            self.assertNotIn("DIRECT_ALPHA_SENTINEL", second_prompt)
            self.assertIn("PERMISSION MODE — SCOPED LOCAL TASK APPROVED", first_prompt)
            self.assertEqual(first["token_usage"]["fresh_input"], 10)
            self.assertEqual(
                first["token_usage"]["context_pct_at_close"],
                "unavailable from current CLI output",
            )

    def test_missing_clean_session_fails_without_synthetic_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executable = self._fake_codex(root, with_session=False)
            target = replace(policy.CODEX_TARGET, root=root, executable=executable, codex_home=root / ".codex")
            with patch.object(backend, "BASE_DIR", root), patch.object(backend, "CODEX_TARGET", target):
                result = backend._run_codex_local("CLEAN_SESSION_FAILURE_SENTINEL")
            self.assertFalse(result["success"])
            self.assertEqual(result["failure_class"], "clean_session_creation_failure")
            self.assertIn("refusing previous-session inheritance", result["output"])
            self.assertNotIn("session_id", result["token_usage"])

    def test_cumulative_threshold_writes_handoff_and_continues_in_new_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            executable = self._fake_threshold_codex(root)
            target = replace(policy.CODEX_TARGET, root=root, executable=executable, codex_home=root / ".codex")
            with patch.object(backend, "BASE_DIR", root), \
                 patch.object(backend, "CODEX_TARGET", target), \
                 patch.object(backend, "CONTEXT_HANDOFF_THRESHOLD_TOKENS", 50), \
                 patch.object(backend, "MAX_CONTEXT_HANDOFFS", 2):
                result = backend._run_codex_local("THRESHOLD_ORIGINAL_TASK_SENTINEL")
                with patch.object(backend, "_log_token_usage") as token_log:
                    backend._compact_agent_closeout(result, "codex", "codex", "threshold fixture")

            self.assertTrue(result["success"])
            self.assertEqual(result["session_id"], "threshold-fresh-2")
            self.assertEqual([row["session_id"] for row in result["handoff_sessions"]], ["threshold-fresh-1"])
            self.assertEqual(result["handoff_sessions"][0]["threshold_usage"]["cumulative_tokens"], 60)
            self.assertEqual(result["handoff_sessions"][0]["threshold_usage"]["event_count"], 2)
            self.assertEqual(token_log.call_count, 2)
            self.assertEqual(
                [call.args[3].get("session_id") for call in token_log.call_args_list],
                ["threshold-fresh-1", "threshold-fresh-2"],
            )

            first_prompt = (root / "threshold-prompt-1.txt").read_text(encoding="utf-8")
            second_prompt = (root / "threshold-prompt-2.txt").read_text(encoding="utf-8")
            handoff_path = root / result["handoff_artifacts"][0]
            handoff = handoff_path.read_text(encoding="utf-8")
            self.assertIn("THRESHOLD_ORIGINAL_TASK_SENTINEL", first_prompt)
            self.assertIn("THRESHOLD_ORIGINAL_TASK_SENTINEL", handoff)
            self.assertNotIn("THRESHOLD_ORIGINAL_TASK_SENTINEL", second_prompt)
            self.assertIn(result["handoff_artifacts"][0], second_prompt)
            self.assertNotIn("LARGE_THRESHOLD_LOG_SENTINEL_", second_prompt)
            self.assertIn("LARGE_THRESHOLD_LOG_SENTINEL_", (root / result["handoff_sessions"][0]["stream_artifacts"][0]).read_text(encoding="utf-8"))
            self.assertNotIn("resume", " ".join(result["invocation"].get("command", [])))
            self.assertNotIn("model_auto_compact", first_prompt + second_prompt)

    def test_queue_cli_threshold_reconciles_each_fresh_session(self):
        queue = load_module("aos_queue_threshold_context_repair", ROOT / "tools" / "aos-queue.py")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue" / "receipts").mkdir(parents=True)
            shutil.copy(ROOT / "queue" / "token_ledger_schema.json", root / "queue" / "token_ledger_schema.json")
            item_id = "AOS-2026-9007"
            receipt_path = f"queue/receipts/{item_id}.md"
            (root / receipt_path).write_text("PASS\n\nToken usage: unavailable from current CLI output.\n", encoding="utf-8")
            item = {
                "id": item_id, "title": "Queue threshold fixture", "owner": "codex",
                "status": "human_review", "tags": ["standard"],
                "receipts": [{"path": receipt_path, "status": "human_review"}],
            }
            (root / "queue" / "work_items.jsonl").write_text(json.dumps(item) + "\n", encoding="utf-8")
            executable = self._fake_queue_threshold_codex(root)
            target = replace(policy.CODEX_TARGET, root=root, executable=executable, codex_home=root / ".codex")
            with patch.object(queue, "CODEX_TARGET", target), \
                 patch.object(queue, "CONTEXT_HANDOFF_THRESHOLD_TOKENS", 50), \
                 patch.object(queue, "MAX_CONTEXT_HANDOFFS", 2):
                result = queue.run_codex_work_item(root, item_id, "QUEUE_THRESHOLD_ORIGINAL_SENTINEL")

            ledger = [json.loads(line) for line in (root / "queue" / "token_ledger.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["session_id"] for row in ledger], ["queue-threshold-fresh-1", "queue-threshold-fresh-2"])
            self.assertEqual(result["session_id"], "queue-threshold-fresh-2")
            self.assertEqual(result["handoff_sessions"][0]["session_id"], "queue-threshold-fresh-1")
            second_prompt = (root / "queue-threshold-prompt-2.txt").read_text(encoding="utf-8")
            self.assertNotIn("QUEUE_THRESHOLD_ORIGINAL_SENTINEL", second_prompt)
            self.assertIn(result["handoff_artifacts"][0], second_prompt)

    def test_correction_is_fresh_compact_and_large_output_is_artifact_backed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue" / "templates").mkdir(parents=True)
            (root / "queue" / "templates" / "codex_task.prompt.md").write_text(
                (ROOT / "queue" / "templates" / "codex_task.prompt.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            executable = self._fake_codex(root, large_output=True)
            target = replace(policy.CODEX_TARGET, root=root, executable=executable, codex_home=root / ".codex")
            item = {
                "id": "AOS-2026-9001", "title": "Hermes child correction", "owner": "codex",
                "context": "Original bounded context", "sources": ["tools/aos_codex_policy.py"],
                "source_refs": ["queue/receipts/prior.md"],
                "allowed_actions": ["local_read", "local_edit", "local_test"],
                "stop_conditions": ["external_action"], "definition_of_done": "Acceptance sentinel satisfied",
            }
            with patch.object(backend, "BASE_DIR", root), patch.object(backend, "CODEX_TARGET", target):
                prior = backend._run_codex_local("LARGE_SYNTHETIC_TASK", item)
                prompt = backend._queue_actual_run_prompt(
                    item, "codex", "Fix the validation receipt", 2, 3, prior,
                )
            raw_path = root / prior["stream_artifacts"][0]
            self.assertTrue(prior["retained_output_truncated"])
            self.assertIn("LARGE_OUTPUT_SENTINEL_", raw_path.read_text(encoding="utf-8"))
            self.assertNotIn("LARGE_OUTPUT_SENTINEL_", prior["stdout"])
            self.assertIn("Fresh compact correction work order", prompt)
            self.assertIn(prior["stream_artifacts"][0], prompt)
            self.assertIn("Fix the validation receipt", prompt)
            self.assertIn("Acceptance sentinel satisfied", prompt)
            self.assertNotIn("LARGE_OUTPUT_SENTINEL_", prompt)
            self.assertLess(len(prompt.encode("utf-8")), policy.MAX_FRESH_PROMPT_BYTES)

    def test_large_child_evidence_is_artifact_backed_not_reinjected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue" / "templates").mkdir(parents=True)
            shutil.copy(ROOT / "queue" / "templates" / "codex_task.prompt.md", root / "queue" / "templates" / "codex_task.prompt.md")
            large_context = "\n".join((
                "LARGE_DIFF_SENTINEL diff --git a/a b/b",
                "LARGE_TEST_OUTPUT_SENTINEL 999 failed",
                "LARGE_SCREENSHOT_SENTINEL data:image/png;base64," + ("A" * 2_000),
                "LARGE_BROWSER_EVIDENCE_SENTINEL " + ("B" * 3_000),
            ))
            reply = json.dumps({
                "title": "Artifact-backed child fixture",
                "tasks": [{
                    "title": "Inspect bounded evidence",
                    "context": large_context,
                    "definition_of_done": "Return a compact receipt",
                }],
            })
            with patch.object(backend, "BASE_DIR", root):
                plan = backend._normalize_hermes_orchestration_plan(reply, "original task")
                self.assertIsNotNone(plan)
                child_context = plan["children"][0]["context"]
                item = {
                    "id": "AOS-2026-9004", "title": "Artifact-backed child fixture",
                    "owner": "codex", "context": child_context, "sources": [],
                    "allowed_actions": ["local_read"], "stop_conditions": ["external_action"],
                    "definition_of_done": "Return a compact receipt",
                }
                child_prompt = backend._queue_actual_run_prompt(item, "codex")

            artifact_match = next(
                value for value in child_context.split("`") if value.startswith("logs/codex_prompt_evidence/")
            )
            artifact = (root / artifact_match).read_text(encoding="utf-8")
            for sentinel in (
                "LARGE_DIFF_SENTINEL", "LARGE_TEST_OUTPUT_SENTINEL",
                "LARGE_SCREENSHOT_SENTINEL", "LARGE_BROWSER_EVIDENCE_SENTINEL",
            ):
                self.assertIn(sentinel, artifact)
                self.assertNotIn(sentinel, child_context)
                self.assertNotIn(sentinel, child_prompt)
            self.assertIn(artifact_match, child_prompt)

    def test_cumulative_jsonl_terminal_snapshot_is_not_summed_or_backfilled(self):
        queue = load_module("aos_queue_cumulative_context_repair", ROOT / "tools" / "aos-queue.py")
        output = "\n".join((
            json.dumps({"type": "thread.started", "thread_id": "usage-fixture"}),
            json.dumps({"type": "turn.completed", "usage": {
                "input_tokens": 100, "cached_input_tokens": 40,
                "output_tokens": 20, "reasoning_output_tokens": 5,
            }}),
            "{malformed-json",
            json.dumps({"type": "turn.completed", "usage": {
                "input_tokens": 150, "cached_input_tokens": 60,
                "output_tokens": 30, "reasoning_output_tokens": 7,
            }}),
        ))
        summary = queue.parse_codex_token_summary(output)
        self.assertEqual((summary["input"], summary["cached"], summary["output"], summary["reasoning"]), (150, 60, 30, 7))
        self.assertEqual(summary["total"], 180)
        self.assertEqual(summary["normalized_usage"]["fresh_input"], 90)
        self.assertEqual(summary["usage_counters"]["input_plus_output"], 180)
        backend_summary = backend._codex_json_summary(output)[1]
        self.assertEqual((backend_summary["input_tokens"], backend_summary["cached_input_tokens"], backend_summary["output_tokens"]), (150, 60, 30))

        malformed_terminal = output + "\n" + json.dumps({"type": "turn.completed", "usage": {"output_tokens": 31}})
        with self.assertRaisesRegex(queue.QueueError, "terminal turn.completed usage lacks input/output"):
            queue.parse_codex_token_summary(malformed_terminal)
        malformed_backend = backend._codex_json_summary(malformed_terminal)[1]
        self.assertFalse(malformed_backend["available"])
        self.assertEqual(malformed_backend["total_input"], "unavailable from current CLI output")
        with self.assertRaisesRegex(queue.QueueError, "without a parseable final token summary"):
            queue.parse_codex_token_summary('{"type":"thread.started","thread_id":"missing-usage"}')
        with self.assertRaisesRegex(queue.QueueError, "cached input cannot exceed"):
            queue.normalize_codex_usage(10, 11, 1, 0)
        with self.assertRaisesRegex(queue.QueueError, "reasoning output"):
            queue.normalize_codex_usage(10, 1, 2, 3)

    def test_cache_normalization_warnings_rollup_and_pricing_do_not_double_count(self):
        queue = load_module("aos_queue_context_repair", ROOT / "tools" / "aos-queue.py")
        rollup = load_module("token_rollup_context_repair", ROOT / "scripts" / "token_rollup.py")
        normalized = queue.normalize_codex_usage(1_000, 900, 100, 20)
        self.assertEqual(normalized["fresh_input"], 100)
        self.assertEqual(normalized["cache_ratio"], 9.0)
        prices = {"fixture-model": {"input_per_mtok": 2.0, "cache_read_per_mtok": 0.5, "output_per_mtok": 10.0}}
        expected_cost = 0.00165
        self.assertEqual(
            queue.cost_for("fixture-model", 1_000, 100, prices, fresh_input=100, cached_input=900),
            expected_cost,
        )
        usage = {
            "orchestrator": {"input": 0, "output": 0}, "subagents": [],
            "workbenches": [{
                "tool": "codex", "session_id": "cache-proof", "model": "fixture-model",
                **normalized, "context_pct_at_close": 51, "source": "reported",
            }],
            "totals": {"input": 1_000, "output": 100}, "est_cost_usd": 99,
            "unavailable": [],
        }
        with patch.object(queue, "load_prices", return_value=prices):
            priced, _ = queue.build_token_usage(
                {"profile_requested": "fixture"}, usage_file=None, token_usage_json=usage,
            )
        self.assertEqual(priced["totals"], {"input": 1_000, "output": 100})
        self.assertEqual(priced["est_cost_usd"], expected_cost)
        line = {
            "item_id": "AOS-2026-9002", "session_id": "cache-proof", "lane": "codex",
            "profile": "default", "timestamp": "2026-07-19T00:00:00Z", "escalated": False,
            "model_requested": "fixture-model", "model_confirmed": "fixture-model",
            "budget_class": "light", "token_usage": usage,
        }
        rolled = rollup.rollup_week("2026-W29", [line], prices)
        self.assertEqual(rolled["totals"]["input"], 1_000)
        self.assertEqual(rolled["totals"]["est_cost_usd"], expected_cost)
        self.assertEqual(rolled["top_cache_ratio_sessions"][0]["cache_ratio"], 9.0)
        self.assertEqual(rolled["context_ceiling_breaches"][0]["context_pct_at_close"], 51)
        self.assertTrue(any("context_pct_at_close > 50" in value for value in rolled["warnings"]))
        warnings = queue.token_usage_warnings({
            **usage,
            "workbenches": [{**usage["workbenches"][0], "fresh_input": 1, "cached_input": 999}],
        })
        self.assertTrue(any("cache_ratio > 20" in value for value in warnings))
        self.assertTrue(any("context_pct_at_close > 50" in value for value in warnings))
        cache_warning_usage = {
            "orchestrator": {"input": 0, "output": 0}, "subagents": [],
            "workbenches": [{
                "tool": "codex", "session_id": "cache-warning-proof", "model": "fixture-model",
                **queue.normalize_codex_usage(1_000, 999, 10, 2),
                "context_pct_at_close": 49, "source": "reported",
            }],
            "totals": {"input": 1_000, "output": 10}, "est_cost_usd": 0, "unavailable": [],
        }
        warning_line = {**line, "item_id": "AOS-2026-9006", "session_id": "cache-warning-proof", "token_usage": cache_warning_usage}
        warning_rollup = rollup.rollup_week("2026-W29", [line, warning_line], prices)
        self.assertEqual(
            [row["session_id"] for row in warning_rollup["top_cache_ratio_sessions"][:2]],
            ["cache-warning-proof", "cache-proof"],
        )
        self.assertTrue(any("cache_ratio > 20" in value for value in warning_rollup["warnings"]))
        self.assertTrue(any("context_pct_at_close > 50" in value for value in warning_rollup["warnings"]))
        direct_line = backend._simple_token_line(
            "AOS-2026-9003", "codex", 1_100, "exact",
            {
                "session_id": "direct-ledger-proof", "total_input": 1_000,
                "fresh_input": 100, "cached_input": 900, "output": 100,
                "reasoning": 20, "context_pct_at_close": "unavailable from current CLI output",
            },
        )
        direct_workbench = direct_line["token_usage"]["workbenches"][0]
        self.assertEqual(direct_workbench["input"], 1_000)
        self.assertEqual(direct_workbench["fresh_input"], 100)
        self.assertEqual(direct_workbench["cached_input"], 900)
        self.assertEqual(direct_line["token_usage"]["totals"]["input"], 1_000)
        dashboard_group = next(
            row for row in backend._token_source_summary([direct_line]) if row["source"] == "Codex"
        )
        self.assertEqual(dashboard_group["input"], 1_000)
        self.assertEqual(dashboard_group["cached_input"], 900)
        self.assertEqual(dashboard_group["output"], 100)
        self.assertEqual(dashboard_group["reasoning_output"], 20)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "queue" / "receipts").mkdir(parents=True)
            shutil.copy(ROOT / "queue" / "token_ledger_schema.json", root / "queue" / "token_ledger_schema.json")
            item_id = "AOS-2026-9005"
            receipt_path = f"queue/receipts/{item_id}.md"
            (root / receipt_path).write_text("PASS\n\nToken usage: unavailable from current CLI output.\n", encoding="utf-8")
            item = {
                "id": item_id, "title": "Cache receipt fixture", "owner": "codex",
                "status": "human_review", "tags": ["standard"],
                "receipts": [{"path": receipt_path, "status": "human_review"}],
            }
            (root / "queue" / "work_items.jsonl").write_text(json.dumps(item) + "\n", encoding="utf-8")
            summary = queue.parse_codex_token_summary(json.dumps({
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 1_000, "cached_input_tokens": 900,
                    "output_tokens": 100, "reasoning_output_tokens": 20,
                },
            }))
            queue.reconcile_codex_usage(root, item_id, summary, "fixture-cli", "receipt-cache-session")
            ledger = json.loads((root / "queue" / "token_ledger.jsonl").read_text(encoding="utf-8"))
            sidecar = json.loads((root / "queue" / "receipts" / f"{item_id}.token_usage.json").read_text(encoding="utf-8"))
            receipt = (root / receipt_path).read_text(encoding="utf-8")
            for materialized in (ledger["token_usage"], sidecar["token_usage"]):
                workbench = materialized["workbenches"][0]
                self.assertEqual(materialized["totals"], {"input": 1_000, "output": 100})
                self.assertEqual((workbench["input"], workbench["fresh_input"], workbench["cached_input"]), (1_000, 100, 900))
                self.assertEqual((workbench["output"], workbench["reasoning"]), (100, 20))
            self.assertIn('"input": 1000', receipt)
            self.assertIn('"fresh_input": 100', receipt)
            self.assertIn('"cached_input": 900', receipt)
            self.assertNotIn('"fresh_input": 1000', receipt)


if __name__ == "__main__":
    unittest.main()
