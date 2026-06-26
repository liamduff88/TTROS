# Provider-neutral boundary

`src.sheets_sync_adapter` builds deterministic ordered rows.
`src.sheets_adapter` validates them against the local specs and emits generic
read/write request contracts. Payload construction, validation, dry-run, and a
future Hermes wrapper do not require Composio or any other provider SDK.

Run the default local check with:

```bash
python3 -m src.sheets_adapter --dry-run
```

The deployment may later select a Hermes-native Google/Drive/Sheets connector,
direct Google Sheets API, or optional Composio through configuration. No
provider is the default final architecture.

# Direct Google Sheets API scaffold

src.google_sheets_provider is a direct-provider scaffold behind the same
provider-neutral request boundary. It defaults to provider=none,
reads_enabled=false, writes_enabled=false, and execution_enabled=false.
It builds append payload placeholders and validates configuration, but it does
not create a Google client or call Sheets/Drive APIs. The Google SDK and
credentials are optional future deployment prerequisites, not core package
requirements.

# Optional Composio scaffold

`src.composio_sheets_writer` is only an optional provider preflight. Its local
preflight never requires Composio. CLI discovery is opt-in and has no default
path; `NORTH_SHORE_COMPOSIO_CLI_PATH` must be configured explicitly. When it is
absent, the scaffold reports `Composio CLI not configured` without failing the
generic package. It never prints configuration values, row contents, provider
output, or credentials.

All generic and provider-specific execute/write modes remain fail-closed. Live
execution requires a separate provider implementation, configuration, and
explicit approval.

# Later sync sequence

1. Read and check the existing target Sheet metadata.
2. Confirm the expected tab names against `tab_headers.json`.
3. Create missing tabs only after explicit approval; preserve existing tabs and data.
4. Append the rows from `demo_rows.json` only after explicit approval and only when demo identifiers are not already present.
5. Enable append-only `Raw_Logs` sync later, after a separate approval and validation of the JSONL-to-column mapping.

Before implementing any adapter, build rows solely from `sheet_schema.json` mappings. Validate that each emitted row has exactly the ordered columns in `tab_headers.json`. Apply the declared row policies for `Daily_Team_Summary`, `Daily_Salesperson_Scorecard`, `Followups`, and each `Missing_Data.row_sources` branch. Apply the declared `Users` display-name precedence after merging by `telegram_user_id`.

The current report model does not emit a separate follow-up time. A future adapter must therefore write a blank `followup_time` unless deterministic local code later supplies that field explicitly; it must not parse a time from `next_step`, `raw_text`, or other free text.

Before any future write, verify the target spreadsheet name, protect integration-owned tabs, confirm all sample rows remain synthetic, and run `QA_Checks`. Do not update existing rows by position; use the declared keys for idempotency checks.
