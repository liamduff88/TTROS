# Revenue LinkedIn Outreach Queue Template

Use this template for a Revenue-owned Work Queue item that prepares LinkedIn relationship outreach through the existing Revenue Hermes lane. LinkedIn is an access path, not an agent.

## Example queue item

"Add this to the queue: create a Revenue task to prepare LinkedIn outreach angles for [target segment]."

## Required references

- [agents/revenue.card.md](../../agents/revenue.card.md)
- [context/ACCESS_MODEL.md](../../context/ACCESS_MODEL.md)
- [context/MEMORY_ROOT.md](../../context/MEMORY_ROOT.md)
- [memory_index/README.md](../../memory_index/README.md) or [memory_index/INDEX.md](../../memory_index/INDEX.md)
- [queue/templates/receipt.prompt.md](receipt.prompt.md)

## Work item

- ID: <AOS-ID>
- Title: Prepare LinkedIn relationship outreach angles for <TARGET_SEGMENT>
- Owner: revenue
- Requested by: Liam
- Status: inbox
- Priority: <PRIORITY>
- Tags: revenue, linkedin, outreach, relationship-first

## Purpose

Prepare practical, premium, systems-led, commercially grounded LinkedIn outreach options for Liam review. The output should help Revenue decide who to research, why they may be relevant, what relationship angle is credible, and what message options are safe to approve.

Avoid generic AI-hype tone. Do not frame Time to Revenue as a vague AI agency. Preserve Time to Revenue positioning: practical operator support, premium execution standards, systems-led growth, and commercially grounded revenue work.

## Queue-aware instructions

1. Treat this as a queued Revenue task, not a live LinkedIn action.
2. Use [agents/revenue.card.md](../../agents/revenue.card.md) for ownership, allowed outputs, and stop conditions.
3. Use [context/ACCESS_MODEL.md](../../context/ACCESS_MODEL.md) for access and mutation boundaries.
4. Use [context/MEMORY_ROOT.md](../../context/MEMORY_ROOT.md) and [memory_index/README.md](../../memory_index/README.md) or [memory_index/INDEX.md](../../memory_index/INDEX.md) to identify Business Brain pointers only. Do not copy Business Brain content into this repo.
5. Use [queue/templates/receipt.prompt.md](receipt.prompt.md) for the closeout shape.
6. Return the result as a receipt-ready queue closeout with sources accessed at category/path level only.

## Inputs to clarify

- Target market or segment:
- Prospect criteria:
- Exclusions or disqualifiers:
- Offer or commercial context:
- Known relationship paths, referrals, or relevant proof already approved:
- Desired outcome:
- Source references already attached to the queue item:

If target market or prospect criteria are missing, ask for only the smallest clarification needed or return a concise assumptions list for Liam approval.

## Workflow stages

1. Clarify target market and prospect criteria.
2. Read relevant Business Brain context by pointer only, using [context/MEMORY_ROOT.md](../../context/MEMORY_ROOT.md) and the memory index.
3. Prepare a prospect research plan that names what to verify and what would disqualify a prospect.
4. Prepare LinkedIn search/research instructions for manual or approved connector use. Keep these instructions focused on public, work-relevant context.
5. Draft relationship-first outreach angles that are specific, respectful, and commercially relevant.
6. Draft LinkedIn connection request and message options for Liam review. Label all drafts as unsent.
7. Prepare CRM-ready notes that can be reviewed before any CRM/GHL mutation.
8. Stop for Liam approval before any external action.
9. Return a receipt-ready closeout using [queue/templates/receipt.prompt.md](receipt.prompt.md).

## Required output

Return:

- Target segment summary:
- Prospect criteria:
- Business Brain pointers used:
- Prospect research plan:
- LinkedIn search/research instructions:
- Outreach angles:
- Connection request options:
- Message options:
- CRM-ready notes:
- Unsupported facts or claims to verify:
- Liam approval needed before:
- Receipt-ready closeout:

## Explicit stop conditions

Stop before:

- Sending LinkedIn connection requests.
- Sending LinkedIn messages.
- Publishing posts.
- Mutating CRM/GHL.
- Making pricing commitments.
- Making scope commitments.
- Using unsupported company facts.
- Making unsupported ROI or client proof claims.
- Exposing secrets, tokens, OAuth values, account identifiers, or private account metadata.

## External action boundary

This template does not authorize live LinkedIn, Gmail, Drive, Calendar, CRM/GHL, Composio, connector, browser automation, scraping, posting, sending, or account mutation. If any of those are needed, move the queue item to Liam review or request explicit approval in the receipt.
