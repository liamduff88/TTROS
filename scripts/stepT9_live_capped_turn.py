#!/usr/bin/env python3
"""STEP T9 -- one capped live David turn, parameterised.

Reuses scripts/stepT8BCD_live_capped_passage_turn.py's shape (invocation, budget,
sentinel and session-lookup logic) with --max-turns, --label and --tool-describe-ceiling
made into parameters, per T9 Part 0b / Part C's instruction to reuse rather than write a
new instrument.

Invocation shape: `HERMES_HOME=<david profile> hermes chat -q QUESTION --oneshot
--max-turns N`, TTROS_DAVID_TEST_TURN=1 in the child env. Hard caps enforced by THIS
instrument:
  - exactly ONE invocation attempt (hard error on any second call)
  - 180s wall-clock kill
  - --max-turns N passed to Hermes itself as a spend guard

Tees scripts/stepT9_live_capped_turn_<label>.txt beside itself; refuses to overwrite
without --overwrite.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path("/home/liam/agentic-os-live")
STATE_DB = Path("/home/liam/.hermes/profiles/david/state.db")
HERMES_HOME = "/home/liam/.hermes/profiles/david"
VAULT_SENTINEL = Path(
    "/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain/"
    "sessions/2026-09-10_hermes-cli_7cd4569d6fe3.md"
)
THREAD_SENTINEL = Path(
    "/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain/"
    "sessions/thread_david.md"
)
QUESTION = "In my meeting with Fred, what were his exact words about how many GVR boards there are?"
WALL_CLOCK_KILL_SECONDS = 180

lines: list[str] = []


def log(msg: str) -> None:
    print(msg)
    lines.append(msg)


class InvocationBudget:
    def __init__(self, maximum: int = 1) -> None:
        self.maximum = maximum
        self.count = 0

    def take(self) -> None:
        if self.count >= self.maximum:
            raise RuntimeError(
                f"model-call budget exceeded: attempted invocation {self.count + 1} "
                f"but the declared maximum is {self.maximum}"
            )
        self.count += 1


def file_sentinel(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    data = path.read_bytes()
    return {
        "exists": True,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "mtime": path.stat().st_mtime,
    }


def query_new_session(after_epoch: float) -> dict | None:
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, started_at, api_call_count, tool_call_count, title, model_config "
        "FROM sessions WHERE started_at > ? ORDER BY started_at ASC",
        (after_epoch,),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    if len(rows) > 1:
        log(f"WARNING: {len(rows)} new sessions appeared after launch time, expected 1. "
            f"Using the earliest: {[r['id'] for r in rows]}")
    return dict(rows[0])


def fetch_messages(session_id: str) -> list[dict]:
    conn = sqlite3.connect(str(STATE_DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content, tool_call_id, tool_calls, tool_name, timestamp "
        "FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-turns", type=int, required=True)
    ap.add_argument("--label", required=True, help="suffix for the transcript filename")
    ap.add_argument("--api-call-ceiling", type=int, default=None,
                     help="if set, criterion checked against session api_call_count")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    transcript = REPO_ROOT / "scripts" / f"stepT9_live_capped_turn_{args.label}.txt"
    if transcript.exists() and not args.overwrite:
        print(f"refusing to overwrite existing transcript: {transcript}", file=sys.stderr)
        return 2

    budget = InvocationBudget(maximum=1)

    log("=" * 78)
    log(f"STEP T9 -- one capped live David turn (label={args.label})")
    log("=" * 78)
    log(f"Question (verbatim): {QUESTION!r}")
    log(f"Invocation shape: hermes chat -q QUESTION --oneshot --max-turns {args.max_turns}")
    log(f"HERMES_HOME={HERMES_HOME}  TTROS_DAVID_TEST_TURN=1")
    log(f"Wall-clock kill: {WALL_CLOCK_KILL_SECONDS}s. Invocation budget: 1 (hard error beyond).")
    if args.api_call_ceiling is not None:
        log(f"api_call_count ceiling for this run: {args.api_call_ceiling}")

    log("\n--- PRE-CALL VAULT SENTINELS ---")
    sentinel_before = file_sentinel(VAULT_SENTINEL)
    thread_before = file_sentinel(THREAD_SENTINEL)
    log(f"session journal sentinel BEFORE: {sentinel_before}")
    log(f"thread sentinel BEFORE: {thread_before}")

    env = dict(os.environ)
    env["HERMES_HOME"] = HERMES_HOME
    env["TTROS_DAVID_TEST_TURN"] = "1"

    argv = ["hermes", "chat", "-q", QUESTION, "--oneshot", "--max-turns", str(args.max_turns)]
    log(f"\n--- LIVE CALL ---\nargv: {argv}")

    budget.take()
    launch_epoch = time.time()
    log(f"launch_epoch: {launch_epoch}")
    timed_out = False
    try:
        proc = subprocess.run(
            argv, env=env, cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=WALL_CLOCK_KILL_SECONDS,
        )
        returncode = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = None
        stdout = (exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = (exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    elapsed = time.time() - launch_epoch
    log(f"elapsed: {elapsed:.1f}s  timed_out={timed_out}  returncode={returncode}")
    log(f"stdout (first 2000 chars):\n{stdout[:2000]}")
    if stderr.strip():
        log(f"stderr (first 2000 chars):\n{stderr[:2000]}")

    log(f"\nModel invocations made this run: {budget.count} (declared max: {budget.maximum})")

    log("\n--- POST-CALL VAULT SENTINELS ---")
    sentinel_after = file_sentinel(VAULT_SENTINEL)
    thread_after = file_sentinel(THREAD_SENTINEL)
    log(f"session journal sentinel AFTER: {sentinel_after}")
    log(f"thread sentinel AFTER: {thread_after}")
    vault_unchanged = (sentinel_before == sentinel_after) and (thread_before == thread_after)
    log(f"vault unchanged: {vault_unchanged}")

    log("\n--- SESSION LOOKUP ---")
    session = query_new_session(launch_epoch - 1)
    if session is None:
        log("FAIL: no new session found in state.db after launch time.")
        transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1
    log(f"session: id={session['id']} title={session['title']!r} "
        f"started_at={session['started_at']} api_call_count={session['api_call_count']} "
        f"tool_call_count={session['tool_call_count']}")
    model_config = json.loads(session["model_config"] or "{}")
    log(f"model_config.max_iterations recorded: {model_config.get('max_iterations')}")

    messages = fetch_messages(session["id"])
    log(f"\n--- MESSAGE TRACE ({len(messages)} rows) ---")
    tool_sequence = []
    final_answer = ""
    for m in messages:
        role = m["role"]
        content = m.get("content") or ""
        tool_name = m.get("tool_name")
        if role == "tool":
            tool_sequence.append(tool_name)
            snippet = content[:300].replace("\n", " ")
            log(f"  [tool:{tool_name}] {snippet}")
        elif role == "assistant" and content:
            final_answer = content
            log(f"  [assistant] {content[:500]}")
        elif role == "user":
            log(f"  [user] {content[:200]}")

    log(f"\ntool call sequence: {tool_sequence}")
    tool_describe_count = tool_sequence.count("tool_describe")
    log(f"tool_describe calls this turn: {tool_describe_count}")

    api_calls = session["api_call_count"]
    if args.api_call_ceiling is not None:
        log(f"\napi_calls <= {args.api_call_ceiling}: "
            f"{'PASS' if api_calls <= args.api_call_ceiling else 'FAIL'} (actual: {api_calls})")

    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\ntranscript written: {transcript}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
