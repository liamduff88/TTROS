# AOS-2026-0173 — integrated lane workspace validation and browser receipt
> Revisit when the lane workspace, Cockpit lane cards, or protected implementations change. · Last touched: 2026-07-18.

**Verdict: PASS.** Final child of AOS-2026-0169 validated against AOS-2026-0173 and the accepted AOS-2026-0170–0172 receipts only. No integrated-workspace defect was found and no product implementation was corrected or redesigned.

## Automated evidence

- Focused frontend: `node --test tests/shellState.test.js tests/laneWorkspaceState.test.js tests/laneWorkspaceActions.test.js tests/laneWorkspaceComponent.test.js` — 18/18 passed.
- Affected frontend: `npm test` — 40/40 passed.
- Production frontend: `npm run build` — Vite 6.4.3, 1,652 modules transformed, build passed.
- Protected regressions: `python3 -m unittest tests.test_aos_queue tests.test_aos_paths dashboard.backend.test_composio_hermes` — 238 tests passed.
- Local browser: `.venv-pdf/bin/python scripts/aos_0173_browser_proof.py` against the existing Vite server at `127.0.0.1:3010`, with local Playwright API interception and no external systems — passed with no console or page errors. Machine-readable assertions: `workflows/queue_artifacts/AOS-2026-0173_browser_proof/browser-proof.json`.

## Browser and visual proof

- `desktop-cockpit-1440x1000.png`: five Cockpit lane cards; Operations is a whole-card semantic link to `/lane/operations`, has no nested button, and has no separate queue CTA.
- `desktop-lane-needs-me-1440x1000.png`: six filters in order (Needs Me, To Run, Blocked, All Active, Done, Cancelled), counts 2/2/1/5/1/1, and default Needs Me behavior showing only the two lane-scoped review/input items. The compact HumanReviewCard body, receipt field, close-status select, and Save/Attach remain intact; Approve, Needs changes, and Reject remain available in the lane action wrapper.
- `desktop-lane-ready-1440x1000.png`: two ready items, item and select-all controls, one selected item, enabled Run selected/Cancel selected, and per-item Run now/Cancel controls.
- `desktop-lane-blocked-1440x1000.png`: the blocking reason is visible and Unblock is present and enabled.
- `narrow-lane-needs-me-390x844.png`: visually inspected at 390×844 after collapsing the responsive sidebar and Needs Me rail. Document width is 390/390 client/scroll and main width is 290/290; the workspace remains inside main with no horizontal overflow.

All captures are durable under `workflows/queue_artifacts/AOS-2026-0173_browser_proof/`. The proof harness was adjusted only to use the repository's existing Playwright virtual environment and to position the Cockpit screenshot on the lane-card region; these were evidence-harness adjustments, not application corrections.

## Protected implementation invariants

Pre-validation and final fingerprints are identical. Existing unrelated worktree modifications were already present before this child, so the before/after fingerprints—not repository cleanliness—are the workflow boundary.

- `dashboard/frontend/src/components/HumanReviewCard.jsx`: `e47f1caf21fb3699dde9a63dd22a9fee2c626509053a685adb7f29ce009d92d1` (matches the accepted AOS-2026-0172 hash).
- Work Queue, `dashboard/frontend/src/views/Queue.jsx`: `c658976dd7437aa4279692ce20150bd4fec520901cb12ab521422b24bd22a76c`.
- Backend tracked-file aggregate: `9c354ae49fffe16fb74f2f059d3a1397b45ea01afca527f9be2ff82c3058412a`.
- Schema tracked-file aggregate: `c48ab211c5177699bea73ca9df539e86f390cdccb442e0b014eae785ca0c0789`.
- Runner, `tools/aos-orchestration-runner.py`: `f7f55c4873949c552b9874aeb9a96320fcf9d55eba7438d5e9cf60fd178c6584`.
- Queue/runner implementation aggregate (`aos-queue.py`, storage, orchestration runner/helpers): `b954a73368d51a853260c6b9082516604c6878eb57fb9896ae9a35ba22275f83`.

Therefore HumanReviewCard, Work Queue, backend, schema, and runner protected implementations were not changed by AOS-2026-0173. This child adds only the local validation harness, browser evidence, this receipt, and the authorized queue receipt/status record.

## Token usage

Token usage: unavailable from the current CLI harness; no estimate recorded.


<!-- token_usage:AOS-2026-0173 -->
## token_usage
```json
{
  "token_usage": {
    "orchestrator": {
      "input": 0,
      "output": 0
    },
    "subagents": [],
    "workbenches": [
      {
        "tool": "codex",
        "session_id": "019f76ff-8295-7f03-bbd5-7a3e7bd902e1",
        "input": 1976721,
        "output": 17825,
        "source": "reported"
      }
    ],
    "totals": {
      "input": 1976721,
      "output": 17825
    },
    "est_cost_usd": 0.0,
    "unavailable": [
      "Codex model identity",
      "cost for unavailable Codex model"
    ]
  },
  "profile_invocation": {
    "requested_profile": "default",
    "fallback_profile": "default",
    "invoked": false,
    "native_invocation": "not_applicable",
    "resolved_profile": "default",
    "evidence": "`hermes profile show default` rc=0; profile present",
    "reason": "Default Hermes route confirmed present; no profile switch needed."
  },
  "initial_prompt_bytes": "unavailable from current CLI output",
  "model_turns": "unavailable from current CLI output",
  "retained_context_bytes": "unavailable from current CLI output",
  "compaction_count": "unavailable from current CLI output",
  "fresh_input": "unavailable from current CLI output",
  "cached_input": "unavailable from current CLI output",
  "output": "unavailable from current CLI output",
  "reasoning": "unavailable from current CLI output",
  "largest_tool_result_bytes": "unavailable from current CLI output"
}
```
