# Capture runtime contract
> Revisit: before live capture activation or when retention/backup roots change. · Last touched: 2026-07-15.

`capture/runtime/` is the single Linux-authoritative communications-capture
runtime. It is Git-ignored, excluded from dashboard previews and ordinary
search traversal, and outside Business Brain, Graphify source, and promotion
roots. The existing Linux backup copies it with its owner-only modes.

The runtime is partitioned into provider state and scope-owned evidence. Raw
records and fixture evidence are append-only; processing, triage, proposal,
metadata projection, and operational receipt records reference immutable raw
record IDs. Cursor files are atomically replaced only after raw and processing
records are durable. Directories are mode `0700`; runtime files are mode
`0600`.

Retention boundary: raw evidence is retained until a separately approved
client/data-retention decision authorizes deletion. Block 3 performs no
automatic deletion, compaction, movement, or scheduled cleanup.

Live Gmail capture is disabled by default and requires all three independent
conditions: the production `tools/aos_capture_live.py poll` entry point, a
separate activation record, and an untripped kill switch. Phase 6B schedules
that exact entry point through the existing Hermes cron machinery. It is
single-instance locked, bounded by a 180-second scheduler timeout, and exposes
only profile, INBOX message-addition history, metadata-only bootstrap, and
single-message metadata actions through the existing Composio adapter.
