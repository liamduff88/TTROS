# Block 3 metadata leakage proof
> Expires: when capture projection, search, Graphify, receipt, or dashboard serialization changes. · Last touched: 2026-07-15.

Result: **PASS**.

The typed projection accepts exactly nine fields: safe record ID, scoped
reference, client scope, linked item ID, subject classification, timestamp,
source type, triage state, and proposal state. Unknown fields fail validation.
Queue proposal nested objects are closed-schema allowlists.

Synthetic sentinel hashes (raw values deliberately omitted):

- body: `f0f3fb1758e28f84d66a19200eeee68b29206bd14c0fc30fb39c94add2aee1cd`
- thread: `03c9a6a3c71f0d35280a238bdb11f523ce0e3e158992de89dc83ba7b3b26d7f2`
- attachment: `884408ae5a55f631824fc44ae599f8c3688bf474c55e430953d805ae878a05ff`

Direct results after real projection:

- Git tracked content: 0 hits for each sentinel;
- repository queue/receipt/dashboard/search/proof surfaces: 0 hits each;
- Business Brain and Pass 10 Graphify trees: 0 hits each;
- SQLite `path/title/tags/snippet/body`: 0 hits each;
- capture SQLite rows: 1; body empty; generated title/snippet only;
- scoped public search API: 1 client-A result, no `body` field;
- dashboard payloads: 0 sentinel hits;
- capture graph: 1 metadata node, 1 safe proposal edge, no raw-content keys;
- queue proposals, receipts, token/run rows, and promotion candidates: 0 hits.

The existing Business Brain graph files and all Pass 10 graphs/receipts stayed
byte-identical. Raw capture is `never_promote`; a communications fact is
`liam_review_required` and not writable.

Token usage: no agent invocation.
