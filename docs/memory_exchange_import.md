# TTROS Memory Exchange importer
> Revisit: when the frozen v2 manifest or transport changes. · Last touched: 2026-10-03.

The importer accepts `directory-v1` package folders immediately beneath a materialized `03_READY_FOR_TTROS` directory. `--dry-run --package PATH` validates one package and reports planned Brain paths without modifying the Brain, receipt ledger, search index, Graphify, or Drive. `--ready PATH` processes immediate children only; combine `--ready PATH --package PATH/ID` to select exactly one ready package. The default ready path can come from `TTROS_MEMORY_READY`.

The local directory transport is the boundary for a synced or materialized Drive folder. It exposes list, materialize, success move, and rejection move operations. `--move` enables folder moves after import; omitting it leaves every package in place. Set `--source`, `--ready`, `--imported`, and `--rejected` to the corresponding configured folders. The source folder is configuration only; the importer consumes ready packages. The importer contains no provider IDs or model calls.

The frozen v2 manifest declares `source_count` and `sources[]`, `output_count` and `outputs[]`, and `requires_human_review`. Each package file and output uses `size_bytes`; each output uses `package_path`, source IDs, and `target.suggested_relative_path`. The importer checks counts, references, hashes, and exact target paths before writing. Canonical base hashes and refs live inside `target`.

`historical_record` maps `historical/<name>.md` to `business_brain:sources/historical_calls/<name>.md`. `canonical_replace` maps `canonical/<name>.md` to `business_brain:memory/<name>.md` and requires `canonical_changes`, complete comparison, matching `canonical_ref`, and an exact base hash. Unknown operations fail closed. New historical notes are indexed by the existing indexer one target at a time, preserving unrelated search entries even when an unrelated full scan is blocked. Graphify refresh runs only for pointers allowed by the existing Graphify registry.

The installed systemd unit reads `%h/.config/ttros-memory-exchange.env` with `TTROS_MEMORY_READY`, `TTROS_MEMORY_IMPORTED`, and `TTROS_MEMORY_REJECTED`. Stage 2 enables its 15-minute timer for `CHECKPOINT.json` packages only. Ordinary ingest packages remain available to the existing manual importer.

## Shared Brain Stage 2 checkpoint handoff

When ChatGPT has no direct Brain connector, it places one typed package immediately under `TTROS Memory Exchange/03_READY_FOR_TTROS/`. The package contains only `CHECKPOINT.json`:

```json
{
  "schema_version": "shared-brain-checkpoint-v1",
  "operation": "checkpoint",
  "workstream_id": "example-workstream",
  "expected_version": 0,
  "fields": {
    "goal": "Continue the agreed work",
    "done": "First bounded step",
    "decisions": "Use the current approach",
    "work_product_reference": "https://example.com/result",
    "next_action": "Take the next step",
    "open_questions": "None"
  }
}
```

The 15-minute systemd timer invokes the importer with `--checkpoint-only`, leaving all non-checkpoint ready packages untouched. A missing DriveFS mount yields no ready packages and does not prevent direct checkpoints. The existing `memory_exchange_import.py` consumer dispatches this type to the same `shared_brain_checkpoint.checkpoint()` function used by the HTTP and David stdio tools. It preserves the frozen v2 ingest manifest path unchanged. With `TTROS_SHARED_BRAIN_WRITE` off, a checkpoint package stays in the ready folder and is not consumed or moved. The consumer sets ChatGPT Drive-channel attribution itself; values supplied in the package cannot override it. Stale versions and invalid fields are rejected. The package is moved to the existing imported or rejected folder by the existing transport. The current note is projected to `TTROS Memory Exchange/06_WORKSTREAMS_READ/<workstream_id>.md` for ChatGPT to read. That folder is a copy of working state; the Brain note is authoritative. It is not a durable submit, Git commit or memory import.
