# TOKEN_POLICY.md — one visible dial, one token fuse
> Revisit: on a Hermes/Codex release, provider usage-schema change, or monthly pricing check. · Last touched: 2026-08-04.

## Binding contract

Model cognition has exactly two operator controls:

1. One visible cost/effort dial: `light`, `standard`, or `heavy`.
2. One 500,000 canonical-token fuse per work item or sticky/executive session.

Precedence is scope override → `queue/notifications.json` global value →
documented default `standard`. Invalid values fail visibly. The dial may guide
model/reasoning preference; it never changes assembled-context completeness,
Brain access, action permissions, protected paths, or the fuse threshold.

## Exact accounting

`queue/token_ledger.jsonl` is the canonical durable accounting and Step 6
evidence store. Separate invocations remain separate. When exposed, each row
records provider, actual model, scope, input, cached input, output, reasoning,
canonical total, cost/unpriced state, pricing version/effective date, and time.

Canonical fuse formula:

```text
canonical_fuse_total = provider-reported input + provider-reported output
```

Cached input is always displayed separately and is never added to provider
input again. For Codex/OpenAI usage, cached input is a subset of provider-total
input and fresh input is `input - cached`. For Hermes providers that expose
cache reads as an independent cumulative counter, it is priced as cache
activity but does not enter the fuse total. Reasoning is a labelled subset of
output. Unknown or malformed counters are not zero: the scope fails closed.

`scripts/model_prices.json` is effective-dated. Missing/inapplicable pricing
keeps exact usage and reports `unpriced`; it never produces false zero cost.

## Fuse

```text
250,000 / 50%  advisory (informational)
400,000 / 80%  warning  (informational)
500,000 / 100% pause after recording the completed invocation
```

The advisory and warning do not truncate, change model, compact, or pause. A
crossing invocation completes and records exact usage; the next call is
blocked. Threshold evidence is derived idempotently by scope and invocation ID
from the existing ledger. A scoped override/reset is visible, durable,
idempotent and applies only to the named fuse. It never grants external-action
or protected-path permission. Unknown accounting cannot be overridden as if it
were zero.

## Context and compaction

Context Assembler remains mandatory, shows every block count, and never
silently truncates selected blocks. `model_auto_compact_token_limit` remains
session hygiene. It may summarise retained conversation but must preserve the
assembled context required to understand and complete the task. The former
75,000-token forced handoff, 50%-context stop, four-handoff maximum, and 64 KiB
prompt ceiling are removed.

## Deterministic work

Operations such as the Step 5 detector record zero model invocations. Codex
implementation usage is its own invocation and is never merged with Hermes
runtime usage.

## Enforcement

`tools/step6_cost_control.py`, guarded Hermes launchers and native pre-call
hook, guarded Codex/Claude/backend boundaries, `queue/token_ledger_schema.json`,
`scripts/model_prices.json`, status/override API, and named Step 6 verifiers.
