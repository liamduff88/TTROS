# Block 3 cursor recovery and idempotency proof
> Expires: when the Gmail delta or durable writer contract changes. · Last touched: 2026-07-15.

Result: **PASS**.

Implemented order:

`read delta → validate envelope → deduplicate → append immutable raw → append processing state → publish cursor`.

Focused failure injections proved:

- before raw append: zero raw records, zero cursor movement;
- after raw append: replay produced one raw and one processing record;
- after processing: replay retained one raw and one processing record;
- during cursor publication: prior cursor `20` remained usable, then replay
  advanced to `30`;
- repeated identical and out-of-order history: deterministic order and no
  duplicate raw records;
- kill switch: provider activity count zero and no cursor/state mutation;
- backward cursor: rejected with the prior checkpoint preserved;
- live adapter: no executor activity without non-live override removal, live
  control state, and a separate exact activation record.

The real fixture sorted history entries `101/102`, published cursor `102`,
wrote two raw records, and reported `replay_new_raw_count=0`. Repeated proposer
execution created no duplicate queue items or ledger rows.

Token usage: no agent invocation.
