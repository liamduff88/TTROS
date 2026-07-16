# Block 1 preservation and collision report

Status: PASS
Date: 2026-07-15
Token usage: unavailable from current CLI output.

## Collision/preflight

- HEAD, main, and origin/main were all `8b26010772196c448e01fae4dacfbe4ef9106c4b`; no later committed delta required reconciliation.
- Dashboard backend/frontend/runner, Hermes, Obsidian, and Graphify had no overlapping active writer before mutation.
- The one nonterminal queue claim (`AOS-2026-0020`) was stale and did not overlap Block 1 surfaces.
- Services started only for real local proof and were returned to their original stopped state. Final listeners on 3010/8010: zero.

## Protected and unrelated state

- Path-level metadata for `workspaces/north_shore_sales_coach/`, `connectors/telegram_bridge/`, and the three protected route files is byte-for-byte identical to the before record. Their interiors were not inspected.
- The four pre-existing dirty paths—`decisions/DECISIONS.md`, `tests/test_aos_orchestration.py`, `tools/aos-linux-runtime.sh`, and `tests/test_aos_dashboard_cleanup.py`—retain exactly their before-task SHA-256 hashes.
- The two adopted authority documents and their Zone.Identifier streams were pre-existing untracked files and were read/preserved, not claimed as Block 1 changes.
- `AOS-2026-0071`, `AOS-2026-0073`, `AOS-2026-0074`, and `AOS-2026-0075` were not mutated.
- Queue work items, run/token/goal ledgers, orchestration events, notifications, rollups, and the live search database/WAL/SHM are byte-identical. Two documentation prompts changed intentionally: `queue/work_order_prompt.md` and `queue/memory_promotion_prompt.md`.
- No queue item was created.
- Graphify Pass 10 `intake/` (64 files), `repo_graphs/` (56 files), and `receipts/` (2 files) manifests are byte-identical before/after.
- The pipx-installed Graphify package was inspected only to locate its deterministic extractor and was not modified.
- The canonical vault manifest is byte-identical immediately before and after live Graphify extraction.

Before/after source manifests and final process/worktree state are retained beside this report.
