# Hermes wrapper readiness

This directory is a package-local contract for a future Hermes wrapper. It is
not an installed Hermes workspace and contains no Hermes runtime state. The
wrapper must invoke only the North Shore entrypoints declared in
`hermes_workspace_manifest.json`; it must not forward messages or commands to a
general Hermes agent.

The direct North Shore Telegram bot remains isolated and package-owned. A
future host may start that transport explicitly, but wrapper installation must
not route it through the Agentic OS Telegram bridge or start live polling as an
installation or validation step.

All basic commands, authorization, local routing, reporting, and configuration
validation remain deterministic, local, and zero-token. Sheets integration is
provider-neutral: a deployment may later choose Hermes native, direct Google
API, or optional Composio. Provider selection does not authorize reads, writes,
or execution.

This scaffold deliberately contains no `.hermes`, sessions, skills, ZPC, MCP,
OpenRouter, vault, runtime cache, generated credentials, or old-host paths.
