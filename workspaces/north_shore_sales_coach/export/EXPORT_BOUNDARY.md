# North Shore Export Boundary

This package is the boxed North Shore Sales Coach product: `src/`, `config/`,
`tests/`, `scripts/`, `schemas/`, `prompts/`, `google_sheets/`,
`hermes_wrapper/`, and these `export/` notes belong with it.

Do not import the main Agentic OS Telegram bridge, dashboard, backend, queue,
agents, context, tools, scripts, sessions, vaults, MCP/plugin state, Hermes
runtime state, or Composio execution paths. Keep one direct runner:
salesperson DM -> dedicated North Shore bot -> North Shore direct runner ->
this workspace.

Secrets, runtime data, tokens, Sheet IDs, OAuth/client secrets, bridge secrets,
chat IDs, and customer data are deployment/runtime state. Do not commit them,
print them, or include them in exports.

Keep this workspace extractable as a standalone product package. External
Google Sheets or Apps Script access must stay behind the provider-neutral
adapter boundary.
