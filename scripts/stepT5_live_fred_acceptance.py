"""Step T5 -- first live acceptance of T1+T3+T4. Budget-enforced David call.

Declared maximum: 1 live provider call, via `hermes -p david -z ...` (fresh session,
non-interactive). The budget is enforced IN THIS SCRIPT, not by the `Bash(hermes *)` ask rule
(which does not see subprocess calls). Hard-stops before a second call and exits nonzero rather
than exceeding it. No retry on any outcome. Writes the actual count against the declared maximum
into the transcript.

Tees a .txt transcript beside itself; refuses to overwrite without --overwrite.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

MAX_CALLS = 1
TRANSCRIPT = Path(__file__).with_suffix(".txt")
REPO_ROOT = "/home/liam/agentic-os-live"
QUESTION = "What happened in my meeting with Fred, and what did he say about MLS?"
USAGE_FILE = Path("/tmp/stepT5_usage.json")

call_count = 0


def run_call(prompt: str, usage_path: Path) -> dict:
    global call_count
    call_count += 1
    if call_count > MAX_CALLS:
        raise RuntimeError(
            f"BUDGET EXCEEDED: attempted call #{call_count} against declared max {MAX_CALLS}"
        )
    t0 = time.time()
    proc = subprocess.run(
        ["hermes", "-p", "david", "-z", prompt, "--usage-file", str(usage_path)],
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
        "call_index": call_count,
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

    log("=== Step T5 live Fred/MLS acceptance ===")
    log(f"DECLARED MAXIMUM: {MAX_CALLS} David call(s), fresh CLI-David session.")
    log(f"cwd for the call: {REPO_ROOT}")
    log(f"question (verbatim from stepT1 line 589): {QUESTION!r}")

    r1 = run_call(QUESTION, USAGE_FILE)

    log("")
    log(f"ACTUAL CALL COUNT: {call_count} against declared maximum {MAX_CALLS}.")
    log(f"model calls: {call_count} / declared max {MAX_CALLS}")
    log(f"returncode: {r1['returncode']}")
    log(f"wall_clock_seconds: {r1['wall_clock_seconds']}")
    log(f"stdout (answer text): {r1['stdout']!r}")
    if r1["stderr"]:
        log(f"stderr: {r1['stderr']!r}")
    log(f"usage_file: {json.dumps(r1['usage_file'], indent=2)}")

    Path("/tmp/stepT5_live_exercise_result.json").write_text(json.dumps(r1, indent=2))
    TRANSCRIPT.write_text("\n".join(out_lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
