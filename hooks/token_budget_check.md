# hooks/token_budget_check.md
> Revisit: when the ledger schema or budget thresholds change. · Last touched: 2026-07-08 (status/receipt paths now hard-refuse like `done`; schema validation is a hard block).

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
(best-effort only in the sense that validation is skipped if `jsonschema`
isn't installed; when it is, a schema failure is a hard block, same as an
incomplete `token_usage` block). `est_cost_usd` is always computed
deterministically from `scripts/model_prices.json` — no caller-supplied cost
override is accepted on any path.

Budget class is derived from the item's `budget:<class>` tag (or overridden on
the `done` command) and recorded as a reporting label — a soft signal, never a
hard mid-task stop, per `rules/token_budget.md`.

## On block
All three done-transition paths — `status ITEM_ID done`, `receipt ITEM_ID PATH
--status done`, and the explicit `done` command — refuse identically: `tools/
aos-queue.py` runs `finalize_done()` (build token_usage, validate both ledger
lines against schema) *before* persisting the status change or the receipt.
On refusal, `finalize_done()` raises, nothing is written (no ledger line, no
`<id>.token_usage.json` sidecar), and the item's prior status stands — never a
"done" item with a missing or invalid ledger entry. The error is surfaced as
`NEEDS ATTENTION: ...` on stderr and the command exits non-zero. Never fills a
missing token count with a guess to let the transition pass.

## Enforces
`rules/always.md` #1, #5 · `rules/token_budget.md` · `context/TOKEN_POLICY.md`.

## Status
Wired. `finalize_done()` in `tools/aos-queue.py` runs this check before every
done-transition (status, receipt, and explicit `done` commands alike), appends
one line to both `queue/run_ledger.jsonl` and `queue/token_ledger.jsonl` only
on success, and writes the `token_usage` block into the receipt (markdown
fenced block plus a `<id>.token_usage.json` sidecar).
