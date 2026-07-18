# PASS

## Original repair closeout confirmation

PASS — the 17-path files-touched list matches the current scoped repair status. The closeout contains the required evidence baseline (5,031-byte initial prompt, one invocation, 1,511,725 retained tool-output bytes, 237 turns, one compaction, 30,381,312 cached-input tokens) and the compaction finding. Unrelated pre-existing dirty paths remain outside the repair list and proposed add command. Dashboard repair paths were explicitly scoped for the original repair; no unscoped protected path was absorbed.

## Smoke work-item ID

AOS-2026-0167

## Files touched by the repair — paths only

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

## Pre-existing unrelated dirty paths — paths only

- .gitignore
- connectors/CONNECTORS.md
- connectors/NATURAL_LANGUAGE_CONNECTOR_PROMPT.md
- connectors/composio_access_adapter.py
- connectors/composio_access_spine.md
- connectors/composio_tool_registry.json
- connectors/telegram_bridge/telegram_bridge.py
- context/ACCESS_MODEL.md
- context/OPERATING_BASELINE.md
- context/RUNTIME_STATUS.md
- dashboard/frontend/src/App.jsx
- dashboard/frontend/src/api.js
- dashboard/frontend/src/launcherPrompts.js
- dashboard/frontend/tests/launcherPrompts.test.js
- queue/rollups/week-2026-W29.json
- skills/prospecting_daily_run/SKILL.md
- tests/test_aos_orchestration.py
- tests/test_business_brain_context.py
- tests/test_telegram_bridge_formatting.py
- tests/test_workflow_prompt_templates.py
- tools/aos-linux-runtime.sh
- tools/aos-orchestration-runner.py
- tools/aos_indexer.py
- tools/business_brain_context.py
- workflows/prospecting_daily_run/workflow.md
- .vite/
- connectors/gmail_draft_adapter.py
- connectors/gmail_draft_policy.py
- queue/receipts/AOS-2026-0125-phase-6b-capture-live.json
- queue/receipts/gmail-draft-eaf7ea6500a619a6e2c05220.json
- queue/run_prompts/
- scripts/aos_0164_browser_proof.py
- tests/test_aos_dashboard_cleanup.py
- tests/test_gmail_draft_capability.py
- workflows/queue_artifacts/AOS-2026-0127_prospecting_daily_run_run_today_s_prospecting.md
- workflows/queue_artifacts/AOS-2026-0128_wsl_exe_-d_AgenticOSClean_--user_liam_--_bash_-l.md
- workflows/queue_artifacts/AOS-2026-0129_I_approve.md
- workflows/queue_artifacts/AOS-2026-0130_Approve_and_resume_AOS-2026-0128.md
- workflows/queue_artifacts/AOS-2026-0132_approve_and_resume_pply_this_as_the_operator_res.md
- workflows/queue_artifacts/AOS-2026-0134_Run_a_harmless_approval-routing_self-test_using.md
- workflows/queue_artifacts/AOS-2026-0134_approval_routing_self_test_closeout.md
- workflows/queue_artifacts/AOS-2026-0135_Run_a_harmless_approval-routing_self-test.md
- workflows/queue_artifacts/AOS-2026-0136_OK_pass_on_all_the_people_necessary.md
- workflows/queue_artifacts/AOS-2026-0139_I_can_t_read_that_Dot_MD_file_Can_you_give_it_to.md
- workflows/queue_artifacts/AOS-2026-0140_For_all_completed_Agentic_OS_tasks_do_not_send_m.md
- workflows/queue_artifacts/AOS-2026-0141_You_re_right_An_AOS_number_without_a_title_is_us.md
- workflows/queue_artifacts/AOS-2026-0142_Show_me_the_full_details_for_AOS-2026-0140_befor.md
- workflows/queue_artifacts/AOS-2026-0143_Why_was_it_blocked.md
- workflows/queue_artifacts/AOS-2026-0144_Do_not_create_a_new_work_item.md
- workflows/queue_artifacts/AOS-2026-0145_OK_just_direct_us_to_Hermes_agent_I_don_t_want_i.md
- workflows/queue_artifacts/AOS-2026-0146_I_approve_AOS-2026-0140_AOS-2026-0141_AOS-2026-0.md
- workflows/queue_artifacts/AOS-2026-0147_Inspect_the_current_Agentic_OS_queue_receipts_ru.md
- workflows/queue_artifacts/AOS-2026-0148_work_hermes_Read_queue_receipts_AOS-2026-0147_md.md
- workflows/queue_artifacts/AOS-2026-0152_route_repair_codex_pass.md
- workflows/queue_artifacts/AOS-2026-0155_work_codex_Create_one_harmless_deterministic_loc.md
- workflows/queue_artifacts/AOS-2026-0157_work_claude_BOUNDED_CANONICAL_CLAUDE_PRODUCTION.md
- workflows/queue_artifacts/AOS-2026-0158_work_claude_FINAL_BOUNDED_CANONICAL_CLAUDE_PRODU.md
- workflows/queue_artifacts/AOS-2026-0159_work_claude_FINAL_GREEN_CANONICAL_CLAUDE_PROOF_W.md
- workflows/queue_artifacts/AOS-2026-0160_work_claude_CANONICAL_CLAUDE_AND_TELEGRAM_ATTACH.md
- workflows/queue_artifacts/AOS-2026-0164-browser-proof/
- workflows/queue_artifacts/AOS-2026-0164_token_evidence.md
- workflows/queue_artifacts/AOS-2026-0164_work_codex_PERMISSION_MODE_SCOPED_LOCAL_TASK_APP.md
- workflows/queue_artifacts/AOS-2026-0165_Recover_AOS-2026-0161_dashboard_and_Telegram_UX.md

## Normal runner compaction-control proof

PASS — `tools/aos-orchestration-runner.py --execute-item AOS-2026-0167` freshly imported `dashboard/backend/main.py`; the normal queue route called `_run_codex_local`, which passed the shared `build_codex_exec_command(CODEX_TARGET)` result to `subprocess.Popen`. That builder includes `--config model_auto_compact_token_limit=75000`. The focused production-route policy tests passed.

## Counter field/value table

| Field | Parsed CLI value |
|---|---:|
| initial_prompt_bytes | unavailable from current CLI output |
| model_turns | unavailable from current CLI output |
| retained_context_bytes | unavailable from current CLI output |
| compaction_count | unavailable from current CLI output |
| fresh_input | 59051 |
| cached_input | 52224 |
| output | 942 |
| reasoning | 462 |
| largest_tool_result_bytes | unavailable from current CLI output |

## One-entry ledger proof

PASS — `token_ledger.jsonl` contains exactly one measured row for `AOS-2026-0167`/`codex`: basis `exact`, total `59993`, with only exact parsed values or the required unavailable literal. `queue/run_ledger.jsonl` contains exactly one row for the item: status `done`, review `ACCEPT`, receipt `queue/receipts/AOS-2026-0167.md`. The separate queue-ledger notification rows are distinct deterministic `no agent invocation` effects, not worker runs. No NaN, inferred value, estimate, or invented measurement zero appears.

## Model-review skip proof

PASS — item `review` is `none`; receipt records `Review mode: none (deterministic proof)`, `Review result: PASS`, and `Attempt 1 deterministic review: no agent invocation`. Hermes was not invoked during run or finalization.

## Needs Me threshold result

PASS — the human-review item exposed `needs_me: []`; no `excessive model turns` reason fired. The CLI did not expose `model_turns`, so the persisted value is the required unavailable literal.

## Focused validation performed, if any

PASS — the initial disposable setup item AOS-2026-0166 was cancelled after its optional title produced a secret-guarded artifact filename; the permitted repeat AOS-2026-0167 completed in one normal Codex runner attempt. Validation covered the one-line/61-byte artifact, one measured token row, one run-ledger row, exact-or-unavailable integrity, six focused unit tests passing in 1.059s, and path-limited diff/whitespace checks. No full suite was rerun.

## Exact suggested commit message

`repair token efficiency bounds review gate and intake accounting`

## Exact path-limited git add command Liam may run

`git add -- dashboard/backend/main.py dashboard/backend/test_composio_hermes.py dashboard/frontend/src/components/DashboardKit.jsx dashboard/frontend/src/queueState.js dashboard/frontend/src/views/Queue.jsx dashboard/frontend/tests/queueState.test.js decisions/DECISIONS.md queue/schemas/work_item.schema.json queue/token_ledger_schema.json tests/test_aos_codex_policy.py tests/test_aos_queue.py tools/aos-queue.py tools/aos_capture.py tools/aos_codex_policy.py tools/aos_orchestration.py workflows/prompt_templates/codex_workflow_runner.md workflows/queue_artifacts/direct_token_repair_token_efficiency_repair.md workflows/queue_artifacts/direct_token_repair_live_smoke.md`

## Exact git commit command Liam may run

`git commit -m "repair token efficiency bounds review gate and intake accounting"`

## Protected areas

No protected path was modified by this live-smoke task. The original repair's six dashboard paths are protected by default but were explicitly scoped for that repair. North Shore, Telegram bridge, route maps, environment/secrets/authentication material, legacy/Windows paths, immutable evidence, and the Hermes global/default profile were not modified by this task.

## Blockers

None.

## Next action

Liam may run the exact path-limited `git add` command and exact `git commit` command above after reviewing this closeout. Do not push automatically.

## Token usage

Token usage: exact smoke-worker CLI output — input 59051; output 942; total 59993; cached input 52224; reasoning output 462.
