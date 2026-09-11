# STEP T8-A — the five contaminating turns are deleted, re-indexed, verified

**Verdict: PASS against the revised (Liam-approved 2026-09-10) acceptance rule.** The five turns
are gone from the vault, the recency mechanism that was surfacing them to David no longer selects
any of them, the fabricated-context phrase ("11 boards") is absent from both probe questions'
rendered context, and Fred's genuine "11 boards" fact remains retrievable from the real source
record through the normal retrieval path, unaffected by the cleanup.

## Corrected architecture (found during Part B, before any vault write — this is the reason the
original hard-pass rule was revised)

`brain_memory_mcp.search_history()` — the tool named in T7's own diagnosis and in this step's
original Part B/D design — is not a valid detector for anything under `sessions/`. It always
calls `tools/aos_indexer.py`'s FTS index with `client_scope="global"` hard-coded. That scope's
`search_source_identities` for `business_brain` in `context/client_scope_registry.json` allow only
three prefixes (`sources/intake/records/`, `sources/historical_calls/cards/`,
`sources/intake/cards/`) plus a fixed allow-list of named notes — **`sessions/` has no rule at
all, in any scope.** Confirmed directly: a freshly rebuilt `search/os_index.db` (4367 documents,
0 failures) contains **zero** `business_brain:sessions/*` rows, before any change was made. This
means:

- The five residue-probe phrases (one per contaminated turn, each independently verified unique
  across the whole vault by direct `grep -rF` before use — so this was not a phrase-choice
  problem) could never be found via `search_history`, regardless of whether the turns existed.
- The "sessions/ hit" half of the positive control (`search_history("like, I think 11")`) could
  likewise only ever return zero, before or after.

Both legs print the same answer no matter the state of the world — the forbidden "detector that
can only print PASS." **T7's and this step's original prediction that `search_history` would
surface a `sessions/` hit was structurally wrong**, not merely unlucky; earlier assertions built
on that assumption should be read as vacuous, not as evidence sessions content was ever reachable
through `search_history`. No new machinery was added to fix this (per Liam's instruction) — the
scope-registry gap is a separate, pre-existing fact about the retrieval surface, out of this
step's scope, and is recorded here for the record, not repaired.

The recency mechanism (`tools.context_assembler._session_recency_block`) is unaffected by any of
this: it reads `sessions/*.md` directly off disk, bypassing the FTS index and the scope registry
entirely. This is the actual path that put "11 boards" in front of David in T6-D1/D2, and it is
what this step's revised acceptance rule is built on.

## Revised Part B/D acceptance rule (Liam-approved)

1. Zero of the five contaminating turn timestamps selected by `_session_recency_block` for either
   recency probe question, after cleanup.
2. "11 boards" absent from the rendered context of the contamination-probe recency question.
3. Fred's genuine "11 boards" fact remains retrievable from the real source record
   (`business_brain:sources/intake/records/d9cb4668fd766474278e414bb53223f944342004f34be23020c161fa4160dd74.md`)
   through the normal retrieval path (`search_history` finds the pointer; `open_note` reads it).

## Before / after

| Check | Before | After |
|---|---|---|
| Recency (i) `"What happened in my meeting with Fred, and what did he say about MLS?"` — selects a contaminating timestamp | yes — both `23:43:14.377494Z` and `23:44:01.549610Z` | **no — zero of five**; now selects two turns from `sessions/2026-08-17_hermes-cli_7cd4569d6fe3.md` instead |
| Recency (i) contains "11 boards" | no (these two turns' excerpted paragraphs didn't repeat the exact phrase) | no |
| Recency (ii) `"In my meeting with Fred, what were his exact words about how many GVR boards there are?"` — selects a contaminating timestamp | yes — same two turns | **no — zero of five**; now selects turns from `2026-09-08` and `2026-09-09` session files |
| Recency (ii) contains "11 boards" | **yes** (live contamination, reproduced) | **no** |
| Positive control — Fred source record returned via `search_history("like, I think 11")` | yes, rank 1 | yes, rank 1 (unchanged) |
| Fred source `open_note` contains "11 boards" | yes (truncated at 60,000 chars but the phrase is within that window) | yes (unchanged) |

Full machine-readable before/after runs: `scripts/stepT8A_residue_detector_before.txt`,
`scripts/stepT8A_residue_detector_after.txt`.

## Part A — preconditions (established, read-only)

- Gated vault-write script: `tools/brain_memory.py::write_transaction` (line 261) — confirmed it
  replaces a whole note's content atomically via `documents={relative: new_full_text}`, with an
  `expected_hashes` concurrency guard, frontmatter/markdown validation, and a local git commit —
  the correct guarded path per header rule 2. It always re-stamps the `hermes_last_write`
  frontmatter submapping via `apply_provenance()`; this is intrinsic to the gated path, not
  something this step controls, and is the only frontmatter change made.
- Production Brain indexer entrypoint: `tools/aos_indexer.py` (`scan()` = full rebuild; `search()`
  is what `brain_memory_mcp._vault_search()` calls for `search_history`).
- Target file frontmatter (lines 1-13) intact before the change; exactly the five named
  `### Turn ·` headers present, matching the table, and no other turn headers existed.
- Target file before: 259 lines, 13,812 bytes, mtime `2026-09-10T23:44:01Z`,
  sha256 `a6fd9ad589d66d7b730a36c8c7717081cf26e1d0866cbf32858ef45ba105cbef`.

## Part C — the change (executed)

- **Backup:** `/home/liam/ttros_backups/stepT8A_2026-09-10/2026-09-10_hermes-cli_7cd4569d6fe3.md.PREIMAGE`
  (refused-if-exists, did not exist), sha256 verified equal to the pre-change file's hash
  (`a6fd9ad5…`) before proceeding.
- **Exact change:** replaced the note's content with only its frontmatter and preamble (through
  `## Conversation`), removing all five turns (they were the only turns in the file, so the
  "Conversation" section is now empty pending the next real write).
- **Exact rollback:** `write_transaction({relative: <PREIMAGE bytes>}, source=..., session_id=...,
  expected_hashes={relative: "7443461025e2efadbd25a26ffd75b204fab2b05b6e24963e28ba8398dbaababc"})`
  through the same gated script, then re-run `python3 tools/aos_indexer.py scan`.
- **Pre-write assertions, checked in code before calling the gated script:** no `### Turn ·`
  header present in the new content; frontmatter substring (up to the closing `---`) byte-identical
  to the original. Both held.
- One iteration needed a content fix, not a logic change: the vault's own `git diff --cached
  --check` (part of `write_transaction`'s commit step) rejected a trailing blank line at EOF in
  the turn-less file; `write_transaction` correctly rolled back to the original bytes and left the
  git index clean on that rejection (verified: post-failure hash matched the pre-change hash, `git
  status` was empty). Trimmed the trailing blank line and re-ran; this time it wrote and committed
  cleanly (local commit `2e97281` in the vault's own git worktree — no push).
- **Written through the gated script:** yes, `write_transaction`, no editor/sed/redirect used.
- Target file after: 18 lines, 493 bytes,
  sha256 `7443461025e2efadbd25a26ffd75b204fab2b05b6e24963e28ba8398dbaababc`.
- Re-index: `python3 tools/aos_indexer.py scan` → `{"status": "success", "indexed": 4369,
  "skipped": 1429, "failures": []}` (before-change scan for Part B baseline was `{"indexed": 4367,
  "failures": []}`; the small delta is unrelated background churn elsewhere in the two roots, not
  the target file, which was never a member of the indexed/searchable set either before or after —
  see the scope-registry finding above).

## Part D — verify after (done, see table above)

Hard pass rule (revised, fixed before running Part D, not relaxed afterward): zero of the five
timestamps selected by either recency probe, "11 boards" absent from both, Fred's source record
still returns via `search_history` and still contains "11 boards" via `open_note`. **All four
held.**

`sessions/thread_david.md`: untouched — mtime `2026-09-09T09:47:23-07:00` (predates this session
entirely; this file was never part of T8-A's scope).

## What this PASS licenses and what it does not

It licenses: these five turns can no longer reach David through the recency mechanism that was
actually surfacing them (the only path they were ever reachable through — they were never
reachable via `search_history`, before or after). It also licenses continued confidence that the
underlying Fred source-of-truth record is untouched and retrievable.

It does not license: any claim about `search_history`'s general usefulness for session content
(it has none, for any session file, which is a standing architectural fact this step surfaced but
did not fix), any claim about retrieval cost, or anything about residue in files this detector did
not target — no sweep of other session files was run, per this step's scope.

Model calls made: 0.
