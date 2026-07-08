# goals/queue_receipts_visible.goal.md
> Revisit: on a queue schema change or a failed daily check. · Last touched: 2026-07-07.

predicate: every done-transition in queue/run_ledger.jsonl has a matching
  receipt path that exists on disk
born: 2026-07-07
source: Batch 6 queue scaffold + Batch 7 goal build
status: satisfied
last-pass: 2026-07-07
on-violation: wake Liam. Do not auto-fix — a missing receipt means the
  work may not actually be done, not just unlogged.
retire-when: the receipt model is replaced by something else. Retirement
  is a human decision, logged.

## Why this goal exists
Done without proof is a claim, not a fact. Every queue item that reaches
`status: done` in `run_ledger.jsonl` must point at a receipt file — the
one piece of evidence a human or a fresh-context verifier can check
without trusting the agent's own report.

## Enforces
`rules/completion_contract.md` · `context/OPERATOR_CONTRACT.md` ·
`run_ledger_schema.json`.
