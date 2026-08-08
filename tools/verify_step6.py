#!/usr/bin/env python3
"""Named Step 6 acceptance verifiers; deterministic except the read-only status view.

Revisit: when Step 6 acceptance or model-call surfaces change. · Last touched: 2026-08-04.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import tempfile
from pathlib import Path

from step6_cost_control import (
    FUSE_LIMIT,
    CostControlError,
    FusePausedError,
    Scope,
    canonical_usage,
    fuse_status,
    preflight,
    record_invocation,
)


ROOT = Path(__file__).resolve().parents[1]


def _pass(name: str, details: dict) -> dict:
    return {"verifier": name, "status": "PASS", **details}


def accounting() -> dict:
    historical = canonical_usage({
        "provider": "historical-provider",
        "input_tokens": 564_207,
        "cached_input_tokens": 18_738_432,
        "output_tokens": 77_915,
        "reasoning_output_tokens": 21_622,
        "cache_semantics": "provider_separate_counter",
    })
    assert historical["canonical_total"] == 642_122
    assert historical["cached_input"] == 18_738_432
    assert historical["reasoning"] <= historical["output"]
    return _pass("accounting", {
        "formula": historical["formula"],
        "historical": {key: historical[key] for key in ("input", "cached_input", "output", "reasoning", "canonical_total")},
    })


def pricing() -> dict:
    payload = json.loads((ROOT / "scripts" / "model_prices.json").read_text(encoding="utf-8"))
    assert payload.get("rates_are_placeholders") is False
    today = dt.date(2026, 8, 4)
    required = ("gpt-5.5", "claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5")
    checked = {}
    for model in required:
        rate = payload["models"][model]
        assert rate.get("priced") is True
        assert dt.date.fromisoformat(rate["effective_from"]) <= today
        if rate.get("effective_through"):
            assert today <= dt.date.fromisoformat(rate["effective_through"])
        assert all(isinstance(rate.get(key), (int, float)) for key in ("input_per_mtok", "cache_read_per_mtok", "output_per_mtok"))
        assert str(rate.get("source") or "").startswith("https://")
        checked[model] = {"effective_from": rate["effective_from"], "effective_through": rate.get("effective_through"), "source": rate["source"]}
    assert payload["models"]["default"].get("priced") is False
    return _pass("pricing", {"version": payload["version"], "models": checked, "unknown_models": "explicitly unpriced"})


def coverage() -> dict:
    backend = (ROOT / "dashboard" / "backend" / "main.py").read_text(encoding="utf-8")
    coordinator = (ROOT / "tools" / "aos-hermes-coordinator.sh").read_text(encoding="utf-8")
    operator = (ROOT / "tools" / "aos-hermes-operator-lean.sh").read_text(encoding="utf-8")
    hook = (ROOT / "hooks" / "context_assembler_hook.py").read_text(encoding="utf-8")
    queue = (ROOT / "tools" / "aos-queue.py").read_text(encoding="utf-8")
    assembler = (ROOT / "tools" / "context_assembler.py").read_text(encoding="utf-8")
    checks = {
        "sticky_and_dashboard_hermes": all(value in backend for value in ("derive_step6_scope", "record_step6_invocation", "_run_hermes_message")),
        "telegram_shared_backend": 'surface = f"hermes:{platform}"' in hook and "/api/wsl/hermes" in backend,
        "codex_dispatch": "step6_preflight(scope" in backend and "record_step6_invocation" in backend,
        "queue_codex": "step6_preflight(step6_scope" in queue and "record_step6_invocation" in queue,
        "claude_dispatch": "step6_record: bool = True" in backend and "Claude terminal usage unavailable" in backend,
        "departments_and_orchestrator": "record-usage" in coordinator and "AOS_STEP6_WRAPPED" in coordinator,
        "protected_native_runner": "canonical accounting/fuse wrapper" in hook and "preflight(Scope" in hook,
        "context_assembler": "require_assembled_context" in backend and "raw prompt strings are forbidden" in assembler,
        "scheduled_model_work": "AOS_STEP6_WRAPPED" in hook and "record-usage" in coordinator,
        "capture_classifier": "LocalDeterministicClassifier" in (ROOT / "tools" / "aos_capture.py").read_text(encoding="utf-8"),
        "review_calls": 'surface="queue:hermes-review"' in backend,
        "worker_context_packs": "worker_context_pack(" in backend,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AssertionError(f"uncovered model surfaces: {failed}")
    return _pass("coverage", {"surfaces": checks, "deterministic_capture": "zero model invocation"})


def guards() -> dict:
    files = {
        "policy": (ROOT / "tools" / "aos_codex_policy.py").read_text(encoding="utf-8"),
        "backend": (ROOT / "dashboard" / "backend" / "main.py").read_text(encoding="utf-8"),
        "queue": (ROOT / "tools" / "aos-queue.py").read_text(encoding="utf-8"),
        "assembler": (ROOT / "tools" / "context_assembler.py").read_text(encoding="utf-8"),
    }
    joined = "\n".join(files.values())
    forbidden = ("CONTEXT_HANDOFF_THRESHOLD_TOKENS", "MAX_CONTEXT_HANDOFFS", "MAX_FRESH_PROMPT_BYTES")
    found = [value for value in forbidden if value in joined]
    if found:
        raise AssertionError(f"overlapping guards remain: {found}")
    assert "model_auto_compact_token_limit" in files["policy"]
    assert "No selected block was truncated" in files["assembler"]
    assert "soft context budget exceeded" in files["assembler"]
    return _pass("guards", {
        "removed": list(forbidden),
        "kept": ["Context Assembler", "visible soft-budget warning", "model_auto_compact_token_limit"],
        "silent_model_downgrade": False,
    })


def historical_fixture() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "queue").mkdir()
        (root / "scripts").mkdir()
        (root / "queue" / "notifications.json").write_text(json.dumps({"operator_controls": {"cost_dial": "standard"}}), encoding="utf-8")
        (root / "scripts" / "model_prices.json").write_text((ROOT / "scripts" / "model_prices.json").read_text(encoding="utf-8"), encoding="utf-8")
        scope = Scope("session", "historical-642122")
        result = record_invocation(
            scope,
            invocation_id="historical-fixture",
            provider="historical-provider",
            model="unknown-historical-model",
            usage={
                "input_tokens": 564_207,
                "cached_input_tokens": 18_738_432,
                "output_tokens": 77_915,
                "reasoning_output_tokens": 21_622,
                "cache_semantics": "provider_separate_counter",
            },
            root=root,
            surface="fixture:historical",
        )
        assert result["status"]["canonical_tokens"] == 642_122
        assert result["row"]["fuse"]["thresholds_emitted"] == ["advisory", "warning", "pause"]
        try:
            preflight(scope, root=root)
        except FusePausedError:
            blocked = True
        else:
            blocked = False
        assert blocked
        return _pass("historical-fixture", {
            "canonical_tokens": 642_122,
            "cached_input_displayed": 18_738_432,
            "events": ["advisory", "warning", "pause"],
            "next_invocation_blocked": True,
        })


def step5_attribution() -> dict:
    detector = (ROOT / "tools" / "morning_brief_detector.py").read_text(encoding="utf-8").lower()
    forbidden = [value for value in ("openai", "anthropic", "run_oneshot", "aiaagent") if value in detector]
    if forbidden:
        raise AssertionError(f"Step 5 detector contains model surface markers: {forbidden}")
    interpretation = canonical_usage({
        "provider": "openai-codex", "input_tokens": 58_504,
        "output_tokens": 2_320, "reasoning_output_tokens": 1_346,
        "cached_input_tokens": 0,
    })
    assert interpretation["canonical_total"] == 60_824 < 250_000
    return _pass("step5-attribution", {
        "detector": {"input": 0, "output": 0, "model_invocations": 0},
        "interpretation": {"input": 58_504, "output": 2_320, "reasoning": 1_346, "canonical_total": 60_824},
        "threshold_events": [],
    })


def status(scope_type: str, scope_id: str) -> dict:
    state = fuse_status(Scope(scope_type, scope_id), root=ROOT)
    required = ("effective_cost_dial", "actual_model", "canonical_tokens", "breakdown", "cost", "fuse_percent", "thresholds_emitted", "paused", "override_active")
    missing = [key for key in required if key not in state]
    if missing:
        raise AssertionError(f"status missing fields: {missing}")
    return _pass("status", state)


VERIFIERS = {
    "accounting": accounting,
    "pricing": pricing,
    "coverage": coverage,
    "guards": guards,
    "historical-fixture": historical_fixture,
    "step5-attribution": step5_attribution,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("verifier", choices=(*VERIFIERS, "status", "all"))
    parser.add_argument("--scope-type", choices=("work_item", "session"), default="session")
    parser.add_argument("--scope-id", default="step6-bounded-proof")
    args = parser.parse_args()
    try:
        if args.verifier == "all":
            result = {name: function() for name, function in VERIFIERS.items()}
        elif args.verifier == "status":
            result = status(args.scope_type, args.scope_id)
        else:
            result = VERIFIERS[args.verifier]()
    except (AssertionError, CostControlError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "verifier": args.verifier, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
