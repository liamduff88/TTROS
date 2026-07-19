# AOS-2026-0172 — lane actions receipt
> Revisit: if Hermes requests revision. · Last touched: 2026-07-18.

PASS

- Parent: `AOS-2026-0169`
- Lane / workbench: operations / Codex
- Profile / model: Codex workbench / GPT-5
- Implemented: per-item review actions for `human_review` and `needs_input`; per-item run/cancel for `inbox` and `agent_todo`; blocked reason/unblock; current-filter checkbox selection with strictly sequential run/cancel.
- Endpoint constraint: all operations use existing per-item `run`, `status`, `receipt`, or `review-close` endpoints. Cancel selected calls `receipt` once per item with `status: cancelled`, preserving each cancellation receipt; no bulk endpoint was added.
- Preserved component: `dashboard/frontend/src/components/HumanReviewCard.jsx` unchanged at SHA-256 `e47f1caf21fb3699dde9a63dd22a9fee2c626509053a685adb7f29ce009d92d1`; reused in compact `human_review` rows.
- Focused tests: `node --test tests/shellState.test.js tests/laneWorkspaceState.test.js tests/laneWorkspaceActions.test.js tests/laneWorkspaceComponent.test.js` — 18/18 pass.
- Frontend build: `npm run build` — pass (Vite, 1,652 modules transformed).
- Scope: dashboard lane view/API helper/action helper and focused dashboard tests only. Work Queue, backend, queue schema, runner, and protected non-dashboard implementation paths were not edited.
- Evidence paths: `dashboard/frontend/src/laneWorkspaceActions.js`, `dashboard/frontend/src/views/LaneWorkspace.jsx`, `dashboard/frontend/tests/laneWorkspaceActions.test.js`, `dashboard/frontend/tests/laneWorkspaceComponent.test.js`.

## Correction 1 evidence

- Removed the full `className` visual/body-hiding override from the `HumanReviewCard` call in `LaneWorkspace.jsx`; the established card now renders with its body, border, and radius intact.
- Kept the lane action panel outside the review card. The component test now proves `data-review-card-body` renders once, no body-hiding variant is emitted, and the operator-note/actions markup begins after the review card's closing `article`.
- Preserved component check: `dashboard/frontend/src/components/HumanReviewCard.jsx` remains unchanged at SHA-256 `e47f1caf21fb3699dde9a63dd22a9fee2c626509053a685adb7f29ce009d92d1`.
- Narrow correction tests: `node --test tests/laneWorkspaceActions.test.js tests/laneWorkspaceComponent.test.js` — 5/5 pass; follow-up component-only assertion run — 1/1 pass.
- Frontend build (required because rendered JSX changed): `npm run build` — pass (Vite, 1,652 modules transformed).
- Correction implementation/proof edits were limited to `dashboard/frontend/src/views/LaneWorkspace.jsx`, its focused component test, and this existing receipt. The only queue-state mutation was the requested receipt reattachment/status transition; no `HumanReviewCard`, Work Queue view, backend, schema, or runner implementation was changed.

## Token usage

- Input: unavailable (workbench telemetry not exposed)
- Output: unavailable (workbench telemetry not exposed)
- Total: unavailable (workbench telemetry not exposed)

<!-- token_usage:AOS-2026-0172 -->
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
        "session_id": "019f76fc-5fce-7851-a02b-e413bf03c7cd",
        "input": 682510,
        "output": 5485,
        "source": "reported"
      }
    ],
    "totals": {
      "input": 682510,
      "output": 5485
    },
    "est_cost_usd": 0.0,
    "unavailable": [
      "Codex model identity",
      "cost for unavailable Codex model"
    ]
  },
  "profile_invocation": {
    "invoked": true,
    "tool": "codex",
    "session_id": "019f76fc-5fce-7851-a02b-e413bf03c7cd",
    "lifecycle": "process_exit",
    "queue_status_at_reconciliation": "human_review",
    "runtime_policy": {
      "executable": "/home/liam/.local/npm/bin/codex",
      "cwd": "/home/liam/agentic-os-live",
      "linux_user": "liam",
      "effective_uid": 1002,
      "sandbox": "danger-full-access",
      "sandbox_mode": "danger-full-access",
      "approval_policy": "never",
      "ask_for_approval": "never"
    }
  },
  "capture_evidence": {
    "source": "Codex supervisor final structured usage event",
    "captured_after_process_exit": true,
    "raw_summary": "{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":682510,\"cached_input_tokens\":598784,\"output_tokens\":5485,\"reasoning_output_tokens\":2422}}",
    "summary_format": "turn.completed JSONL",
    "input_tokens": 682510,
    "output_tokens": 5485,
    "total_tokens": 687995,
    "cli_version": "codex-cli 0.144.1",
    "model_identity": "unavailable",
    "component_scope": {
      "orchestrator": "not invoked by direct Codex launch",
      "subagents": "none invoked",
      "workbench": "Codex CLI reported exact usage"
    },
    "cached_input_tokens": 598784,
    "reasoning_output_tokens": 2422,
    "invocation": {
      "executable": "/home/liam/.local/npm/bin/codex",
      "cwd": "/home/liam/agentic-os-live",
      "linux_user": "liam",
      "effective_uid": 1002,
      "sandbox": "danger-full-access",
      "sandbox_mode": "danger-full-access",
      "approval_policy": "never",
      "ask_for_approval": "never"
    }
  },
  "initial_prompt_bytes": "unavailable from current CLI output",
  "model_turns": "unavailable from current CLI output",
  "retained_context_bytes": "unavailable from current CLI output",
  "compaction_count": "unavailable from current CLI output",
  "fresh_input": 682510,
  "cached_input": 598784,
  "output": 5485,
  "reasoning": 2422,
  "largest_tool_result_bytes": "unavailable from current CLI output"
}
```
