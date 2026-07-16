# PROTECTED_PATHS.md — what nothing in this OS touches uninvited
> Revisit: on a new protected area or a boundary incident. · Last touched: 2026-07-15.

## Source of truth
The binding list lives in the Business Brain at
`business_brain:operating_context/protected_paths.md` (mirrored into this repo's memory
pointers). This file is the OS-side enforcement contract for that list — it
does not restate it in full, it commits to respecting it.

## Categories (see Business Brain for exact paths)
- **Runtime / connector state** — Telegram bridge `.env` and config, North
  Shore sales coach `.runtime/` and `data/`, all connector credentials, OAuth
  state, tokens, secrets, live runner state.
- **Dashboard code** — `dashboard/backend/`, `dashboard/frontend/`, launcher
  files. Frozen this phase; patch in place, no second dashboard.
- **Archive / quarantine only** — `C:\AI-Vault`, old Ubuntu, old Hermes state,
  old AI Native Source of Truth vaults, old sessions, old skills, old ZPC
  material, any old runtime/connector/plugin/MCP state. Reference for mining
  only, on explicit approval — never a live dependency, never imported wholesale.
- **North Shore files** — a separate client system. Not this OS's to read,
  write, or reason about beyond what's explicitly scoped.

## Rule
No agent, workbench, or skill modifies anything in these categories without
Liam explicitly scoping that specific work in that turn. Read access for
context is not write access for change. "I need to check X" is not "I may
edit X."

## Enforcement
Hook: protected_path_check.md — fires before any write/edit tool call,
blocks on a path match, surfaces the match in the receipt. Mirrored in
rules/never.md #2, #3, #8. A blocked attempt is reported, not silently
retried against a different path.

## What this is not
Not a blanket "don't touch the filesystem" rule — AgenticOSClean and the live
workspace outside these categories are the normal work surface. This file
exists so the narrow, high-cost mistakes (leaking a secret, corrupting a
client's live data, reviving legacy state) can't happen by drift.
