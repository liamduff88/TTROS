# Agentic OS Stable Startup State — 2026-06-22

Status: working.

## Stable startup model

Windows startup now brings Telegram and the dashboard backend online hidden.

Telegram startup chain:
Windows startup -> AgenticOS-Telegram-Bridge-Hidden.vbs -> Start-Telegram-Bridge-Auto.ps1 -> py.exe -3 -u telegram_bridge.py -> python.exe -u telegram_bridge.py

Backend startup chain:
Windows startup -> AgenticOS-Backend-Hidden.vbs -> Start-AgenticOS-Backend-Auto.ps1 -> uvicorn backend.main:app on http://127.0.0.1:8010

Desktop dashboard launcher remains the operator cockpit launcher:
C:\Users\Admin\Desktop\Agentic OS Dashboard.bat -> Start-AgenticOS-Dashboard.ps1 -> dashboard frontend/browser on http://127.0.0.1:3010

## Normal process shape

A healthy Telegram bridge normally appears as two processes:
py.exe -3 -u telegram_bridge.py
python.exe -u telegram_bridge.py

That is one bridge, not a duplicate.

Backend should show port 8010 listening with python/uvicorn.

## Startup folder stable entries

Keep:
AgenticOS-Telegram-Bridge-Hidden.vbs
AgenticOS-Backend-Hidden.vbs

Disabled duplicate Telegram startup entries were moved to:
Startup\AgenticOS-disabled-duplicates\

Do not restore these unless explicitly needed:
AgenticOS-Telegram-Bridge.bat
AgenticOS-Telegram-Bridge.lnk
AgenticOS-TelegramBridge.cmd

## Critical fixes learned

Do not redirect bridge stdout into logs\telegram_bridge.log because telegram_bridge.py writes to that file itself.
Use separate files only:
logs\telegram_bridge.stdout.log
logs\telegram_bridge.stderr.log

Do not make Start-Telegram-Bridge-Auto.ps1 kill processes matching Start-Telegram-Bridge-Auto.ps1. It can kill itself.
It should only manage actual bridge worker processes matching telegram_bridge.py.

## Working behavior

Telegram /status works.
Normal Telegram operator text routes through Telegram bridge -> dashboard backend on 8010 -> AgenticOSClean -> Hermes/Codex lower-token route.

If /status works but normal text says Hermes route failed: URLError, the likely issue is backend 8010, not Telegram.

## Do not touch unless explicitly requested

Do not patch:
connectors\telegram_bridge\telegram_bridge.py
connectors\telegram_bridge\.env
dashboard\backend\main.py /api/wsl/hermes route
Hermes/Codex wrappers

Do not change /api/wsl/hermes away from the stable lower-token route:
aos-hermes codex '<task>'

Do not reopen Telegram token-burn optimization.

## Next build direction

Leave Telegram/startup alone.
Continue with connector/dashboard work: read / search / status / draft / prepare.
External send/write/push/mutate actions only when Liam explicitly commands the specific action.
