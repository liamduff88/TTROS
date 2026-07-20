---
workflow: linkedin_carousel_from_md
skill: skills/linkedin_carousel_from_md/SKILL.md
path: workflows/linkedin_carousel_from_md/workflow.md
lane: marketing
profile: aos-marketing
trust: v0 pre-seeded
workflow: linkedin_carousel_from_md — sourced .md → LinkedIn carousel review package (draft-only, never publishes)
> Revisit: after first 3 real runs; when marketing_voice, positioning, or dashboard P2.5 schema changes. · Last touched: 2026-07-20
First slice of Dashboard P2.5 Workflow Action Packages. Manual LinkedIn handoff only — direct publish is a separate, later, explicitly-gated capability.
Trigger
Queue item with `source: command_bar` (or manually queued), a `.md` source file in `source_refs`, and workflow match `linkedin_carousel_from_md` (via queue/command_routes.json or explicit selection).
Input contract
Required = source `.md`, carousel draft with one `{{RESOURCE_CTA}}` marker on its final slide, and caption with one `{{RESOURCE_CAPTION_CTA}}` immediately followed by one `{{RESOURCE_LINK}}` marker on the next line. Optional `--resource-metadata <json>` accepts `resource_type`, `action`, `title`, `url`, `context`, and link-only `cta_mode`. Explicit type/action metadata wins. Without it, the deterministic resolver uses source titles/headings/content, carousel/caption context, and link context. Ambiguous type inference remains the neutral `resource` type and uses its `access` action. Missing URL resolves to exactly `[ADD RESOURCE LINK BEFORE POSTING]` in the caption only.
Completion contract (default)
Done = `post_package.json` status `ready_for_review`; package contains `source.md`, `carousel_draft.md`, `linkedin_caption.md`, `carousel.pdf`, `review_receipt.md`, `post_package.json`; caption and slides voice-checked; receipt has a token block; manifest `resource_cta` metadata matches both generated CTA surfaces.
Allowed unprompted = reading `business_brain:memory/marketing_voice.md` + `business_brain:memory/positioning.md` (both, every time), `business_brain:memory/offers.md` if source touches pricing; drafting slides/caption; deterministic PDF render.
Stop conditions = no `.md` source attached; source contains a claim on the offers.md "do not claim" list; anything that would post, schedule, connect, or publish (never allowed regardless of flags).
Run
Execute skill steps in order: frame → slide plan → caption → voice check → deterministic CTA resolution → render → package. Use `<!-- slide -->` between 6–10 slides and run `.venv-pdf/bin/python workflows/linkedin_carousel_from_md/scripts/build_package.py --source <source.md> --carousel-draft <carousel_draft.md> --caption <linkedin_caption.md> --output-dir workflows/linkedin_carousel_from_md/output/{item_id} --item-id {item_id} [--resource-metadata <resource.json>]`. The package runner calls the existing `workflows/pdf_branding` carousel profile; it does not implement a second PDF subsystem. It infers the most specific supported resource type only when evidence clears a deterministic confidence/margin threshold, chooses a grammatical action, keeps the URL in the caption, and records resolution provenance. Package lands at `workflows/linkedin_carousel_from_md/output/{item_id}/`. Status set to `ready_for_review`, surfaced on the operator dashboard. Queue-owned real runs append the existing run_ledger + token_ledger and update skill_trust.jsonl toward v0-marker removal (3 real uses); direct deterministic proof runs record their token-unavailable/no-model block inside `review_receipt.md` without mutating queue state.
Never
Publish, schedule, connect, or post anywhere, under any approval flag.
Claim revenue lift, savings, or timelines not approved by Liam.
Reference clients by name unless already public in context files.
Invent offer or pricing facts.
Generate a message/DM CTA on the active default path, or put a URL, URL placeholder, QR code, or embedded resource hyperlink in the PDF carousel.
Verifier check
`post_package.json` status is `ready_for_review`, all 6 artifacts are present at stated paths, resource metadata distinguishes final-slide CTA text from caption-link status and matches both surfaces, the caption has a configured URL or review placeholder, the readable 8×10-inch PDF page count matches `carousel_draft.md`, pages are non-blank and unique, the PDF contains no URL, URL placeholder, QR code, or embedded resource hyperlink, browser layout checks report no overflow, and the caption ties to the source's actual hook — not a generic hook. Manual LinkedIn upload remains outside the workflow.
