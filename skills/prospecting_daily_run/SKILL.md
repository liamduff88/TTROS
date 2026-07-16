---
name: prospecting_daily_run
description: The daily LinkedIn prospecting loop — discover 5 evidenced ICP-fit prospects per the rotation plan, score, draft outreach, write ledger rows, surface due follow-ups. Wraps internal_outreach_daily + linkedin_outreach_prep and adds ledger instrumentation. Never sends.
when-to-use: Every prospecting weekday, morning. Owner: aos-revenue. Trust: v0 (pre-seeded — hardened by first 3 runs; approval to be logged in decisions/DECISIONS.md).
---
# /prospecting-daily-run
> Revisit: after first 3 runs, then at each cycle review. · Last touched: 2026-07-16

## Purpose
Turn the existing find + draft skills into an instrumented daily ritual
with ≤30 min of Liam's time. Every prospect gets a ledger row; every
state change gets logged; the weekly review turns the log into ICP
decisions. This engine is also portfolio proof for the GTM-engineer
positioning.

## Inputs
- `business_brain:memory/prospecting_rotation_plan.md` — today's lane + ICP split.
- `business_brain:memory/ideal_clients.md` (router) → canonical ICP-A / ICP-B notes.
- `business_brain:memory/prospecting_query_bank.md` — today's queries.
- `business_brain:memory/prospecting_scoring_contract.md` — seven gates,
  reproducible 100-point score, tiers, and hard caps.
- `queue/prospects.jsonl` + `queue/prospect_status_vocabulary.md` —
  duplicate/do-not-contact checks, follow-up due dates.
- Config: first_touch_style = `noted_request` only when Liam confirms LinkedIn
  Premium is active; otherwise use `blank_request` + post-acceptance DM.
- Optional: paste-in candidate table from the ChatGPT discovery arm,
  in ledger-schema columns — merges at Step 3, same gates apply.

## Steps
1. **Follow-up sweep first** — read the ledger: surface prospects with
   `next_touch_due` ≤ today (draft touch_2/touch_3 per V4.1 three-touch
   formulas; InMail variant allowed as touch_3 for A-tier), and flag
   connection requests pending ≥7 days for withdrawal.
2. **Discover** — run `internal_outreach_daily` Steps 1–4 scoped to
   today's lane/variant and query bank: N=5 evidenced, scored prospects.
   Ledger check before acceptance: skip duplicates and do_not_contact.
3. **Gate** — canonical wedge sentence + freshness + seven gates per
   candidate. Drop, don't pad. Fewer than 5 with a stated reason beats
   5 with soft evidence.
4. **Draft** — chain into `linkedin_outreach_prep`: per prospect, either a
   blank connection request when the fallback is active or a ≤180-character
   signal-specific, zero-pitch note, plus a post-acceptance first message in
   Liam's voice with one low-friction next step. Tag each with `angle_type`.
5. **Ledger write** — append one full-snapshot row per new prospect with
   status `drafted`, per schema. Log the source query in `source_query` and
   the lawful outreach basis in `outreach_basis`. Create/update the canonical
   Business Brain prospect entity page using sourced facts only. Later state
   changes append another full snapshot; never rewrite history.
6. **Review package** — one artifact: due follow-ups on top, then new
   prospects (evidence line, wedge, score/tier, note + message drafts).
   Liam sends manually and logs `sent` / `rejected` same day.
7. **Receipt** — standard receipt with token block; run_ledger +
   skill_trust updated for the chained skills.

## Never
- Send, connect, message, or withdraw anything — Liam does all
  platform actions.
- Invent prospects, signals, scores, or ledger states.
- Exceed 3 touches or contact a do_not_contact record.
- Substitute for `lead_gen_agent` (client-scoped delivery).
- Write to the ledger without schema-valid fields.

## Done when
Follow-up sweep surfaced (or explicitly empty); N (or fewer, reasoned)
new prospects each with evidence, wedge, drafts, and a ledger row; one
review package artifact; receipt written.
