---
name: internal_outreach_daily
description: Find and name N ICP-fit prospects for Liam's own outreach (not client delivery) from public signals, then hand off named prospects to /linkedin-outreach-prep for drafting. Never sends, never connects, never runs client lead-gen.
when-to-use: Liam asks to "find N people to reach out to" without naming prospects himself. Owner: aos-revenue. Trust: v0 pre-seeded.
---
# /internal-outreach-daily
> Revisit: when ICP (`business_brain:memory/ideal_clients.md`), offers, or the LinkedIn lane split changes. · Last touched: 2026-07-15

## Purpose
Close the gap between "find me people" (not covered — `linkedin_outreach_prep` refuses unnamed requests) and "draft messages for these named prospects" (`linkedin_outreach_prep`'s job). This skill only finds and evidences prospects; it never drafts outreach copy itself — Step 5 hands off to `/linkedin-outreach-prep` for that. This is Liam's own prospecting, distinct from `lead_gen_agent` (client-delivery, post-Fit-Call, client CRM/entity-page bound).

## Inputs
- Requested count N (default 5 if unstated).
- `business_brain:memory/ideal_clients.md` — ICP definition and fit signals (source of truth for matching).
- `business_brain:memory/positioning.md`, `business_brain:memory/offers.md` — for relevance framing only, not drafting.
- Public LinkedIn/web signals only — no scraping beyond existing legitimate tooling; no purchased lists, no private data.

## Steps
1. **Scope** — confirm N and any stated focus (industry, geography, trigger event). Default geography per `business_brain:memory/ideal_clients.md` (Vancouver/Metro Vancouver/BC/Canada, remote NA where practical).
2. **Search** — identify N+buffer candidate businesses/individuals matching ICP fit signals (inbound-lead-dependent service businesses, visible operational friction signals) via public search only.
3. **Evidence check** — for each candidate, record the specific public signal observed (a post, a hiring listing, a visible workflow gap, a business-change signal). Drop any candidate with no verifiable public signal — do not pad the list with weak fits.
4. **Score** — rank by ICP fit strength using `business_brain:memory/ideal_clients.md` criteria; select top N with evidence.
5. **Handoff** — pass the N named, evidenced prospects to `/linkedin-outreach-prep` for angle/drafting. Do not draft messages in this skill.
6. **Output** — artifact: N prospects with name/entity, one-line why-fit, evidence source, ICP score. Receipt with token block. Do not create or infer prospect Brain paths; record an entity-page proposal only when the work item supplied an exact pointer.

## Never
- Draft outreach messages, connection notes, or angles — that's `/linkedin-outreach-prep`'s job.
- Send, connect, or message anyone.
- Invent a prospect, a signal, urgency, or fit — undocumented signal means the candidate is dropped, not included with a guess.
- Run client-scoped lead generation (that's `lead_gen_agent`, signed-scope only).
- Use purchased lists, scraped private data, or non-public sources.

## Done when
Artifact lists exactly N (or fewer, with a stated reason if fewer) evidenced prospects, each with a real public signal and ICP score, handed to `/linkedin-outreach-prep`. Receipt written.
