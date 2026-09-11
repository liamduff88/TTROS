#!/usr/bin/env python3
"""Step 6 -- B7 rescoring pass with the four new brain MCP corpus/vault tools
(search_calls, open_call, open_note, search_history) available to David.

Reuses the frozen Step 3 question set and scorer (imported by path, not
re-implemented) and the same vault-isolation snapshot Step 3/5 used, so this
pass's totals are comparable to the Step 5 k=1 baseline (map_bytes=1788,
same tools-absent map, no corpus/vault tools) without a second source of
drift. This is the ONE rescoring pass CLAUDE.md's budget line authorizes for
this step.

Beyond fact coverage, this script also classifies each question's round-trip
behaviour by reading (read-only) David's own Hermes session state.db
(~/.hermes/profiles/david/state.db, sessions/messages tables) for the exact
session_id each call produced:
  - "direct"      -- sessions.tool_call_count == 0 for that session
  - "brain_tool"  -- at least one tool_calls entry names one of the four new
                     brain MCP tools (mcp__brain__search_calls/open_call/
                     open_note/search_history)
  - "other_tool"  -- tool_call_count > 0 but no new brain tool was used
                     (e.g. the CLI's own generic search_files/read_file,
                     which pre-Step-6 evidence shows can already reach the
                     vault snapshot directly -- a pre-existing capability,
                     not attributable to this step)
This three-way split is the honest version of "direct-answer vs. tool
round-trip": a two-way split would credit this step for round trips that
were already possible before it.

Budget: exactly 25 hermes calls, hard-stopped in-process, actual count
written to the transcript against the declared maximum.

Usage:
  step6_b7_tools_harness.py run-pass [--dry-run] [--overwrite] [--resume]
  step6_b7_tools_harness.py score-pass [--overwrite]
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/liam/agentic-os-live")
SCRIPT_DIR = Path(__file__).resolve().parent
LIVE_VAULT = Path("/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain")
# POST-I3 REPAIR (2026-09-10): the original Step 6 snapshot
# (b7_harness_vault_snapshot_20260907_000711Z) predates STEP I1/I2/I3
# semantic-historical and production ingestion entirely -- it has no
# sources/historical_calls/cards/, no sources/intake/, and still carries the
# now-removed MANIFEST.md. Rerunning against it would silently measure the
# pre-ingestion vault regardless of what I1/I2/I3 actually did. A fresh,
# read-only master (b7_harness_vault_snapshot_20260910_015654Z, rsync'd from
# LIVE_VAULT, diff-confirmed byte-identical to it at snapshot time) is
# substituted here under a new LABEL so this pass cannot collide with or
# overwrite the historical step6_b7_pass.* evidence (58.3% §E) that the
# closeout compares against. The write-isolation purpose of the snapshot
# (protect the live vault from anything David's own session does) is
# unchanged; only its content currency is repaired.
MASTER_SNAPSHOT = Path("/home/liam/ttros_backups/b7_harness_vault_snapshot_20260910_015654Z")
WORK_VAULT = Path(
    "/tmp/claude-1002/-home-liam-agentic-os-live/d049c07d-01d1-411f-bd2a-854966eef41a/"
    "scratchpad/step6_post_i3_b7_vault_work"
)
ASSEMBLY_DIR = ROOT / "queue" / "context_assemblies"
HERMES_BIN = "/home/liam/.local/bin/hermes"
DAVID_STATE_DB = Path("/home/liam/.hermes/profiles/david/state.db")
CALL_TIMEOUT_SECONDS = 600
MAX_CALLS = 25
LABEL = "step6_post_i3"
NEW_BRAIN_TOOLS = {
    "mcp__brain__search_calls",
    "mcp__brain__open_call",
    "mcp__brain__open_note",
    "mcp__brain__search_history",
}

spec = importlib.util.spec_from_file_location("step3_b7_harness", SCRIPT_DIR / "step3_b7_harness.py")
step3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step3)  # type: ignore[union-attr]

QUESTIONS = step3.QUESTIONS
NON_HONESTY_FACT_COUNT = step3.NON_HONESTY_FACT_COUNT
score_pass = step3.score_pass


def refresh_work_vault() -> None:
    WORK_VAULT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsync", "-a", "--delete", f"{MASTER_SNAPSHOT}/", f"{WORK_VAULT}/"], check=True)


def git_status_porcelain() -> set[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                          capture_output=True, text=True, check=True)
    return set(out.stdout.splitlines())


def newest_assembly_file(after: float) -> Path | None:
    candidates = [p for p in ASSEMBLY_DIR.glob("*.json") if p.stat().st_mtime >= after]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def call_david(question_text: str, usage_file: Path, dry_run: bool) -> dict:
    refresh_work_vault()
    before_status = git_status_porcelain()
    before_mtime = datetime.datetime.now().timestamp()
    start = datetime.datetime.now(datetime.timezone.utc)
    env = dict(os.environ)
    env["AOS_ROOT"] = str(ROOT)
    env["AOS_OPERATOR_CONSULTATION"] = "1"
    env["TTROS_BRAIN_ROOT"] = str(WORK_VAULT)
    # TTROS_CANONICAL_RANKER_ENABLED deliberately NOT set -> defaults to "0"
    # (disabled), same surface as the Step 5 k=1 baseline this pass is
    # compared against: map + tools measured on top of the new default.
    if dry_run:
        answer = f"[DRY RUN stub answer for: {question_text}]"
        stderr = ""
        returncode = 0
    else:
        proc = subprocess.run(
            [HERMES_BIN, "-p", "david", "-z", question_text, "--usage-file", str(usage_file)],
            env=env, capture_output=True, text=True, timeout=CALL_TIMEOUT_SECONDS,
        )
        answer = proc.stdout.strip()
        stderr = proc.stderr.strip()
        returncode = proc.returncode
    end = datetime.datetime.now(datetime.timezone.utc)
    manifest_path = None if dry_run else newest_assembly_file(before_mtime)
    manifest = {}
    if manifest_path and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            manifest = {"_read_error": str(exc)}
    after_status = git_status_porcelain()
    unexpected = {
        line for line in (after_status - before_status)
        if re.search(r"\bqueue/", line)
        and "queue/context_assemblies/" not in line
        and "scripts/step6_b7_pass_" not in line
        # Transient lock-candidate churn from other running systemd timers
        # (e.g. aos-gmail-capture.timer), confirmed unrelated to this harness
        # by Step 3 (scripts/step3_b7_harness.py's own comment on this) and
        # reproduced here in --dry-run (zero real calls, so it cannot be this
        # harness's own effect).
        and "queue/locks/" not in line
    }
    usage = {}
    if usage_file.exists():
        try:
            usage = json.loads(usage_file.read_text(encoding="utf-8"))
        except Exception:
            usage = {"_unparsed": usage_file.read_text(encoding="utf-8")[:2000]}
    # B6 depth-tool arrival evidence for this call's own session (see
    # step3_b7_harness.extract_tool_reads -- shared, not re-implemented; this
    # module already imports that file as `step3` for QUESTIONS/score_pass).
    tool_reads = sorted(step3.extract_tool_reads(usage.get("session_id"))) if not dry_run else []
    return {
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "latency_seconds": (end - start).total_seconds(),
        "answer": answer,
        "stderr": stderr,
        "returncode": returncode,
        "manifest_path": str(manifest_path) if manifest_path else None,
        "manifest": manifest,
        "usage": usage,
        "tool_reads": tool_reads,
        "unexpected_repo_mutation": sorted(unexpected),
    }


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def cmd_run_pass(args: argparse.Namespace) -> int:
    transcript_path = SCRIPT_DIR / f"{LABEL}_b7_pass.transcript.txt"
    json_path = SCRIPT_DIR / f"{LABEL}_b7_pass.raw.json"

    records: list[dict] = []
    already_done: set[str] = set()
    if args.resume:
        if not json_path.exists():
            print(f"--resume given but no prior evidence at {json_path}.", file=sys.stderr)
            return 2
        prior = json.loads(json_path.read_text(encoding="utf-8"))
        if not prior.get("aborted"):
            print(f"{json_path} is not marked aborted -- nothing to resume.", file=sys.stderr)
            return 2
        records = prior["records"]
        already_done = {r["question_id"] for r in records}
        lines = (transcript_path.read_text(encoding="utf-8").splitlines() if transcript_path.exists() else [])
        lines += [f"[resumed at {datetime.datetime.now(datetime.timezone.utc).isoformat()}, "
                  f"{len(records)} prior call(s) carried forward: {sorted(already_done)}]", ""]
    elif not args.overwrite and (transcript_path.exists() or json_path.exists()):
        print(f"REFUSING to overwrite existing pass evidence: "
              f"{transcript_path} / {json_path}. Pass --overwrite or --resume.", file=sys.stderr)
        return 2
    else:
        lines = [
            f"STEP 6 -- B7 RESCORING PASS (corpus/vault tools live) -- "
            f"{'DRY RUN' if args.dry_run else 'LIVE'}",
            f"Started (UTC): {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
            "Surface declared: CLI-David (direct `hermes -p david -z` invocation, not dashboard/gateway).",
            "Model pin (from ~/.hermes/profiles/david/config.yaml): openai-codex / gpt-5.5.",
            f"Vault isolation: TTROS_BRAIN_ROOT={WORK_VAULT} (restored from {MASTER_SNAPSHOT}, "
            f"a fresh post-STEP-I3 snapshot of {LIVE_VAULT} taken 2026-09-10T01:56:54Z -- "
            f"NOT the Step 3/5/6-pre/post snapshot from 2026-09-07 -- before every call).",
            f".hermes.md present at repo root, unchanged since Step 5 (k=1, 1788 B).",
            "brain MCP server: tools/brain_memory_mcp.py, now with search_calls/open_call/"
            "open_note/search_history live (this step's change).",
            f"Declared maximum calls this pass: {MAX_CALLS}.",
            "",
        ]

    if not MASTER_SNAPSHOT.exists():
        print(f"HARD STOP: vault master snapshot missing at {MASTER_SNAPSHOT}", file=sys.stderr)
        return 3

    declared_max = MAX_CALLS
    call_count = len(records)

    for q in QUESTIONS:
        if q["id"] in already_done:
            continue
        if call_count >= declared_max:
            lines.append(f"HARD STOP: reached declared maximum of {declared_max} calls "
                         f"before question {q['id']}.")
            _write(transcript_path, lines)
            _write_json(json_path, {"pass": LABEL, "aborted": True,
                                      "declared_max": declared_max, "actual_calls": call_count,
                                      "records": records})
            print("HARD STOP: budget exceeded.", file=sys.stderr)
            return 4
        call_count += 1
        usage_file = SCRIPT_DIR / f"{LABEL}_b7_pass_{q['id']}.usage.json"
        result = call_david(q["text"], usage_file, args.dry_run)
        result["question_id"] = q["id"]
        result["question_text"] = q["text"]
        result["call_index"] = call_count
        records.append(result)
        lines.append(f"--- Q{call_count}/{declared_max} [{q['id']}] {q['text']}")
        lines.append(f"    latency_s={result['latency_seconds']:.1f} manifest={result['manifest_path']} "
                     f"session_id={result['usage'].get('session_id')}")
        if result["unexpected_repo_mutation"]:
            lines.append(f"    !!! UNEXPECTED REPO MUTATION: {result['unexpected_repo_mutation']}")
        lines.append(f"    ANSWER: {result['answer'][:4000]}")
        lines.append("")
        if result["unexpected_repo_mutation"]:
            lines.append("HARD STOP: unexpected repo mutation detected outside "
                         "queue/context_assemblies/. Aborting.")
            _write(transcript_path, lines)
            _write_json(json_path, {"pass": LABEL, "aborted": True,
                                      "declared_max": declared_max, "actual_calls": call_count,
                                      "records": records})
            print("HARD STOP: unexpected repo mutation detected.", file=sys.stderr)
            return 5

    lines.append(f"Finished (UTC): {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    lines.append(f"Actual call count: {call_count} / declared maximum {declared_max}")
    _write(transcript_path, lines)
    _write_json(json_path, {"pass": LABEL, "aborted": False,
                              "declared_max": declared_max, "actual_calls": call_count,
                              "records": records})
    print(f"Pass complete: {call_count}/{declared_max} calls. "
          f"Transcript: {transcript_path}  JSON: {json_path}")
    return 0


def classify_round_trip(session_id: str | None) -> dict:
    """Read-only lookup against David's own Hermes session state.db. Never
    writes. Returns {'disposition': 'direct'|'brain_tool'|'other_tool'|
    'unknown', 'tool_call_count': int|None, 'tool_names': [...]}."""
    if not session_id or not DAVID_STATE_DB.exists():
        return {"disposition": "unknown", "tool_call_count": None, "tool_names": []}
    try:
        conn = sqlite3.connect(f"file:{DAVID_STATE_DB}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        session_row = conn.execute(
            "SELECT tool_call_count FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if session_row is None:
            return {"disposition": "unknown", "tool_call_count": None, "tool_names": []}
        tool_call_count = session_row["tool_call_count"]
        names: list[str] = []
        if tool_call_count:
            rows = conn.execute(
                "SELECT tool_calls FROM messages WHERE session_id = ? AND tool_calls IS NOT NULL",
                (session_id,),
            ).fetchall()
            for row in rows:
                try:
                    parsed = json.loads(row["tool_calls"])
                except Exception:
                    continue
                if isinstance(parsed, list):
                    for entry in parsed:
                        fn = (entry or {}).get("function") or {}
                        name = fn.get("name")
                        if name == "tool_call":
                            # POST-I3 REPAIR (2026-09-10): 2026-09-08+ Hermes routes every
                            # MCP tool call through this generic dispatcher; the real name
                            # is nested in arguments.name (see step3_b7_harness.py's
                            # extract_tool_reads for the confirming evidence). Record the
                            # real name so brain_tool classification still works.
                            try:
                                inner = json.loads(fn.get("arguments") or "{}")
                            except Exception:
                                inner = {}
                            name = (inner.get("name") if isinstance(inner, dict) else None) or name
                        if name:
                            names.append(name)
        conn.close()
        if not tool_call_count:
            disposition = "direct"
        elif any(n in NEW_BRAIN_TOOLS for n in names):
            disposition = "brain_tool"
        else:
            disposition = "other_tool"
        return {"disposition": disposition, "tool_call_count": tool_call_count, "tool_names": sorted(set(names))}
    except Exception as exc:
        return {"disposition": "unknown", "tool_call_count": None, "tool_names": [], "_error": str(exc)}


def cmd_score_pass(args: argparse.Namespace) -> int:
    raw_path = SCRIPT_DIR / f"{LABEL}_b7_pass.raw.json"
    scored_path = SCRIPT_DIR / f"{LABEL}_b7_pass.scored.json"
    if not raw_path.exists():
        print(f"No raw evidence at {raw_path} -- run run-pass first.", file=sys.stderr)
        return 2
    if not args.overwrite and scored_path.exists():
        print(f"REFUSING to overwrite {scored_path}. Pass --overwrite.", file=sys.stderr)
        return 2
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if raw.get("aborted"):
        print("Pass was aborted mid-run. Scoring a partial pass is not meaningful.", file=sys.stderr)
        return 3
    scored = score_pass(raw)

    records_by_id = {r["question_id"]: r for r in raw["records"]}
    round_trip_by_id = {}
    for qid, rec in records_by_id.items():
        session_id = (rec.get("usage") or {}).get("session_id")
        classification = classify_round_trip(session_id)
        classification["latency_seconds"] = rec["latency_seconds"]
        classification["session_id"] = session_id
        round_trip_by_id[qid] = classification
    scored["round_trip"] = round_trip_by_id

    _write_json(scored_path, scored)
    honesty_fails = [q["id"] for q in scored["questions"] if q["honesty"] and q["verdict"] == "FAIL"]
    zero_pct = [q["id"] for q in scored["questions"] if not q["honesty"] and q["coverage"] == 0.0]
    e_q = [q for q in scored["questions"] if q["section"] == "E" and not q["honesty"]]
    e_present = sum(q["facts_present"] for q in e_q)
    e_total = sum(q["facts_total"] for q in e_q)
    dispositions = [v["disposition"] for v in round_trip_by_id.values()]
    print(f"Pass {LABEL}: coverage {scored['coverage_pct']:.1f}% "
          f"({scored['total_facts_present']}/{scored['total_facts_possible']}). "
          f"Section E: {e_present}/{e_total} = {100.0*e_present/e_total:.1f}%. "
          f"Dispositions: direct={dispositions.count('direct')} "
          f"brain_tool={dispositions.count('brain_tool')} "
          f"other_tool={dispositions.count('other_tool')} "
          f"unknown={dispositions.count('unknown')}. "
          f"Honesty fails: {honesty_fails or 'none'}. Zero-coverage: {zero_pct or 'none'}.")
    print(f"Written: {scored_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run-pass")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--overwrite", action="store_true")
    p_run.add_argument("--resume", action="store_true")
    p_run.set_defaults(func=cmd_run_pass)

    p_score = sub.add_parser("score-pass")
    p_score.add_argument("--overwrite", action="store_true")
    p_score.set_defaults(func=cmd_score_pass)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
