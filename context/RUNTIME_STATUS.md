# Agentic OS Live — Runtime Status
> Revisit: after runtime or service topology changes. · Last touched: 2026-07-17.

Runtime:
- WSL distro: AgenticOSClean
- Canonical workspace: /home/liam/agentic-os-live
- Authoritative storage: Linux-native filesystem
- Frozen rollback: /mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live
- Codex execution root: fixed at `/home/liam/agentic-os-live` (not caller-overridable)

Services:
- FastAPI: existing `dashboard/backend/main.py`, Linux port 8010
- Frontend: existing `dashboard/frontend`, Linux port 3010
- Runner: existing `tools/aos-orchestration-runner.py --watch`
- Lifecycle: systemd user units - `aos-backend`, `aos-frontend`,
  `aos-runner`, `aos-bridge`, `aos-north-shore` (linger enabled, start at boot)
- Manage with: `systemctl --user start|stop|status <unit>`
- Recurring Gmail capture: `aos-gmail-capture.timer` and
  `aos-gmail-capture.service` - read-only, every 15 minutes, no model invocation
- The legacy shell launcher under `tools/` was deleted 2026-08-15. systemd is the
  only runtime authority and there is no wrapper script to run.

Ready:
- aos-codex
- aos-claude
- aos-hermes

Hermes delegates:
- `aos-hermes codex "TASK"` forwards to the supervised `aos-codex` backend route
- aos-hermes claude "TASK"

Codex policy:
- Executable: `/home/liam/.local/npm/bin/codex`
- Linux user: `liam`
- Working directory: `/home/liam/agentic-os-live`
- Sandbox: `danger-full-access`
- Approval policy: `never`

Rules:
- Old Ubuntu-24.04 is archive only.
- Do not import old .hermes, old vault, old sessions, old skills, ZPC, MCP, gateway, OpenRouter/glm state, or old runtime files.
- Dashboard is Antigravity-built front end.
- Clean WSL is the live runtime.
- Windows is an optional launcher/browser client only; native Windows mutation is retired.
- The superseded Downloads native-Windows storage proof tests an unsupported architecture and must not be run as acceptance evidence.
