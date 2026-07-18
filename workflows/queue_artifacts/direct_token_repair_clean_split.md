# PASS — clean split of token-efficiency repair
> Revisit: when the scoped token-efficiency repair is committed or the Codex CLI/review/intake contracts change. · Last touched: 2026-07-18.

## PASS / NEEDS ATTENTION

PASS — the four approved repairs were reconstructed from parent `4b5756734657c10d93f955176446d61018588fc1` without importing the mixed commit's excluded behavior. No commit or push was performed.

## Files touched

- dashboard/backend/main.py
- dashboard/backend/test_composio_hermes.py
- dashboard/frontend/src/components/DashboardKit.jsx
- dashboard/frontend/src/queueState.js
- dashboard/frontend/src/views/Queue.jsx
- dashboard/frontend/tests/queueState.test.js
- decisions/DECISIONS.md
- queue/schemas/work_item.schema.json
- queue/token_ledger_schema.json
- tests/test_aos_codex_policy.py
- tests/test_aos_queue.py
- tools/aos-queue.py
- tools/aos_capture.py
- tools/aos_codex_policy.py
- tools/aos_orchestration.py
- workflows/prompt_templates/codex_workflow_runner.md
- workflows/queue_artifacts/direct_token_repair_live_smoke.md
- workflows/queue_artifacts/direct_token_repair_token_efficiency_repair.md
- workflows/queue_artifacts/direct_token_repair_clean_split.md

## Focused validation

- PASS — `python3 -m unittest -v tests.test_aos_queue tests.test_aos_codex_policy`: 51 tests.
- PASS — `python3 -m unittest dashboard.backend.test_composio_hermes`: 136 tests.
- PASS — `npm test`: 22 frontend tests.
- PASS — `npm run build`: Vite production build completed.
- PASS — `python3 -m unittest tests.test_aos_paths`: 7 tests.
- PASS — Python compilation for all affected Python modules/tests.
- PASS — both affected JSON schemas parse.
- PASS — `git diff --check`.
- PASS — 74/75/76 model-turn boundary, exact-or-unavailable counters, default deterministic review, explicit final-artifact-only reviewer input, and oversized `/work` continuation behavior are covered.

## Clean-worktree proof

- PASS — this worktree began clean at the mixed commit's parent and remained isolated from `/home/liam/agentic-os-live`.
- PASS — with `AOS_ROOT=/home/liam/agentic-os-token-repair-clean`, fresh imports of the Codex policy, queue tool, and dependency-light backend succeeded.
- PASS — the shared Codex builder contains `model_auto_compact_token_limit=75000`.
- PASS — protected/excluded representative paths remained byte-identical to `HEAD`.
- PASS — no AOS-2026-0166/0167 queue artifacts, receipts, ledgers, run prompts, or runtime files were created.

## Excluded mixed changes

- Claude execution or timeout repair.
- Detached queue-worker survival, heartbeat, lease, and executor changes.
- Telegram approval binding, Telegram bridge changes, document delivery, and title-first notifications.
- Gmail drafts, prospecting, desktop dashboard launch, Business Brain work, and general dashboard cleanup.
- AOS-2026-0161/0162/0164 browser-card work and disposable AOS-2026-0166/0167 runtime evidence.
- Unrelated historical decision entries.
- Route maps, protected paths, secrets/authentication material, and the original dirty worktree.

## Suggested commit message

`repair token efficiency bounds review gate and intake accounting`

## Exact path-limited git add command

`git add -- dashboard/backend/main.py dashboard/backend/test_composio_hermes.py dashboard/frontend/src/components/DashboardKit.jsx dashboard/frontend/src/queueState.js dashboard/frontend/src/views/Queue.jsx dashboard/frontend/tests/queueState.test.js decisions/DECISIONS.md queue/schemas/work_item.schema.json queue/token_ledger_schema.json tests/test_aos_codex_policy.py tests/test_aos_queue.py tools/aos-queue.py tools/aos_capture.py tools/aos_codex_policy.py tools/aos_orchestration.py workflows/prompt_templates/codex_workflow_runner.md workflows/queue_artifacts/direct_token_repair_live_smoke.md workflows/queue_artifacts/direct_token_repair_token_efficiency_repair.md workflows/queue_artifacts/direct_token_repair_clean_split.md`

## Exact git commit command

`git commit -m "repair token efficiency bounds review gate and intake accounting"`

## Blockers

None.

## Token usage

Token usage: unavailable from current CLI output.
