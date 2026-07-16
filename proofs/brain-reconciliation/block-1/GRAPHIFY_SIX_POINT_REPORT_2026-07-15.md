# Graphify Markdown six-point contract report

Status: PASS
Date: 2026-07-15
Package: Graphify 0.9.11, installed pipx package unchanged
Live namespace: `/home/liam/graphify-brain/document_graphs/ttros-business-brain`
Token usage: no agent invocation for Graphify extraction, projection, status, or query.

## Fixture proof

The real installed Graphify documents CLI discovered three Markdown documents, then exited because version 0.9.11 requires an external LLM key. No key was supplied. TTROS therefore uses Graphify's installed deterministic Markdown extractor API through `tools/aos_graphify_markdown_extract.py`, then applies a stable TTROS projection in `dashboard/backend/business_brain_graph.py`.

1. Representative ingestion: three canonical fixture notes ingested; backup note excluded; six raw nodes, six raw edges, three raw references.
2. Identity/path: all three frontmatter IDs survived; each note has its canonical `business_brain:<relative-path>`.
3. Metadata/links: note metadata is projected without bodies; three explicit wiki-link edges are present.
4. Explicit/derived distinction: `edge_kind=explicit` for wiki links and `edge_kind=structural` for note-to-heading containment; two explicit edges were package-confirmed and one root-style Obsidian edge was safely TTROS-repaired.
5. Ranked file targets: query `offers workflow` returned only `business_brain:memory/offers.md` plus score `3.0`; no note body or content excerpt is returned.
6. Freshness/fallback: deterministic source manifest and aggregate hash drive fresh/stale state; stale and unavailable fixtures return no targets and route to `pointers_search`.

Fixture artifacts were byte-identical on an unchanged second build:

- `graph.json`: `5f3c736edbf5e63423463aef45518eaa0223fa97e71ad3c38a4385693a1fd9d1`
- `projection_manifest.json`: `d3d64879ff5275154fa82e5c221ccda8d4d40cc389fa99c66ff8bbe35db46c56`
- `source_manifest.json`: `b55720da4b35e2e1622c0658d0e4c27543bef5be26ed34209916eb28ee7556f7`

## Live-vault proof

- 19 canonical Markdown notes and 19 stable frontmatter IDs.
- 61 raw Graphify nodes, 64 raw edges, 22 raw references.
- 42 projected heading nodes and 22 identifiable explicit wiki-link edges.
- Four explicit edges package-confirmed; 18 root-style Obsidian edges repaired by the TTROS projection.
- Bodies absent from the graph projection and ranked result API.
- Query `offers positioning revenue` returned exactly three path/score targets: offers, positioning, and sales/revenue. `trusted_for_model` remains false until Block 2 client-scope enforcement exists.
- Pre/post extraction vault manifests are byte-identical.
- An unchanged second build reported `operation=unchanged` and retained identical stable artifact hashes.
- An intentionally unavailable extractor failed the rebuild; the three prior published artifact hashes remained identical and the previous graph remained fresh/usable.
- Independently stale and unavailable graphs returned zero targets and recorded `pointers_search` fallback.

Live stable hashes:

- `graph.json`: `2506b964ea24f18ea43a594932344eab935e9a30828f3e3e7eec50a8e327c31e`
- `projection_manifest.json`: `94cc80425ab6016d5521967f74623b5390a8bf71ed83151a1a979146146fafd0`
- `source_manifest.json`: `da67448d188aa8fdf97e121936a40873f49007c093b61aecb1d29a5b56769ad4`

Pass 10 intake, repository graphs, and receipts are byte-identical before/after. Existing Repo Ingest, artifact serving, embedded graph interaction contracts, atomic rebuild/refetch preservation, and queue-only model-assisted behavior passed 24 tests. Dashboard frontend tests passed 21/21 and the production build succeeded.
