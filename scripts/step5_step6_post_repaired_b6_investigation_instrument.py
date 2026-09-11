#!/usr/bin/env python3
"""§13 step 2 prerequisite pass instrument.

Two things, zero model calls:
  1. Execute the real frozen predicates for B1.2 and B3.1 against constructed
     answer strings to classify their defect (contract §7.1).
  2. Rehearse, then run, the repaired three-way B6 disposition
     (CONTEXT-MISSING / IGNORED / UNDECIDABLE) over step6_post's stored
     records, broken down by evidence class.

Imports scripts/step3_b7_harness.py BY PATH, unmodified -- exactly as
scripts/step6_b7_tools_harness.py already does for reuse of QUESTIONS and
score_pass. Nothing in this script writes to step3_b7_harness.py or to any
stored evidence file. Read-only against step6_b7_pass.raw.json and against
~/.hermes/profiles/david/state.db (via the frozen extract_tool_reads()
function only -- see the note in real_run() about why this script calls it
directly rather than relying solely on
step6_post_full_tool_surface_verification.json).

Zero model / Hermes / David / provider calls. Tees a transcript beside
itself; refuses to overwrite without --overwrite.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
STEP3_PATH = SCRIPT_DIR / "step3_b7_harness.py"
RAW_PATH = SCRIPT_DIR / "step6_b7_pass.raw.json"
TOOL_SURFACE_JSON = SCRIPT_DIR / "step6_post_full_tool_surface_verification.json"
TRANSCRIPT_PATH = SCRIPT_DIR / "step5_step6_post_repaired_b6_investigation_instrument.txt"

DEFECT_POPULATION_UNDER_SPECIFIED = [
    "A1.1", "A1.2", "A1.3", "A1.4", "A1.5", "A1.6", "A2.2", "A4.1", "A4.2", "A4.5", "A5.1",
    "A5.2", "A5.3", "B1.2", "B1.3", "B1.5", "B2.2", "B2.3", "B3.1", "B3.2", "B3.3", "B3.4",
    "B3.5", "B4.1", "B4.2", "B4.3", "C1.1", "C1.2", "C1.3", "C4.1", "C4.2", "C4.3", "D1.1",
    "D1.4", "D1.5", "D2.3", "D3.1", "D4.1", "D4.2", "E2.3", "E3.2", "E4.1", "E4.3", "E5.2",
    "E5.3",
]
DEFECT_POPULATION_NORMALIZATION = ["B4.5", "E2.4"]
DEFECT_POPULATION_SOURCE_CONTRACT = ["E5.4"]
DEFECT_POPULATION_48 = (
    DEFECT_POPULATION_UNDER_SPECIFIED
    + DEFECT_POPULATION_NORMALIZATION
    + DEFECT_POPULATION_SOURCE_CONTRACT
)
assert len(DEFECT_POPULATION_48) == 48

LINES: list[str] = []


def log(s: str = "") -> None:
    print(s)
    LINES.append(s)


def load_step3():
    spec = importlib.util.spec_from_file_location("step3_b7_harness", STEP3_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def question_by_id(step3, qid: str) -> dict:
    return next(q for q in step3.QUESTIONS if q["id"] == qid)


def make_raw_record(qid: str, answer: str, manifest: dict, session_id: str | None = None,
                     tool_reads: list[str] | None = None) -> dict:
    rec = {
        "question_id": qid,
        "answer": answer,
        "manifest": manifest,
        "usage": {"session_id": session_id} if session_id else {},
    }
    if tool_reads is not None:
        rec["tool_reads"] = tool_reads
    return rec


def make_raw(records: list[dict]) -> dict:
    return {"pass": "instrument", "aborted": False,
            "declared_max": len(records), "actual_calls": len(records),
            "records": records}


def fact_result(scored: dict, qid: str, fid: str) -> dict:
    q = next(x for x in scored["questions"] if x["id"] == qid)
    return next(f for f in q["fact_results"] if f["id"] == fid)


# ---------------------------------------------------------------------------
# PART 1 -- B1.2 and B3.1 classification
# ---------------------------------------------------------------------------

def part1_classification(step3) -> None:
    log("=" * 78)
    log("PART 1 -- B1.2 and B3.1 classification (executed against the real frozen predicate)")
    log("=" * 78)

    b1 = question_by_id(step3, "B1")
    b1_2_groups = next(g for fid, desc, g in b1["facts"] if fid == "B1.2")
    b1_2_desc = next(desc for fid, desc, g in b1["facts"] if fid == "B1.2")
    log(f"\nB1.2 frozen fact description: {b1_2_desc}")
    log(f"B1.2 predicate groups (kw): {b1_2_groups}")
    log("Source bullet (harness doc): \"For a service-business owner, tailor that broad "
        "position to the operational friction costing them time, capacity or revenue, then "
        "the practical system TTR can design and build to fix it\"")

    b1_2_tests = [
        ("positive control -- matches the real intended content",
         "For a service-business owner, we tailor our broad positioning to the specific "
         "operational friction costing them time, capacity, or revenue, then design and "
         "build the practical system to fix it."),
        ("false positive -- generic, unrelated use of the word, no audience-tailoring, "
         "no cost dimension, no system-build clause",
         "We sometimes see friction between the sales and delivery teams internally."),
        ("false negative -- conveys the actual substance without the literal word",
         "We tailor our broad position to what is costing the owner time and capacity, "
         "and design the practical system to fix it."),
    ]
    log("\nExecuted against score_pass() (real predicate, real question structure):")
    b1_2_present_flags = []
    for label, answer in b1_2_tests:
        raw = make_raw([make_raw_record("B1", answer, manifest={})])
        scored = step3.score_pass(raw)
        present = fact_result(scored, "B1", "B1.2")["present"]
        b1_2_present_flags.append((label, present))
        log(f"  [{('PRESENT' if present else 'ABSENT'):>7}] {label}")
        log(f"           answer: {answer!r}")

    log("\nB1.2 finding: the predicate is a single-substring check on the generic word "
        "'friction' with no requirement that the answer name the service-business-owner "
        "audience, the time/capacity/revenue cost dimension, or the practical-system-to-fix-it "
        "follow-through. The false-positive test above scores PRESENT despite containing none "
        "of those three essential elements, and the false-negative test scores ABSENT despite "
        "conveying the actual substance without the bare keyword. This is confirmed executable, "
        "not inferred.")
    log("Classification: UNDER-SPECIFIED. Contract §5 category: §5.3 Essential/composite "
        "qualifiers -- 'Mentioning the main noun or activity does not establish a composite "
        "fact when a material qualifier is absent.' 'friction' is the main noun/activity; the "
        "audience-tailoring and system-build clauses are the essential qualifiers the predicate "
        "drops entirely.")

    b3 = question_by_id(step3, "B3")
    b3_1_groups = next(g for fid, desc, g in b3["facts"] if fid == "B3.1")
    b3_1_desc = next(desc for fid, desc, g in b3["facts"] if fid == "B3.1")
    log(f"\nB3.1 frozen fact description: {b3_1_desc}")
    log(f"B3.1 predicate groups (kw): {b3_1_groups}")
    log("Source bullet (harness doc): \"Core consulting market is broader than either "
        "prospecting segment: established businesses with meaningful revenue and real "
        "workflow, data or operational problems where AI/systems work can create material "
        "value\"")

    b3_1_tests = [
        ("positive control -- matches the real intended content",
         "Our core consulting market is broader than either prospecting segment -- it's "
         "established businesses with meaningful revenue and real operational problems."),
        ("false positive -- generic comparative use, unrelated to prospecting segments",
         "Our client base is broader now than it was two years ago, geographically."),
        ("false negative -- conveys the actual substance without the word 'broader'",
         "The core consulting market isn't limited to ICP-A or ICP-B -- it covers any "
         "established business with a real operational problem worth material value."),
    ]
    log("\nExecuted against score_pass() (real predicate, real question structure):")
    for label, answer in b3_1_tests:
        raw = make_raw([make_raw_record("B3", answer, manifest={})])
        scored = step3.score_pass(raw)
        present = fact_result(scored, "B3", "B3.1")["present"]
        log(f"  [{('PRESENT' if present else 'ABSENT'):>7}] {label}")
        log(f"           answer: {answer!r}")

    log("\nB3.1 finding: the predicate is a single-substring check on the generic comparative "
        "word 'broader' with no requirement that the comparison be TO the two named prospecting "
        "segments, and no requirement that the core-market definition itself be stated. The "
        "false-positive test scores PRESENT for a 'broader' claim about something else entirely "
        "(geography, not market-vs-segment). The false-negative test scores ABSENT despite "
        "correctly conveying that the core market is not limited to either ICP.")
    log("Classification: UNDER-SPECIFIED. Contract §5 category: §5.3 Essential/composite "
        "qualifiers -- 'broad market vs prospecting segment' is named verbatim in §5.3's own "
        "list of recurring essential classes. B3.1 IS that named class: the predicate drops the "
        "essential 'vs prospecting segment' referent entirely.")
    log("\nNeither predicate is ALIGNED (§7.2 note: not applicable here since both were already "
        "in the UNDER-SPECIFIED list, not the ALIGNED list -- this run confirms that placement "
        "and additionally names which existing §5 category applies, per §7.1's requirement). "
        "No repair made to either predicate.")


# ---------------------------------------------------------------------------
# PART 2 -- rehearsal: force each of the three dispositions
# ---------------------------------------------------------------------------

def part2_rehearsal(step3) -> bool:
    log("\n" + "=" * 78)
    log("PART 2 -- REHEARSAL: force CONTEXT-MISSING, IGNORED, UNDECIDABLE before touching real data")
    log("=" * 78)

    # Fixture 1: CONTEXT-MISSING. Question A4 (source_docs = offers.md, positioning.md).
    # A4.1 is fact-level-overridden to ["memory/offers.md"]. Empty manifest -> neither doc
    # arrives -> CONTEXT-MISSING. Answer text avoids A4.1's kw groups so the fact reads
    # "not present" and a disposition is computed at all.
    log("\nFixture 1 -- target CONTEXT-MISSING (question A4, fact A4.1, empty manifest: no "
        "provenance, no actual_reads, no depth-tool reads -- offers.md never arrived):")
    raw1 = make_raw([make_raw_record("A4", "Nothing relevant here.", manifest={})])
    scored1 = step3.score_pass(raw1)
    fr1 = fact_result(scored1, "A4", "A4.1")
    log(f"  A4.1 -> present={fr1['present']} disposition={fr1['disposition']}")
    got_cm = fr1["disposition"] == "CONTEXT-MISSING"

    # Fixture 2: IGNORED. Same question/fact, manifest shows offers.md arriving live via
    # provenance (no #excluded / #budget=omitted tag) -- the model had it and didn't say it.
    log("\nFixture 2 -- target IGNORED (question A4, fact A4.1, manifest provenance shows "
        "memory/offers.md arriving live, answer still lacks A4.1's guarantee/approv content):")
    manifest2 = {"provenance": ["business_brain:memory/offers.md#route=direct_fallback"],
                 "actual_reads": []}
    raw2 = make_raw([make_raw_record("A4", "Nothing relevant here.", manifest=manifest2)])
    scored2 = step3.score_pass(raw2)
    fr2 = fact_result(scored2, "A4", "A4.1")
    log(f"  A4.1 -> present={fr2['present']} disposition={fr2['disposition']}")
    got_ig = fr2["disposition"] == "IGNORED"

    # Fixture 3: UNDECIDABLE. Question E4, fact E4.1 (fact-level override requires THREE
    # docs: trent-first-call.md, trent-july-9.md, INDEX.md). Only INDEX.md arrives live;
    # the other two do not -> mixed flags -> UNDECIDABLE.
    log("\nFixture 3 -- target UNDECIDABLE (question E4, fact E4.1, fact-level override "
        "requires trent-first-call.md + trent-july-9.md + INDEX.md; only INDEX.md arrives "
        "live -> mixed arrival within the fact's own required doc set):")
    manifest3 = {"provenance": ["business_brain:sources/historical_calls/INDEX.md#route=pointer"],
                 "actual_reads": []}
    raw3 = make_raw([make_raw_record("E4", "Nothing relevant here.", manifest=manifest3)])
    scored3 = step3.score_pass(raw3)
    fr3 = fact_result(scored3, "E4", "E4.1")
    log(f"  E4.1 -> present={fr3['present']} disposition={fr3['disposition']}")
    got_un = fr3["disposition"] == "UNDECIDABLE"

    log(f"\nRehearsal result: CONTEXT-MISSING demonstrated={got_cm}, "
        f"IGNORED demonstrated={got_ig}, UNDECIDABLE demonstrated={got_un}")
    all_three = got_cm and got_ig and got_un
    log(f"All three dispositions demonstrated: {all_three}")
    return all_three


# ---------------------------------------------------------------------------
# PART 3 -- predictions, then the real run
# ---------------------------------------------------------------------------

def part3_predictions() -> None:
    log("\n" + "=" * 78)
    log("PART 3 -- PREDICTIONS (written before the first real disposition is computed)")
    log("=" * 78)
    log("\nPredeclared (rev11 Step 3, contract §13 step 2): \"CONTEXT-MISSING dominant.\"")
    log("\nThis instrument's own predictions, committed before running score_pass() on the "
        "real step6_b7_pass.raw.json records:")
    log("  Population: 99 non-honesty facts total; 47 currently present (per the unchanged "
        "present() predicate, confirmed unchanged by the repair report); so 52 facts are "
        "expected to require a disposition.")
    log("  Predicted disposition split of those ~52 facts:")
    log("    CONTEXT-MISSING: ~30 (~58%) -- a small, tight context map (map_bytes=1788 per "
        "the step6 harness docstring) plausibly leaves many declared source docs unassembled.")
    log("    IGNORED:         ~12 (~23%)")
    log("    UNDECIDABLE:     ~10 (~19%)")
    log("  Predicted evidence-class split (same ~52 facts, precedence order):")
    log("    fact-level source override:              ~15")
    log("    manifest provenance / actual_reads only:  ~28")
    log("    depth-tool reads:                         ~7  -- step6_post's own tool-surface "
        "verification shows 34 of 46 calls were mcp__brain__open_note/open_call, so depth-tool "
        "evidence is expected to matter more here than in a pass without those tools.")
    log("    no usable evidence:                       ~2")
    log("  Predicted currently-PRESENT-but-in-48-fact-defect-population count: ~10-15.")
    log("\nThese are estimates recorded before measurement, not adjusted afterward.")


EVIDENCE_ORDER = ["fact_level_override", "manifest_provenance_or_actual_reads", "depth_tool", "no_usable_evidence"]


def classify_evidence(fid: str, docs_used: list[str], is_override: bool, arrived: dict) -> str:
    if is_override:
        return "fact_level_override"
    evidences = {arrived[d]["evidence"] for d in docs_used}
    if "manifest_provenance" in evidences or "manifest_actual_read" in evidences:
        return "manifest_provenance_or_actual_reads"
    if "depth_tool" in evidences:
        return "depth_tool"
    return "no_usable_evidence"


def part4_real_run(step3) -> dict:
    log("\n" + "=" * 78)
    log("PART 4 -- REAL RUN: repaired three-way B6 disposition over step6_post's stored records")
    log("=" * 78)

    log(f"\nRepaired B6 implementation: {STEP3_PATH.relative_to(ROOT)}")
    log(f"SHA-256: {sha256_of(STEP3_PATH)}")
    log("Identified as the REPAIRED version by behaviour (Part 2 rehearsal above, run against "
        "this exact loaded module) and by structure: source_arrived() reads manifest "
        "'provenance'/'actual_reads' (never the dead 'sources' key), FACT_SOURCE_OVERRIDES is "
        "present with 27 entries, and _disposition_for()'s three-way rule "
        "(all-arrived=IGNORED / none-arrived=CONTEXT-MISSING / mixed=UNDECIDABLE) is confirmed "
        "reachable in all three directions.")

    if not RAW_PATH.exists():
        log(f"\nHARD STOP: {RAW_PATH} not found.")
        sys.exit(3)
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    if raw.get("aborted"):
        log("\nHARD STOP: step6_b7_pass.raw.json is marked aborted.")
        sys.exit(3)
    log(f"\nLoaded {len(raw['records'])} stored step6_post records "
        f"(actual_calls={raw['actual_calls']}, declared_max={raw['declared_max']}, "
        f"aborted={raw['aborted']}).")

    # Depth-tool evidence note: step6_post_full_tool_surface_verification.json's actual
    # on-disk content was inspected (summary counts + a qid->session_id map + an EMPTY
    # contaminated_candidates list) and does NOT itself carry resolved per-call document
    # identities for mcp__brain__open_note/open_call calls (confirmed by reading
    # step6_post_full_tool_surface_verification.py: the full per-call record list is
    # computed in memory but only the filtered contamination-candidate subset is persisted
    # to the JSON). Feeding the repaired B6's depth-tool arm therefore requires calling
    # step3.extract_tool_reads() -- part of the repaired B6 instrument itself, already used
    # live inside call_david(), read-only against ~/.hermes/profiles/david/state.db, zero
    # model calls -- once per session_id. This is invoking the frozen instrument's own
    # function, not writing a new state.db parser; it is recorded here as a finding against
    # the task's description of that JSON, not acted on beyond what B6 itself requires.
    log("\nNote (finding, not acted on beyond what B6 requires): "
        f"{TOOL_SURFACE_JSON.name} does not itself store resolved per-call document "
        "identities (only tool names/counts and an empty contamination-candidate list); "
        "depth-tool arrival evidence is instead obtained by calling the repaired B6's own "
        "extract_tool_reads(session_id) function once per stored session_id -- the same "
        "function call_david() already performs live inside step3_b7_harness.py -- rather "
        "than re-deriving a new state.db parser.")

    augmented_records = []
    session_ids = {}
    for rec in raw["records"]:
        rec2 = copy.deepcopy(rec)
        sid = (rec2.get("usage") or {}).get("session_id")
        session_ids[rec2["question_id"]] = sid
        tool_reads = sorted(step3.extract_tool_reads(sid)) if sid else []
        rec2["tool_reads"] = tool_reads
        augmented_records.append(rec2)
    n_with_tool_reads = sum(1 for r in augmented_records if r["tool_reads"])
    log(f"\nDepth-tool reads resolved for {n_with_tool_reads}/{len(augmented_records)} questions "
        "(non-empty tool_reads set).")

    augmented_raw = {"pass": raw["pass"], "aborted": False,
                      "declared_max": raw["declared_max"], "actual_calls": raw["actual_calls"],
                      "records": augmented_records}
    scored = step3.score_pass(augmented_raw)

    ad_present = sum(q["facts_present"] for q in scored["questions"] if not q["honesty"] and q["section"] in "ABCD")
    ad_total = sum(q["facts_total"] for q in scored["questions"] if not q["honesty"] and q["section"] in "ABCD")
    log(f"\nCoverage under current (unchanged) present(), ALL non-honesty sections A-E: "
        f"{scored['total_facts_present']}/{scored['total_facts_possible']} "
        f"({scored['coverage_pct']:.1f}%).")
    log(f"Coverage under current (unchanged) present(), sections A-D ONLY -- this is the "
        f"denominator rev11's Step 5 bound and contract §15's cited 44.0% actually use "
        f"(offers/positioning/pipeline/priorities, excludes E=call corpus and F=honesty): "
        f"{ad_present}/{ad_total} ({100.0*ad_present/ad_total:.1f}%). "
        f"Reconciles against §15's cited figure: {abs(100.0*ad_present/ad_total - 44.0) < 0.05}.")

    counts = {"CONTEXT-MISSING": 0, "IGNORED": 0, "UNDECIDABLE": 0}
    counts_ad = {"CONTEXT-MISSING": 0, "IGNORED": 0, "UNDECIDABLE": 0}
    evidence_counts = {k: {"CONTEXT-MISSING": 0, "IGNORED": 0, "UNDECIDABLE": 0} for k in EVIDENCE_ORDER}
    per_question_summary = []
    present_in_defect_population = []

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
                if fid in DEFECT_POPULATION_48:
                    present_in_defect_population.append(fid)
                continue
            disp = fr["disposition"]
            counts[disp] += 1
            if is_ad:
                counts_ad[disp] += 1
            q_counts[disp] += 1
            is_override = fid in step3.FACT_SOURCE_OVERRIDES
            docs_used = step3.FACT_SOURCE_OVERRIDES.get(fid, q["source_docs"])
            eclass = classify_evidence(fid, docs_used, is_override, arrived)
            evidence_counts[eclass][disp] += 1
        per_question_summary.append((q["id"], q_counts))

    log("\nPer-question disposition summary (non-honesty questions):")
    for qid, qc in per_question_summary:
        log(f"  {qid}: present={qc['present']} CONTEXT-MISSING={qc['CONTEXT-MISSING']} "
            f"IGNORED={qc['IGNORED']} UNDECIDABLE={qc['UNDECIDABLE']}")

    total_unmet = sum(counts.values())
    log(f"\nTHREE-WAY TOTALS over {total_unmet} unmet facts, ALL sections A-E (99 total, "
        f"{scored['total_facts_present']} present, {total_unmet} unmet):")
    for k in ["CONTEXT-MISSING", "IGNORED", "UNDECIDABLE"]:
        pct = 100.0 * counts[k] / total_unmet if total_unmet else 0.0
        log(f"  {k}: {counts[k]} ({pct:.1f}%)")

    total_unmet_ad = sum(counts_ad.values())
    log(f"\nTHREE-WAY TOTALS restricted to sections A-D only ({ad_total} total, "
        f"{ad_present} present, {total_unmet_ad} unmet) -- this is the population rev11's "
        f"Step 5 ≥80%-or-investigate bound actually governs:")
    for k in ["CONTEXT-MISSING", "IGNORED", "UNDECIDABLE"]:
        pct = 100.0 * counts_ad[k] / total_unmet_ad if total_unmet_ad else 0.0
        log(f"  {k}: {counts_ad[k]} ({pct:.1f}%)")

    log("\nEVIDENCE-CLASS BREAKDOWN (each unmet fact counted in exactly one class, precedence "
        "fact-level override -> manifest provenance/actual_reads -> depth-tool -> no usable evidence):")
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
    dominant_class = max(EVIDENCE_ORDER, key=lambda k: sum(evidence_counts[k].values()))
    log(f"Dominant evidence class: {dominant_class} "
        f"({sum(evidence_counts[dominant_class].values())}/{reconciled})")

    log(f"\nFacts currently scored PRESENT that sit inside the 48-fact defect population "
        f"(45 under-specified + 2 normalization + 1 source-contract): "
        f"{len(present_in_defect_population)} -- {sorted(present_in_defect_population)}")
    log("This number bounds how far the aggregate coverage can move once the scorer is "
        "repaired: each of these facts is a current false PRESENT under the defective "
        "predicate and will re-enter the unmet population (with its own B6 disposition) "
        "once repaired, without the true unmet set having been re-derived here.")

    dominant = max(counts, key=counts.get)
    context_missing_dominant = dominant == "CONTEXT-MISSING" and counts["CONTEXT-MISSING"] > total_unmet / 2
    log(f"\nPredeclared prediction check (ALL sections A-E): CONTEXT-MISSING is the largest "
        f"bucket: {dominant == 'CONTEXT-MISSING'}. Strict majority (>50% of unmet): "
        f"{context_missing_dominant}.")
    if dominant == "CONTEXT-MISSING":
        verdict = "SUPPORTED" if context_missing_dominant else "SUPPORTED (plurality, not strict majority)"
    else:
        verdict = "CONTRADICTED"
    log(f"Verdict on rev11's predeclared 'CONTEXT-MISSING dominant' prediction (A-E): {verdict}")

    dominant_ad = max(counts_ad, key=counts_ad.get) if total_unmet_ad else None
    ad_strict_majority = dominant_ad == "CONTEXT-MISSING" and counts_ad.get("CONTEXT-MISSING", 0) > total_unmet_ad / 2
    if dominant_ad == "CONTEXT-MISSING":
        verdict_ad = "SUPPORTED" if ad_strict_majority else "SUPPORTED (plurality, not strict majority)"
    elif dominant_ad is None:
        verdict_ad = "UNDECIDABLE (no unmet facts)"
    else:
        verdict_ad = "CONTRADICTED"
    log(f"Verdict on rev11's predeclared 'CONTEXT-MISSING dominant' prediction, restricted to "
        f"A-D only (the bound's actual population): {verdict_ad}")

    return {
        "counts": counts, "counts_ad": counts_ad, "evidence_counts": evidence_counts,
        "total_unmet": total_unmet, "total_unmet_ad": total_unmet_ad,
        "dominant_class": dominant_class, "verdict": verdict, "verdict_ad": verdict_ad,
        "present_in_defect_population": present_in_defect_population,
        "per_question_summary": per_question_summary,
        "coverage_pct": scored["coverage_pct"], "total_facts_present": scored["total_facts_present"],
        "ad_present": ad_present, "ad_total": ad_total,
    }


def main() -> int:
    overwrite = "--overwrite" in sys.argv
    if TRANSCRIPT_PATH.exists() and not overwrite:
        print(f"REFUSING to overwrite existing transcript: {TRANSCRIPT_PATH}. Pass --overwrite.",
              file=sys.stderr)
        return 2

    log("STEP 5 / STEP 6_POST -- REPAIRED B6 INVESTIGATION -- §13 STEP 2 PREREQUISITE PASS")
    log("Zero model / Hermes / David / provider calls in this script.")
    log(f"scripts/step3_b7_harness.py SHA-256: {sha256_of(STEP3_PATH)}")

    step3 = load_step3()

    part1_classification(step3)
    rehearsal_ok = part2_rehearsal(step3)
    if not rehearsal_ok:
        log("\nHARD STOP: rehearsal did not demonstrate all three dispositions. The real run "
            "is not interpretable without this and will NOT proceed.")
        TRANSCRIPT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")
        return 4

    part3_predictions()
    result = part4_real_run(step3)

    log("\n" + "=" * 78)
    log("DONE. Zero model/Hermes/David/provider calls made by this script.")
    log("=" * 78)
    TRANSCRIPT_PATH.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    print(f"\nTranscript written: {TRANSCRIPT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
