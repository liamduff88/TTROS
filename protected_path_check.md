# hooks/protected_path_check.md
> Revisit: on a new protected area or a boundary incident. · Last touched: 2026-07-07.

## Event
Fires before any file write or edit tool call.

## Check
Matches the target path against the protected categories in
`PROTECTED_PATHS.md`: runtime/connector state, dashboard code, archive/
quarantine-only paths, and North Shore files. Read access for context is not
write access for change — a path match on read is allowed; a path match on
write is not, regardless of stated intent.

## On block
Blocks the write, surfaces the matched path and category in the receipt.
Not silently retried against a different path or rephrased as an "update"
to route around the match.

## Enforces
`rules/never.md` #2, #3, #8 · `context/PROTECTED_PATHS.md`.

## Status
Documented only. No live filesystem hook installed yet.
