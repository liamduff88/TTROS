# Entrypoint contract

Hermes-facing calls are limited to these package-scoped operations:

- `route_north_shore_message`: accept one message plus package-local identity,
  role, and chat context; return a North Shore intent/result.
- `route_north_shore_command`: accept one slash command plus role and chat
  context; reject commands absent from `config/commands.json`.
- `generate_north_shore_report`: read package-local sales records and return a
  deterministic North Shore report.
- `validate_north_shore_config`: validate paths, placeholders, and disabled
  integration flags without starting services.

These entrypoints may use only package-local routing, authorization, storage,
and report code. Basic commands must be local and zero-token. Unknown input is
rejected or converted to local help; it is never forwarded to a host agent.

The wrapper must block `/work`, general Hermes commands, Codex, Claude,
arbitrary tool invocation, shell or OS control, web/search/browser use, and
filesystem access outside this workspace. It must also block Google writes,
Composio execution, live Telegram polling, and Agentic OS backend or Telegram
bridge routing.

LLM, Telegram, and Sheets boundaries are not Hermes-facing entrypoints. They
remain disabled by default and require separate deployment configuration and
authorization. No entrypoint may activate an integration merely because its
provider or environment-variable name is configured.
