# hooks/token_budget_check.md
> Revisit: when ledger schema, provider usage, pricing, or fuse thresholds change. · Last touched: 2026-08-04.

## Event

Runs before and after every protected model invocation and during queue
process-exit reconciliation.

## Before call

- Require typed assembled context at the model boundary.
- Resolve the one cost dial (scope override → global → `standard`).
- Read the named work-item/session state from `queue/token_ledger.jsonl`.
- Block only a known 500,000-token pause or unknown/corrupt accounting.

## After call

- Record provider, actual model, exact exposed token fields, canonical total,
  price/unpriced state, dial source and scope.
- Emit newly crossed 50/80/100 events once by invocation identity.
- At 100%, preserve state and block the next call; never claim the running call
  was interrupted.

The 50/80 events do not change context, model, compaction, or execution.
Automatic compaction remains independent session hygiene. Deterministic
operations record zero model invocations.

## Enforces

`context/TOKEN_POLICY.md`, `rules/always.md` #1/#5, exact-or-unknown
accounting, and the single Step 6 control contract.
