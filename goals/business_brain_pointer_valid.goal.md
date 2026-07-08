# goals/business_brain_pointer_valid.goal.md
> Revisit: on a Business Brain move or a failed daily check. · Last touched: 2026-07-07.

predicate: the TTROS Business Brain path this OS points to
  (`C:\Users\Admin\Documents\A-Time to revenue\TTROS Business Brain`,
  `_substrate.wiki/schema.md` readable) exists and is readable — not moved,
  not renamed, not silently pointing at an old vault
born: 2026-07-07
source: Batch 1 root identity + operating_context/protected_paths.md
status: satisfied
last-pass: 2026-07-07
on-violation: wake Liam. Do not auto-fix and do not fall back to an old
  vault path — that is exactly the drift this goal exists to catch.
retire-when: the Business Brain is migrated to a new canonical location
  on purpose, and this predicate is rewritten to match. Retirement is a
  human decision, logged.

## Why this goal exists
Every agent's business-context reads route through one pointer. If that
pointer breaks or quietly resolves to an old vault, every downstream
answer looks normal while being wrong. This is the single cheapest check
that catches it early.

## Enforces
`rules/always.md` (read schema before querying) · `PROTECTED_PATHS.md`
(old vaults are archive-only, never a live dependency).
