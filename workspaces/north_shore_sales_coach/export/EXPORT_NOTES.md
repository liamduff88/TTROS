# Export notes

Copy this isolated workspace as one unit. The package has no dependency on the existing Agentic OS Telegram bridge, Hermes state, sessions, vaults, MCP/plugin state, Composio, or model-provider state.

For a future Hermes-on-Orgo deployment, host or wrap this workspace while
providing its own Telegram token/config, role map, local data, and Sheets
connector configuration through deployment-managed settings. Preserve direct
bot isolation and the command whitelist; never expose general Hermes OS,
filesystem, shell, or agent commands. Runtime-generated `data/*.jsonl` and
`logs/*` should be mounted as persistent writable storage and excluded from
source exports.

`data/local_state.json` is also persistent runtime state. It contains local
group registration, Telegram display profiles, invite records, redeemed local
user roles, and the Salespeople roster. Preserve it when moving an active bot;
omit or reset it only for a clean demo export.

The Hermes wrapper is a containment host, not a capability bridge. It must route
only to this package's local intent boundary and must not forward Telegram text
to general Hermes, `/work`, Codex, Claude, browser/search, arbitrary tools, or
operator commands. Keep the North Shore Telegram credentials, role map,
persistent store, dashboard URL, and Sheets connector settings in a dedicated
deployment namespace.

The Sheets request boundary is provider-neutral. Select a Hermes-native
Google/Drive/Sheets connector, direct Google Sheets API, or optional Composio
through deployment configuration. Do not bundle Composio as a required runtime
dependency or assume it is the final architecture.

Phase 1 intentionally requires integration work before live use: Telegram transport, deployment secret injection, operational logging, backups, and adapter implementations are absent.
