# Search reindex and preservation report — Block 2

Status: **PASS**

The index schema adds `client_scope` and an index on that field. Business Brain scope is assigned from the registry before note content is opened; unowned/denied identities are skipped. Retrieval requires explicit scope and applies the scope predicate in SQL before result objects or snippets are constructed. Existing source/kind/tag filters remain available; non-client technical searches use explicit global scope.

After the real write, the live DB/WAL/SHM family was snapshotted in `SEARCH_DB_PRE_REINDEX_AFTER_WRITE_2026-07-15.sha256`. Successful live scan indexed 672 and skipped 72 with zero failures and atomically published a replacement. The promoted pointer is present under global scope.

An injected after-publication failure returned `published: false`, `retained_previous: true`; the exact promoted query returned the same path/count/rank before and after. The previous usable SQLite database was atomically restored. Successful replacement finalized SQLite in DELETE journal mode, so prior transient WAL/SHM files are intentionally absent rather than corrupt or lost state.

Token usage: no agent invocation
