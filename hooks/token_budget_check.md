# hooks/token_budget_check.md
> Revisit: when ledger schema, Codex JSONL semantics, or warning thresholds change. · Last touched: 2026-07-19.

## Event
Fires on all three queue-item transitions to `done` in `tools/aos-queue.py` and
during supervised Codex process-exit reconciliation.

## Hard checks
The existing `finalize_done()` contract builds a complete `token_usage` block,
computes cost from `scripts/model_prices.json`, validates run/token ledger rows,
and refuses before persisting status if the block or schema is invalid. Missing
harness fields remain explicitly unavailable; guessed counts never unblock a
transition.

Supervised Codex reconciliation additionally requires exactly one real
`thread.started` identity. Missing or ambiguous clean-session creation fails
without using a previous or synthetic session ID.

For Codex JSONL, `input_tokens` is provider-total input. When
`cached_input_tokens` is present, the parser derives fresh input by subtraction,
rejects cached input greater than provider input, and never adds cached input to
the provider total. Reasoning must be a subset of output.

The final cumulative `turn.completed` snapshot is authoritative; repeated
events are not summed and an incomplete terminal event does not inherit fields
from an earlier event. At 75,000 cumulative tokens the supervisor writes a
compact handoff receipt, ends the current process, and launches a new
`exec --ephemeral` continuation from the artifact path. No same-session
auto-compaction or transcript replay is available.

## Soft deterministic warnings
For each reported workbench entry:

1. `cached_input / max(fresh_input, 1) > 20` records the tool, session ID, and
   ratio.
2. `context_pct_at_close > 50` records the tool, session ID, and closing value.

Warnings are written into the token sidecar/receipt payload and ledger row and
reproduced deterministically in the weekly rollup, but do not block completion.
Missing inputs are named under `unavailable`; the hook does not estimate them.

## Pricing check
Fresh input is priced at `input_per_mtok`, cached input at
`cache_read_per_mtok`, and output at `output_per_mtok`. A reported split must
sum to provider-total input. Legacy `input` without a split is priced once at
the normal input rate.

## Enforces
`rules/always.md` #1 and #5, `rules/token_budget.md`, and
`context/TOKEN_POLICY.md`.

## Status
Wired in `tools/aos-queue.py`; rollup warnings and rankings are wired in
`scripts/token_rollup.py`.
