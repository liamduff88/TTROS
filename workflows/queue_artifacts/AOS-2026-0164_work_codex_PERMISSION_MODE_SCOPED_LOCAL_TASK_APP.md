PASS

Work item:
- AOS-2026-0164

Summary for operator:
- Recovered the combined AOS-2026-0161/0162 request, repaired the Claude worker control path without extending its lease or 7,800-second execution timeout, and completed the dashboard plus split-Telegram intake behavior. Approval closes this local review and does not send anything externally.

Root cause / behavior changed:
- AOS-2026-0161's Claude/Hermes process survived a restart of its backend-owned supervisor, but its result reader and heartbeat owner did not. The replacement runner then saw a 133-second-old heartbeat and blocked the item even though the exact worker was still live.
- Tagged work now starts in a detached per-item executor using the backend production virtualenv and a durable per-item startup log. Claude launch records exact PID plus Linux process-start identity, heartbeats begin before running notification work, and stale recovery will not reclaim that exact live worker.
- The first proof dispatch also exposed and fixed a detached-startup dependency defect: a manual system-Python dispatch lacked FastAPI. Executor selection now prefers `dashboard/backend/.venv/bin/python`; the item remained unclaimed, so this caused no extra Claude invocation.
- Queue list responses are compact and selected detail/artifacts load lazily. The UI preserves prior valid counts/items after refresh failure, refreshes after navigation and mutations, renders Needs Me summaries and inline safe artifacts, shows `AOS-ID — title`, and hides external handoff controls for internal work.
- A same-conversation Telegram continuation resembling a split oversized `/work` command now fails closed with resend instructions, creating neither a second natural-language item nor a second worker invocation.
- One linked replacement was created without rewriting AOS-2026-0161 or AOS-2026-0162: AOS-2026-0165, parent AOS-2026-0161, now `human_review`.

Files touched:
- `dashboard/backend/main.py`
- `dashboard/backend/test_composio_hermes.py`
- `dashboard/frontend/src/api.js`
- `dashboard/frontend/src/views/Queue.jsx`
- `tools/aos-queue.py`
- `tools/aos-orchestration-runner.py`
- `tools/aos_orchestration.py`
- `tests/test_aos_queue.py`
- `tests/test_aos_orchestration.py`
- `decisions/DECISIONS.md`
- `scripts/aos_0164_browser_proof.py`
- Queue/runtime receipts and proof artifacts listed below

Validation:
- `python3 -m unittest tests.test_aos_queue tests.test_aos_paths tests.test_aos_orchestration tests.test_telegram_bridge_formatting dashboard.backend.test_composio_hermes` — 268 passed.
- `cd dashboard/frontend && node --test tests/*.test.js` — 22 passed.
- `cd dashboard/frontend && npm run build` — production build passed; 1,647 modules transformed.
- Python compilation for all edited Python implementation/proof files — passed.
- Real browser proof at `127.0.0.1:3010` against the updated local backend — passed: 164 initial cards, 58 Needs Me cards, ID-plus-title visible, inline artifact expanded, internal handoff hidden, navigation reload passed, injected 503 preserved prior counts, and Human Review count refreshed 17 to 16 after a real local approval mutation. No unexpected console or page errors.
- Updated compact endpoint measurement: `/api/queue/items` 0.0535 seconds / 109,972 bytes; `/api/queue/status` 0.0282 seconds.
- Real bounded Claude production proof AOS-2026-0165 — PASS in 361.399 seconds, one route-log record, `invocation_count: 1`, return code 0, wrapper `/home/liam/.local/bin/aos-claude`, executable `/home/liam/.local/npm/bin/claude`, exact timeout 7,800 seconds. The same registered PID/start identity and 30-second heartbeats remained healthy beyond the prior 90-second lease.
- `git diff --check` — passed.
- Final targeted diff inspection — completed; unrelated pre-existing worktree changes were preserved. No commit or push.

Artifacts:
- `workflows/queue_artifacts/AOS-2026-0164_work_codex_PERMISSION_MODE_SCOPED_LOCAL_TASK_APP.md`
- `workflows/queue_artifacts/AOS-2026-0164-browser-proof/browser-proof.json`
- `workflows/queue_artifacts/AOS-2026-0164-browser-proof/dashboard-1440x1000.png`
- `workflows/queue_artifacts/AOS-2026-0165_Recover_AOS-2026-0161_dashboard_and_Telegram_UX.md`
- `queue/receipts/AOS-2026-0165.md`
- `logs/runtime/queue-executor-AOS-2026-0165.log`
- `logs/local_agent_route.jsonl` (single AOS-2026-0165 Claude invocation record)

Blockers:
- None.

Next action:
- Liam reviews AOS-2026-0164 and linked replacement AOS-2026-0165 in Needs Me.

Token usage:
- unavailable from current CLI output

Current attempt:
- 1/2
