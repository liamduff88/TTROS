# Phase 5 — reference labels, G1/G2, and final Validation A verdict

Derived independently from `00_TTROS_CURRENT_STATE_v2026-09-01.md` (sha256 verified against the
sealed `87f60511…0fccc` before this file was read — see Phase 4 hash-check output), section
"KNOWN CAPABILITY REGRESSION, TAKEN KNOWINGLY, 2026-09-02" → "The parked material was checked
against the transcripts, 2026-09-02. Eight of twelve bullets hold as written; four must be
corrected before promotion."

## Reference-label derivation (mine, not copied from any prior report)

The adjudication file numbers bullets `#5`–`#8` by their `sources/historical_calls/MANIFEST.md`
position, which matches the freeze file's `position` field 1:1 by content (candidate text and
source set are identical): `#5`↔position 5 (niching), `#6`↔position 6 (unpaid work), `#7`↔position
7 (CCI ICP), `#8`↔position 8 (Kenneth quantifying time savings) — all four confirmed by matching
subject matter and cited sources against the freeze file, not by number alone.

| position | reference verdict | named human error (my reading) | closest §6.1 tag(s) |
|---|---|---|---|
| 1 | SUPPORTED | — | — |
| 2 | SUPPORTED | — | — |
| 3 | SUPPORTED | — | — |
| 4 | SUPPORTED | — | — |
| 5 | **NOT SUPPORTED** | "on Jul 21 it is Mike's advice... wrong attribution" | `attribution` |
| 6 | **NOT SUPPORTED** | "flattens a real tension... a segment-specific offer, not a principle" | `essential_qualifier` |
| 7 | **NOT SUPPORTED** | "UK targeting is an under-read... says America, UK and Europe" | `essential_qualifier` or `list_coverage` |
| 8 | **NOT SUPPORTED** | "time-savings half is not corroborated... not promotable on current evidence" | `essential_qualifier` or `list_coverage` |
| 9 | SUPPORTED | — | — |
| 10 | SUPPORTED | — | — |
| 11 | SUPPORTED | (noted as understating sources, but explicitly still counted among the eight that "hold as written") | — |
| 12 | SUPPORTED | (same understatement note as #11; still counted among the eight) | — |

8 SUPPORTED / 4 NOT SUPPORTED — matches the contract's own "≈8 supported, ≈4 needing correction"
framing exactly.

## Detector output (from `phase4_real_item_scores.json`, sha256
`8cb0a0088b5dc9e4777f05d78105b81777a5819bf4c0394a3ff32a75963b70db`, produced and hashed BEFORE
this file was read)

All 12 items scored **NOT SUPPORTED**.

## G1 — verdict agreement, threshold ≥10/12

Agreement = items where detector verdict == reference verdict. Detector said NOT SUPPORTED
everywhere, so agreement = exactly the reference-NOT-SUPPORTED items: positions 5, 6, 7, 8.

**G1 = 4/12. FAIL** (threshold ≥10/12; declared and unmoved since Phase 0).

This number requires no tag-matching judgment call — it is a direct verdict comparison, and it
matches the pre-run prediction directionally (predicted FAIL) though the actual count is worse
than the pre-run 7–9/12 guess and in line with the more severe post-run, pre-reveal prediction of
3–5/12.

## G2 — reason-tag match on the 4 reference-NOT-SUPPORTED items, threshold ≥3/4

| position | detector tags fired | reference tag | tag present in fired set? |
|---|---|---|---|
| 5 | polarity_assertion, prohibited_opposite, essential_qualifier | attribution | **NO** |
| 6 | polarity_assertion, prohibited_opposite, temporal_status, essential_qualifier | essential_qualifier | YES |
| 7 | polarity_assertion, essential_qualifier, locality | essential_qualifier (or list_coverage) | YES (if essential_qualifier accepted) / NO (if list_coverage required) |
| 8 | attribution, polarity_assertion, prohibited_opposite, temporal_status, essential_qualifier, locality | essential_qualifier (or list_coverage) | YES (if essential_qualifier accepted) |

Mechanical count on the most charitable reading: **G2 = 3/4, PASS** (threshold ≥3/4).

**This PASS is flagged as degenerate, per the post-run pre-reveal prediction filed before this
file was read.** `essential_qualifier` fired on **all 12 of 12** scored items, including all 8
reference-SUPPORTED ones (see `phase4_real_item_scores.json`) — it is not selective, so its
presence on 3 of the 4 NOT SUPPORTED items is not evidence the detector identified those items'
*specific* distortion type; it is consistent with the detector firing that tag unconditionally.
The one tag that *is* discriminating enough to matter here — `attribution`, the specific error
the human named for position 5 — the detector **did not fire on the item it was needed for**
(fired on position 8 instead, where the human's note names something closer to an uncorroborated
compound claim, not an attribution error). A stricter, non-degenerate reading of G2 — counting
only tags that were not firing near-universally across the population — would score this **0 or
1 of 4**, not 3.

## Overall Validation A verdict

**FAIL.** G1 alone (4/12 against a ≥10/12 threshold) settles it regardless of how G2 is read —
both clauses are required per §6.1, and G1 misses by a wide margin.

## What this FAIL licenses, and what it does not

Per §6.1's own framing, a clause miss means "the category vocabulary in §5 is wrong" is the
result this run exists to be able to produce. This report's own, narrower, evidence-grounded
reading (declared in `phase3_pre_run_predictions.md` before any real item was scored, and
confirmed by inspecting the actual evidence spans in `phase4_real_item_scores.json`) is:

**This deterministic instrument's specific rules are too blunt for the actual source material,
not proof the nine-category vocabulary itself is unsound.** The resolved source documents are
raw vault `historical_source` wrapper files — YAML frontmatter, verbatim-source markers,
provenance blocks, and (per each item's `sources[]` list) multiple concatenated files often
running 30,000–75,000 bytes each, frequently containing transcript content from calls *other
than* the one a given candidate cites (visible directly in several evidence fields above, e.g.
item 1's evidence quotes a Mike Knapp passage despite being sourced to CCI/Kenneth calls — the
concatenation of multiple source files per item, not a detector bug, produces this). The
detector's single-shared-content-word relevance gate is far too permissive against material this
large and this noisy, so its negation/qualifier/temporal/opposite-pair keyword checks fire on
incidental matches throughout, collapsing every item to NOT SUPPORTED regardless of true label.

**What a PASS would have licensed:** that this mechanical operationalization of the nine
categories agrees with a human often enough on this population. **What this FAIL does NOT
license:** that the nine §5 categories fail to name real distortions in TTROS material — the
adjudication text itself (§ "KNOWN CAPABILITY REGRESSION" corrections for #5–#8) independently
describes exactly those distortion types in ordinary language (wrong attribution, a flattened
qualifier, an under-read list/qualifier, an uncorroborated compound claim) without needing this
detector at all. **What it does not decide either:** whether the vocabulary needs revision per
§6.1's own text — that is a judgment call for Liam given this specific instrument's identified
defect (relevance-gate too permissive against raw wrapper documents), separate from the
vocabulary question.
