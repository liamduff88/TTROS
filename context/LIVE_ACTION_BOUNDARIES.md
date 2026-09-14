# Live action boundaries
> Revisit: when queue completion, connector adapters, notification allowlists, or action policy changes. · Last touched: 2026-09-13.

This is the live permission behavior enforced by the TTROS queue, runtime guard,
notification paths, and governed Composio adapter.

## Automatic actions

- Successful scoped TTROS source implementation runs validation and secret/diff
  checks, commits only intentional changes, pushes normally, and verifies local
  HEAD equals the authoritative remote. Validation failure, inseparable dirty
  work, secrets, or remote divergence stops the sequence. Force-push is never
  permitted.
- Operator delivery is internal: messages, files, artifacts, results, and
  notifications to `queue/notifications.json`'s allowlisted Telegram operator
  chat, configured Liam email addresses, and approved internal AgentMail
  destinations are AUTO and do not enter `human_review`.
- Liam's exact command naming a consequential action and exact target is the
  approval. It is not sent back for duplicate approval.
- Calendar booking/change/cancellation is AUTO on Liam's exact unambiguous
  request. A clearly agreed booking from supplied meeting/transcript context is
  also AUTO only when date, time, participants, and timezone are complete.

## Gated or protected actions

- An agent-initiated third-party send/action retains the existing exact-action
  approval gate.
- A materially ambiguous target/action asks one clarification. Ambiguous
  Calendar details route to `needs_input`.
- Secret-shaped paths and values remain blocked before read, log, commit, or
  send. Ordinary work is not blocked merely because `.env` files exist or are
  mentioned without access.
- CRM, money/payment, destructive deletion, broader deploy/publish, Business
  Brain review tiers, the token fuse, North Shore, and Telegram bridge files are
  unchanged.

## Enforcement

- `tools/aos_orchestration.py::action_authorization()` classifies allowlisted
  internal delivery, exact Liam commands, complete agreed Calendar context, and
  unapproved third-party actions.
- `tools/aos_orchestration.py::external_effect_review_status()` prevents generic
  `send`/`external` tags from manufacturing `human_review` for an authorized
  action, while retaining `human_review` for an unapproved third-party effect
  and `needs_input` for an ambiguous Calendar effect.
- `connectors/composio_access_adapter.py::authorize_external_mutation()` applies
  the same decision before a mutation and still performs secret, publish-review,
  and CASL/email-safe checks.
- `tools/aos_orchestration.py::prepare_telegram_send()` remains the allowlisted,
  idempotent message/file path and loads the existing bridge without modifying
  bridge or startup files.

Token usage: unavailable from current CLI output.
