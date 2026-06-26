# Natural Language Connector Standard

Every new Agentic OS connector must default to natural language.

Plain human text is the primary interface.

Slash commands may exist for explicit control, testing, admin, or fallback, but routine use must not require slash commands.

Operator mode:
- Private/operator normal text routes to Hermes / Agentic OS.

Pilot/customer/group mode:
- Normal text performs that channel's scoped business action.
- Example: North Shore Honda group normal text saves a sales report.
- Do not give pilot/customer groups full OS control unless Liam explicitly asks.

Connector build requirement:
- Normal plain text should work for the main use case.
- Slash commands are advanced/admin/fallback only.
- Keep operator mode and pilot/customer mode separate.

Do not create a second dashboard, second bot, or new connector architecture just to enable natural language.
