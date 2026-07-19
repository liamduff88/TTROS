# Codex retained-context repair proof — 2026-07-19
> Revisit: when Codex JSONL, fresh-session, correction, or token-pricing semantics change. · Last touched: 2026-07-19.

PASS

## Files touched

- `/home/liam/.local/bin/aos-codex`
- `tools/aos_codex_policy.py`
- `tools/aos-queue.py`
- `dashboard/backend/main.py`
- `dashboard/frontend/src/launcherPrompts.js`
- `dashboard/frontend/tests/launcherPrompts.test.js`
- `workflows/prompt_templates/codex_workflow_runner.md`
- `scripts/token_rollup.py`
- `tests/test_codex_context_repair.py`
- `tests/test_aos_codex_policy.py`
- `tests/test_aos_queue.py`
- `tests/test_workflow_prompt_templates.py`
- `context/TOKEN_POLICY.md`
- `rules/token_budget.md`
- `hooks/token_budget_check.md`
- `decisions/2026-07-19-codex-executable-context-handoff.md`
- this proof artifact

`decisions/DECISIONS.md` was not changed by this closeout; its pre-task bytes
and dirty hunks are preserved exactly.

## Caller/session-isolation proof

The live caller inventory was built with bounded searches excluding protected
route/lane JSON, Telegram bridge interiors, legacy runtime state, secrets, and
existing runtime collections.

| Live surface | Route to Codex | Enforced constructor |
|---|---|---|
| `/home/liam/.local/bin/aos-codex` | no-fallback POST to `/api/wsl/codex`; argument or stdin task | dashboard `_run_codex_local` |
| `/home/liam/.local/bin/aos-hermes codex ...` | `exec aos-codex` | dashboard `_run_codex_local` |
| Dashboard direct Codex API | `/api/wsl/codex` | dashboard `_run_codex_local` |
| Dashboard copy launcher | supervised `aos-codex '<TASK>'` | dashboard `_run_codex_local` |
| Dashboard queue/Cockpit run | `/api/queue/items/{id}/run` | dashboard `_run_codex_local` |
| Detached orchestration runner | POSTs the same queue run endpoint | dashboard `_run_codex_local` |
| Explicit `tools/aos-queue.py codex-run` | local supervised CLI boundary | `run_codex_work_item` |
| Dashboard manual queue prompt | `aos-queue.py codex-run ... --prompt-file -` | `run_codex_work_item` |
| Workflow runner template | supervised `aos-codex` with prompt on stdin | dashboard `_run_codex_local` |
| Hermes-created Codex child | queue child owner `codex` | dashboard `_run_codex_local` |
| Hermes correction attempt | fresh compact correction through queue worker | dashboard `_run_codex_local` |

The only other `/home/liam/.local/bin` match was a dated `.bak_...` file; it is
not executable routing and its legacy interior was not inspected.

Both constructors receive their immutable command from
`tools/aos_codex_policy.py`:

```text
/home/liam/.local/npm/bin/codex --sandbox danger-full-access --ask-for-approval never -C /home/liam/agentic-os-live exec --ephemeral --skip-git-repo-check --json --color never -
```

There is no `resume`, `--last`, persisted-session, or same-session
auto-compaction argument. The constructors accept no caller override for root,
sandbox, approval mode, or session mode. `require_clean_session_id()` now
requires exactly one valid `thread.started` event: missing, invalid, two
different IDs, or the same event repeated twice all fail explicitly without a
synthetic fallback or accepted result.

### Verified real sessions

The existing bounded real-process artifacts were re-parsed without printing
their raw contents. Every artifact has exactly one `thread.started`, contains
its own unique sentinel, contains none of the named foreign sentinels, and has
one final structured usage snapshot.

| Role | Real session ID | Provider input | Cached | Fresh | Output | Reasoning |
|---|---|---:|---:|---:|---:|---:|
| unrelated alpha / `DIRECT_ALPHA_7F3C` | `019f77fe-f84d-7393-80ad-431d3049be3c` | 12,941 | 8,960 | 3,981 | 26 | 12 |
| unrelated beta / `DIRECT_BETA_91D2` | `019f77ff-0a42-7b62-9bd2-db3ac38a969b` | 13,242 | 9,984 | 3,258 | 12 | 0 |
| compact correction / `CORRECTION_GAMMA_5A6E` | `019f77ff-181c-77b1-929f-f0b78082e576` | 13,471 | 9,984 | 3,487 | 139 | 121 |

Raw evidence remains at:

- `logs/codex_sessions/codex-871ab916b7284f88b0da4217a23a0d3d.stdout.jsonl`
- `logs/codex_sessions/codex-c624c412a66940e5aba59427ae5a3c6c.stdout.jsonl`
- `logs/codex_sessions/codex-8d2dc6fa006b463283cc20c6ba52f101.stdout.jsonl`

## 50% executable handoff proof

The default configured boundary is 75,000 cumulative tokens, representing the
50% policy boundary. It can be changed only through the positive-integer
`AOS_CODEX_CONTEXT_HANDOFF_TOKENS` runtime configuration; four successive
fresh handoffs are the fail-closed maximum.

`test_cumulative_threshold_writes_handoff_and_continues_in_new_session` uses a
50-token deterministic threshold. Its first fake process emits two cumulative
snapshots (35 then 60 tokens), one real-shaped `thread.started`, and then waits.
The dashboard supervisor observes the second snapshot, terminates that process,
writes a compact `logs/codex_handoffs/codex-<invocation>.md` receipt, and starts
a new process from only that path:

```text
threshold-fresh-1 --handoff--> threshold-fresh-2
```

The first prompt contains `THRESHOLD_ORIGINAL_TASK_SENTINEL`; the handoff
receipt retains its compact task summary; the second prompt contains the
handoff path and does not contain that original sentinel or
`LARGE_THRESHOLD_LOG_SENTINEL_`. The large sentinel remains only in the first
raw JSONL artifact. Two independent token-ledger calls are proven, one for each
session.

`test_queue_cli_threshold_reconciles_each_fresh_session` proves the standalone
queue constructor independently:

```text
queue-threshold-fresh-1 --handoff--> queue-threshold-fresh-2
```

Its deterministic token ledger contains two rows in that order. The second
prompt contains only the generated handoff path, not
`QUEUE_THRESHOLD_ORIGINAL_SENTINEL`. Neither path enables or relies on
same-session auto-compaction or transcript replay.

## Cumulative accounting and pricing proof

The final `turn.completed.usage` object is authoritative. Repeated cumulative
events replace prior events; they are never summed. A fixture with snapshots
`100/40 cached/20 output/5 reasoning` followed by
`150/60 cached/30 output/7 reasoning` parses as exactly the second snapshot:

```text
provider input=150; cached=60; fresh=90; output=30; reasoning=7; total=180
```

It does not become input 250 or output 50. A malformed JSON line is ignored;
an incomplete final `turn.completed` does not backfill from the older complete
event. The queue parser fails explicitly and the direct backend marks terminal
usage unavailable. Missing terminal usage, cached input greater than provider
input, and reasoning greater than output have named regression failures.
Closing-context metadata absent from JSONL remains exactly
`unavailable from current CLI output`; no percentage is inferred from tokens.

The cache/pricing fixture is:

```text
provider-total input=1,000
cached input=900
fresh input=100
output=100 (including reasoning=20)
fresh rate=$2.00/M; cache-read rate=$0.50/M; output rate=$10.00/M
cost=(100*2.00 + 900*0.50 + 100*10.00)/1,000,000 = $0.001650
```

Parser, canonical ledger row, receipt Markdown JSON block, token sidecar,
dashboard source summary, and weekly rollup all retain input 1,000—not 1,900—
with fresh 100 and cached 900. Reasoning 20 is metadata within output 100 and
is not added to output totals or priced a second time. Legacy `input` remains
provider-total input, is charged once when no cache split exists, and is never
labelled fresh.

### Real deterministic rollup excerpt

Command: a bounded Python fixture imported `scripts/token_rollup.py` and called
`rollup_week('2026-W29', ...)` with three reported sessions. Stored
`est_cost_usd=999` values were ignored and cost was recomputed from the fixture
prices.

```json
{
  "totals": {"input": 3000, "output": 130, "est_cost_usd": 0.003012},
  "warnings": [
    "cache_ratio > 20: codex session ratio-24 ratio=24.0",
    "cache_ratio > 20: codex session ratio-999 ratio=999.0",
    "context_pct_at_close > 50: codex session ratio-24 context_pct_at_close=55",
    "context_pct_at_close > 50: codex session ratio-9 context_pct_at_close=51"
  ],
  "top_cache_ratio_session_ids": ["ratio-999", "ratio-24", "ratio-9"],
  "context_ceiling_breaches": [
    {"session_id": "ratio-24", "context_pct_at_close": 55},
    {"session_id": "ratio-9", "context_pct_at_close": 51}
  ]
}
```

## Artifact-retention proof

Bounded synthetic fixtures cover every named large-evidence class:

- raw Codex command output over 30 KiB remains in
  `logs/codex_sessions/*.stdout.jsonl`; returned stdout is a bounded tail;
- large diff, test-output, screenshot data-URI, and browser-evidence sentinels
  from a Hermes child plan are written once under
  `logs/codex_prompt_evidence/`; the child prompt contains only path, bytes, and
  SHA-256;
- correction prompts contain bounded task context, a compact prior-result
  summary, artifact paths, bounded Hermes feedback, and acceptance criteria;
  none of the raw large sentinels is present;
- continuation prompts contain only the compact handoff path and fresh-session
  instructions; the original task and raw streams are not replayed.

The exact synthetic sentinels are `LARGE_DIFF_SENTINEL`,
`LARGE_TEST_OUTPUT_SENTINEL`, `LARGE_SCREENSHOT_SENTINEL`,
`LARGE_BROWSER_EVIDENCE_SENTINEL`, `LARGE_OUTPUT_SENTINEL_`, and
`LARGE_THRESHOLD_LOG_SENTINEL_`. Tests assert they exist in their artifacts and
do not exist in child, correction, or continuation prompts.

## Exact regression commands/results

Direct Codex, direct Claude Code, deterministic routing, Hermes child/correction
orchestration, and backend human review:

```text
dashboard/backend/.venv/bin/python -m unittest -v \
  dashboard.backend.test_composio_hermes.HermesComposioTests.test_codex_supervisor_real_subprocess_captures_prompt_streams_completion_and_exact_tokens \
  dashboard.backend.test_composio_hermes.HermesComposioTests.test_claude_worker_passes_separate_startup_and_execution_timeouts \
  dashboard.backend.test_composio_hermes.HermesComposioTests.test_direct_api_routes_are_preserved \
  dashboard.backend.test_composio_hermes.HermesComposioTests.test_natural_language_explicit_workbench_routes_bypass_hermes \
  dashboard.backend.test_composio_hermes.HermesComposioTests.test_explicit_codex_review_request_uses_native_hermes_as_outer_coordinator \
  dashboard.backend.test_composio_hermes.HermesComposioTests.test_hermes_orchestration_children_pass_after_zero_one_and_two_corrections \
  dashboard.backend.test_composio_hermes.HermesComposioTests.test_hermes_orchestration_third_failed_review_escalates_once_without_fourth_attempt \
  dashboard.backend.test_composio_hermes.HermesComposioTests.test_dashboard_queue_review_close_marks_human_review_done_with_note_receipt \
  dashboard.backend.test_composio_hermes.HermesComposioTests.test_human_review_detail_shows_substantive_receipt_and_note_save_cannot_close \
  dashboard.backend.test_composio_hermes.HermesComposioTests.test_workflow_review_creates_one_bounded_correction_and_returns_to_review \
  dashboard.backend.test_composio_hermes.HermesComposioTests.test_human_review_close_uses_existing_review_close_and_correction_paths
```

Result: 11 tests passed in 8.237s.

Queue lifecycle, cumulative parser, policy, workflow, paths, and orchestration:

```text
dashboard/backend/.venv/bin/python -m unittest -q \
  tests.test_codex_context_repair \
  tests.test_aos_codex_policy \
  tests.test_aos_queue \
  tests.test_aos_orchestration \
  tests.test_workflow_prompt_templates \
  tests.test_aos_paths
```

Result: 110 tests passed in 17.962s. The post-manual-caller adjustment reran
the directly affected 23 tests in 1.017s; all passed. The final workflow/
launcher-only check passed 15 tests. The full backend module
also passed all 184 tests; its only output was an unrelated existing
`datetime.utcnow()` deprecation warning.

Frontend human-review tests:

```text
cd dashboard/frontend && node --test \
  tests/reviewCard.test.js tests/queueState.test.js tests/launcherPrompts.test.js
```

Result: 17 tests passed. Full `npm test`: 39 tests passed.

Production build:

```text
cd dashboard/frontend && npm run build
```

Result: PASS; Vite transformed 1,652 modules and built production assets in
2.07s on the final recorded run.

`python3 -m py_compile` passed for all changed Python implementation and test
modules. `git diff --check` passed.

## Dirty-work preservation

Before task edits:

```text
decisions/DECISIONS.md sha256 = 51f138e37a8c809e88c20b766a3f638f9796cecc01a5d591fd0b32b6c704bba0
pre-task diff sha256           = 86ad48983580639bf32e3368ec59563d915f7844a78d04b4025b6f470bee341f
```

After implementation, `cmp -s decisions/DECISIONS.md
/tmp/aos-retained-context-decisions-before.md` passed and the file SHA-256 is
still `51f138e37a8c809e88c20b766a3f638f9796cecc01a5d591fd0b32b6c704bba0`.
The new executable-handoff decision is isolated in
`decisions/2026-07-19-codex-executable-context-handoff.md`. Other unrelated
dirty files and hunks were left in place. No commit or push occurred.

## Protected areas

Not inspected or modified: secrets, credentials, `.env`, protected-path
interiors, North Shore, protected route/lane JSON interiors, Telegram bridge
internals, legacy runtime state, and immutable AOS items. The inactive dated
launcher backup was identified by filename only and not opened. No external or
destructive action occurred.

## Blockers and next action

Blockers: none.

Next action: none required. Merge the standalone decision and focused repair
diff when the surrounding unrelated dirty work is ready.

## Token usage

Exact retained real proof-session totals:

```json
{
  "provider_total_input": 39654,
  "fresh_input": 10726,
  "cached_input": 28928,
  "output": 177,
  "reasoning": 133,
  "closing_context_pct": "unavailable from current CLI output"
}
```

The current supervising Codex conversation's provider counters and closing
context percentage are unavailable from the harness and are not estimated.
