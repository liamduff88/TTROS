#!/usr/bin/env python3
"""STEP T7 Part B -- zero-model fixture proof for the David test-turn write gate.

Calls hooks/context_assembler_hook.py::evaluate() directly (the same function Hermes's
post_llm_call hook invokes), mocking write_thread/append_session_turn so no vault write
actually happens. Proves BOTH directions on the same topic/profile:
  1. A turn marked TTROS_DAVID_TEST_TURN=1 does NOT call write_thread or append_session_turn.
  2. An otherwise-identical unmarked turn (real session, same topic) DOES call both --
     the gate suppresses only marked turns, not journalling in general.

A detector that can only print PASS proves nothing (rules/evidence discipline), hence both
directions are asserted, not just the marked case.

Tees a .txt transcript beside itself; refuses to overwrite without --overwrite.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path("/home/liam/agentic-os-live")
sys.path.insert(0, str(REPO_ROOT))

from hooks import context_assembler_hook  # noqa: E402

TRANSCRIPT = Path(__file__).with_suffix(".txt")

PAYLOAD = {
    "hook_event_name": "post_llm_call",
    "native_plugin": True,
    "session_id": "steptt7-fixture",
    "extra": {
        "platform": "cli",
        "user_message": "What happened in my meeting with Fred, and what did he say about MLS?",
        "assistant_response": (
            "Fred forwarded the SnapStats sheet and is waiting on GVR for data access.\n"
            "<<<TTROS_THREAD\n"
            "Current thread: Fred meeting follow-up.\n"
            "TTROS_THREAD>>>"
        ),
    },
}


def run_case(label: str, *, marked: bool, out_lines: list[str]) -> bool:
    env = dict(os.environ)
    env["HERMES_HOME"] = "/isolated/profiles/david"
    if marked:
        env[context_assembler_hook.DAVID_TEST_TURN_ENV_SENTINEL] = "1"
    else:
        env.pop(context_assembler_hook.DAVID_TEST_TURN_ENV_SENTINEL, None)
    with mock.patch.dict(os.environ, env, clear=True), \
         mock.patch.object(context_assembler_hook, "write_thread") as wt, \
         mock.patch.object(context_assembler_hook, "append_session_turn") as ast_:
        context_assembler_hook.evaluate(PAYLOAD)
    wrote_thread = wt.called
    wrote_journal = ast_.called
    out_lines.append(
        f"[{label}] marked={marked} write_thread.called={wrote_thread} "
        f"append_session_turn.called={wrote_journal}"
    )
    if marked:
        return (not wrote_thread) and (not wrote_journal)
    return wrote_thread and wrote_journal


def main() -> int:
    if TRANSCRIPT.exists() and "--overwrite" not in sys.argv:
        print(f"refusing to overwrite existing transcript: {TRANSCRIPT}", file=sys.stderr)
        return 1

    out_lines: list[str] = ["=== STEP T7 Part B -- test-turn write-gate fixture proof ==="]

    marked_ok = run_case("marked test turn", marked=True, out_lines=out_lines)
    unmarked_ok = run_case("unmarked real turn (same topic)", marked=False, out_lines=out_lines)

    overall = marked_ok and unmarked_ok
    out_lines.append("")
    out_lines.append(f"marked-turn-excluded assertion: {'PASS' if marked_ok else 'FAIL'}")
    out_lines.append(f"unmarked-turn-still-journalled assertion: {'PASS' if unmarked_ok else 'FAIL'}")
    out_lines.append(f"OVERALL: {'PASS' if overall else 'FAIL'}")

    for line in out_lines:
        print(line)
    TRANSCRIPT.write_text("\n".join(out_lines) + "\n")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
