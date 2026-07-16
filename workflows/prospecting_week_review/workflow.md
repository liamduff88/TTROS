---
workflow: prospecting_week_review
skill: skills/prospecting_week_review/SKILL.md
path: workflows/prospecting_week_review/workflow.md
lane: revenue
profile: aos-revenue
trust: v0 pre-seeded
---
# workflow: prospecting_week_review — weekly ledger rollup and cycle-end ICP proposals (read + report, never edits memory)
> Revisit: after the first cycle review. · Last touched: 2026-07-16

Companion to `prospecting_daily_run`: the daily loop writes the ledger,
this reads it. Runs at standard reasoning effort always — this is the
step that proposes ICP changes.

## Trigger
Queue item every Friday (after the daily run's follow-up sweep),
workflow match `prospecting_week_review`; the 4th run of a cycle is
automatically the cycle review.

## Completion contract (default)
- **Done** = weekly report artifact: integrity flags, funnel vs cycle-1
  targets, segment cuts (lane / signal_class / icp_variant / angle_type
  / first_touch_style) with sample sizes shown, tier-accuracy check,
  query performance. Week-4 runs additionally contain evidence-cited
  proposals (ICP files, 60/40 split, rotation, query bank, LinkedIn
  Premium decision) formatted for `memory_promotion`. Receipt with
  token block.
- **Allowed unprompted** = reading the full ledger, ICP files, query
  bank, rotation plan, prior review artifacts; computing all metrics.
- **Stop conditions** = ledger missing or majority-invalid rows (stop,
  flag integrity, produce no metrics from bad data); any attempt to
  write to canonical Business Brain memory, the query bank, or rotation plan (never
  allowed — proposals only); segment conclusions requested on <20 sends
  (report INSUFFICIENT SAMPLE instead).

## Run
Execute `prospecting_week_review` skill Steps 1–6 (integrity → funnel →
segments → tier accuracy → queries → artifact); on week-4 runs add
Step 7 (cycle proposals). Approved proposals flow through the existing
`memory_promotion` skill — this workflow's output is its input.
run_ledger + token_ledger appended; skill_trust.jsonl updated toward
v0-marker removal (3 real runs).

## Never
- Edit memory files, the query bank, or the rotation plan.
- Smooth over logging gaps — an unlogged week is reported as unknown,
  not zero.
- Propose more than 2 variable changes per cycle.

## Verifier check
Every metric in the report traces to countable ledger rows; every
segment shows its sample size; every week-4 proposal cites specific
prospect_ids or row counts as evidence; no memory file was modified by
this run.
