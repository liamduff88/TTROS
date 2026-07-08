# TOKEN_POLICY.md — visible spend on every unit of work
> Revisit: on a Hermes release (usage-metadata fields can reshape) or monthly pricing check. · Last touched: 2026-07-08 (done-transition hardened: all three paths hard-refuse, schema validation enforced, est_cost_usd override removed).

## Purpose
Clear token usage on every task, subagent, the orchestrator, and every
workbench (Claude Code, Codex, Antigravity). Visibility and drift detection —
not throttling judgment, and not a dashboard build this phase (back end only).

## The rule that overrides everything else here
Numbers come from the harness/API usage fields only. A component that can't
report goes into `unavailable` by name. **"Unavailable" is recorded, never
estimated, never invented** — never.md #7. This holds even under pressure to
give a complete-looking number.

## Receipt schema (extended)
Every queue-item receipt carries a `token_usage` block:
```json
{
  "orchestrator": {"input": 0, "output": 0},
  "subagents": [{"role": "...", "model": "...", "input": 0, "output": 0}],
  "workbenches": [{"tool": "...", "input": 0, "output": 0, "source": "reported|unavailable"}],
  "totals": {"input": 0, "output": 0},
  "est_cost_usd": 0.00,
  "unavailable": []
}
```
The receipt-completeness hook refuses the done-transition without this block —
on every path that can reach `done` (`status`, `receipt --status done`, and the
explicit `done` command alike), the block is built and both ledger lines are
schema-validated *before* the item's status is persisted, so a refusal leaves
the item's prior status untouched rather than landing a "done" item with a
missing or invalid ledger entry.

## Budget classes
`light` (briefs, drafts, reviews) · `standard` (most work) · `heavy` (lead-gen
runs, client builds, anything escalated). Labels for reporting and a soft
threshold warning in the receipt — never a hard stop mid-task. Assigned by
`/queue-item` at creation.

## The ledger
`queue/token_ledger.jsonl` — append-only, one line per completed receipt's
token_usage block plus item id, lane, profile, timestamp, escalation flag.
Written at done-transition. Single source the future dashboard reads; nothing
else aggregates spend state. Git-versioned with the nightly backup.

## Workbench reporting
Claude Code / Codex / Antigravity report input/output totals at session end
if the harness exposes them; the launching agent appends the entry. Where a
harness writes usage to local logs, a deterministic parser script is
preferred over self-report. Where nothing is exposed: `"source": "unavailable"`.

## Cost
`est_cost_usd` is always computed deterministically from
`scripts/model_prices.json` — a rotting file with its own Revisit line,
checked monthly for provider pricing changes. Rates there are placeholders
until Liam fills real provider pricing. No caller-supplied cost is ever
accepted as an override, on any path; the orchestrator component (which
carries no per-component model of its own) is priced at the run's confirmed
model, the same attribution `scripts/token_rollup.py` uses for its by-model
breakdown, so the ledger's stored cost and the rollup's recomputed cost always
agree.

## Rollups
`scripts/token_rollup.py` (no model calls): daily/weekly totals by lane,
profile, workbench, budget class; top-10 most expensive items; escalation
cost share. `/weekly-review` embeds the weekly rollup. Every cost figure is
recomputed from each line's own components on every run — never read from a
line's stored `est_cost_usd` — so totals always reconcile with the by-model
breakdown, including against older ledger data.

## Enforcement
Hooks: token_budget_check.md, receipt-completeness-check. Mirrored in
rules/always.md #1, rules/token_budget.md, rules/never.md #7.

## Known gaps
- Done-transition writes the token_usage block and the ledger append as
  two separate steps, not one atomic operation (accepted tradeoff,
  audit #2 finding #3, 2026-07-05). A crash between the two could leave
  a receipt without a matching ledger line. Not fixed this phase —
  revisit if ledger/receipt drift is ever observed in practice.
