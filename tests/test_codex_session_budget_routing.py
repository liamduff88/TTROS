"""Per-session Codex fuse, streaming stop, model routing and work-order prompts.

Revisit: when the Codex fuse scope, ``codex exec --json`` usage events, the
codex_selection tiers, or the technical-worker prompt shape change. · Last touched: 2026-10-25.
"""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from dashboard.backend import main as backend
from tools import aos_codex_policy as policy
from tools import context_assembler
from tools import step6_cost_control as step6


ROOT = Path(__file__).resolve().parents[1]
ITEM = "AOS-2026-9101"


def _fixture_root(tmp: str) -> Path:
    root = Path(tmp)
    (root / "queue").mkdir(parents=True, exist_ok=True)
    (root / "queue" / "notifications.json").write_text(
        json.dumps({"operator_controls": {"cost_dial": "standard"}}), encoding="utf-8",
    )
    return root


def _usage(total: int) -> dict:
    return {"input_tokens": total - 10, "output_tokens": 10, "cache_semantics": "included_in_provider_input"}


def _record_session(root: Path, invocation: str, total: int, item: str = ITEM) -> dict:
    return step6.record_invocation(
        step6.codex_session_scope(invocation), invocation_id=invocation, provider="openai-codex",
        model="gpt-6-sol", usage=_usage(total), root=root, surface="test:codex", work_item_id=item,
    )


class SessionFuseScopeTest(unittest.TestCase):
    def test_each_new_session_starts_at_zero_despite_parent_item_spend(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture_root(tmp)
            # Legacy shape: 600K already charged to the work-item scope.
            step6.record_invocation(
                step6.Scope("work_item", ITEM), invocation_id="legacy-1", provider="openai-codex",
                model="gpt-6-sol", usage=_usage(600_000), root=root, surface="test:codex",
            )
            self.assertTrue(step6.fuse_status(step6.Scope("work_item", ITEM), root=root)["paused"])
            scope, status = step6.codex_session_preflight("codex-new-1", work_item_id=ITEM, root=root)
            self.assertEqual("session:codex-new-1", scope.key)
            self.assertEqual(0, status["canonical_tokens"])
            self.assertFalse(status["paused"])
            self.assertEqual(600_000, status["work_item_aggregate"]["known_tokens"])

    def test_step_budgets_are_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture_root(tmp)
            first = _record_session(root, "codex-step-1", 500_000)
            self.assertTrue(first["status"]["paused"])
            with self.assertRaises(step6.FusePausedError):
                step6.codex_session_preflight("codex-step-1", work_item_id=ITEM, root=root)
            _scope, status = step6.codex_session_preflight("codex-step-2", work_item_id=ITEM, root=root)
            self.assertFalse(status["paused"])
            second = _record_session(root, "codex-step-2", 120_000)
            self.assertEqual(120_000, second["status"]["canonical_tokens"])
            self.assertEqual(ITEM, second["row"]["parent_work_item_id"])
            self.assertEqual("codex-step-2", second["row"]["session_id"])

    def test_historical_rows_aggregate_without_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture_root(tmp)
            step6.record_invocation(
                step6.Scope("work_item", ITEM), invocation_id="legacy-1", provider="openai-codex",
                model="gpt-6-sol", usage=_usage(1_415_907), root=root, surface="test:codex",
            )
            ledger = root / "queue" / "token_ledger.jsonl"
            legacy_bytes = ledger.read_bytes()
            _record_session(root, "codex-a", 30_000)
            _record_session(root, "codex-b", 40_000)
            _record_session(root, "codex-other", 99_999, item="AOS-2026-9102")
            self.assertTrue(ledger.read_bytes().startswith(legacy_bytes), "historical ledger bytes were rewritten")
            aggregate = step6.work_item_usage(ITEM, root=root)
            self.assertEqual(1_415_907 + 30_000 + 40_000, aggregate["known_tokens"])
            self.assertEqual(3, aggregate["invocation_count"])
            self.assertEqual([], aggregate["accounting_unknown_since_reset"])

    def test_unknown_usage_fails_closed_for_the_item_until_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture_root(tmp)
            step6.record_unavailable_invocation(
                step6.codex_session_scope("codex-lost"), invocation_id="codex-lost", provider="openai-codex",
                model="gpt-6-sol", reason="fixture: no terminal usage", root=root, surface="test:codex",
                work_item_id=ITEM,
            )
            with self.assertRaisesRegex(step6.FusePausedError, "codex-lost: canonical usage unavailable"):
                step6.codex_session_preflight("codex-next", work_item_id=ITEM, root=root)
            # A different item is unaffected; the unknown is never treated as zero.
            step6.codex_session_preflight("codex-elsewhere", work_item_id="AOS-2026-9102", root=root)
            self.assertEqual(1, step6.work_item_usage(ITEM, root=root)["unknown_invocations"])
            step6.reset_scope(step6.Scope("work_item", ITEM), reason="fixture accounting repaired", root=root)
            step6.codex_session_preflight("codex-next", work_item_id=ITEM, root=root)
            self.assertEqual(1, step6.work_item_usage(ITEM, root=root)["unknown_invocations"])


    def test_fuse_stopped_session_does_not_block_a_fresh_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture_root(tmp)
            step6.record_unavailable_invocation(
                step6.codex_session_scope("codex-stopped"), invocation_id="codex-stopped", provider="openai-codex",
                model="gpt-6-sol", reason="stopped at session fuse (fixture); Codex emitted no terminal usage",
                root=root, surface="test:codex", work_item_id=ITEM, stop_cause="session_fuse",
            )
            # Row shape written for AOS-2026-0947 before stop_cause existed (reason prefix only).
            step6.record_unavailable_invocation(
                step6.codex_session_scope("codex-454889f5823f454ebc8400e17219c2de"),
                invocation_id="codex-454889f5823f454ebc8400e17219c2de", provider="openai-codex", model="gpt-6-sol",
                reason="stopped at session fuse (in_flight_lower_bound_estimate 515610/500000); Codex emitted no terminal usage",
                root=root, surface="test:codex", work_item_id=ITEM,
            )
            aggregate = step6.work_item_usage(ITEM, root=root)
            self.assertEqual([], aggregate["accounting_unknown_since_reset"])
            self.assertEqual(2, aggregate["unknown_invocations"])
            self.assertEqual(0, aggregate["known_tokens"])
            self.assertEqual(2, len(aggregate["fuse_stopped_sessions"]))
            _scope, status = step6.codex_session_preflight("codex-fresh", work_item_id=ITEM, root=root)
            self.assertFalse(status["paused"])
            self.assertEqual(0, status["canonical_tokens"])
            # A stopped session's own scope still fails closed; only the sibling is freed.
            with self.assertRaises(step6.FusePausedError):
                step6.codex_session_preflight("codex-stopped", work_item_id=ITEM, root=root)
            # Any other unknown accounting in the item still blocks the next session.
            step6.record_unavailable_invocation(
                step6.codex_session_scope("codex-lost"), invocation_id="codex-lost", provider="openai-codex",
                model="gpt-6-sol", reason="Codex terminal usage unavailable", root=root, surface="test:codex",
                work_item_id=ITEM,
            )
            with self.assertRaisesRegex(step6.FusePausedError, "codex-lost: canonical usage unavailable"):
                step6.codex_session_preflight("codex-fresh-2", work_item_id=ITEM, root=root)


class TornLedgerReadTest(unittest.TestCase):
    def test_in_flight_final_line_is_retried_and_permanent_tear_is_corrupt(self):
        import threading

        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture_root(tmp)
            ledger = root / "queue" / "token_ledger.jsonl"
            whole = json.dumps({"event": "x", "n": 1})
            ledger.write_text(whole + "\n" + whole[:7], encoding="utf-8")
            finisher = threading.Timer(0.05, lambda: ledger.write_text(whole + "\n" + whole + "\n", encoding="utf-8"))
            finisher.start()
            try:
                self.assertEqual(2, len(step6._ledger_rows(root)))
            finally:
                finisher.join()
            ledger.write_text(whole + "\n" + whole[:7], encoding="utf-8")
            with self.assertRaisesRegex(step6.CostControlError, "corrupt token ledger line 2"):
                step6._ledger_rows(root)


def _events(*events: dict) -> str:
    return "".join(json.dumps(event) + "\n" for event in events)


class StreamingFuseTest(unittest.TestCase):
    def test_exact_turn_usage_at_limit_refuses_the_next_turn(self):
        fuse = policy.StreamingSessionFuse("prompt")
        self.assertIsNone(fuse.feed(_events({"type": "turn.completed", "usage": {"input_tokens": 400_000, "output_tokens": 1}})))
        self.assertIsNone(fuse.feed(_events({"type": "turn.started"})))
        # The turn that reaches the limit has completed; it is kept, not stopped.
        self.assertIsNone(fuse.feed(_events({"type": "turn.completed", "usage": {"input_tokens": 499_990, "output_tokens": 10}})))
        self.assertTrue(fuse.summary()["limit_reached_at_turn_end"])
        breach = fuse.feed(_events({"type": "turn.started"}))
        self.assertEqual({"basis": policy.EXACT_BASIS, "tokens": 500_000, "limit": 500_000}, breach)

    def test_single_turn_that_ends_over_the_limit_is_recorded_not_stopped(self):
        fuse = policy.StreamingSessionFuse("prompt")
        self.assertIsNone(fuse.feed(_events(
            {"type": "turn.started"},
            {"type": "turn.completed", "usage": {"input_tokens": 599_000, "output_tokens": 1_000}},
        )))
        self.assertIsNone(fuse.breach)
        self.assertEqual(600_000, fuse.exact_cumulative)
        self.assertTrue(fuse.summary()["limit_reached_at_turn_end"])

    def test_small_session_never_breaches_and_split_lines_are_buffered(self):
        fuse = policy.StreamingSessionFuse("x" * 4_000)
        stream = _events(
            {"type": "thread.started", "thread_id": "t"}, {"type": "turn.started"},
            {"type": "item.started", "item": {"type": "command_execution"}},
            {"type": "item.completed", "item": {"type": "command_execution", "command": "ls", "aggregated_output": "a" * 8_000}},
            {"type": "turn.completed", "usage": {"input_tokens": 30_000, "output_tokens": 500}},
        )
        for start in range(0, len(stream), 7):  # arbitrary chunk boundaries
            self.assertIsNone(fuse.feed(stream[start:start + 7]))
        self.assertEqual(30_500, fuse.exact_cumulative)
        self.assertEqual(1, fuse.requests_estimated)

    def test_unverified_estimate_never_stops_a_long_single_turn(self):
        fuse = policy.StreamingSessionFuse("p" * 40_000)
        for _ in range(200):
            self.assertIsNone(fuse.feed(_events(
                {"type": "item.started", "item": {"type": "command_execution"}},
                {"type": "item.completed", "item": {"type": "command_execution", "command": "cat f", "aggregated_output": "o" * 40_000}},
            )))
        self.assertGreater(fuse.in_flight_estimate, 8 * fuse.limit)
        self.assertIsNone(fuse.exact_cumulative)
        self.assertIsNone(fuse.summary()["stopped"])

    def test_real_aos_0943_stream_runs_to_its_exact_usage(self):
        stream_path = ROOT / "logs" / "codex_sessions" / "codex-338d6e72e2d441349c26c9a1538e38ce.stdout.jsonl"
        if not stream_path.exists():
            self.skipTest("AOS-2026-0943 stream artifact not present")
        fuse = policy.StreamingSessionFuse("x" * 32_818)
        for line in stream_path.read_text(encoding="utf-8").splitlines(keepends=True):
            self.assertIsNone(fuse.feed(line))
        self.assertEqual(1_415_907, fuse.exact_cumulative)
        self.assertTrue(fuse.summary()["limit_reached_at_turn_end"])

    def test_real_aos_9954_stream_is_not_stopped_by_the_estimate(self):
        """AOS-2026-9954 was stopped after 111s at an unverified 507,720 estimate (40 tool calls)."""
        stream_path = ROOT / "logs" / "codex_sessions" / "codex-787ca932c741441e88c8a95d8214adec.stdout.jsonl"
        if not stream_path.exists():
            self.skipTest("AOS-2026-9954 stream artifact not present")
        fuse = policy.StreamingSessionFuse("x" * 2_774)  # 2,776 prompt bytes; the header em dash is 3 bytes, 1 char
        for line in stream_path.read_text(encoding="utf-8").splitlines(keepends=True):
            self.assertIsNone(fuse.feed(line))
        self.assertEqual(40, fuse.requests_estimated)
        self.assertEqual(507_720, fuse.in_flight_estimate)  # the figure the old fuse stopped on
        self.assertIsNone(fuse.exact_cumulative)

    def test_real_aos_0947_stream_is_not_stopped_by_the_estimate(self):
        """AOS-2026-0947 was stopped after 35s at a 515,610 'lower-bound' estimate (21 tool calls)."""
        stream_path = ROOT / "logs" / "codex_sessions" / "codex-454889f5823f454ebc8400e17219c2de.stdout.jsonl"
        if not stream_path.exists():
            self.skipTest("AOS-2026-0947 stream artifact not present")
        fuse = policy.StreamingSessionFuse("x" * 5_810)  # route log initial_prompt_bytes
        for line in stream_path.read_text(encoding="utf-8").splitlines(keepends=True):
            self.assertIsNone(fuse.feed(line))
        self.assertEqual(17, fuse.requests_estimated)  # 21 tool starts, 2 messages, in 17 responses
        self.assertEqual(17 * (5_810 // 4 + policy.REQUEST_OVERHEAD_FLOOR_TOKENS), fuse.in_flight_estimate)
        self.assertIsNone(fuse.exact_cumulative)
        summary = fuse.summary()
        self.assertNotIn("estimated_lower_bound", summary)
        self.assertIn("never stops a session", summary["in_flight_estimate_status"])

    def test_message_and_tool_calls_in_one_response_count_once(self):
        fuse = policy.StreamingSessionFuse("")
        fuse.feed(_events(
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "plan"}},
            {"type": "item.started", "item": {"type": "command_execution"}},
            {"type": "item.started", "item": {"type": "command_execution"}},
            {"type": "item.completed", "item": {"type": "command_execution", "aggregated_output": "o" * 400_000}},
            {"type": "item.completed", "item": {"type": "command_execution", "aggregated_output": "o" * 400_000}},
            {"type": "item.started", "item": {"type": "command_execution"}},
        ))
        self.assertEqual(2, fuse.requests_estimated)
        self.assertEqual(2 * policy.REQUEST_OVERHEAD_FLOOR_TOKENS, fuse.in_flight_estimate)

    def test_estimate_past_the_limit_is_telemetry_and_only_exact_usage_is_described(self):
        fuse = policy.StreamingSessionFuse("p" * 400_000)
        self.assertIsNone(fuse.feed(_events(*(
            {"type": "item.started" if i % 2 == 0 else "item.completed", "item": {"type": "command_execution"}}
            for i in range(9)
        ))))
        self.assertGreaterEqual(fuse.in_flight_estimate, fuse.limit)
        exact = policy.describe_fuse_stop({"basis": policy.EXACT_BASIS, "tokens": 512_000, "limit": 500_000})
        self.assertEqual("exact provider usage 512,000 of 500,000; further turn refused", exact)

    def test_run_streaming_kills_the_process_group_at_the_fuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "codex-flood"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys, time\n"
                "sys.stdin.read()\n"
                "print(json.dumps({'type':'thread.started','thread_id':'flood'}), flush=True)\n"
                "print(json.dumps({'type':'turn.started'}), flush=True)\n"
                "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':600000,'output_tokens':100}}), flush=True)\n"
                "print(json.dumps({'type':'turn.started'}), flush=True)\n"
                "for _ in range(400):\n"
                "    print(json.dumps({'type':'item.started','item':{'type':'command_execution'}}), flush=True)\n"
                "    print(json.dumps({'type':'item.completed','item':{'type':'command_execution','command':'x','aggregated_output':'o'*40000}}), flush=True)\n"
                "    time.sleep(0.01)\n"
                "time.sleep(3600)\n",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            fuse = policy.StreamingSessionFuse("prompt")
            started = time.monotonic()
            result = policy.run_streaming(
                [str(fake)], cwd=tmp, env={"PATH": "/usr/bin:/bin"}, prompt="prompt",
                timeout_seconds=60, fuse=fuse, terminate_grace_seconds=0.5, kill_grace_seconds=0.5,
            )
            self.assertLess(time.monotonic() - started, 20)
            self.assertFalse(result["timed_out"])
            self.assertEqual(policy.EXACT_BASIS, result["fuse_breach"]["basis"])
            self.assertIsNotNone(result["returncode"])
            self.assertIn('"thread_id": "flood"', result["stdout"])


class ModelRoutingTest(unittest.TestCase):
    STANDARD = {"value": "standard", "source": "global_config"}

    def test_simple_medium_complex(self):
        simple = policy.select_model_and_effort({
            "title": "Status check", "context": "Report the count of open items; read-only.",
            "allowed_actions": ["local_read"], "definition_of_done": "Count reported.",
        }, cost_dial=self.STANDARD)
        self.assertEqual(("simple", "gpt-6-luna", "low"), (simple["tier"], simple["model"], simple["reasoning_effort"]))
        medium = policy.select_model_and_effort({
            "title": "Add a dashboard filter",
            "context": "Add a status filter to the Queue view and its endpoint. " + "Keep the existing layout and behaviour. " * 12,
            "allowed_actions": ["local_read", "local_edit", "local_test"],
            "definition_of_done": "Filter works; focused tests pass.",
        }, cost_dial=self.STANDARD)
        self.assertEqual(("medium", "gpt-6-sol", "medium"), (medium["tier"], medium["model"], medium["reasoning_effort"]))
        complex_ = policy.select_model_and_effort({
            "title": "Ledger schema migration",
            "context": "Migrate the token ledger schema with locking and rollback. " + "Preserve every historical row. " * 12,
            "allowed_actions": ["local_read", "local_edit", "local_test"],
            "definition_of_done": "Migration proven reversible.",
        }, cost_dial=self.STANDARD)
        self.assertEqual(("complex", "gpt-6-sol", "high"), (complex_["tier"], complex_["model"], complex_["reasoning_effort"]))
        for chosen in (simple, medium, complex_):
            self.assertTrue(chosen["reason"])
            self.assertIn(chosen["model"], policy.load_codex_tiers(ROOT)["supported_models"])

    def test_operator_override_pins_and_global_dial_shifts(self):
        risky = {"title": "Security refactor", "context": "Refactor credential handling. " * 20, "allowed_actions": ["local_edit"]}
        pinned = policy.select_model_and_effort(risky, cost_dial={"value": "light", "source": "scope_override"})
        self.assertEqual("simple", pinned["tier"])
        self.assertIn("operator override budget:light", pinned["reason"])
        shifted = policy.select_model_and_effort(risky, cost_dial={"value": "light", "source": "global_config"})
        self.assertEqual("medium", shifted["tier"])
        self.assertIn("light dial shifted complex->medium", shifted["reason"])
        retry = policy.classify_step_complexity({"context": "x" * 600}, attempt=2)
        self.assertIn("retry attempt 2 (+1)", retry["reasons"])

    def test_unconfigured_model_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            routes = json.loads((ROOT / "queue" / "model_routes.json").read_text(encoding="utf-8"))
            routes["routes"]["codex"]["codex_selection"]["tiers"]["simple"]["model"] = "gpt-invented"
            (root / "queue").mkdir()
            (root / "queue" / "model_routes.json").write_text(json.dumps(routes), encoding="utf-8")
            with self.assertRaisesRegex(policy.CodexPolicyError, "unconfigured model"):
                policy.select_model_and_effort({}, cost_dial=self.STANDARD, root=root)
        with self.assertRaises(policy.CodexPolicyError):
            policy.build_exec_command(selection={"model": "gpt-6-sol", "reasoning_effort": "ultra"})

    def test_command_carries_selected_model_and_effort(self):
        command = policy.build_exec_command(selection={"model": "gpt-6-luna", "reasoning_effort": "low"})
        self.assertEqual("gpt-6-luna", command[command.index("--model") + 1])
        self.assertIn("model_reasoning_effort=low", command)
        self.assertIn("--ephemeral", command)


class BackendCodexSessionTest(unittest.TestCase):
    def _fake(self, root: Path, *, flood: bool = False, input_tokens: int = 900) -> Path:
        fake = root / "codex-fixture"
        body = (
            "print(json.dumps({'type':'turn.started'}), flush=True)\n"
            "print(json.dumps({'type':'turn.completed','usage':{'input_tokens':600000,'cached_input_tokens':570000,'output_tokens':100}}), flush=True)\n"
            "print(json.dumps({'type':'turn.started'}), flush=True)\n"
            "for _ in range(400):\n"
            "    print(json.dumps({'type':'item.started','item':{'type':'command_execution'}}), flush=True)\n"
            "    print(json.dumps({'type':'item.completed','item':{'type':'command_execution','command':'x','aggregated_output':'o'*40000}}), flush=True)\n"
            "time.sleep(3600)\n"
            if flood else
            "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'PASS'}}), flush=True)\n"
            f"print(json.dumps({{'type':'turn.completed','usage':{{'input_tokens':{input_tokens},'cached_input_tokens':100,'output_tokens':40}}}}), flush=True)\n"
        )
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, sys, time\n"
            "root = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
            "(root / 'argv.json').write_text(json.dumps(sys.argv), encoding='utf-8')\n"
            "sys.stdin.read()\n"
            "print(json.dumps({'type':'thread.started','thread_id':'fixture-thread'}), flush=True)\n" + body,
            encoding="utf-8",
        )
        fake.chmod(0o755)
        return fake

    def _context(self, item: dict):
        return backend.assemble_model_context(
            "fixture task", surface="test:codex", classification="technical_only", write_artifact=False,
        )

    def test_each_call_is_its_own_session_scope_with_recorded_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture_root(tmp)
            target = replace(policy.CODEX_TARGET, root=root, executable=self._fake(root), codex_home=root / ".codex")
            item = {"id": ITEM, "title": "Status check", "context": "Read-only count.", "allowed_actions": ["local_read"]}
            with patch.object(backend, "BASE_DIR", root), patch.object(backend, "CODEX_TARGET", target):
                first = backend._run_codex_local(self._context(item), item)
                second = backend._run_codex_local(self._context(item), item)
            self.assertTrue(first["success"])
            self.assertNotEqual(first["invocation"]["fuse_scope"], second["invocation"]["fuse_scope"])
            argv = json.loads((root / "argv.json").read_text(encoding="utf-8"))
            self.assertEqual("gpt-6-luna", argv[argv.index("--model") + 1])
            rows = [json.loads(line) for line in (root / "queue" / "token_ledger.jsonl").read_text().splitlines()]
            invocations = [row for row in rows if row.get("event") == "model_invocation"]
            self.assertEqual(2, len(invocations))
            for row in invocations:
                self.assertEqual("session", row["scope_type"])
                self.assertEqual(ITEM, row["parent_work_item_id"])
                self.assertEqual(940, row["fuse"]["invocation_tokens"])
                self.assertEqual(940, row["fuse"]["scope_total_after"])
                self.assertEqual("gpt-6-luna", row["model_selection"]["model"])
                self.assertEqual("low", row["model_selection"]["reasoning_effort"])
                self.assertEqual("gpt-6-luna", row["model_selection"]["actual_model"])
                self.assertTrue(row["model_selection"]["reason"])
            self.assertEqual(1_880, step6.work_item_usage(ITEM, root=root)["known_tokens"])

    def test_streaming_fuse_stops_session_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture_root(tmp)
            target = replace(policy.CODEX_TARGET, root=root, executable=self._fake(root, flood=True), codex_home=root / ".codex")
            item = {"id": ITEM, "title": "Flood", "context": "Fixture.", "allowed_actions": ["local_read"]}
            started = time.monotonic()
            with patch.object(backend, "BASE_DIR", root), patch.object(backend, "CODEX_TARGET", target), \
                 patch.object(backend, "AGENT_GRACEFUL_TERMINATION_SECONDS", 0.5):
                result = backend._run_codex_local(self._context(item), item)
            self.assertLess(time.monotonic() - started, 30)
            self.assertFalse(result["success"])
            self.assertEqual("session_fuse_stop", result["failure_class"])
            self.assertEqual(policy.EXACT_BASIS, result["invocation"]["session_fuse"]["stopped"]["basis"])
            row = next(
                json.loads(line) for line in (root / "queue" / "token_ledger.jsonl").read_text().splitlines()
                if json.loads(line).get("event") == "model_invocation"
            )
            # The stop is recorded with the exact usage that triggered it, never an estimate.
            self.assertEqual(600_100, row["fuse"]["invocation_tokens"])
            self.assertIn("exact provider usage 600,100 of 500,000", result["output"])
            self.assertNotIn("estimate", result["output"])
            # A fresh session gets a fresh fuse.
            _scope, status = step6.codex_session_preflight("codex-after-stop", work_item_id=ITEM, root=root)
            self.assertFalse(status["paused"])

    def test_completed_single_turn_over_the_limit_is_kept_not_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture_root(tmp)
            target = replace(policy.CODEX_TARGET, root=root, executable=self._fake(root, input_tokens=700_000), codex_home=root / ".codex")
            item = {"id": ITEM, "title": "Status check", "context": "Read-only count.", "allowed_actions": ["local_read"]}
            with patch.object(backend, "BASE_DIR", root), patch.object(backend, "CODEX_TARGET", target):
                result = backend._run_codex_local(self._context(item), item)
            self.assertTrue(result["success"], result.get("output"))
            fuse = result["invocation"]["session_fuse"]
            self.assertIsNone(fuse["stopped"])
            self.assertTrue(fuse["limit_reached_at_turn_end"])
            row = next(
                json.loads(line) for line in (root / "queue" / "token_ledger.jsonl").read_text().splitlines()
                if json.loads(line).get("event") == "model_invocation"
            )
            self.assertEqual(700_040, row["fuse"]["invocation_tokens"])
            self.assertTrue(row["fuse"]["blocks_next_invocation"])


class TechnicalWorkOrderPromptTest(unittest.TestCase):
    def test_technical_worker_prompt_is_a_single_compact_work_order(self):
        item = {
            "id": "AOS-2026-9103", "title": "Repair local preflight and verify the runtime", "owner": "codex",
            "context": "Inspect the effective AI route and the blocked receipts; attempt one read-only model call.",
            "definition_of_done": "A diagnostic artifact records the command, exit status and output.",
            "allowed_actions": ["local_read", "local_edit", "local_test"], "stop_conditions": ["git_push"],
            "sources": ["tools/aos_codex_policy.py"],
        }
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(context_assembler, "ASSEMBLY_DIR", Path(tmp) / "assemblies"):
            instructions = backend._queue_actual_run_prompt(item, "codex")
            context, _pack = context_assembler.worker_context_pack(
                item, owner="codex", execution_instructions=instructions, pack_dir=Path(tmp),
            )
        prepared = policy.prepare_fresh_prompt(context.render())
        self.assertEqual("technical_only", context.classification)
        self.assertTrue(prepared.startswith(policy.PERMISSION_HEADER + "\n\nTask AOS-2026-9103: "))
        self.assertEqual(1, prepared.count(policy.PERMISSION_HEADER))
        order = prepared[len(policy.PERMISSION_HEADER):].strip().splitlines()
        self.assertEqual(["Task", "Context", "Pointers", "Done", "Allowed", "Closeout"], [line.split()[0].rstrip(":") for line in order])
        non_blank = [line for line in prepared.splitlines() if line.strip()]
        self.assertLessEqual(len(non_blank), 10)
        self.assertIn("Pointers: tools/aos_codex_policy.py", prepared)
        self.assertIn("Stop and report instead of: git_push.", prepared)
        self.assertIn("Token usage", prepared)
        for unrelated in ("lead_gen_agent", "voice_agent_setup", "client_memory/workflow.md", "fit_call_prep"):
            self.assertNotIn(unrelated, prepared)
        for manifest_only in (
            "[TTROS_ASSEMBLED_CONTEXT_V1]", "Not applicable", "## provenance", "## action boundaries",
            "## recent receipts", "queue reference validity", "Fresh-session", "ephemeral", "500,000",
            "Required artifact/receipt shape", "Summary for operator:\n",
        ):
            self.assertNotIn(manifest_only, prepared)
        self.assertTrue(any(block.name == "provenance" and block.sources for block in context.blocks))
        self.assertTrue(any(block.name == "action boundaries" for block in context.blocks))  # kept in the manifest

    def test_technical_worker_keeps_a_cited_items_status_but_not_its_own(self):
        item = {
            "id": "AOS-2026-9105", "title": "Repair the receipt parser", "owner": "codex",
            "context": "The parser broke after AOS-2026-9106; repair it.", "definition_of_done": "Focused test passes.",
            "allowed_actions": ["local_read"], "stop_conditions": ["git_push"],
        }
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(context_assembler, "ASSEMBLY_DIR", Path(tmp) / "assemblies"):
            context, _pack = context_assembler.worker_context_pack(
                item, owner="codex", execution_instructions=backend._queue_actual_run_prompt(item, "codex"),
                pack_dir=Path(tmp),
            )
        rendered = context.render()
        self.assertIn("Cited queue items, current status:\n- AOS-2026-9106:", rendered)
        self.assertNotIn("- AOS-2026-9105:", rendered)
        self.assertNotIn("Pointers:", rendered)  # none provided -> line omitted
        self.assertEqual("The parser broke after AOS-2026-9106; repair it.", context_assembler.worker_brief(context.request).split("Context: ", 1)[1].split("\n", 1)[0])
        self.assertNotIn("Allowed:", context_assembler.worker_brief(context.request))

    def test_business_terms_keep_codex_step_knowledge_sensitive(self):
        item = {"id": "AOS-2026-9104", "title": "Prospect follow-up export", "owner": "codex",
                "context": "Export the prospect follow-up list.", "definition_of_done": "CSV written."}
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(context_assembler, "ASSEMBLY_DIR", Path(tmp) / "assemblies"):
            context, _pack = context_assembler.worker_context_pack(item, owner="codex", pack_dir=Path(tmp))
        self.assertEqual("knowledge_sensitive", context.classification)

    def _direct_codex_prompt(self, task: str) -> tuple[context_assembler.AssembledContext, str]:
        captured: list = []
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(context_assembler, "ASSEMBLY_DIR", Path(tmp) / "assemblies"), \
             patch.object(backend, "_run_codex_local", side_effect=lambda ctx: captured.append(ctx) or {
                 "success": True, "output": "ok", "stdout": "", "stderr": "", "returncode": 0,
             }):
            backend.wsl_codex(backend.TaskRun(task=task))
        self.assertEqual(1, len(captured))
        return captured[0], policy.prepare_fresh_prompt(captured[0].render())

    def test_direct_dashboard_codex_gets_the_same_compact_work_order(self):
        context, prepared = self._direct_codex_prompt(
            "Read-only status check: count the files directly inside queue/templates."
        )
        self.assertEqual(("dashboard:codex", "technical_only"), (context.surface, context.classification))
        self.assertEqual(1, prepared.count(policy.PERMISSION_HEADER))
        self.assertIn(context_assembler.DIRECT_WORKER_BOUNDARY, prepared)  # no item stop list here
        self.assertLessEqual(len([line for line in prepared.splitlines() if line.strip()]), 10)
        self.assertNotIn("Not applicable", prepared)
        self.assertNotIn("## provenance", prepared)
        self.assertNotIn("## identity/company", prepared)
        self.assertTrue(any(block.name == "provenance" and block.sources for block in context.blocks))

    def test_direct_dashboard_codex_with_business_terms_keeps_full_context(self):
        context, prepared = self._direct_codex_prompt("Export the prospect follow-up list.")
        self.assertEqual("knowledge_sensitive", context.classification)
        self.assertIn("[TTROS_ASSEMBLED_CONTEXT_V1]", prepared)
        self.assertIn("## identity/company", prepared)

    def test_named_playbook_is_still_selected_for_a_technical_step(self):
        block = context_assembler._matching_workflows_block(
            "Run the submit-confirm path for record shared-submit-1", require_named=True,
        )
        self.assertIn("READ_SOURCE=submit-confirm/SKILL.md", block.content)
        none = context_assembler._matching_workflows_block(
            "Attempt one read-only model call and record the route", require_named=True,
        )
        self.assertTrue(none.content.startswith("N/A"))


if __name__ == "__main__":
    unittest.main()
