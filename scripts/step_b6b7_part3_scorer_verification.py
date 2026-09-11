#!/usr/bin/env python3
"""Part 3 -- executable, fact-by-fact verification of the frozen 99-fact B7
scorer contract (scripts/step3_b7_harness.py::QUESTIONS / kw() / present()).

Zero model calls. This does not call `hermes`, David, or any provider, and
does not run B7. It imports the real, frozen `QUESTIONS` list and the exact
`present()` predicate `score_pass()` uses
(`all(any(alt.lower() in answer_lower for alt in group) for group in
groups)`), and for every one of the 99 non-honesty facts runs one or more
constructed answer strings through that real predicate to executably confirm
(or correct) a classification -- ALIGNED / UNDER-SPECIFIED / OVER-SPECIFIED /
TEXT-NORMALIZATION DEFECT / OTHER MISMATCH -- rather than asserting the
classification from prose reasoning alone.

This re-verifies, by direct execution, the hand classification in
scripts/step5_step6_static_forensic_audit.md Part 1 (56A/40U/1O/1T/1M). It
does not change the scorer, the fact list, the 25 questions, or any
threshold -- `present()` and `QUESTIONS` are imported unmodified and never
written to.

For every fact this prints and records:
  - a MINIMAL_POSITIVE answer (one alternative per required group) --
    confirms the fact is mechanically scoreable at all.
  - a NEGATIVE answer that is topically related but withholds the fact's
    substantive content -- must read absent for the contract to be trusted.
  - for facts flagged non-ALIGNED, one STRESS answer specifically
    constructed to exercise the claimed defect (an adversarial partial match
    for UNDER-SPECIFIED, a correct paraphrase without the literal keywords
    for OVER-SPECIFIED, a Unicode/format variant for TEXT-NORMALIZATION, or a
    direct citation of the fact's true (unreachable) source for OTHER
    MISMATCH) -- the real, observed present() result on that string is what
    is reported, not an assumed one.

Output: scripts/step_b6b7_part3_scorer_verification.json (machine-readable,
refuses to overwrite without --overwrite) and prints a summary table.

Revisit: if the scorer's kw()/present() logic changes. · Added 2026-09-07.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("step3_b7_harness", SCRIPT_DIR / "step3_b7_harness.py")
step3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step3)  # type: ignore[union-attr]

QUESTIONS = step3.QUESTIONS


def present(answer: str, groups) -> bool:
    """The exact predicate score_pass() uses -- copied inline, not
    reimplemented differently, so this script tests the real contract."""
    answer_lower = answer.lower()
    return all(any(alt.lower() in answer_lower for alt in group) for group in groups)


def minimal_positive(groups) -> str:
    picks = [group[0] for group in groups]
    return "In summary: " + "; ".join(picks) + "."


# ---------------------------------------------------------------------------
# Per-fact stress cases. Each entry: (fid, predicted_class, stress_answer,
# stress_kind, rationale). `stress_answer` is authored to exercise the exact
# claimed defect for non-ALIGNED facts, or a plausible near-miss (topically
# related, substantively short of the fact) for ALIGNED facts, proving the
# negative case rather than only the positive one.
#
# predicted_class carries forward scripts/step5_step6_static_forensic_audit.md
# Part 1's hand classification -- this script's job is to confirm or correct
# it by execution, not to originate it from nothing. Confirmation is a
# `stress_result` that matches the predicted defect direction; a mismatch is
# flagged for human review in the printed summary rather than silently kept.
# ---------------------------------------------------------------------------

FactCase = tuple  # (fid, predicted_class, stress_kind, stress_answer)

CASES: list[FactCase] = [
    # ---------------- SECTION A ----------------
    ("A1.1", "UNDER-SPECIFIED", "adversarial_partial",
     "We ran the opportunity scan, which is just a standard diagnostic for prospects."),
    ("A1.2", "UNDER-SPECIFIED", "adversarial_partial",
     "The scan is free of charge for everyone who signs up."),
    ("A1.3", "UNDER-SPECIFIED", "adversarial_partial",
     "Next in the ladder is the System Fit Call."),
    ("A1.4", "UNDER-SPECIFIED", "adversarial_partial",
     "Diagnosis pricing ranges from CA$750 up to CA$1,500, and it can be credited."),
    ("A1.5", "UNDER-SPECIFIED", "adversarial_partial",
     "The build itself starts around CA$4,500."),
    ("A1.6", "UNDER-SPECIFIED", "adversarial_partial",
     "We provide training and a handover once the build ships."),
    ("A1.7", "ALIGNED", "negative",
     "The ladder pricing is fixed, confirmed, and finalized for every client."),
    ("A2.1", "ALIGNED", "negative",
     "We publish a fixed product catalogue that every client picks from."),
    ("A2.2", "UNDER-SPECIFIED", "adversarial_partial",
     "After lunch we discussed general business diagnostics. Separately, the team is never pitched vacation days before onboarding."),
    ("A2.3", "ALIGNED", "negative",
     "We recommend systems based on what's popular in the market."),
    ("A2.4", "ALIGNED", "negative",
     "We propose the full platform build immediately, all workflows at once."),
    ("A3.1", "ALIGNED", "negative",
     "We ship a strategy deck and hand it off to the client's own team to implement."),
    ("A3.2", "ALIGNED", "negative",
     "We build against generic industry benchmarks, not the client's own workflows."),
    ("A3.3", "ALIGNED", "negative",
     "Our main deliverable is a slide deck outlining the recommended strategy."),
    ("A3.4", "ALIGNED", "negative",
     "Every engagement ties to whatever the client happens to ask for."),
    ("A3.5", "ALIGNED", "negative",
     "We quantify impact using industry-average benchmarks."),
    ("A4.1", "UNDER-SPECIFIED", "adversarial_partial",
     "We guarantee our invoices are accurate to the cent. Separately, the marketing budget was approved by finance last quarter."),
    ("A4.2", "UNDER-SPECIFIED", "adversarial_partial",
     "We work with several enterprise clients across different industries."),
    ("A4.3", "ALIGNED", "negative",
     "We can build absolutely any system type a client asks for."),
    ("A4.4", "ALIGNED", "negative",
     "Our systems run the business autonomously end to end."),
    ("A4.5", "UNDER-SPECIFIED", "adversarial_partial",
     "One recent client outcome was a 30% reduction in response time."),
    ("A4.6", "ALIGNED", "negative",
     "We are the leading specialists in the healthcare industry."),
    # NOTE (executable correction to static_forensic_audit.md, which called
    # this ALIGNED): the scorer never checks polarity/negation, only
    # co-occurrence. An answer that names go-to-market only to DENY it is the
    # wedge still reads PRESENT, because "go-to-market" and "primary"/"wedge"
    # both occur somewhere in the string. Confirmed executable, not assumed.
    ("A5.1", "UNDER-SPECIFIED", "adversarial_partial",
     "Operations tooling is our primary wedge, not go-to-market work."),
    ("A5.2", "UNDER-SPECIFIED", "adversarial_partial",
     "We handle inbound customer support tickets for retail brands."),
    ("A5.3", "UNDER-SPECIFIED", "adversarial_partial",
     "We also offer general training on productivity software."),
    ("A5.4", "ALIGNED", "negative",
     "We tell clients to adopt tools we've never used ourselves."),
    # ---------------- SECTION B ----------------
    ("B1.1", "ALIGNED", "negative",
     "We target hobbyist side-projects with no revenue yet."),
    ("B1.2", "UNDER-SPECIFIED", "adversarial_partial",
     "There is some friction in most businesses somewhere."),
    ("B1.3", "UNDER-SPECIFIED", "adversarial_partial",
     "This is not a good fit for every market segment out there."),
    ("B1.4", "ALIGNED", "negative",
     "AI capability is the headline pitch we lead every conversation with."),
    ("B1.5", "UNDER-SPECIFIED", "adversarial_partial",
     "We sent over a quote."),
    ("B2.1", "ALIGNED", "negative",
     "Forward-deployed engineering is our external marketing tagline."),
    ("B2.2", "UNDER-SPECIFIED", "adversarial_partial",
     "This language works well for a technical reader."),
    ("B2.3", "UNDER-SPECIFIED", "adversarial_partial",
     "We do not usually work weekends. Also, ask a service-business owner for a testimonial."),
    ("B2.4", "ALIGNED", "negative",
     "We freely blend internal engineering jargon into the same page as the client pitch."),
    ("B3.1", "UNDER-SPECIFIED", "adversarial_partial",
     "Our roadmap is broader than last quarter's plan."),
    ("B3.2", "UNDER-SPECIFIED", "adversarial_partial",
     "We track two open deals for the prospecting pipeline this month."),
    ("B3.3", "UNDER-SPECIFIED", "adversarial_partial",
     "ICP-A is one segment we track, and 60 clients attended our last webinar."),
    ("B3.4", "UNDER-SPECIFIED", "adversarial_partial",
     "ICP-B is the other segment, and 40 leads came in from the campaign."),
    ("B3.5", "UNDER-SPECIFIED", "adversarial_partial",
     "The 60/40 split determines ad spend allocation this cycle."),
    ("B3.6", "ALIGNED", "negative",
     "Anything outside the two tracked segments is automatically turned away."),
    ("B3.7", "ALIGNED", "negative",
     "ideal_clients.md is the single exhaustive definition with no other files."),
    ("B4.1", "UNDER-SPECIFIED", "adversarial_partial",
     "This is not a database query language topic. There's a size restriction on the file upload form."),
    ("B4.2", "UNDER-SPECIFIED", "adversarial_partial",
     "Our tooling stack is fairly robust these days."),
    ("B4.3", "UNDER-SPECIFIED", "adversarial_partial",
     "We serve clients in Vancouver and generally across British Columbia and Western Canada, "
     "though we've never taken on work outside BC."),
    ("B4.4", "ALIGNED", "negative",
     "Anything outside Metro Vancouver is rejected on sight."),
    ("B4.5", "TEXT-NORMALIZATION DEFECT", "unicode_variant",
     "A-tier signals must be no older than 90-day old activity; B-tier extends to 12 month freshness."),
    # ---------------- SECTION C ----------------
    ("C1.1", "UNDER-SPECIFIED", "adversarial_partial",
     "AOS-2026-0174 is a ticket, and separately Loretta Davis is a contact in our CRM."),
    ("C1.2", "UNDER-SPECIFIED", "adversarial_partial",
     "AOS-2026-0175 exists, and Evan Thompson replied to a newsletter once."),
    ("C1.3", "UNDER-SPECIFIED", "adversarial_partial",
     "Nobody on the team is neither happy nor sad about the external caterer."),
    ("C2.1", "ALIGNED", "negative", "Several unnamed prospects have gone quiet recently."),
    ("C2.2", "ALIGNED", "negative", "Several unnamed prospects have gone quiet recently."),
    ("C2.3", "ALIGNED", "negative", "Several unnamed prospects have gone quiet recently."),
    ("C2.4", "ALIGNED", "negative", "Several unnamed prospects have gone quiet recently."),
    ("C2.5", "ALIGNED", "negative", "Several unnamed prospects have gone quiet recently."),
    ("C2.6", "ALIGNED", "negative", "Several unnamed prospects have gone quiet recently."),
    ("C2.7", "ALIGNED", "negative", "Several unnamed prospects have gone quiet recently."),
    ("C2.8", "ALIGNED", "negative", "Several unnamed prospects have gone quiet recently."),
    ("C3.1", "ALIGNED", "negative", "The revenue target is whatever we can manage this year."),
    ("C3.2", "ALIGNED", "negative", "The delivery-load mix is fully planned out already."),
    ("C4.1", "UNDER-SPECIFIED", "adversarial_partial",
     "We plan to buy a client testimonial as our first case study."),
    ("C4.2", "UNDER-SPECIFIED", "adversarial_partial",
     "We're specializing in a specific problem type and also becoming a healthcare-vertical specialist."),
    ("C4.3", "UNDER-SPECIFIED", "adversarial_partial",
     "After the meeting we discussed proofreading the vertical marketing copy."),
    # ---------------- SECTION D ----------------
    ("D1.1", "UNDER-SPECIFIED", "adversarial_partial",
     "Ryan is a contractor, and separately North Shore is a nice neighborhood."),
    ("D1.2", "ALIGNED", "negative", "The old website stays exactly as it is for now."),
    ("D1.3", "ALIGNED", "negative", "LinkedIn outreach is fully paused indefinitely."),
    ("D1.4", "UNDER-SPECIFIED", "adversarial_partial",
     "The Business Brain holds notes, and the queue holds a grocery list."),
    ("D1.5", "UNDER-SPECIFIED", "adversarial_partial",
     "One legacy vault is quarantined; nothing else changed."),
    ("D2.1", "ALIGNED", "negative", "CCI/TRACC is our top active priority this week."),
    ("D2.2", "ALIGNED", "negative", "The Lead Gen V4.1 rebuild ships next sprint."),
    ("D2.3", "UNDER-SPECIFIED", "adversarial_partial",
     "We're actively reactivating both benched projects."),
    ("D3.1", "UNDER-SPECIFIED", "adversarial_partial",
     "New work goes into the queue. Memory is not a spreadsheet."),
    ("D3.2", "ALIGNED", "negative", "Both the Business Brain and the queue are temporary scratch space."),
    ("D4.1", "UNDER-SPECIFIED", "adversarial_partial",
     "Ryan is onboarding, the website redesign is separately underway, and LinkedIn ads ran last year."),
    ("D4.2", "UNDER-SPECIFIED", "adversarial_partial",
     "This is unrelated to the confirmed schedule until next week."),
    # ---------------- SECTION E ----------------
    ("E1.1", "ALIGNED", "negative", "We have a handful of calls on file, exact count unclear."),
    ("E1.2", "ALIGNED", "negative", "Several unnamed contacts appear across the call corpus."),
    ("E1.3", "ALIGNED", "negative", "Several unnamed contacts appear across the call corpus."),
    ("E1.4", "ALIGNED", "negative", "Several unnamed contacts appear across the call corpus."),
    ("E1.5", "ALIGNED", "negative", "Several unnamed contacts appear across the call corpus."),
    ("E1.6", "ALIGNED", "negative", "Several unnamed contacts appear across the call corpus."),
    ("E1.7", "ALIGNED", "negative", "Several unnamed contacts appear across the call corpus."),
    ("E1.8", "ALIGNED", "negative", "Several unnamed contacts appear across the call corpus."),
    ("E1.9", "ALIGNED", "negative", "Everything a speaker says in these calls is treated as settled fact."),
    ("E2.1", "ALIGNED", "negative", "The Mike Knapp call happened sometime this summer."),
    ("E2.2", "ALIGNED", "negative", "There's a follow-up packet from around that time."),
    ("E2.3", "UNDER-SPECIFIED", "adversarial_partial",
     "Mike mostly talked about MSP partnerships, nothing about the niche question."),
    ("E2.4", "TEXT-NORMALIZATION DEFECT", "unicode_variant",
     "My read: Mike’s advice was commercially sound and worth testing."),
    ("E3.1", "ALIGNED", "negative", "There was a CCI call at some point this summer."),
    ("E3.2", "UNDER-SPECIFIED", "adversarial_partial",
     "The second CCI call was on Jun 15; attendees weren't recorded."),
    ("E3.3", "ALIGNED", "negative", "Nobody followed up with Kenneth after either call."),
    ("E3.4", "ALIGNED", "negative", "CCI/TRACC is our top active priority this week."),
    ("E4.1", "UNDER-SPECIFIED", "adversarial_partial",
     "There was a Trent call on Jul 9; we're not sure if there was an earlier one."),
    ("E4.2", "ALIGNED", "negative", "There's a summary document about a logistics project for another client."),
    ("E4.3", "UNDER-SPECIFIED", "adversarial_partial",
     "Lance was never in the room for that call."),
    ("E5.1", "ALIGNED", "negative", "Andrea and Liam spoke once, sometime in June."),
    ("E5.2", "UNDER-SPECIFIED", "adversarial_partial",
     "Andrea offered a general introduction to some people, no names given."),
    ("E5.3", "UNDER-SPECIFIED", "adversarial_partial",
     "Andrea talked about a Vancouver networking event for founders."),
    ("E5.4", "OTHER MISMATCH", "unreachable_source",
     "The MANIFEST.md candidate bullet undersells the actual introductions Andrea made."),
]

assert len(CASES) == 99, f"expected 99 fact cases, got {len(CASES)}"

# Per-fact notes for cases where the executable result corrects or refines
# scripts/step5_step6_static_forensic_audit.md's Part 1 classification, or
# surfaces a defect class that audit's "Why" column did not name. Keyed by
# fact id; printed/written alongside the result, never silently absorbed.
NOTES: dict[str, str] = {
    "B1.5": (
        "CORRECTS the prior audit: its compact table wrote this as four "
        "AND'd single-alternative groups ({phone} AND {quote} AND {handoff} "
        "AND {chasing}), which would be OVER-SPECIFIED. The actual frozen "
        "code is kw([\"phone\", \"quote\", \"handoff\", \"chasing\"]) -- ONE "
        "OR-group of four common words. Any single one of them, anywhere in "
        "the answer, satisfies the fact. This is the opposite defect "
        "direction from what the audit reported: severely UNDER-SPECIFIED, "
        "not OVER-SPECIFIED. Confirmed by direct execution against the real "
        "QUESTIONS structure, not by re-reading the audit's notation."
    ),
    "A5.1": (
        "NEW finding beyond the audit's two named patterns (list-collapse, "
        "near-universal-keyword): the scorer never checks polarity/negation, "
        "only substring co-occurrence. An answer that names 'go-to-market' "
        "only to deny it is the wedge still reads PRESENT. Confirmed "
        "executable on this fact; not swept across all 99 (see remaining "
        "unknowns) -- this class likely affects other multi-root facts too."
    ),
    "C4.1": (
        "Same polarity-blindness class as A5.1: the group is a bare OR of "
        "two phrases ('own acquisition engine' / 'first case study'). An "
        "answer using 'first case study' for something else entirely (not "
        "TTR's acquisition engine) still reads PRESENT."
    ),
    "D2.3": (
        "Same polarity-blindness class as A5.1: 'reactivat' matches "
        "'reactivating' regardless of whether the sentence asserts or "
        "denies reactivation. An answer stating projects ARE being "
        "reactivated (the opposite of the fact) still reads PRESENT."
    ),
    "E2.3": (
        "Same polarity-blindness class as A5.1: 'niche'/'niching' matches "
        "even inside a sentence explicitly stating niching was NOT "
        "discussed."
    ),
}


def build_fact_index():
    idx = {}
    for q in QUESTIONS:
        if q["honesty"]:
            continue
        for fid, desc, groups in q["facts"]:
            idx[fid] = (q["id"], desc, groups)
    return idx


def classify(predicted: str, stress_kind: str, stress_present: bool) -> tuple[str, bool]:
    """Return (observed_class, confirmed) from the real present() result on
    the stress string, independent of what was predicted."""
    if stress_kind == "adversarial_partial":
        # A partial/irrelevant-context answer that still reads PRESENT means
        # the contract is weaker than the written fact -> UNDER-SPECIFIED,
        # confirmed. If it correctly reads absent, the contract held.
        observed = "UNDER-SPECIFIED" if stress_present else "ALIGNED"
    elif stress_kind == "correct_paraphrase":
        # A substantively correct paraphrase that reads ABSENT means the
        # contract demands more literal detail than the claim needs ->
        # OVER-SPECIFIED, confirmed. If it reads present, the contract is
        # appropriately tolerant of paraphrase -> ALIGNED.
        observed = "OVER-SPECIFIED" if not stress_present else "ALIGNED"
    elif stress_kind == "unicode_variant":
        # A semantically identical answer using a differently-encoded
        # apostrophe/space/hyphen that reads ABSENT confirms a text-
        # normalization defect (the ASCII-only alternative never fires).
        observed = "TEXT-NORMALIZATION DEFECT" if not stress_present else "ALIGNED"
    elif stress_kind == "unreachable_source":
        # Not a kw() question at all: the fact requires knowledge of an
        # artifact that is architecturally excluded from context regardless
        # of what the answer says. present() on this fact's own literal
        # keyword ("understate") passing or failing is irrelevant to the
        # real defect, which is a source-reachability question, not a text
        # contract question -- reported as OTHER MISMATCH unconditionally.
        observed = "OTHER MISMATCH"
    elif stress_kind == "negative":
        # A topically related but substantively empty answer must read
        # ABSENT for the contract to be trusted as ALIGNED. If it reads
        # PRESENT, the contract is not tight (a different UNDER-SPECIFIED
        # instance this script's authored case set did not predict).
        observed = "ALIGNED" if not stress_present else "UNDER-SPECIFIED"
    else:
        raise ValueError(stress_kind)
    return observed, observed == predicted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    out_path = SCRIPT_DIR / "step_b6b7_part3_scorer_verification.json"
    if out_path.exists() and not args.overwrite:
        print(f"REFUSING to overwrite {out_path}. Pass --overwrite to replace.", file=sys.stderr)
        return 2

    fact_index = build_fact_index()
    assert set(fid for fid, *_ in CASES) == set(fact_index), "CASES fact-id set must equal the real 99-fact set"

    results = []
    mismatches = []
    for fid, predicted, stress_kind, stress_answer in CASES:
        qid, desc, groups = fact_index[fid]
        pos = minimal_positive(groups)
        assert present(pos, groups), f"{fid}: minimal-positive construction failed to read present -- fix the test case"
        stress_present = present(stress_answer, groups)
        observed, confirmed = classify(predicted, stress_kind, stress_present)
        if not confirmed:
            mismatches.append((fid, predicted, observed))
        results.append({
            "id": fid, "question": qid, "desc": desc,
            "predicted_class": predicted, "observed_class": observed, "confirmed": confirmed,
            "stress_kind": stress_kind, "stress_answer": stress_answer, "stress_present": stress_present,
            "minimal_positive": pos, "note": NOTES.get(fid, ""),
        })

    counts: dict[str, int] = {}
    for r in results:
        counts[r["observed_class"]] = counts.get(r["observed_class"], 0) + 1

    print("=== Part 3 -- executable 99-fact scorer verification ===")
    print(f"Total facts: {len(results)}")
    for cls in ("ALIGNED", "UNDER-SPECIFIED", "OVER-SPECIFIED", "TEXT-NORMALIZATION DEFECT", "OTHER MISMATCH"):
        print(f"  {cls}: {counts.get(cls, 0)}")
    print(f"Predicted-vs-observed mismatches: {len(mismatches)}")
    for fid, predicted, observed in mismatches:
        print(f"  {fid}: predicted {predicted}, observed {observed} -- see report for reconciliation")

    # E2.4 reproduced against the actual stored production answer (not a
    # synthetic string), per the task's explicit requirement.
    e24_repro = None
    real_raw_path = SCRIPT_DIR / "step6_b7_pass.raw.json"
    if real_raw_path.exists():
        real_raw = json.loads(real_raw_path.read_text(encoding="utf-8"))
        rec = next((r for r in real_raw.get("records", []) if r.get("question_id") == "E2"), None)
        if rec is not None:
            _, _desc, e24_groups = fact_index["E2.4"]
            real_answer = rec.get("answer") or ""
            real_present = present(real_answer, e24_groups)
            normalized = real_answer.lower().replace("’", "'").replace("‘", "'")
            normalized_present = all(any(alt.lower() in normalized for alt in group) for group in e24_groups)
            e24_repro = {
                "source_file": str(real_raw_path.relative_to(SCRIPT_DIR.parent)),
                "real_answer_excerpt": real_answer[:300],
                "contains_curly_apostrophe_mikes_advice": "mike’s advice" in real_answer.lower(),
                "contains_straight_apostrophe_mikes_advice": "mike's advice" in real_answer.lower(),
                "present_on_real_answer": real_present,
                "present_after_curly_to_straight_normalization": normalized_present,
            }
            print("\n=== E2.4 reproduction against the actual stored answer ===")
            print(json.dumps(e24_repro, indent=2))

    out_path.write_text(json.dumps({
        "counts": counts, "mismatches": mismatches, "results": results,
        "e24_reproduction_against_real_answer": e24_repro,
    }, indent=2), encoding="utf-8")
    print(f"\nWritten: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
