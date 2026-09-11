# Phase 4 — post-run, pre-reveal predictions

Written after `phase4_real_item_scores.json` was produced and hashed (sha256
`8cb0a0088b5dc9e4777f05d78105b81777a5819bf4c0394a3ff32a75963b70db`), and BEFORE the sealed
adjudication file has been read or its hash checked. This updates, but does not replace,
`phase3_pre_run_predictions.md` — both stand as the record.

## What the mechanical output actually shows

All 12 items scored **NOT SUPPORTED**. Every item fired multiple reason tags (3–6 each), drawn
broadly across 7 of the 9 tags (`polarity_assertion` and `essential_qualifier` fired on all 12;
`prohibited_opposite`, `temporal_status`, `locality` on most; `attribution` on 3;
`list_coverage` on 2; `normalization` and `source_contract` on none). This is worse than
predicted pre-run (7–9/12 agreement was predicted; the actual behavior is uniform NOT SUPPORTED).

**Root cause, visible in the evidence field itself:** the resolved source "documents" are not
the clean call-note prose the detector was designed against — they are the raw vault historical-
source wrapper files (YAML frontmatter, multiple concatenated candidate-adjacent transcripts,
verbatim-source markers, provenance blocks), tens of thousands of bytes each, often naming a
*different* call than the one the candidate cites. `relevant_sentences()`'s single-content-word
overlap gate is far too permissive against documents this large and this noisy: frontmatter and
transcript filler share incidental words with almost any claim, so most sentences count as
"relevant," and the generic negation/qualifier/opposite-pair keyword lists then fire on
incidental matches throughout. This is exactly the failure mode flagged as a risk in the
pre-run prediction, just more severe than predicted.

## Updated numeric prediction (before reading labels)

**G1: predict FAIL, with agreement around 3–5 of 12** — only the true unsupported items (however
many of the ~4 they turn out to be) can coincidentally match a uniform "NOT SUPPORTED" verdict;
every truly-supported item is a guaranteed disagreement under this output.

**G2: predict PASS, but flag it as likely a DEGENERATE pass, not a meaningful one** — because
most items fired most of the negative-tag vocabulary at once, a human-named error type on a
truly-unsupported item is likely to appear somewhere in that item's fired tag list almost by
construction, not because the detector selectively identified that error type. A G2 PASS under
these conditions does not license "the vocabulary correctly identifies distortion types" — it is
consistent with "the detector fires broadly enough that it can't help matching."

## What this predicts about the overall verdict

Predict **overall FAIL on G1**, which per §6.1 is the run's own declared trigger: *"If either
clause misses, the category vocabulary in §5 is wrong [is the contract's framing] and is revised
before any scorer rule is written."* This report's own assessment (recorded pre-run, unchanged)
is narrower: this specific mechanical operationalization is too blunt against real, noisy,
wrapper-laden source documents — not evidence that the nine-category vocabulary itself is wrong.
That distinction is preserved into the final report regardless of what the reveal shows.
