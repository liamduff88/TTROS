# Step 5 -- apply-gate evidence (2026-09-07)

Final map: k=1 (business_model only). Growth stopped at the first pass per the
predeclared noise-allowance rule (see step5_b7_growth_report.md). This file
records the four declared bounds against the k=1 live pass
(scripts/step5_b7_pass_k1.{raw,scored}.json).

## B7 coverage on offers/positioning/pipeline/priorities (sections A-D), >=80% or investigate

- Section A (offers):    12/26 = 46.2%
- Section B (positioning/ICP): 5/21 = 23.8%
- Section C (pipeline/commitments): 11/16 = 68.8%
- Section D (priorities): 7/12 = 58.3%
- Section E (call corpus, not gated at 80%, Step 6 territory): 18/24 = 75.0%

VERDICT: bound NOT met on any of A-D. This is INVESTIGATE, not a hard stop --
the design of record uses "or revert" only for the B2/latency bounds below,
not this one. This is also not a new Step 5 regression: Step 3's baseline
already measured the same underlying shortfall (52.5%/54.5%), and Step 3's
own investigation found the majority of misses are IGNORED (50) not
CONTEXT-MISSING (42) -- i.e. more than half the gap is a reasoning-layer
defect a canonical-fact map cannot fix by construction. A 1-class map
touching none of sections A-D's actual source documents (memory/offers.md,
memory/positioning.md, decisions/DECISIONS.md, operating_context/
current_priorities.md) was never going to move these sections; the growth
loop correctly stopped before reaching class 2 (offers) or class 4 (icp),
which are the classes that could. FINDING, carried forward: Step 6
(corpus/vault behind tools) and, if IGNORED keeps dominating after Step 6,
Step 7 (Context Navigator) are the design-of-record's own remedies for this
gap -- not in scope for this session.

## B2 total <= 96,000 B

Not directly measured at k=1: `total_bytes` in the context_assembler manifest
(the historically-instrumented B2 figure) does not include `.hermes.md`
(that lives in Hermes's own system prompt, outside this repo's assembler).
`.hermes.md` at k=1 is 1,788 B either way -- trivial against the 96,000 B
ceiling. Assembler total_bytes observed this pass: 15,256-45,466 B (mean
33,536 B), all comfortably under 96,000 B. PASS, with the caveat that this
is the same instrument Step 3/production already used, not a new Step-5-wide
"total context including the map" figure (no such combined instrument
exists yet -- flagged, not built, since it wasn't needed for k=1's decision).

## Fresh bytes per turn below today's 45,804 B equivalent, or revert

Observed this pass (assembler manifest total_bytes, the historical fresh-
bytes instrument): min 15,256 B, mean 33,536 B, max 45,466 B (< 45,804 B
baseline on every one of the 25 calls).

DOES NOT SETTLE that this is a Step-5-caused improvement: class 1's only
source document, `memory/company.md`, was ALREADY excluded from
`_scoped_note_block`'s output before Step 5 (it sits in the pre-existing
`fixed` set, loaded instead as the always-on `identity/company` block).
Flipping TTROS_CANONICAL_RANKER_ENABLED off therefore changed nothing about
what this pass's old-ranker path could return -- these fresh-byte numbers
are indistinguishable from pre-Step-5 production behaviour at k=1. The
bound is technically not breached (PASS by the numbers), but Step 5 cannot
yet claim credit for it. A real test of the fresh-bytes claim needs a class
whose source documents the old ranker actually serves today (class 4/6/7)
-- which growth did not reach.

## Latency not worse than the 25.9 s baseline, or revert

Observed this pass (wall-clock per `hermes -p david -z` CLI invocation,
including the harness's own vault-snapshot restore before each call): min
9.7 s, mean 22.3 s, max 60.4 s.

Mean (22.3 s) is below the 25.9 s baseline -- PASS by mean, which is the
comparable unit to the baseline figure (itself a measured average, not a
worst case, per docs/ttros's chat-GPT context pack). One outlier at 60.4 s
is flagged, not hidden; B8 was not re-attached this session to decompose it
into cache-hit/miss (that would be a new B8 exercise, out of this step's
declared 25-call budget, which was spent entirely on the B7 growth pass).

## Net apply-gate verdict

Both bounds carrying "or revert" (fresh bytes, latency) are not breached by
the numbers, so NO REVERT. The coverage bound is not met but is explicitly
"investigate" language, not "revert" language, and the investigation above
attributes the shortfall to a pre-existing, already-diagnosed condition
(Step 3), not to this step's change. The live state --.hermes.md at k=1,
TTROS_CANONICAL_RANKER_ENABLED unset/off by default, context_file_max_chars
pinned to 40,000 in the david profile only -- STANDS as this step's result.

Rollback, if ever needed: `export TTROS_CANONICAL_RANKER_ENABLED=1` (restores
the old ranker for the manifest-covered documents) and/or remove
`.hermes.md` at the repo root. No backup restore is needed for either --
both are flag/file flips, per the design of record ("rollback is flipping
the flag").
