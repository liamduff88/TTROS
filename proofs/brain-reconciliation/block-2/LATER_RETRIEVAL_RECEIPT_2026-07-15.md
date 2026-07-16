# Independent later retrieval receipt — Block 2

Status: **PASS**

Original deterministic write ID: `d675303903a41b6c823e6d2e`.

After the writer invocation ended and live search reindex completed, two new Python executions independently instantiated the registry and loader:

- PID 3732 retrieved `business_brain:index/MEMORY_INDEX.md` through an explicit pointer.
- PID 3733 retrieved the same durable note through exact scoped search for the promoted text.

Both actual opens recorded stable note `ttros-brain-memory-index`, scope `global`, postimage hash `afcd3d1644453f763158d2b0b59430299abfd560a71e452a4d27e693b36379b7`, and the correct distinct route. Both verified the promoted content in the authoritative opened note. No model was invoked.

Raw receipts: `LATER_RETRIEVAL_POINTER_RAW_2026-07-15.json` and `LATER_RETRIEVAL_SEARCH_RAW_2026-07-15.json`.

Token usage: no agent invocation
