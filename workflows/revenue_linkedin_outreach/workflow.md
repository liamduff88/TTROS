---
workflow: revenue_linkedin_outreach
skill: skills/linkedin_outreach_prep/SKILL.md
path: workflows/revenue_linkedin_outreach/workflow.md
lane: revenue
profile: aos-revenue
trust: watch
---
# Revenue LinkedIn Relationship Outreach Workflow

Purpose: draft relationship-first LinkedIn outreach and follow-up messages without sending anything, automating LinkedIn, scraping private data, or mutating CRM records.

## Inputs

Place source material in `input/`:

- Prospect name, role, and company.
- Public context supplied by Liam or already available in approved notes.
- Relationship history, referral path, or reason for relevance.
- Fit notes and disqualification notes.
- Desired soft CTA.

Use only provided context and public information intentionally supplied for the task. Do not scrape private data.

## Draft-First Steps

1. Confirm prospect, company, and context.
2. Write fit notes: why the person or company may be relevant.
3. Write disqualification notes: reasons not to reach out or reasons to pause.
4. Identify a relationship angle that is specific, respectful, and non-pushy.
5. Draft a first-touch LinkedIn message.
6. Draft one follow-up message.
7. Include a soft CTA that gives the prospect an easy out.
8. Save the outreach pack in `output/`.
9. Write a receipt in `receipts/`.
10. Require human review before any message is sent.

## Message Rules

- Draft only.
- Do not send messages.
- Do not automate LinkedIn.
- Do not scrape private data.
- Do not mutate CRM records.
- Do not claim a relationship that does not exist.
- Do not invent company facts, events, funding, hiring, pain, or intent.
- Keep the CTA soft and relationship-first.

## Receipt Format

Create a receipt in `receipts/YYYY-MM-DD_prospect_outreach_receipt.md`:

```markdown
# LinkedIn Outreach Draft Receipt

- Prospect:
- Company:
- Source context:
- Fit notes:
- Disqualification notes:
- Relationship angle:
- First-touch draft:
- Follow-up draft:
- Soft CTA:
- Human review status:
- Send status: not sent by workflow
- CRM status: not changed by workflow
- Blockers:
- Decisions needed:
```
