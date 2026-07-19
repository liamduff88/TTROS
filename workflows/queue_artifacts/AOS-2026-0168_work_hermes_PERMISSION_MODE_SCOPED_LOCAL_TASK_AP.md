# AOS-2026-0168 — Lane workspace consolidated receipt

Revisit: if lane queue states, per-item action endpoints, or cockpit routing change.

PASS

## Work item

- AOS-2026-0168
- Workflow parent: AOS-2026-0169
- Dependency-linked Codex children: AOS-2026-0170 through AOS-2026-0173

## Summary for operator

- Cockpit Lane Activity cards now open a lane-scoped workspace with the requested filters, ordering, review/run/cancel/unblock actions, sequential selection actions, and responsive proof. Approval closes the local queue work only; nothing was published, pushed, or sent externally.

## Files touched

- `dashboard/frontend/src/App.jsx`
- `dashboard/frontend/src/api.js`
- `dashboard/frontend/src/components/DashboardKit.jsx`
- `dashboard/frontend/src/shellState.js`
- `dashboard/frontend/src/views/DashboardV1.jsx`
- `dashboard/frontend/src/views/LaneWorkspace.jsx` (new)
- `dashboard/frontend/src/laneWorkspaceActions.js` (new)
- `dashboard/frontend/src/laneWorkspaceState.js` (new)
- `dashboard/frontend/tests/shellState.test.js`
- `dashboard/frontend/tests/laneWorkspaceActions.test.js` (new)
- `dashboard/frontend/tests/laneWorkspaceComponent.test.js` (new)
- `dashboard/frontend/tests/laneWorkspaceState.test.js` (new)
- `scripts/aos_0173_browser_proof.py` (new local proof harness)
- Child receipts and browser-proof artifacts listed below

## Validation

- Focused frontend tests: 18/18 passed.
- Full frontend test suite: 40/40 passed.
- Frontend production build: passed with Vite 6.4.3 (1,652 modules transformed).
- Queue/path/backend regression suite: 238/238 passed.
- Desktop and narrow Playwright proof: passed with no console or page errors; narrow viewport measured 390px client/scroll width with no horizontal overflow.

Commands:

- `node --test tests/shellState.test.js tests/laneWorkspaceState.test.js tests/laneWorkspaceActions.test.js tests/laneWorkspaceComponent.test.js`
- `npm test`
- `npm run build`
- `python3 -m unittest tests.test_aos_queue tests.test_aos_paths dashboard.backend.test_composio_hermes`
- `.venv-pdf/bin/python scripts/aos_0173_browser_proof.py`

## Behavior

- Entire Lane Activity cards link to `/lane/{name}`; card content is retained and the separate queue CTA is removed.
- Workspace filters are Needs Me, To Run, Blocked, All Active, Done, and Cancelled. The default is Needs Me when non-empty, otherwise All Active.
- Items sort by Needs Me, ready, blocked, then other/newest within each group.
- Existing compact `HumanReviewCard` is reused unchanged. Review actions are Approve, Needs changes, and Reject.
- Inbox/agent-todo actions are Run now and Cancel. Blocked items show their reason and can return to agent-todo.
- Current-filter ready items support checkbox selection, sequential Run selected, and Cancel selected through the existing per-item endpoint so every cancellation retains its normal receipt.

## Corrections and review

- AOS-2026-0170: accepted on first review.
- AOS-2026-0171: accepted on first review.
- AOS-2026-0172: accepted after correction 1/2. The repair removed wrapper CSS that hid the reused HumanReviewCard body; browser proof confirms the full compact card remains visible.
- AOS-2026-0173: accepted on first review.
- Total corrections: 1.

## Protected areas

- Work Queue view, queue schema, backend, runner, and queue/runner machinery were not changed by this workflow.
- `HumanReviewCard` remained byte-identical: `e47f1caf21fb3699dde9a63dd22a9fee2c626509053a685adb7f29ce009d92d1`.
- Final protected fingerprints matched the pre-validation fingerprints recorded in the validation receipt.
- Existing unrelated dirty worktree changes were preserved.

## Artifacts

- `workflows/queue_artifacts/AOS-2026-0170_lane_route_receipt.md`
- `workflows/queue_artifacts/AOS-2026-0171_lane_workspace_receipt.md`
- `workflows/queue_artifacts/AOS-2026-0172_lane_actions_receipt.md`
- `workflows/queue_artifacts/AOS-2026-0172_correction_1.md`
- `workflows/queue_artifacts/AOS-2026-0173_validation_browser_receipt.md`
- `workflows/queue_artifacts/AOS-2026-0173_browser_proof/browser-proof.json`
- `workflows/queue_artifacts/AOS-2026-0173_browser_proof/desktop-cockpit-1440x1000.png`
- `workflows/queue_artifacts/AOS-2026-0173_browser_proof/desktop-lane-needs-me-1440x1000.png`
- `workflows/queue_artifacts/AOS-2026-0173_browser_proof/desktop-lane-ready-1440x1000.png`
- `workflows/queue_artifacts/AOS-2026-0173_browser_proof/desktop-lane-blocked-1440x1000.png`
- `workflows/queue_artifacts/AOS-2026-0173_browser_proof/narrow-lane-needs-me-390x844.png`

## Blockers

- None.

## Next action

- None required. Close the workflow parent and original item as done through the existing queue machinery.

## Token usage

- Token usage: unavailable from current CLI output.
- Nested queue Codex workbenches recorded an exact aggregate of 5,912,297 input tokens and 71,801 output tokens across five sessions; individual exact usage is retained in child sidecars.


<!-- token_usage:AOS-2026-0169 -->
## token_usage
```json
{
  "token_usage": {
    "orchestrator": {
      "input": 0,
      "output": 0
    },
    "subagents": [],
    "workbenches": [],
    "totals": {
      "input": 0,
      "output": 0
    },
    "est_cost_usd": 0.0,
    "unavailable": [
      "orchestrator tokens",
      "subagent tokens",
      "workbench session totals"
    ]
  },
  "profile_invocation": {
    "requested_profile": "aos-orchestrator",
    "fallback_profile": "default",
    "invoked": false,
    "native_invocation": "unavailable",
    "resolved_profile": "aos-orchestrator",
    "evidence": "`hermes profile show aos-orchestrator` rc=0; profile present WITH configured model",
    "reason": "Profile 'aos-orchestrator' has a configured model, but `hermes profile use` is prohibited for queue routing (queue/profiles/README.md); the queue does not switch the sticky default. Native switching intentionally not performed."
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


<!-- token_usage:AOS-2026-0168 -->
## token_usage
```json
{
  "token_usage": {
    "orchestrator": {
      "input": 0,
      "output": 0
    },
    "subagents": [],
    "workbenches": [],
    "totals": {
      "input": 0,
      "output": 0
    },
    "est_cost_usd": 0.0,
    "unavailable": [
      "orchestrator tokens",
      "subagent tokens",
      "workbench session totals"
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
