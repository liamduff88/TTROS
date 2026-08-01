# hooks/pre_publish_check.md
> Revisit: on a compliance change or a new outreach channel. · Last touched: 2026-07-31.

## Event
Fires before any write to a public or external-facing surface: LinkedIn,
website, published content, or a lead-outreach send.

## Check
- Draft states its outreach basis (CASL block for leads) — `rules/always.md` #2.
- For lead contact specifically: the lead has a passing email-safe/CASL
  check on record. No stated basis or a failed check blocks the send outright.
- A failed CASL check removes the lead from outreach entirely, not a
  downgrade — `rules/never.md` #12 applies (report, don't quietly drop).

## On block
Surfaces the missing basis or failed check in the receipt; the draft stays
in draft state. No partial publish.

## Enforces
`rules/always.md` #2 · `rules/never.md` #10, #12 · `context/EXTERNAL_ACTIONS.md`
CASL/outreach-specific gate.

## Status
LIVE. Hermes' `pre_tool_call` guard rejects direct send/post/publish bypasses.
At the governed Composio adapter, SEND/POST/PUBLISH/UPLOAD requires the queue
item's `publish_review_passed=true`; SEND additionally requires `email_safe`
and a non-empty outreach basis. Gmail remains draft-only through its narrower
adapter.
