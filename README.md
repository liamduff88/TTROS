# Agentic OS Live — v0.1

Local operator cockpit for Liam's AI workbench system.

## Ports
- Backend: http://127.0.0.1:8010
- Frontend: http://127.0.0.1:3010

## Launch
Double-click: `C:\Users\Admin\Desktop\Agentic OS Dashboard.bat`

## Stack
- Backend: FastAPI + Python 3.11+
- Frontend: React + Vite + TailwindCSS
- Icons: lucide-react

## Principles
- Model-silent by default — zero API tokens for UI interactions
- Local-only — no cloud, no login, no database
- v0.1 — agent cards are placeholders and command-copy surfaces only

## Structure
```
Agentic OS Live/
  context/          Operator rules
  dashboard/
    backend/        FastAPI app (port 8010)
    frontend/       React + Vite app (port 3010)
    data/           Local tracker state
    screenshots/    Validation captures
  packets/          Task packets (JSON)
  results/          Output results (read-only view)
  logs/             Log files (read-only view)
```
