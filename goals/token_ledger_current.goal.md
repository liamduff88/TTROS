# goals/token_ledger_current.goal.md
> Revisit: on a token policy change or a failed daily check. · Last touched: 2026-07-07.

predicate: the most recent entry in queue/token_ledger.jsonl has a date
  within the current active session window (never silently stale across
  a session that reported token usage)
born: 2026-07-07
source: Batch 6 queue scaffold + rules/token_budget.md
status: satisfied
last-pass: 2026-07-07
on-violation: wake Liam. Do not auto-fix — an unavailable token count is
  reported as "unavailable," never estimated or backfilled.
retire-when: token reporting moves to a different mechanism entirely.
  Retirement is a human decision, logged.

## Why this goal exists
`rules/never.md` bans inventing token numbers. This goal is the flip
side: it catches the ledger going quiet — a session that should have
logged usage and didn't — before that silence gets mistaken for "no
cost incurred."

## Enforces
`rules/token_budget.md` · `context/TOKEN_POLICY.md` ·
`hooks/token_budget_check.md` · `token_ledger_schema.json`.
