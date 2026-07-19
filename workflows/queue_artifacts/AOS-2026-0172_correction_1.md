# AOS-2026-0172 — Hermes correction 1
> Revisit: after Codex repair. · Last touched: 2026-07-18.

REVISE

- Remaining defect: `LaneWorkspace.jsx` passes `[&_[data-review-card-body]]:hidden` to `HumanReviewCard`, hiding its established compact body. This changes the rendered card even though the component source hash is unchanged.
- Required repair: remove the hiding/visual override and render the existing `HumanReviewCard` intact. Keep the new lane actions outside it; retain all valid endpoint, selection, receipt, test, and build evidence.
- Correction count: 1.
- Token usage: no agent invocation.
