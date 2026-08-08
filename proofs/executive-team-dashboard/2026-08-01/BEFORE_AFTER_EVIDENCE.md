# Executive Team dashboard before/after evidence
> Point-in-time proof · Created: 2026-08-01.

## Task baseline

- Git: `main` at `1ec13b608fdcd66ed62052d28fe3b908d1ddfc97`; `origin/main` matched.
- Pre-existing worktree state: untracked `queue/locks/.work_items.write.lock.candidate-64b297c517eb4feea3405f2d69717afc/`; untouched.
- Services: frontend `127.0.0.1:3010` and backend `127.0.0.1:8010` reachable.
- Queue: 440 current rows; SHA-256 `91820cdd1c556f281ce0de7a1c524c63f0b7450a3c1a96b25e2610b295c36461`.
- Run ledger: 317 rows.
- Token ledger: 1,061 rows.
- Orchestration events: 832 rows.
- Receipt files: 1,260.
- Protected items AOS-2026-0071, -0073, -0074, and -0075 were all `done` and were not mutated.

## Concurrent background activity before browser consultations

At 15:46 UTC the existing Gmail capture schedule created `AOS-2026-0441`, a
`capture/gmail-live-read-only-digest` review item, plus its three existing
notification/digest receipts. This was after the task baseline and before the
16:02 UTC consultation window. It accounts for the task-wide queue/ledger
delta and is not attributable to the Executive Team surface.

## Browser consultation window

- Before: queue 441; SHA-256 `4d935c56689b565249c4d78d0c614d2ba6fc9870ed6b04624775672c29d179f9`.
- After: queue 441; same SHA-256.
- Run ledger: 318 before and after.
- Token ledger: 1,064 before and after.
- Receipt files: 1,263 before and after.
- Each of six response payloads reported `queue_effect.action=none`, `items_created=0`, and `unchanged=true`.
- The Hermes card double-click emitted one consultation POST.
- No ordinary consultation created queue work or a receipt.

Primary machine evidence: `browser-evidence.json`.
