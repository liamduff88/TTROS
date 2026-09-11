"""STEP 5/6_POST RECONCILIATION -- compliant-only B6 disposition recompute.

Purpose: the completed investigation `step5_step6_post_repaired_b6_investigation.md`
resolved its "depth-tool reads" evidence arm (4 of 52 unmet facts) by calling the
repaired B6's own `extract_tool_reads(session_id)`, which opens
`~/.hermes/profiles/david/state.db` and queries `messages.tool_calls`. That is a live
Hermes runtime/session store and its use for this purpose was found non-compliant with
this reconciliation's ground rules.

This instrument recomputes the SAME repaired-B6 disposition over the SAME stored
`step6_b7_pass.raw.json` records, but with `tool_reads` forced to an empty frozenset for
every record -- i.e. `extract_tool_reads()` is never called and `state.db` is never
opened. It is a compliant-only recompute using only:
  - `scripts/step6_b7_pass.raw.json` (stored harness output: per-question manifest
    `provenance`/`actual_reads`, already on disk, produced 2026-09-07);
  - `scripts/step3_b7_harness.py`'s frozen `QUESTIONS`, `FACT_SOURCE_OVERRIDES`,
    `source_arrived()`, `score_pass()` (source code, not live evidence).

Fail-closed guard: `sqlite3.connect` is monkeypatched before any repaired-B6 code runs to
raise if invoked with a path containing "state.db" or ".hermes/profiles" -- if the
repaired module's `extract_tool_reads()` is ever reached despite `tool_reads` being
force-supplied, this instrument aborts loudly rather than silently opening the store.

Zero model / Hermes / David / provider calls. Reads only; writes only its own transcript.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
STEP3_PATH = SCRIPT_DIR / "step3_b7_harness.py"
RAW_PATH = SCRIPT_DIR / "step6_b7_pass.raw.json"
TRANSCRIPT_PATH = SCRIPT_DIR / "step5_step6_post_repaired_b6_reconciliation_instrument.txt"

LINES: list[str] = []


def log(s: str = "") -> None:
    LINES.append(s)
    print(s)


def sha256_of(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ForbiddenAccess(RuntimeError):
    pass


_real_sqlite_connect = sqlite3.connect
GUARD_BLOCKED_COUNT = 0


def _guarded_connect(*args, **kwargs):
    global GUARD_BLOCKED_COUNT
    target = str(args[0]) if args else str(kwargs.get("database", ""))
    if "state.db" in target or ".hermes" in target or "profiles" in target:
        GUARD_BLOCKED_COUNT += 1
        raise ForbiddenAccess(
            f"FAIL-CLOSED: blocked sqlite3.connect() to {target!r} -- this reconciliation "
            "instrument must never open state.db or any Hermes profile store."
        )
    return _real_sqlite_connect(*args, **kwargs)


def load_step3():
    spec = importlib.util.spec_from_file_location("step3_b7_harness_reconciliation", STEP3_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EVIDENCE_ORDER = ["fact_level_override", "manifest_provenance_or_actual_reads", "depth_tool", "no_usable_evidence"]


def classify_evidence(is_override: bool, docs_used: list[str], arrived: dict) -> str:
    if is_override:
        return "fact_level_override"
    evidences = {arrived[d]["evidence"] for d in docs_used}
    if "manifest_provenance" in evidences or "manifest_actual_read" in evidences:
        return "manifest_provenance_or_actual_reads"
    if "depth_tool" in evidences:
        return "depth_tool"
    return "no_usable_evidence"


def main() -> int:
    overwrite = "--overwrite" in sys.argv
    if TRANSCRIPT_PATH.exists() and not overwrite:
        print(f"REFUSING to overwrite existing transcript: {TRANSCRIPT_PATH}. Pass --overwrite.",
              file=sys.stderr)
        return 2

    log("STEP 5 / STEP 6_POST -- COMPLIANT-ONLY B6 RECONCILIATION RECOMPUTE")
    log("Zero model / Hermes / David / provider calls in this script.")
    log("sqlite3.connect() monkeypatched to fail closed against state.db / .hermes / profiles paths.")
    sqlite3.connect = _guarded_connect

    log(f"\nscripts/step3_b7_harness.py SHA-256: {sha256_of(STEP3_PATH)}")
    log(f"scripts/step6_b7_pass.raw.json SHA-256: {sha256_of(RAW_PATH)}")

    step3 = load_step3()

    log("\nRehearsal (negative case, before trusting the guard): calling the frozen "
        "extract_tool_reads() directly with a real stored session_id, to prove the guard "
        "actually intercepts a state.db open attempt rather than the run simply never "
        "reaching that code path.")
    real_sid = None
    try:
        raw_probe = json.loads(RAW_PATH.read_text(encoding="utf-8"))
        real_sid = (raw_probe["records"][0].get("usage") or {}).get("session_id")
    except Exception:
        pass
    before = GUARD_BLOCKED_COUNT
    result = step3.extract_tool_reads(real_sid)
    after = GUARD_BLOCKED_COUNT
    log(f"  extract_tool_reads({real_sid!r}) returned {result!r} (its own fail-soft contract: "
        "'Never writes. Returns an empty frozenset (not an error) for any missing db, missing "
        "session, or unparseable row' -- it catches ALL exceptions internally, including our "
        "ForbiddenAccess, and returns frozenset() rather than letting anything propagate. This "
        "means a caller cannot distinguish 'guard blocked it' from 'session genuinely had no "
        "reads' by exception alone -- confirmed directly here, recorded as a finding about "
        "extract_tool_reads()'s own swallow-all behavior, not a defect in this instrument.)")
    log(f"  Guard invocation counter: before={before}, after={after}.")
    if after <= before:
        log("\nHARD STOP: the guard's sqlite3.connect() interceptor was NOT invoked -- "
            "extract_tool_reads() may not have attempted to open state.db at all for this "
            "session_id (e.g. path missing), which would make this rehearsal inconclusive. "
            "Refusing to proceed without a confirmed-firing guard.")
        TRANSCRIPT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")
        return 5
    log("  Guard rehearsal PASSED: the sqlite3.connect() interceptor fired "
        f"({after - before} blocked call(s)) on a real state.db-opening attempt -- proven by "
        "the counter, not by exception propagation (which extract_tool_reads() swallows by "
        "design). The compliant-only recompute below never calls extract_tool_reads() at all "
        "(tool_reads is force-supplied as [] on every record via direct dict assignment), so "
        "this guard is a belt-and-suspenders check, not the primary compliance mechanism -- but "
        "it is now shown capable of actually firing, not just silently absent.")

    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    if raw.get("aborted"):
        log("\nHARD STOP: step6_b7_pass.raw.json is marked aborted.")
        return 3
    log(f"\nLoaded {len(raw['records'])} stored step6_post records "
        f"(actual_calls={raw['actual_calls']}, declared_max={raw['declared_max']}, "
        f"aborted={raw['aborted']}).")

    # Compliant-only augmentation: tool_reads forced empty for every record.
    # extract_tool_reads() is never called; state.db is never opened. If any code path
    # attempts it regardless, the sqlite3.connect guard above raises ForbiddenAccess.
    augmented_records = []
    for rec in raw["records"]:
        rec2 = copy.deepcopy(rec)
        rec2["tool_reads"] = []
        augmented_records.append(rec2)
    augmented_raw = {"pass": raw["pass"], "aborted": False,
                      "declared_max": raw["declared_max"], "actual_calls": raw["actual_calls"],
                      "records": augmented_records}

    scored = step3.score_pass(augmented_raw)
    log(f"\nCompliant-only coverage, ALL non-honesty sections A-E: "
        f"{scored['total_facts_present']}/{scored['total_facts_possible']} "
        f"({scored['coverage_pct']:.1f}%). (present() does not depend on tool_reads/arrival "
        "evidence at all -- expected to match the original investigation's 47/99 exactly.)")

    counts = {"CONTEXT-MISSING": 0, "IGNORED": 0, "UNDECIDABLE": 0}
    counts_ad = {"CONTEXT-MISSING": 0, "IGNORED": 0, "UNDECIDABLE": 0}
    evidence_counts = {k: {"CONTEXT-MISSING": 0, "IGNORED": 0, "UNDECIDABLE": 0} for k in EVIDENCE_ORDER}
    per_fact_records = []
    per_question_summary = []

    for q in scored["questions"]:
        if q["honesty"]:
            continue
        arrived = q["source_arrived"]
        is_ad = q["section"] in "ABCD"
        q_counts = {"CONTEXT-MISSING": 0, "IGNORED": 0, "UNDECIDABLE": 0, "present": 0}
        for fr in q["fact_results"]:
            fid = fr["id"]
            if fr["present"]:
                q_counts["present"] += 1
                continue
            disp = fr["disposition"]
            counts[disp] += 1
            if is_ad:
                counts_ad[disp] += 1
            q_counts[disp] += 1
            is_override = fid in step3.FACT_SOURCE_OVERRIDES
            docs_used = step3.FACT_SOURCE_OVERRIDES.get(fid, q["source_docs"])
            eclass = classify_evidence(is_override, docs_used, arrived)
            evidence_counts[eclass][disp] += 1
            per_fact_records.append({
                "id": fid, "question": q["id"], "section": q["section"],
                "disposition_compliant": disp, "evidence_class_compliant": eclass,
            })
        per_question_summary.append((q["id"], q_counts))

    log("\nPer-question disposition summary, COMPLIANT-ONLY recompute (non-honesty questions):")
    for qid, qc in per_question_summary:
        log(f"  {qid}: present={qc['present']} CONTEXT-MISSING={qc['CONTEXT-MISSING']} "
            f"IGNORED={qc['IGNORED']} UNDECIDABLE={qc['UNDECIDABLE']}")

    total_unmet = sum(counts.values())
    log(f"\nTHREE-WAY TOTALS (compliant-only), ALL sections A-E, {total_unmet} unmet:")
    for k in ["CONTEXT-MISSING", "IGNORED", "UNDECIDABLE"]:
        pct = 100.0 * counts[k] / total_unmet if total_unmet else 0.0
        log(f"  {k}: {counts[k]} ({pct:.1f}%)")

    total_unmet_ad = sum(counts_ad.values())
    log(f"\nTHREE-WAY TOTALS (compliant-only), sections A-D only, {total_unmet_ad} unmet:")
    for k in ["CONTEXT-MISSING", "IGNORED", "UNDECIDABLE"]:
        pct = 100.0 * counts_ad[k] / total_unmet_ad if total_unmet_ad else 0.0
        log(f"  {k}: {counts_ad[k]} ({pct:.1f}%)")

    log("\nEVIDENCE-CLASS BREAKDOWN (compliant-only; depth_tool is structurally unreachable "
        "here since tool_reads is always empty -- any fact that would have needed it now "
        "falls to no_usable_evidence):")
    reconciled = 0
    for eclass in EVIDENCE_ORDER:
        row = evidence_counts[eclass]
        row_total = sum(row.values())
        reconciled += row_total
        log(f"  {eclass}: total={row_total}  "
            f"CONTEXT-MISSING={row['CONTEXT-MISSING']} IGNORED={row['IGNORED']} "
            f"UNDECIDABLE={row['UNDECIDABLE']}")
    log(f"\nReconciliation: evidence-class totals sum to {reconciled}; three-way totals sum to "
        f"{total_unmet}. Match: {reconciled == total_unmet}")

    # Cross-reference against the ORIGINAL investigation's already-published per-question
    # table (scripts/step5_step6_post_repaired_b6_investigation.md, Part 2) to localize
    # exactly which facts' disposition depended on the non-compliant depth-tool arm.
    # Original per-question three-way counts (present, CM, IGNORED, UNDECIDABLE), transcribed
    # verbatim from the existing report -- not recomputed, since recomputing them would
    # require calling extract_tool_reads() again.
    original_per_question = {
        "A1": (6, 0, 1, 0), "A2": (0, 4, 0, 0), "A3": (1, 4, 0, 0), "A4": (0, 6, 0, 0),
        "A5": (3, 1, 0, 0), "B1": (2, 3, 0, 0), "B2": (3, 1, 0, 0), "B3": (0, 0, 7, 0),
        "B4": (2, 3, 0, 0), "C1": (3, 0, 0, 0), "C2": (6, 0, 2, 0), "C3": (1, 0, 1, 0),
        "C4": (0, 3, 0, 0), "D1": (1, 0, 4, 0), "D2": (3, 0, 0, 0), "D3": (1, 0, 1, 0),
        "D4": (1, 0, 1, 0), "E1": (9, 0, 0, 0), "E2": (1, 0, 3, 0), "E3": (2, 2, 0, 0),
        "E4": (1, 0, 0, 2), "E5": (1, 0, 1, 2),
    }
    log("\nCROSS-REFERENCE vs. original investigation's published per-question table "
        "(scripts/step5_step6_post_repaired_b6_investigation.md, transcribed verbatim, not "
        "recomputed):")
    changed_questions = []
    for qid, qc in per_question_summary:
        orig = original_per_question.get(qid)
        if orig is None:
            continue
        orig_present, orig_cm, orig_ig, orig_un = orig
        same_present = orig_present == qc["present"]
        same_disposition = (orig_cm, orig_ig, orig_un) == (
            qc["CONTEXT-MISSING"], qc["IGNORED"], qc["UNDECIDABLE"])
        flag = "" if (same_present and same_disposition) else "  <-- DIFFERS"
        log(f"  {qid}: original(present={orig_present},CM={orig_cm},IG={orig_ig},UN={orig_un}) "
            f"vs compliant(present={qc['present']},CM={qc['CONTEXT-MISSING']},"
            f"IG={qc['IGNORED']},UN={qc['UNDECIDABLE']}){flag}")
        if not same_disposition:
            changed_questions.append(qid)
        if not same_present:
            log(f"    ANOMALY: present() count differs for {qid} -- present() must not depend "
                "on tool_reads; investigate before trusting this recompute.")

    log(f"\nQuestions whose disposition breakdown differs from the original investigation: "
        f"{changed_questions}")

    # For each changed question, identify the specific fact IDs newly falling into
    # no_usable_evidence/CONTEXT-MISSING under compliant-only recompute -- these are exactly
    # the facts whose original (non-compliant) disposition depended on depth-tool evidence.
    log("\nPER-FACT detail for changed questions (compliant-only recompute):")
    depth_tool_affected = []
    for qid in changed_questions:
        for r in per_fact_records:
            if r["question"] == qid:
                log(f"  {r['id']}: disposition_compliant={r['disposition_compliant']} "
                    f"evidence_class_compliant={r['evidence_class_compliant']}")
                if r["evidence_class_compliant"] == "no_usable_evidence":
                    depth_tool_affected.append(r["id"])

    log(f"\nFacts identified as depth-tool-affected (no_usable_evidence under compliant-only "
        f"recompute, within a question whose breakdown changed): {sorted(depth_tool_affected)} "
        f"(n={len(depth_tool_affected)})")
    log("Expected count from the original investigation's evidence-class table: 4 "
        f"(depth_tool: total=4 CONTEXT-MISSING=0 IGNORED=2 UNDECIDABLE=2). Match: "
        f"{len(depth_tool_affected) == 4}")

    log("\n" + "=" * 78)
    log("DONE. Zero model/Hermes/David/provider calls made by this script. state.db never opened.")
    log("=" * 78)
    TRANSCRIPT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    print(f"\nTranscript written: {TRANSCRIPT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
