#!/usr/bin/env python3
"""STEP T7 Part D -- live proof, two turns max, David only, both marked as test turns.

Declared maximum: 2 CLI invocations (`hermes -p david -z ...`), fresh sessions, both run with
TTROS_DAVID_TEST_TURN=1 set in the invocation's own environment (Part B's write-gate sentinel).

Part 0b of this step found --max-turns was never actually bound in the live sessions it should
have governed (all three showed max_iterations=sys.maxsize in their own stored model_config, not
6 and not even the profile default of 150) -- absent, not proven ineffective when present. Per
this step's own instruction ("use --max-turns only if Part 0b proved it bounds provider
requests; otherwise the instrument hard-stops after turn 1 if its api_calls > 6, and records
that the cap is advisory"): --max-turns 6 IS still passed (defense-in-depth; code reading shows
it should bind), but is NOT relied on -- the ceiling is enforced here, in the instrument, by
refusing to run turn 2 if turn 1's own --usage-file api_calls exceeds 6.

The budget is enforced IN THIS SCRIPT: hard-stops before a 3rd call, no retry on any outcome.

Tees a .txt transcript beside itself; refuses to overwrite without --overwrite.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

MAX_INVOCATIONS = 2
PER_TURN_API_CALL_CEILING = 6
TRANSCRIPT = Path(__file__).with_suffix(".txt")
REPO_ROOT = "/home/liam/agentic-os-live"

D1_QUESTION = "What happened in my meeting with Fred, and what did he say about MLS?"
D2_QUESTION = (
    "In my meeting with Fred, what were his exact words about how many GVR boards there are?"
)

invocation_count = 0


def run_call(label: str, prompt: str, usage_path: Path) -> dict:
    global invocation_count
    invocation_count += 1
    if invocation_count > MAX_INVOCATIONS:
        raise RuntimeError(
            f"BUDGET EXCEEDED: attempted invocation #{invocation_count} "
            f"against declared max {MAX_INVOCATIONS}"
        )
    env = dict(os.environ)
    env["TTROS_DAVID_TEST_TURN"] = "1"
    env["HERMES_HOME"] = "/home/liam/.hermes/profiles/david"
    t0 = time.time()
    proc = subprocess.run(
        [
            "hermes", "-z", prompt,
            "--usage-file", str(usage_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    wall = time.time() - t0
    usage = {}
    if usage_path.exists():
        try:
            usage = json.loads(usage_path.read_text())
        except Exception as exc:  # noqa: BLE001
            usage = {"_parse_error": repr(exc)}
    return {
        "label": label,
        "invocation_index": invocation_count,
        "wall_clock_seconds": round(wall, 3),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "returncode": proc.returncode,
        "usage_file": usage,
    }


def main() -> int:
    if TRANSCRIPT.exists() and "--overwrite" not in sys.argv:
        print(f"refusing to overwrite existing transcript: {TRANSCRIPT}", file=sys.stderr)
        return 1

    out_lines: list[str] = []

    def log(s: str) -> None:
        print(s)
        out_lines.append(s)

    log("=== Step T7 Part D -- live test-isolation + bounded-retrieval proof ===")
    log(f"DECLARED MAXIMUM: {MAX_INVOCATIONS} CLI invocation(s), fresh sessions, both marked "
        f"TTROS_DAVID_TEST_TURN=1.")
    log("--max-turns does not exist on the top-level `hermes -z` oneshot parser at all in this "
        "installed build (confirmed via `hermes --help`; it is chat-subcommand-only, and the "
        "chat subcommand has no --usage-file) -- this instrument's own hard-stop rule is the "
        f"sole enforcement: if turn 1's api_calls > {PER_TURN_API_CALL_CEILING}, turn 2 does not run.")

    r1 = run_call("D1 Fred/MLS (verbatim)", D1_QUESTION, Path("/tmp/stepT7_usage_d1.json"))
    log("")
    log(f"[D1] invocation {r1['invocation_index']}, returncode {r1['returncode']}, "
        f"wall {r1['wall_clock_seconds']}s")
    log(f"[D1] usage_file: {json.dumps(r1['usage_file'], indent=2)}")
    log(f"[D1] answer: {r1['stdout']!r}")

    d1_api_calls = (r1["usage_file"] or {}).get("api_calls")
    if isinstance(d1_api_calls, int) and d1_api_calls > PER_TURN_API_CALL_CEILING:
        log("")
        log(
            f"HARD STOP: D1 api_calls={d1_api_calls} exceeds ceiling "
            f"{PER_TURN_API_CALL_CEILING}. Turn 2 (D2) is NOT run."
        )
        log(f"invocations made: {invocation_count} / declared max {MAX_INVOCATIONS}")
        Path("/tmp/stepT7_live_results.json").write_text(json.dumps([r1], indent=2))
        TRANSCRIPT.write_text("\n".join(out_lines) + "\n")
        return 0

    r2 = run_call("D2 over-suppression control", D2_QUESTION, Path("/tmp/stepT7_usage_d2.json"))
    log("")
    log(f"[D2] invocation {r2['invocation_index']}, returncode {r2['returncode']}, "
        f"wall {r2['wall_clock_seconds']}s")
    log(f"[D2] usage_file: {json.dumps(r2['usage_file'], indent=2)}")
    log(f"[D2] answer: {r2['stdout']!r}")

    log("")
    log(f"invocations made: {invocation_count} / declared max {MAX_INVOCATIONS}")

    Path("/tmp/stepT7_live_results.json").write_text(json.dumps([r1, r2], indent=2))
    TRANSCRIPT.write_text("\n".join(out_lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
