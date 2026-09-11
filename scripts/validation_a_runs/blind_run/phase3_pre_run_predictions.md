# Phase 3 — pre-run predictions (written BEFORE reading any of the 14 sealed
sources, before lifting the Phase 2A guard extension, before scoring any of
the 12 items)

Per evidence discipline: predicted here, in writing, before the check runs — not reverse-engineered
from a result.

## Basis available for this prediction

Only: the 12 candidate claim texts (`bullet_text` in `blind_run_phase1_freeze.json`, already
legitimately read as part of the allowed "candidate claim" input) and the frozen detector's own
rule design/rehearsal behavior (`phase2b_deterministic_rehearsal.txt`). No source document content.
No historical label. No adjudication file.

## Prediction

**G1 (verdict agreement ≥10/12): predict FAIL.** Reasoning: the frozen rules trigger on generic
lexical cues (negation words, qualifier words like "only"/"pending"/"explicitly", temporal words
like "currently"/"finalized", the fixed opposite-pairs table) anywhere a claim-overlapping source
sentence contains them — real call-note prose is likely to contain such words incidentally (e.g. a
sentence elsewhere in a source using "not" or "only" for an unrelated clause), which the
`relevant_sentences()` overlap gate does not fully filter out. I expect this produces **false
NOT SUPPORTED verdicts on some of the ~8 candidates the frozen human labels call supported** —
specifically, my numeric prediction is **7–9 of 12 verdicts agreeing with the withheld labels**,
below the declared 10/12 threshold.

**G2 (reason-tag match on ≥3 of the ~4 known-unsupported items): predict borderline PASS.**
Reasoning: the ~4 unsupported items are (per the contract's own framing) exactly instances of the
five shared error types this vocabulary targets, and the detector's tag vocabulary is a direct,
literal implementation of §5 — so where the detector does correctly land on NOT SUPPORTED for a
truly-unsupported item, the fired tag is likely to line up with the human's named error type more
often than chance. Numeric prediction: **2–4 of 4** (not confidently ≥3, given the same
false-positive noise from clause 1 could also produce a *wrong* tag on a truly-unsupported item by
firing an unrelated rule first).

## What licenses what

A PASS on both licenses only "the nine-category vocabulary, mechanically operationalized this
way, agrees with a human often enough on this 12-item set" — never that the specific rules here
are correct implementations of §5 (that is Validation B's job, and does not apply to this
zero-model-call Validation A instrument at all since there is no scorer being flip-reviewed here).
A FAIL is equally informative: per §6.1, "If either clause misses, the category vocabulary in §5
is wrong" is the contract's own claim — this run's more likely conclusion, given how these rules
are built, is that **this particular deterministic operationalization is too blunt** (over-fires
on generic lexical cues), which is a narrower, weaker claim than "the vocabulary itself is wrong."
That distinction is recorded now so it does not get blurred after the result is seen.
