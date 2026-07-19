# TOKEN_POLICY.md — visible spend and bounded workbench context
> Revisit: on a Hermes/Codex release (usage metadata can reshape) or monthly pricing check. · Last touched: 2026-07-19.

## Purpose
Make token use and retained-context drift visible on every unit of work while
preventing unrelated tasks from inheriting workbench transcripts. This is
metering and session hygiene, not a hard spend throttle.

## Source-of-truth rule
Numbers come from harness/API usage fields only. A field the harness does not
report is named under `unavailable`; it is never estimated or inferred from
prompt size. Provider-total input must not be labelled fresh input.

For Codex JSONL where cached input is included in provider input:

```text
provider_total_input = input_tokens
cached_input = cached_input_tokens
fresh_input = input_tokens - cached_input_tokens
output = output_tokens
reasoning = reasoning_output_tokens
cache_ratio = cached_input / max(fresh_input, 1)
```

Legacy `input` remains provider-total input. Cached input is not added to it
again. New workbench entries carry `input`, `fresh_input`, `cached_input`,
`output`, and `reasoning`; older entries without the additive fields remain
valid. Missing fields use the explicit unavailable marker, not zero.

An incomplete or malformed final `turn.completed` usage object never falls
back to an older complete cumulative snapshot. Queue reconciliation records
usage as unavailable when no exact terminal summary exists; semantic
contradictions such as cached input exceeding provider input fail explicitly.

## Fresh-session contract

1. Every unrelated direct Codex task starts a separate fresh ephemeral
   session. `resume`, `--last`, implicit inheritance, and fallback to an old or
   synthetic session ID are prohibited.
2. A real `thread.started` ID is required. Failure to create exactly one clean
   session fails clearly before the result is accepted or reconciled.
3. Hermes-created Codex children each use their own fresh session.
4. A correction uses a fresh compact work order containing only the original
   bounded task, essential repository context, a compact prior-result summary
   and artifact paths, Hermes feedback, and acceptance criteria. It never
   replays orchestration history or the prior transcript.
5. The supervisors treat 75,000 cumulative JSONL tokens as the configured 50%
   handoff boundary. The final cumulative snapshot replaces earlier snapshots;
   events are never summed. At the boundary the current process ends, a compact
   receipt/handoff is written under `logs/codex_handoffs/`, and continuation
   starts through a new `exec --ephemeral` process from that artifact path.
   Same-session auto-compaction and transcript resume are not used. At most four
   successive handoffs are allowed before an explicit failure.
6. Large logs, screenshots, browser evidence, and verbose test output are
   stored as artifacts. Later prompts carry compact summaries and paths.

All Codex workbench prompts retain the scoped-local permission header and are
bounded to 64 KiB. Oversized context must be artifact-backed.

## Receipt and ledger
Every completed item carries `orchestrator`, `subagents`, `workbenches`,
provider-total `totals`, deterministic `est_cost_usd`, and an explicit
`unavailable` list. The existing done-transition contract remains wired on
all three paths and schema-validates before persisting `done`.

Per reported workbench session, deterministic soft warnings are recorded for:

```text
cache_ratio > 20
context_pct_at_close > 50
```

Warnings do not interrupt a running task. Missing closing-context metadata is
recorded as unavailable; it is never reconstructed.

## Cost
`scripts/model_prices.json` is the deterministic source. Fresh input is charged
at `input_per_mtok`, cached input at `cache_read_per_mtok`, and output at
`output_per_mtok`. When a reported fresh/cache split exists it must sum to the
provider-total `input`; pricing never adds cached input to provider input.
Legacy input without a cache split is charged once at the normal input rate.

## Rollups
`scripts/token_rollup.py` makes no model calls and recomputes cost from ledger
components. Weekly output includes lane/profile/workbench/model/budget views,
top expensive items, top five sessions by cache ratio, context-ceiling
breaches, and deterministic soft-warning text. Stored cost is never trusted as
an aggregate source.

## Enforcement
`tools/aos_codex_policy.py`, both guarded Codex constructors, executable
handoff writers/continuations, correction prompt builder, `tools/aos-queue.py`, `scripts/token_rollup.py`,
`hooks/token_budget_check.md`, and the three workbench identity files.

## Known gap
Receipt and ledger writes remain separate durable operations. A crash between
them can still create drift; this pre-existing tradeoff is unchanged.
