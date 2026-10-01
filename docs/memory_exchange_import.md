# TTROS Memory Exchange importer
> Revisit: when the frozen v2 manifest or transport changes. · Last touched: 2026-10-01.

The importer accepts `directory-v1` package folders immediately beneath a materialized `03_READY_FOR_TTROS` directory. `--dry-run --package PATH` validates one package and reports planned Brain paths without modifying the Brain, receipt ledger, search index, Graphify, or Drive. `--ready PATH` processes immediate children only; combine `--ready PATH --package PATH/ID` to select exactly one ready package. The default ready path can come from `TTROS_MEMORY_READY`.

The local directory transport is the boundary for a synced or materialized Drive folder. It exposes list, materialize, success move, and rejection move operations. `--move` enables folder moves after import; omitting it leaves every package in place. Set `--source`, `--ready`, `--imported`, and `--rejected` to the corresponding configured folders. The source folder is configuration only; the importer consumes ready packages. The importer contains no provider IDs or model calls.

The frozen v2 manifest declares `source_count` and `sources[]`, `output_count` and `outputs[]`, and `requires_human_review`. Each package file and output uses `size_bytes`; each output uses `package_path`, source IDs, and `target.suggested_relative_path`. The importer checks counts, references, hashes, and exact target paths before writing. Canonical base hashes and refs live inside `target`.

`historical_record` maps `historical/<name>.md` to `business_brain:sources/historical_calls/<name>.md`. `canonical_replace` maps `canonical/<name>.md` to `business_brain:memory/<name>.md` and requires `canonical_changes`, complete comparison, matching `canonical_ref`, and an exact base hash. Unknown operations fail closed. New historical notes are indexed by the existing indexer one target at a time, preserving unrelated search entries even when an unrelated full scan is blocked. Graphify refresh runs only for pointers allowed by the existing Graphify registry.

The prepared systemd unit reads `%h/.config/ttros-memory-exchange.env` with `TTROS_MEMORY_READY`, `TTROS_MEMORY_IMPORTED`, and `TTROS_MEMORY_REJECTED`. Install and enable it only after the operator has authorized live import and transport moves. It has not been installed or started by this build.
