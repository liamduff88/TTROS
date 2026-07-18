# PASS — direct_token_repair token-efficiency repair
> Revisit: when the Codex CLI output contract, queue review gate, or Telegram intake boundary changes. · Last touched: 2026-07-18.

## Evidence baseline confirmation

Confirmed as supplied: initial prompt 5,031 bytes; task stored once; one Codex invocation; no ledger double-counting; retained tool output 1,511,725 bytes; 237 model turns; one compaction; 30,381,312 cached input tokens. Root cause was retained tool output repeatedly reprocessed across a long session; prompt transport/context copying remained out of scope.

## Files touched — paths only

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
- workflows/queue_artifacts/direct_token_repair_token_efficiency_repair.md

## Validation table — test/proof and result

| Test / proof | Result |
|---|---|
| Repository Python discovery | PASS — 250 tests |
| Full dashboard backend suite | PASS — 175 tests |
| Full frontend suite | PASS — 23 tests |
| Affected core suites | PASS — 110 tests |
| Oversized `/work` plus continuation | PASS — one item, one persistent prompt file, merged content, `consider decomposing` |
| Token ledger/receipt counters | PASS — one entry per run; all nine fields; exact values preserved; missing values use the required literal |
| Measurement integrity | PASS — no NaN, estimates, inferred values, null measurements, or invented counter zeroes |
| Review gate | PASS — default skips model review; `review: model` selects the existing mocked path |
| Reviewer input bound | PASS — final artifact present; transcript and raw-log sentinels absent |
| Turn alert | PASS — 76 raises `excessive model turns`; 75 and 74 do not; default is 75 |
| Existing short intake | PASS — backend suite green |
| `git diff --check` | PASS |

## Root cause / behavior changed

Shared Codex prompts now bound file/test/runtime output. Coding work defaults to deterministic proof with no model reviewer; explicit model review receives only a final artifact or bounded closeout. Oversized intake persists and merges deterministically. Exact-or-unavailable counters feed existing receipts/ledgers and Needs Me metadata.

## Compaction control finding — exact option/value or the required unavailable statement

Supported by installed `codex-cli 0.144.1`: `--config model_auto_compact_token_limit=75000` on the shared Codex launch command. Installed feature inspection also reported stable `remote_compaction_v2` enabled.

## Protected-path grep result

PASS — baseline-to-final newly dirty path grep found no protected-path modification. The pre-existing dirty bridge path remained outside this task.

## Protected areas

North Shore, Telegram bridge, route maps, environment/secrets/authentication material, legacy/Windows paths, immutable AOS evidence items, and Hermes global/default profile were not modified.

## Open issues

Counters not explicitly emitted by the current CLI remain `unavailable from current CLI output`; the turn alert activates only from an explicit persisted `model_turns` value.

## Suggested commit message

`repair token efficiency bounds review gate and intake accounting`

## Blockers

None.

## Next action

Review and commit the scoped changes when ready; do not push automatically.

## Token usage

Token usage: unavailable from current CLI output.
