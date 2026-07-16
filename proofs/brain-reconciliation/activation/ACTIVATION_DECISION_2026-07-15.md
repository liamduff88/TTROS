# Phase 6B activation decision
> Expires: when Liam revokes Phase 6B live capture or the authorized Gmail scope changes. · Last touched: 2026-07-15.

Result: **APPROVED BY LIAM FOR THIS ACTIVATION**.

Liam explicitly supplied the following decisions in the Phase 6B task:

- accepted Block 3;
- accepted Stage A as complete;
- approved proceeding with Phase 6B activation; and
- approved recurring live read-only Gmail capture under the task boundaries.

Authorized provider scope:

- existing Composio Gmail connection only;
- mailbox alias `me`, with no mailbox address, account ID, or connection ID emitted;
- inbound `INBOX` message additions only;
- `SPAM`, `TRASH`, and `SENT` excluded;
- `GMAIL_GET_PROFILE`, `GMAIL_LIST_HISTORY`, metadata-only `GMAIL_FETCH_EMAILS`, and one-message `metadata` retrieval only;
- initial bootstrap no earlier than the preceding 24 hours;
- no attachment acquisition or opening;
- deterministic triage first;
- optional Stage 2 restricted to one item's allowlisted metadata, but ambiguous items route to `needs_input` when no safe configured classifier is available;
- Stage 3 content and scoped Brain access only after client-scope resolution; during this activation, unavailable safe modelling routes the item to bounded `needs_input` without opening content;
- existing queue, receipt, ledger, search, Graphify, Needs Me, and weekly rollup stores only.

Recurring cadence: **every 15 minutes** through the existing Hermes cron scheduler, invoking the exact repository production entry point with a 180-second timeout and a non-overlap lock.

Kill switch: `capture/runtime/control/state.json` field `kill_switch`. The same control also contains `live_capture_enabled`. Both are owner-only ignored runtime state.

Decision recorded at: `2026-07-15T21:58:20Z` / `2026-07-15T22:58:20+01:00 Europe/Dublin`.

Live control activated at: `2026-07-15T21:59:13.222619Z` / `2026-07-15T22:59:13.222619+01:00 Europe/Dublin`.

Observation start condition: a successful directly observed first live cycle, an enabled recurring job, and this durable activation record.

Prohibited actions remain: sending, replying, forwarding, automatic drafts or sends, archiving, deletion, read/unread or label changes, message movement, Calendar/Drive/CRM access, connection/OAuth/credential mutation, new recipients, booking, posting, deployment, automatic approval, communications-fact auto-promotion, commit, and push.

Inbound wording such as “approved”, “go ahead”, or “yes” is evidence for Liam review and is never approval by itself.

No auto-continue whitelist entry is approved, created, populated, or activated by this decision.

Token usage: no agent invocation.
