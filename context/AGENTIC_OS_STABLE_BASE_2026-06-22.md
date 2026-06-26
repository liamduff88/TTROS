# Agentic OS Stable Base — 2026-06-22

Status: STABLE BASE CONFIRMED

Confirmed:
- Windows Startup launches backend through AgenticOS-Backend-Hidden.vbs → Start-AgenticOS-Backend-Auto.ps1.
- Windows Startup launches Telegram through AgenticOS-Telegram-Bridge-Hidden.vbs → Start-Telegram-Bridge-Auto.ps1.
- Backend 8010 is live.
- Hermes clean router is live in AgenticOSClean.
- Telegram bridge has normal process shape: py.exe + python.exe.
- Telegram /status returns compact closeout only.
- Telegram responses preserve Token usage field.
- Raw Codex transcript leak is fixed.
- Duplicate "Hermes accepted. Running." Telegram response is fixed.

Expected token fallback:
Token usage: unavailable from current CLI output

Do not touch unless explicitly requested:
- connectors\telegram_bridge\.env
- connectors\telegram_bridge\allowed_chats.json
- connectors\telegram_bridge\telegram_bridge.py
- connectors\telegram_bridge\Start-Telegram-Bridge-Auto.ps1
- Start-AgenticOS-Backend-Auto.ps1
- dashboard\backend\main.py /api/wsl/hermes
- aos-hermes / aos-codex / aos-claude wrappers

Next safe build options:
1. Composio action usability.
2. Archive old launcher/patch clutter using the cleanup candidate manifest.
3. Dashboard polish.

Do not rebuild the runtime.
