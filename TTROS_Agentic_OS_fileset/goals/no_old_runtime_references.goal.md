# goals/no_old_runtime_references.goal.md
> Revisit: on a new legacy-path discovery or a failed daily check. · Last touched: 2026-07-07.

predicate: grep -rIl -e 'C:\\AI-Vault' -e 'AI Native Source of Truth' -e 'old Ubuntu' -e 'legacy_harvest' -e 'ZPC' . --exclude-dir=.git returns nothing outside goals/ and operating_context/old_vault_archive_plan (the archive-plan doc itself is allowed to name what it archives)
born: 2026-07-07
source: operating_context/old_vault_archive_plan.md + Batch 7 goal build
status: satisfied
last-pass: 2026-07-07
on-violation: wake Liam. Do not auto-fix — a new reference to a legacy
  path is a routing bug (something pointing at a dead system), not a
  typo to quietly correct.
retire-when: the old vaults are fully decommissioned and even the
  archive-plan doc is retired. Retirement is a human decision, logged.

## Why this goal exists
`C:\AI-Vault` and `AI Native Source of Truth` are archive-only per
`PROTECTED_PATHS.md` — reference for mining, never a live dependency.
This goal catches any file in this OS that starts depending on one of
those paths again, which would mean old state leaking back into the
live system.

## Enforces
`PROTECTED_PATHS.md` · `rules/never.md` #2 · `operating_context/old_vault_archive_plan.md`.
