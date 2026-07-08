# TOKEN_POLICY.md — visible spend on every unit of work
> Revisit: on a Hermes release (usage-metadata fields can reshape) or monthly pricing check. · Last touched: 2026-07-07.

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
The receipt-completeness hook refuses the done-transition without this block.

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
`est_cost_usd` is computed by a deterministic script from `queue/model_prices.json`
— a rotting file with its own Revisit line, checked monthly for provider
pricing changes.

## Rollups
`scripts/token_rollup.py` (no model calls): daily/weekly totals by lane,
profile, workbench, budget class; top-10 most expensive items; escalation
cost share. `/weekly-review` embeds the weekly rollup.

## Enforcement
Hooks: token_budget_check.md, receipt-completeness-check. Mirrored in
rules/always.md #1, rules/token_budget.md, rules/never.md #7.
