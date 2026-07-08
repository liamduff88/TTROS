---
workflow: revenue_sales_prep
skill: skills/fit_call_prep/SKILL.md
path: workflows/revenue_sales_prep/workflow.md
lane: revenue
profile: aos-revenue
trust: watch
---
# Revenue Sales Prep Workflow

Purpose: turn provided prospect notes, website notes, call notes, or transcript snippets into sales preparation documents without sending outreach, mutating CRM records, or inventing company facts.

Owner agent: Revenue.

Do not execute automatically. This workflow creates reusable local drafts only. Human review is required before external use.

## When To Use

- Preparing for a sales discovery call.
- Summarizing prospect fit from notes supplied by Liam.
- Turning a completed call into a CRM-ready opportunity summary.
- Preparing a proposal outline from reviewed discovery context.

## Inputs

Place source material in the intake template:

- Prospect or account name.
- Source notes, website notes, call notes, or transcript snippets.
- Known context, goals, blockers, stakeholders, and timing.
- Offer or service context already approved for use.
- Existing constraints, unknowns, and disqualification notes.

Use only provided context. Do not invent company facts, buying intent, budget, urgency, stakeholders, technology stack, or pricing commitments.

## Local-Only Steps

1. Confirm the source material and intended sales stage.
2. Extract stated facts, unknowns, signals, risks, and disqualifiers.
3. Draft a prospect fit brief.
4. Draft a sales discovery prep note.
5. Draft a discovery question set.
6. Draft a call summary if call notes or transcript snippets are present.
7. Draft a CRM-ready opportunity summary without mutating CRM.
8. Draft a proposal prep outline without committing pricing, scope, or timelines.
9. Save draft content using the output template.
10. Write a receipt in `receipts/`.
11. Stop for human review before any external use.

## Output Contract

The output should include:

- Source material used.
- Sales stage.
- Prospect fit brief.
- Discovery prep.
- Discovery questions.
- Call summary, if applicable.
- CRM-ready opportunity summary marked as not written to CRM.
- Proposal prep outline with assumptions and decisions needed.
- Stop conditions and human review status.

## Stop Conditions

- Source material is missing, ambiguous, or appears private without approval.
- The output would require unsupported company facts.
- Pricing, scope, timeline, or legal commitments are requested without approval.
- The workflow would need to send outreach or mutate CRM.
- Human review has not happened before external use.

## Definition Of Done

- The output uses only supplied source material.
- Unknowns and assumptions are clearly marked.
- CRM status says not changed by workflow.
- Outreach status says not sent by workflow.
- Proposal commitments are marked as decisions needed.
- A receipt is written.

## Receipt Format

Use `templates/receipt_template.md` or create a receipt in `receipts/YYYY-MM-DD_revenue_sales_prep_receipt.md`.

## Validation Notes

- Local-only markdown workflow.
- No network, connectors, dashboard, Telegram, Hermes, runtime, CRM, or external service is required.
- Do not send outreach.
- Do not mutate CRM.
- Human review before external use is required.
