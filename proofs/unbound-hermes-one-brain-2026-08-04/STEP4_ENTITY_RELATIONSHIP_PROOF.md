# Step 4 — targeted entity and relationship typing

> Point-in-time proof · Created: 2026-08-04 · Token usage: no agent invocation for Graphify discovery or proof queries.

Verdict: **PASS.** Step 4 is complete. Steps 5–8 were not started.

## Before state

- Agentic OS HEAD: `1ec13b608fdcd66ed62052d28fe3b908d1ddfc97`; dirty-state digest `65afbeeaf6820102312f481ab638529ede64f471200a27a20828852a2a8c9dd7`. Existing modifications and untracked work were preserved.
- Vault HEAD: `15adf71c72f83bf7c90ed90a11456ecb4d76bf9f`; ahead 14 with pre-existing edits to `memory/company.md`, `memory/offers.md`, `memory/positioning.md` and four untracked operating-context documents. Canonical Markdown manifest digest: `e52b55eb60c58890b912c815b9913d7c0e956a826a5c8f58e1cd9b6a9a68b2d1`.
- Graphify was not a Git worktree. Published source aggregate: `ad82858981723f24009399f0e760597dae4633e90dcfd8b1c3b98eafb3388d54`; artifact hashes were graph `c989c197…`, projection `1edcc707…`, source manifest `fb947afb…`.
- Loretta note SHA-256: `122343ea7a43dcc7529ddf2a5647b05faa19d21f9d5e79ed2480632644a2d01c`; Evan: `23197f6ce1bce384c59ea2cf6a62ff80f344ac13036009e9cd6f6c67e59a126f`.

## Deliberate entity inventory

Graphify schema v2 ingested 37 allowlisted canonical notes and classified 10 genuine entity notes, all `prospect`. It preserved each stable ID and existing `status`; only Loretta and Evan had justified `date: 2026-07-22`, and Graphify preserved it. The inventory comprises Club Hub/Ilan Puterman, Cyborg/Nicolas Dupont, DeepInspect.AI/Parminder Singh, Flox/Ron Efroni, Highway 99/Evan Thompson, Manufex/Anush Sridhar, Ollama/Jeffrey Morgan, PunttAI/Ronnie Coleman, Talent Harbour/Loretta Davis, and Zunesha Labs/Omar Alani.

No empty fields were added. `memory/offers.md` remained `type: knowledge` because it is a human-edited aggregate offer narrative rather than one unambiguous offer entity. READMEs, indexes, sessions, transcripts, executive view, open loops, current priorities, narrative memory, architecture/context documents, aggregate decision/client/project notes, receipts, and queue records were not typed as entities.

## Supported relationship vocabulary

- Semantic relation: `activity → touched → prospect` only.
- Derivation: exact `AOS-YYYY-NNNN` values already declared in a prospect note's `queue_ids` frontmatter.
- Evidence: two derived edges, `AOS-2026-0174 → Loretta` and `AOS-2026-0175 → Evan`.
- Explicit/derived distinction: 66 wiki-link edges remain `edge_kind: explicit`; the two `touched` edges are `edge_kind: derived`, `confidence: DERIVED`, extractor `ttros.frontmatter.queue_ids`, with canonical target paths and human-readable relationship reasons.
- Unsupported locked examples were not invented because the live Brain does not establish genuine interest, supersession, or open-client-commitment entities.

## Graphify publication and one-hop result

- Final build receipt: `20260804T100446298265Z-build-success.json`.
- Final unchanged receipt: `20260804T100447203504Z-unchanged-success.json`.
- Final injected failure receipt: `20260804T100448434908Z-build-failed.json`; previous artifact hashes remained exact and status remained fresh.
- Published source aggregate: `ba8423f9f87fe665870ca2f146af2d0785120b7cca04928417245c879e2f83a6`.
- Published hashes: graph `2cb34ede7303ab41a5813d4f967b492cc9c41ea23dcaffc2ecb23611b44a50ba`; projection `149ecace51e45f92879e1923bf8d5fddfe120df9ef7d0f2fe03590ececfbb11b`; source manifest `191c75bfd9672629beeb089ac261ca4980edf26f8fa1889f7a1b415b439f813c`.
- Projection: 37 sources, 10 typed entities, 66 explicit wiki edges, 2 derived semantic edges, zero input/output tokens, `bodies_in_projection: false`.
- `AOS-2026-0174` returned only `business_brain:prospects/2026-07-talent-harbour-loretta-davis.md`, score 110, reason `one-hop derived touched`.
- `AOS-2026-0175` returned only `business_brain:prospects/2026-07-highway-99-evan-thompson.md`, score 110, reason `one-hop derived touched`.
- `Loretta Davis activity` and `Evan Thompson activity` each returned only their own canonical note. The generic-activity seed defect found during proof was repaired and regression-tested.
- Missing, blank, and unknown scopes raised before target return. Two-client fixtures returned only the declared client's path. Stale/unavailable fixtures returned zero graph targets plus the existing pointer/search fallback.

## Loretta / Evan and Steps 0–3 regression

- Both note hashes remained exact; both retained `type: prospect`, `status: human_review`, `date: 2026-07-22`, stable IDs, authorship, provenance, and human content.
- Context Assembler v1 selected Loretta plus `queue/work_items.jsonl#AOS-2026-0174` and its two notification receipt paths; it selected Evan plus `#AOS-2026-0175` and its two notification receipt paths.
- Fresh-process Graphify retrieval opened exactly one correct canonical prospect for each activity ID.
- Queue count stayed 475 and SHA-256 stayed `746fdea55682b9633a92ba3447b0304589e2cc9dca0f6ec3563a5c8652ee3228` across the read-only assembly/discovery proof. Model invocations: 0. External actions: 0.
- Immutable record hashes remained: 0071 `44d1d9dd…`, 0073 `b734109d…`, 0074 `4325bbc…`, 0075 `3b88d3be…`, 0174 `2df5abf…`, 0175 `e92ff399…`.
- Ordinary discussion/no-queue backend test and all 15 Telegram conversational routing tests passed. Worker-pack and sticky-anaphora Context Assembler tests passed.

## Runtime reproducibility / drift

`tools/validate_unbound_runtime.py --status` and `--dry-run` passed. The repository-controlled, read-only check verifies the owned Step 0–3 markers in native `turn_context.py`, the external Hermes router, `aos-claude`, and exactly six scoped profile configs. It verifies mandatory assembled context, no hook spilling, native memory disabled, exact pre/post hooks, Brain MCP, canonical-root routing, and permission-header dedup. It fails closed on missing/drifted markers. It does not read the Hermes global/default profile, secrets, environment values, tokens, credentials, or runtime data.

## Validation commands and outcomes

- `python3 -m unittest ...step4...business_brain...one_brain...search...runtime...prospecting...` — 51/51 affected tests passed after excluding the dependency-blocked Telegram module from that first invocation.
- `python3 -m unittest -v tests.test_telegram_conversational_routing` — 15/15 passed after installing declared `tiktoken==0.11.0` locally.
- `python3 -m unittest -v tests.test_graphify_pass10` — 24/24 passed.
- `python3 -m unittest -v dashboard.backend.test_composio_hermes.HermesComposioTests.test_ordinary_conversation_uses_operator_lean_without_queue` — 1/1 passed.
- `python3 -m unittest tests.test_aos_queue tests.test_aos_paths dashboard.backend.test_composio_hermes` — 311-test standing suite completed successfully.
- `python3 tools/validate_business_brain.py --vault <canonical Brain>` — PASS: 44 Markdown files, unique IDs where required, zero broken links, two-hop reachability, backup exclusion, valid Obsidian config.
- Real Graphify build, unchanged rebuild, injected failed rebuild, status, four isolated queries, and two fresh-process loader calls — PASS.
- `python3 tools/validate_unbound_runtime.py --status` and `--dry-run` — PASS.
- `python3 -m py_compile ...`; `python3 -m json.tool context/client_scope_registry.json`; repository and vault `git diff --check`; vault `git fsck --full` — PASS.
- No frontend code changed; frontend tests/build were not run.

## Brain diff and audit history

The sole Step 4 Brain edit adds direct wiki navigation from the canonical index to executive view, open loops, and contradictions. It was committed locally as `5419184` (`hermes: step-4 canonical relationship navigation`), exact path `index/MEMORY_INDEX.md` only. No vault push occurred. All pre-existing human edits remain unstaged and unchanged; `memory/offers.md` was verified back at its exact before-state SHA-256 `612f407ef6628348f07e3169fca3cd06b580a7417e2165646ded0fe0f21ad9da` before the final Graphify rebuild.

## Protected boundary

No North Shore interior, Telegram bridge interior, routing JSON, lane profiles JSON, global/default Hermes profile, environment file, secret, credential, token, authentication material, raw communication, transcript body, protected immutable queue record, external connector, publication, deployment, recurring job, remote repository, or external system was inspected or mutated as part of Step 4.
