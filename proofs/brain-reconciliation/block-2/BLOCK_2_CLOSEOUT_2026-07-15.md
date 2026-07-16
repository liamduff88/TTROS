# TTROS Business Brain reconciliation — Block 2 closeout

## PASS

Checkpoint 2 is complete. Block 3 has not begun.

## Files touched

The exact repository, vault, Graphify, queue/receipt/search, proof, accepted Block 1, and unrelated-dirty classifications are in `FILES_TOUCHED_2026-07-15.txt`. The only vault mutation is the authorized marker section in `business_brain:index/MEMORY_INDEX.md`. The only proof queue item is disposable `AOS-2026-0091`, closed blocked/rejected without acceptance or write.

## Validation

Commands and results:

- `python3 -m unittest tests.test_business_brain_scope tests.test_business_brain_context tests.test_business_brain_search_scope tests.test_business_brain_graph tests.test_business_brain_promotion tests.test_business_brain_full_loop tests.test_aos_search tests.test_business_brain tests.test_business_brain_vault tests.test_dashboard_memory` — 36 passed before real mutation; final affected run 108 passed after all repairs.
- `python3 -m unittest tests.test_business_brain_scope tests.test_business_brain_context tests.test_business_brain_search_scope tests.test_business_brain_graph tests.test_business_brain_promotion tests.test_business_brain_full_loop tests.test_aos_search tests.test_business_brain tests.test_business_brain_vault tests.test_dashboard_memory tests.test_aos_queue tests.test_graphify_pass10` — 108 passed.
- `python3 -m unittest discover -s tests -p 'test*.py'` — 172 passed.
- `./dashboard/backend/.venv/bin/python -m unittest discover -s dashboard/backend -p 'test*.py'` — 132 passed, 0 failures/errors/skips.
- `npm test -- --run` in `dashboard/frontend` — 21/21 passed.
- `npm run build` in `dashboard/frontend` — production build passed, 1,647 modules transformed.
- `python3 tools/validate_business_brain.py --vault '/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain' --report proofs/brain-reconciliation/block-2/VAULT_STRUCTURE_AFTER_2026-07-15.json` — PASS: 19 canonical notes, 19 unique IDs, zero broken links, backups excluded.
- `bash loop/verify-goals.sh` — the same two historical/unrelated finding classes before and after; classification in `GOAL_VERIFIER_CLASSIFICATION_2026-07-15.md`.
- Real API/browser proof used local ports 8010/3010, captured `DASHBOARD_MEMORY_API_LIVE_2026-07-15.json`, `DASHBOARD_SCOPED_SEARCH_API_LIVE_2026-07-15.json`, and `TTROS_BLOCK_2_MEMORY_BOARD_2026-07-15.png`; services were restored stopped.

Isolation is green for two synthetic clients plus global, including no-open sentinels. Review-tier routing/no-write and never-promote refusal are real queue/policy proofs. The real automatic write changed preimage `a741c97bcac06b7dee5f9163bb5f8a80ab0e0aff064a19544e13d975bfae2669` to postimage `afcd3d1644453f763158d2b0b59430299abfd560a71e452a4d27e693b36379b7`; repeat invocation was an idempotent duplicate with one marker. Injected post-mutation failure restored the exact preimage. Live reindex published and an injected replacement failure retained the previous usable index. Fresh processes 3732 and 3733 independently retrieved by pointer and exact scoped search with actual-read provenance. Fresh process 3832 proved Graphify-assisted scoped selection. The graph is fresh, repeat publication unchanged, and injected failure preserved its published artifacts.

## Root cause / behavior changed

Before Block 2, no single executable authority bound client identity to exact Brain, search, graph, evidence, receipt, and promotion identities; search and downstream provenance could not prove scope-before-load or actual reads; promotion policy had no fully recoverable writer.

The schema-backed registry in `context/client_scope_registry.json` is now the shared default-deny authority. Every relevant boundary validates declared scope and exact source before access. The loader follows pointer → conditional Graphify → exact search → direct fallback and records only successfully opened sources in `brain_context_used`. Classification treats ambiguity as knowledge-sensitive/`needs_input`; technical-only is affirmative.

Only `generated_marker_section` is automatic, on one exact global index target/marker. Review classes route to `human_review`; forbidden classes refuse; unknown classes route to review. The atomic writer checks scope/tier/preimage/marker, writes by same-directory atomic replace, validates, records provenance, and rolls back exact bytes on any post-mutation failure. The real write added useful accepted-checkpoint and transaction-proof links inside the machine-owned outcome-index marker without changing the human preimage. Reindex and independent retrieval closed the durable loop.

The dashboard now truthfully reports promotion machinery operational, the one enabled automatic class, review route, and latest safe receipt without raw note bodies/preimages/diffs.

## Protected areas

The four unrelated dirty files are hash-identical to preflight. Protected metadata, immutable queue items, vault backups, run/token/goal ledgers, and Pass 10 intake/repo graphs/receipts are unchanged. Historical queue/receipt lines were not rewritten. No live connector, Gmail, Calendar, message, attachment, protected workspace, or protected note body was read. No capture/job/external action/deploy/commit/push occurred. Block 3 is excluded.

## Blockers

None.

## Next action

Checkpoint 2 only: Liam reviews this complete Block 2 closeout. Acceptance authorizes Block 3.

Token usage: unavailable from current CLI output.
