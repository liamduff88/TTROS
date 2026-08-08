---
name: morning_brief
description: Deterministic morning attention query plus optional Hermes interpretation. Detection reads live authority and spends zero model tokens.
when-to-use: Scheduled daily 8am, or on Liam's command any morning. Owner: orchestrator. Trust: earned.
---
# /morning-brief
> Revisit: if queue, prospect, Graphify, or canonical entity contracts change. · Last touched: 2026-08-04

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
1. Run `python3 tools/aos_executive_brief.py --format markdown`. This is the
   sole generator used by CLI and Hermes context assembly.
2. Detect active queue commitments, decisions/review waiting on Liam, blocked
   work, prospect integrity gaps and due follow-ups, open contradictions,
   unresolved canonical loops, and explicitly blocked typed projects.
3. For Graphify-discovered entities, validate client scope before returning a
   canonical target; fall back to exact canonical `queue_ids` relationships.
4. Emit stable, deduplicated findings with rule, entity/path, exact state,
   evidence, calculated age, owner/wait, next permitted action, external-action
   boundary, observation time, and zero-token accounting.
5. Pass the fresh deterministic JSON through Context Assembler. Hermes may
   propose priorities, but may not add/remove detector matches or act externally.

## Never
- Write to the Brain, calendar, queue, or any external system.
- Launch other skills (suggest them by name instead).
- Read the prior generated brief as evidence or require manual removal.
- Open raw Gmail bodies or Graphify note bodies.

## Done when
Fresh findings are published atomically (or the complete prior artifact remains
unchanged on failure), detector token use is exactly zero, and the assembled
Hermes context includes the same findings. Resolution clears the next query by
authoritative status/outcome transition while history remains intact.
