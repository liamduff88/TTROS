# ESCALATION — exactly two triggers, no third
> Revisit: on a routing change or an escalation-trigger dispute. · Last touched: 2026-07-07.

## The two triggers
1. **External-facing / high-stakes at creation.** The output reaches a
   prospect, client, or public surface, or commits price or scope. Strong
   model from attempt 1 — not earned through a failed cheap attempt first.
2. **Orchestrator review returns REVISE.** One escalated retry, at the
   stronger model tier for that lane.

Nothing else escalates. Any agent proposing a third trigger stops and asks
Liam rather than inventing one in the moment (always.md #10). Naming a
task "important" or "urgent" is not a trigger — only the two above are.

## Retry discipline
- REVISE = one escalated retry, same item, stronger model.
- A second REVISE on the same item goes to Liam as a blocked item, not a
  third attempt. Repeated failure means the skill or the completion
  contract needs fixing, not more spend.

## Who decides
Only the orchestrator (Operating Hermes) sets the external-facing flag at
`/queue-item` creation and only the orchestrator issues ACCEPT/REVISE.
Department subagents cannot self-escalate; they report back and the
orchestrator decides.

## Cost visibility
Escalated items carry their token delta plainly in the receipt (rules/
token_budget.md) — escalation is not free, and the ledger tracks its share
of total spend so the two-trigger discipline stays honest.

## Enforcement
Hooks: token_budget_check.md flags escalated spend; receipt-completeness
check refuses a done-transition without ACCEPT/REVISE recorded. Mirrored in
LOOP_POLICY.md, OPERATOR_CONTRACT.md, soul.md §routing.
