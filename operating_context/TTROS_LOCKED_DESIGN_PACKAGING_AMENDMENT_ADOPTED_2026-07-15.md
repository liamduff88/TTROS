# TTROS_LOCKED_DESIGN_PACKAGING_AMENDMENT_2026-07-15
> Layer: operating_context · Owner: Liam · Status: adopted by Liam on 2026-07-15 alongside the final reconciliation runbook
> Amends: TTROS_BRAIN_RECONCILIATION_LOCKED_DESIGN_2026-07-15.md §10 (implementation packaging only) · Last touched: 2026-07-15

## DATED IMPLEMENTATION-PACKAGING AMENDMENT — 2026-07-15

Locked Design §§1–9 and §§11–13 remain unchanged in full: system authorities, retrieval hierarchy, promotion tiers, Graphify's derived role, capture semantics, client-isolation requirement, graceful degradation, deferred items, and Stage A completion criteria.

§10's execution packaging ("one bounded implementation session should own…") is replaced. For implementation, Stage A BR-0–6A is packaged into three bounded stages:

1. **Knowledge plane repair and Graphify Markdown proof** (BR-0, 1, 2).
2. **Scoped retrieval, client isolation, and promotion/write/later-retrieval** (BR-3, 4, 5, with client-scope authority and enforcement preceding the first write).
3. **Capture built dark with integrated Stage A proof** (BR-6A).

Each stage owns its complete inspect → repair → test → diagnose → rerun → prove outcome. There are two inter-stage checkpoints and no per-phase queue items or operator-relay steps.

The Stage 3 closeout is the Stage A evidence package, presented at the single Phase 6B activation gate. Recurring live polling and future auto-continue whitelist entries remain separately approval-gated exactly as §§9–10 Stage B describe.

Rationale: the checkpoints sit at genuine risk-class changes (structure → first machine write → new client-data subsystem) for a first run of unproven machinery, without reintroducing per-phase operator mediation. Once the loop is proven, future work of this class may revert to single-session packaging without further amendment.
