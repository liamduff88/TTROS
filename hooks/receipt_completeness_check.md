# hooks/receipt_completeness_check.md
> Revisit: on a queue completion-contract, receipt, or token-sidecar schema change. · Last touched: 2026-07-31.

## Event
Fires inside `tools/aos-queue.py:finalize_done()` for every real transition to
`done`, before the receipt sidecar or run/token ledger rows are written.

## Check

- A root-relative, existing regular receipt file is required.
- The queue item must retain its definition of done, allowed actions, and stop
  conditions.
- A Markdown receipt must start with `PASS` and include a substantive
  `Validation:` note. A JSON receipt must carry structured validation,
  verification, or evidence references.
- The structured completeness record must include lane, requested/resolved
  profile, requested/confirmed model, token usage, receipt/artifact paths, the
  completion contract, and a deterministic hash of that contract.
- The record must pass `queue/schemas/receipt_completeness.schema.json`.

## On block
Raises `QueueError` and refuses the done-transition. No token sidecar or
run/token ledger row is written. The queue lifecycle's pre-existing durable
transition intent remains retryable after the receipt is corrected.

## Enforces
`rules/always.md` #1 and #8 · `rules/completion_contract.md`.

## Status
Wired at the shared `finalize_done()` lifecycle point. Covered by focused unit
tests in `tests/test_aos_queue.py`.
