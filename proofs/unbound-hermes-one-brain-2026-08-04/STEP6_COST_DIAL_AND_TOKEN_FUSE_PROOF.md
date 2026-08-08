# Step 6 — one cost dial and one 500,000-token fuse

> Point-in-time proof · Created: 2026-08-04 · Verdict: **PASS**

Step 6 is complete. Steps 7–8 were not started. The implementation uses the
existing `queue/token_ledger.jsonl`, model-price contract, Context Assembler,
operator notification formatter, and runtime status surface. It does not add a
second ledger, notifier, queue, scheduler, or alert database.

## Preserved baseline

Before edits, the repository was already substantially dirty with accepted
Steps 0–5 and unrelated dashboard/queue work. That status was recorded and all
unrelated changes were preserved. The local runtime was healthy with backend,
frontend, and runner processes ready. The two live token-ledger schemas,
`scripts/model_prices.json`, model-call constructors, callers, context guards,
session guards, and notification/status machinery were inspected before the
Step 6 implementation.

The canonical queue remained byte-exact against the Step 5 baseline after the
implementation and live proof: 475 rows, SHA-256
`746fdea55682b9633a92ba3447b0304589e2cc9dca0f6ec3563a5c8652ee3228`.

## Before/after control disposition

| Live mechanism before Step 6 | Callers/effect | Final disposition |
|---|---|---|
| Context Assembler typed boundary, Brain selection, provenance and per-block counts | Hermes, dashboard, Telegram shared path, workers, Codex/Claude dispatch | **KEEP.** Mandatory and independent of cost dial/fuse. Selected blocks are never silently truncated. |
| Context Assembler soft token budget | Assembler emits a visible warning only | **KEEP.** Advisory telemetry; it removes no block and triggers no pause/model change. |
| `model_auto_compact_token_limit=75,000` | Native Codex session hygiene | **KEEP.** Automatic compaction only; full required assembled context remains in the prompt and its regression fixture exceeds the former 64 KiB cap. |
| 75,000 cumulative-token forced Codex handoff | Backend and queue Codex runners | **REPLACED BY 500K FUSE.** Removed. |
| 50% context stop/warning | Codex policy, backend, queue and weekly rollup | **REMOVED/NEUTRALISED AS OVERLAPPING.** Context percentage remains visible telemetry only. |
| Four-handoff maximum | Backend and queue Codex runners | **REPLACED BY 500K FUSE.** Removed with recursive handoff execution. |
| 64 KiB fresh-prompt ceiling | Codex prompt preparation | **REMOVED/NEUTRALISED AS OVERLAPPING.** Required assembled context is retained. |
| Cheap/strong/cheapest lane defaults and escalation-driven model changes | Department cards and work-item budget labels | **REPLACED BY COST DIAL.** The only values are `light`, `standard`, `heavy`; review escalation does not secretly change model tier. |
| Implicit Codex default model/reasoning | Backend and queue Codex constructors | **REPLACED BY COST DIAL.** Actual model is pinned and visible as `gpt-5.5`; dial maps deterministically to low/medium/high reasoning effort. |
| Placeholder zero-dollar prices and unknown-model zero fallback | Ledger finalisation and rollups | **REMOVED.** Verified effective-dated prices are used; unknown/inapplicable price is `unpriced`, never false zero. |
| Provider/startup/execution/review/finalisation timeouts | Process supervision and failure receipts | **KEEP.** These are explicit infrastructure-liveness boundaries, not token/context/model controls; failures are visible and partial exact usage is retained when exposed. They do not compact, downgrade, or silently continue. |
| Fresh `--ephemeral` / Hermes `--oneshot` invocation transport | Native subprocess calls | **KEEP.** This is transport isolation, not a work-item/session cognition limit: sticky state, assembled context and ledger scope persist across invocations. |
| External-action and protected-path checks | All action-capable routes | **KEEP.** Neither the dial nor fuse override changes permissions. |

No active lower token breaker, context-percentage breaker, handoff maximum,
prompt byte cap, or silent model downgrade remains in the protected model path.

## Canonical accounting formula

```text
canonical invocation total = provider-reported input + provider-reported output
canonical scope total      = sum(canonical invocation totals for unique invocation IDs)
```

Cached input is displayed separately and never added to provider input again.
For OpenAI/Codex, cached input is a subset of provider-total input and fresh
input is `input - cached input`. A provider that exposes an independent cache
read counter retains and prices that counter without adding it to the fuse.
Reasoning is a labelled subset of output. Missing/corrupt input or output makes
accounting unknown and the named scope fails closed; a fuse override cannot
turn unknown accounting into zero. Separate invocations and implementation
usage remain separate rows.

The historical fixture reconciles exactly:

```text
564,207 input + 77,915 output = 642,122 canonical tokens
18,738,432 cached input is displayed separately and not added again
21,622 reasoning is displayed within output
```

It crosses advisory, warning and pause in order exactly once and blocks the
next invocation without resuming the historical Codex session.

## Cost dial contract

The canonical values are `light`, `standard`, and `heavy`. Precedence is:

```text
work-item/session override -> queue/notifications.json global value -> standard
```

The runtime exposes effective value and source. Invalid overrides and invalid
global values fail visibly. For Codex, the values deterministically select
`low`, `medium`, and `high` reasoning effort while the actual selected model is
pinned as `gpt-5.5`. The dial never alters assembled-context completeness,
Brain access, action permissions, protected-path permission, or the 500,000
threshold. Other providers retain their configured model and record the actual
provider-returned identity, so no model substitution is hidden.

## Fuse and override contract

The one shared breaker is scoped to a named work item or sticky/executive
session and stored as invocation evidence in the existing ledger:

| Threshold | Event | Effect |
|---:|---|---|
| 250,000 / 50% | advisory | Informational only |
| 400,000 / 80% | warning | Informational only |
| 500,000 / 100% | pause | Completed call is recorded; next call is blocked |

Thresholds are derived from durable unique invocation IDs and survive restart
without duplication. `override` and `reset` append idempotent, named-scope
evidence to the same ledger. Override changes only known fuse state, is visible
in status, is revocable, and leaves unrelated scopes and all action boundaries
untouched.

Threshold messages are rendered through the existing canonical operator work
item notification formatter. The local formatting regression exercised that
path; no Telegram message was sent.

## Pricing evidence

`scripts/model_prices.json` version `2026-08-04` has effective dates, cached
input treatment and primary provider sources for every active supported model:

| Model | Effective contract on 2026-08-04 |
|---|---|
| `gpt-5.5` | OpenAI standard/long-context pricing; effective 2026-04-23 |
| `claude-opus-4-8` | Anthropic pricing; effective 2026-05-27 |
| `claude-sonnet-5` | Introductory Anthropic pricing through 2026-08-31; future rate recorded separately |
| `claude-haiku-4-5` | Anthropic pricing; effective 2025-10-01 |

Unknown models are explicitly `unpriced`. Token counts remain exact. The named
pricing verifier checks numeric input/cache/output rates, applicability dates,
source URLs, and the absence of a zero-dollar default.

## Model-call coverage

| Surface | Protected path |
|---|---|
| Sticky Hermes and dashboard consultations | Context Assembler -> Hermes wrapper preflight -> provider -> exact usage record |
| Telegram conversation | Shared backend/operator-lean path -> same assembler and Hermes wrapper |
| Codex direct and queued dispatch | Typed assembled context/work item -> shared preflight -> pinned model/dial effort -> exact terminal usage record |
| Claude Code dispatch | Typed assembled context -> shared preflight -> exact usage or explicit unknown/fail-closed record |
| Departments and orchestrator/review | Scoped Hermes coordinator flags -> native hook wrapper marker/preflight -> usage file -> ledger |
| Scheduled model work | Same coordinator/native hook boundary; no raw-prompt runner bypass |
| Worker execution/context packs | Fresh worker pack -> protected Codex/Hermes constructor |
| Capture classifier and Step 5 detector | Deterministic path; zero model invocations |

The native pre-call hook refuses a protected call without the canonical wrapper
marker and runs fuse preflight before context assembly. The coverage verifier
checks every listed live surface and the tests prove raw prompts are rejected.

## Step 5 attribution

The named attribution verifier preserved the accepted split:

```text
Detector:               0 input, 0 output, 0 model invocations
Hermes interpretation: 58,504 input, 2,320 output, 1,346 reasoning,
                       60,824 canonical total, below all thresholds
```

## Bounded runtime proof

After a local runtime restart, one direct request was sent to
`/api/hermes/message`: “Reply exactly STEP6_RUNTIME_OK. Do not use tools.” The
response was exactly `STEP6_RUNTIME_OK`. No tool or external action ran.

Runtime invocation `hermes-5d0824a793bb4bbf810d025c6e139c15`, scope
`session:dashboard-7b683e78d6094df5916de809af33fbf8`:

```text
provider: openai-codex
actual model: gpt-5.5
cost dial: standard (global_config)
input: 71,587
cached input: 0
output: 26
reasoning: 16
canonical total: 71,613
cost: $0.358715 (priced, version 2026-08-04, effective 2026-04-23)
fuse: 14.323%; no threshold; not paused; no override
```

The live ledger row passed `queue/token_ledger_schema.json`. The status API
returned the same dial, model, breakdown, cost, fuse percentage and state.
After reload the backend, frontend and runner were healthy and ready.

## Exact validation commands and concise outcomes

- `dashboard/backend/.venv/bin/python tools/verify_step6.py all` — exit 0;
  accounting, pricing, coverage, guards, historical fixture and Step 5
  attribution all PASS.
- `dashboard/backend/.venv/bin/python -m unittest -v tests.test_step6_cost_fuse`
  — 13/13 PASS, including accounting/cache semantics, unknown fail-closed,
  dial precedence/invalid values, prices, threshold transitions, retry/restart
  and concurrent-completion idempotency, pause, scoped override/reset, scope
  isolation, notification formatting, protected runner and compaction preservation.
- Combined Step 6/ledger/assembler/worker/Step 5/queue/orchestration/runtime suite
  — 183/183 PASS in 40.519s.
- Step 4 plus affected Business Brain/full-loop/executive/search suites — 67/67
  PASS in 4.198s.
- `dashboard.backend.test_composio_hermes` backend/orchestration suite — 219/219
  PASS in 105.967s.
- `tests.test_telegram_conversational_routing` — 15/15 PASS in 30.706s.
- Python compilation, shell syntax, four changed JSON contracts, three
  non-protected YAML files, and `git diff --check` — exit 0.
- Runtime restart, bounded model call, status query, live ledger-schema check,
  and final runtime status — exit 0 / healthy.

No Step 6 frontend file was changed, so no frontend build was required.

## Acceptance gate

| # | Result | Verifier/evidence |
|---:|---|---|
| 1 | PASS | Control disposition table above |
| 2 | PASS | Dial config/status and focused tests |
| 3 | PASS | Precedence, reasoning mapping and invalid-value tests |
| 4 | PASS | Guard/coverage verifier and shared preflight callers |
| 5 | PASS | Threshold fixture: 50/80/100 once |
| 6 | PASS | Pause/next-call/override/reset/isolation fixture |
| 7 | PASS | `verify_step6.py accounting` |
| 8 | PASS | `verify_step6.py pricing` |
| 9 | PASS | `verify_step6.py coverage` plus protected-hook tests |
| 10 | PASS | `verify_step6.py guards`, full-prompt and model-pin regressions |
| 11 | PASS | `verify_step6.py historical-fixture` |
| 12 | PASS | `verify_step6.py step5-attribution` |
| 13 | PASS | Native compaction/full-context focused regression |
| 14 | PASS | Bounded runtime call and `/api/cost-control/status` |
| 15 | PASS | 183-test affected suite, 67 Step 0–5 tests, 219 backend tests, 15 Telegram tests |
| 16 | PASS | Protected-path diff empty; queue hash/row count exact; no external action |

## Protected boundary

No North Shore workspace, Telegram bridge interior, protected route JSON,
Hermes global/default profile, environment/credential/authentication file, or
secret was inspected or modified. The protected-path `git diff` and status
sets were empty. Immutable work items `AOS-2026-0071`, `0073`, `0074`, `0075`,
`0174`, and `0175` remain present exactly once within the byte-identical queue.
No Telegram/email/LinkedIn/CRM/Calendar/Drive action, publication, deployment,
recurring job, repository commit/push, vault push, or destructive deletion
occurred.
