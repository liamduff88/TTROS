---
name: linkedin_carousel_from_md
description: Turn one sourced .md article/transcript into a LinkedIn carousel review package — slide copy, rendered PDF, caption. Draft-only; never publishes.
when-to-use: Liam sources a .md file (article, transcript, notes) via command bar or queue item and asks for a LinkedIn carousel. Owner: aos-marketing. Trust: v0 pre-seeded.
---
# /linkedin-carousel-from-md
> Revisit: when marketing_voice, positioning, or the P2.5 review-package schema changes. · Last touched: 2026-07-20

## Purpose
Produce one ready-to-review LinkedIn carousel package from a source .md file: no manual slide-building, no manual voice pass — Liam opens the review package, approves or edits, then hands off to LinkedIn manually (never auto-posts).

## Inputs
- Source `.md` file attached to the queue item (`source_refs`) — required. Refuse if no .md source is attached; do not draft from a topic alone (that's `/content-draft`).
- Optional resource metadata JSON: `resource_type`, `action`, `title`, `url`, and/or `context`. Structured type/action values take precedence over inference. Link CTA mode is the active default; no URL means the visible `[ADD RESOURCE LINK BEFORE POSTING]` review placeholder.
- `business_brain:memory/marketing_voice.md` + `business_brain:memory/positioning.md` (read both, every time).
- `business_brain:memory/offers.md` — only if the source material touches offers/pricing; never invent claims.

## Steps
1. **Frame** — read the source in full. State in one line: the one insight/hook worth a carousel, and who it's for.
2. **Slide plan** — 6–10 slides: hook (slide 1) → insight beats (2 through n-1, one idea per slide, short lines) → resource CTA (final slide contains `{{RESOURCE_CTA}}`). Output `carousel_draft.md`.
3. **Caption** — one LinkedIn post caption in marketing_voice, answer-first opening, references the carousel, no hashtag-stuffing, and ends with `{{RESOURCE_CAPTION_CTA}}` immediately followed by `{{RESOURCE_LINK}}` on the next line. Output `linkedin_caption.md`.
4. **Voice check** — reread both against marketing_voice.md; strip anything Liam wouldn't say; confirm no claim outside offers.md "do not claim" list.
5. **Resolve CTA + render** — deterministic step (not model): use explicit resource metadata first; otherwise score the source title/headings/content, non-CTA carousel/caption context, and resource-link context against supported resource types. Use the most specific unambiguous match and its grammatical action; ambiguous inference remains the neutral `resource` type with its `access` action. Resolve the three controlled markers, then call the canonical `workflows/pdf_branding` carousel profile through `workflows/linkedin_carousel_from_md/scripts/build_package.py`. The PDF slide directs the reader to the link in the LinkedIn post and contains no URL, URL placeholder, QR code, or embedded resource hyperlink. The caption contains the supplied resource URL or exactly `[ADD RESOURCE LINK BEFORE POSTING]`. No model call in this step.
6. **Package** — write the review package:
   - `source.md` (copy of source)
   - `carousel_draft.md`
   - `linkedin_caption.md`
   - `carousel.pdf`
   - `review_receipt.md` (token block, source path, slide count)
   - `post_package.json` (status: `ready_for_review`, artifact paths, caption text)

## Never
- Publish, schedule, post, or connect to LinkedIn — manual handoff only, always.
- Draft without a sourced .md file.
- Claim revenue lift, savings, timelines, or results not approved by Liam.
- Reference clients by name unless already public in context files.
- Invent offer or pricing facts.
- Use a message/DM CTA unless a future input contract explicitly introduces and requests that mode.
- Put a URL, URL placeholder, QR code, or embedded resource hyperlink in the PDF carousel.
- Treat any one resource type as the default; supported terms are inference evidence, not fixed CTA copy.

## Done when
`post_package.json` status is `ready_for_review`, all six artifacts exist, caption is voice-checked, receipt has a token block, and `resource_cta` records the resolved type, action, separate final-slide/caption copy, caption-link status, inference source, evidence, and fallback status. Verifier check: package metadata matches both generated CTA surfaces; the caption contains its configured URL or visible review placeholder; the structurally readable 8×10-inch PDF page count matches `carousel_draft.md`; and the PDF contains no URL, URL placeholder, QR code, or embedded resource hyperlink. No PDF placeholder or HTML fallback satisfies this contract.
