# queue/templates/memory_promotion.prompt.md
> Template only — does not write to the Business Brain. A promotion is a
> proposal until Liam accepts it (MEMORY_PROMOTION_POLICY.md).

## Purpose
Turn a completed item's discovery into an explicit, reviewable proposal to
update durable memory — never a direct write.

---

**Memory promotion proposal — {item_id}**

Lane: {lane} · Source item: {item_id}

### What's being proposed
{proposed_change}

### Target file
{target_memory_file} (e.g. `memory/positioning.md`, `memory/offers.md`,
`decisions/DECISIONS.md`, or a client entity page)

### Why this qualifies
Check against MEMORY_PROMOTION_POLICY.md — must be one of:
- [ ] Stable decision
- [ ] Approved positioning/offer change
- [ ] Recurring workflow improvement (skill graduated — see skill_trust.jsonl)
- [ ] Durable source-of-truth change (new client fact, new ICP evidence)
- [ ] Receipt worth keeping as precedent

### Explicitly NOT this
Confirm none of these apply — if any do, do not propose:
- Draft, raw transcript, or failed run
- Old-vault or legacy content
- Secret, credential, or connector account metadata
- Speculative or unsourced claim
- Another client's data

### Source
{source_pointer} — every claim in the proposal must trace back here.

### Gate
Routes through the orchestrator's normal ACCEPT/REVISE review
(`orchestrator_review.prompt.md`) before landing in memory. No agent writes
to the Business Brain directly.
