# goals/os_startup_health.goal.md
> Revisit: on a root-layer restructure or a failed startup check. · Last touched: 2026-07-07.

predicate: test -f soul.md && test -f CLAUDE.md && test -f AGENTS.md && test -f CODEX.md && test -f ANTIGRAVITY.md && test -f ROT.md && test -f rules/always.md && test -f rules/never.md && test -d hooks && test -d goals
born: 2026-07-07
source: Batch 7 goal build, os build queue
status: satisfied
last-pass: 2026-07-07
on-violation: wake Liam. Do not auto-fix — a missing root file means the
  repo is mid-edit or corrupted, not something to patch blind.
retire-when: the root identity layer is restructured on purpose and this
  predicate is rewritten to match. Retirement is a human decision, logged.

## Why this goal exists
Every other layer assumes the root identity files and the rules/hooks/goals
folders exist and are readable. This is the cheapest possible tripwire for
"something upstream broke the scaffold" before any agent starts reasoning
from a partial repo.

## Enforces
`rules/always.md` (read root before acting) · `ROT.md` (root layer is
always-current, never stale).
