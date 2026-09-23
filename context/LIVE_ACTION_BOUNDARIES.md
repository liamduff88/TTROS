# Live action boundaries
> Revisit: when the dashboard backend, queue runner, Hermes profiles, connector adapters, notification wiring, or Business Brain writers change. · Last touched: 2026-09-13.

Operator map of rules reachable from the current TTROS runtime. This excludes archive/history unless a live caller still reaches it.

## Live entrypoints confirmed

- `aos-backend.service` is active and runs `dashboard/backend/main.py` through Uvicorn from `/home/liam/agentic-os-live/dashboard`.
- `aos-runner.service` is active and runs `tools/aos-orchestration-runner.py --root /home/liam/agentic-os-live --skip-telegram-escalation --watch --interval 5`.
- The runner dispatches tagged queue items into `dashboard/backend/main.py::run_queue_item()`.
- Ask David runs the `david` profile, parses `execution_handoff`, then calls `hermes_message()` / `_hermes_objective_from_handoff()` to create the Hermes-owned objective and children.
- The live `aos-orchestrator` and department profile configs register `hooks/runtime_guard.py` as `pre_tool_call`; David registers only the B7-scoped guard and has filesystem, terminal, code, web, and delegation toolsets disabled.
- `aos-bridge.service` is active for inbound Telegram. Its files/content were not inspected; live outbound callers use the existing bridge function only.

## Reachable rules

| Action | Current behavior | Exact file/function/config | What triggers the block | How Liam changes it |
|---|---|---|---|---|
| Normal queue-launched Codex local reads/edits/tests/install/dev server/browser/screenshot | **AUTO** | `tools/aos_codex_policy.py`: `SANDBOX_MODE`, `APPROVAL_POLICY`, `PERMISSION_HEADER`, `build_exec_command()` | No approval prompt. A task can still stop on its queue `stop_conditions`, a hard boundary below, or execution failure. | Change the queue item's scope/fields or the defaults in `dashboard/backend/main.py::QueueItemCreate`; do not change the Codex runtime policy merely to widen one task. |
| Queue `allowed_actions` / `stop_conditions` | **ALLOWLISTED** | `dashboard/backend/main.py::_queue_actual_run_prompt()`, `_queue_actual_department_run_prompt()`, `_queue_render_prompt()`; stored by `tools/aos-queue.py::create_item()` | These are instructions supplied to the worker and reviewer, not a mechanical filesystem permission layer. A worker stopping on them or a reviewer returning `REVISE` can ultimately create `needs_input`/`blocked`. | Edit them when creating the task, or edit the specific live work item fields. Defaults are on `QueueItemCreate` / `DashboardTaskCreate`; Hermes objective mandatory stops are in `_create_executive_objective()`. |
| Start a queue item | **AUTO** | `tools/aos-orchestration-runner.py::next_async_item()`, `dispatch_via_executor()`; `dashboard/backend/main.py::run_queue_item()` | Refused if dependencies lack `done` receipts, the item is already actively claimed/working, it is a terminal Hermes-owned child, no runner capacity exists, or the selected runtime/profile cannot start. | Satisfy dependencies/release stale claims; capacity and lease/timeouts are `AOS_MAX_CONCURRENT_EXECUTORS`, `AOS_AGENT_LEASE_SECONDS`, and runner timeout env vars. Profile routes are `queue/lane_profiles.json` and `queue/model_routes.json`. |
| Further model invocation in the same named scope | **BLOCKED/PROTECTED** | `tools/step6_cost_control.py::preflight()`; called by `dashboard/backend/main.py::_run_wsl_prompt_command()` and operator-lean wrapper | The 500,000 canonical-token scope fuse is reached, or usage accounting is missing/corrupt and fails closed. | Safest: use the scoped `/api/cost-control/fuse-override`, `/fuse override`, or scoped reset with a visible reason. The global limit is `FUSE_LIMIT` in `tools/step6_cost_control.py`. |
| Hermes reads of secret-shaped paths/content | **BLOCKED/PROTECTED** | `hooks/runtime_guard.py::evaluate()`; live profile configs under `~/.hermes/profiles/{aos-orchestrator,aos-revenue,aos-marketing,aos-delivery,aos-ops}/config.yaml` | Credential-shaped path or payload regex matches. | Change `SECRET_PATH_RE` / `SECRET_VALUE_RES` in `hooks/runtime_guard.py`, or hook registration in the named profile config. This is not a recommended blocker to weaken. |
| Hermes mutation of protected paths | **BLOCKED/PROTECTED** | `hooks/runtime_guard.py::PROTECTED_PATH_PATTERNS` and `evaluate()` | A mutating tool/terminal command targets North Shore, Telegram bridge, dashboard code, protected queue routing configs, or named legacy categories. | Change `PROTECTED_PATH_PATTERNS` or remove the hook from a specific Hermes profile. Prefer explicit scoped work through Codex rather than weakening the shared guard. |
| Hermes direct connector send/post/publish/mutation | **BLOCKED/PROTECTED** | `hooks/runtime_guard.py::evaluate()` | A direct connector mutation/action slug or direct send phrase is used outside the single-command governed adapter path. | Change `EXTERNAL_ACTION_RE`, `DIRECT_SEND_RE`, or `SAFE_ADAPTER_CALL_RE`; substantive approval policy lives in `connectors/composio_access_adapter.py`. |
| Generic Composio read action | **AUTO** | `connectors/composio_access_adapter.py::command_tool_run()` / `command_run()` | Gmail is additionally limited by `connectors/gmail_draft_policy.py`; invalid/unregistered actions fail. | Change the connector registry/policy or Gmail policy. |
| Generic Composio external mutation from CLI | **EXACT AUTHORITY** | `tools/aos_orchestration.py::action_authorization()`; `connectors/composio_access_adapter.py::authorize_external_mutation()`, `command_tool_run()`, `command_run()` | Operator/internal delivery is automatic when the exact recipient is in `queue/notifications.json`. A third-party mutation requires an exact Liam-authored action, target, and command on the queue item. Complete agreed Calendar context is automatic. Agent-initiated third-party actions and ambiguous Calendar details stop. Publish/upload/send keep their existing review and CASL checks; secret-shaped payloads always fail. | Supply the exact action/target command once, complete the Calendar agreement fields, or change the internal recipient allowlist. Do not add a second approval after an exact Liam command. |
| Generic Composio mutation from dashboard `/api/connectors/composio/action` | **BLOCKED/PROTECTED** | `dashboard/backend/main.py::composio_action()` → `_run_composio_adapter()` → adapter `tool-run` | The dashboard route supplies neither `--confirmed` nor queue-item approval arguments, so mutation verbs are refused. Read actions remain usable. | A code change to this endpoint/contract would be required; changing queue data alone cannot open this path. |
| Gmail draft creation through the dedicated adapter | **ALLOWLISTED** | `connectors/gmail_draft_policy.py`; `connectors/gmail_draft_adapter.py::GmailDraftAdapter.create_draft()` | Only `GMAIL_CREATE_EMAIL_DRAFT` is allowed; malformed inputs, duplicate/indeterminate recovery state, provider failures, or prospect validation/CASL conditions stop it. Send/reply/forward/schedule/update/delete/label actions remain forbidden on generic Gmail routing; internal email uses AgentMail. | Change the exact authority contract in `gmail_draft_policy.py` and validation in `gmail_draft_adapter.py`. Draft authority does not grant send authority. |
| Third-party send stub in dashboard | **EXPLICIT APPROVAL** | `dashboard/backend/main.py::_write_external_dry_run_receipt()` | Typed confirmation must equal `SEND <recipient>`. Even when accepted it is dry-run only and transmits nothing. | This path cannot be made live through config; it requires a code/wiring decision. |
| Liam/internal email or AgentMail delivery | **AUTO / ALLOWLISTED** | `tools/aos_orchestration.py::action_authorization()`; `dashboard/backend/main.py::_agentmail_digest_attempt()`; `queue/notifications.json`; morning-brief path in `connectors/composio_access_adapter.py::send_authorized_morning_brief_agentmail()` | Recipient not in `agentmail_internal`, invalid provider contract, duplicate idempotency key, provider failure, or secret-shaped content blocks delivery. An allowlisted delivery never enters `human_review` merely because it is tagged `send`/`external`. | Edit `queue/notifications.json::allowlist.agentmail_internal`. |
| Operator Telegram message/file delivery | **AUTO / ALLOWLISTED** | `tools/aos_orchestration.py::action_authorization()`, `prepare_telegram_send()`; `queue/notifications.json::allowlist.telegram` | Recipient is not allowlisted; a prior send exists; or a durable intent exists without a result, which refuses automatic retry pending reconciliation. Message and file delivery use the existing bridge path and do not enter `human_review`. | Edit `queue/notifications.json`. Immediate Telegram-origin run/completion replies remain active. The recurring 10-minute escalation is currently disabled by `--skip-telegram-escalation` in `aos-runner.service`; change that unit flag and restart the service to enable it. |
| Calendar booking/change/cancellation | **EXACT AUTHORITY** | `tools/aos_orchestration.py::action_authorization()`; governed Composio adapter | Liam's exact action+target command is automatic. Supplied meeting/transcript agreement is automatic only with date, time, participants, and timezone. Missing material detail routes to one `needs_input` clarification; agent-initiated action remains approval-gated. | Supply the one missing material detail or issue an exact action+target command. |
| David decides conversation vs execution | **AUTO** | `rules/david_execution_handoff.md`; `dashboard/backend/main.py::_david_execution_handoff()`, `_hermes_objective_from_handoff()` | Material ambiguity makes David ask one question and emit no handoff. External/protected intent still hands off; it does not ask early or bypass downstream gates. | Change `rules/david_execution_handoff.md` and the handoff parser/router in `dashboard/backend/main.py`. |
| Native Hermes memory write in David | **EXPLICIT APPROVAL** | `~/.hermes/profiles/david/config.yaml`: `memory.write_approval: true` | A native memory write asks for approval under Hermes's native memory tool. This setting does not gate the separate TTROS Brain MCP writer. | Set `memory.write_approval` in David's profile config. |
| Ordinary durable Business Brain learning through MCP | **AUTO** | `tools/brain_memory_mcp.py::remember_brain_knowledge()` | Refuses unsafe pointer/section/body, missing source/session provenance, and commitment/consequential language matched by `COMMITMENT_RE`. | Change ordinary placement in `tools/brain_memory.py` and the commitment regex/validation in `brain_memory_mcp.py`. Keep commitments on an explicit Liam-confirmation path. |
| Dashboard quick capture to Brain inbox | **AUTO** | `dashboard/backend/main.py::dashboard_capture()` → `tools/business_brain_inbox.py::capture_text()` | Unsafe/unavailable canonical inbox, invalid text/capture identity, or boundary failure. It writes inbox only and does not promote. | Change the dashboard endpoint or inbox validation. |
| Memory Intake / explicit David attachment ingest | **AUTO** | `dashboard/backend/main.py::memory_intake_ingest()`, `_try_ask_david_explicit_ingest()`, `_run_memory_intake_capture()` | Requires an explicit Ingest action or an explicit ingest phrase plus attachment. Scope/path, byte-preservation, semantic-card, index-integrity, or downstream validation failures return failed/needs-attention (not queue `needs_input`). | Change the explicit-phrase matcher or intake validation in `dashboard/backend/main.py` / `tools/source_intake.py`. |
| Direct dashboard edit of an existing permitted Brain note | **AUTO** | `dashboard/backend/main.py::dashboard_save_memory()` | Refuses denied/out-of-scope pointers, stale `expected_revision`, invalid content, or failed persistence verification. No second approval gate exists after Liam clicks Save. | Change permitted pointers in `context/client_scope_registry.json`; concurrency/content checks are in `_dashboard_memory_note_path()`, `_validate_dashboard_memory_content()`, and `dashboard_save_memory()`. |
| Business Brain machine promotion | **ALLOWLISTED** | `tools/business_brain_promotion.py::evaluate_promotion()` / `PromotionWriter.apply()` | Automatic write is allowed only for `generated_marker_section` at `business_brain:index/MEMORY_INDEX.md` with marker `block-2-outcome-index`. Target/marker mismatch falls to review. Never classes and scope violations refuse outright. | Safest widening point: add an exact target+marker under `ENABLED_AUTOMATIC_RULES`; never/review class sets are beside it. |
| Business Brain review-tier promotion | **EXPLICIT APPROVAL** | `tools/promotion_review_queue.py::PromotionReviewQueue.create_or_get()`; `tools/business_brain_promotion.py::PromotionWriter.apply()` | Proposal sits in queue `human_review`; writer refuses without an accepted `human_review` approval reference. | Approve the exact proposal, then call the writer with that reference. Change `REVIEW_CHANGE_CLASSES` only if Liam deliberately reclassifies a whole consequence class. |
| Business Brain never-tier promotion | **BLOCKED/PROTECTED** | `tools/business_brain_promotion.py::NEVER_CHANGE_CLASSES`, `evaluate_promotion()` | Secrets/credentials/auth, raw queue/runtime/log trees, speculation-as-fact, source/cloned/raw communications, or protected/out-of-scope material. | Change `NEVER_CHANGE_CLASSES`. These are unsafe candidates for blocker removal. |

## Queue status creation

### What creates `blocked`

- `run_queue_item()` sets it on worker timeout, non-zero worker exit, reported worker failure, Hermes review timeout, or a pre-completion exception; stale/dead `agent_working` recovery also sets it.
- A Hermes/executive objective child that does not pass within its retry limit is forced to `blocked`; an executive child failure also blocks its parent. A failed final executive synthesis blocks the parent.
- Liam can set it through dashboard review **Block/Reject** (note required), Telegram rejection of one bound pending item, the generic status endpoint, or receipt attachment with status `blocked`.
- A notification result named `blocked` (for example, recipient not allowlisted) does **not** change the queue item to `blocked`; it records a blocked notification while preserving the item's status.

### What creates `needs_input`

- An ordinary (non-Hermes-objective) run that receives no `PASS` after its two attempts.
- A successful run whose item explicitly has `on_complete: needs_input`.
- Hermes decomposition returning a clarification question creates a new `needs_input` item.
- A Calendar action tagged for external effect with ambiguous date, time,
  participants, or timezone asks one clarification.
- Liam selecting **Needs changes** on a `human_review` item, or the generic status/receipt endpoints setting it directly.

### What creates `human_review`

- A passing run with `on_complete: human_review`, or an agent-initiated/unapproved
  third-party effect tagged `external`, `outbound`, `send`, `client_facing`,
  `payment`, or `calendar`.
- Generic effect tags do not override an allowlisted operator/internal
  delivery, an exact Liam-authorized action, or complete agreed Calendar context.
- Completion of all children for a normal workflow parent.
- Exhaustion of the three-attempt Hermes orchestration child loop moves its parent to `human_review` (the child itself is `blocked`).
- Filing a Business Brain review-tier promotion proposal.
- The generic status/receipt endpoints can set it directly.

`human_review` closes only through explicit **Approve**, **Needs changes**, **Block**, or **Reject** actions. Generic Telegram approval refuses external/destructive items and requires an exact action+target route instead.

## Old rules still reachable

No old/obsolete permission code can block **normal** local work.

- `hooks/b7_test_material_guard.py` is still wired to David, but `evaluate()` is inert unless the process has `TTROS_BRAIN_ROOT`; only the B7 harness launchers set that marker. During a B7 run it blocks David's generic file/search/code/session/terminal tools and B7 paths.
- `tools/aos_orchestration.py::_historical_acceptance_gate()` is still reachable only for the specifically tagged immutable `orchestration_acceptance` fixture's step 2. It does not affect normal workflows.
- Named legacy path patterns remain in `hooks/runtime_guard.py`; they only prevent Hermes from writing those paths. They are protective deny rules, not dependencies on an old runtime.

## Safest ways to reduce blockers

1. Change per-item `allowed_actions`, `stop_conditions`, `on_complete`, `review`, tags, and dependencies instead of weakening shared enforcement.
2. Use a named-scope token-fuse override/reset rather than raising/removing the global fuse.
3. Adjust notification recipients in `queue/notifications.json`; this affects delivery, not task execution.
4. If a legitimate Hermes task needs a currently protected local path, scope it to Codex or narrow one exact `runtime_guard.py` path rule. Do not relax secret, client-isolation, external-send, or never-tier Brain rules globally.
5. Add only exact target+marker pairs to `ENABLED_AUTOMATIC_RULES` for proven deterministic Brain writes; leave consequential classes review-tier.

## Primary edit points

- Queue scope/gates/status behavior: `dashboard/backend/main.py`, `tools/aos-orchestration-runner.py`, `tools/aos_orchestration.py`, `tools/aos-queue.py`
- Queue profile/model routing: `queue/lane_profiles.json`, `queue/model_routes.json`
- Codex local permission posture: `tools/aos_codex_policy.py`
- Hermes hard tool guard: `hooks/runtime_guard.py` and the live configs under `~/.hermes/profiles/*/config.yaml`
- Connector approval: `connectors/composio_access_adapter.py`, `connectors/gmail_draft_policy.py`, `connectors/gmail_draft_adapter.py`
- Recipients/escalation window: `queue/notifications.json`; recurring escalation enablement: `/home/liam/.config/systemd/user/aos-runner.service`
- Business Brain write classes: `tools/brain_memory_mcp.py`, `tools/business_brain_promotion.py`, `tools/promotion_review_queue.py`, and `context/client_scope_registry.json`
- Token fuse: `tools/step6_cost_control.py` or the scoped dashboard/Telegram override interfaces

Token usage: unavailable from current CLI output.
