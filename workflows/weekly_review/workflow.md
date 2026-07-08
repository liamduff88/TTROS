---
workflow: weekly_review
skill: skills/weekly_review/SKILL.md
path: workflows/weekly_review/workflow.md
lane: orchestrator
profile: orchestrator
trust: earned
---
# workflow: weekly_review — one weekly brief: shipped, open/blocked, token rollup, signals, next 3
> Revisit: if the receipt or token-ledger schema changes. · Last touched: 2026-07-07.

Recurring workflow: one instance per week (suggested Fri EOD or Mon before /maintain-os), or on Liam's command. Read-and-summarize only.

## Trigger
Weekly schedule fires or Liam requests it. Inputs: the week's open/closed queue items, run_ledger receipts, queue/token_ledger.jsonl window, operating_context/current_priorities.md.

## Completion contract (default)
- **Done** = one brief artifact covering, in order: shipped (by lane, one line each, linked to receipts/artifacts) · open & blocked (with age and what each waits on: Liam / client / external) · token rollup by lane per §8.5 (est_cost from the deterministic script; non-reporting components listed by name under `unavailable`, never estimated) · signals (lanes trending toward §3.3 promotion math, v0 skill uses, stale Revisit stamps handed to /maintain-os) · proposed top-3 next-week priorities against current_priorities.md for Liam to confirm or reorder. Receipt with its own token block.
- **Allowed unprompted** = all reads listed above; drafting the brief.
- **Stop conditions** = token ledger unreadable for the window (report that, don't reconstruct); any impulse to close, delete, or modify queue items mid-review.

## Run
Execute the skill's steps 1–6 in order; brief → `output/YYYY-WW/`; receipt → `receipts/`; run_ledger + token_ledger appended.

## Never
- Estimate missing token numbers.
- Close, delete, or modify queue items during review.
- Fix stale Revisit stamps here — hand to /maintain-os.
- Bury a blocker — blockers lead, not trail.

## Verifier check
All five sections present and the token rollup traces to the ledger window — completeness of structure, not narrative quality.
