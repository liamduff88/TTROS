# Brain placement and scoped fuse recovery repair
> Revisit: if ordinary Brain placement aliases or Step 6 recovery routing changes. · Last touched: 2026-08-04.

## Result

PASS.

## Pre-repair reproduction

- `business_brain:memory/company.md`, `memory/company.md`, `company`, and the
  contained absolute Brain path all returned `pointer is outside ordinary
  Hermes knowledge placement`.
- The live current Telegram executive scope was
  `session:5b45fd27ca66ca1e4dbc339c`. Its explicit scoped reset request selected
  `hermes_operator_lean`, reported `model_process_count: 1`, and returned the
  Step 6 blocker. Queue delta was zero.

## Root causes and repair

- `tools/brain_memory_mcp.py` stripped only the logical prefix, then applied an
  allowlist that omitted `memory/company.md`; it never normalized aliases or
  contained absolute paths. Normalization now resolves supported forms through
  the canonical vault containment/Markdown checks before the placement gate.
- `dashboard/backend/main.py` had no Step 6 recovery intercept, so explicit
  recovery fell through to `_operator_lean_closeout` and its paused launcher
  preflight. The exact explicit intent now runs before context assembly.
- The live scope contained unknown usage. Because unknown must never become
  zero by override, `fuse_scope_reset` starts a visible named-scope ledger epoch
  while retaining all historical rows. The global limit remains 500,000.

## Live scoped reset proof

- Reset event: `2026-08-04T16:46:12Z`.
- Current scope after reset: 0 canonical tokens, known accounting, not paused,
  reset count 1, next invocation preflight permitted.
- Comparison scope `session:claude-4872f880e4ef427e96b601bbdd7b6a2a`
  remained unchanged and paused.
- Route fields: deterministic scoped recovery, zero model processes, zero
  workers, zero queue delta, no Hermes orchestrator invocation.

## Brain transaction and recall

- Vault commit: `755a9a47b30ba6eb1a521b60fb5f3f4c5da4df9b`.
- Author: `Hermes <hermes@local.ttros>`.
- Subject: `hermes: brain-placement-fuse-repair-20260804`.
- Exact paths: `memory/company.md`,
  `operating_context/current_priorities.md`,
  `operating_context/executive_view.md`, and
  `operating_context/open_loops.md`.
- Each note has one `defect_repair_e2e_20260804` marker and matching
  `hermes_last_write` author/source/session provenance.
- Full vault validation passed every structural check.
- A fresh-process scoped pointer retrieval reopened all four notes with stable
  IDs and SHA-256 provenance and found `Synthetic production proof marker`.
- The pre-existing 21-add/10-delete human `memory/company.md` worktree change
  was preserved outside the Hermes commit and restored uncommitted.

## Zero-side-effect delta

The final idempotent `/fuse reset` proof window had exact deltas of zero for
queue items and queue hash, token-ledger lines, model invocations, worker
processes, `aos-orchestrator` invocations, promotion proposals, and external
action records. The route itself also returned all zero/no-invocation fields.

## Validation

- Step 6 verifier `all`: PASS.
- Focused One Brain, Step 6, Telegram routing, vault, and runtime drift suite:
  PASS.
- Required queue/path suite: 92 tests PASS.
- Required backend/orchestration suite: 219 tests PASS.
- Additional orchestration/Codex policy/Brain full-loop/promotion suite:
  51 tests PASS.
- Python compilation, Agentic OS diff check, and vault diff check: PASS.
- Backend/frontend/runner healthy after the scoped runtime restart.

## Protected areas

- Changed only the proven protected route file `dashboard/backend/main.py`.
- Did not change `connectors/telegram_bridge/telegram_bridge.py` or Telegram
  bridge configuration/state.
- No Agentic OS commit or push and no vault push.

## Token usage

```json
{
  "provider_total_input": "unavailable",
  "fresh_input": "unavailable",
  "cached_input": "unavailable",
  "output": "unavailable",
  "reasoning": "unavailable",
  "closing_context_percentage": "unavailable"
}
```
