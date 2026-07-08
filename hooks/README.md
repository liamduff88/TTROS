# hooks/ — deterministic reflexes
> Revisit: when a hook stops firing or a new event needs one. · Last touched: 2026-07-07.

Hooks are Layer 2's enforcement half — rules state the constraint, hooks are
the script/checkpoint tied to an event that makes it fire every time, no
model discretion. None are wired live yet; each doc below is the spec to
wire (Claude Code `.claude/settings.json` hooks, or a Hermes queue-runner
checkpoint) when the harness is ready.

## Inventory

| Hook | Event | Enforces |
|---|---|---|
| `pre_external_action.md` | Any send/write/push/mutate/delete tool call | `EXTERNAL_ACTIONS.md` gated list · `rules/never.md` #1, #11 |
| `pre_publish_check.md` | Any public-surface write (LinkedIn, website, outreach send) | `rules/always.md` #2 · `rules/never.md` #10 · CASL/outreach-basis check |
| `client_isolation_check.md` | Any output referencing client data | `rules/always.md` #7 · `rules/never.md` #9 · `rules/client_data_boundaries.md` |
| `protected_path_check.md` | Any file write/edit | `PROTECTED_PATHS.md` · `rules/never.md` #2, #3, #8 |
| `secret_exposure_check.md` | Any commit, print, or external-facing draft | `rules/never.md` #6 · `EXTERNAL_ACTIONS.md` verification note |
| `token_budget_check.md` | Any queue item transition to done | `rules/always.md` #1 · `rules/token_budget.md` · `context/TOKEN_POLICY.md` |

## Status
Documented, not executed. Every hook doc states its trigger event, its
check, and its blocked-action behavior — none call live APIs. Wiring is a
one-time harness config step, not part of this batch.

## Pointers
- Rules: `rules/always.md` · `rules/never.md`
- Context: `context/EXTERNAL_ACTIONS.md` · `context/PROTECTED_PATHS.md` ·
  `context/TOKEN_POLICY.md`
