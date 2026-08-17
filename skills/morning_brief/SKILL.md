---
name: morning_brief
description: Deterministic morning attention query plus David interpretation and authorized operator delivery. Detection reads live authority and spends zero model tokens.
when-to-use: Daily at 08:00 America/Vancouver or on Liam's command. Owner: orchestrator. Trust: earned.
---
# /morning-brief
> Revisit: if queue, prospect, Graphify, canonical entity, or scheduled delivery contracts change. · Last touched: 2026-08-17

## Purpose
Start the day from a fresh query of authoritative state. The detector decides
what matches without a model; Hermes may interpret and prioritise only after
the exact findings enter the mandatory assembled-context path.

## Inputs
- Queue state from `queue/work_items.jsonl`.
- Activity/outcomes from linked receipts and `queue/prospects.jsonl`.
- Canonical typed entity notes, decision notes, `open_loops.md`, and
  `inbox/contradictions.md`.
- Graphify one-hop target discovery, with the existing scoped pointer/search
  fallback when Graphify is stale or unavailable.

## Steps
1. Run `python3 tools/aos_executive_brief.py --format markdown` for factual
   detection only. This is the sole detector generator used by CLI and Context
   Assembler.
2. Detect active queue commitments, decisions/review waiting on Liam, blocked
   work, prospect integrity gaps and due follow-ups, open contradictions,
   unresolved canonical loops, and explicitly blocked typed projects.
3. For Graphify-discovered entities, validate client scope before returning a
   canonical target; fall back to exact canonical `queue_ids` relationships.
4. Emit stable, deduplicated findings with rule, entity/path, exact state,
   evidence, calculated age, owner/wait, next permitted action, external-action
   boundary, observation time, and zero-token accounting.
5. Pass the fresh deterministic JSON through mandatory Context Assembler.
   David may interpret and prioritise, but may not add/remove detector matches
   or act externally.
6. The complete scheduled path is `python3 -m tools.aos_morning_brief --deliver`; it invokes
   the real Ask David API and atomically publishes the concise interpretation
   to `context/DAVID_MORNING_BRIEF.md`, then sends that exact artifact through
   the governed Composio AgentMail and Telegram operator paths. Daily delivery is
   idempotent by America/Vancouver service date.

## Never
- Write to the Brain, calendar, queue, or any external system except the two
  expressly authorized operator deliveries named above.
- Launch other skills (suggest them by name instead).
- Read the prior generated brief as evidence or require manual removal.
- Open raw email bodies or Graphify note bodies.

## Done when
Fresh findings are published atomically (or the complete prior artifact remains
unchanged on failure), detector token use is exactly zero, and the assembled
David context includes the same findings. A complete scheduled run also proves
zero queue delta, authoritative provider usage, one concise local artifact,
matching delivery hashes, and provider acknowledgements for both authorized
channels. Resolution clears the next query by authoritative status/outcome
transition while history remains intact.
