---
workflow: delivery_client_kickoff
skill: skills/client_hub/SKILL.md
path: workflows/delivery_client_kickoff/workflow.md
lane: delivery
profile: aos-delivery
trust: watch
---
# Delivery Client Kickoff Workflow

Purpose: turn a signed or likely engagement into kickoff planning documents without sending client deliverables, requesting credentials in plain text, or touching live client systems.

Owner agent: Delivery.

Do not execute automatically. This workflow creates reusable local drafts only. Human review is required before client-facing or external use.

## When To Use

- Preparing an onboarding checklist for a new engagement.
- Drafting a kickoff agenda.
- Summarizing implementation assumptions and first-week plan.
- Listing source and access requests without collecting credentials in plain text.
- Planning client review checkpoints.

## Inputs

Place source material in the intake template:

- Engagement name and status.
- Approved scope, goals, stakeholders, and timeline notes.
- Known systems, source materials, and access needs.
- Delivery assumptions, risks, blockers, and dependencies.
- Human reviewer.

Do not request credentials in plain text. Do not touch live client systems.

## Local-Only Steps

1. Confirm engagement status and source material.
2. Extract stated scope, goals, stakeholders, dependencies, and risks.
3. Draft an onboarding checklist.
4. Draft a kickoff agenda.
5. Draft an implementation kickoff brief.
6. Draft a source and access request checklist without requesting secrets in plain text.
7. Draft delivery assumptions.
8. Draft a first-week implementation plan.
9. Draft client review checkpoints.
10. Save draft content using the output template.
11. Write a receipt in `receipts/`.
12. Stop for human review before client-facing use.

## Output Contract

The output should include:

- Source material used.
- Engagement status.
- Onboarding checklist.
- Kickoff agenda.
- Implementation kickoff brief.
- Source/access request checklist.
- Delivery assumptions.
- First-week implementation plan.
- Client review checkpoints.
- Human review status.

## Stop Conditions

- Engagement status or scope is unclear.
- Client-facing use is requested before human review.
- Credentials, API keys, passwords, or secrets would be requested in plain text.
- The workflow would need to touch live client systems.
- The workflow would need to send client deliverables.

## Definition Of Done

- Drafts are clearly marked as draft only.
- Access requests avoid plain-text credentials.
- Client system status says not changed by workflow.
- Delivery status says not sent by workflow.
- Assumptions and decisions needed are listed.
- A receipt is written.

## Receipt Format

Use `templates/receipt_template.md` or create a receipt in `receipts/YYYY-MM-DD_client_kickoff_receipt.md`.

## Validation Notes

- Local-only markdown workflow.
- No network, connectors, dashboard, Telegram, Hermes, runtime, client system, or external service is required.
- Do not send client deliverables.
- Do not request credentials in plain text.
- Human review before client-facing use is required.
