---
name: memory_promotion
description: Promote Liam-reviewed results into the Business Brain per MEMORY_PROMOTION_POLICY.md — pointers not copies, sources required, nothing speculative.
when-to-use: A receipt, decision, or case-note lesson is flagged worth keeping; or /maintain-os / /weekly-review surfaces promotion candidates. Owner: aos-ops. Trust: watch.
---
# /memory-promotion
> Revisit: when MEMORY_PROMOTION_POLICY.md or the Brain's memory areas change. · Last touched: 2026-07-15

## Purpose
Move durable, verified knowledge into the Business Brain without contaminating it. The Brain stays stable because this gate is strict.

## Inputs
- The candidate: receipt, decision, approved positioning/offer change, or case-note lesson.
- MEMORY_PROMOTION_POLICY.md (binding — the what-gets-promoted / never-promoted lists).

## Steps
1. **Classify** — target destination: an exact canonical `business_brain:<relative-path>` such as `business_brain:decisions/DECISIONS.md`, `business_brain:memory/positioning.md`, or `business_brain:memory/offers.md`. No explicit unambiguous destination → not ready; return to sender with why.
2. **Scope** — validate `client_scope`, target pointer, and provenance identities through the canonical client-scope registry before reading a target.
3. **Tier** — evaluate through the executable policy. Only the named generated-marker rule is automatic; substantive classes route `human_review`; forbidden classes are refused; unknown classes route review.
4. **Verify** — every claim sourced. Review-tier candidates require an accepted review reference; automatic candidates require the exact allowlisted rule.
5. **Write** — invoke the promotion writer. Never edit a Brain file directly. It enforces the target hash, marker boundary, atomic replace, validation, provenance, refresh state, and exact rollback.
6. **Receipt** — keep only durable references in `memory_promotion`; outcome state remains in the promotion receipt.

## Never
- Promote anything on the policy's never-promoted list.
- Copy wholesale when a pointer suffices.
- Promote review-tier material without Liam review of the underlying result.
- Treat an unclassifiable candidate as automatic.

## Done when
Candidate is either promoted (target updated, stamped, sourced) or explicitly returned with a one-line reason. Receipt written.
