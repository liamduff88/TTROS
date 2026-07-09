---
name: linkedin_carousel_from_md
description: Turn one sourced .md article/transcript into a LinkedIn carousel review package — slide copy, rendered PDF, caption. Draft-only; never publishes.
when-to-use: Liam sources a .md file (article, transcript, notes) via command bar or queue item and asks for a LinkedIn carousel. Owner: aos-marketing. Trust: v0 pre-seeded.
---
# /linkedin-carousel-from-md
> Revisit: when marketing_voice, positioning, or the P2.5 review-package schema changes. · Last touched: 2026-07-08

## Purpose
Produce one ready-to-review LinkedIn carousel package from a source .md file: no manual slide-building, no manual voice pass — Liam opens the review package, approves or edits, then hands off to LinkedIn manually (never auto-posts).

## Inputs
- Source `.md` file attached to the queue item (`source_refs`) — required. Refuse if no .md source is attached; do not draft from a topic alone (that's `/content-draft`).
- memory/marketing_voice.md + memory/positioning.md (read both, every time).
- memory/offers.md — only if the source material touches offers/pricing; never invent claims.

## Steps
1. **Frame** — read the source in full. State in one line: the one insight/hook worth a carousel, and who it's for.
2. **Slide plan** — 6–10 slides: hook (slide 1) → insight beats (2 through n-1, one idea per slide, short lines) → CTA (final slide: System Fit Call or stated next step, per positioning.md). Output `carousel_draft.md`.
3. **Caption** — one LinkedIn post caption in marketing_voice, answer-first opening, references the carousel, no hashtag-stuffing. Output `linkedin_caption.md`.
4. **Voice check** — reread both against marketing_voice.md; strip anything Liam wouldn't say; confirm no claim outside offers.md "do not claim" list.
5. **Render** — deterministic step (not model): render `carousel_draft.md` slides to PDF via the dashboard's render tool. No model call in this step.
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

## Done when
`post_package.json` status is `ready_for_review`, all five artifacts exist, caption is voice-checked, receipt has a token block. Verifier check: PDF slide count matches `carousel_draft.md` slide count; caption references the carousel's actual hook, not a generic one.
