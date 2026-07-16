# Live metadata leakage proof
> Expires: when capture serialization, queue, search, Graphify, or dashboard contracts change. · Last touched: 2026-07-15.

Result: **PASS**.

At proof freeze:

- 23 live queue proposals were all `needs_input` and visible through existing Needs Me behavior;
- live proposal/receipt email-pattern matches: zero;
- forbidden live proposal keys (`body`, `body_preview`, `thread_text`, `attachments`, `sender`, raw headers, account/connection IDs, provider source IDs): zero;
- 24 immutable live raw records contained zero body/thread/attachment keys;
- live raw records remained inside ignored owner-only runtime storage;
- search capture rows: one accepted scoped metadata row, body empty; unresolved live rows were rejected before indexing;
- search API serialized no `body` key;
- Graphify capture graph: one scoped metadata node, one safe work-item edge, `raw_content_fields_serializable=false`, zero forbidden keys;
- unresolved live rows were rejected before Graphify publication;
- dashboard raw preview returned unavailable because capture runtime is outside allowlisted artifact roots;
- no body/thread/attachment action appears in any production receipt;
- attachments opened: zero; body/thread reads: zero; Gmail mutations: zero; external actions: zero.

No live subject, address, account/connection ID, provider message/thread ID, body, thread text, attachment name, or sensitive excerpt is present in proofs, queue proposals, receipts, ledgers, search, Graphify, dashboard payloads, promotion candidates, or Pass 10.

Token usage: no agent invocation.
