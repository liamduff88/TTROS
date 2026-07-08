# hooks/token_budget_check.md
> Revisit: when the ledger schema or budget thresholds change. · Last touched: 2026-07-07.

## Event
Fires when a queue item transitions to done.

## Check
Refuses the transition if the receipt is missing lane, profile, model
requested, model confirmed, tokens (or an explicit "unavailable" — never an
estimate), or artifact paths. Also checks the item against the thresholds in
`rules/token_budget.md` and `context/TOKEN_POLICY.md` — deterministic script
first, cheap model second, strong model only on the two named escalation
triggers.

## On block
Blocks the done-transition, lists the missing receipt field(s) or the
threshold breached. Never fills a missing token count with a guess to let
the transition pass.

## Enforces
`rules/always.md` #1, #5 · `rules/token_budget.md` · `context/TOKEN_POLICY.md`.

## Status
Documented only. This is the check a queue-runner would run before marking
an item done — not yet wired to a live queue.
