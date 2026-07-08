---
name: proposal_prep
description: /proposal-draft — drafts a proposal from offer templates + the client entity page. Artifact + receipt. Never sends. (Blueprint V2 names this earned skill /proposal-draft; filed here as proposal_prep per batch prompt.)
when-to-use: A Fit Call, scan, or assessment produced a recommended next step and Liam asks for the proposal. Owner: aos-revenue. Trust: earned.
---
# /proposal-draft
> Revisit: when offers, pricing, or delivery terms change. · Last touched: 2026-07-07

## Purpose
Turn a scoped recommendation into a send-ready proposal draft in Liam's voice, priced only from approved offer facts.

## Inputs
- Client/prospect entity page (required — refuse without it).
- The originating artifact: Fit Call brief, Quick-Win Scan (CA$350), or Business Efficiency Assessment (CA$750) output.
- memory/offers.md + sales_and_revenue context for pricing floors (Speed-to-Lead from CA$1,000; Voice Agent from CA$1,000 + platform/usage; Client Memory from CA$2,000; Lead Gen Agent scoped after Fit Call; custom work SCOPE-LOCKed).

## Steps
1. **Ground** — pull the client's stated bottleneck and the recommended build from the entity page + source artifact. No new diagnosis here.
2. **Scope** — deliverables, exclusions, acceptance criteria, and human-approval gates, mirrored from the relevant playbook's stages.
3. **Price** — from approved offer ladder only. Anything off-ladder → mark `PRICE: Liam to set` — never invent a number.
4. **Draft** — problem → proposed build → what it will/won't do without approval → scope → price → timeline placeholder → next step. Plain language, no guaranteed outcomes.
5. **Output** — artifact + receipt with token block. Do not send; do not update CRM/email.

## Never
- Send, or commit price/scope beyond the approved ladder (that judgment is Liam's).
- Promise ROI numbers or timelines Liam hasn't approved.
- Draft without an entity page and a source artifact.

## Done when
Proposal artifact exists with scope, exclusions, acceptance criteria, ladder-based (or Liam-flagged) pricing, and next step. Receipt written.
