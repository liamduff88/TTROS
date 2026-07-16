# Promotion rollback report — Block 2

Status: **PASS**

The writer transaction validates containment, canonical pointer/scope, tier, marker, and target preimage hash before mutation. It journals a private preimage under the existing queue lock convention, fsyncs a same-directory temporary file, atomically replaces the target, validates the postimage, writes durable provenance, and links a run ledger only when one is supplied.

Failure injection after the real vault mutation forced post-write validation failure. The writer atomically restored and verified the exact preimage hash `a741c97bcac06b7dee5f9163bb5f8a80ab0e0aff064a19544e13d975bfae2669`, removed transient journal state, emitted failed-attempt receipt `queue/receipts/brain-promotion-d675303903a41b6c823e6d2e-failed-acda3f8425fe.json`, and left no false success reference.

Tests also inject partial write, validation, provenance receipt, and run-ledger-link failures; all restore exact bytes. Stale hash, outside-vault, `_backups`, cross-client, unauthorized field, and outside-marker attempts are rejected before mutation. Duplicate review close/invocation and the real repeated automatic invocation are idempotent.

Search replacement failure restores the previous SQLite index. Graph publication failure retains the previous published graph and records explicit failure/fallback state.

Token usage: no agent invocation
