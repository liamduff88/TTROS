# Step 0 recon — Unbound Hermes, One Brain

> Revisit: on a Hermes package upgrade, invocation-path change, or memory-provider change. · Last touched: 2026-08-04.

## 1. Production implementation

- AOS wrapper: `/home/liam/.local/bin/aos-hermes` resolves to `/home/liam/agentic-os/hermes/hermes.py`.
- Native CLI: `/home/liam/.local/bin/hermes` runs `/home/liam/.hermes/hermes-agent/venv/bin/hermes`.
- Installed package: `hermes-agent 0.18.0`; checkout and venv: `/home/liam/.hermes/hermes-agent`; CLI entry: `hermes_cli.main`.
- AOS coordinator and operator wrappers: `tools/aos-hermes-coordinator.sh` and `tools/aos-hermes-operator-lean.sh`.
- Codex entry: `/home/liam/.local/bin/aos-codex` routes through the dashboard API. Claude entry: `/home/liam/.local/bin/aos-claude` now does the same; the AOS Hermes delegate assembles before invoking the underlying Claude binary.

## 2. Real model/cognition entry points

| Surface | Production path | One Brain boundary |
|---|---|---|
| Dashboard executive cards / consultations | dashboard API | typed `AssembledContext` before `_run_hermes_message` |
| Telegram | protected bridge POST to `/api/wsl/hermes` | shared dashboard/operator assembler; no protected bridge edit required |
| Sticky operator conversation | `/api/wsl/hermes` → operator-lean oneshot | backend assembly plus native pre-LLM hook; durable vault session |
| Queue/orchestrator and reviews | dashboard backend and queue runner | assembly before orchestration/review; worker context pack before lane worker |
| Codex | dashboard `_run_codex_local` | raw prompts rejected; typed assembled context required |
| Claude Code | dashboard `_run_wsl_prompt_command` | raw prompts rejected; typed assembled context required |
| Department workers | `aos-hermes-coordinator.sh --profile aos-*` | native pre-hook plus fail-closed native turn boundary |
| Scheduled work | Hermes cron records; Gmail capture job `04125023e5ce` is enabled and `no_agent:true`; other inspected model jobs disabled | model jobs use their profile hook; deterministic capture has explicit N/A/no-agent semantics |
| Capture classification | `LocalDeterministicClassifier` | no model invocation; no assembled Brain context needed |

At recon time the live Telegram bridge, native dashboard, gateway, dashboard backend/frontend, and queue runner were independently running. The protected Telegram process and North Shore process were not killed or changed.

## 3. Native memory mechanics

- `tools/memory_tool.py` owns `<HERMES_HOME>/memories/MEMORY.md` and `USER.md` as delimiter-separated entry stores. It loads a snapshot for the system prompt and exposes add, replace, and remove operations.
- Add/replace/remove take a file lock and persist by atomic rename. Replace/remove reconstruct the owned file; section and character caps are part of that private format.
- Conversation state is separate SQLite `state.db`. Context compression uses an auxiliary summarizer, keeps compacted originals as `active=0, compacted=1`, and writes the compacted live set. Rewind rows remain `active=0, compacted=0`; explicit session deletion hard-deletes session/message rows.
- Native memory has no meaning-based canonical-note routing, frontmatter preservation contract, expected-hash comparison against an Obsidian edit, exact-path vault Git transaction, or validation rollback for arbitrary vault Markdown.

## 4–6. Ownership and writer safety

The native writer assumes ownership of its memory directory and file format. It is not safe to point at the vault or at selected human-authored notes: replace/remove are whole-owned-file reconstructions and native locking would not coordinate with Obsidian. A symlink was therefore rejected.

The selected adapter uses a vault-local lock plus expected content hashes. It validates candidate Markdown before replacement, writes/fsyncs a same-filesystem temporary file, atomically replaces only the validated candidate, stages exact paths, commits with the local Hermes identity, and rolls back only if its own candidate is still present. A stale expected hash aborts and preserves the concurrent Obsidian edit. Focused tests prove preservation, invalid-candidate rollback, and stale-hash concurrency refusal.

## 7. Useful private-profile knowledge

No AOS profile contained `memories/MEMORY.md` or `USER.md`. Durable-looking material was in private session transcripts:

| Profile | Sessions | Messages |
|---|---:|---:|
| aos-orchestrator | 110 | 2,497 |
| aos-revenue | 18 | 273 |
| aos-marketing | 12 | 92 |
| aos-delivery | 13 | 130 |
| aos-ops | 12 | 110 |
| operator-lean | 70 | 135 |

The useful Loretta/Evan interpretations and their conflict were migrated once to `sessions/2026-08-04_profile-memory-migration.md` with `status: unreconciled`; canonical records and Liam corrections take precedence.

## 8. Telegram context

Before this release Telegram reached the operator endpoint, but the operator loaded only three fixed Brain pointers with a 6,000-byte cap and kept four/2,400-byte recent turns in process RAM. It therefore did not have the complete shared executive context and lost conversation state on restart. Telegram now reaches the same mandatory assembler as the dashboard. The real `/api/wsl/hermes` proof selected both prospect notes, AOS-0174/0175 and their receipts, and the durable session; the bridge itself needed no edit.

## 9. Context and boilerplate measurements

The exact snapshot is in `CONTEXT_COUNTS.json`. Highlights:

- Final fourth-restart operator call: 111,285 bytes / 23,702 estimated assembled tokens, zero truncation warnings; durable conversation block 20,225 bytes / 4,194 tokens. The larger context is visible and intact, not silently clipped.
- AOS-2026-0482 pack: 44,570 bytes on disk. Its assembled payload is 42,973 bytes / 9,306 tokens; 39,223 bytes / 8,573 tokens are selected blocks and 3,750 bytes / 733 tokens are the task request.
- The same pack rendered for Codex is 44,353 bytes / 9,564 tokens; Claude Code is 44,359 / 9,566; revenue is 44,355 / 9,564. The only difference is visible assembler framing. Provider-owned hidden Codex/Claude system preambles are not observable from the local CLI and are recorded as unavailable rather than guessed.
- Native profile memory/user-profile prompt contribution is exactly zero for every AOS profile. The file records exact fixed system/tool-schema snapshots for operator and all departments.

## 10. Vault-local Git health

The vault on `/mnt/c` passed `git fsck --full`, exact-path staging/commits, validation after writes, and repeated commits from the native post-hook. Existing human changes to `memory/company.md`, `memory/offers.md`, `memory/positioning.md`, and four untracked architecture documents remained unstaged and untouched. The remote exists, but the adapter has no push operation and no push was run.

## 11. Binding decision

Selected mechanism: explicit adapter and mandatory pre/post model hooks. This is safer than a scoped symlink because the native store owns its Markdown, and safer than configuration-only redirection because arbitrary canonical notes need meaning-based routing, provenance, human-content preservation, concurrent-edit detection, validation, rollback, and coherent exact-path Git commits. Native profile memory is disabled; the Obsidian vault is the only durable knowledge authority.
