"""Focused acceptance fixtures for Step 6 cost dial and token fuse.

Revisit: when the Step 6 accounting, dial, pricing, or fuse contract changes. · Last touched: 2026-08-06.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from hooks import context_assembler_hook
from tools import aos_codex_policy
from tools.step6_cost_control import (
    CostControlError,
    FusePausedError,
    Scope,
    calculate_cost,
    canonical_usage,
    format_threshold_alert,
    fuse_status,
    preflight,
    record_invocation,
    record_unavailable_invocation,
    reset_scope,
    resolve_cost_dial,
    set_override,
)


ROOT = Path(__file__).resolve().parents[1]


class Step6Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "queue").mkdir()
        (self.root / "scripts").mkdir()
        (self.root / "queue" / "notifications.json").write_text(json.dumps({
            "operator_controls": {"cost_dial": "standard"},
        }), encoding="utf-8")
        (self.root / "scripts" / "model_prices.json").write_text(
            (ROOT / "scripts" / "model_prices.json").read_text(encoding="utf-8"), encoding="utf-8"
        )
        (self.root / "queue" / "token_ledger.jsonl").write_text("", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def record(self, scope, identity, total, *, cached=0, model="gpt-5.5", provider="openai-codex"):
        output = min(100, total)
        return record_invocation(
            scope,
            invocation_id=identity,
            provider=provider,
            model=model,
            usage={
                "input_tokens": total - output,
                "cached_input_tokens": cached,
                "output_tokens": output,
                "reasoning_output_tokens": min(10, output),
                "cache_semantics": "included_in_provider_input",
            },
            root=self.root,
            surface="fixture",
            timestamp="2026-08-04T12:00:00Z",
        )


class AccountingTests(Step6Fixture):
    def test_historical_fixture_reconciles_without_cached_double_counting(self):
        normalized = canonical_usage({
            "provider": "historical-provider",
            "input_tokens": 564_207,
            "cached_input_tokens": 18_738_432,
            "output_tokens": 77_915,
            "reasoning_output_tokens": 21_622,
            "cache_semantics": "provider_separate_counter",
        })
        self.assertEqual(normalized["canonical_total"], 642_122)
        self.assertEqual(normalized["cached_input"], 18_738_432)
        self.assertEqual(normalized["reasoning"], 21_622)

    def test_codex_cached_input_is_subset_and_not_added_twice(self):
        normalized = canonical_usage({
            "provider": "openai-codex", "input_tokens": 1000,
            "cached_input_tokens": 800, "output_tokens": 50,
            "reasoning_output_tokens": 25,
        })
        self.assertEqual(normalized["fresh_input"], 200)
        self.assertEqual(normalized["canonical_total"], 1050)
        with self.assertRaisesRegex(CostControlError, "cached input exceeds"):
            canonical_usage({"provider": "openai-codex", "input_tokens": 10, "cached_input_tokens": 11, "output_tokens": 1})

    def test_hermes_openai_codex_aggregate_report_keeps_separate_cache_counter(self):
        normalized = canonical_usage({
            "provider": "openai-codex",
            "input_tokens": 79_865,
            "output_tokens": 6_663,
            "cache_read_tokens": 852_992,
            "cache_write_tokens": 0,
            "reasoning_tokens": 967,
            "total_tokens": 939_520,
            "api_calls": 17,
        })
        self.assertEqual(normalized["cache_semantics"], "provider_separate_counter")
        self.assertEqual(normalized["fresh_input"], 79_865)
        self.assertEqual(normalized["cached_input"], 852_992)
        self.assertEqual(normalized["canonical_total"], 86_528)

    def test_unknown_is_not_zero(self):
        scope = Scope("session", "unknown-accounting")
        record_unavailable_invocation(
            scope, invocation_id="unknown-1", reason="missing terminal usage", root=self.root
        )
        status = fuse_status(scope, root=self.root)
        self.assertIsNone(status["canonical_tokens"])
        self.assertTrue(status["accounting_unknown"])
        with self.assertRaises(FusePausedError):
            preflight(scope, root=self.root)
        set_override(scope, active=True, reason="known fuse override only", root=self.root)
        with self.assertRaises(FusePausedError):
            preflight(scope, root=self.root)


class DialAndPricingTests(Step6Fixture):
    def test_dial_precedence_and_invalid_values(self):
        self.assertEqual(resolve_cost_dial(root=self.root), {"value": "standard", "source": "global_config"})
        self.assertEqual(resolve_cost_dial(override="heavy", root=self.root), {"value": "heavy", "source": "scope_override"})
        with self.assertRaisesRegex(CostControlError, "invalid cost dial"):
            resolve_cost_dial(override="turbo", root=self.root)
        (self.root / "queue" / "notifications.json").write_text(
            json.dumps({"operator_controls": {"cost_dial": "silent-fallback"}}), encoding="utf-8"
        )
        with self.assertRaisesRegex(CostControlError, "invalid global cost dial"):
            resolve_cost_dial(root=self.root)

    def test_effective_dated_pricing_and_unpriced_state(self):
        usage = canonical_usage({
            "provider": "openai-codex", "input_tokens": 1000,
            "cached_input_tokens": 800, "output_tokens": 100,
        })
        priced = calculate_cost("gpt-5.5", usage, at="2026-08-04T00:00:00Z", root=self.root)
        self.assertEqual(priced["status"], "priced")
        self.assertEqual(priced["usd"], 0.0044)
        unpriced = calculate_cost("unknown-model", usage, at="2026-08-04T00:00:00Z", root=self.root)
        self.assertEqual(unpriced["status"], "unpriced")
        self.assertIsNone(unpriced["usd"])
        expired = calculate_cost("claude-sonnet-5", usage, at="2026-09-01T00:00:00Z", root=self.root)
        self.assertEqual(expired["status"], "unpriced")


class FuseTransitionTests(Step6Fixture):
    def test_concurrent_completions_assign_one_threshold_event(self):
        scope = Scope("session", "concurrent-threshold")
        self.record(scope, "base", 249_999)
        gate = threading.Barrier(2)

        def finish(identity):
            gate.wait()
            return self.record(scope, identity, 1)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(finish, ("race-a", "race-b")))
        emitted = [
            event
            for result in results
            for event in result["row"]["fuse"]["thresholds_emitted"]
        ]
        self.assertEqual(emitted, ["advisory"])
        self.assertEqual(fuse_status(scope, root=self.root)["canonical_tokens"], 250_001)

    def test_thresholds_restart_idempotency_pause_override_reset_and_isolation(self):
        scope = Scope("work_item", "AOS-2026-9001")
        other = Scope("session", "unrelated-scope")
        first = self.record(scope, "one", 249_999)
        self.assertEqual(first["row"]["fuse"]["thresholds_emitted"], [])
        advisory = self.record(scope, "two", 1)
        self.assertEqual(advisory["row"]["fuse"]["thresholds_emitted"], ["advisory"])
        retry = self.record(scope, "two", 1)
        self.assertTrue(retry["idempotent"])
        self.assertEqual(fuse_status(scope, root=self.root)["thresholds_emitted"], ["advisory"])
        warning = self.record(scope, "three", 150_000)
        self.assertEqual(warning["row"]["fuse"]["thresholds_emitted"], ["warning"])
        pause = self.record(scope, "four", 100_000)
        self.assertEqual(pause["row"]["fuse"]["thresholds_emitted"], ["pause"])
        self.assertTrue(fuse_status(scope, root=self.root)["paused"])
        with self.assertRaises(FusePausedError):
            preflight(scope, root=self.root)
        set_override(scope, active=True, reason="operator approved one named continuation", root=self.root)
        preflight(scope, root=self.root)
        again = set_override(scope, active=True, reason="same state", root=self.root)
        self.assertTrue(again["idempotent"])
        set_override(scope, active=False, reason="", root=self.root)
        with self.assertRaises(FusePausedError):
            preflight(scope, root=self.root)
        self.assertFalse(fuse_status(other, root=self.root)["paused"])

    def test_explicit_scope_epoch_reset_preserves_history_and_repairs_unknown_only_for_named_scope(self):
        scope = Scope("session", "telegram-current")
        other = Scope("session", "telegram-other")
        record_unavailable_invocation(scope, invocation_id="unknown-current", reason="missing usage", root=self.root)
        self.record(other, "other-known", 123)
        other_before = fuse_status(other, root=self.root)

        result = reset_scope(scope, reason="operator explicitly reset this named Telegram scope", root=self.root)

        self.assertTrue(result["recorded"])
        self.assertFalse(result["status"]["paused"])
        self.assertFalse(result["status"]["accounting_unknown"])
        self.assertEqual(result["status"]["canonical_tokens"], 0)
        self.assertEqual(result["status"]["fuse_limit"], 500_000)
        self.assertEqual(fuse_status(other, root=self.root), other_before)
        preflight(scope, root=self.root)
        rows = [json.loads(line) for line in (self.root / "queue/token_ledger.jsonl").read_text().splitlines()]
        self.assertTrue(any(row.get("invocation_id") == "unknown-current" for row in rows))
        reset = next(row for row in rows if row.get("event") == "fuse_scope_reset")
        self.assertTrue(reset["previous_accounting_unknown"])
        self.assertTrue(reset["no_agent_invocation"])

    def test_historical_fixture_crosses_all_thresholds_once_and_blocks_next(self):
        scope = Scope("session", "historical-642122")
        result = record_invocation(
            scope,
            invocation_id="historical",
            provider="historical-provider",
            model="unknown-historical-model",
            usage={
                "input_tokens": 564_207,
                "cached_input_tokens": 18_738_432,
                "output_tokens": 77_915,
                "reasoning_output_tokens": 21_622,
                "cache_semantics": "provider_separate_counter",
            },
            root=self.root,
            surface="fixture:historical",
        )
        self.assertEqual(result["row"]["fuse"]["thresholds_emitted"], ["advisory", "warning", "pause"])
        self.assertEqual(result["status"]["canonical_tokens"], 642_122)
        self.assertTrue(result["status"]["paused"])
        with self.assertRaises(FusePausedError):
            preflight(scope, root=self.root)

    def test_telegram_compatible_alert_is_compact_and_visible(self):
        scope = Scope("session", "format-proof")
        result = self.record(scope, "alert", 250_000)
        message = format_threshold_alert(scope, result["status"], "advisory")
        self.assertIn("50% / 250,000", message)
        self.assertIn("informational only", message)
        self.assertIn("Cost dial standard (global_config)", message)


class CompactionAndGuardTests(unittest.TestCase):
    def test_auto_compaction_remains_and_lower_handoff_breaker_is_absent(self):
        policy = (ROOT / "tools" / "aos_codex_policy.py").read_text(encoding="utf-8")
        backend = (ROOT / "dashboard" / "backend" / "main.py").read_text(encoding="utf-8")
        queue = (ROOT / "tools" / "aos-queue.py").read_text(encoding="utf-8")
        self.assertIn("model_auto_compact_token_limit", policy)
        self.assertNotIn("CONTEXT_HANDOFF_THRESHOLD_TOKENS", backend + queue)
        self.assertNotIn("MAX_CONTEXT_HANDOFFS", backend + queue)
        self.assertNotIn("MAX_FRESH_PROMPT_BYTES", policy)

    def test_compaction_is_native_and_full_required_prompt_is_preserved(self):
        required_tail = "REQUIRED_CONTEXT_TAIL_SENTINEL"
        request = ("retained context\n" * 6_000) + required_tail
        prepared = aos_codex_policy.prepare_fresh_prompt(request)
        command = aos_codex_policy.build_exec_command(cost_dial="standard")
        self.assertGreater(len(prepared.encode("utf-8")), 64 * 1024)
        self.assertIn(required_tail, prepared)
        self.assertIn(
            f"model_auto_compact_token_limit={aos_codex_policy.AUTO_COMPACT_TOKEN_LIMIT}",
            command,
        )

    def test_protected_native_hook_requires_wrapper_and_preflights_before_assembly(self):
        payload = {
            "hook_event_name": "pre_llm_call",
            "session_id": "hook-session",
            "extra": {"platform": "cli", "user_message": "bounded request"},
        }
        with mock.patch.object(context_assembler_hook, "_profile", return_value="aos-orchestrator"), \
             mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "canonical accounting/fuse wrapper"):
                context_assembler_hook.evaluate(payload)
        fake = SimpleNamespace(render=lambda include_request=False: "[CONTEXT ASSEMBLER v1]\n")
        env = {
            "AOS_STEP6_WRAPPED": "1",
            "AOS_STEP6_SCOPE_TYPE": "session",
            "AOS_STEP6_SCOPE_ID": "hook-session",
        }
        with mock.patch.object(context_assembler_hook, "_profile", return_value="aos-orchestrator"), \
             mock.patch.object(context_assembler_hook, "preflight") as guarded, \
             mock.patch.object(context_assembler_hook, "assemble", return_value=fake) as assembled, \
             mock.patch.dict("os.environ", env, clear=True):
            result = context_assembler_hook.evaluate(payload)
        guarded.assert_called_once()
        assembled.assert_called_once()
        self.assertIn("CONTEXT ASSEMBLER", result["context"])

    def test_step5_detector_has_no_model_client(self):
        detector = (ROOT / "tools" / "morning_brief_detector.py").read_text(encoding="utf-8")
        self.assertNotIn("openai", detector.lower())
        self.assertNotIn("anthropic", detector.lower())
        self.assertNotIn("run_oneshot", detector)


if __name__ == "__main__":
    unittest.main()
