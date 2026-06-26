# Composio-First Connector Plan

Updated: 2026-06-21 18:05:31

Decision:
- Use Composio as the primary connector hub.
- Rebuild all connector auth fresh.
- Do not copy old auth, old connector configs, old prompts, old MCP/plugin state, sessions, skills, gateway files, or old runtime credential folders.

Target first connectors:
- Gmail
- Google Calendar
- Google Drive
- GitHub
- AgentMail
- GoHighLevel / HighLevel

Operating rule:
- Read/search/status/draft/prepare are normal once configured.
- External sends, CRM writes, calendar/email mutations, website deploys, paid actions, and GitHub pushes require explicit operator command.

Notes:
- Composio managed auth should be used where available.
- HighLevel may require custom OAuth/API setup inside Composio.
- AgentMail can be handled through Composio if preferred.
