# PASS — fresh-session Telegram conversational routing repair
> Point-in-time proof · Created: 2026-08-04 · Revisit: if Telegram approval syntax, operator tools, sticky sessions, or One Brain writes change.

## Files changed for this repair

- `dashboard/backend/main.py`
- `dashboard/backend/test_composio_hermes.py`
- `tests/test_telegram_conversational_routing.py`
- `tools/operator_lean_mcp.py`
- `queue/profiles/operator-lean.md`
- `decisions/DECISIONS.md`
- `proofs/telegram-conversation-routing-2026-08-04/PRE_REPAIR_EVIDENCE.md`
- `proofs/telegram-conversation-routing-2026-08-04/REPAIR_CLOSEOUT.md`

## Exact root causes and branches

1. The first conversation did not stall in Context Assembler or Telegram polling. Hermes session `20260804_180247_9c71a6` called `mcp__operator__escalate_to_executive` at UTC `17:02:57.649`; the nested executive returned at `17:03:48.319` after `50.543` seconds. The outer `operator-lean` turn still needed to finish, but `_operator_lean_closeout` supplied `OPERATOR_LEAN_TIMEOUT_SECONDS=90` to `_run_hermes_message`; the outer process was terminated at UTC `17:04:16.312` with no final assistant message.
2. The exact retry entered `_try_telegram_approval` because `_TELEGRAM_APPROVAL_PREFIX_RE` treated any message beginning with `Continue` as item approval.
3. With no explicit item ID, `_try_telegram_approval` admitted 18 historical pending Telegram candidates. Historical rows lacking a chat ID correlated through `_safe_operator_telegram_chats`; AOS-2026-0128 sorted first.
4. `_approval_clarification` returned the candidate list without `direct_reply`. Telegram `compact_telegram_closeout` extracted the first AOS-shaped string and presented it as a failed work item.
5. AOS-2026-0128 was formatter-inserted lookup text only. It was not created, reused, bound, resumed, accepted, or changed.
6. Stale conversational state was not the routing cause. A stale delivery ID was a separate potential leak in `_operator_delivery_item`; closeouts now bind only to IDs newly added during that turn.

## Behavior changed

- Approval without an AOS ID must be a complete bounded approval phrase. `Continue from ...`, `continue the interview`, priorities, `save this`, `next question`, and negative execution language remain conversation.
- Legacy natural-language queue prefixes no longer create items through this Telegram endpoint.
- Only the explicit pre-model `/work codex|claude|hermes ...` route can create or execute work.
- The operator MCP exposes its stable schema but its conversational `create_task` implementation is read-only refusal; no queue mutation implementation remains in that server.
- Sticky operator conversation answers priority judgment directly. Its escalation tool returns a direct-surface instruction and contains no subprocess/orchestrator implementation.
- Conversation exceptions cannot bind an existing item by stale delivery metadata.
- The existing backend 90-second model bound and global 500,000-token fuse remain unchanged. Removing the demonstrated nested 50.543-second path repairs the avoidable timeout; the live exact turn completed in 15.321 seconds.

## Real Telegram production proof

The exact 474-byte retry (`sha256 de119f16b7a3c11b9767c363f320e66a2cfb95a47f4e9ca3369fe2f1d8adb2e5`) was passed through the production bridge `post_agent` → `/api/wsl/hermes` → sticky `operator-lean` → `deliver_agent_result` path with delivery `telegram-live-conversation-repair-20260804` and operator reply target `1320777128`.

- Route: `hermes_operator_lean`
- Profile used: `operator-lean`; no fallback
- End-to-end latency: `15.321s`; backend latency: `15.099s`
- Direct reply: `true`
- Reply words: `95` (required maximum: 150)
- Telegram send: `message_sent=true`; documents: none
- Queue created/delta: `false / 0`
- Worker count: `0`
- Orchestrator invoked: `false`
- AOS identifiers in reply: none

Reply delivered:

```text
Saved.

Strategically, this means TTR’s immediate job is not “build the perfect AI business.” It is to pick a narrow enough market to make cold prospecting specific, credible, and repeatable — while building public proof that you understand one buyer’s pain better than a generic AI consultant. The niche should be chosen for access, urgency, ability to pay, fast delivery, and future specialization/product potential.

Single most useful question:

Which buyer group can you realistically reach fastest through your existing network, local access, past experience, or warm-ish credibility — even if the niche is not perfect?
```

## Brain persistence and vault Git evidence

Hermes session `20260804_182515_708280` made exactly one tool call: `mcp__brain__remember_brain_knowledge`.

- Pointer: `business_brain:operating_context/current_priorities.md`
- Section: `current_priorities`
- Knowledge state: `verified_fact`
- Source: `telegram-live-conversation-repair-20260804 / sticky session 5b45fd27ca66ca1e4dbc339c / user message 2026-08-04`
- Statement: Liam needs to choose a practical niche/target for cold prospecting, develop a strong approach, and build visible specialization; the niche is not yet known.
- One Brain transaction result: `success=true`, `external_action=false`
- Priority transaction commit: `4a9f67b82e60fd1745d80f06323bc6478ba84407`
- Priority postimage SHA-256: `e9e22d3c4cb5d1fa2417df3ebda54917824da1a109d14243314903573a003176`
- Normal sticky-session journal commit: `7dbc91a8004ddbc4a7e754ae921242999fee74c9`

Pre-existing unrelated vault modifications remained present and untouched (`memory/offers.md`, `memory/positioning.md`, and five untracked operating-context notes).

## Queue and activity deltas

| Evidence | Before | After | Delta |
|---|---:|---:|---:|
| Queue items | 475 | 475 | 0 |
| Queue SHA-256 | `746fdea55682b9633a92ba3447b0304589e2cc9dca0f6ec3563a5c8652ee3228` | same | unchanged |
| Run-ledger rows | 349 | 349 | 0 |
| Run-ledger SHA-256 | `9f0f7b199a807b88eeb8ff43d11b157162fba6258e56758ed257f0f1fa51f4f9` | same | unchanged |
| Orchestration-event rows | 909 | 909 | 0 |
| Orchestration SHA-256 | `fa92f1c352eac189cb8faf21493320b775cb5c3ca461a44b2e44835e844086fe` | same | unchanged |
| Queue receipt files | 1386 | 1386 | 0 |
| Promotion artifacts | unchanged | unchanged | 0 |
| Conversation token records | 496 | 497 | +1 expected Hermes turn |
| Step 6 token-ledger rows after scoped reset | 1192 | 1193 | +1 expected Hermes turn |

The named scope was deterministically reset before proof because the timed-out invocation left canonical usage unknown. Reset epoch: `fuse_scope_reset:session:5b45fd27ca66ca1e4dbc339c:2`. The global limit remains `500000`; after proof the scope is unpaused at `14590` canonical tokens (`2.918%`).

No queue worker, queue run, orchestrator event, promotion proposal, or third-party external action occurred. The only send was the explicitly required allowlisted internal Telegram reply to Liam.

After this closed live-proof bracket, the required regression suite appended two retained test-probe Step 6 rows (one mocked direct Claude route and one dashboard Hermes-message route), bringing the final token-ledger row count to `1195`. They did not create a queue item, run-ledger row, orchestration event, receipt, worker process, or orchestrator process; they are reported rather than deleted.

## AOS-2026-0128 immutability

- Whole-queue hash unchanged, therefore its queue record is byte-unchanged.
- Primary receipt SHA-256 before/after: `1b7e77501e17a38951ad34dc687f8badef97f48dc72285f7be0f71c47d1444bc`.
- Primary receipt mtime remains `2026-07-17 12:14:03.273187842 +0100`.
- Successful response contains no reference to AOS-2026-0128 or any other work item.

## Services and protected areas

- Restarted only dashboard backend: PID `27281` → `32126`.
- Frontend PID `19386`, runner PID `27412`, and Telegram bridge were preserved.
- No files were changed in `connectors/telegram_bridge/`, protected queue route JSON, North Shore, credentials, secrets, tokens, or authentication state.
- The connector already contained the completed 120-second conversation transport and direct timeout-failure repair; it was exercised/read but not edited.
- No Agentic OS commit or push was made.

## Tests

- Focused before live proof: `24 passed, 5 subtests passed`.
- Approval/operator affected slice: `11 passed, 208 deselected, 7 subtests passed`.
- Post-live affected suites: `361 passed, 65 subtests passed` in `196.70s` (four existing `datetime.utcnow` deprecation warnings).
- Final post-cleanup focus: `25 passed, 218 deselected, 5 subtests passed`.
- `git diff --check`: PASS.

Suites included Telegram conversational routing, One Brain context, Step 6 fuse, unbound runtime drift, queue, paths, and the complete dashboard backend Hermes suite.

## token_usage

```json
{
  "codex_current_repair_session": "unavailable from current harness",
  "live_hermes_proof": {
    "input_tokens": 14230,
    "cache_read_tokens": 11776,
    "fresh_input": 2454,
    "output_tokens": 360,
    "reasoning_tokens": 93,
    "total_tokens": 26366,
    "api_calls": 2,
    "model": "gpt-5.5",
    "provider": "openai-codex",
    "session_id": "20260804_182515_708280",
    "invocation_id": "hermes-ddf6410630a749609dd8965fd0004b7b"
  }
}
```

## Blockers and next action

- Blockers: none.
- Next action: none required; ordinary Telegram conversation is live and green. Use `/work ...` only when execution is intended.
