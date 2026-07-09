---
workflow: linkedin_carousel_from_md
skill: skills/linkedin_carousel_from_md/SKILL.md
path: workflows/linkedin_carousel_from_md/workflow.md
lane: marketing
profile: aos-marketing
trust: v0 pre-seeded
workflow: linkedin_carousel_from_md — sourced .md → LinkedIn carousel review package (draft-only, never publishes)
> Revisit: after first 3 real runs; when marketing_voice, positioning, or dashboard P2.5 schema changes. · Last touched: 2026-07-08
First slice of Dashboard P2.5 Workflow Action Packages. Manual LinkedIn handoff only — direct publish is a separate, later, explicitly-gated capability.
Trigger
Queue item with `source: command_bar` (or manually queued), a `.md` source file in `source_refs`, and workflow match `linkedin_carousel_from_md` (via queue/command_routes.json or explicit selection).
Completion contract (default)
Done = `post_package.json` status `ready_for_review`; package contains `source.md`, `carousel_draft.md`, `linkedin_caption.md`, `carousel.pdf`, `review_receipt.md`, `post_package.json`; caption and slides voice-checked; receipt has a token block.
Allowed unprompted = reading memory/marketing_voice.md + memory/positioning.md (both, every time), memory/offers.md if source touches pricing; drafting slides/caption; deterministic PDF render.
Stop conditions = no `.md` source attached; source contains a claim on the offers.md "do not claim" list; anything that would post, schedule, connect, or publish (never allowed regardless of flags).
Run
Execute skill steps in order: frame → slide plan → caption → voice check → render (deterministic, no model call) → package. Package lands at `workflows/linkedin_carousel_from_md/output/{item_id}/`. Status set to `ready_for_review`, surfaced on the operator dashboard. run_ledger + token_ledger appended. skill_trust.jsonl updated toward v0-marker removal (3 real uses).
Never
Publish, schedule, connect, or post anywhere, under any approval flag.
Claim revenue lift, savings, or timelines not approved by Liam.
Reference clients by name unless already public in context files.
Invent offer or pricing facts.
Verifier check
`post_package.json` status is `ready_for_review`, all 5 artifacts present at stated paths, PDF slide count matches `carousel_draft.md`, caption ties to the source's actual hook — not a generic hook.