# Local Search Index
> Revisit: after WP8 search schema changes. · Last touched: 2026-07-09

`tools/aos-indexer.py` builds a deterministic local SQLite FTS5 index at
`search/os_index.db`. It indexes Agentic OS Live plus TTROS Business Brain as a
read-only source. It does not call Hermes, Codex, Claude, embedding APIs, cloud
stores, or model providers.

Supported commands:

```bash
python3 tools/aos-indexer.py scan
python3 tools/aos-indexer.py index queue/inbox/example.md
python3 tools/aos-indexer.py watch --once
python3 tools/aos-indexer.py search carousel
python3 tools/aos-indexer.py status
```

PDF, DOCX, and XLSX files are indexed by filename only in v1.
