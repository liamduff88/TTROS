# AOS-2026-0165 — Recover AOS-2026-0161/0162 dashboard + Telegram UX completion proof

PASS

## Work item
- AOS-2026-0165 (parent: AOS-2026-0161; split fragment: AOS-2026-0162)

## Summary for operator
Verification only — no code was changed. The combined AOS-2026-0161/0162 dashboard, Telegram-label, and worker-supervision outcome is already present in the uncommitted working tree (delivered by the AOS-2026-0164 recovery pass) and is confirmed correct by full test runs, a production build, and an existing real-browser proof; nothing was sent externally and this task made no external calls.

## Method
Read both original split contexts (AOS-2026-0161, AOS-2026-0162) from `queue/work_items.jsonl`, read the AOS-2026-0164 recovery item and its browser-proof artifact (`workflows/queue_artifacts/AOS-2026-0164-browser-proof/browser-proof.json`, `pass: true`), then traced each requested outcome to the exact implementing code in the current uncommitted diff and to its test coverage.

## Requirement-by-requirement verification

1. **Reliable initial queue load / preserve last valid state on error** — `dashboard/frontend/src/queueState.js:20-37` (`mergeQueueSummary` now calls `preserveQueueDataOnRefreshFailure` instead of silently dropping data on a failed/timed-out refresh). Covered by `dashboard/frontend/tests/queueState.test.js` ("failed or timed-out refresh preserves prior queue data and counts") — passes.
2. **Refresh after navigation and every mutation** — verified in `dashboard/frontend/src/views/Queue.jsx` navigation/mutation refresh wiring and exercised by `AOS-2026-0164-browser-proof/browser-proof.json` checks `navigation_reload` (164 cards) and `automatic_mutation_refresh` (Human Review 17→16 after a real mutation).
3. **Needs Me cards, meaningful operator summaries, safe inline artifacts** — `/` opens the Needs Me feed (`dashboard/frontend/src/App.jsx:121-123`); newest-first human_review/needs_input cards with "AOS-ID — title", lane, age (`Queue.jsx:892-935`); deterministic non-title-echo `summary_for_operator` built server-side from the receipt/context contract, no extra model call (`dashboard/backend/main.py:4690-4723`); inline artifact expandable at ~1000 chars (`Queue.jsx:1207-1217`, confirmed live in browser proof: `collapsed_chars: 1036`, `expanded_in_place: true`); tags/parents/sources/receipt history collapsed behind one `<details>` "Details" control (`Queue.jsx:1178`).
4. **ID-plus-title labels, dashboard and Telegram** — shared `operator_item_label`/`format_operator_work_item_notification` helpers (`tools/aos_orchestration.py:206-229`) used by notification and split-guard paths in `dashboard/backend/main.py`; Telegram receipt/document captions use the same "ID — title status" contract (`connectors/telegram_bridge/telegram_bridge.py:315-325`). Covered by `tests/test_aos_orchestration.py` (title-first tests) and `tests/test_telegram_bridge_formatting.py` (`test_compact_completion_and_receipt_caption_are_title_first`, `test_receipt_caption_uses_work_item_title_when_body_has_no_bracket_header`) — all pass.
5. **No misleading third-party handoff form for internal work** — the manual dry-run handoff `<details>` block only renders when `selected.external_handoff_relevant` is true (`Queue.jsx:1293`), which the backend derives from an actual external/destructive-action text match (`main.py:4774-4776`), not shown for ordinary internal tasks; block is explicitly labeled "never sent" (`Queue.jsx:1294-1297`).
6. **Exact worker PID/start identity, heartbeat, stale-recovery** — `_linux_process_start_id` (`/proc/<pid>/stat` starttime) plus `_queue_worker_runtime_live` compare recorded `worker_runtime.pid`/`process_start_id` before treating a heartbeat gap as stale (`dashboard/backend/main.py:7099-7118`, mirrored in `tools/aos-orchestration-runner.py:next_async_item`). Registered at Claude launch via `register_worker_runtime` (`main.py:6927-6933`). Covered by `dashboard.backend.test_composio_hermes`: `test_stale_heartbeat_with_exact_live_worker_runtime_is_not_recovered`, `test_dead_worker_is_recovered_to_blocked_with_receipt_and_clear_claim`; and `tests.test_aos_queue`: `test_async_runner_does_not_recover_stale_heartbeat_while_exact_worker_process_is_live`, `test_async_runner_recovers_expired_lease_before_ready_work_and_skips_healthy_claim` — all pass.
7. **Detached worker supervision surviving backend/runner loss, 7800s timeout and `aos-claude --dangerously-skip-permissions` unchanged** — `dispatch_via_executor` (`tools/aos-orchestration-runner.py:148-172`) spawns the queue executor with `start_new_session=True`, `stdin=DEVNULL`, `close_fds=True`, log redirected to file — a standard detached-daemon pattern immune to the launching runner/backend process dying. `DEFAULT_EXECUTION_TIMEOUT_SECONDS = 7800` is unchanged (`tools/aos-orchestration-runner.py:24`). `/home/liam/.local/bin/aos-claude` still execs `claude -p "$*" --dangerously-skip-permissions` against the canonical root only. **Caveat**: this detachment mechanism is confirmed correct by code inspection and is a prerequisite the stale-recovery tests above rely on, but there is no dedicated kill-based integration test that spawns the executor, kills its parent, and observes the child keep running to completion — flagged as a minor follow-up, not a defect.
8. **Fail-closed Telegram-split oversized `/work` intake, one item / one worker regression** — `_telegram_split_request_guard` (`dashboard/backend/main.py:7937-7978`) detects a same-conversation continuation of an oversized prior `/work` message within a 120s window and returns `split-work-request-rejected` without creating a second item or starting a worker. Regression: `dashboard.backend.test_composio_hermes.HermesComposioTests.test_split_telegram_work_request_creates_one_item_and_invokes_one_worker` asserts exactly one queue row, `worker.call_count == 1`, and one runner dispatch attempt — **passes**.

## Files touched
- None (verification-only; no source edits were necessary)
- `workflows/queue_artifacts/AOS-2026-0165_Recover_AOS-2026-0161_dashboard_and_Telegram_UX.md` (this artifact)

## Validation
- `git diff --check` — clean (exit 0)
- `dashboard/backend/.venv/bin/python -m unittest tests.test_aos_orchestration` — 24 passed
- `dashboard/backend/.venv/bin/python -m unittest tests.test_aos_queue tests.test_telegram_bridge_formatting` — 63 passed
- `dashboard/backend/.venv/bin/python -m unittest tests.test_aos_codex_policy tests.test_aos_dashboard_cleanup tests.test_gmail_draft_capability` — 21 passed
- `dashboard/backend/.venv/bin/python -m unittest dashboard.backend.test_composio_hermes` — 172 passed (includes the split-intake and worker-identity regressions above)
- `cd dashboard/frontend && npm test` (`node --test tests/*.test.js`) — 22 passed
- `cd dashboard/frontend && npm run build` — production build succeeded, `dist/` output only (git-ignored, tree left clean)
- Reused existing real-browser proof: `workflows/queue_artifacts/AOS-2026-0164-browser-proof/browser-proof.json` (`pass: true`, initial load 164 cards, AOS-2026-0160 still `done`, Needs Me 58 cards, inline artifact expand, navigation reload, failed-refresh preserves counts, automatic mutation refresh)
- No connectors used, nothing sent externally, no commit/push performed

## Artifacts
- This file: `workflows/queue_artifacts/AOS-2026-0165_Recover_AOS-2026-0161_dashboard_and_Telegram_UX.md`
- Reused: `workflows/queue_artifacts/AOS-2026-0164-browser-proof/browser-proof.json` and `dashboard-1440x1000.png`

## Blockers
- None. Minor observation only (see item 7 caveat above): the detached-executor survival property is verified by code inspection, not by a kill-based integration test.

## Next action
- Ready for human review/approval of AOS-2026-0165 as the closing verification of AOS-2026-0161/0162. Optional follow-up (not blocking): add a kill-based integration test proving the detached queue executor survives backend/runner process loss.

## Token usage
- unavailable (no CLI usage evidence exposed to this session)
