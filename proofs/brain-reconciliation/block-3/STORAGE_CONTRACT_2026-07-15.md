# Block 3 capture storage contract
> Expires: when live capture is activated or the retention/backup contract changes. · Last touched: 2026-07-15.

Result: **PASS**.

- Canonical runtime: `/home/liam/agentic-os-live/capture/runtime/`.
- Authority: Linux-native and inside the canonical repository root, but ignored by Git.
- Layout: provider cursor/processing state plus scope-partitioned raw, derived,
  fixture, metadata, and operational-receipt records. Raw records/evidence use
  append-only file descriptors and are never moved or rewritten by triage.
- Modes: every runtime directory `0700`; every runtime file `0600`. The live
  fixture permission audit reported zero exceptions after capture and replay.
- Retention: retained until a separately approved retention decision; no
  deletion, compaction, movement, or scheduled cleanup exists.
- Exclusions: `git check-ignore` resolved to `.gitignore:91`; tracked runtime
  files = 0; the dashboard artifact API rejected the raw evidence path because
  it is outside the allowlisted roots; ordinary index traversal rejects
  `capture/runtime`; promotion class `raw_communications` returned
  `never_promote`, writable false.
- Search proof: real reindex published 701 rows and exactly one allowlisted
  `capture_metadata` row. Its `body` is empty.
- Graphify proof: metadata projection lives beside the existing Business Brain
  graph as `capture_evidence.graph.json`; the accepted Brain graph's three
  published hashes are unchanged. Pass 10 remains separate.
- Backup proof: the existing rsync contract dry-run listed 27 capture-runtime
  entries. A strict disposable execution copied 13 runtime files; raw-evidence
  source/recovery hashes both equal
  `fdf2aed51003b6756d986b711fb49e89d1e1177ac48ee5291f10b4f61a3f24d2`,
  and recovered modes remained `0700/0600`.

The first disposable backup attempt used an incomplete synthetic `AOS_ROOT`
without `tools/aos_paths.py`; the backup correctly refused it. The rerun added
the authority helper, enabled strict shell failure propagation, and passed.

Token usage: no agent invocation.
