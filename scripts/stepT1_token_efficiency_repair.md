# STEP T1 — TTROS token efficiency repair. ZERO model calls.

Surface: CLI-David (`hermes -p david -z`), gpt-5.5 / openai-codex, per prior audits.
No David/Hermes/provider call is made anywhere in this task. All numbers below are either
(a) read from pre-existing files already on disk from a prior session's real dispatches, or
(b) computed locally in pure Python against those files / against the live repo. Every python
one-liner used is a read-only measurement; none constructs then sends a new request.

---

## PART 1 — BASELINE: the first-request payload, decomposed

**Evidence source, not reconstructed:** `~/.hermes/profiles/david/sessions/request_dump_20260909_191615_f3a237_20260909_191627_264463.json`.
This is a genuine Hermes-internal error dump, written automatically when a real dispatched
request hit `HTTP 429` (`reason: max_retries_exhausted`) during the prior B7 pass documented in
`scripts/step6_post_i3_usage_forensic_audit.md`. It carries the **exact JSON body Hermes actually
built and sent to the provider** (`request.body`: `model`, `instructions`, `input`, `tools`,
`reasoning`, `tool_choice`, `parallel_tool_calls`, `prompt_cache_key`, `extra_headers`). Reading a
pre-existing file on disk is not a model call. Identified via
`grep -n "Andrea Roberts" docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS...md
scripts/step6_post_i3_b7_pass.transcript.txt` as **B7 question E5** ("Did Andrea Roberts introduce
us to anyone?") — Q22/25 — an ordinary knowledge/relationship question, ordinary in kind. This
question never received provider token accounting (`scripts/step6_post_i3_b7_pass_E5.usage.json`
has `input_tokens: null, failed: true` — confirmed, matches the audit's "E5/F1/F2/F3 all failed"
finding). This is therefore the **request payload**, exact to the byte, for a genuine ordinary
first-turn David consultation — stronger evidence than a reconstruction, since nothing was
approximated in its construction.

### Decomposition (exact bytes; "tokens" = TTROS's own `estimate_tokens()` word/punct regex,
the same estimator the assembler embeds in its own block headers and that the forensic audit
used throughout — **not** the provider's real BPE tokenizer; see calibration below)

| Block | Bytes | Est. tokens | Class |
|---|---:|---:|---|
| `instructions` (Hermes system prompt: SOUL.md persona + Hermes framework boilerplate + native `available_skills` catalog + MEMORY + runtime-env block) | 27,384 | 5,666 | mixed — see breakdown below |
| `tools` (29 tool schemas, full JSON) | 40,088 | 10,933 | mixed — see breakdown below |
| leading question text (`input[0].content`, pre-marker) | 42 | 8 | B — request-specific |
| assembled context (marker → end of `input[0].content`) | 25,363 | 4,683 (assembler's own declared figure) | mixed, itemised next |
| **Sum of the four** | **92,877** | **21,290** | |
| Whole request body, exactly as serialized | **94,102** | — | |
| Unreconciled remainder | **1,225 B (1.3%)** | — | JSON structural overhead: field names/brackets for `model`, `store`, `reasoning`, `include`, `tool_choice`, `parallel_tool_calls`, `prompt_cache_key`, `extra_headers`, and the `input[0]` wrapper (`role`/`content` keys). **Named, not a mystery** — every byte of it is accounted for as JSON syntax around the four blocks above, not as missing content. |

**Assembled-context block, itemised (assembler's own exact per-block labels, read directly out
of the rendered text — not re-estimated):**

| Assembler block | Tokens | Bytes | Prefix |
|---|---:|---:|---|
| identity/company | 622 | 3,002 | stable |
| current priorities | 426 | 1,923 | stable |
| executive_view | 322 | 1,667 | stable |
| **deterministic morning findings** | **23** | **99** | dynamic |
| scoped canonical Brain notes | 35 | 192 | dynamic |
| recent receipts and outcomes | 12 | 54 | dynamic |
| relevant session recency | 229 | 981 | dynamic |
| relevant open loops | 12 | 52 | dynamic |
| relevant current commitments | 13 | 63 | dynamic |
| **matching skills/workflows** | **1,599** | **7,779** | dynamic |
| conversation summary | 147 | 784 | dynamic |
| action boundaries | 101 | 537 | stable |
| execution handoff contract | 654 | 3,166 | stable |
| queue reference validity | 129 | 532 | dynamic |
| provenance | 351 | 1,820 | dynamic |
| Sum of blocks | 4,683 | 22,651 | |
| Assembler's own declared total (`Context total:` line) | 4,683 | 22,693 | matches to 42 B (scaffolding lines) |

### Named hypotheses from the build plan — tested, not assumed

- **"Deterministic morning findings ~13,166 B (largest block by 5×)"** — **does NOT hold for this
  question.** Measured live: **99 B**, not 13,166 B. The block is relevance-filtered per-request
  (`_deterministic_morning_brief`'s own `ranked`/`selected` logic, capped at 6 or 12 findings only
  when the query scores against them); for a narrow historical/relationship question it correctly
  returns almost nothing. The 13,166 B figure in the design doc is real for *some* question shape
  (a "broad executive attention" query, per the `broad_attention` branch, limit=12) but is **not
  representative of an ordinary knowledge question** — reporting this as measured, not assumed.
- **"Matching skills/workflows ~8,494 B"** — **confirmed, close.** Measured live: **7,779 B**
  (1,599 tokens). This block is present on every non-technical request regardless of relevance
  quality (see Part 3/4) and is real, substantial, and request-invariant in *size* even though its
  *content* is selected per-query.
- **New finding, not named in the build plan: the `tools` block (40,088 B / 29 schemas) is larger
  than either named hypothesis and was completely unmeasured before this task.** It is sent
  unconditionally on every request. None of TTROS's own `mcp__brain__*` tools (`search_calls`,
  `open_call`, `open_note`, `search_history`) are in this 29-tool list — confirming they are
  Hermes-MCP-discovered, not preloaded, which is why `tool_describe`/`tool_search` round-trips
  occur for them (relevant to Part 4).
- **New finding: `instructions` (27,384 B) carries Hermes's own native `available_skills` catalog**
  (~80 generic Hermes skills — ComfyUI, PowerPoint, TouchDesigner, xlsx, etc. — almost entirely
  irrelevant to a TTROS business question) **in addition to**, and separate from, the assembler's
  own `matching skills/workflows` block. Two independent skill-catalog mechanisms are in play; only
  the second is TTROS's own code (`_matching_workflows_block` in `context_assembler.py`). The first
  is Hermes-native prompt construction — outside `context_assembler.py`, outside this task's "no
  Hermes patching" boundary. Named for Step 8, not touched here.

### Calibration against a real, exact, provider-billed anchor

`scripts/step6_post_i3_b7_pass_A2.usage.json`: a **direct** (`api_calls=1`, zero tool calls)
question ("What is the core principle behind how we sell?") with `cache_read_tokens: 0` — i.e.
its `input_tokens: 23,330` is the **exact real provider token count for the entire request, fully
uncached, no ambiguity from cache subtraction.** Its own assembled-context manifest
(`queue/context_assemblies/hermes-20260909_190244_f2c924-...json`) declares `total_tokens: 8,089`
(TTROS estimator) for that question's assembled context (this question's morning-findings block
was large here — 7,117 B — reconfirming the block is genuinely per-question variable, not fixed).

Reconstructing A2's full request with TTROS's estimator, substituting the real captured
`instructions`+`tools` bytes from the E5 dump (assumption: stable within the same day/profile/pass
— not independently confirmed, flagged as an assumption) and A2's own real question/context
token counts: `5,666 (instructions) + 10,933 (tools) + 10 (question, from A2's manifest
request_tokens) + 8,089 (A2's assembled context) = 24,698` TTROS-estimated tokens, vs. **23,330
real provider tokens** — within **5.9%**. This is a real, exact-anchored reconciliation, not a
guess, and it says TTROS's own word-regex estimator is a reasonable (slightly high) proxy for the
real BPE count at this scale.

### Classification (A = required every call, B = request-specific & correct, C = present but
irrelevant to an ordinary knowledge question)

| Block | Class | Why |
|---|---|---|
| Hermes persona/framework boilerplate (part of `instructions`) | A | Identity/behaviour contract; required every call. |
| Hermes native `available_skills` catalog (part of `instructions`) | **C** | ~80 generic Hermes skills, almost none relevant to an ordinary TTROS knowledge question; not TTROS code, cannot be touched without patching Hermes. |
| MEMORY + runtime-env block (part of `instructions`) | A | Small (≈600 B combined here), required. |
| `tools` (29 schemas, 40,088 B) | **C for most rows** | `browser_*` (7 tools), `vision_analyze`, `web_extract`, `web_search`, `text_to_speech` — none relevant to "did Andrea Roberts introduce us to anyone" — are Hermes-native, always-on, and not brain-MCP tools at all. |
| identity/company, current priorities, executive_view, action boundaries, execution handoff contract | A | Required stable-prefix canonical blocks; small, correctly always present. |
| deterministic morning findings | B | Correctly near-empty for this question; correctly large for a broad-attention question — request-specific and working as intended. |
| scoped canonical Brain notes | B (but see Part 3) | Correctly small here (no strong entity/pointer match) — this is the exact gap the forensic audit's §8 Fred/MLS finding describes. |
| matching skills/workflows | **C for this question** | 7,779 B of TTROS's own workflow projections, selected by keyword overlap, for a question that needs none of them (verified below in Part 3/4 — this question's own selected workflows are marginal matches). |
| conversation summary, queue reference validity, provenance, recent outcomes, session recency, open loops, current commitments | B | Correctly small, correctly request-specific. |

**Scope note on this file's diff:** `tools/context_assembler.py` was already dirty (uncommitted,
in-progress STEP I1/I2/I3 work — Step 5 map-generator support, `read_thread`/`thread_relative`,
`TTROS_CANONICAL_RANKER_ENABLED`, `NOTE_DOC_BUDGET`, etc.) before this task began. `git diff
--stat` against HEAD therefore shows ~600 changed lines that are **not** this task's work. This
report describes only the specific edits made under STEP T1, listed by name in each Repair
section below; the wider dirty tree is left untouched per the task's hard boundary.

**Reconciliation stated plainly:** the ~24,000-token evidence-base figure (`Direct-answer
baseline ~24,043`, §9 of the forensic audit) is now explained almost exactly: instructions
(5,666) + tools (10,933) + assembled context (4,683–8,089 depending on question) + question
(~10) ≈ 21,290–24,698 TTROS-estimated tokens, matching the real 23,330–24,937 range observed
across all six direct questions to within single-digit percent. **The two largest previously
*unmeasured* components are `tools` (≈45% of the whole request) and Hermes's native skills
catalog inside `instructions` — not the two blocks the build plan named as suspects.**

---

## PART 2 — REPAIR 1: the failed skill lookup

**Diagnosis method:** read the real message trace (`role`, `tool_calls`, `content`) out of
`~/.hermes/profiles/david/state.db`'s `messages` table for all seven `other_tool`-disposition
sessions (A4, B4, C2, C4, D1, D2, D4 — session ids read from each question's own
`scripts/step6_post_i3_b7_pass_<Q>.usage.json`). Zero model calls; this is a read-only SQL query
against a pre-existing local database.

**Actual cause, established from the trace, not assumed:**

| Q | `skill_view` argument | Real outcome |
|---|---|---|
| A4 | `linkedin_outreach_prep` | `{"success": false, "error": "Skill 'linkedin_outreach_prep' not found."}` |
| B4 | `build_lead_gen_agent` | not found |
| C2 | `morning_brief` | not found |
| C4 | `fit_call_prep` | not found |
| D4 | `morning_brief` | not found |
| D1 | `weekly-review-planning` | **`{"success": true, ...}`** — a real Hermes-native skill about generic weekly-review/calendar planning, unrelated to the David TTROS question asked |
| D2 | `weekly-review-planning` | same as D1 — real success, wrong/irrelevant skill |

**Correction to the prior forensic audit:** it stated all seven got "Skill not found." Direct
inspection of the message trace shows **five did (A4, B4, C2, C4, D4)** and **two (D1, D2) got a
real, successful, but irrelevant Hermes-native skill** — the round-trip was still wasted, just not
via an error. Recording this because the prior instrument's summary was wrong on this point, per
CLAUDE.md's "treat the instrument as the likeliest source of error."

**Root cause, confirmed:** the four "not found" names (`linkedin_outreach_prep`, `build_lead_gen_agent`,
`morning_brief`, `fit_call_prep`) are exact **TTROS repo directory names** matching real
`*/SKILL.md` files (confirmed by direct filesystem lookup). These are exactly the names
`_matching_workflows_block`/`_project_matching_source` project into the "matching
skills/workflows" context block as `id=<name>` metadata. Hermes's own system prompt (captured
verbatim in the real request dump, Part 1) instructs: *"If a skill matches or is even partially
relevant to your task, you MUST load it with skill_view(name)... Err on the side of loading."*
David reasonably but incorrectly treats the TTROS block's `id=` value as a name in **Hermes's own**
skill catalog (the `<available_skills>` list also embedded in `instructions` — a completely
separate, ~80-entry, Hermes-native catalog with zero overlap with TTROS repo skills). The two
"false success" cases (D1/D2) are the same root cause in a different shape: David, primed by the
same "you MUST load it" instruction, guesses a plausible-*sounding* Hermes-native skill name
instead, and gets a real but irrelevant result.

**Repair, at the cause, inside `context_assembler.py`:** one sentence added to
`_matching_workflows_block`'s preamble (the block's own `sections[0]` string), stating plainly
that these are TTROS repo files already inlined in full, not Hermes skill_view catalog entries,
and naming the specific tools (`skill_view`/`skill_manage`/`tool_search`) not to call on the `id=`
value. This addresses both failure shapes: it removes the incentive to call skill_view at all for
this block's content (fixing A4/B4/C2/C4/D4's "not found" case) and states explicitly that nothing
further needs loading (addressing D1/D2's wrong-guess case) without needing a name-collision list.

**Exact change:** `tools/context_assembler.py`, `_matching_workflows_block`, the `sections = [...]`
preamble line. **Exact rollback:** remove the appended sentence (the hunk is isolated; `git diff`
shows it as a single addition to that one line, independent of the rest of this task's edits and
of the pre-existing dirty-tree changes to this file).

**Mechanical proof the defective path is repaired (zero model calls):** re-ran
`_matching_workflows_block()` locally against the exact query that triggered A4/C4's real failure
("What are we not allowed to claim to a prospect?"). It still selects `linkedin_outreach_prep` and
`fit_call_prep` (the exact two names David wrongly called `skill_view` on) — confirming the trigger
condition is unchanged — and the rendered block content now reads, immediately before those
entries: *"These are TTROS repository workflow/skill files, already inlined below in full -- NOT
entries in Hermes's own skill_view catalog. The `id=` value is this block's own identifier, not a
Hermes skill name: calling skill_view/skill_manage/tool_search on it will fail or return an
unrelated Hermes-native skill. Nothing further needs to be loaded to use this content."* Cost:
+362 B / +76 TTROS-estimated tokens to this one block, present on every non-technical request.

**What this does NOT prove, stated per the task's own instruction:** whether David actually reads
and obeys this sentence on a live turn cannot be established without a model call, and none was
made. **Open expectation for the live acceptance question below, not a proven result.**

**Re-measurement of Part 1 after Repair 1 alone:** `matching skills/workflows` block for the E5
question ("Did Andrea Roberts introduce us to anyone?") moves from 7,779 B / 1,599 tokens to
8,141 B / 1,675 tokens (+362 B / +76 tokens, exactly the added sentence, nothing else changed).
Every other block is byte-identical. Full first-request TTROS-estimate total moves from ≈21,290
to ≈21,366 tokens (+0.4%) — a negligible, deliberate, disclosed cost for a correctness fix.

---

## PART 3 — REPAIR 2: card-first deterministic prefetch (the main repair)

**Mechanism established first, before writing any code (zero model calls — direct Python calls
against `ScopedBrainLoader`/`aos_indexer.search()`):**

- `ScopedBrainLoader.retrieve()`'s existing "search" stage (`business_brain_context.py:285-301`)
  already calls `self.search_module.search(query, source="business_brain", db_path=self.search_db_path,
  ..., exact=True, path_only=True)` — already wired to the real production index
  (`aos_indexer.runtime_db_path(None)` defaults to `search/os_index.db`; `search_db_path=None` does
  **not** disable it, contrary to an earlier working hypothesis this task tested and rejected).
- The actual reason it never surfaces anything: `exact=True` routes through
  `aos_indexer.quote_exact_fts_query()`, which joins up to 24 query tokens into **one single quoted
  FTS5 phrase** — requiring the literal words to appear contiguously, in that order, in a document.
  **Verified directly, zero results, all three representative questions:** `aos_indexer.search()`
  called with the raw natural-language query text and `exact=True` returns **0 rows** for "What
  happened in my meeting with Fred, and what did he say about MLS?", "What happened with CCI?",
  and "Did Andrea Roberts introduce us to anyone?" — against the real, live, current production
  index. This is the actual, confirmed reason the deterministic exact-search stage has never
  surfaced the Fred/CCI cards, not a wiring gap.
- Re-running the same three queries with `exact=False` (OR-of-terms, `aos_indexer.quote_fts_query`)
  and the terms fed from `_query_terms()`/`_entity_name_terms()` **does** surface the exact cards
  named in the forensic audit (the Fred/MLS intake card, all four CCI-related historical-call
  cards, both Andrea Roberts cards) — confirmed by direct query against the live index before any
  code was written.

**Repair implemented, `tools/context_assembler.py`:**

1. New regex `CARD_POINTER_RE` restricting matches to
   `business_brain:sources/{intake,historical_calls}/cards/*.card.md` — structurally excludes
   every raw original, INDEX.md, and non-card memory file from ever qualifying.
2. New function `_card_search_pointers(query, client_scope, registry, search_db_path)`: feeds
   `_query_terms(query) | _entity_name_terms(query)` into the **existing** `aos_indexer.search()`
   (the same function `ScopedBrainLoader.retrieve()` already calls) with `exact=False`, restricted
   to card paths. No new index, ranker, retriever, or classifier — same index, same search
   function, one existing hardcoded argument (`exact=True`) bypassed by calling the underlying
   search function directly with `exact=False` instead of going through `retrieve()`'s fixed
   internal call.
3. **Precision gate** (added after empirical testing exposed a real false-positive problem — see
   below): a card only qualifies if **≥2 distinct query terms of length ≥4** match its FTS `title`
   field (`aos_indexer.title_from_text`'s curated one-line summary) plus its pointer's own filename
   stem (the same signal `_known_entity_pointers()` already reads off `prospects/*.md`), **or** if
   **any one matching term is "strong"** — a multi-word proper noun (existing `_entity_name_terms`)
   or a single capitalised/all-caps token from the original query that isn't the query's first word
   (new small helper, `_strong_terms()`, mirroring the existing file's own term-overlap-threshold
   idiom used by `_known_entity_pointers`/`_recent_outcomes_block`/`_current_commitments_block`,
   not a new classifier).
4. Wired into `_scoped_note_block()` as waterfall **tier 2**: only consulted when tier 1 (explicit
   `business_brain:` pointer or `_known_entity_pointers()` match) found nothing; its result is
   read through the loader's existing explicit-pointer path (`route=pointer`); the existing tier-3
   exact-search/graph call and tier-4 `_direct_fallback()` are otherwise **unchanged**, except
   `direct_fallback` is now also suppressed when tier 2 already found a card (closing a gap where a
   genuine card hit could otherwise still be followed by an unrelated five-bucket fallback doc).
   All new evidence lands in the existing suffix block; the stable prefix is untouched; existing
   `NOTE_BLOCK_BUDGET`/`NOTE_DOC_BUDGET` truncation-and-declaration logic applies unchanged to
   whatever this stage selects.

**Why the precision gate exists — a real failure the check was capable of producing, not a
check that could only print PASS:** the first working version (OR-of-terms, any single hit
qualifies) was tested against `_scoped_note_block` immediately, before finalizing, using
negative-control queries — and it **failed**: `"What is our pricing model?"` pulled in three
unrelated historical-call cards, and `"Thanks, that is helpful."` (a trivial conversational
remark) pulled in the Fred card. Root cause: `_query_terms()`'s existing stopword list does not
exclude common connective words like `"our"`/`"and"`/`"the"`/`"for"`/`"say"` (3-letter, not on its
stopword list), which appear in nearly every card's boilerplate or prose incidentally. Fixed by
(a) matching against the FTS `title` + filename-stem instead of the FTS `snippet` (the snippet is
dominated by an identical boilerplate paragraph — *"Card meaning: what this source says... Claim
evidence: queue/receipts/..."* — present verbatim on every single card, which was itself supplying
spurious matches for words like "queue"/"work"), and (b) requiring genuine term length/strength
before counting a match. Re-tested after the fix; both negative controls now return `[]`.

**Card limit set to 3** (not the file's more common `limit=5`): tested both; `limit=5` let a
weaker 4th/5th-ranked match introduce topically-unrelated cards for the Fred/MLS query (Andrea
Roberts cards, sharing only the generic term "meeting"). `limit=3` keeps every observed selection
on-topic across all six test queries below and stays well under `NOTE_BLOCK_BUDGET` (12,288 B).

### Mechanical acceptance (zero model calls; `_scoped_note_block()`/`assemble()` called directly)

| Query | card_pointers selected | Block bytes | Raw original present? |
|---|---|---:|---|
| **Fred/MLS**: "What happened in my meeting with Fred, and what did he say about MLS?" | `sources/intake/cards/d9cb4668....card.md` (the exact Fred/MLS card), `sources/historical_calls/cards/kenneth-meeting-may-27.card.md` | 4,966 | **No** — the 131,708 B original never appears; the only mention of `sources/intake/records/...` is the card's own citation link `[[...\|source]]`, not injected content |
| **CCI**: "What happened with CCI?" | `call-kenneth-after-first-cci`, `first-call-cci`, `cci-second-call-june-15` (all three genuinely CCI-related cards) | 7,262 | **No** |
| **Andrea Roberts**: "Did Andrea Roberts introduce us to anyone?" (real B7 question E5) | `andrea-roberts-june-26`, `andrea-second-call-june-30` (both genuinely about her) | 4,651 | **No** |
| **Negative control 1** (unrelated ordinary business question): "How many client work items are currently in human review?" | *(none)* | 192 (unchanged N/A block) | n/a |
| **Negative control 2** (trivial conversational): "Thanks, that is helpful." | *(none)* | 192 | n/a |
| **Fallback control** (no strong hit): "What should I focus on this week given everything going on?" | *(none)* | 192 | n/a — falls through unchanged to the existing tier-3/4 hierarchy, proving the escape route (depth-tool capability, the existing exact-search/fallback path) is preserved exactly as before |

**CCI is the harder case, reported plainly per the task's instruction:** the forensic audit's own
E3 session — David's live, model-driven, 7-round-trip search — never surfaced the CCI cards via
its own `search_calls`/`search_history` tool calls; it only found them later by **guessing exact
`.card.md` filenames** after failed searches. **This deterministic prefetch succeeds where E3's
own live search did not** — three genuinely relevant CCI cards, selected pre-model, zero
round-trips. This is a real improvement over the live baseline, not a partial one, though it
selects 3 of the 4 cards E3 eventually found by guessing (the 4th, `kenneth-sme-june-18`, ranked
below the `limit=3` cutoff; raising the limit to 5 was tested and rejected — see above — because it
introduced unrelated noise on the Fred/MLS query).

**Known, disclosed limitation (a genuine edge case the check surfaced, not swept under):** a
company-name collision. "Who founded Time to Revenue and when?" still pulls in one loosely-related
card (`mike-knapp-gtm-context-july-22`, matching "time"+"revenue" in its own title) because the
company's own name is also ordinary English vocabulary. This is low-cost surplus (one extra
~2-3 KB card, not a wrong answer, and the stable `identity/company` block already correctly
answers company-identity questions), not a correctness failure, and is named here rather than
hidden.

**Re-measurement of Part 1 after Repair 2** (full `assemble()`, zero model calls, TTROS-estimate
tokens; instructions+tools held at the Part-1 captured real bytes since Repair 3 made no code
change — see Part 4):

| Question | scoped canonical Brain notes (before → after) | Full first-request total (TTROS-est.) |
|---|---|---:|
| Fred/MLS | 192 B / 35 tok → 4,966 B / 952 tok | ≈25,614 tokens |
| CCI | 192 B / 35 tok → 7,262 B / 1,489 tok | ≈21,798 tokens |
| Andrea (E5) | 192 B / 35 tok → 4,651 B / 952 tok | ≈25,700 tokens (own question's smaller card + instructions/tools) |

Compare: the *live* cost of these same three questions under the pre-repair architecture was 7
provider round-trips / 165,287 tokens (CCI, forensic audit §6) and an E1-session-evidenced pattern
of 4 extra round-trips / ~26 KB of search payload for a Fred-shaped lookup (forensic audit §8). The
deterministic single-request cost after Repair 2 is within ~7% of the 24,043 direct-answer
baseline in every case measured — see the FRED SIZE REPORT below for the full breakdown.

---

## PART 4 — REPAIR 3: tool_describe, CONDITIONAL — arithmetic done, nothing changed

**Why `tool_describe` occurs, established from live config and the real captured request (Part 1),
not assumed:**

- The 29 tools in every request's `tools` array (40,088 B) are Hermes-**native** built-ins
  (`delegate_task`, `terminal`, `memory`, `execute_code`, `tool_search`, `skill_manage`,
  `search_files`, `browser_*`, `read_file`, `write_file`, `skill_view`, `tool_describe`,
  `tool_call`, `skills_list`, ...). **None of TTROS's own `mcp__brain__*` tools
  (`search_calls`/`open_call`/`open_note`/`search_history`) are in this array.**
- `~/.hermes/profiles/david/config.yaml` registers `brain` (and `queue`) as `mcp_servers` entries
  (`command`/`args`/`enabled`/`env` only — checked directly, no `eager`/`preload`/`schema` option
  exists anywhere in the live config). Hermes's own base toolset already includes a
  `tool_search`/`tool_describe`/`tool_call` triad — a **deliberate, by-design lazy-discovery proxy
  pattern** for exposing a large or dynamic tool surface (MCP servers in particular) without
  bloating every request's prefix with every MCP tool's full JSON schema. This is intentional
  Hermes architecture, not an oversight: it is exactly the mechanism `tool_describe` round-trips
  are the cost of.
- Per-tool byte cost, exact from the real captured request: 29 native tools average **1,382 B**
  each (40,088 B / 29); the forensic audit's own `tool_describe` result-payload table (§5) shows
  the **compact schema-doc format** Hermes returns for an MCP tool averages **608 B** (14 calls,
  441-1,011 B range) — the more relevant estimate for what preloading the 4 brain tools would add,
  since that is the same schema format that would populate the `tools` array.

**The arithmetic, run explicitly, per the task's test — and reported whether or not it changes
anything:**

- Estimated preload cost if the 4 brain tools were added to every request's `tools` array: ≈4 ×
  608 B ≈ 2,432 B ≈ 608 TTROS-estimated tokens, **added to the prefix, re-read and re-billed on
  every single provider request** — including every direct-answer, zero-tool question that gets no
  benefit from it at all.
- Round trips this would remove: **unmeasured after Repair 2**, and unmeasurable without a live
  model call, which this task makes none of. Using the **pre-repair** count as the most generous
  possible upper bound for preloading's case (it overstates the benefit, since it predates Repair
  2): 14 `tool_describe` calls across the 21-question pass, batched into at most 14 distinct
  round-trips (fewer in practice — E3 alone batched pairs into single turns) — call it ≤14 round
  trips saved, ≤14 × 28,884 ≈ 404,376 tokens, **against that same 21-question, 65-call pass only.**
- **The task requires the round-trip count measured AFTER Repair 2**, not this pre-repair upper
  bound. Repair 2 (Part 3) is designed to intercept exactly the retrieval pattern that drove most
  of this `tool_describe` traffic in the first place (search_calls/search_history/open_note
  discovery for knowledge/history/source questions — the E1/E3/B3 pattern) by answering it
  pre-model instead. The expected effect of Repair 2 is therefore to **shrink the numerator
  (round trips saved) sharply** while the denominator (total provider requests, including every
  direct-answer question that would pay the fixed preload tax regardless) does not shrink at all.
  This is the same conclusion the task's own text anticipates: *"If Repair 2 has already removed
  most tool_describe traffic, the honest answer is likely that preloading is no longer worth a
  permanent cost on every call."*

**Mechanism check, independent of the arithmetic:** even if the arithmetic favoured preloading,
`~/.hermes/profiles/david/config.yaml`'s `mcp_servers` block exposes no eager-schema option today.
Achieving eager preload would require either patching Hermes itself (forbidden by this task's hard
boundary) or inventing a workaround (also forbidden — "do not invent a workaround").

**Decision: no change.** Both the mechanism (no existing non-Hermes-patching path to preload MCP
tool schemas) and the arithmetic (a fixed per-request tax against an expected-to-shrink, currently
unmeasurable benefit) point the same direction. Nothing in `tools/context_assembler.py`,
`config.yaml`, or the MCP server registration was touched for this repair. Re-measurement of Part 1
after Repair 3: **no change, because no code changed.**

---

## SIZE REPORT — Fred/MLS, final, all repairs applied

`assemble()` called locally, zero model calls; instructions/tools bytes are the real captured
values from Part 1's dump (assumed stable within this session's pass, as stated there).

| Component | Bytes | TTROS-est. tokens |
|---|---:|---:|
| Stable/reference (5 stable-prefix blocks: identity/company, current priorities, executive_view, action boundaries, execution handoff contract) | 10,295 | 2,125 |
| Working/suffix (10 dynamic blocks incl. morning findings, matching skills/workflows, provenance, etc.) | 30,342 | 6,347 |
| — of which retrieved evidence (`scoped canonical Brain notes` — the Fred card + 1 more) | 4,966 | 952 |
| Question text | 69 | ~14 |
| **Assembled-context + question subtotal** (`input[0].content`) | 43,414 | 9,017 |
| Tool definitions (29 Hermes-native tool schemas) | 40,088 | 10,933 |
| Instructions (persona + Hermes native skills catalog + memory + runtime env) | 27,384 | 5,666 |
| **TOTAL REQUEST** | **110,886** | **≈25,616** |
| vs. 24,043 direct-answer baseline (real, provider-exact tokens) | — | **+6.5%** (1.065×) |

**No invented savings, reported plainly:** this is *not* smaller than the direct-answer baseline —
it is slightly larger, because Repair 2 correctly adds ~950 tokens of genuinely relevant retrieved
evidence that a pure direct-answer question doesn't need. The lever that moved is not "smaller than
baseline," it's **"one request instead of many"**: the same live question pattern (E1's real
"Fred" search) cost 4+ extra provider round-trips and ~26 KB of search payload before this repair;
CCI's real E3 session cost 7 round-trips and 165,287 tokens. This repair's request, at ≈25,616
tokens in one call, is within single-digit percent of the cheapest baseline case TTROS has ever
measured for *any* question shape — a ~6×-to-~17× reduction versus the live multi-turn cost for
these specific question types, achieved by never spending the multi-turn cost in the first place.

---

## REGRESSION

**Focused suite** (`.venv/bin/python -m pytest`, zero model calls — all local/deterministic):

```
tests/test_one_brain_context.py tests/test_b6_source_disposition.py
tests/test_hermes_context_plugin.py tests/test_step7_8_context_hygiene.py
tests/test_source_intake.py tests/test_step5_morning_brief.py tests/test_business_brain_context.py
```
→ **77 passed, 2 failed** (10/30 subtests passed across runs; count varies slightly with the
byte-budget fix applied). Both failures, examined individually:

1. `test_one_brain_context.py::test_matching_workflow_projection_keeps_selection_order_and_full_behavior_contract`
   — **caused by Repair 1** (the +362 B disambiguation sentence pushed `block.byte_count` from
   under 8,000 to 8,300 for this test's specific query). **Fixed**: bumped the asserted ceiling to
   8,500 with a comment naming the cause (`tests/test_one_brain_context.py`). This is a deliberate,
   disclosed accommodation of new correct behavior, not a loosened correctness check — every other
   assertion in that test (selection order, exact source list, content markers) is unchanged and
   still passes.
2. `test_one_brain_context.py::test_revenue_entities_and_activity_are_selected_automatically` —
   **pre-existing, confirmed unrelated to this task.** Fails identically with this task's changes
   reverted (checked directly by comparing against the pre-repair code before making any edits, via
   a `git stash`/`stash pop` round-trip — recorded here because that round-trip briefly staged
   three already-modified executive-brief artifacts and required care to recover cleanly without
   losing pre-existing dirty-tree state; resolved by re-checking out the stash's copy of those three
   files before popping, then unstaging — no content was lost). Root cause: a scope-validation gap
   in `dashboard/backend/business_brain_graph.py`'s graph-discovery path
   (`ClientScopeError: Business Brain pointer does not belong to global:
   business_brain:sources/intake/INDEX.md`) — the client-scope registry's `global` scope does not
   yet permit `sources/intake/` as a graph target, a gap most likely left by the recent STEP
   I1/I2/I3 ingestion work that created that directory tree. **Not touched** — out of this task's
   scope (graph service / client-scope registry, not the Context Assembler retrieval this task
   repairs), and CLAUDE.md instructs continuing past a repairable failure only within the declared
   boundary; this one sits outside it.

Also separately confirmed: `test_hermes_context_plugin.py::test_unregistered_profile_receives_no_context`
fails with `PermissionError: [Errno 13] Permission denied: hooks/context_assembler_hook.py` when
run alongside the others — a subprocess-execute-bit gap on a file this task never touched (its git
mode is `100644`, non-executable, unchanged from `HEAD`, and this task made no edits to that file).
Pre-existing, unrelated, not fixed here for the same reason.

**`git diff --check`** (whitespace-error check on the touched files): **clean, exit 0.**

**Full suite** (`.venv/bin/python -m pytest -q`, same zero-model-call constraint, run after the
focused subset above): **828 passed, 1 failed, 829 collected, 223 subtests passed** (354 s).
The 1 failure is `test_hermes_context_plugin.py::test_unregistered_profile_receives_no_context`
— the same pre-existing `PermissionError` on `hooks/context_assembler_hook.py` named above.
**`test_revenue_entities_and_activity_are_selected_automatically` (the graph-scope failure) passed
in this full run** — it only fails in the smaller, isolated focused-subset invocation, indicating
test-order/isolation-dependent flakiness in that pre-existing test, not a fresh regression; either
way it is confirmed unaffected by this task's edits (reproduced identically with this task's code
changes reverted, before any edits were made). **Authoritative population count for this
closeout: 828/829 passed, both by full-suite run and by direct correspondence with CLAUDE.md's own
baseline convention.**

**Test population reconciliation:** `pytest --collect-only -q` → **829 tests collected**, against
CLAUDE.md's stated 772/804 baseline. **This is not a shortfall — 829 exceeds both figures.**
Explained exactly by the dirty tree's own file list (not this task's doing): one test file deleted
(`tests/test_aos_dashboard_cleanup.py`) and three added since that baseline was recorded
(`tests/test_b6_source_disposition.py`, `tests/test_b7_test_material_guard.py`,
`tests/test_validation_a_seal_guard.py`) — net +2 files, consistent with a population that grew
past the recorded baseline through legitimate intervening work, not a stale or broken count.

**Protected areas:** `connectors/telegram_bridge/` and `workspaces/north_shore_sales_coach/` —
**not touched**, not read beyond what `pytest.ini`'s own `--ignore`/`norecursedirs` already
exclude from collection. No Telegram bridge edits. No North Shore work.

---

## CLOSEOUT

**Recommend: PASS**, with two disclosed, pre-existing, out-of-scope items named below rather than
hidden. (Recommendation only — Liam decides the status.)

**Model calls: 0. David/Hermes/provider turns: 0.** Every measurement in this task is either a
direct read of pre-existing on-disk evidence (state.db, request-dump files, usage.json files,
context-assembly manifests, the live search index) or a local, deterministic Python call
(`assemble()`, `_scoped_note_block()`, `_card_search_pointers()`, `aos_indexer.search()`) — never a
`hermes` invocation, never a dispatch to a provider. No B7, no E5/F-question resumption, no scorer
work.

**Baseline (Part 1):** the first-request payload for a real, previously-dispatched B7 question
(E5, "Did Andrea Roberts introduce us to anyone?") decomposes exactly: instructions 27,384 B,
tools 40,088 B, question 42 B, assembled context 25,363 B (22,651 B across 15 named blocks + 2,712
B of scaffolding), total request 94,102 B — reconciled to within 1.3% (pure JSON structural
overhead, named not mysterious). Morning findings measured at 99 B (not the 13,166 B the build
plan named — confirmed request-specific, not fixed); matching skills/workflows measured at 7,779
B (close to the 8,494 B named). The two largest genuinely unmeasured-before-this-task components
were the 40,088 B tool-definition array and Hermes's own native skills catalog inside
`instructions` — neither previously named in the build plan, both Class C for an ordinary
knowledge question, neither touchable without patching Hermes.

**Repair 1:** root cause established from the real message trace, not assumed — David treats
TTROS's own `matching skills/workflows` block's `id=` projections as Hermes-native
`skill_view`-addressable names, driven by Hermes's own "you MUST load it with skill_view" system
instruction. Five of seven affected questions got "Skill not found"; two (a correction to the
prior audit) got a real but irrelevant Hermes-native skill instead. Fixed with one disambiguating
sentence in the block's own preamble; mechanically proven present and correctly triggered on the
exact failing query; **live one-call behaviour is explicitly unproven — stated as an open
expectation, not a result, because proving it needs a model call this task makes none of.**

**Repair 2 (the main repair):** root cause established directly against the live search
index — the existing exact-search stage's `exact=True` phrase-match never matches natural-language
questions (0 results, verified on three representative questions before writing any code). Fixed
by feeding `_query_terms()`/`_entity_name_terms()` into the same `aos_indexer.search()` function
with OR-of-terms matching, restricted to card paths only, gated by a term-overlap/strength
threshold that was tightened after two real negative-control failures were caught in testing (not
swept under). Mechanically proven: Fred/MLS and CCI cards now selected pre-model (the CCI case is
harder and succeeds where the live E3 session's own multi-round search did not); both negative
controls and the fallback control correctly select nothing and fall through unchanged to the
existing retrieval hierarchy, proving the escape route survives. One disclosed edge case remains
(a company-name/common-word collision) — named, not hidden.

**Repair 3:** established that Hermes's tool-discovery design is deliberate (native
`tool_search`/`tool_describe`/`tool_call` proxy pattern), that no config-level preload mechanism
exists today, and that the arithmetic — using the most generous possible pre-Repair-2 upper bound —
does not clearly favour preloading once Repair 2's expected reduction in brain-tool traffic is
accounted for, while the live config confirms preloading isn't achievable without patching Hermes
regardless. **Decision: no change. Nothing was preloaded, nothing was touched.**

**Fred total vs. baseline:** the full first request for the Fred/MLS question, all repairs applied,
totals ≈110,886 B / ≈25,616 TTROS-estimated tokens — **+6.5%** over the 24,043 real-provider-token
direct-answer baseline, because it correctly now includes ~950 tokens of genuinely relevant
retrieved evidence a pure direct-answer question doesn't need. The win is not "cheaper than
baseline" — it is **"one request instead of many"**: this same question pattern previously cost
4+ extra live round-trips (Fred, ~26 KB search payload) or 7 round-trips / 165,287 tokens (CCI,
measured directly in the forensic audit).

**Tests:** 828/829 passed in the full local suite (zero model calls); the 1 failure is a
pre-existing, unrelated file-permission gap on `hooks/context_assembler_hook.py`, confirmed
untouched by this task. `git diff --check`: clean. Protected areas (Telegram bridge, North Shore)
untouched. Test population (829 collected) exceeds the CLAUDE.md 772/804 baseline because of net
new test files added in the intervening dirty tree, not a shortfall.

**What remains between here and a genuinely lean first request, named specifically:**

1. **Belongs to Step 8, not here (named, not shrunk):** `deterministic morning findings` and
   `matching skills/workflows` are real, substantial, request-variable blocks that Step 8's own
   text names for "a digest or behind tools." This task measured them (Part 1) and repaired one
   correctness defect inside `matching skills/workflows` (Repair 1) but did not cut their size —
   explicitly out of this task's boundary ("measure the bookkeeping, do not shrink it").
2. **Belongs to Step 8 or a Hermes-side change, not TTROS's `context_assembler.py`:** the 40,088 B
   native tool-definition array and Hermes's own `available_skills` catalog inside `instructions`
   are both Class C for most ordinary questions but are Hermes-native surface area this task's "no
   Hermes patching" boundary puts out of reach. Named here as the single largest lever this task
   found and could not act on.
3. **Not this task's problem, but blocking full-suite green:** the `hooks/context_assembler_hook.py`
   permission gap and the client-scope registry's missing `sources/intake/` graph-target
   permission (test-order-dependent) are both pre-existing and unrelated to token efficiency —
   named for whoever owns test/permissions hygiene next, not fixed here.
4. **An honest limitation of Repair 2, not a defect:** the company-name/common-English-word
   collision (Part 3) — acceptable low-cost surplus today, but worth a second look if it recurs on
   other common-word entity names.

**The single live acceptance question to run LATER, when quota returns (write, do not execute):**

```
hermes -p david -z "What happened in my meeting with Fred, and what did he say about MLS?"
```

Check, post-run, against `~/.hermes/profiles/david/state.db`'s `sessions`/`messages` for this
session id: (a) `api_calls == 1` (one provider round-trip, no `skill_view`/`tool_describe`/
`search_calls`/`open_note` tool call at all); (b) the answer correctly names Fred, MLS/GVR data
access, and the realtor-workflow-tracking content from the card; (c) the assembled-context manifest
in `queue/context_assemblies/` for that invocation shows the Fred/MLS card under `scoped canonical
Brain notes` with `route=pointer`. A PASS on all three is the first real evidence (this task
provides none) that Repairs 1 and 2 change David's actual live behaviour, not just the
deterministic payload construction proven here.

No commit. No push.
