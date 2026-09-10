#!/usr/bin/env python3
"""STEP I2 Part A step 6 -- depth/precision follow-up, continued from the
existing 12-call budget already at 2/12 (1 semantic extraction + 1 David
retrieval turn from the earlier session; see
scripts/i2_source_intake_production_path_transcript.md).

Declared maximum for THIS script: 1 additional live David call (bringing the
running total to 3 of 12). Hard-stops and exits nonzero rather than
exceeding it. Real, unmocked `hermes -p david -z ...` call -- the same
CLI-David surface already used for the first retrieval call.

Question is a depth/precision follow-up that requires a specific fact
present only in the verbatim original transcript
(sources/intake/records/<sha256>.md), not in the compact source card (which
is bounded to ~3000 B and elides/paraphrases most detail -- confirmed by
reading the real card before writing this prompt: it has no mention of a
board count or named cities). If David cannot answer without the original,
a correct answer here is evidence the retrieval path actually reaches the
original, not just the card.

Tees a .txt transcript beside itself; refuses to overwrite without
--overwrite.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

CALLS_ALREADY_USED = 2
MAX_TOTAL_BUDGET = 12
MAX_CALLS_THIS_SCRIPT = 1
TRANSCRIPT = Path(__file__).with_suffix(".txt")
REPO_ROOT = "/home/liam/agentic-os-live"

PROMPT = (
    "In the Fred Haiderzada real-estate transcript you have on file (the "
    "sept 9th meeting about realtor workflow tracking and MLS/GVR market "
    "reporting), Fred gives a specific number of realty boards under GVR "
    "and names specific cities covered by the Fraser Valley board. What "
    "number does he give, and which cities does he name? Quote his exact "
    "words if you can."
)

call_count = 0


def run_call(label: str, prompt: str, usage_path: Path) -> dict:
    global call_count
    call_count += 1
    if CALLS_ALREADY_USED + call_count > MAX_TOTAL_BUDGET:
        raise RuntimeError(
            f"BUDGET EXCEEDED: attempted call {CALLS_ALREADY_USED + call_count} "
            f"against declared max {MAX_TOTAL_BUDGET}"
        )
    if call_count > MAX_CALLS_THIS_SCRIPT:
        raise RuntimeError(
            f"BUDGET EXCEEDED: this script's own declared max is {MAX_CALLS_THIS_SCRIPT} call(s)"
        )
    t0 = time.time()
    proc = subprocess.run(
        ["hermes", "-p", "david", "-z", prompt, "--usage-file", str(usage_path)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=180,
    )
    wall = time.time() - t0
    usage = {}
    if usage_path.exists():
        try:
            usage = json.loads(usage_path.read_text())
        except Exception as exc:
            usage = {"_parse_error": repr(exc)}
    return {
        "label": label, "call_index_this_script": call_count,
        "running_total_of_12": CALLS_ALREADY_USED + call_count,
        "wall_clock_seconds": round(wall, 3), "stdout": proc.stdout.strip(),
        "returncode": proc.returncode, "usage_file": usage,
    }


def main() -> int:
    if TRANSCRIPT.exists() and "--overwrite" not in sys.argv:
        print(f"refusing to overwrite existing transcript: {TRANSCRIPT}", file=sys.stderr)
        return 1

    out_lines: list[str] = []

    def log(s: str) -> None:
        print(s)
        out_lines.append(s)

    log("=== STEP I2 Part A step 6 -- depth/precision follow-up ===")
    log(f"Calls already used before this script: {CALLS_ALREADY_USED} of {MAX_TOTAL_BUDGET}")
    log(f"DECLARED MAXIMUM for this script: {MAX_CALLS_THIS_SCRIPT} call(s).")
    log("")
    log("PREDICTION (written before running): the compact source card does not")
    log("contain a GVR board count or Fraser Valley city names -- confirmed by")
    log("reading the real card before this call. A correct, specific answer")
    log("(a number close to '11 boards', and city names such as Langley, Surrey,")
    log("Abbotsford) can only come from David actually reading the verbatim")
    log("original (sources/intake/records/<sha256>.md) during this turn, not")
    log("from the card alone. Expect a fresh hermes-*.json context assembly and")
    log("a citation of the original record pointer.")
    log("")

    usage_path = Path("/tmp/i2_step6_depth_followup_david.usage.json")
    usage_path.unlink(missing_ok=True)
    result = run_call("depth/precision follow-up", PROMPT, usage_path)

    log(f"Call {result['running_total_of_12']} of {MAX_TOTAL_BUDGET} (this script's call "
        f"{result['call_index_this_script']} of {MAX_CALLS_THIS_SCRIPT}):")
    log(f"  wall clock: {result['wall_clock_seconds']}s, returncode: {result['returncode']}")
    log(f"  usage file: {usage_path}")
    log(f"  usage contents: {json.dumps(result['usage_file'])}")
    log("")
    log("David's real answer:")
    log(result["stdout"])
    log("")
    log(f"CALLS USED THIS SCRIPT: {call_count} of {MAX_CALLS_THIS_SCRIPT} declared.")
    log(f"RUNNING TOTAL: {CALLS_ALREADY_USED + call_count} of {MAX_TOTAL_BUDGET} declared.")

    TRANSCRIPT.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"\nWrote {TRANSCRIPT}")
    return 0 if result["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
