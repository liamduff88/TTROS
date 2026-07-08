# hooks/token_budget_check.md
> Revisit: when the ledger schema or budget thresholds change. · Last touched: 2026-07-07.

## Event
Fires when a queue item transitions to `done` in `tools/aos-queue.py`
(`status ... done`, `receipt ... --status done`, or the explicit `done`
subcommand). Implemented by `finalize_done()`.

## Check
The coordinator assembles the `token_usage` block for the receipt from
harness/API usage fields only — a Hermes one-shot `--usage-file`, a
pre-assembled `--token-usage` block, or, when neither is supplied, a block in
which every component is listed by name under `unavailable`. Because an
explicit-`unavailable` block is always constructible, the transition is refused
only when the block cannot be built with its required keys
(`orchestrator`, `subagents`, `workbenches`, `totals`, `est_cost_usd`,
`unavailable`) — never to force a guessed token count. The assembled
run-ledger and token-ledger lines are validated against
`queue/run_ledger_schema.json` and `queue/token_ledger_schema.json`
(best-effort: `jsonschema` when installed); `est_cost_usd` is computed
deterministically from `scripts/model_prices.json`.

Budget class is derived from the item's `budget:<class>` tag (or overridden on
the `done` command) and recorded as a reporting label — a soft signal, never a
hard mid-task stop, per `rules/token_budget.md`.

## On block
The explicit `done` command raises and blocks when the `token_usage` block is
incomplete. The `status`/`receipt` paths keep queue liveness: a metering
failure or a schema warning is surfaced as `NEEDS ATTENTION (metering): ...` on
stderr, and the already-saved status change stands. Never fills a missing token
count with a guess.

## Enforces
`rules/always.md` #1, #5 · `rules/token_budget.md` · `context/TOKEN_POLICY.md`.

## Status
Wired. `finalize_done()` in `tools/aos-queue.py` runs this check on every
done-transition, appends one line to both `queue/run_ledger.jsonl` and
`queue/token_ledger.jsonl`, and writes the `token_usage` block into the
receipt (markdown fenced block plus a `<id>.token_usage.json` sidecar).
