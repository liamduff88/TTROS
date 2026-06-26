# North Shore Sales Coach profile

This profile is a narrow interface to the package-local North Shore Sales Coach.
It is not a general Hermes coordinator, operator route, or Agentic OS route.

## Required routing

Route a salesperson's Telegram DM only through the dedicated North Shore Sales
Coach bot and its direct package runner or command handler. The package performs
deterministic local handling first, writes local JSONL, and exposes a
provider-neutral Sheets adapter. A selected Google Sheets connector may be
configured later for Ryan's admin group and dashboard/report tabs.

Basic commands and recognized local intents are deterministic, local, and
zero-token. Reject unknown input or convert it to safe package-local help.
Never forward unknown or recognized North Shore input to general Hermes,
Agentic OS, or a private operator route.

## Capability boundary

Expose only the four operations declared in
`north_shore_wrapper_manifest.yaml`. Do not expose general Hermes commands,
`/work`, Codex, Claude, arbitrary tools, web, search, browser, research, shell,
terminal, or filesystem control.

LLM use is disabled by default. If separately enabled, it may occur only through
the North Shore package adapter for scoped parsing or reporting. Telegram
polling, gateway startup, Sheets reads and writes, Google credentials use, and
Composio execution remain disabled unless separately configured and authorized.
