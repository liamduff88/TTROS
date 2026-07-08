# COMPLETION CONTRACT
> Revisit: on a /queue-item or /goal format change. · Last touched: 2026-07-07.

## The rule
Every queue item is created with a completion contract — definition of
done, allowed actions, and stop conditions — before work starts.
`/queue-item` refuses to create an item missing one (always.md #8).

## What a contract must state
1. **Definition of done** — the concrete artifact or state that counts as
   finished, not a vibe of "looks finished."
2. **Allowed actions** — what the assigned subagent may do unprompted
   (read, draft, prepare) versus what needs the `approved_external_action`
   flag named explicitly on the item (never.md #1, EXTERNAL_ACTIONS.md).
3. **Stop conditions** — the conditions under which the subagent halts and
   returns to the orchestrator instead of proceeding: missing client entity
   page, cross-lane need, ambiguous scope, or a would-be client-data blend
   (rules/client_data_boundaries.md).

## Verification before "done"
Work is checked against its own contract before being reported done —
never against a general impression of quality. A department subagent that
can't show the definition-of-done artifact hasn't finished, regardless of
effort spent.

## Playbooks
The five pre-seeded delivery playbooks (Blueprint V2 §6.2) use their
Stage 6 CLOSE as the completion contract's definition of done: updated
entity page, receipt with full token breakdown, access closeout checklist
reviewed by aos-ops.

## Enforcement
Hook: receipt_completeness_check.md — refuses a done-transition without a
contract reference and a verification note. Mirrored in always.md #8,
LOOP_POLICY.md "Completion contract" section.
