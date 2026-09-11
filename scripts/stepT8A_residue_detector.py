#!/usr/bin/env python3
"""STEP T8-A bounded, read-only residue detector.

Runs the same three checks before and after the T8-A deletion of the five
contaminating turns from sessions/2026-09-10_hermes-cli_7cd4569d6fe3.md, using
the same functions David's live path uses:

  - residue probes: brain_memory_mcp.search_history() for a unique 6+ word
    phrase from each of the five turns.
  - positive control: brain_memory_mcp.search_history("like, I think 11").
  - recency: tools.context_assembler.assemble() for the T5/T6-D1 Fred question
    verbatim, and for a rephrased GVR-boards question.

Zero model calls. Read-only: makes no vault write, no index write (beyond
whatever the already-published os_index.db state is), no code change.

Tees a transcript beside itself and refuses to overwrite without --overwrite.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRATCH_MCP_STUB = Path(
    "/tmp/claude-1002/-home-liam-agentic-os-live/5eb3819c-4221-4516-98c1-c4b1d86c60f3/scratchpad/mcp_stub"
)
sys.path.insert(0, str(SCRATCH_MCP_STUB))
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT))

import brain_memory_mcp as bmm  # noqa: E402
import context_assembler as ca  # noqa: E402

TARGET_RELATIVE = "sessions/2026-09-10_hermes-cli_7cd4569d6fe3.md"
FRED_SOURCE_POINTER = (
    "business_brain:sources/intake/records/"
    "d9cb4668fd766474278e414bb53223f944342004f34be23020c161fa4160dd74.md"
)

RESIDUE_PROBES = [
    ("2026-09-10T00:15:18.194177Z", "ask Fred for the SnapStats sheet plus one anonymized example"),
    ("2026-09-10T00:52:29.283079Z", "What number does he give, and which cities does he name"),
    ("2026-09-10T22:54:12.282800Z", "Bottom line: do not build the MLS product first"),
    ("2026-09-10T23:43:14.377494Z", "the assembled context here does not include the full quote"),
    ("2026-09-10T23:44:01.549610Z", "what is the exact name of the MLS platform Fred said he uses"),
]

POSITIVE_CONTROL_QUERY = "like, I think 11"

RECENCY_QUERY_I = "What happened in my meeting with Fred, and what did he say about MLS?"
RECENCY_QUERY_II = (
    "In my meeting with Fred, what were his exact words about how many GVR boards there are?"
)

FIVE_TIMESTAMPS = {ts for ts, _ in RESIDUE_PROBES}

TURN_HEADER_RE = re.compile(r"### Turn · ([0-9T:.Z-]+)")
SESSIONS_POINTER_RE = re.compile(r"business_brain:(sessions/[^\s#]+)")


def run_residue_probes() -> list[dict]:
    results = []
    for ts, phrase in RESIDUE_PROBES:
        r = bmm.search_history(phrase, limit=20)
        pointers = [m["pointer"] for m in r.get("matches", [])] if r.get("success") else []
        hit = any(TARGET_RELATIVE in p for p in pointers)
        rank = next((i + 1 for i, p in enumerate(pointers) if TARGET_RELATIVE in p), None)
        results.append({
            "turn_timestamp": ts,
            "phrase": phrase,
            "success": r.get("success"),
            "found": hit,
            "rank": rank,
            "all_pointers": pointers,
        })
    return results


def run_positive_control() -> dict:
    r = bmm.search_history(POSITIVE_CONTROL_QUERY, limit=20)
    pointers = [m["pointer"] for m in r.get("matches", [])] if r.get("success") else []
    fred_rank = next((i + 1 for i, p in enumerate(pointers) if p == FRED_SOURCE_POINTER), None)
    sessions_hits = [p for p in pointers if p.startswith("business_brain:sessions/")]
    return {
        "success": r.get("success"),
        "fred_source_returned": fred_rank is not None,
        "fred_source_rank": fred_rank,
        "sessions_hits": sessions_hits,
        "all_pointers": pointers,
    }


def run_recency(query: str) -> dict:
    assembled = ca.assemble(
        query,
        surface="hermes-cli",
        session_id="stepT8A-detector",
        session_key="stepT8A-detector",
        client_scope="global",
        profile="",
        write_artifact=False,
    )
    block = next((b for b in assembled.blocks if b.name == "relevant session recency"), None)
    content = block.content if block else ""
    selected_turn_timestamps = TURN_HEADER_RE.findall(content)
    selected_session_files = sorted(set(SESSIONS_POINTER_RE.findall(content)))
    contaminating_selected = sorted(set(selected_turn_timestamps) & FIVE_TIMESTAMPS)
    return {
        "query": query,
        "selected_turn_timestamps": selected_turn_timestamps,
        "selected_session_files": selected_session_files,
        "contaminating_timestamps_selected": contaminating_selected,
        "contains_11_boards": "11 boards" in content,
        "block_content": content,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=["before", "after"])
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    out_path = Path(__file__).resolve().parent / f"stepT8A_residue_detector_{args.phase}.txt"
    if out_path.exists() and not args.overwrite:
        print(f"refusing to overwrite existing transcript: {out_path}", file=sys.stderr)
        return 2

    lines = []

    def emit(text: str = "") -> None:
        lines.append(text)
        print(text)

    emit(f"=== STEP T8-A residue detector — phase: {args.phase} ===")
    emit()
    if args.phase == "before":
        emit("PREDICTION (written before running, per Part B):")
        emit("  - residue probes: 5/5 found")
        emit("  - positive control: returns Fred source record AND at least one sessions/ hit")
        emit("  - recency query (ii) selects at least one of the five contaminating timestamps")
    else:
        emit("PREDICTION (written before running, per Part D):")
        emit("  - residue probes: 0/5 found")
        emit("  - positive control: still returns Fred source record; rank not worse than before")
        emit("  - no sessions/ hit contains the Fred quote")
        emit("  - recency (i) and (ii) select none of the five timestamps")
        emit("  - '11 boards' absent from (i)'s rendered context")
    emit()

    emit("--- Residue probes ---")
    probes = run_residue_probes()
    for p in probes:
        emit(f"  turn {p['turn_timestamp']}: found={p['found']} rank={p['rank']} phrase={p['phrase']!r}")
    found_count = sum(1 for p in probes if p["found"])
    emit(f"  TOTAL FOUND: {found_count}/5")
    emit()

    emit("--- Positive control: search_history('like, I think 11') ---")
    pc = run_positive_control()
    emit(f"  fred_source_returned={pc['fred_source_returned']} rank={pc['fred_source_rank']}")
    emit(f"  sessions/ hits: {pc['sessions_hits']}")
    emit()

    emit("--- Recency (i): T5/T6-D1 verbatim question ---")
    rec_i = run_recency(RECENCY_QUERY_I)
    emit(f"  selected_turn_timestamps={rec_i['selected_turn_timestamps']}")
    emit(f"  selected_session_files={rec_i['selected_session_files']}")
    emit(f"  contaminating_timestamps_selected={rec_i['contaminating_timestamps_selected']}")
    emit(f"  contains_11_boards={rec_i['contains_11_boards']}")
    emit()

    emit("--- Recency (ii): rephrased GVR-boards question ---")
    rec_ii = run_recency(RECENCY_QUERY_II)
    emit(f"  selected_turn_timestamps={rec_ii['selected_turn_timestamps']}")
    emit(f"  selected_session_files={rec_ii['selected_session_files']}")
    emit(f"  contaminating_timestamps_selected={rec_ii['contaminating_timestamps_selected']}")
    emit(f"  contains_11_boards={rec_ii['contains_11_boards']}")
    emit()

    payload = {
        "phase": args.phase,
        "residue_probes": probes,
        "positive_control": pc,
        "recency_i": {k: v for k, v in rec_i.items() if k != "block_content"},
        "recency_ii": {k: v for k, v in rec_ii.items() if k != "block_content"},
    }
    emit("--- JSON summary ---")
    emit(json.dumps(payload, indent=2))

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\ntranscript written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
