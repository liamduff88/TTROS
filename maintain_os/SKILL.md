---
name: maintain_os
description: The upkeep verb (§9) — weekly scan + monthly interview. v2 scope adds §3.3 promotion/demotion math, v0-skill usage audit, model_prices.json freshness, ledger unavailable-rate. Never deletes.
when-to-use: Scheduled weekly scan Mon 8am; monthly interview on the 1st; or on Liam's command. Owner: aos-ops. Trust: earned.
---
# /maintain-os
> Revisit: when the rot table, hooks, or scan list changes. · Last touched: 2026-07-07

## Purpose
Keep the OS from rotting. Finds problems and asks; never fixes destructively, never deletes.

## Inputs
- ROT.md rot table · Revisit/Expires stamps across layer files · skill_trust.jsonl, run_ledger, token_ledger · queue/model_prices.json · lane_profiles + §3.3 thresholds.

## Weekly scan
1. **Stale stamps** — every layer file's Revisit/Expires vs today; list overdue.
2. **v0 audit** — pre-seeded skills: uses logged this period? 3 uses → propose removing v0 marker; 90 days unused → propose demotion to note. Propose only.
3. **§3.3 math** — per lane, 3-week trigger check (promotion) and 6-week floor check (demotion). Trigger met → recommendation with ledger cost delta attached.
4. **Ledger health** — token_ledger `unavailable` rate trend; receipts missing token blocks.
5. **model_prices.json** — freshness vs provider changes (monthly minimum).
6. **Output** — findings as multiple-choice questions to Liam's channel; approved changes become queue items. Receipt with token block.

## Monthly interview
Walk the three cadences (§8 v1): monthly interview questions, confirm weekly scans ran, on-contact rule intact. Include `hermes update` check in the monthly cadence.

## Never
- Delete anything (never.md — no delete-on-maintenance).
- Act on a promotion/demotion or v0 change without Liam's answer.
- Estimate ledger numbers to make a trend look complete.

## Done when
Scan list fully walked, findings delivered as decisions-to-make (or "all clean"), receipt written.
