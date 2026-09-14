# hooks/pre_external_action.md
> Revisit: on a new connector or a boundary incident. · Last touched: 2026-09-13.

## Event
Fires before any tool call classified as a gated verb: send, write/publish/
post, push, mutate, delete/archive/move, connect/grant scope, spend, or
touch a production/client-owned system — per `EXTERNAL_ACTIONS.md`'s gated
list.

## Check
Allows operator/internal delivery when the exact target matches the existing
notification allowlist. For a third party, allows an exact action and target
already authorized by Liam's command; it does not ask for duplicate approval.
An unambiguous agreed Calendar record is equivalent when date, time,
participants, and timezone are complete. Otherwise it blocks. A general
go-ahead on the task ("build the proposal") does not satisfy this.

## On block
Writes a blocked-action line to the receipt: the verb attempted, the target,
and that no execution occurred. Reports to Liam rather than retrying against
a different path or silently downgrading the action.

## Enforces
`rules/never.md` #1, #11 · `context/EXTERNAL_ACTIONS.md` gated list.

## Status
LIVE. `hooks/runtime_guard.py` blocks direct connector mutations at Hermes'
native `pre_tool_call` event. The governed boundary in
`connectors/composio_access_adapter.py`, using
`tools/aos_orchestration.py::action_authorization()`, distinguishes internal
allowlisted delivery, an exact Liam command, complete agreed Calendar context,
and agent-initiated third-party action before calling a mutation tool, then
writes a redacted gate receipt.
