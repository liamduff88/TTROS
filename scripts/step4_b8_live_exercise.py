"""Step 4 -- B8 live exercise. Budget-enforced David calls.

Declared maximum: 3 live provider calls, via `hermes -p david -z ...`.
  Call 1: D-STALENESS live confirmation (ask David to state the sentinel
          written into .hermes.md).
  Call 2: B8 cache exercise leg A -- cache write / cache miss.
  Call 3: B8 cache exercise leg B -- cache read / cache hit (same large
          shared prefix as call 2).

The budget is enforced IN THIS SCRIPT, not by the `Bash(hermes *)` ask rule
(which does not see subprocess calls). Hard-stops at MAX_CALLS and exits
nonzero rather than exceeding it. Writes the actual count against the
declared maximum into the transcript.

Tees a .txt transcript beside itself; refuses to overwrite without
--overwrite.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

MAX_CALLS = 3
TRANSCRIPT = Path(__file__).with_suffix(".txt")
REPO_ROOT = "/home/liam/agentic-os-live"
SENTINEL = "TTROS-DSTALE-SENTINEL-1788744467-a803ee62"

# Large, byte-identical-between-calls filler to sit ahead of the differing
# tail so the two cache-exercise calls share a long common prefix beyond
# whatever the stable system prompt already provides.
SHARED_PREFIX = (
    "Reference material for this turn (ignore unless asked): " + ("lorem ipsum ttros b8 cache probe filler token block. " * 220)
)

call_count = 0


def run_call(label: str, prompt: str, usage_path: Path) -> dict:
    global call_count
    call_count += 1
    if call_count > MAX_CALLS:
        raise RuntimeError(
            f"BUDGET EXCEEDED: attempted call #{call_count} against declared max {MAX_CALLS}"
        )
    t0 = time.time()
    proc = subprocess.run(
        [
            "hermes", "-p", "david", "-z", prompt,
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
        except Exception as exc:
            usage = {"_parse_error": repr(exc)}
    return {
        "label": label,
        "call_index": call_count,
        "wall_clock_seconds": round(wall, 3),
        "stdout": proc.stdout.strip(),
        "returncode": proc.returncode,
        "usage_file": usage,
    }


def main() -> int:
    if TRANSCRIPT.exists() and "--overwrite" not in sys.argv:
        print(f"refusing to overwrite existing transcript: {TRANSCRIPT}", file=sys.stderr)
        return 1

    out_lines = []

    def log(s: str) -> None:
        print(s)
        out_lines.append(s)

    log("=== Step 4 B8 live exercise ===")
    log(f"DECLARED MAXIMUM: {MAX_CALLS} David calls.")

    results = []

    # Call 1 -- D-STALENESS live confirmation.
    r1 = run_call(
        "D-STALENESS live ask",
        "Read .hermes.md in the current directory and reply with ONLY the sentinel value it names, nothing else.",
        Path("/tmp/step4_usage_call1.json"),
    )
    results.append(r1)
    log(f"[call 1] D-STALENESS ask -> stdout: {r1['stdout']!r}")
    log(f"[call 1] sentinel present in reply: {SENTINEL in r1['stdout']}")

    # Call 2 -- cache exercise leg A (miss expected).
    r2 = run_call(
        "cache exercise leg A (miss)",
        SHARED_PREFIX + "\n\nQuestion A: reply with just the single word ALPHA.",
        Path("/tmp/step4_usage_call2.json"),
    )
    results.append(r2)
    log(f"[call 2] leg A stdout: {r2['stdout']!r}")

    # Call 3 -- cache exercise leg B (hit expected), immediately after.
    r3 = run_call(
        "cache exercise leg B (hit)",
        SHARED_PREFIX + "\n\nQuestion B: reply with just the single word BETA.",
        Path("/tmp/step4_usage_call3.json"),
    )
    results.append(r3)
    log(f"[call 3] leg B stdout: {r3['stdout']!r}")

    log("")
    log(f"ACTUAL CALL COUNT: {call_count} against declared maximum {MAX_CALLS}.")

    for r in results:
        u = r["usage_file"]
        log(
            f"[{r['label']}] wall={r['wall_clock_seconds']}s "
            f"usage_file={json.dumps(u)}"
        )

    Path("/tmp/step4_live_exercise_results.json").write_text(json.dumps(results, indent=2))
    TRANSCRIPT.write_text("\n".join(out_lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
