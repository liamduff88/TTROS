# TTROS Business Brain reconciliation — Block 1 closeout

## PASS

Checkpoint 1 is complete. Block 2 was not started.

## Files touched

- Repo: exact source/config/test/build-output and proof paths are enumerated in `FILES_TOUCHED_2026-07-15.txt`. Principal runtime additions are `/home/liam/agentic-os-live/tools/business_brain.py`, `/home/liam/agentic-os-live/tools/validate_business_brain.py`, `/home/liam/agentic-os-live/tools/aos_graphify_markdown_extract.py`, and `/home/liam/agentic-os-live/dashboard/backend/business_brain_graph.py`; active consumers listed in `ACTIVE_CONSUMER_DISPOSITION_2026-07-15.md` were repaired in place.
- Business Brain: 19 existing canonical Markdown notes received minimal `id`/`type` frontmatter; `README.md` and `index/MEMORY_INDEX.md` received navigation links; `.obsidian/graph.json` received the backup-exclusion filter; `.obsidian/workspace.json` records the real Obsidian open proof. No note was added, removed, relocated, or substantively rewritten.
- Graphify derived output: exactly three published artifacts and three receipts under `/home/liam/graphify-brain/document_graphs/ttros-business-brain/`, all individually listed in `FILES_TOUCHED_2026-07-15.txt`.
- Evidence package: `/home/liam/agentic-os-live/proofs/brain-reconciliation/block-1/`, with every file listed individually in `FILES_TOUCHED_2026-07-15.txt`.

## Validation

- `python3 -m unittest discover -s tests -p 'test_*.py'` — 153 passed after final repair.
- `./dashboard/backend/.venv/bin/python -m unittest dashboard.backend.test_composio_hermes` — 132 passed.
- `python3 -m unittest tests.test_graphify_pass10` — 24 passed.
- `python3 -m unittest tests.test_business_brain tests.test_business_brain_vault tests.test_business_brain_graph tests.test_aos_search tests.test_dashboard_memory` — 18 passed.
- `npm test -- --run` in `dashboard/frontend` — 21/21 passed.
- `npm run build` in `dashboard/frontend` — production build succeeded (1,647 modules transformed).
- `python3 tools/validate_business_brain.py --before-manifest proofs/brain-reconciliation/block-1/VAULT_CONTENT_BEFORE_2026-07-15.sha256 --report proofs/brain-reconciliation/block-1/VAULT_STRUCTURE_REPORT_2026-07-15.json` — PASS: 19 unique IDs, zero missing IDs, zero broken wiki links, all canonical notes reachable within one hop, backups excluded, Obsidian JSON valid, authorized structural diff only.
- Python compilation passed for the resolver, indexer, vault validator, Graphify wrapper/service, and dashboard backend.
- `bash loop/verify-goals.sh | rg business_brain_pointer_valid` — focused goal PASS. The broader pre-existing verifier still reports unrelated historical-reference and receipt visibility violations; none was masked or expanded into Block 1.
- Real dashboard proof: backend 8010 and frontend 3010 were started from stopped, `/api/dashboard/memory` returned the live canonical Brain (19 notes, 18 backups excluded, logical paths, true headings, promotion inactive), and Windows Edge captured `TTROS_DASHBOARD_MEMORY_2026-07-15.png`. Both services were returned to stopped.
- Real Obsidian proof: installed Windows Obsidian opened the canonical README, memory index, and graph. Screenshots show working properties/navigation/backlinks and a 19-note canonical graph with backups filtered. Obsidian was returned to stopped.
- Real Graphify fixture proof: installed Graphify structural Markdown extraction ingested three fixture notes; stable IDs/paths/metadata and three explicit wiki links survived; second build was hash-identical; ranked result contained path+score only; stale/unavailable fallbacks returned zero targets.
- Real live-vault Graphify proof: 19 notes/IDs, 61 raw nodes, 64 raw edges, 22 raw references, 42 headings, and 22 explicit wiki edges were projected into `ttros-business-brain`. Query returned paths+scores only. Stable hashes were identical on the unchanged second build.
- Vault source hashes immediately before and after live extraction are identical.
- Failed live rebuild preserved all three prior published artifact hashes and left the previous graph fresh/usable. Stale/unavailable cases recorded `pointers_search` fallback.
- Pass 10 intake (64 files), repository outputs (56), and receipts (2) are byte-identical before/after.

## Root cause / behavior changed

- The active system had multiple stale Brain conventions: a repo-relative indexer root, `_substrate.wiki`, `graph-imports/aos-repo`, bare/numeric memory references, repo-local dashboard “memory,” and a title/tag-inferred promotion queue.
- One shared resolver now maps `business_brain:<relative-path>` to the live `/mnt/c` vault and rejects absolute paths, traversal, noncanonical separators, basename ambiguity, symlink escape, missing files, and `_backups`.
- Active identities, rules, goals, prompts, skills, workflows, search, dashboard, and Graphify integration now use or route through that convention. Client-specific reads require an exact full pointer; unresolved client scope stops. No Block 2 registry/loader was implemented.
- Vault navigation now has stable note identity and complete root links without rewriting knowledge.
- Graphify is a failure-preserving derived selector. The installed package remains unchanged; TTROS compensates for Graphify 0.9.11's LLM-required documents CLI and root-style wiki-link gap in the maintainable wrapper/projection. Graph targets are not trusted for model context before Block 2.

## Protected areas

- Protected path metadata is identical and protected interiors were not inspected.
- Unrelated dirty work is SHA-256 identical to preflight.
- Immutable queue items were not mutated; no queue item was created.
- Queue work items, run/token/goal ledgers, events, notifications, rollups, and live search DB/WAL/SHM are byte-identical. Only the two authorized queue documentation prompts changed.
- Pass 10 outputs/history/receipts were not repurposed or overwritten.
- `_backups/` was not written and is excluded from navigation, resolver, search, dashboard, Obsidian graph, and Graphify source selection.
- No connector, external action, credential, commit, push, recurring job, capture activation, or protected client runtime action occurred.
- Services/processes/listeners were restored to their original stopped state.

## Blockers

- None.
- Documentation gap recorded, not blocking implementation: the requested exact locked-design, current-state, and history-index filenames were absent. The exact July 15 system readout was found/read, and the adopted runbook, adopted packaging amendment, live executable reality, and proof results controlled the work. No duplicate authority document was invented.

## Next action

- Checkpoint 1 only — Liam reviews this complete Block 1 closeout; acceptance authorizes Block 2.

## Token usage

Token usage: unavailable from current CLI output.
