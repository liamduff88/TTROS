# MEMORY_PROMOTION_POLICY.md — what earns a place in the Business Brain
> Revisit: when a new memory area is added or a promotion causes contamination. · Last touched: 2026-07-07.

## The flow
```
TTROS Business Brain (durable, stable)
        ↓ pointers, not copies
Operating Hermes reads only the files the lane/task needs
        ↓
Queue item references the specific source, not the whole vault
        ↓
Agent/workbench executes scoped work
        ↓
Receipt captures what changed
        ↓
Liam-reviewed results get promoted back
```
Memory is read by reference, never dumped wholesale into a task.

## What lanes read (scoped, not the whole Brain)
- **Revenue** — company, positioning, ideal_clients, offers, sales_and_revenue,
  marketing_voice.
- **Marketing** — company, positioning, offers, website/content, marketing_voice.
- **Delivery** — delivery_model, active_projects, protected_paths, relevant
  scope notes.
- **Ops** — current_priorities, active_projects, decisions, protected_paths.

## What gets promoted
- Stable decisions (→ decisions/DECISIONS.md).
- Approved positioning or offer changes (→ memory/positioning.md, offers.md).
- Recurring workflow improvements once a skill graduates (see
  SKILL_GRADUATION_POLICY.md) — the durable version, not every draft.
- Durable source-of-truth changes (new client facts, new ICP evidence).
- Receipts worth keeping as precedent, after Liam review.

## What never gets promoted
- Drafts, raw transcripts, failed runs.
- Old vault content, ZPC material, any legacy_harvest artifact.
- Secrets, connector account metadata, credentials, OAuth state.
- Speculative claims, unverified numbers, anything without a source.
- Anything from one client's context into another's (client isolation is
  absolute — never.md #9).

## The missing-contract gap this file closes
Queue workers know their memory pointers but historically had no explicit
convention for what to read and what to propose back. This file is that
contract: read only the scoped files above; propose promotions explicitly in
the receipt (`memory_promotion` field) rather than writing to the Brain
directly. A promotion is a proposal until Liam accepts it — mirrors the
`memory_promotion` prompt template in `queue/templates/`.

## Gate
No agent writes to the Business Brain directly. Promotions go through the
orchestrator's review step (ACCEPT/REVISE, same mechanism as any other queue
item) before landing in memory. This keeps the Brain durable and prevents a
bad run from corrupting the substrate other lanes depend on.

## Enforcement
Mirrored in rules/always.md #6–#8, never.md #9. Hook: none dedicated yet —
covered by receipt-completeness-check requiring the memory_promotion field
be explicit (even if empty) rather than silently omitted.
