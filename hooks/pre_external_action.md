# hooks/pre_external_action.md
> Revisit: on a new connector or a boundary incident. · Last touched: 2026-07-07.

## Event
Fires before any tool call classified as a gated verb: send, write/publish/
post, push, mutate, delete/archive/move, connect/grant scope, spend, or
touch a production/client-owned system — per `EXTERNAL_ACTIONS.md`'s gated
list.

## Check
Blocks unless the queue item carries an explicit `approved_external_action:
<verb>` flag naming that specific action, given in that turn. A general
go-ahead on the task ("build the proposal") does not satisfy this — approval
is per-action, not per-project.

## On block
Writes a blocked-action line to the receipt: the verb attempted, the target,
and that no execution occurred. Reports to Liam rather than retrying against
a different path or silently downgrading the action.

## Enforces
`rules/never.md` #1, #11 · `context/EXTERNAL_ACTIONS.md` gated list.

## Status
Documented only. No live tool call is wired — this spec is what a Claude
Code hook or Hermes queue-runner checkpoint would implement.
