# Runtime requirements

- Python 3.10 or newer
- Writable `data/` and `logs/` directories
- UTF-8 filesystem support
- No third-party Python packages for the Phase 1 shell or tests

Future integrations must be optional dependency groups. The isolated workspace
owns its Telegram token/config, role map, local data, and Sheets connector
configuration. Telegram must run as a direct bot transport and must not use the
Agentic OS Telegram bridge. A Hermes host/wrapper must not expose general Hermes
OS commands.

The wrapper must inject a dedicated `NORTH_SHORE_TELEGRAM_BOT_TOKEN` and may
inject `NORTH_SHORE_DASHBOARD_URL`; neither value belongs in the export. Basic
routing, authorization, roster/report generation, and dashboard-link handling
are local and zero-token. Optional LLM work must enter only through the North
Shore LLM adapter after an approved deterministic intent; it is never a general
Telegram fallback.

The provider-neutral Sheets boundary has no third-party dependency. A deployment
may separately select a Hermes-native Google/Drive/Sheets connector, direct
Google Sheets API, or Composio. Provider selection alone must not enable reads
or writes; integrations remain disabled until separately configured and invoked.

For the demo Apps Script bridge, set
`NORTH_SHORE_SHEETS_PROVIDER=apps_script_webapp` and
`NORTH_SHORE_SHEETS_WEBAPP_URL` locally. Do not commit the real `/exec` URL.
