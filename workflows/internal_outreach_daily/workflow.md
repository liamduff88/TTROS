---
workflow: internal_outreach_daily
skill: skills/internal_outreach_daily/SKILL.md
path: workflows/internal_outreach_daily/workflow.md
lane: revenue
profile: aos-revenue
trust: v0 pre-seeded
workflow: internal_outreach_daily — find + name N ICP-fit prospects, hand off to outreach drafting (find-only, never sends)
> Revisit: after first 3 real runs; when memory/ideal_clients.md or the LinkedIn lane split changes. · Last touched: 2026-07-08
Fills the gap between "find me people" (unnamed) and `linkedin_outreach_prep` (named-prospect drafting only). Chains into `linkedin_outreach_prep` as its own Step 5 — a single command-bar request ("find 5 people to reach out to today") should run both in sequence and land one review package.
Trigger
Queue item with `source: command_bar` (or manually queued), no named prospects, requested count N (default 5), workflow match `internal_outreach_daily` (via queue/command_routes.json "find people"/"outreach" without named prospects, or explicit selection).
Completion contract (default)
Done = artifact with N (or fewer, reasoned) evidenced prospects, each with public signal + ICP score, chained into a `linkedin_outreach_prep` run producing per-prospect connection note + message drafts; combined review package with both artifacts; receipt with token block.
Allowed unprompted = reading memory/ideal_clients.md, memory/positioning.md, memory/offers.md; public-signal search; scoring; invoking `linkedin_outreach_prep` as a chained step with the named, evidenced output.
Stop conditions = fewer than 1 evidenced candidate found (report zero, do not fabricate); any send/connect/message attempt (never allowed); request implies client-scoped delivery (route to `lead_gen_agent` instead — stop and flag).
Run
Execute `internal_outreach_daily` skill Steps 1–4 (scope → search → evidence check → score) → Step 5 chains directly into `linkedin_outreach_prep` Steps 2–5 (angle → draft → CASL check → output) using the evidenced prospect list as input, no re-verification of ICP fit needed since Step 3 already evidenced it. Single combined review package: prospect list + per-prospect drafts. run_ledger + token_ledger appended for both skill invocations. skill_trust.jsonl updated toward v0-marker removal (3 real uses).
Never
Send, connect, or message anyone — ever — without Liam's explicit per-message send action.
Invent prospects, signals, or fit scores.
Run this in place of `lead_gen_agent` for client-scoped delivery.
Draft messages without the evidence-check step having run first.
Verifier check
Every prospect in the final package has a distinct, real public signal (not a templated placeholder) and a message draft that references that specific signal — not a generic opener.