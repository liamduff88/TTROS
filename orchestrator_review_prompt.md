# queue/templates/orchestrator_review.prompt.md
> Template only — does not launch agents or change queue state.

## Purpose
Operating Hermes's final review of a department subagent's completed work,
before a done-transition. This is the review step in LOOP_POLICY.md — the
only step that can trigger escalation trigger (b).

---

**Orchestrator review — {item_id}**

Lane: {lane} · Profile: {profile} · Verifier result: {verifier_result}

### Inputs
- Original work order: `queue/templates/work_order.prompt.md` (filled, {item_id})
- Receipt: `queue/receipts/{item_id}.md`
- Verifier output: {verifier_result_detail}

### Judgment (only the orchestrator holds this)
1. Does the receipt's `token_usage` block satisfy TOKEN_POLICY.md §8.1?
2. Does the `memory_promotion` field exist (empty array acceptable, absence
   is not)?
3. Cross-lane leakage check: did this item stay inside its declared lane?
4. If the verifier returned NEEDS ATTENTION, is the gap fixable within scope
   or does it need a new, separately-scoped item?

### Decision — exactly one
- **ACCEPT** — done-transition proceeds. Append lines to `run_ledger.jsonl`,
  `token_ledger.jsonl`, and (if a skill ran) `skill_trust.jsonl`.
- **REVISE** — one escalated retry, stronger model tier for this lane
  (LOOP_POLICY.md escalation trigger b). A second REVISE on the same item
  becomes a blocked item for Liam — not a third attempt.

### Never
- Accept on the strength of a self-report alone — the verifier result gates
  this decision.
- Invent a REVISE reason outside the two named escalation triggers.
