# TOKEN BUDGET
> Revisit: on a Hermes/Codex release or monthly pricing check. · Last touched: 2026-07-19.

## Purpose
Visibility and retained-context drift detection, not a hard throttle. Full
mechanics live in `context/TOKEN_POLICY.md`.

## Rules

- Budget classes remain `light`, `standard`, and `heavy`; they are reporting
  labels and soft signals.
- Token fields come only from harness/API evidence. Missing fields are named
  as unavailable, never estimated.
- `input` is provider-total input. When cached input is included, derive
  `fresh_input = input - cached_input`; never add cached input to total input.
- Unrelated workbench tasks use separate fresh sessions. Resume is never
  implicit. A missing clean-session ID is a clear failure.
- At the configured 75,000-cumulative-token 50% boundary, the supervisor writes
  a compact artifact-backed receipt/handoff, ends the process, and continues
  only through a new ephemeral process from that path. Repeated cumulative
  JSONL events replace prior events and are never summed.
- Hermes Codex children and correction attempts use independently scoped fresh
  sessions. Corrections contain bounded task context, prior-result summary and
  artifact paths, Hermes feedback, and acceptance criteria only.
- Large logs, screenshots, browser evidence, and test output stay in artifacts.

## Soft warnings

- `cached_input / max(fresh_input, 1) > 20`
- `context_pct_at_close > 50`

Missing inputs to either check are unavailable, not guessed.

## Completion and cost
Every completed item retains the existing complete `token_usage` block and
done-transition refusal contract. Fresh input uses the normal input rate;
cached input uses the configured cache-read rate; output uses the output rate.
Provider-total input is never double-counted or double-priced.

## Enforcement
`context/TOKEN_POLICY.md`, `hooks/token_budget_check.md`, guarded workbench
constructors, identity files, the token ledger schema, and weekly rollup.
