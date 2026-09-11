"""Step T6 Part D -- live proof, two turns max, David only.

Declared maximum: 2 CLI invocations (`hermes -p david -z ... --max-turns 6`), fresh sessions.
The budget is enforced IN THIS SCRIPT: hard-stops before a 3rd call, no retry on any outcome, and
hard-stops before turn 2 if turn 1's own `api_calls` (from --usage-file) exceeds 6 -- a genuine
per-invocation provider-request ceiling, established in Part A5 (--max-turns), that does not touch
the live profile's agent.max_turns: 150.

Tees a .txt transcript beside itself; refuses to overwrite without --overwrite.
"""

from __future__ import annotations

import json
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
    t0 = time.time()
    proc = subprocess.run(
        [
            "hermes", "-p", "david", "-z", prompt,
            "--max-turns", "6",
            "--usage-file", str(usage_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
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

    log("=== Step T6 Part D -- live over-retrieval repair proof ===")
    log(f"DECLARED MAXIMUM: {MAX_INVOCATIONS} CLI invocation(s), fresh sessions.")
    log(f"Per-invocation provider-request ceiling: --max-turns 6 (A5 finding).")
    log(f"Hard-stop rule: if turn 1's api_calls > {PER_TURN_API_CALL_CEILING}, do not run turn 2.")

    r1 = run_call("D1 Fred/MLS (verbatim)", D1_QUESTION, Path("/tmp/stepT6_usage_d1.json"))
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
        Path("/tmp/stepT6_live_results.json").write_text(json.dumps([r1], indent=2))
        TRANSCRIPT.write_text("\n".join(out_lines) + "\n")
        return 0

    r2 = run_call("D2 over-suppression control", D2_QUESTION, Path("/tmp/stepT6_usage_d2.json"))
    log("")
    log(f"[D2] invocation {r2['invocation_index']}, returncode {r2['returncode']}, "
        f"wall {r2['wall_clock_seconds']}s")
    log(f"[D2] usage_file: {json.dumps(r2['usage_file'], indent=2)}")
    log(f"[D2] answer: {r2['stdout']!r}")

    log("")
    log(f"invocations made: {invocation_count} / declared max {MAX_INVOCATIONS}")

    Path("/tmp/stepT6_live_results.json").write_text(json.dumps([r1, r2], indent=2))
    TRANSCRIPT.write_text("\n".join(out_lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
