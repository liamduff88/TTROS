# Obsidian usability proof

Status: PASS
Date: 2026-07-15
Vault: canonical TTROS Business Brain
Token usage: no agent invocation.

- Installed Windows Obsidian was accessible and was driven locally against the real `/mnt/c` vault.
- Obsidian began stopped, opened the canonical `README.md`, `index/MEMORY_INDEX.md`, and graph view, and was returned to stopped state.
- Screenshots: `TTROS_OBSIDIAN_README_2026-07-15.png`, `TTROS_OBSIDIAN_MEMORY_INDEX_2026-07-15.png`, and `TTROS_OBSIDIAN_GRAPH_2026-07-15.png`.
- The README and index render valid properties and wiki navigation; representative backlinks are visible.
- The graph view shows canonical relationships and applies `.obsidian/graph.json` search `-path:_backups`.
- All five existing `.obsidian` JSON files parse successfully. Only `graph.json` (intentional backup filter) and `workspace.json` (actual application open state) changed.
- Deterministic exact-link validation reports 19 canonical notes, 19 unique IDs, zero broken wiki links, every note reachable from `README.md` or `index/MEMORY_INDEX.md` within one hop, and zero backup targets.
- `_backups/` contains 18 Markdown files but none appears in canonical navigation or relationship targets.

The exact machine-readable relationship and validation evidence is `VAULT_STRUCTURE_REPORT_2026-07-15.json`.
