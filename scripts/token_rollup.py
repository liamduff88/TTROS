#!/usr/bin/env python3
"""Weekly token rollups for the Agentic OS token ledger.

Reads queue/token_ledger.jsonl and emits one dashboard-ready JSON rollup per
ISO week to queue/rollups/, plus queue/rollups/index.json. This script makes no
model calls and invents no numbers: it aggregates the counts already recorded
in the ledger (harness/API-derived) and recomputes model-level cost from
scripts/model_prices.json only. Token counts recorded as part of an
"unavailable" component contribute zero and are surfaced, never guessed.

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
    totals = {"input": 0, "output": 0, "est_cost_usd": 0.0}
    by_lane: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    by_budget: dict[str, dict] = {}
    escalated_cost = 0.0
    items: list[dict] = []
    unavailable: dict[str, int] = {}

    for line in lines:
        usage = line.get("token_usage", {})
        line_in = int(usage.get("totals", {}).get("input", 0))
        line_out = int(usage.get("totals", {}).get("output", 0))
        line_cost = float(usage.get("est_cost_usd", 0.0) or 0.0)

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

        budget_b = _bucket(by_budget, line.get("budget_class", "unknown"))
        budget_b["input"] += line_in
        budget_b["output"] += line_out
        budget_b["est_cost_usd"] = round(budget_b["est_cost_usd"] + line_cost, 6)
        budget_b["count"] += 1

        # by_model: attribute each component's tokens to its model; cost is
        # recomputed deterministically from model_prices.json.
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
        for comp in components:
            mb = _bucket(by_model, comp["model"])
            mb["input"] += comp["input"]
            mb["output"] += comp["output"]
            mb["est_cost_usd"] = round(mb["est_cost_usd"] + cost_for(comp["model"], comp["input"], comp["output"], prices), 6)
            mb["count"] += 1

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
