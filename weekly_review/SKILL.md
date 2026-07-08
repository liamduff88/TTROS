---
name: weekly_review
description: Weekly rollup — open items, the week's receipts, blockers, next week's priorities, plus the token rollup by lane (§8.5). One brief.
when-to-use: Scheduled weekly (suggested Fri EOD or Mon before /maintain-os), or on Liam's command. Owner: orchestrator. Trust: earned.
---
# /weekly-review
> Revisit: if the receipt or token-ledger schema changes. · Last touched: 2026-07-07

## Purpose
One page that tells Liam what moved, what stalled, what it cost, and what's next. Read-and-summarize only.

## Inputs
- Queue: open/closed items for the week. Receipts from run_ledger.
- queue/token_ledger.jsonl for the week's window.
- operating_context/current_priorities.md.

## Steps
1. **Shipped** — completed items by lane, one line each, linked to receipts/artifacts.
2. **Open & blocked** — open items with age; blockers with what they're waiting on (Liam decision / client / external).
3. **Token rollup (§8.5)** — totals by lane from the ledger; est_cost from the deterministic script; components that couldn't report listed under `unavailable` by name — recorded, never estimated.
4. **Signals** — anything trending: a lane heating toward §3.3 promotion math, a v0 skill used, a stale Revisit spotted (hand to /maintain-os, don't fix here).
5. **Next week** — top 3 priorities proposed against current_priorities.md; Liam confirms or reorders.
6. **Output** — one brief artifact + receipt with its own token block.

## Never
- Estimate missing token numbers.
- Close, delete, or modify queue items during review.
- Bury a blocker — blockers lead, not trail.

## Done when
One brief exists covering shipped / open+blocked / token rollup by lane / signals / proposed top 3. Receipt written.
