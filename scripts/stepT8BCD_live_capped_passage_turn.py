#!/usr/bin/env python3
"""STEP T8-BCD Part D -- one capped live David turn.

Invocation shape (Part B): `hermes chat -q QUESTION --oneshot --max-turns 6`
with HERMES_HOME=<david profile> and TTROS_DAVID_TEST_TURN=1 in the child
env. Hard caps enforced by THIS instrument (not relied on from Hermes alone,
per Part B's own finding that --max-turns has never been proven to bind on
any previously-used invocation shape):
  - exactly ONE invocation attempt (hard error on any second call)
  - 180s wall-clock kill
  - --max-turns 6 passed to Hermes itself as a spend guard

Tees its own transcript beside itself; refuses to overwrite without
--overwrite.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path("/home/liam/agentic-os-live")
TRANSCRIPT = Path(__file__).with_suffix(".txt")
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
HERMES_MAX_TURNS_ARG = 6
API_CALLS_CEILING = 4  # acceptance ceiling; separate from the spend-guard turn cap above
REQUIRED_QUOTE = "I think 11 boards"

lines: list[str] = []


def log(msg: str) -> None:
    print(msg)
    lines.append(msg)


class InvocationBudget:
    """Hard-stops at 1 invocation and exits with an error rather than exceeding it."""

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
    import hashlib
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
    row = rows[0]
    return dict(row)


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
    if TRANSCRIPT.exists() and "--overwrite" not in sys.argv:
        print(f"refusing to overwrite existing transcript: {TRANSCRIPT}", file=sys.stderr)
        return 2

    budget = InvocationBudget(maximum=1)

    log("=" * 78)
    log("STEP T8-BCD Part D -- one capped live David turn")
    log("=" * 78)
    log(f"Question (verbatim): {QUESTION!r}")
    log(f"Invocation shape: hermes chat -q QUESTION --oneshot --max-turns {HERMES_MAX_TURNS_ARG}")
    log(f"HERMES_HOME={HERMES_HOME}  TTROS_DAVID_TEST_TURN=1")
    log(f"Wall-clock kill: {WALL_CLOCK_KILL_SECONDS}s. Invocation budget: 1 (hard error beyond).")

    log("\n--- PRE-REGISTERED PREDICTIONS (written before the live call) ---")
    log("Offline pre-check (already run, zero model calls): assemble() for this exact question "
        "does NOT contain '11 boards' in its rendered context (confirmed fresh this step; "
        "matches T8-A's own finding) -- provenance is therefore testable.")
    log("Predicted api_calls: bimodal, both outcomes pre-registered as plausible --")
    log("  (a) IF David passes `query` to open_note on the Fred card's pointer: ~2 calls "
        "(tool_describe + one bounded open_note), no spill, no search_history guessing.")
    log("  (b) IF David omits `query` (defaults to the old full-truncated 60,000-char content, "
        "still above Hermes's 50,000-char MCP spill threshold): the old open_note-spills-then-"
        "search_history-guessing pattern likely recurs, similar to T7's D2 (8 calls) -- FAILING "
        "the api_calls<=4 ceiling. This step's docstring change can only encourage query use, "
        "not force it -- David's tool-call shape is a live model decision, not code-controlled.")
    log("Predicted tool sequence (case a): tool_describe(open_note) -> open_note(pointer, "
        "query=...) -> answer.")
    log(f"Acceptance ceiling: api_calls <= {API_CALLS_CEILING} (separate from the {HERMES_MAX_TURNS_ARG}-turn "
        "spend guard passed to Hermes itself).")
    log(f"Required quote in the answer: {REQUIRED_QUOTE!r}")

    log("\n--- PRE-CALL VAULT SENTINELS ---")
    sentinel_before = file_sentinel(VAULT_SENTINEL)
    thread_before = file_sentinel(THREAD_SENTINEL)
    log(f"session journal sentinel BEFORE: {sentinel_before}")
    log(f"thread sentinel BEFORE: {thread_before}")

    env = dict(os.environ)
    env["HERMES_HOME"] = HERMES_HOME
    env["TTROS_DAVID_TEST_TURN"] = "1"

    argv = ["hermes", "chat", "-q", QUESTION, "--oneshot", "--max-turns", str(HERMES_MAX_TURNS_ARG)]
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
        TRANSCRIPT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1
    log(f"session: id={session['id']} title={session['title']!r} "
        f"started_at={session['started_at']} api_call_count={session['api_call_count']} "
        f"tool_call_count={session['tool_call_count']}")
    model_config = json.loads(session["model_config"] or "{}")
    log(f"model_config.max_iterations recorded: {model_config.get('max_iterations')}")

    messages = fetch_messages(session["id"])
    log(f"\n--- MESSAGE TRACE ({len(messages)} rows) ---")
    tool_sequence = []
    provenance_hit = False
    final_answer = ""
    for m in messages:
        role = m["role"]
        content = m.get("content") or ""
        tool_name = m.get("tool_name")
        if role == "tool":
            tool_sequence.append(tool_name)
            snippet = content[:300].replace("\n", " ")
            log(f"  [tool:{tool_name}] {snippet}")
            if REQUIRED_QUOTE in content and "d9cb4668fd766474278e414bb53223f944342004f34be23020c161fa4160dd74" in content:
                provenance_hit = True
                log(f"    -> PROVENANCE: this tool result contains {REQUIRED_QUOTE!r} and the "
                    f"Fred record's pointer.")
        elif role == "assistant" and content:
            final_answer = content
            log(f"  [assistant] {content[:500]}")
        elif role == "user":
            log(f"  [user] {content[:200]}")

    log(f"\ntool call sequence: {tool_sequence}")

    log("\n--- ACCEPTANCE, PER CRITERION ---")
    api_calls = session["api_call_count"]
    crit_answer = REQUIRED_QUOTE in final_answer
    log(f"1. answer contains {REQUIRED_QUOTE!r}: {'PASS' if crit_answer else 'FAIL'} "
        f"(answer: {final_answer[:300]!r})")
    log(f"2. provenance (tool result THIS TURN returned the passage from Fred's intake record): "
        f"{'PASS' if provenance_hit else 'FAIL'}")
    crit_calls = api_calls <= API_CALLS_CEILING
    log(f"3. api_calls <= {API_CALLS_CEILING}: {'PASS' if crit_calls else 'FAIL'} (actual: {api_calls}; "
        f"itemised tool sequence above)")
    log(f"4. vault journal unchanged after the turn: {'PASS' if vault_unchanged else 'FAIL'}")

    overall = crit_answer and provenance_hit and crit_calls and vault_unchanged
    log(f"\nOVERALL: {'PASS (all four criteria)' if overall else 'FAIL on at least one criterion'}")

    TRANSCRIPT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\ntranscript written: {TRANSCRIPT}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
