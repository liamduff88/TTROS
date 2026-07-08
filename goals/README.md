# goals/ — standing invariants, re-verified daily
> Revisit: when a goal is added, retired, or flips to VIOLATED. · Last touched: 2026-07-07.

A goal is a finished thing that must stay true. Verifying it once is an
assumption with a timestamp — so a passed check graduates into a
`*.goal.md` file here and is re-checked every day, forever, by
`loop/verify-goals.sh` (documented, not yet wired live). Results append to
`queue/goal_ledger.jsonl` per `run_ledger_schema` / `goal_ledger_schema.json`.

## Predicate rule
Every predicate is a command or a deterministic read: exit 0 (or an
observable match) means the invariant holds. No adjectives, no judgment
calls — if a shell script can't check it, it isn't a goal, it's a hope.

## Inventory

| Goal | Checks | On violation |
|---|---|---|
| `os_startup_health.goal.md` | Root identity + rules + hooks files all present and readable | Wake Liam. Do not auto-fix. |
| `queue_receipts_visible.goal.md` | Every done-transition in `run_ledger.jsonl` has a matching receipt | Wake Liam. Do not auto-fix. |
| `token_ledger_current.goal.md` | `token_ledger.jsonl` has an entry within the last active session window | Wake Liam. Do not auto-fix. |
| `business_brain_pointer_valid.goal.md` | The Business Brain path this OS points to still exists and is readable | Wake Liam. Do not auto-fix. |
| `no_old_runtime_references.goal.md` | No file in this repo references `C:\AI-Vault`, old Ubuntu, ZPC, or legacy_harvest paths | Wake Liam. Do not auto-fix. |
| `no_external_action_without_approval.goal.md` | No `run_ledger.jsonl` entry shows a gated verb executed without an `approved_external_action` flag | Wake Liam immediately. Do not auto-fix. |

## Status
All six are `status: satisfied` at authoring time (files exist as of this
batch). The daily sentinel and `verify-goals.sh` script are specced in
`How_to_Build_An_Agentic_OS_using_Fable_5` but not yet wired to a live
scheduler — that's a harness step, not a content step.

## Pointers
- Ledger: `queue/goal_ledger.jsonl` · schema: `queue/goal_ledger_schema.json`
- Rules: `rules/never.md` · `rules/always.md`
- Enforcement pattern: `hooks/README.md`
