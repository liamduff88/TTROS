# hooks/client_isolation_check.md
> Revisit: on a new client or a boundary incident. · Last touched: 2026-07-07.

## Event
Fires before any output that references client data — a report, a draft, a
memory write, or a cross-client query.

## Check
Confirms the output draws from exactly one client's folder/thread and that
no second client's name, figures, or context appears anywhere in the same
artifact. One client, one thread, one folder — no exceptions for
"just for comparison."

## On block
Blocks the output, flags the second client reference in the receipt, and
asks rather than silently stripping the offending line (stripping could
still leave inferential leakage).

## Enforces
`rules/always.md` #7 · `rules/never.md` #9 · `rules/client_data_boundaries.md`.

## Status
Documented only. Runs as a check step before any client-facing artifact is
marked done, not a live filter on an external system.
