# hooks/ — deterministic reflexes
> Revisit: when a hook stops firing or a new event needs one. · Last touched: 2026-07-31.

Hooks are Layer 2's enforcement half — rules state the constraint, hooks are
the script/checkpoint tied to an event that makes it fire every time, no
model discretion. Hooks are activated only where a real lifecycle event exists.

## Inventory

| Hook | Event | Enforces |
|---|---|---|
| `pre_external_action.md` | Hermes `pre_tool_call` plus shared Composio mutation adapter | `EXTERNAL_ACTIONS.md` gated list · `rules/never.md` #1, #11 |
| `pre_publish_check.md` | Hermes `pre_tool_call` plus shared Composio send/post/publish adapter | `rules/always.md` #2 · `rules/never.md` #10 · CASL/outreach-basis check |
| `client_isolation_check.md` | Scoped Brain retrieval/completion and Hermes `pre_tool_call` | `rules/always.md` #7 · `rules/never.md` #9 · `rules/client_data_boundaries.md` |
| `protected_path_check.md` | Hermes `pre_tool_call` before mutating tools | `PROTECTED_PATHS.md` · `rules/never.md` #2, #3, #8 |
| `secret_exposure_check.md` | Hermes `pre_tool_call` plus pre-mutation payload scan | `rules/never.md` #6 · `EXTERNAL_ACTIONS.md` verification note |
| `token_budget_check.md` | Any queue item transition to done | `rules/always.md` #1 · `rules/token_budget.md` · `context/TOKEN_POLICY.md` |
| `receipt_completeness_check.md` | Any queue item transition to done | `rules/always.md` #1, #8 · `rules/completion_contract.md` |

## Status
All seven contracts have executable enforcement. `hooks/runtime_guard.py` is
installed as the native Hermes `pre_tool_call` hook for the orchestrator and
four department profiles. Exact external authorization and publication checks
run again at `connectors/composio_access_adapter.py`; client Brain reads and
completion provenance are constrained by `tools/business_brain_context.py`.
Token-budget and receipt-completeness checks remain at the shared queue
`finalize_done()` lifecycle point.

## Pointers
- Rules: `rules/always.md` · `rules/never.md`
- Context: `context/EXTERNAL_ACTIONS.md` · `context/PROTECTED_PATHS.md` ·
  `context/TOKEN_POLICY.md`
