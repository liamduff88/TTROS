---
name: ai_operations_support
description: Run the AI Operations Support retainer (CA$1,500–6,000/mo) — session cadence, AOA cycles, hub upkeep, renewal visibility.
when-to-use: A support/concierge client is active; monthly cycle tasks or session prep/follow-up are queued. Owner: aos-delivery. Trust: watch.
---
# /ai-operations-support
> Revisit: if retainer structure, cadence, or tiers change. · Last touched: 2026-07-07

## Purpose
Keep retainer clients moving: two 45-min working sessions per month, AOA applied to one workflow per session, everything logged to the client hub so accumulated value is visible at renewal.

## Inputs
- Client entity page, signed retainer scope, client hub path, latest intake form / session notes. Refuse without entity page + scope.

## Monthly cycle
1. **Pre-session** — run `/aoa-working-session` prep: pick the session's one workflow from the intake form and open items in the hub.
2. **Session support** — Liam runs the session; this skill drafts agendas and captures nothing live without approval for recording.
3. **Post-session** — within 24h: call notes, top-3 takeaways, action items (owner + date), decisions, build manifest updates → client hub via `/client-hub`.
4. **Between sessions** — draft replies for the agreed support channel within stated response times; drafts only, Liam sends.
5. **Month close** — one-page month summary: workflows improved, open risks/blockers, next recommended build (the upsell path into scoped builds). Receipt with token rollup for the client lane.

## Never
- External sends/mutations without the approved_external_action flag.
- Scope creep into an unscoped build — flag it as a "next recommended build" instead.
- Mix client data across clients (client-isolation folder check first).
- Let the hub go stale — a stale hub kills renewal.

## Done when
Each session has notes + actions in the hub within 24h; month summary exists; receipt with token breakdown written; renewal-relevant progress visible in the hub.
