# AOS-2026-0171 — dedicated lane workspace receipt
> Revisit: if Hermes requests revisions during parent AOS-2026-0169 review. · Last touched: 2026-07-18.

- Parent: `AOS-2026-0169`
- Dependency reviewed: accepted child-1 receipt `AOS-2026-0170_lane_route_receipt.md`
- Lane / workbench: operations / Codex
- Profile: Codex workbench
- Model requested / confirmed: unavailable / Codex (exact model identifier unavailable)

## Intended diff

- `dashboard/frontend/src/laneWorkspaceState.js`: add pure lane normalization/scoping, the six required filter counts, the Needs Me-or-All Active default, and Needs Me → ready → blocked → other ordering with newest-first ordering inside each group.
- `dashboard/frontend/src/views/LaneWorkspace.jsx`: add the dedicated lane workspace over the existing all-scope queue endpoint, with lane-scoped filter tiles, explicit Done/Cancelled history, existing compact human-review cards, generic queue work-item cards, refresh, empty, loading, and error states.
- `dashboard/frontend/src/components/DashboardKit.jsx`: add a reusable queue work-item card built from the existing lane, workbench-color, and status-chip primitives.
- `dashboard/frontend/src/shellState.js` and `dashboard/frontend/src/App.jsx`: minimally retarget accepted `/lane/{name}` navigation from temporary `work-queue` rendering to `lane-workspace`; ordinary Work Queue navigation and the `/` Needs Me shortcut remain Work Queue routes.
- `dashboard/frontend/tests/laneWorkspaceState.test.js`, `dashboard/frontend/tests/laneWorkspaceComponent.test.js`, and `dashboard/frontend/tests/shellState.test.js`: add focused state, render, and route-target coverage.

## Behavioral proof

- Lane membership is resolved from `lane:*` tags first, then `lane`, then a recognized lane owner, with `ops` normalized to `operations` and unmatched items scoped to `unassigned`.
- Counts and filters are lane-local for `Needs Me`, `To Run`, `Blocked`, `All Active`, `Done`, and `Cancelled`; another lane's items do not enter the count or result set.
- The default is `Needs Me` when the selected lane contains `human_review` or `needs_input`; otherwise it is `All Active`.
- Results sort by Needs Me, ready (`inbox` / `agent_todo`), blocked, then other statuses, with updated/created timestamp and ID tie-breaking newest first inside each group.
- A `human_review` result renders the existing `HumanReviewCard` once; all other visible results use the shared queue work-item card.
- Accepted whole-card Cockpit navigation still calls `work-queue` with a lane parameter, and shell navigation translates only that valid lane intent to the dedicated workspace and `/lane/{name}` URL.

## Validation summary

- PASS — focused state/component/route suite: `node --test tests/shellState.test.js tests/laneWorkspaceState.test.js tests/laneWorkspaceComponent.test.js`: 14 passed, 0 failed.
- PASS — complete frontend suite: `npm test`: 36 passed, 0 failed.
- PASS — `npm run build`: Vite production build completed; 1,651 modules transformed.
- PASS — targeted `git diff --check`: no whitespace errors.
- PASS — `dashboard/frontend/src/components/HumanReviewCard.jsx` remained byte-identical throughout; SHA-256 `e47f1caf21fb3699dde9a63dd22a9fee2c626509053a685adb7f29ce009d92d1` before and after.

## Protected areas and dirty-tree handling

- This task did not edit `dashboard/frontend/src/views/Queue.jsx`, `dashboard/frontend/src/components/HumanReviewCard.jsx`, `dashboard/backend/`, queue schema/tooling, orchestration runner, or unrelated workflow artifacts.
- All pre-existing dirty and untracked work was left in place. Existing accepted child-1 edits in `App.jsx`, `shellState.js`, and `shellState.test.js` were extended narrowly instead of replaced.
- No external systems, pushes, secrets, North Shore data, legacy runtime, or destructive actions were accessed.
- Status requested: `human_review`; this child is not marked done.

## Token usage

```yaml
token_usage:
  input: unavailable
  output: unavailable
  total: unavailable
  source: harness did not expose exact session token counts
```


<!-- token_usage:AOS-2026-0171 -->
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
        "session_id": "019f76e9-5899-7331-a368-4aebca2c8ecd",
        "input": 1371445,
        "output": 16387,
        "source": "reported"
      }
    ],
    "totals": {
      "input": 1371445,
      "output": 16387
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
