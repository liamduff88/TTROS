# TTROS / Agentic OS Operating Baseline
> Revisit: after authoritative runtime, launcher, or Codex policy changes. · Last touched: 2026-07-17.

Date: 2026-07-17

## Live workspace

Linux:
`AgenticOSClean` at `/home/liam/agentic-os-live`

The prior Windows/`/mnt/c` tree is a frozen rollback snapshot, not a live
workspace or invocation target.

Memory root:
`business_brain:README.md`

Old AI Native Source of Truth and `C:\AI-Vault` are archive only, not live memory.

## Git

Remote: `https://github.com/liamduff88/TTROS.git`
Branch: `main` tracking `origin/main`

## Launch commands

Dashboard:
`tools/aos-linux-runtime.sh desktop-start`

Codex:
`cd "/home/liam/agentic-os-live" && /home/liam/.local/npm/bin/codex --sandbox danger-full-access --ask-for-approval never -C /home/liam/agentic-os-live`

Headless Codex route used by dashboard:
`aos-codex '<task>'` forwards to `/api/wsl/codex`, whose shared policy adds the
same executable, user, cwd, sandbox, and approval contract with captured output
and no direct fallback.

## Status and tests

Dashboard:
- Backend source compiles with `python3 -m py_compile dashboard/backend/main.py`.
- Existing mocked backend routing tests pass with `python3 -m unittest dashboard/backend/test_composio_hermes.py`.
- Manual test: start the dashboard command, then open `http://127.0.0.1:3010` and confirm backend health through the UI.

Telegram / Olmec:
- Telegram bridge is owned separately by `connectors\telegram_bridge\Start-Telegram-Bridge-Auto.ps1`.
- Olmec / Telegram live connector execution is not part of this checkpoint.
- Manual test when explicitly operating live connectors: send `/status` in Telegram and confirm the compact closeout returns without raw transcript leakage.

Token usage:
- Codex token capture works when CLI output exposes token usage.
- Hermes / Claude may show `Token usage: unavailable from current CLI output`.
- Token usage unavailable is not a blocker for operating the system.

## Stable

- Clean workspace pointer to TTROS Business Brain.
- Dashboard backend source compiles.
- Dashboard backend mocked routing tests pass.
- Dashboard launcher starts backend on `127.0.0.1:8010` and frontend on `127.0.0.1:3010`.
- Old vaults are archive only.

## Intentionally deferred

- North Shore work unless explicitly resumed.
- Live connector writes unless explicitly commanded.
- Hermes gateway/profile activation.
- Dashboard feature patches until business use reveals a real need.

## Hard rules

- No old Ubuntu, old vault, old `.hermes`, old session, old skill, ZPC, MCP, OpenRouter, old AI Native Source of Truth, or `C:\AI-Vault` runtime.
- Do not inspect private vault contents or print secrets, tokens, OAuth values, API keys, Telegram IDs, Sheet IDs, or credentials.
- Do not touch `/home/liam/.composio` or `/home/liam/.hermes`.
- Do not run Hermes, Composio, Telegram polling, Google calls, or live connectors during stabilization.
- No North Shore unless explicitly resumed.
- No live connector writes unless explicitly commanded.
- No more dashboard feature patches until business use reveals a real need.
