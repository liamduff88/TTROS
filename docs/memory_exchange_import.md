# TTROS Memory Exchange importer
> Revisit: when the frozen v2 manifest or transport changes. · Last touched: 2026-10-07.

The importer accepts `directory-v1` package folders immediately beneath a materialized `03_READY_FOR_TTROS` directory. `--dry-run --package PATH` validates one package and reports planned Brain paths without modifying the Brain, receipt ledger, search index, Graphify, or Drive. `--ready PATH` processes immediate children only; combine `--ready PATH --package PATH/ID` to select exactly one ready package. The default ready path can come from `TTROS_MEMORY_READY`.

The local directory transport is the boundary for a synced or materialized Drive folder. It exposes list, materialize, success move, and rejection move operations. `--move` enables folder moves after import; omitting it leaves every package in place. Set `--source`, `--ready`, `--imported`, and `--rejected` to the corresponding configured folders. The source folder is configuration only; the importer consumes ready packages. The importer contains no provider IDs or model calls.

The frozen v2 manifest declares `source_count` and `sources[]`, `output_count` and `outputs[]`, and `requires_human_review`. Each package file and output uses `size_bytes`; each output uses `package_path`, source IDs, and `target.suggested_relative_path`. The importer checks counts, references, hashes, and exact target paths before writing. Canonical base hashes and refs live inside `target`.

`historical_record` maps `historical/<name>.md` to `business_brain:sources/historical_calls/<name>.md`. `canonical_replace` maps `canonical/<name>.md` to `business_brain:memory/<name>.md` and requires `canonical_changes`, complete comparison, matching `canonical_ref`, and an exact base hash. Unknown operations fail closed. New historical notes are indexed by the existing indexer one target at a time, preserving unrelated search entries even when an unrelated full scan is blocked. Every imported note must be inside the existing Graphify registry scope (global `sources/historical_calls/` is a Graphify path prefix, matching global Search). It is deliberately not a Brain pointer prefix: that list is also the dashboard save gate and the promotion target scope, so a prefix would make every imported note writable. Graph queries return a note only when it is also in Brain pointer scope, so a newly imported note appears in Search, the entity index and the published graph, and in graph query results once its pointer is listed in global `brain_pointers`; the importer then checks each note's Brain hash against the published source manifest and graph node and records per-output coverage. An out-of-scope note or a hash mismatch leaves the package `refresh_pending` in READY, and the next pass retries only the refresh. A ledger row with Graphify `not_applicable` does not count as already imported.

Brain transactions stamp provenance, so a written note differs from its package bytes. The importer records `written_sha256` for each output after writing; a rerun of the same package is `already_imported` only while those notes are unchanged, and a later edit rejects the rerun instead of being called already present. Ledger rows from before that field existed keep their earlier trust.

The installed systemd unit reads `%h/.config/ttros-memory-exchange.env` with `TTROS_MEMORY_READY`, `TTROS_MEMORY_IMPORTED`, and `TTROS_MEMORY_REJECTED`. Its 2-minute timer consumes every ready package type: `CHECKPOINT.json`, `SUBMIT.json`, and full `INGEST_MANIFEST.json` packages (`--typed-only` remains available but the timer no longer passes it). After moving a full package, the importer writes `<package>.IMPORT_RECEIPT.json` beside it in IMPORTED or REJECTED: a projection of its ledger row with the manifest's sources, never inside the hashed packet. The local ledger stays authoritative. Each pass republishes a missing or changed receipt for imported packages from matching ledger rows, without repeating import work, and leaves unchanged receipts untouched. Typed packages get no receipt file.

Anything placed in READY is imported unattended. The superseded 2026-10-06 batch (nine `INGEST_20261006T222200Z_*` packages) was moved, byte-verified, to `07_WORKSTREAM_ARTIFACTS/memory-ingest-attachments-20261006/held_ready_packages_20261007/` before full consumption was enabled; `HOLD_RECORD.json` there lists their hashes. Moving one back to READY imports it.

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

The 2-minute systemd timer processes checkpoint packages alongside the other ready types. A missing DriveFS mount yields no ready packages and does not prevent direct checkpoints. The existing `memory_exchange_import.py` consumer dispatches this type to the same `shared_brain_checkpoint.checkpoint()` function used by the HTTP and David stdio tools. It preserves the frozen v2 ingest manifest path unchanged. With `TTROS_SHARED_BRAIN_WRITE` off, a checkpoint package stays in the ready folder and is not consumed or moved. The consumer sets ChatGPT Drive-channel attribution itself; values supplied in the package cannot override it. Stale versions and invalid fields are rejected. The package is moved to the existing imported or rejected folder by the existing transport. The current note is projected to `TTROS Memory Exchange/06_WORKSTREAMS_READ/<workstream_id>.md` for ChatGPT to read. That folder is a copy of working state; the Brain note is authoritative. It is not a durable submit, Git commit or memory import.

## Large working artifacts (Stage 4 repair, 2026-10-04)

The note stays capped at 2,500 characters. An unfinished work product too large for it (a prompt, research package, draft, plan or report) lives as a working artifact at `TTROS Memory Exchange/07_WORKSTREAM_ARTIFACTS/<workstream_id>/<name>`, and the note's `work_product_reference` is `artifact:<workstream_id>/<name>`. Names are lowercase letters, digits, `-`, `_` and `.`, ending `.md` or `.txt`; content is at most 20,000 characters.

- Direct clients (Claude, David) pass `work_product: {name, content}` to the existing `checkpoint`. Under the workstream lock and after the version check, TTROS writes the file, then the note. A stale version, an over-size note or unavailable Drive storage writes neither.
- ChatGPT on the Drive handoff saves the file there itself, then sends an ordinary `CHECKPOINT.json` whose `work_product_reference` names it. The package format is unchanged; TTROS refuses a reference to a missing file or to another workstream's artifact.
- `resume` of that workstream returns the artifact (bounded to 20,000 characters) with the note, so the receiver opens it before continuing. ChatGPT reads the same file in Drive.

Artifacts are working storage. They are not Brain content, not indexed and not committed, and `submit` does not accept them as source references. A finished result still goes through `submit`.
