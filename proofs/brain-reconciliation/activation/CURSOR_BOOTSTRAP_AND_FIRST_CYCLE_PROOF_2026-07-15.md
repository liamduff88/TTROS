# Cursor bootstrap and first live cycle proof
> Expires: when the Gmail cursor or bootstrap transaction contract changes. · Last touched: 2026-07-15.

Result: **PASS after one safe repair replay**.

Observed bootstrap boundary: `2026-07-14T22:01:41.870863Z`, less than 24 hours before the successful cycle. Scope was inbound `INBOX`, payload disabled, spam/trash excluded, maximum 100.

The initial attempt read 23 bounded metadata candidates and produced 22 authorized inbound envelopes. It durably appended 22 raw/processing records, deterministically classified one noise item, and routed 21 unresolved identities to existing `needs_input` without content opening. Publication then failed because unresolved metadata was passed to Graphify instead of being skipped. The cursor was restored to its prior absent state. An additive correction receipt records the exact 22 persisted rows from processing timestamps; the original receipt was not rewritten.

Repair: Graphify publication now applies the same fail-closed scope gate as search. Unresolved metadata remains in the owner-only runtime and does not enter search or Graphify. The successful replay:

- received the same 23 bounded metadata candidates;
- accepted 22 inbound envelopes;
- deduplicated all 22 immutable raw records;
- created no duplicate queue, receipt, run-ledger, or token-ledger record;
- published the Gmail history checkpoint only after raw and processing state were durable;
- recorded one deterministic discard and 21 unresolved fail-closed routes;
- made zero Stage 2 classifier calls;
- opened no body, thread, attachment, Brain note, search result, or Graphify target for unresolved items;
- published search metadata-only and Graphify scoped metadata-only output.

Immediate history replay returned zero additions and an identical cursor hash. Later scheduled cycles advanced the cursor only for new inbound-INBOX metadata additions. At the 23:15 automatic cycle, the cursor value hash recorded in the receipt was `53ea9db59703ed2bd081761aef36121c06a256cef4df3f0c950a08eb6cb3a3a9`.

Current production totals at proof freeze: 24 immutable live raw metadata records, 23 live `needs_input` queue items, zero human-review proposals, zero content opens, and zero Gmail mutations.

Token usage: no agent invocation.
