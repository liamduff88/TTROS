# goals/no_external_action_without_approval.goal.md
> Revisit: on an EXTERNAL_ACTIONS.md change or a failed daily check. · Last touched: 2026-07-07.

predicate: no entry in queue/run_ledger.jsonl shows a gated verb (send,
  write/publish/post, push, mutate, delete/archive/move, connect/grant
  scope, spend) executed without a matching `approved_external_action:
  <verb>` flag recorded for that same item
born: 2026-07-07
source: context/EXTERNAL_ACTIONS.md + hooks/pre_external_action.md
status: satisfied
last-pass: 2026-07-07
on-violation: wake Liam immediately — this is the highest-severity goal
  in this repo. Do not auto-fix, do not roll back silently; the exposure
  itself needs eyes on it first.
retire-when: never, while any external-action capability exists in this
  OS. Not retirable by drift — only by removing the capability entirely.

## Why this goal exists
This is the backstop behind `hooks/pre_external_action.md`. A hook can be
skipped, misconfigured, or bypassed by a new code path; this goal reads
the ledger after the fact and catches it if that ever happens. Approval
is per-action, not per-project — a general go-ahead on a task does not
satisfy the flag this goal checks for.

## Enforces
`rules/never.md` #1, #11 · `context/EXTERNAL_ACTIONS.md` gated list ·
`hooks/pre_external_action.md`.
