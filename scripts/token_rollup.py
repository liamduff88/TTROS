#!/usr/bin/env python3
"""Weekly token rollups for the Agentic OS token ledger.

Reads queue/token_ledger.jsonl and emits one dashboard-ready JSON rollup per
ISO week to queue/rollups/, plus queue/rollups/index.json. This script makes no
model calls and invents no numbers: it aggregates the token counts already
recorded in the ledger (harness/API-derived) and recomputes every cost figure
— per line, and every breakdown (lane, profile, workbench, model, budget
class) — from scripts/model_prices.json only. A ledger line's own stored
est_cost_usd is never read; recomputing from components on every run means
totals always reconcile with by_model, even against historical ledger data.
Token counts recorded as part of an "unavailable" component contribute zero
and are surfaced, never guessed.

Usage:
    python3 scripts/token_rollup.py            # roll up every week found
    python3 scripts/token_rollup.py --week 2026-W28
    python3 scripts/token_rollup.py --print    # also echo rollups to stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parents[1]
TOKEN_LEDGER_PATH = REPO_DIR / "queue" / "token_ledger.jsonl"
ROLLUPS_DIR = REPO_DIR / "queue" / "rollups"
MODEL_PRICES_PATH = REPO_DIR / "scripts" / "model_prices.json"


def _read_json_or(default: Any, path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_ledger(path: Path) -> list[dict]:
    lines = []
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    for line_number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            lines.append(json.loads(raw))
        except json.JSONDecodeError as exc:
            print(f"skipping malformed ledger line {line_number}: {exc}", file=sys.stderr)
    return lines


def load_prices() -> dict:
    prices = _read_json_or({}, MODEL_PRICES_PATH)
    return prices.get("models", {}) if isinstance(prices, dict) else {}


def _no_agent_invocation(line: dict) -> bool:
    usage = line.get("token_usage") if isinstance(line.get("token_usage"), dict) else {}
    unavailable = usage.get("unavailable") if isinstance(usage.get("unavailable"), list) else []
    return bool(
        line.get("no_agent_invocation")
        or usage.get("no_agent_invocation")
        or any(str(value).strip().lower() == "no agent invocation" for value in unavailable)
    )


def _exact_invocation(line: dict) -> bool:
    usage = line.get("token_usage") if isinstance(line.get("token_usage"), dict) else {}
    return any(
        isinstance(workbench, dict) and workbench.get("source") == "reported"
        for workbench in (usage.get("workbenches") or [])
    )


def effective_ledger_lines(lines: list[dict]) -> list[dict]:
    """Apply invocation deduplication and exact-over-placeholder precedence."""
    exact_items = {str(line.get("item_id") or "") for line in lines if _exact_invocation(line)}
    selected: dict[tuple[str, str], tuple[int, int, dict]] = {}
    passthrough: list[tuple[int, dict]] = []
    for position, line in enumerate(lines):
        item_id = str(line.get("item_id") or "")
        if item_id in exact_items and not line.get("session_id") and _no_agent_invocation(line):
            continue
        session_id = str(line.get("session_id") or line.get("invocation_id") or "")
        if not item_id or not session_id:
            passthrough.append((position, line))
            continue
        rank = 2 if _exact_invocation(line) else 0 if _no_agent_invocation(line) else 1
        key = (item_id, session_id)
        prior = selected.get(key)
        if prior is None or rank > prior[0] or (rank == prior[0] and position > prior[1]):
            selected[key] = (rank, position, line)
    combined = passthrough + [(position, line) for _, position, line in selected.values()]
    return [line for _, line in sorted(combined, key=lambda value: value[0])]


def cost_for(model: str | None, inp: int, outp: int, prices: dict) -> float:
    rate = prices.get(model) if model else None
    if not isinstance(rate, dict):
        return 0.0
    return round(inp / 1_000_000 * rate.get("input_per_mtok", 0.0)
                 + outp / 1_000_000 * rate.get("output_per_mtok", 0.0), 6)


def iso_week_key(timestamp: str) -> str:
    ts = timestamp.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        return "unknown"
    iso_year, iso_week, _ = dt.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _bucket(store: dict, key: str) -> dict:
    return store.setdefault(key, {"input": 0, "output": 0, "est_cost_usd": 0.0, "count": 0})


def rollup_week(week: str, lines: list[dict], prices: dict) -> dict:
    lines = effective_ledger_lines(lines)
    totals = {"input": 0, "output": 0, "est_cost_usd": 0.0}
    by_lane: dict[str, dict] = {}
    by_profile: dict[str, dict] = {}
    by_workbench: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    by_budget: dict[str, dict] = {}
    escalated_cost = 0.0
    items: list[dict] = []
    unavailable: dict[str, int] = {}

    for line in lines:
        usage = line.get("token_usage", {})
        line_in = int(usage.get("totals", {}).get("input", 0))
        line_out = int(usage.get("totals", {}).get("output", 0))

        # Never trust a stored top-level est_cost_usd (it may be stale or, on
        # older lines, wrong): recompute every line's cost deterministically
        # from its own components, the same way as by_model below, so totals
        # and every breakdown always reconcile with by_model by construction.
        components: list[dict] = []
        orch = usage.get("orchestrator", {})
        if orch.get("input") or orch.get("output"):
            components.append({"model": line.get("model_confirmed", "unavailable"),
                               "input": int(orch.get("input", 0)), "output": int(orch.get("output", 0))})
        for sub in usage.get("subagents", []):
            components.append({"model": sub.get("model", "unavailable"),
                               "input": int(sub.get("input", 0)), "output": int(sub.get("output", 0))})
        for work in usage.get("workbenches", []):
            components.append({"model": work.get("model", "unavailable"),
                               "input": int(work.get("input", 0)), "output": int(work.get("output", 0))})
        line_cost = round(sum(cost_for(c["model"], c["input"], c["output"], prices) for c in components), 6)

        totals["input"] += line_in
        totals["output"] += line_out
        totals["est_cost_usd"] = round(totals["est_cost_usd"] + line_cost, 6)
        if line.get("escalated"):
            escalated_cost = round(escalated_cost + line_cost, 6)

        lane_b = _bucket(by_lane, line.get("lane", "unknown"))
        lane_b["input"] += line_in
        lane_b["output"] += line_out
        lane_b["est_cost_usd"] = round(lane_b["est_cost_usd"] + line_cost, 6)
        lane_b["count"] += 1

        profile_b = _bucket(by_profile, line.get("profile", "unknown"))
        profile_b["input"] += line_in
        profile_b["output"] += line_out
        profile_b["est_cost_usd"] = round(profile_b["est_cost_usd"] + line_cost, 6)
        profile_b["count"] += 1

        budget_b = _bucket(by_budget, line.get("budget_class", "unknown"))
        budget_b["input"] += line_in
        budget_b["output"] += line_out
        budget_b["est_cost_usd"] = round(budget_b["est_cost_usd"] + line_cost, 6)
        budget_b["count"] += 1

        # by_model: attribute each component's tokens to its model; cost is
        # recomputed deterministically from model_prices.json.
        for comp in components:
            mb = _bucket(by_model, comp["model"])
            mb["input"] += comp["input"]
            mb["output"] += comp["output"]
            mb["est_cost_usd"] = round(mb["est_cost_usd"] + cost_for(comp["model"], comp["input"], comp["output"], prices), 6)
            mb["count"] += 1

        # by_workbench: one bucket per tool, across every workbench entry on
        # the line (a line may report more than one workbench).
        for work in usage.get("workbenches", []):
            wb = _bucket(by_workbench, work.get("tool", "unknown"))
            wb["input"] += int(work.get("input", 0))
            wb["output"] += int(work.get("output", 0))
            wb["est_cost_usd"] = round(
                wb["est_cost_usd"] + cost_for(work.get("model", "unavailable"), int(work.get("input", 0)), int(work.get("output", 0)), prices), 6
            )
            wb["count"] += 1

        for name in usage.get("unavailable", []):
            unavailable[name] = unavailable.get(name, 0) + 1

        items.append({
            "item_id": line.get("item_id"),
            "lane": line.get("lane"),
            "budget_class": line.get("budget_class"),
            "escalated": bool(line.get("escalated")),
            "input": line_in,
            "output": line_out,
            "est_cost_usd": round(line_cost, 6),
        })

    top_items = sorted(items, key=lambda i: (i["est_cost_usd"], i["input"] + i["output"]), reverse=True)[:10]
    total_cost = totals["est_cost_usd"]
    return {
        "week": week,
        "generated_from": "queue/token_ledger.jsonl",
        "model_prices": "scripts/model_prices.json (placeholder rates until filled)",
        "line_count": len(lines),
        "totals": totals,
        "by_lane": by_lane,
        "by_profile": by_profile,
        "by_workbench": by_workbench,
        "by_model": by_model,
        "by_budget_class": by_budget,
        "escalation": {
            "escalated_cost_usd": escalated_cost,
            "total_cost_usd": total_cost,
            "escalated_share": round(escalated_cost / total_cost, 4) if total_cost else 0.0,
        },
        "top_items": top_items,
        "unavailable_components": unavailable,
    }


def write_rollup(rollup: dict) -> Path:
    ROLLUPS_DIR.mkdir(parents=True, exist_ok=True)
    path = ROLLUPS_DIR / f"week-{rollup['week']}.json"
    path.write_text(json.dumps(rollup, indent=2) + "\n", encoding="utf-8")
    return path


def write_index(weeks: list[str]) -> Path:
    ROLLUPS_DIR.mkdir(parents=True, exist_ok=True)
    index = {"weeks": sorted(weeks), "files": [f"week-{w}.json" for w in sorted(weeks)]}
    path = ROLLUPS_DIR / "index.json"
    path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Weekly Agentic OS token rollups")
    parser.add_argument("--week", help="Only roll up this ISO week, e.g. 2026-W28")
    parser.add_argument("--print", dest="echo", action="store_true", help="Echo rollups to stdout")
    args = parser.parse_args(argv)

    lines = load_ledger(TOKEN_LEDGER_PATH)
    prices = load_prices()

    weeks: dict[str, list[dict]] = {}
    for line in lines:
        weeks.setdefault(iso_week_key(line.get("timestamp", "")), []).append(line)

    if args.week:
        weeks = {args.week: weeks.get(args.week, [])}

    written = []
    for week, week_lines in sorted(weeks.items()):
        rollup = rollup_week(week, week_lines, prices)
        path = write_rollup(rollup)
        written.append(week)
        if args.echo:
            print(json.dumps(rollup, indent=2))
    if not args.week:
        write_index(written)

    print(f"wrote {len(written)} weekly rollup(s) to {ROLLUPS_DIR.relative_to(REPO_DIR)}: {', '.join(written) or '(none)'}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
