# AOS-2026-0528 — pre-edit state and predictions

Written 2026-10-04 before any code edit or validation run.

## Pre-edit Git state (read-only)

- /home/liam/agentic-os-live: branch main, HEAD 15a3aa6c4e97cf4abd4600a0f52cd3dd8766cba5 == origin/main.
  Dirty: one untracked lock-candidate dir only
  (`queue/locks/.work_items.write.lock.candidate-af47be81257840599234661c4bbf2004/`), not ours, left alone.
- TTROS Business Brain: branch main, HEAD 41a87454a27dfd6648262d65cc8f8de9234c8a89 == origin/main.
  Dirty: ` M sessions/thread_david.md`, `?? sessions/workstreams/` (intentional continuity dirt; preserve).
- Shared Brain control: Stage 1-3 COMPLETE, Stage 4 NOT STARTED. This task does not start Stage 4.

## Root causes found (diagnosis before edit)

1. Duplicate IDs: work_items.jsonl max live/tombstoned ID = AOS-2026-0528, but orchestration_events,
   receipts and ledgers carry history up to AOS-2026-0921 for items removed without tombstones.
   `next_id` only reserves live + tombstoned IDs, so 0500..0528 were already re-issued and 0529 is next.
2. Reused IDs poison notification idempotency: prior-send / intent / receipt identities key on
   (item_id, key) only, so a re-issued ID inherits an older item's "sent" or "intent" rows.
3. Completion callback only fires for `source == "telegram"`; David hand-offs are
   `source = dashboard/hermes_message` with `dispatch.reply_to`, so none report back. Executive
   objective parents never notify on done/blocked.
4. Runner status reads logs/runtime/runner.pid (2026-08-09, pid 30039, dead) while systemd runs the
   runner as aos-runner.service MainPID 138240 -> dashboard says "unavailable".
5. Live runner unit is started with `--skip-telegram-escalation` (outside repo; not changed here).
6. No supersession lifecycle: replacement work (AOS-2026-0525 done) leaves AOS-2026-0523/0524 blocked.

## Predictions (written before running)

- P1 live next ID before fix: AOS-2026-0529. After fix: AOS-2026-0922.
- P2 live runner status after fix: available=True, state running/idle, pid 138240, source systemd,
  pid_file reported stale (30039).
- P3 stale-PID fixture: pid file to a dead pid with no systemd runner -> state "stale_pid", available False.
- P4 cleanup of live queue: exactly 8 items move to cancelled (0499,0500,0519,0520,0521,0522,0523,0524);
  work_items.jsonl line count stays 32; 0 records deleted; done count stays 4; 8 supersession receipts written.
- P5 Each new/changed test fails on the pre-fix code (negative rehearsal) and passes after.
- P6 Full suite: 772 baseline + new tests, 0 failed.
