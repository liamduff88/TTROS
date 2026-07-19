# AOS-2026-0170 — lane route and Cockpit card receipt
> Revisit: if Hermes requests revisions during parent AOS-2026-0169 review. · Last touched: 2026-07-18.

- Parent: `AOS-2026-0169`
- Lane / workbench: operations / Codex
- Profile: Codex workbench
- Model requested / confirmed: unavailable / Codex (exact model identifier unavailable)

## Intended diff

- `dashboard/frontend/src/shellState.js`: add validated `/lane/{name}` path helpers and let a lane URL override restored shell state with a lane-filtered Work Queue tab.
- `dashboard/frontend/src/App.jsx`: synchronize lane routes with browser history, restore direct lane links, and handle back/forward navigation while preserving the pre-existing refresh-failure and `/` shortcut edits.
- `dashboard/frontend/src/views/DashboardV1.jsx`: make each full Lane Activity card a semantic link, retain all displayed card content, convert nested item controls to display chips, and remove the separate filtered-queue button.
- `dashboard/frontend/tests/shellState.test.js`: add focused route/path/restoration coverage.

## Validation summary and proof

- PASS — `node --test dashboard/frontend/tests/shellState.test.js`: 8 tests passed, 0 failed; includes valid/invalid lane paths and direct-route restoration proof.
- PASS — `npm --prefix dashboard/frontend run build`: Vite production build completed; 1,649 modules transformed.
- PASS — `git diff --check -- dashboard/frontend/src/App.jsx dashboard/frontend/src/shellState.js dashboard/frontend/src/views/DashboardV1.jsx dashboard/frontend/tests/shellState.test.js`: no whitespace errors.
- Behavioral proof: `/lane/marketing`, `/lane/revenue`, `/lane/delivery`, `/lane/operations`, and `/lane/unassigned` resolve to `work-queue` with `{ lane }`; each Cockpit lane card exposes that URL in `href` and uses the whole card as the click target.

## Protected areas

- No edits to `dashboard/frontend/src/views/Queue.jsx`, queue schema/tooling, orchestration runner, `dashboard/backend/`, or `HumanReviewCard.jsx`.
- No external systems, pushes, secrets, North Shore data, legacy runtime, or destructive actions accessed.
- Pre-existing dirty edits were preserved; in particular, unrelated `App.jsx` refresh-failure handling and keyboard-shortcut changes remain intact.

## Token usage

```yaml
token_usage:
  input: unavailable
  output: unavailable
  total: unavailable
  source: harness did not expose exact session token counts
```


<!-- token_usage:AOS-2026-0170 -->
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
        "session_id": "019f76e3-2970-70f2-a86a-b6fc79703b08",
        "input": 590380,
        "output": 12440,
        "source": "reported"
      }
    ],
    "totals": {
      "input": 590380,
      "output": 12440
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
