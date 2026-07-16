# queue/templates/memory_promotion.prompt.md
> Template only — does not write to the Business Brain. A promotion is a
> proposal until Liam accepts it (MEMORY_PROMOTION_POLICY.md).
> Revisit: when promotion authority or logical pointer conventions change. · Last touched: 2026-07-15.

## Purpose
Turn a completed item's discovery into an explicit, reviewable proposal to
update durable memory — never a direct write.

---

**Memory promotion proposal — {item_id}**

Lane: {lane} · Source item: {item_id}

### What's being proposed
{proposed_change}

### Target file
{target_memory_file} (e.g. `business_brain:memory/positioning.md`,
`business_brain:memory/offers.md`, `business_brain:decisions/DECISIONS.md`,
or an exact canonical client pointer supplied by the reviewed work item)

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

### Required executable fields
- Client scope: {client_scope}
- Target preimage SHA-256: {target_preimage_sha256}
- Candidate diff: {candidate_diff}
- Provenance references: {provenance_references}
- Authority tier and reason: {authority_tier_reason}

### Gate
Routes through the orchestrator's normal ACCEPT/REVISE review
(`orchestrator_review.prompt.md`) before the promotion writer may run.
Deterministic automatic work does not use a queue item; all Brain mutations go
through the promotion writer.
