---
workflow: marketing_content
skill: skills/content_draft/SKILL.md
path: workflows/marketing_content/workflow.md
lane: marketing
profile: aos-marketing
trust: earned
---
# workflow: marketing_content — produce one publish-ready content draft (draft-only, never publishes)
> Revisit: when marketing_voice or positioning changes. · Last touched: 2026-07-15.

Workflow name differs from skill (`content_draft`) — named for the lane's deliverable, per workflows/README.md; mapping is explicit here.

## Trigger
Queue item with a content brief or topic (one piece per item), from Liam directly or the marketing lane's authority cadence.

## Completion contract (default)
- **Done** = one draft artifact attached to the queue item: answer-first (AEO) opening, drafted in marketing_voice, voice-checked against `business_brain:memory/marketing_voice.md`, offer/pricing facts only from `business_brain:memory/offers.md` + `business_brain:memory/sales_and_revenue.md`, stated target placement noted (not published); receipt with token block.
- **Allowed unprompted** = reading `business_brain:memory/marketing_voice.md` + `business_brain:memory/positioning.md` (both, every time), `business_brain:memory/offers.md`; drafting and voice-checking.
- **Stop conditions** = no brief/topic on the item; the piece would require a claim on the offers.md "do not claim" list; anything that publishes, schedules, or posts (never allowed regardless of flags in this workflow).

## Run
Execute the skill's steps in order: frame (audience + the one leak/lever: effectiveness / efficiency / quality + next step) → answer-first block → draft → voice check → output artifact + receipt. run_ledger + token_ledger appended.

## Never
- Publish, schedule, or post anywhere.
- Claim revenue lift, savings, or timelines not approved by Liam; no guaranteed-outcome claims.
- Reference clients by name unless already public in context files.
- Invent offer or pricing facts.

## Verifier check
Artifact opens with a direct answer, passes a re-read against marketing_voice.md, and names its target placement — presence of all three, not general polish.
