#!/usr/bin/env python3
"""STEP U-CLOSE, Part A/C/D/E: full tool-surface, two-sided contamination
verification for step6_post's 25 stored B7 pass records.

Read-only against ~/.hermes/profiles/david/state.db and the repo's stored
step6_b7_pass_*.usage.json / step6_b7_pass.raw.json files. Zero Hermes/model
calls. Throwaway instrument per Evidence Discipline (bounded one-off).

Tees scripts/step6_post_full_tool_surface_verification.txt; refuses to
overwrite without --overwrite.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sqlite3
import sys

REPO = "/home/liam/agentic-os-live"
STATE_DB = os.path.expanduser("~/.hermes/profiles/david/state.db")
SCRIPTS = os.path.join(REPO, "scripts")

HARNESS_DOC = os.path.join(
    REPO, "docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md"
)
SCORER_FILES = [
    os.path.join(SCRIPTS, "step3_b7_harness.py"),
    os.path.join(SCRIPTS, "step5_b7_growth_harness.py"),
    os.path.join(SCRIPTS, "step6_b7_tools_harness.py"),
]

PATH_SIGNATURES = [
    "docs/ttros",
    "TTROS_CAPABILITY_HARNESS_QUESTIONS",
    "step3_b7_harness.py",
    "step5_b7_growth_harness.py",
    "step6_b7_tools_harness.py",
    "step3_b7_pass",
    "step5_b7_pass",
    "step6_b7_pass",
    ".scored.json",
    ".raw.json",
    ".transcript.txt",
    "ttros_backups",
    "PREIMAGE",
]


def load_session_ids() -> dict[str, str]:
    out = {}
    for f in sorted(glob.glob(os.path.join(SCRIPTS, "step6_b7_pass_*.usage.json"))):
        qid = os.path.basename(f).replace("step6_b7_pass_", "").replace(".usage.json", "")
        d = json.load(open(f))
        out[qid] = d["session_id"]
    return out


def load_content_signatures() -> list[str]:
    """Structural/meta signatures unique to the harness document's and
    scorer's own scaffolding -- NOT the underlying business-fact vocabulary,
    which legitimately also lives in the real vault documents the harness
    describes. A first pass of this script used harness-doc prose lines and
    scorer kw() literals directly as signatures and produced ~29 false
    positives (e.g. "forward-deployed", "measurable outcome") that are
    themselves real, legitimate content in memory/offers.md and
    memory/positioning.md -- the exact "ordinary business search terms match
    the answer key incidentally" trap this task's Part D warns about. Fixed
    by signaling on the harness's *meta*-scaffolding (question-set framing,
    scorer code identifiers, classification vocabulary) instead of paraphrased
    fact content."""
    sigs = [
        # harness doc's own framing / meta text -- would not appear in a real
        # business vault document, which describes the business, not the test.
        "B7 — the bound that can say NO",
        "the bound that can say NO",
        "Trap: this is Mike's advice, not Liam's stated intention",
        "vault records Liam as reluctant to niche down",
        "## §A — Offer and delivery",
        "## §B — Positioning and ideal client",
        "## §C — Pipeline and commitments",
        "## §D — Priorities and current state",
        "## §E — The call corpus",
        "## §F — Honesty",
        "Do not tune the questions to what David currently answers well",
        "CONTEXT-MISSING is determined by checking whether the",
        # scorer's own code identifiers -- executable scaffolding, never
        # legitimate vault prose.
        "def score_pass",
        "def kw(",
        "QUESTIONS = [",
        "FACT_SOURCE_OVERRIDES",
        "NON_HONESTY_FACT_COUNT",
        "honesty=False,",
        "honesty=True,",
        "fail_if=",
        # this task's / prior audits' own classification vocabulary -- would
        # never appear inside a real business document or call transcript.
        "MATERIAL_CONTAMINATION",
        "TEST_MATERIAL_EXPOSED",
        "answer-key",
        "BLOCKED_TOOL_NAMES",
    ]
    for qid in re.findall(r'dict\(id="([A-F]\d)"', open(SCORER_FILES[0], encoding="utf-8").read()):
        sigs.append(f'dict(id="{qid}", section=')
    return sorted(set(sigs), key=len, reverse=True)


def find_cross_leak(text: str, own_sid: str, other_session_ids: dict[str, str]) -> list[str]:
    """Check whether `text` embeds another step6_post question's own opaque
    session-ID token verbatim -- a structural, unfakeable marker of the
    session_search-class cross-session leak the prior audit confirmed
    elsewhere (that leak mechanism returns another session's content
    alongside its session_id). A first version of this check instead did a
    fuzzy 40-char substring match against other questions' final answer text
    and produced false positives from shared LEGITIMATE source documents
    (company.md, INDEX.md) that multiple questions correctly cite
    independently -- overlapping business content is not evidence of a
    session-to-session leak. Session-ID strings are random per-run tokens
    with no legitimate reason to appear in unrelated content, so this is a
    much higher-precision signal."""
    hits = []
    if not text:
        return hits
    for qid, sid in other_session_ids.items():
        if sid == own_sid:
            continue
        if sid in text:
            hits.append(f"CROSS_LEAK_SESSION_ID_OF_{qid}:{sid}")
    return hits


READ_CAPABLE_KNOWN = {
    "terminal": (True, "arbitrary shell command execution -- can read/cat any file the process can reach"),
    "process_manage": (True, "v0.21.1 rename of 'process'; process control can include piping/reading process output, and per STEP U's own finding was reachable to run shell-equivalent commands"),
    "process": (True, "pre-v0.21.1 name for process_manage; same capability class"),
    "search_files": (True, "generic filesystem content/path search -- confirmed leak vector in step3/5"),
    "read_file": (True, "generic filesystem read"),
    "execute_code": (True, "arbitrary code execution with filesystem access"),
    "session_search": (True, "cross-session history search -- confirmed leak vector"),
    "mcp__brain__open_note": (True, "reads a named Business Brain vault note"),
    "mcp__brain__open_call": (True, "reads a historical call transcript"),
    "mcp__brain__search_calls": (True, "searches historical call corpus, returns content"),
    "mcp__brain__search_history": (True, "searches Business Brain vault, returns content"),
    "skill_view": (True, "reads skill definition content by name"),
    "remember_brain_knowledge": (False, "writes a candidate fact to the Business Brain intake path -- no arbitrary read"),
    "brain_memory_status": (False, "returns fixed status/health fields, not arbitrary file content"),
}


def classify_tool(name: str) -> tuple[bool, str]:
    if name in READ_CAPABLE_KNOWN:
        return READ_CAPABLE_KNOWN[name]
    return (True, "unknown tool, not in the known-safe list -- treated as read-capable by default (fail open to caution, not fail closed to a clean verdict)")


def fetch_session_messages(con: sqlite3.Connection, session_id: str) -> list[dict]:
    cur = con.cursor()
    cur.execute(
        "select id, role, tool_call_id, tool_name, tool_calls, content from messages "
        "where session_id=? order by id",
        (session_id,),
    )
    cols = ["id", "role", "tool_call_id", "tool_name", "tool_calls", "content"]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def extract_calls(messages: list[dict]) -> list[dict]:
    """Pair each assistant tool_calls entry with its tool-role response by
    tool_call_id. Returns one record per call: {name, arguments_str, call_id,
    output_content, output_present}."""
    calls = []
    # index tool-role messages by tool_call_id
    tool_msgs_by_id = {}
    for m in messages:
        if m["role"] == "tool" and m["tool_call_id"]:
            tool_msgs_by_id.setdefault(m["tool_call_id"], []).append(m)

    for m in messages:
        if m["role"] != "assistant" or not m["tool_calls"]:
            continue
        try:
            tc_list = json.loads(m["tool_calls"])
        except (json.JSONDecodeError, TypeError):
            continue
        for tc in tc_list:
            fn = tc.get("function", {}) if isinstance(tc, dict) else {}
            name = fn.get("name") or tc.get("name") or "UNKNOWN"
            args = fn.get("arguments", "")
            call_id = tc.get("id") or tc.get("call_id")
            resp_msgs = tool_msgs_by_id.get(call_id, [])
            output_content = "\n".join(
                (rm.get("content") or "") for rm in resp_msgs
            )
            calls.append(
                {
                    "name": name,
                    "arguments": args if isinstance(args, str) else json.dumps(args),
                    "call_id": call_id,
                    "output_content": output_content,
                    "output_present": bool(resp_msgs) and any(rm.get("content") for rm in resp_msgs),
                }
            )
    return calls


def scan_text(text: str, content_sigs: list[str]) -> list[str]:
    hits = []
    if not text:
        return hits
    for sig in PATH_SIGNATURES:
        if sig in text:
            hits.append(f"PATH_SIG:{sig}")
    for sig in content_sigs:
        if sig and sig in text:
            hits.append(f"CONTENT_SIG:{sig[:80]}")
    return hits


def main():
    overwrite = "--overwrite" in sys.argv
    out_txt = os.path.join(SCRIPTS, "step6_post_full_tool_surface_verification.txt")
    if os.path.exists(out_txt) and not overwrite:
        print(f"REFUSING to overwrite existing transcript: {out_txt}", file=sys.stderr)
        sys.exit(1)

    lines = []

    def log(s=""):
        print(s)
        lines.append(s)

    session_ids = load_session_ids()
    log(f"Loaded {len(session_ids)} step6_post session IDs from usage.json files.")
    assert len(session_ids) == 25, f"expected 25, got {len(session_ids)}"

    content_sigs = load_content_signatures()
    log(f"Loaded {len(content_sigs)} structural/meta signatures from harness doc + scorer sources.")

    con = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)

    all_tool_names = set()
    total_calls = 0
    calls_with_output = 0
    per_call_records = []
    missing_sessions = []

    for qid, sid in session_ids.items():
        cur = con.cursor()
        cur.execute("select id from sessions where id=?", (sid,))
        if cur.fetchone() is None:
            missing_sessions.append((qid, sid))
            continue
        messages = fetch_session_messages(con, sid)
        calls = extract_calls(messages)
        for c in calls:
            total_calls += 1
            all_tool_names.add(c["name"])
            if c["output_present"]:
                calls_with_output += 1
            arg_hits = scan_text(c["arguments"], content_sigs)
            out_hits = scan_text(c["output_content"], content_sigs)
            leak_hits = find_cross_leak(
                c["output_content"], sid, session_ids
            ) + find_cross_leak(c["arguments"], sid, session_ids)
            per_call_records.append(
                {
                    "qid": qid,
                    "session_id": sid,
                    "tool": c["name"],
                    "call_id": c["call_id"],
                    "output_present": c["output_present"],
                    "arg_hits": arg_hits,
                    "out_hits": out_hits,
                    "leak_hits": leak_hits,
                }
            )

    log("")
    log("=== PART A: output-retention precondition ===")
    log(f"Total tool calls across 25 step6_post sessions: {total_calls}")
    log(f"Tool calls with a non-empty stored output (tool-role content): {calls_with_output}")
    coverage = (calls_with_output / total_calls * 100) if total_calls else 0.0
    log(f"Output-retention coverage: {coverage:.1f}%")
    log(f"Missing sessions (not found in state.db): {missing_sessions}")

    log("")
    log("=== PART C: tool surface enumerated from the records ===")
    log(f"Distinct tool names observed: {sorted(all_tool_names)}")
    log(f"Count: {len(all_tool_names)}")
    for name in sorted(all_tool_names):
        cap, reason = classify_tool(name)
        log(f"  {name}: read-capable={cap} -- {reason}")
    log(f"'terminal' present in step6_post surface: {'terminal' in all_tool_names}")
    log(f"'process_manage' present in step6_post surface: {'process_manage' in all_tool_names}")
    log(f"'process' present in step6_post surface: {'process' in all_tool_names}")

    log("")
    log("=== PART D: two-sided contamination scan (real records) ===")
    contaminated = [
        r for r in per_call_records if r["arg_hits"] or r["out_hits"] or r["leak_hits"]
    ]
    log(f"Total tool calls scanned: {len(per_call_records)}")
    log(f"Calls with ANY hit (argument, output, or cross-question leak): {len(contaminated)}")
    for r in contaminated:
        log(f"  CONTAMINATION CANDIDATE: q={r['qid']} tool={r['tool']} session={r['session_id']}")
        log(f"    arg_hits={r['arg_hits']}")
        log(f"    out_hits={r['out_hits']}")
        log(f"    leak_hits={r['leak_hits']}")

    log("")
    log(f"VERDICT (real records only): {'CLEAN' if not contaminated else 'CONTAMINATED'} on the full enumerated surface, {len(per_call_records)} calls, {coverage:.1f}% output coverage.")

    # Save structured data for the rehearsal step and the report.
    data_out = os.path.join(SCRIPTS, "step6_post_full_tool_surface_verification.json")
    with open(data_out, "w") as f:
        json.dump(
            {
                "session_ids": session_ids,
                "total_calls": total_calls,
                "calls_with_output": calls_with_output,
                "coverage_pct": coverage,
                "distinct_tool_names": sorted(all_tool_names),
                "contaminated_candidates": contaminated,
                "missing_sessions": missing_sessions,
            },
            f,
            indent=2,
        )
    log("")
    log(f"Structured output written to {data_out}")

    with open(out_txt, "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"Transcript written to {out_txt}")


if __name__ == "__main__":
    main()
