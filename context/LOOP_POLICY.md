# LOOP_POLICY.md — how work moves through the OS
> Revisit: on a Hermes release, a routing change, or an escalation-trigger dispute. · Last touched: 2026-07-07.

## The loop
```
intent → classify lane → resolve profile → queue item (contract + flags + budget class)
       → fan out to department subagent → subagent runs skill/task
       → orchestrator review → ACCEPT or REVISE
       → done: receipt + artifact, or REVISE: one escalated retry
```
One Hermes install, one orchestrator (Operating Hermes). Department subagents
are profiles inside it, never separate installs. Departments never cross
lanes — a cross-lane need returns to the orchestrator, it doesn't get solved
sideways.

## Classification
Lane = revenue | marketing | delivery | ops. Unknown lane → orchestrator takes
it itself and notes the gap in the receipt, rather than guessing a profile.

## Escalation — exactly two triggers, no third
1. The output is external-facing (reaches a prospect, client, or public
   surface, or commits price/scope).
2. Orchestrator review returns REVISE.
Nothing else escalates. An agent that wants to escalate for a third reason
stops and asks, rather than inventing a trigger in the moment.

## Retry discipline
REVISE = one escalated retry, using the stronger model tier for that lane.
A second REVISE on the same item goes to Liam as a blocked item, not a third
attempt — repeated failure is a signal to fix the skill or the contract, not
to keep spending tokens on it.

## Completion contract
Every queue item is created with a definition of done, allowed actions, and
stop conditions before work starts (`/queue-item` refuses items missing a
contract). Work is checked against that contract before being reported done —
never against a vibe of "looks finished."

## Non-collision
Two subagents never work the same item concurrently. One client, one thread.
Cross-client or cross-lane contamination is a stop condition, not a merge point.

## Scheduled loops
- `/morning-brief` — daily, read-only by construction (calendar, queue,
  overnight receipts, top 3 priorities). The safe first automation.
- `/maintain-os` — weekly scan (drift, unused skills, stale Revisit dates),
  monthly interview (walks due dates, asks refresh questions). Reports and
  recommends only; never deletes without Liam's okay (never.md #12).

## Enforcement
Hooks: receipt-completeness-check (refuses done-transition without contract +
token_usage block). Mirrored in rules/escalation.md, rules/completion_contract.md.
