# Operator Rules — Minimal v0.1

## Model-Silent Default
Opening the dashboard, clicking cards, switching agents, editing packets, copying commands, and moving sliders use ZERO model/API tokens.

## Allowed in v0.1
- Open Agentic OS Live folder
- Open ChatGPT in browser (allowlisted launcher)
- Copy placeholder commands
- Create and save task packets locally
- View logs and results (read-only)
- Update tracker state locally

## Not Allowed in v0.1
- Live agent execution
- Connecting to existing Claude/Codex/Hermes/Antigravity installations
- Importing old vault/session/memory data
- Arbitrary shell command execution
- Any external API calls from the launcher

## Launcher Allowlist
Only two launchers are active in v0.1:
1. ChatGPT — opens chatgpt.com in browser
2. Local Vault / Obsidian — opens the Agentic OS Live folder

All other agent launchers return: "Not connected yet — configure clean install path first."

## Packet Discipline
Packets are created locally and saved to /packets/. They are never auto-sent or executed.

## Data Scope
- All data is local to: C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live
- No old Mission Control, Hermes runtime, or vault data is imported
