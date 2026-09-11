# Validation A — Fidelity Detector Report

**Status: NEEDS ATTENTION — stopped before detector construction.**

## Plain English

I could not find the 12-item, human-labelled historical-call evaluation set that the v2.1
contract's §6.1 (Validation A) is specified to run against. The contract itself only defines the
*schema and threshold* for Validation A; it does not contain the 12 items. I searched every
location the task authorized (scripts/, docs/ttros/, context/, tools/, tests/, queue/,
decisions/, and the Business Brain vault's `sources/historical_calls/` folder that the contract's
own provenance points to) and found only a candidate *pool* (`MANIFEST.md`, 23 candidate bullets
across five categories, 11 of them with an explicit per-item source mapping) — not a discrete,
already-adjudicated 12-item set, and no file anywhere carries item-level SUPPORTED / NOT
SUPPORTED / error-type labels for these candidates.

The task's own instructions require stopping here rather than improvising: don't create a new
evaluation set, don't infer the 12 items from B7, and stop needs-attention if either the paired
sources or the human label source can't be identified for all 12. Both conditions apply. I did
not build the detector, did not create a blind projection, did not run rehearsal, and made no
model calls, because doing any of that ahead of a resolved item set would not be the frozen,
reproducible Validation A the contract specifies — it would be guessing at the test population.

## 1. Contract path + SHA-256 and SOURCE.sha256 validation

- Path: `docs/ttros/TTROS_B7_SCORING_FIDELITY_CONTRACT_v2.1_2026-09-08.md`
- SHA-256 (computed): `b00e409e143f553ff6b10711a9c0aceff8b80bb2e8141884f8ea4e8d2a543af9`
- `SOURCE.sha256` entry: identical hash, same filename. **MATCH.**
- No competing v1/v2 revision present in `docs/ttros/` for this document.

## 2. Exact 12-item source artifact and SHA-256

**Not found.** No discrete 12-item labelled artifact exists in the authorized search scope. The
nearest related artifact is the candidate pool:

- `sources/historical_calls/MANIFEST.md` (Business Brain vault) — SHA-256:
  `3fbf1cc46c7d011024c8585f42bd27f3d6afbf5c087d6d987eaa09353f87aa0e`, current size 8,850 bytes.
  Contains 23 candidate bullets in five categories (Liam intentions/preferences: 5; third-party
  statements/opinions: 6; interpretations/hypotheses/uncertainty: 5; review-tier holds: 3;
  historical open loops: 4). Only the first two categories (11 items total) carry an explicit,
  mechanically identifiable `Sources:` field pairing the candidate to a specific transcript.
  `docs/ttros/00_TTROS_CURRENT_STATE_v2026-09-08_rev7.md` line 355 describes this file as "audit
  + 12 candidates" at an earlier size (8,688 B); the file has since been touched (current mtime
  2026-09-05, current size 8,850 B) and no longer matches that description exactly, and no
  "audit" (label) content is present in it at all — confirmed by a zero-hit grep for
  SUPPORTED/NOT SUPPORTED/VERIFIED/CORRECT markers.

This is a candidate pool, not the adjudicated 12-item evaluation set §6.1 describes.

## 3. Exact human-label artifact and SHA-256

**Not found.** No file under the authorized search scope (scripts/, docs/ttros/, context/,
tools/, tests/, queue/, decisions/, or the vault) contains an item-level SUPPORTED / NOT
SUPPORTED verdict or named error type for any historical-call candidate. Related-but-distinct
audit files were checked and ruled out (they audit individual B7 §E facts such as E5.4, not a
12-item source→claim candidate set):

- `scripts/step5_step6_b7_reconciliation_audit.md`
- `scripts/step6_b7_section_e_source_relevance_audit.md`
- `scripts/b6_leak_scorer_mechanical_repair_report.md`
- `scripts/b7_cleanup_pass_report.md`
- `scripts/b7_contamination_map_and_clean_subset.md`
- `scripts/b7_honesty_fail_if_mechanical_test.md`
- `decisions/DECISIONS.md`

`git log --all` for filenames matching `validation_a*` or `fidelity_detector*` returned no
results — no such artifact was built and later deleted in this repo's history.

## 4. Blindness method and anti-leak proof

Not applicable — no blind projection was built. No item-level label was read by me or by any
script during this investigation. `MANIFEST.md` (the only candidate-pool file inspected in
detail) was confirmed by mechanical grep to contain zero label/verdict markers, so its
inspection did not expose anything to withhold.

## 5–15. Detector, rehearsal, run, gates, confusion matrix

Not applicable. Detector construction never started; per contract §11 anti-overfitting rules and
the task's explicit STOP instructions, no evaluation set may be improvised.

## 16. Final Validation A result

**PASS/FAIL: NEITHER — STOPPED (NEEDS ATTENTION) at the population-location precondition.**

## 17. What this result licenses / does not license

**Licenses:** nothing about the §5 fidelity vocabulary. This run establishes only that the
12-item historical-call evaluation set referenced by contract §6.1 is not currently locatable as
a discrete artifact in this repository or its connected Business Brain vault under the search
this task authorized.

**Does not license:** any conclusion about whether the nine §5 categories are well-grounded, any
scorer repair, any §8 policy decision, Step 5/6 status, or B7 status.

## 18. Confirmations

- No B7 run: confirmed, 0 runs.
- No scorer edits: confirmed, no scorer file touched.
- No §8 policy decisions made: confirmed.
- David calls: 0
- Hermes calls: 0
- Codex calls: 0
- OpenAI calls: 0
- Claude/Anthropic detector calls: 0 (no detector was built, so none were made or authorized to run)

## What would resolve this

To proceed, Liam needs to either point to the specific file/location holding the canonical
12-item set with its human labels (if it exists outside the searched scope, e.g. not yet
imported into this repo/vault), or confirm that the pool in `MANIFEST.md` combined with a
specific human-adjudication record (to be named) is in fact the intended population — at which
point a fresh Validation A run can be authorized against a confirmed population.
