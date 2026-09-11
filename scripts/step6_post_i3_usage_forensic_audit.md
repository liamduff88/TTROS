# Post-I3 B7 usage forensic audit — ZERO model calls

Scope: read-only forensic reconciliation of why the post-I3 B7 pass consumed ~1.69M tokens, and
whether Step 6's brain MCP tools have turned deterministic retrieval into a David→tool→David
model-call loop. No David/Hermes/provider call made. B7 not resumed. No scorer, architecture, or
production code changed. Nothing committed, nothing pushed.

**Evidence used, all pre-existing on disk:**
- `scripts/step6_post_i3_b7_pass.raw.json` (21 successful records; the pass is marked
  `"aborted": true`, `actual_calls: 21` of declared max 25 — questions E5/F1/F2/F3 all failed with
  `HTTP 429: The usage limit has been reached`, confirmed in
  `scripts/step6_post_i3_b7_pass.transcript.txt`, both on the original attempt and a resume attempt).
- `scripts/step6_post_i3_b7_pass_{A1..F3}.usage.json` (per-question Hermes `--usage-file` output).
- `~/.hermes/profiles/david/state.db` (`sessions`, `messages` tables — read-only queries only).
- `search/os_index.db` (`documents` table — read-only).
- `tools/context_assembler.py` (`assemble()`, `_scoped_note_block()`, `_direct_fallback()`,
  `_known_entity_pointers()` — read only, not modified).
- Live vault (`/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain/`) — read only.
- `logs/token_usage.jsonl` — checked and found to be a **different surface** (gateway/dashboard
  "Executive consultation: David" daily cadence calls), zero overlap with the 21 CLI-David B7
  sessions. Named per CLAUDE.md's "state the surface" rule; not used further.
- `queue/receipts/AOS-2026-0489-step6-usage-report.json` — checked, is an unrelated single
  invocation from 2026-08-04, not the source of this task's reconciliation numbers.

Surface declared throughout: **CLI-David** (`hermes -p david -z`), `gpt-5.5` / `openai-codex`, per
`scripts/step6_b7_tools_harness.py`'s own transcript header.

---

## 1. Per-question table (all 21 successful post-I3 questions)

`api_calls` = actual provider/model requests (Hermes' own count, from `--usage-file`).
`tcc` = `tool_call_count` from David's own session row in `state.db` (individual tool invocations,
which can be batched — see §3). Disposition classification reuses
`step6_b7_tools_harness.py::classify_round_trip`'s own three-way rule.

| Q | api_calls | input | output | reasoning | cache_read | cache_write | total_tokens | tcc | tool names used | disposition |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| A1 | 4 | 30,049 | 990 | 182 | 73,216 | 0 | 104,255 | 6 | skill_view×2, tool_describe, open_note×2, search_history | brain_tool |
| A2 | 1 | 23,330 | 279 | 45 | 0 | 0 | 23,609 | 0 | — | direct |
| A3 | 1 | 11,280 | 857 | 118 | 12,800 | 0 | 24,937 | 0 | — | direct |
| A4 | 2 | 23,783 | 551 | 90 | 22,016 | 0 | 46,350 | 1 | skill_view (failed) | other_tool |
| A5 | 3 | 15,111 | 727 | 357 | 55,808 | 0 | 71,646 | 3 | tool_describe, skill_view, search_history | brain_tool |
| B1 | 1 | 10,953 | 488 | 71 | 12,800 | 0 | 24,241 | 0 | — | direct |
| B2 | 1 | 10,612 | 830 | 96 | 12,800 | 0 | 24,242 | 0 | — | direct |
| B3 | 4 | 16,273 | 855 | 162 | 83,968 | 0 | 101,096 | 5 | tool_describe, open_note×4 | brain_tool |
| B4 | 2 | 9,488 | 1,066 | 217 | 33,792 | 0 | 44,346 | 1 | skill_view | other_tool |
| C1 | 6 | 35,980 | 1,779 | 508 | 121,344 | 0 | 159,103 | 9 | skill_view, tool_describe×2, search_history×2, open_note×4 | brain_tool |
| C2 | 2 | 24,139 | 582 | 146 | 22,016 | 0 | 46,737 | 1 | skill_view | other_tool |
| C3 | 1 | 10,116 | 558 | 270 | 12,800 | 0 | 23,474 | 0 | — | direct |
| C4 | 2 | 11,930 | 1,422 | 130 | 35,840 | 0 | 49,192 | 1 | skill_view | other_tool |
| D1 | 2 | 15,529 | 322 | 68 | 37,888 | 0 | 53,739 | 1 | skill_view | other_tool |
| D2 | 2 | 12,892 | 709 | 61 | 35,840 | 0 | 49,441 | 1 | skill_view | other_tool |
| D3 | 1 | 10,775 | 177 | 50 | 12,800 | 0 | 23,752 | 0 | — | direct |
| D4 | 2 | 12,483 | 240 | 106 | 36,864 | 0 | 49,587 | 1 | skill_view | other_tool |
| E1 | 14 | 34,501 | 1,986 | 495 | 373,760 | 0 | 410,247 | 13 | skill_view, tool_describe×3, search_calls×3, list_resources, open_call, open_note×2, search_history, read_file | brain_tool |
| E2 | 3 | 19,580 | 976 | 90 | 50,688 | 0 | 71,244 | 2 | tool_describe, open_note | brain_tool |
| E3 | 7 | 20,139 | 1,276 | 199 | 143,872 | 0 | 165,287 | 13 | tool_describe×4, search_history×2, search_calls, open_note×6 | brain_tool |
| E4 | 4 | 45,221 | 1,018 | 230 | 79,872 | 0 | 126,111 | 5 | skill_view, tool_describe, open_call×3 | brain_tool |
| **Σ** | **65** | **404,164** | **17,688** | **3,691** | **1,270,784** | **0** | **1,692,636** | | | |

Dispositions: **direct = 6** (A2,A3,B1,B2,C3,D3 — all `api_calls=1`), **other_tool = 7**
(A4,B4,C2,C4,D1,D2,D4 — all a single `skill_view`, none of the new Step-6 brain MCP tools),
**brain_tool = 8** (A1,A5,B3,C1,E1,E2,E3,E4 — at least one of
`search_calls`/`open_call`/`open_note`/`search_history`).

---

## 2. Reconciliation of the four headline numbers — exact, not approximate

Summed directly from the 21 `usage.json` files (`python3` sum over `raw.json` records):

- **Input: 404,164** — exact match.
- **Output: 17,688** — exact match.
- **Reasoning: 3,691** — exact match.
- **Total: 1,692,636** — exact match.

**The gap is closed exactly, not approximately.** For every one of the 21 records,
`total_tokens == input_tokens + output_tokens + cache_read_tokens + cache_write_tokens`
(verified record-by-record; e.g. A1: 30,049+990+73,216+0 = 104,255, matching the reported total to
the token). Summed: 404,164 + 17,688 + 1,270,784 + 0 = **1,692,636** — exact.

`reasoning_tokens` (3,691) is **not** a fifth additive bucket — it is a nested subset already
counted inside `output_tokens` (confirmed by the arithmetic above closing exactly without adding
it; this is GPT-5.5/openai-codex's own accounting convention for reasoning-model output).

**The "1.27M gap" is cache_read_tokens, in full: 1,270,784 tokens, 75.1% of the entire spend.**
Not a mystery bucket, not double-counting, not an accounting bug — it is prompt-cache reads,
evidenced and quantified in §4 below. `cache_write_tokens` is 0 across all 21 records with no
exception — see §4's caveat on what this does and does not prove.

---

## 3. Does every tool round-trip cause another provider request? — YES, with one refinement

Every session with `tool_call_count == 0` has exactly `api_calls == 1` (A2,A3,B1,B2,C3,D3 — 6/6,
no exception). Every session with `tool_call_count >= 1` has `api_calls >= 2` (15/15, no
exception). **Tool use always costs at least one additional full provider request.**

The refinement: `api_calls` does not equal `tool_call_count + 1` in every case, because Hermes can
batch **multiple parallel tool calls into a single assistant turn** (confirmed directly in the
message trace — e.g. E3's turn at message id 1227 issues five `open_note` calls in one assistant
message, id 1218 issues two `tool_describe` calls in one). The real relationship is:

**`api_calls` = (number of distinct request-turns that contained at least one tool call) + 1 (final
answer turn).**

This is confirmed exactly: for every single-tool-call session (`tcc=1`: A4,B4,C2,C4,D1,D2,D4),
`api_calls=2` (1 tool-turn + 1 final), no exception. For `tcc=0`, `api_calls=1`. For higher `tcc`
with batching (e.g. E3: 13 individual tool calls compressed into 6 distinct turns, `api_calls=7`;
E1: 13 tool calls across 13 turns with **no** batching, `api_calls=14`), the turn-count model holds
in every row of the table above.

**Conclusion: YES, tool use triggers repeated model calls, every time, without exception in this
21-question dataset.** Parallel tool-call batching reduces the *number* of extra round-trips below
"one per tool call," but never eliminates them — any tool activity at all costs at least one full
extra provider request.

---

## 4. Is the large stable/system context repeated and accounted on every subsequent turn? — YES

**Direct evidence, not inference.** Every direct-answer session (`api_calls=1`, no tools) shows a
`cache_read_tokens` value of either 0 (A2 only) or **exactly 12,800** (A3, B1, B2, C3, D3 — five
of six, bit-for-bit identical). A single first-and-only provider call in these sessions already
reads ~12,800 tokens of *pre-existing* cached content — content this specific session did not
write to cache; it was already warm from a previous invocation sharing the same static system
prompt / tool schema block. This 12,800-token figure is the stable-context floor.

**Regression across all 21 questions (total_tokens vs. api_calls): r² = 0.989.** Slope = **28,884
tokens per additional provider round-trip.** This is a near-perfect linear relationship — the
single strongest predictor of a question's total token cost is simply how many provider requests
it took, not what was asked or what was found. A ~29K-token, largely-fixed context (system prompt +
tool schemas + accumulating conversation/tool-result history) is being read from cache and counted
on every single turn of a multi-turn session, exactly as the "context re-sent every turn" hypothesis
predicts.

**Per-request breakdown (first/second/third call individually) is not directly recoverable.**
Hermes' `--usage-file` and `state.db`'s `sessions`/`session_model_usage` tables both aggregate at
the **session** level only — there is no per-API-call token ledger in the schema (checked directly:
`messages.token_count` is `NULL` for every row in every one of these 21 sessions). The session-level
aggregate and the regression above are the strongest evidence obtainable from existing
instrumentation; a true first/second/Nth-call breakdown would require new logging, which this task
does not authorize.

**Cached vs. uncached:** `cache_write_tokens = 0` in all 21 records, with no exception. This is
worth flagging as an evidence gap in its own right: heavy, repeated cache *reads* are proven, but
this dataset contains **zero evidence of any cache write ever being billed/reported** for these
sessions — meaning either (a) the cache is populated by a different, unlogged mechanism/session
outside this measurement, or (b) this provider's accounting does not surface write costs the same
way it surfaces reads. Not resolved further here — flagged as an open instrumentation question,
not asserted as a bug.

---

## 5. Actual tool-result payload sizes (bytes, from `messages.content` in `state.db`)

| tool | n | min | max | avg | sum |
|---|---:|---:|---:|---:|---:|
| `mcp__brain__open_call` | 4 | 442 | 46,252 | 28,477 | 113,909 |
| `mcp__brain__open_note` | 19 | 1,747 | 50,229 | 5,990 | 113,812 |
| `mcp__brain__search_history` | 7 | 7,009 | 17,410 | 9,556 | 66,890 |
| `skill_view` | 13 | 427 | 15,455 | 2,675 | 34,771 |
| `mcp__brain__search_calls` | 4 | 543 | 19,850 | 7,502 | 30,006 |
| `tool_describe` | 14 | 441 | 1,011 | 608 | 8,513 |
| `read_file` | 1 | 2,301 | 2,301 | 2,301 | 2,301 |
| `mcp__brain__list_resources` | 1 | 17 | 17 | 17 | 17 |

**`open_call` vs. `open_note` — confirmed "both, depending on path," not one behavior:**

- **`open_note` pointed at a `.card.md` path returns the compact card**, not the original. Directly
  observed: E3's five `open_note` calls on `sources/historical_calls/cards/{first-call-cci,
  cci-second-call-june-15,call-dr-kenneth-after-second-cci,kenneth-sme-june-18}.card.md` returned
  1,747–3,755 bytes each — matching the ~3.2KB card format seen directly in the vault
  (`sources/intake/cards/*.card.md` is 3,177 B on disk, confirmed by direct read in §8).
- **`open_note` pointed at the raw original path returns the full original**, no card substitution.
  Directly observed: E2's session called `open_note({"pointer":
  "sources/historical_calls/mike-knapp-gtm-context-july-22.md"})` (the raw path, not
  `.../cards/....card.md`) and received **50,229 bytes** back — the entire ~45KB memo, the single
  largest tool-result payload in the whole dataset.
- **`open_call` (by `call_id`) returns the full original transcript, always, in this dataset.**
  E4's three `open_call` invocations (`trent-first-call`, `trent-july-9`,
  `hermes-water-treatment-summary-trent`) returned 46,252 / 43,125 / 24,090 bytes — full transcripts,
  not cards, totaling 113,467 bytes (≈28,000 tokens) in one question. E1's `open_call({"call_id":
  "INDEX"})` returned only 442 bytes because `INDEX` itself is a short index file, not because
  `open_call` compresses content — confirming `open_call` returns whatever the target document's
  actual size is, unfiltered.

**Conclusion for Q5: `open_note` is path-dependent (card path → compact card; raw path → full
original); `open_call` returns full originals unconditionally.** Both behaviors are real and both
were exercised inside this single 21-question pass.

---

## 6. E3 deep dive — complete flow and cost

**Question:** "What happened with CCI?" — session `20260909_191442_1879a9`.

**Step 1 — deterministic pre-model assembly** (`tools/context_assembler.py::assemble()`, read from
the manifest embedded in `raw.json`'s E3 record):
- `request_bytes: 23, request_tokens: 5` — the user's question text itself.
- `total_bytes: 15,296, total_tokens: 3,155` — the entire deterministically-assembled context:
  `memory/company.md`, `operating_context/current_priorities.md`,
  `operating_context/executive_view.md`, `context/MORNING_BRIEF_FINDINGS.json`, plus queue/session
  bookkeeping blocks. **No CCI-specific document was included by the deterministic assembler** —
  `_scoped_note_block`'s explicit-search stage found nothing CCI-specific for this query (see §8 for
  why).
- `classification: knowledge_sensitive`, `retrieval_hierarchy: [explicit_pointer,
  graphify_one_hop, exact_search, direct_canonical_fallback]`, `whole_vault_default: False`.

**Step 2 — model request #1** (turn id=1217→1218): model receives the ~3,155-token assembled
context + question, responds with two parallel `tool_describe` calls
(`mcp__brain__search_history`, `mcp__brain__search_calls`) instead of an answer.

**Step 3 — tool round 1** (id=1219–1220): `tool_describe` × 2 return schema docs (488 B, 581 B).

**Step 4 — model request #2** (id=1221): issues `search_history({"query":"CCI OR TRACC"})` and
`search_calls({"query":"CCI TRACC"})` in parallel.

**Step 5 — tool round 2** (id=1222–1223): `search_history` returns 7,324 B of snippets;
`search_calls` returns 5,388 B. **Neither the CCI call transcripts nor their cards are named in
these results** (matching the earlier `step5_step6_b7_reconciliation_audit.md` finding that E3's
searches surfaced only canonical notes, never the transcripts, in the pre-I3 pass — this post-I3
run shows the model compensating differently, see next step).

**Step 6 — model request #3** (id=1224): two more `tool_describe` calls
(`mcp__brain__open_note`, `mcp__brain__open_call`).

**Step 7 — tool round 3** (id=1225–1226): schema docs, 457 B + 441 B.

**Step 8 — model request #4** (id=1227): issues **five parallel `open_note` calls** —
`business_brain:memory/clients.md` and four `.card.md` pointers:
`first-call-cci.card.md`, `cci-second-call-june-15.card.md`,
`call-dr-kenneth-after-second-cci.card.md`, `kenneth-sme-june-18.card.md`.

**Step 9 — tool round 4** (id=1228–1232): returns 1,747 B (`clients.md`) + 3,703/3,705/3,755/3,674 B
(the four compact I1 cards — **not** the full original transcripts). This is the STEP I1 card
system working exactly as designed, and it is materially cheaper than E4's full-transcript opens
(§5) for equivalent coverage — but see below for what it still misses.

**Step 10 — model request #5** (id=1233): `search_history({"query":"\"Full detail\" \"CCI/TRACC\"
OR \"Loss Mirror\""}, limit=10)` — a broader retry.

**Step 11 — tool round 5** (id=1234): 8,984 B returned.

**Step 12 — model request #6** (id=1235): `open_note("business_brain:index/MEMORY_INDEX.md")`.

**Step 13 — tool round 6** (id=1236): 7,468 B returned.

**Step 14 — model request #7 (final answer)** (id=1237): 2,469-character synthesized answer
(quoted in full in `raw.json`). Correctly states Ollie/Graham/Kenneth Moodley, the "Loss Mirror"
thesis, and "benched, not dead" — but **never states either call date (Jun 10 / Jun 15)**, because
neither the compact cards it opened nor the original transcripts (never opened this session) were
asked to surface a literal date, and the cards themselves are semantic summaries, not
date-stamped transcripts.

**Total cost for this one question: 7 provider requests, 13 individual tool invocations across 6
tool-bearing turns, 165,287 tokens** (20,139 input + 1,276 output + 143,872 cache read) — **≈6.9×**
the direct-answer baseline (§9) for a single user question.

**What the capability improvement bought:** correct entity/status synthesis from compact,
cheap-to-open I1 cards (a real, working improvement over full-transcript opens) — at the cost of 6
extra provider round-trips whose primary expense (87% of this question's tokens) was cache-read
re-accounting of stable context, not the card payloads themselves (the five cards totaled only
~16.6 KB, ≈4,150 tokens, out of 165,287 total).

---

## 7. Live flow vs. intended architecture

**Intended (per CLAUDE.md / rev11 design):** "Liam → deterministic assembly → ONE David call,"
with depth tools only where genuinely necessary.

**What is actually true, confirmed by direct evidence:**

1. **The deterministic Context Assembler is real, lean, and working as designed.** E3's manifest
   proves it: ~3,155 tokens assembled pre-model, not 20K+. This part of the architecture is not
   compromised.
2. **"ONE David call" is the normal path only for 6 of 21 questions (28.6%).** For the other 15
   (71.4%), David's own agentic loop inside the Hermes session — not the Context Assembler —
   independently issues tool calls, and **every** such session costs ≥2 provider requests (§3),
   with a mean of 5.6 requests and a max of 14 (E1) among the 8 questions that reached a new
   Step-6 brain MCP tool.
3. **Every additional round-trip re-pays a near-fixed ~28.9K-token tax (§4, r²=0.989),** which is
   not primarily the tool payload (§5's actual payloads are 0.4–50 KB, i.e., ~100–12,500 tokens) —
   it is the stable/system/conversation context being re-read from cache on every turn. This is the
   dominant cost driver, confirmed quantitatively, not asserted qualitatively.
4. **Depth tools are not always used "only where genuinely necessary" in the minimal sense implied
   by the design** — 7 of 21 questions (A4,B4,C2,C4,D1,D2,D4) spent a second provider round-trip on
   a **single `skill_view` call that then failed** ("Skill not found," per the prior reconciliation
   audit's Check 3 findings on A4/C4), paying the full ~2× cost penalty for zero retrieved content.

**Verdict: Step 6's brain MCP tools function as a second, David-invoked retrieval layer bolted on
top of the deterministic assembler, not as a replacement for or extension of it.** The assembler
still runs once, deterministically, cheaply, exactly as designed. What has drifted is that a
majority of questions no longer stop at "one call" — the model, not the assembler, decides
mid-session to go looking for more, and that decision is expensive per the mechanics above. This is
**consistent with the assembler's own design intent being preserved**, and **inconsistent with**
"ONE David call" describing the *typical* post-Step-6 request.

---

## 8. The Fred/MLS test — current path vs. an existing-components path

**Real corroborating evidence already in this dataset (not a live invocation — this pass's own
E1 session, "Which historical calls do we have on file, and who was in each?", spontaneously went
looking for a "Fred"):** its message trace shows `search_calls({"query":"Fred","limit":20})` →
4,225 B, then `search_history({"query":"\"Fred Haiderzada\" OR Haiderzada","limit":20})` →
**17,410 B**, then `open_note("sources/intake/records/d9cb...md")` → 2,364 B, then a `read_file` on
a Hermes-internal spillover cache file → 2,301 B. Four extra tool round-trips, ~26 KB of
search-result payload, purely to locate one document by name.

**The document already exists, is already indexed, and is already summarized as a compact card,**
confirmed by direct read this session (zero model calls):
- `sources/intake/records/d9cb4668fd766474278e414bb53223f944342004f34be23020c161fa4160dd74.md` —
  131,708 B, the full original meeting transcript ("Fred Haiderzada meeting sept 9th.txt").
- `sources/intake/cards/d9cb4668fd766474278e414bb53223f944342004f34be23020c161fa4160dd74.card.md` —
  **3,177 B**, titled *"Fred discusses realtor workflow tracking, MLS reports, dashboards, CRM, and
  possible market-data product ideas,"* with explicit sections including "What MLS or GVR data
  access will be available?" — directly answering both halves of "what happened... and what did he
  say about MLS."
- `search/os_index.db` already carries both as indexed `documents` rows (ids 4306/4307), with the
  card's title fully searchable text.

**Current execution path for this question, given the above:** identical in kind to E1's real
behavior — the deterministic assembler's `_scoped_note_block` would not surface this card
pre-call (see below), so David's own session would have to search for "Fred"/"MLS" via
`search_calls`/`search_history`, paying at least one extra provider round-trip and a five-figure
byte search payload, before (maybe) calling `open_note` on either the 3.2KB card or the 132KB raw
record.

**Why the deterministic assembler doesn't already do this, read directly from
`tools/context_assembler.py`:** `_scoped_note_block()` (lines 436–607) does have a working
exact-search stage — `ScopedBrainLoader.retrieve(..., discovery_mode="explicit",
search_db_path=...)` — wired to the same `search/os_index.db` FTS index that already contains and
correctly titles the Fred/MLS card. But entity/keyword resolution feeding that search is currently
narrow: `_known_entity_pointers()` only matches against `business_brain:prospects/*.md` pointers,
and `_direct_fallback()` only matches five hardcoded topic buckets (offer/pricing,
position/claim, sales/revenue/outreach, ideal client/ICP, company/TTROS). **A bare proper name like
"Fred," or a topic like "MLS," is not in either list, so the exact-search stage is never given a
reason to look at `sources/intake/cards/` or `sources/historical_calls/cards/` for it.**

**What existing components could already deterministically identify and insert the Fred card
before the David call, without inventing new architecture:** the same `ScopedBrainLoader` /
`search_db_path` FTS mechanism `_scoped_note_block()` already calls, given a wider set of query
terms to check against — i.e., feeding the user's own extracted keywords/proper nouns (already
computed by `_query_terms()`/`_entity_name_terms()`, currently used only to gate the narrow
`prospects/` and topic-bucket lookups) into an FTS query against `search/os_index.db` across the
intake/historical-call card paths, the same index that already contains the answer. **Not
implemented here, per the task's explicit instruction.**

---

## 9. Cost decomposition

| Component | Value | Evidence |
|---|---|---|
| Base first-model-call cost (direct, no tool) | **~24,043 tokens avg** (6 qs, all `api_calls=1`; range 23,474–24,937) | §1 table |
| Marginal cost per additional provider round-trip | **~28,884 tokens** (regression slope, r²=0.989 across all 21) | §4 |
| Cost of retrieved source payload, by tool (avg bytes → approx tokens at ~4B/token) | `open_call` 28,477 B ≈ 7,120 tok · `open_note` 5,990 B ≈ 1,500 tok (bimodal: ~925 tok for a card, up to ~12,500 tok for a raw original) · `search_history` 9,556 B ≈ 2,390 tok · `search_calls` 7,502 B ≈ 1,875 tok | §5 |
| Cache reads (evidenced) | **1,270,784 tokens = 75.1% of all spend** — the dominant line item | §2, §4 |
| Cache writes (evidenced) | **0 across all 21 records, no exception** — flagged as an instrumentation gap, not asserted as "no caching occurs" | §4 |
| Average provider requests per successful question | **65 / 21 = 3.10** | §1 |
| Direct-answer avg cost | **24,043 tokens**, 1.0 api_calls (n=6) | §1 |
| Other-tool avg cost (`skill_view` only, no brain MCP tool) | **48,485 tokens**, 2.0 api_calls (n=7) | §1 |
| Brain-tool avg cost (≥1 new Step-6 MCP tool) | **151,124 tokens**, 5.6 api_calls avg, range 3–14 (n=8) | §1 |

Brain-tool questions cost **≈6.3×** the direct-answer baseline on average, and up to **≈17×**
(E1, 410,247 tokens) in the worst observed case.

---

## CLOSEOUT

**NEEDS ATTENTION**

**Actual root cause of ~1.69M usage:** 21 questions averaging 3.10 provider requests each (up to
14 for one question), with 15 of 21 (71%) triggering at least one tool round-trip. Each additional
round-trip re-pays a near-fixed ~28,884-token tax via cache-read re-accounting of stable/system
context (r²=0.989 across the dataset) — this single mechanism accounts for 1,270,784 of the
1,692,636 total tokens (75.1%). Real, but secondary, tool-payload bytes (0.4–50 KB per call) add
the remainder. Not a hidden or unexplained gap — closed exactly (§2).

**Provider requests per user question:** avg 3.10 (range 1–14).

**Does tool use trigger repeated model calls: YES.** Confirmed without exception across all 21
sessions (§3): `tool_call_count=0` ⇒ `api_calls=1` in every case; `tool_call_count≥1` ⇒
`api_calls≥2` in every case.

**Is full/large context repeated/accounted each time: YES**, evidenced two ways: (a) a fixed
~12,800-token cache-read floor appears identically in 5 of 6 zero-tool, single-call sessions; (b)
cache_read_tokens scales linearly with api_calls at ~28.9K tokens/call, r²=0.989 (§4). Per-request
(1st/2nd/Nth call) breakdown is not directly recoverable — Hermes only logs session-level
aggregates, not per-API-call — so this is the strongest evidence obtainable from existing
instrumentation, not a claim of exact per-turn figures.

**Are originals being over-opened: YES, in identifiable cases, not universally.** E4 opened three
full original transcripts via `open_call` (113,467 B, ~28,000 tokens) in one question; E2 opened
one full 50,229-byte original via `open_note` pointed at the raw path rather than its `.card.md`
equivalent. E3, by contrast, used the compact I1 cards for five documents in the same session type
— proving the cheaper path exists and works, but is not consistently chosen.

**E3 exact flow and cost:** 1 user turn → deterministic assembly (3,155 tokens, no CCI-specific
content) → 7 provider requests / 13 tool calls across 6 tool-bearing turns (2 tool_describe pairs,
1 search pair, 5 parallel card opens, 1 broader search, 1 index open) → final answer (2,469 chars,
correct on people/status, silent on both call dates) → **165,287 tokens total**, ≈6.9× the
direct-answer baseline for one question. Full turn-by-turn table in §6.

**Current Fred-question path:** model-driven multi-turn search (`search_calls` → `search_history`
→ `open_note`), evidenced directly by this pass's own E1 session doing exactly this for "Fred" —
several extra provider round-trips and ~26 KB of search-result payload to locate one document by
name.

**Intended one-call-compatible Fred-question path using EXISTING components:** widen
`context_assembler.py`'s `_scoped_note_block()` entity/keyword resolution (currently limited to
`prospects/*.md` pointers and five hardcoded topic buckets) to also query the same
`search_db_path` FTS index (`search/os_index.db`) across intake/historical-call card paths, using
terms `_query_terms()`/`_entity_name_terms()` already extract from the question. The index already
contains the Fred/MLS card, correctly titled, today (§8). No new architecture, no new tool, no new
index — wider matching against what already exists. **Not implemented, per instruction.**

**Architecture verdict: implementation drift from intended architecture, compounded by expected
(not buggy) multi-turn API cost mechanics.**
1. The deterministic Context Assembler itself is lean and working as designed (~3–11K tokens/question).
2. Step 6's four brain MCP tools are a second, model-invoked retrieval layer bolted on top, not an extension of assembly.
3. Any tool use forces ≥1 extra full provider round-trip, each re-billing ~28.9K tokens of stable context via cache reads (75% of all spend) — real API mechanics, not an accounting error.
4. Originals are sometimes over-opened via `open_call`/raw-path `open_note` even where a compact card of the same material already exists and is used elsewhere in the same pass.
5. Net effect: "ONE David call" describes only 6 of 21 (29%) of this pass's questions; the other 71% now route knowledge-corpus lookups through a David-driven loop the original design placed in the deterministic pre-call assembler instead.

**Highest-leverage fix if needed (not implemented):** widen `_scoped_note_block`'s existing
exact-search stage to match the question's own extracted keywords/entities against the
intake/historical-call card index it already has access to via `search_db_path`, so a named-entity
or topic question is answered from one deterministic pre-call insert instead of a multi-turn
brain-tool loop.

---

Model calls: 0. David/Hermes turns: 0. Token usage: no agent invocation — this audit ran only
read-only `sqlite3`/`python3`/`grep`/`Read` queries against pre-existing local evidence.

Files touched: this report only (`scripts/step6_post_i3_usage_forensic_audit.md`). No production
file, scorer, harness, architecture, vault content, or index modified. B7 not resumed. Telegram and
`workspaces/north_shore_sales_coach/` not touched. No commit. No push.
