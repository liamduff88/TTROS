# hooks/secret_exposure_check.md
> Revisit: on a new connector or a credential incident. · Last touched: 2026-07-07.

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
Documented only. Wires as a pre-commit scan and a pre-send redaction check
when the harness is ready — no live scanning implemented yet.
