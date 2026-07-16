# Phase 6B observation window start
> Expires: after Liam completes or resets the observation window. · Last touched: 2026-07-15.

Result: **STARTED — not complete**.

- Start UTC: `2026-07-15T22:06:04.287278Z`.
- Start Europe/Dublin: `2026-07-15T23:06:04.287278+01:00`.
- Start condition met: successful directly observed first cycle, enabled recurring Hermes job, and durable activation decision/control record.
- Existing rollup mechanism: `queue/rollups/week-2026-W29.json`, additive top-level `capture` block; `queue/rollups/index.json` includes `2026-W29`.
- Metrics contain counts and exact token totals only; no addresses, subjects, message/thread IDs, or content.
- At the automatic 23:15 proof freeze: 10 poll/diagnostic attempts, four successful polls, one processing failure followed by safe replay, one cursor replay, one non-overlap event, one kill-switch event, zero isolation incidents, zero false-positive findings, and zero false-negative findings.
- Stage 2 exact tokens: input 0, output 0. Stage 3 exact tokens: input 0, output 0. No model was invoked.
- Whitelist entries: zero. Whitelist active: false.

The two-week period has only begun. No whitelist conclusion is claimed.

Token usage: no agent invocation.
