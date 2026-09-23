"""Step L1 -- Phase C. EXACTLY ONE live David turn on the Dashboard route.

Declared maximum: 1 live provider call, via the real Dashboard-route function
`dashboard/backend/main.py:_execute_named_profile_consultation("David", "david", ...)`.
This is the exact function the running `/api/...` Dashboard endpoint calls (main.py
imports it and invokes it identically); it is called directly, in-process, instead of
over HTTP against the live `aos-backend.service`, specifically so this diagnostic does
not need to restart the shared systemd service (out of this step's stated
WORK ONLY IN /home/liam/agentic-os-live scope) to inject the temporary
TTROS_STEPL1_TIMING=1 timing-instrumentation env var. Every function on the call path
(`assemble_model_context`, `_run_hermes_message`, `tools/aos-hermes-coordinator.sh`,
`hermes`, `hooks/context_assembler_hook.py`) is the literal, unmodified-in-substance
Dashboard David route -- only additive timing marks were inserted (Phase B2), gated on
this same env var, in main.py, the coordinator script, and the hook.

The budget is enforced IN THIS SCRIPT: it makes exactly one call and hard-stops before a
second could ever be attempted. Tees a .txt transcript beside itself; refuses to
overwrite without --overwrite.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

TRANSCRIPT = Path(__file__).with_suffix(".txt")
MAX_CALLS = 1

if TRANSCRIPT.exists() and "--overwrite" not in sys.argv:
    print(f"refusing to overwrite existing transcript: {TRANSCRIPT}", file=sys.stderr)
    raise SystemExit(1)

os.environ["TTROS_STEPL1_TIMING"] = "1"

DASHBOARD_DIR = Path("/home/liam/agentic-os-live/dashboard")
os.chdir(DASHBOARD_DIR)
sys.path.insert(0, str(DASHBOARD_DIR))

call_count = 0
lines: list[str] = []


def log(line: str) -> None:
    print(line)
    lines.append(line)


def main() -> int:
    global call_count
    log("=== Step L1 Phase C: exactly one live Dashboard-David turn ===")
    log(f"DECLARED MAXIMUM: {MAX_CALLS} live provider call.")

    import backend.main as dashboard_backend  # the real Dashboard route module

    request_id = f"stepL1-{uuid.uuid4().hex[:12]}"
    prompt_text = "Reply with one word: stored"

    call_count += 1
    if call_count > MAX_CALLS:
        raise RuntimeError(f"BUDGET EXCEEDED: attempted call #{call_count} against declared max {MAX_CALLS}")

    t_wall_start = time.monotonic()
    result = dashboard_backend._execute_named_profile_consultation("David", "david", prompt_text, request_id)
    t_wall_end = time.monotonic()

    log(f"ACTUAL CALL COUNT: {call_count} against declared maximum {MAX_CALLS}.")
    log(f"end-to-end wall clock (this process, function-call boundary): {round(t_wall_end - t_wall_start, 3)}s")
    log(f"request_id: {request_id}")
    log(f"result: {json.dumps(result, ensure_ascii=False, default=str)}")

    return 0


if __name__ == "__main__":
    rc = main()
    TRANSCRIPT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    raise SystemExit(rc)
