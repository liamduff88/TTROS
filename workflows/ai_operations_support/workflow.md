---
workflow: ai_operations_support
skill: skills/ai_operations_support/SKILL.md
path: workflows/ai_operations_support/workflow.md
lane: delivery
profile: aos-delivery
trust: watch
---
# workflow: ai_operations_support — run one client's monthly retainer cycle (CA$1,500–6,000/mo)
> Revisit: if retainer structure, cadence, or tiers change. · Last touched: 2026-07-07.

Recurring workflow: one instance per client per month, not per build. Same folder, month-stamped outputs.

## Trigger
Active retainer client with entity page + signed retainer scope + client hub path; monthly cycle opens, or a session-prep / follow-up item is queued.

## Completion contract (per month)
- **Done** = both sessions supported per the skill's monthly cycle: agendas drafted pre-session via `/aoa-working-session` prep; call notes, top-3 takeaways, action items (owner + date), decisions, and build-manifest updates in the client hub via `/client-hub` within 24h of each session; one-page month summary (workflows improved, risks/blockers, next recommended build) delivered; receipt with token rollup for the client lane.
- **Allowed unprompted** = hub reads, agenda drafts, notes drafting, month-summary drafting, support-channel reply *drafts*.
- **Stop conditions** = missing entity page or signed scope (refuse); any external send/mutation without `approved_external_action` — Liam sends all replies; work sliding into an unscoped build; client-isolation check fails.

## Run
1. Pre-session: pick the session's one workflow from intake form + open hub items; draft agenda → `output/YYYY-MM/`.
2. Post-session (≤24h): notes + actions + decisions → client hub.
3. Between sessions: reply drafts only, within stated response times.
4. Month close: month summary → `output/YYYY-MM/`; receipt → `receipts/`; run_ledger + token_ledger appended.

## Never
- Send anything externally; drafts only.
- Scope-creep into an unscoped build — log it as "next recommended build" (the upsell path).
- Mix client data across clients.
- Let the hub go stale — a stale hub kills renewal.

## Verifier check
Hub timestamps show ≤24h post-session logging and a month summary exists — renewal visibility is the contract, not session vibes.
