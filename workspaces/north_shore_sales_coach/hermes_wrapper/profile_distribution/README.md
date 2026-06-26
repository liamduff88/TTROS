# North Shore Sales Coach profile distribution

This directory is the install source for the locked-down
`north-shore-sales-coach` Hermes profile distribution. It contains no inherited
profile state and is intentionally separate from the package root.

The profile preserves this route:

```text
Salesperson Telegram DM
-> dedicated North Shore Sales Coach bot
-> direct North Shore runner / command handler
-> north_shore_sales_coach package
-> deterministic local handling first
-> optional package-local LLM adapter for scoped parsing/reporting only
-> local JSONL
-> provider-neutral Sheets adapter
-> selected Google Sheets connector later
-> Ryan admin group and dashboard/report tabs
```

All transports, providers, LLM use, external Sheets execution, MCP servers,
general tools, and service startup are disabled by default. Unknown input stays
inside package-local safe help and is never forwarded to general Hermes or
Agentic OS.

## Readiness validation

From the North Shore package root:

```bash
PYTHONDONTWRITEBYTECODE=1 NORTH_SHORE_PACKAGE_ROOT="/absolute/path/to/north_shore_sales_coach" \
  python3 hermes_wrapper/profile_distribution/scripts/validate_distribution_readiness.py
```

After validation, an operator may explicitly install this directory with
`hermes profile install SOURCE`. Validation never performs installation or
starts a service.
