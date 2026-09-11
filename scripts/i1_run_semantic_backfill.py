#!/usr/bin/env python3
"""STEP I1 Phase 2 backfill driver: 15 real historical_calls sources through the
real ``run_intake(mode="semantic")`` path, one shared 30-call budget.

Not a new ingestion framework -- a thin loop over the same production
``run_intake`` call the SKILL.md CLI entry point makes. See
scripts/i1_source_intake_semantic_extraction_transcript.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.source_intake import run_intake  # noqa: E402
from tools.source_intake_semantic import ModelCallBudget  # noqa: E402
from tools.business_brain import BUSINESS_BRAIN_ROOT  # noqa: E402

HISTORICAL_CALLS = BUSINESS_BRAIN_ROOT / "sources" / "historical_calls"
SLUGS = [
    "andrea-roberts-june-26", "andrea-second-call-june-30", "call-dr-kenneth-after-second-cci",
    "call-kenneth-after-first-cci", "cci-second-call-june-15", "first-call-cci",
    "hermes-water-treatment-summary-trent", "kenneth-june-30", "kenneth-meeting-may-27",
    "kenneth-sme-june-18", "meeting-ken-stanick", "mike-knapp-gtm-context-july-22",
    "mike-knapp-july-21", "trent-first-call", "trent-july-9",
]


# Restart-safety (2026-09-09): the first backfill process died mid-run --
# monitor plus process both gone, confirmed via `ps` -- after 2 real model calls
# had already been spent (usage files below), only one of which (slug 1) landed
# a card; the other (slug 2) was a wasted/orphaned call with no card ever
# written. ModelCallBudget only lives in-process, so a fresh process restarts
# it at 0/30 unless seeded here -- these two entries make the 30-call cap
# restart-safe: this run begins accounting from 2/30 already spent, not 0/30.
PRIOR_PROCESS_CALLS = [
    {
        "index": 1, "source_id": "andrea-roberts-june-26", "prior_process": True,
        "note": "landed a card + claim record, committed to the vault (3485a54)",
        "usage_file": "queue/context_assemblies/source-intake-semantic-andrea-roberts-june-26-8dfaefe0ea4a.usage.json",
    },
    {
        "index": 2, "source_id": "andrea-second-call-june-30", "prior_process": True,
        "note": "model call completed but the write never landed (no card, no claim) before the process died -- orphaned/wasted call",
        "usage_file": "queue/context_assemblies/source-intake-semantic-andrea-second-call-june-30-a2d774c38a91.usage.json",
    },
]


def main() -> int:
    assert len(SLUGS) == 15
    budget = ModelCallBudget(maximum=30)
    budget.calls.extend(PRIOR_PROCESS_CALLS)
    assert budget.count == 2, "restart seed must land the budget at 2/30 before the loop starts"
    results = []
    for slug in SLUGS:
        source_path = HISTORICAL_CALLS / f"{slug}.md"
        print(f"=== {slug} === (budget so far: {budget.count}/{budget.maximum})", flush=True)
        try:
            result = run_intake(source_path, mode="semantic", commit=True, semantic_budget=budget)
            row = {
                "slug": slug, "status": result.status, "model_invocations": result.model_invocations,
                "imported": result.imported, "duplicates": result.duplicates,
                "imported_pointers": list(result.imported_pointers), "brain_commit": result.brain_commit,
            }
            print(f"    {result.compact()}", flush=True)
        except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
            row = {"slug": slug, "status": "error", "error": f"{type(exc).__name__}: {exc}"}
            print(f"    ERROR: {type(exc).__name__}: {exc}", flush=True)
        results.append(row)

    print(f"\nBudget used: {budget.count} of {budget.maximum}", flush=True)
    out_path = ROOT / "scripts" / "i1_semantic_backfill_results.json"
    out_path.write_text(json.dumps({
        "budget_used": budget.count, "budget_maximum": budget.maximum,
        "calls": budget.calls, "results": results,
    }, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}", flush=True)
    errors = [row for row in results if row["status"] == "error"]
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
