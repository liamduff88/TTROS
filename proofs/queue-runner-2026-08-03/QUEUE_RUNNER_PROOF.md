# Automatic bounded queue-runner proof
> Revisit: when Cockpit eligibility, runner capacity, or queue polling changes. · Last touched: 2026-08-03.

## Before

- Git state: Executive Team work already uncommitted; preserved.
- Queue: 463 items; SHA-256 `ebe74c2729086c65ff517ce8d28e26381734125d4662b0cf419e7c79d65912c6`.
- Runnable tagged work: none.
- Runner: stopped; backend PID 6010 and frontend PID 6059 were reachable.
- Claims: no capacity-consuming `agent_working` items. Three old terminal rows retained sticky historical claims and were not counted.
- Capacity: no enforced runner ceiling was configured; the runner selected one tagged item per tick without active-capacity or dependency filtering.

## Root cause and repair

- `tools/aos-linux-runtime.sh desktop-start` deliberately omitted `start_runner`, matching the stopped live process.
- `dashboard/backend/main.py::_create_cockpit_command_item` created `agent_todo` rows without the runner's required `async_dispatch` tag.
- Manual dashboard Run called `run_queue_item` directly, so it bypassed automatic eligibility and hid both defects.
- The existing runner now starts with the desktop runtime, admits default capacity 2, counts live claims plus detached startup reservations, requires declared dependencies to have a latest `done` receipt, and excludes human gates and terminal states from capacity.

## Live lifecycle

All three independent items were created through `POST /api/dashboard/cockpit/command`; no Run control was used.

- `AOS-2026-0464` operations: `agent_todo` at 0.07s, `agent_working` at 3.27s, `human_review` at 96.07s.
- `AOS-2026-0465` marketing: `agent_todo` at 0.07s, `agent_working` at 8.59s, `human_review` at 83.26s.
- `AOS-2026-0466` revenue: stayed `agent_todo` while both slots were full, automatically became `agent_working` at 85.39s, and reached `human_review` at 106.75s.
- Observed two-worker overlap: 74.67s (`0464` + `0465`).
- Third-task slot release: `0466` started 2.13s after `0465` freed a slot.
- Duplicate proof: one top-level detached-executor result per independent ID; claims cleared on final status; one attempt per receipt.
- Capacity after proof: limit 2, active 0, available 2.

## Gates and routing

- `AOS-2026-0467` depended on `AOS-2026-0464`. It remained `agent_todo` after `0464` reached `human_review`, produced no executor log, receipt, or artifact, and was then cancelled as proof cleanup.
- `human_review`, `needs_input`, and `blocked` capacity exclusion is covered by the focused runner regression and the live final capacity reading.
- Named-profile receipts record exact requested/used pairs: `0464` = `aos-ops`, `0465` = `aos-marketing`, `0466` = `aos-revenue`; no fallback recorded.

## Dashboard and Executive regression

- Live screenshot: `proofs/queue-runner-2026-08-03/live-final-status.png`.
- Polling screenshot: `proofs/queue-runner-2026-08-03/auto-poll-final.png`.
- Headless browser observed queued, working, and human-review states using four automatic queue reads at 5.2s and 10.2s, with zero page reloads.
- Direct Revenue Executive consultation requested and used `aos-revenue` with no fallback. Queue remained 467 items and SHA-256 `b0b914446b5b11371e24b1cc50e1928c9f5c783f6fe34b22c1f9554d246626b3`; `items_created=0`.

## Token usage

- Queue-runner and browser validation: no agent invocation.
- Proof worker model counters: unavailable from current CLI output; recorded as unavailable in each work-item receipt.
- Codex task-session provider totals: unavailable from the current harness.
