---
workflow: marketing_content_repurposing
skill: skills/content_draft/SKILL.md
path: workflows/marketing_content_repurposing/workflow.md
lane: marketing
profile: aos-marketing
trust: earned
---
# Marketing Content Repurposing Workflow

Purpose: turn one approved source asset, transcript, opinion, delivery lesson, PDF, or offer note into reusable marketing draft options without publishing or making unsupported claims.

Owner agent: Marketing.

Do not execute automatically. This workflow creates reusable local drafts only. Human review is required before external use.

## When To Use

- Repurposing one source asset into multiple marketing angles.
- Turning a delivery lesson into content ideas.
- Drafting LinkedIn post options, newsletter outline, website/service-page copy blocks, proof asset outline, and CTA mapping.
- Preparing marketing drafts for review before publishing.

## Inputs

Place source material in the intake template:

- One source asset or note.
- Audience and offer context.
- Approved claims, proof points, examples, and constraints.
- CTA options or destination notes.
- Any private or sensitive material that must be excluded.

Do not use private client data. Do not make unsupported performance claims. Do not sound like generic AI hype.

## Local-Only Steps

1. Confirm the source asset and approval status.
2. Extract usable ideas, proof points, constraints, and exclusions.
3. Draft LinkedIn post options.
4. Draft a newsletter outline.
5. Draft short website or service-page copy blocks.
6. Draft a case study or proof asset outline.
7. Map CTAs to audience intent and source context.
8. Save draft content using the output template.
9. Write a receipt in `receipts/`.
10. Stop for human review before publishing, sending, or distributing.

## Output Contract

The output should include:

- Source material used.
- Audience and offer context.
- LinkedIn post options.
- Newsletter draft outline.
- Website or service-page copy blocks.
- Case study or proof asset outline.
- CTA mapping.
- Unsupported claims removed or flagged.
- Human review status.

## Stop Conditions

- The source asset is not approved for reuse.
- Private client data appears in the material.
- A claim lacks source support.
- The workflow would need to publish, schedule, upload, email, or distribute content.
- Human review has not happened before external use.

## Definition Of Done

- Drafts are clearly marked as draft only.
- Source material and exclusions are listed.
- Private client data is removed or flagged.
- Unsupported claims are removed or marked as decisions needed.
- Publishing status says not published by workflow.
- A receipt is written.

## Receipt Format

Use `templates/receipt_template.md` or create a receipt in `receipts/YYYY-MM-DD_marketing_repurpose_receipt.md`.

## Validation Notes

- Local-only markdown workflow.
- No network, connectors, dashboard, Telegram, Hermes, runtime, publishing tool, or external service is required.
- Do not publish.
- Do not send or distribute drafts.
- Human review before external use is required.
