# Phase 6B kill-switch proof
> Expires: when the production entry point or capture control contract changes. · Last touched: 2026-07-15.

Result: **PASS**.

Disabled-state production proof, before activation:

- invoked `python3 tools/aos_capture_live.py poll` while `live_capture_enabled=false`;
- result: `disabled` with a bounded operational receipt;
- Composio binary `execve` count under process trace: zero;
- provider action count: zero;
- production cursor, raw records, processing state, derived rows, queue, search DB, and capture graph were hash-identical before/after.

Live scheduled kill-switch proof, after recurrence was enabled:

- set `capture/runtime/control/state.json:kill_switch=true`;
- triggered the exact Hermes scheduled job;
- result: `kill_switch`, `scheduled_entry=true`, provider actions `{}`;
- cursor file remained byte-identical;
- restored `kill_switch=false`;
- final control: `live_capture_enabled=true`, `kill_switch=false`.

Non-overlap uses the same owner-only `capture/runtime/control/poll.lock`. A scheduled trigger while the lock was held returned `already_running`, performed zero provider actions, and did not move the cursor.

Token usage: no agent invocation.
