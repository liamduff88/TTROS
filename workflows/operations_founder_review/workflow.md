---
workflow: operations_founder_review
skill: skills/weekly_review/SKILL.md
path: workflows/operations_founder_review/workflow.md
lane: ops
profile: aos-ops
trust: earned
---
# Operations Founder Review Workflow

Purpose: turn weekly notes, receipts, results, blockers, and priorities into a concise founder operating review without booking meetings, sending emails, moving broad folders, or creating bureaucracy.

Owner agent: Operations.

Do not execute automatically. This workflow creates reusable local drafts only. Human review is required before external use.

## When To Use

- Reviewing weekly operating notes and results.
- Summarizing blockers, decisions, and priority changes.
- Turning receipts into next queue or work items.
- Producing a what changed / what matters / what to do next summary.

## Inputs

Place source material in the intake template:

- Weekly notes.
- Receipts or result notes.
- Blockers and decisions.
- Current priorities and queue notes.
- Known constraints and owner notes.

Keep the review practical. Do not create bureaucracy.

## Local-Only Steps

1. Confirm the review period and source notes.
2. Extract results, blockers, decisions, changed context, and priority signals.
3. Draft a weekly founder operating review.
4. Draft a priority stack.
5. Draft a blocker list.
6. Draft a decision list.
7. Draft next queue or work items.
8. Draft a what changed / what matters / what to do next summary.
9. Save draft content using the output template.
10. Write a receipt in `receipts/`.
11. Stop for human review before external use or operational changes.

## Output Contract

The output should include:

- Source material used.
- Review period.
- Weekly founder operating review.
- Priority stack.
- Blocker list.
- Decision list.
- Next queue/work items.
- What changed / what matters / what to do next summary.
- Human review status.

## Stop Conditions

- Source notes are missing or conflict materially.
- The workflow would need to book meetings or send emails.
- The workflow would need to move, delete, archive, or reorganize broad folders.
- The workflow would create process overhead without a clear operating benefit.
- Human review has not happened before external use or operational changes.

## Definition Of Done

- The review is concise and action-oriented.
- Priorities, blockers, and decisions are separated.
- Next queue items are draft only.
- Meeting status says not booked by workflow.
- Email status says not sent by workflow.
- Folder status says not moved, deleted, or archived by workflow.
- A receipt is written.

## Receipt Format

Use `templates/receipt_template.md` or create a receipt in `receipts/YYYY-MM-DD_founder_review_receipt.md`.

## Validation Notes

- Local-only markdown workflow.
- No network, connectors, dashboard, Telegram, Hermes, runtime, calendar, email, file-moving service, or external service is required.
- Do not book meetings.
- Do not send emails.
- Do not move, delete, or archive broad folders.
- Human review before external use is required.
