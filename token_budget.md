# TOKEN BUDGET
> Revisit: on a Hermes release or monthly pricing check. · Last touched: 2026-07-07.

## Purpose
Visibility and drift detection on every unit of work — not a hard throttle
on judgment. Full mechanics live in context/TOKEN_POLICY.md; this file is
the rule form department agents check against.

## Budget classes
- `light` — briefs, drafts, reviews.
- `standard` — most work.
- `heavy` — lead-gen runs, client builds, anything escalated.

Assigned once, at `/queue-item` creation, by the orchestrator. A budget
class is a reporting label and a soft threshold warning in the receipt —
never a hard stop mid-task.

## The rule that overrides everything else here
Numbers come from the harness/API usage fields only. A component that
can't report goes into `token_usage.unavailable` by name.
**"Unavailable" is recorded, never estimated, never invented** — even
under pressure to show a complete-looking number (never.md #7).

## What every completed item must carry
A `token_usage` block with orchestrator, subagent, and workbench
input/output totals, `est_cost_usd`, and an explicit `unavailable` list
where a component didn't report. No done-transition without it
(always.md #1, hooks/receipt_completeness_check.md).

## Escalation and cost
Escalated retries (rules/escalation.md) run at a stronger, more expensive
tier by design. Their cost shows plainly in the receipt and the weekly
rollup — escalation discipline stays honest because its price is visible,
not because spend is capped.

## Enforcement
Hooks: token_budget_check.md (soft threshold warning), receipt_completeness_check.md
(refuses done-transition without the block). Mirrored in always.md #1,
never.md #7, TOKEN_POLICY.md.
