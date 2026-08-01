# hooks/secret_exposure_check.md
> Revisit: on a new connector or a credential incident. · Last touched: 2026-07-31.

## Event
Fires before any commit, print, log, or external-facing draft that could
carry credential-shaped content.

## Check
Scans for `.env` patterns, key/token shapes, and credential values. Also
covers the verification note in `EXTERNAL_ACTIONS.md`: a credential is never
printed even to confirm an action is safe — "let me show you the key works"
is itself the violation.

## On block
Blocks the commit/print/publish, lists the offending lines by location (not
by reproducing the secret itself) in the receipt.

## Enforces
`rules/never.md` #6 · `context/EXTERNAL_ACTIONS.md` verification note.

## Status
LIVE. `hooks/runtime_guard.py` blocks credential-shaped paths and values at
Hermes `pre_tool_call`. `connectors/composio_access_adapter.py` independently
rejects credential-shaped mutation payloads before connector execution. Block
messages name the category and never echo the matched value.
