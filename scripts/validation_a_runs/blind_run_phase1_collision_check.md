# Validation A — blind run — Phase 1 collision check

**Result: HARD STOP.** Independent derivation resolves 11 candidates-with-sources, not 12.

## Method (independent — no prior preparation artifact read for this derivation)

VAULT_ROOT resolved from `tools/brain_memory.py` (`TTROS_BRAIN_ROOT` env var unset, so the
module default applies):

```
/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain
```

Searched the vault directly (never read `scripts/validation_a_runs/collision_precheck.md` or
`scripts/validation_a_runs/seal_manifest_category_breakdown.md`, both prior-prep artifacts, for
this step) for candidate items with Obsidian wikilinks to call sources. Found them at:

```
sources/historical_calls/MANIFEST.md  ("## Compact durable knowledge candidates")
```

Every bullet in that section was enumerated (`grep -n '^- \`' MANIFEST.md`): 23 bullets total,
across five subsections (`liam_intention`/`third_party_*` with sources; `interpretation`/
`hypothesis`/`uncertainty` with none; `review_tier` and `open_loop` holds with none).

Only the bullets carrying an explicit `Source:`/`Sources:` wikilink field resolve to a source
document at all, so those are the candidate population Phase 1.1 asks about:

* `liam_intention` × 5 (lines 56–60), each with 2–3 source wikilinks.
* `third_party_statement` / `third_party_opinion` × 6 (lines 64–69), each with 1–2 source
  wikilinks.

**Mechanical count: 11**, not 12 (`grep -n '^- \`' MANIFEST.md | grep -c Source` = 11).

No other vault location carries a wikilinked candidate list: a vault-wide grep for
`historical_calls` wikilinks outside `sources/historical_calls/` itself turned up only
`README.md` (a pointer to the index, no candidate content) and two Hermes CLI session logs
(`sessions/2026-08-17_...md`, `sessions/2026-09-01_...md`) — not opened, since the manifest
already gives a definitive, mechanically-countable population and reading further would just be
searching for a way around a count that doesn't match, not deriving it.

## Why 11 and not 12 — contextual evidence, not an assumption used to override the count

`MANIFEST.md`'s own frontmatter:

```
split_from: "sources/historical_calls/INDEX.md"
split_at: "2026-09-02"
hermes_last_write:
  source: "ttros-step0-filing-corrections-2026-09-05"
  at: "2026-09-06T01:18:57Z"
```

The sealed historical adjudication file is dated **2026-09-01** (`00_TTROS_CURRENT_STATE_v2026-09-01.md`,
per the seal manifest). This manifest was edited by a "step0 filing corrections" pass on
**2026-09-05/06** — after that adjudication date. The live vault state Phase 1.1 requires me to
derive from is therefore not guaranteed to be the same 12-item set the historical adjudication
scored. This is offered as context for Liam, not as a basis for silently reconciling the count to
12; per the step prompt, "any other count is a hard stop."

## What was NOT done

* Did not read `scripts/validation_a_runs/collision_precheck.md` or
  `..._category_breakdown.md` (prior prep artifacts).
* Did not open either session log for content.
* Did not touch any of the 46 sealed paths or the adjudication file.
* Did not proceed to the intersection check (1.2), rehearsal (Phase 2), freeze (Phase 3), or any
  model call — the run stops before any of those per the step prompt's own instruction.

## Status

`TTROS_VALIDATION_A_RUN` unset; guard confirmed inert. No budget spent (0 of 20 calls used — the
rehearsal/real-item calls never started). Awaiting Liam's ruling on which 12-item population
(or whether 11 is in fact now the correct population, or whether a different/restored source
should be used) before Phase 1 can complete.
