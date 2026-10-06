# Operator blocked-work UX — pre-edit state and predictions

Written 2026-10-06 before any code edit or validation run.

## Pre-edit Git state

- /home/liam/agentic-os-live: branch main, clean, HEAD 8636336 (AOS-0528: queue/operator lifecycle repair) == origin/main.

## Live queue at start (queue/work_items.jsonl, read-only)

- 34 items: cancelled 26, done 4, agent_working 2, blocked 2.
- AOS-2026-0528 blocked (child of AOS-2026-0527, agent_working). Blocker: "Step 6 fuse paused ...
  canonical usage unavailable". The repair itself landed out-of-band as commit 8636336.
- AOS-2026-0923 blocked (child of AOS-2026-0922, agent_working). The worker attached a PASS artifact
  with status `done` at 18:37:56Z; the run then failed at 18:39:26Z ("Business Brain pointer does
  not belong to global") and was recovered to blocked.
- Both blocked steps are folded under an "agent_working" parent card in the list, so the list shows
  no blocked state or reason at all.
- `/run` refuses (409) any terminal executive-objective child, so Retry is not a lifecycle path for
  either live item.

## Predictions (written before running)

- P1 Live AOS-2026-0528 projects as category `system_failure` (spending safety check), Retry not
  offered (objective step), actions = [dismiss], demands_operator = true.
- P2 Live AOS-2026-0923 projects as category `finished` (PASS done receipt precedes the block),
  demands_operator = false, actions = [close_finished, dismiss].
- P3 Live /api/queue/summary needsLiam drops from 2 to 1 (0923 no longer demands attention).
- P4 Fixture dismiss of a blocked objective step: step -> cancelled with supersession, its
  agent_working parent -> cancelled once no open step remains; work_items row count unchanged;
  no new item; next allocated ID unchanged; replay closes nothing.
- P5 Fixture close-finished: step -> done reusing the existing PASS receipt; no new item; refused
  (409) on an item with no PASS done receipt, leaving it blocked.
- P6 New tests fail on pre-edit code (endpoints/projection missing) and pass after.
- P7 Full suite: same failing set as the pre-edit baseline run in the same session; no new failures.
