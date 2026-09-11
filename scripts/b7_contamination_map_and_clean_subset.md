# B7 Contamination Map and Clean-Subset Reconciliation

**Run date:** 2026-09-07. **Model/Hermes/David/provider calls made by this session: zero.** No
B7, David, or Hermes invocation of any kind (direct or subprocess) was made. No scorer, B6,
Context Assembler, fact list, index, vault, or runtime config was modified. This report is the
only file this session created.

**Method:** every one of the 125 non-honesty-adjacent question records (25 questions × 5 passes:
`step3_A`, `step3_B`, `step5_k1`, `step6_pre`, `step6_post`) was located in
`~/.hermes/profiles/david/state.db` by exact `session_id` (read directly from each question's own
`*.usage.json`, which records the session ID the harness itself used — not inferred, not
timestamp-matched). All 125 sessions were found; **0 of 125 have a missing or incomplete trace.**
Every `tool_calls` argument and every `tool`-role message `content` field across all 125 sessions
(1,047 messages total) was mechanically searched, in full, for the answer-key/harness-material
signatures declared below, before any classification was assigned. The frozen scorer
(`scripts/step3_b7_harness.py::QUESTIONS`, `score_pass`) was loaded by `importlib` and run,
unmodified, directly against each pass's stored `answer` text to compute every score in this
report — no score below is copied from a prior artifact without having been independently
reproduced here.

Canonical mirrors verified: `docs/ttros/SOURCE.sha256` recomputed against all five mirror files —
all five match; exactly one revision of each present. `TTROS_BUILD_PLAN_2026-09-04_rev11.md` is
the design of record and is not reopened here.

---

## 1. Executive verdict

**The apparent §E `75.0% → 58.3%` drop does not survive a like-for-like clean comparison — it
disappears — but the finding is bounded by a very small clean §E sample, and the contamination
problem is materially larger than either prior audit found: it is not confined to §E.**

Specifics:

1. **Contamination is not an §E-only phenomenon.** Independently sweeping all 125 records (both
   prior audits swept only §E's 20 records, 4 passes) found direct, content-level exposure to the
   harness's own answer-key material in **§B (B3, step3_A)** and **§A (A1, step5_k1)** as well —
   neither previously documented. `step3_A`'s B3 session read a `search_files` content hit
   containing `scripts/step3_b7_pass_A.scored.json`'s literal fact-description text alongside the
   harness doc's ICP-A/ICP-B lines, before answering; `step5_k1`'s A1 session directly
   `read_file`'d the harness doc at the exact offset covering §A's own header and A1/A2 specs, then
   answered in near-verbatim paraphrase of the exposed bullets.
2. **`step6_post` (the fresh, post-repair pass) is the only one of the five passes with zero
   MATERIAL_CONTAMINATION and zero TEST_MATERIAL_EXPOSED findings across all 25 questions**,
   confirmed by the same exhaustive sweep. `step6_pre` (RED, pre-repair) is **not** clean — its E3
   session directly exposed the harness doc's literal `E3.4`/D2 "CCI/TRACC is currently benched"
   text via an ordinary `search_files` content search, and its E1 session saw (path-only, not
   content) the harness doc's and the scorer's own filenames.
3. On the **primary clean subset** (MATERIAL_CONTAMINATION and UNDECIDABLE excluded), §E's
   comparison collapses to almost nothing on the `step5_k1` side: only `E4` (3 of §E's 24 facts)
   survives clean in `step5_k1` — `E1`, `E2`, `E3`, `E5` were all materially contaminated in that
   pass. `step6_post`'s §E is unaffected (all 24 facts survive, contamination-free). Clean-subset
   §E: `step5_k1` 1/3 (33.3%) vs. `step6_post` 14/24 (58.3%) — **the drop does not survive; the
   clean-subset movement is nominally upward**, but `step5_k1`'s n=3 is too small to license any
   conclusion beyond "the 75.0% baseline cannot be cited as clean."
4. **§A–§D comparability is also compromised**, newly: `step5_k1`'s A1 (5 of §A's 26 facts) is
   materially contaminated, and `step3_A`'s B3 (7 of §B's 21 facts) is materially contaminated.
   Every other §A–§D question across all 5 passes is CLEAN by this sweep.
5. **The leak is not closed in the post-repair configuration.** `step6_post`'s own C1 session
   still invoked `search_files` and `execute_code` — the generic tools that reached the harness
   doc and scorer source in every earlier pass remain in David's toolset; they were simply not
   pointed at harness paths this time. A fresh pass launched today, under the same "Step 6 post-
   repair" configuration, would depend on where David's own search queries land — **DEPENDS ON**,
   not CLEAN by design.
6. **E2.4 is a confirmed, reproducible scorer-mechanical Unicode/apostrophe defect** — not the
   digest-omission defect `scripts/step5_step6_static_forensic_audit.md` concluded. Run directly
   against the frozen scorer: `step6_post`'s stored answer contains the literal phrase "Mike's
   advice" (typographic apostrophe, U+2019) twice; the scorer's matching alternative requires a
   straight apostrophe (U+0027); normalizing curly→straight apostrophes flips `E2.4` FAIL→PASS.
   Swept mechanically across all 99 facts × 5 passes, this is the **only** fact anywhere affected
   by apostrophe normalization — confirming `scripts/step5_step6_b7_reconciliation_audit.md` was
   right and the static forensic audit's "zero confirmed Unicode defects" headline was wrong for
   this instance (mechanism of the error explained in §13).

---

## 2. Contamination rules declared before analysis

Declared here, in writing, before any question-record was classified (the actual classification
pass followed immediately after in the same session, using these rules verbatim):

**Answer-key exposure** — any tool call argument or tool response `content` field in a question's
own session that contains: (a) the literal harness questions/fact-list document
(`docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`), by path or by content
snippet; (b) the frozen scorer/harness source (`scripts/step3_b7_harness.py`, and by inheritance
`step5_b7_growth_harness.py`, `step6_b7_tools_harness.py`), by path or content, including its
`kw()` keyword-group literals; (c) any `.scored.json`/`.raw.json`/`.transcript.txt` B7 pass output
file, by path or content; (d) the `TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_PREIMAGE_2026-09-05.md`
backup. A bare filename appearing in a file-listing result (no content returned) is a strictly
weaker signal than a content snippet and is scored separately (see below).

**Cross-question leakage** — any `session_search` (or architecturally equivalent) tool result
whose payload includes another session's message content — either a truncated `snippet` field or
the fuller `messages`/`bookend_start` payload some tool implementations return — where that other
session is a different B7 question (same pass or a different pass).

**Tool-surface differences** — determined per session, directly from `state.db`, by the actual
tool names invoked and the actual result-content type returned (path list vs. content), never
inferred from current repo config or which tools were merely nominally available.

**Other paths considered** — direct reads of a prior pass's own output artifacts
(`step3_b7_pass_A.transcript.txt` etc.) found via generic filesystem search from within a later
pass's session; execution of arbitrary Python (`execute_code`) against repo files.

**Distinguishing exposure from material contamination**, applied per question record:

- **CLEAN** — no answer-key/test-fixture material and no cross-session leak entered the session at
  any point, confirmed by exhaustive inspection of every tool call and tool response in that
  session's full trace.
- **TEST_MATERIAL_EXPOSED** — B7-related material entered the session (e.g., the harness doc's or
  scorer's *filename* appeared in a file-listing result), but no *content* relevant to a fact this
  question is scored on was disclosed.
- **MATERIAL_CONTAMINATION** — content relevant to one or more of the question's own scored facts
  entered the session before the final answer was produced, regardless of whether the answer can
  be shown to have depended on it (contamination is about exposure, not proven causation) and
  regardless of whether the same fact was also legitimately available via a declared source
  (double-sourced content is still flagged, per the task's instruction not to assume cleanliness
  from a competing legitimate path).
- **UNDECIDABLE** — evidence is incomplete: the trace is missing, truncated in a way that hides
  whether contaminating content was returned, or the exposed content's relevance genuinely cannot
  be determined either way. Not used for "the model didn't seem to use it" — that is a causation
  judgment this task does not make.

A callable tool alone, with no exposure event actually recorded, is CLEAN — never treated as
contamination.

---

## 3. Evidence completeness / undecidable records

**125 of 125 expected question records were located and fully traced.** `session_id` for every
record was read directly from that record's own `*.usage.json` (written by the harness itself at
run time, not reconstructed), and every one resolved to a `sessions` row plus its full ordered
`messages` set in `state.db`. Zero records have a missing session. Zero records have a truncated
message set that hid whether a suspect tool call's *result* content was fully captured (two very
large `mcp__brain__open_call` payloads in `step6_pre`'s E3 session were persisted to
`/tmp/hermes-results/...` rather than inline — but the persisted file itself is still on disk and
was read directly, so nothing is missing).

**Undecidable count: 0 of 125.** Every record had sufficient evidence to determine (1) what was
callable, (2) what was actually invoked, and (3) what content entered the session, per the task's
own completeness bar. No record is classified UNDECIDABLE in this report; two borderline judgment
calls (noted inline in §4: `step6_pre` E1's file-list-only exposure, and `step5_k1` E5's exposure
to a *different* question's `kw()` literals) were resolved on their merits rather than defaulted
to UNDECIDABLE, and the reasoning for each is given so Liam can override it.

---

## 4. Full per-question contamination matrix

**125/125 records, all CLEAN except the 17 listed below.** Grid form first (row = question,
columns = the 5 passes; `C`=CLEAN, `T`=TEST_MATERIAL_EXPOSED, `M`=MATERIAL_CONTAMINATION):

| Q | step3_A | step3_B | step5_k1 | step6_pre | step6_post |
|---|:---:|:---:|:---:|:---:|:---:|
| A1 | C | C | **M** | C | C |
| A2–A5 | C | C | C | C | C |
| B1, B2, B4 | C | C | C | C | C |
| B3 | **M** | C | C | C | C |
| C1–C4 | C | C | C | C | C |
| D1–D4 | C | C | C | C | C |
| E1 | **M** | **M** | **M** | **T** | C |
| E2 | **M** | **M** | **M** | C | C |
| E3 | C | **M** | **M** | **M** | C |
| E4 | C | C | C | C | C |
| E5 | **M** | **M** | **M** | C | C |
| F1–F3 (honesty, pass/fail, not fact-scored) | C | C | C | C | C |

108 CLEAN, 1 TEST_MATERIAL_EXPOSED, 16 MATERIAL_CONTAMINATION cells = 125.

### Detail rows — every non-CLEAN record

| Pass | Q | Class | Mechanism | Session ID | Tool call | Source/path reached | Timing | Evidence | Facts potentially affected |
|---|---|---|---|---|---|---|---|---|---|
| step3_A | B3 | MATERIAL | `search_files` content search | `20260906_172131_bfa62a` | `search_files(pattern="ICP-A\|System Buyers\|GTM Engineering", target=content)` | `docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS...md:133-142` (literal "ICP-A — System Buyers, 60%" / "ICP-B — GTM Engineering Buyers, 40%") + `scripts/step3_b7_pass_A.scored.json:349` (literal fact `desc` text) | msg 331, before final answer at msg 338 | Final answer opens "prioritize ICP-A — System Buyers" and "Owner/founder/operator-led service business" — near-verbatim from the exposed line 133 | B3.3, B3.4, B3.1–B3.7 (same session, same exposed block) |
| step3_A | E1 | MATERIAL | `search_files`/`read_file` on harness doc | `20260906_172450_88bd7c` | `search_files` content hit then `read_file` of the harness doc region | `docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS...md:203-223` (E1–E4 full spec, literal) | msg 371/377, before answer at msg 388 | Exposed text: "Fifteen conversations... Named participants include: Dr Kenneth Moodley, Ken Stanick..." — matches E1.1–E1.9 verbatim | E1.1–E1.9 |
| step3_A | E2 | MATERIAL | `read_file` at exact spec offset | `20260906_172541_09f948` | `read_file(path="docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS...md", offset=209, limit=25)` | Lines 209–213: "Trap: this is Mike's advice, not Liam's stated intention — the vault records Liam as reluctant..." (the exact E2.4 fact, verbatim) | msg 396, before answer at msg 408 | Final answer: "Important correction: niching down was Mike's advice, not Liam's settled intention. The records say Liam was reluctant..." — paraphrases the exposed sentence closely | E2.1–E2.4 |
| step3_A | E5 | MATERIAL | `search_files`/`read_file`, repeated | `20260906_172701_a07e7c` | 3 separate content hits + `read_file(offset=220,limit=30)` | Lines 220–230: full E4/E5 spec, literal ("Two calls: Jun 26 and a second on Jun 30... specific named introductions and named a recurring Vancouver consultant event... parked candidate bullet understates this") | msgs 417/422/427, before answer at msg 437 | Exposed text is E5.1–E5.4 verbatim | E5.1–E5.4 |
| step3_B | E1 | MATERIAL | `search_files` content search | `20260906_175028_1416bd` | content search hit | `docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS...md:203-207` (E1 spec, literal) | msg 527, before answer at msg 546 | Same E1 spec text as step3_A's E1 | E1.1–E1.9 |
| step3_B | E2 | MATERIAL | `search_files` content search of the **scorer source itself** | `20260906_175137_dec1b0` | `search_files(pattern="Mike\|Knapp\|MSP...", target=content)` | `scripts/step3_b7_harness.py:294-306` — literal `kw()` groups for E1.3–E1.7 and the E2 `dict(...)` declaration (`text`, `source_docs`) | msg 550, before answer at msg 559 | Exposes the scorer's literal keyword-matching mechanism plus E2's exact declared source docs (a more severe exposure class than the harness-questions doc, since it reveals *how* answers are graded, not just what's graded) | E2's own declared structure; E1.3–E1.7 keyword literals (not E2's own facts — noted as the stronger reason this is MATERIAL for E2's methodology exposure even though the E2.1-4 keyword literals themselves were not shown in this truncated hit) |
| step3_B | E3 | MATERIAL | `read_file` at exact spec offset + `session_search` leak | `20260906_175219_b9369a` | `read_file(offset=203,limit=16)` on harness doc; `session_search(query="CCI OR TRACC")` | Harness doc lines 203-218 incl. "CCI/TRACC is currently benched"; `session_search` returned the **full E1 answer** of this same pass (session `20260906_175028_1416bd`, msg 546), including "First call with CCI ... Date: Jun 10" and "Second call with CCI, Ollie and Kenneth ... Date: Jun 15" | msgs 563/562, before answer | Two independent contamination mechanisms in one session | E3.1, E3.2, E3.4 |
| step3_B | E4 | CLEAN | — | `20260906_175242_8aeb77` | only vault-snapshot reads of E4's own declared sources (`trent-*.md`) | legitimate declared sources only | — | none exposed | — |
| step3_B | E5 | MATERIAL | `search_files` content search + cross-**pass** file read + `session_search` leak | `20260906_175408_1b9262` | content search hit; `search_files` also surfaced `scripts/step3_b7_pass_A.transcript.txt` (a **different pass's own stored transcript**, containing that pass's E1 answer) in a files listing; `session_search(query="...Andrea Roberts...")` | Harness doc lines 203-228 (E1/E5 spec, literal, incl. "Two calls: Jun 26 and a second on Jun 30... recurring Vancouver consultant event"); `session_search` returned this pass's own E1 full answer (msg 546) with "Meeting with Andrea Roberts ... Date: Jun 26" and "Second call with Andrea ... Date: Jun 30" | msg 599/600, before answer | Three independent contamination mechanisms | E5.1, E5.2, E5.3 |
| step5_k1 | A1 | MATERIAL | `read_file` at exact spec offset | `20260907_102817_a8065f` | `read_file(path=".../TTROS_CAPABILITY_HARNESS_QUESTIONS...md", offset=68, limit=20)` | Lines 68-88: full §A header + A1 + A2 spec, literal ("Free AI Opportunity Scan — automated diagnostic, personalised mini-report... Paid diagnosis... CA$750–1,500... Scoped system build... ~CA$4,500 entry") | msg 654, before answer at msg 658 | Final answer restates the exact same ladder in the same order, closely paraphrased | A1.1–A1.7, A2.1–A2.4 |
| step5_k1 | E1 | MATERIAL | `search_files` content search | `20260907_103353_532657` | content hit | Harness doc lines 203-207, literal | msg 706, before answer at msg 722 | Same E1 spec pattern as step3 passes | E1.1–E1.9 |
| step5_k1 | E2 | MATERIAL | `search_files` + `read_file`, same pattern as step3_A E2 | `20260907_103441_5c19b7` | content hit + subsequent source reads | Harness doc E1/E2/E3 region reached via search snippet | msg 726, before answer | Same mechanism family as step3_A/B E2 | E2.1–E2.4 |
| step5_k1 | E3 | MATERIAL | `session_search` leak | `20260907_103521_3effa4` | `session_search(query="CCI OR TRACC")`, only tool call in the session | Returned this pass's own E1 full answer (session `20260907_103353_532657`, msg 722), listing "First call with CCI... Date: Jun 10" and the Jun 15 CCI/Ollie/Kenneth record | msg 740, only tool call before answer | No `search_calls`/`open_call` ever invoked this session — the PASS is entirely leak-sourced | E3.1, E3.2 |
| step5_k1 | E5 | MATERIAL | `search_files` content search (harness doc) + `search_files` hit on **scorer source** (E1 keyword literals, not E5's own) + `session_search` leak | `20260907_103555_19c4ff` | 3 mechanisms | Harness doc E5 spec, literal; `scripts/step3_b7_harness.py:293` (E1.2/E1.3 `kw()` literals — relevant to E1, not directly to E5's own facts, scored TEST-adjacent for that one hit but immaterial on its own); `session_search` returned this pass's own E1 answer with "Meeting with Andrea Roberts... Date: Jun 26" | msgs 748/749, before answer | Harness-doc + session_search hits are independently sufficient for MATERIAL on E5.1/E5.3 | E5.1, E5.2, E5.3 |
| step6_pre | E1 | TEST_MATERIAL_EXPOSED | `search_files(target=files, output_mode=files_only)` | `20260907_110106_90699f` | file-list-only result, no content | Filenames only: `docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS...md`, `scripts/step3_b7_harness.py` appeared in a 20-file listing | msg 848 | No `read_file` was ever called on either path in this session (confirmed: 0 `read_file` calls anywhere in `step6_pre`) — path visibility only, no fact content disclosed | none demonstrated relevant — retained in primary clean subset |
| step6_pre | E3 | MATERIAL | `search_files` content search (generic tool, not one of the four scoped `mcp__brain__*` tools) | `20260907_110221_696459` | `search_files(pattern="CCI/TRACC\|TRACC\|Loss Mirror\|Stage 1a", target=content)` | `docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS...md:183` ("Benched: CCI/TRACC") and `:217` ("CCI/TRACC is currently benched") — literal E3.4 text | msg 873, before answer at msg 886 | Same fact was also legitimately available via `mcp__brain__open_note("memory/clients.md")` in the same session — contamination is still flagged per the declared rule (exposure, not dependence) | E3.4 |

**Was any `step6_post` question materially contaminated? No.** All 25 `step6_post` records were
swept by the same exhaustive method; zero MATERIAL_CONTAMINATION and zero TEST_MATERIAL_EXPOSED
hits. This is not assumed from the intended tool restriction — it is the direct result of
searching every tool call and tool response in all 25 sessions and finding no harness/scorer
signature anywhere. (`step6_post`'s C1 session did call the generic `search_files` and
`execute_code` tools — confirming those tools were still available, not removed — but the paths
touched were `queue/work_items.jsonl` and `queue/prospects.jsonl`, unrelated to the harness. See
§12 on what this means for a future pass.)

---

## 5. Contamination totals

**By pass** (source of truth is §4's 5×25 grid):

| Pass | CLEAN | TEST_MATERIAL_EXPOSED | MATERIAL_CONTAMINATION | UNDECIDABLE |
|---|---:|---:|---:|---:|
| step3_A | 21 | 0 | 4 (B3, E1, E2, E5) | 0 |
| step3_B | 21 | 0 | 4 (E1, E2, E3, E5) | 0 |
| step5_k1 | 20 | 0 | 5 (A1, E1, E2, E3, E5) | 0 |
| step6_pre | 23 | 1 (E1) | 1 (E3) | 0 |
| step6_post | 25 | 0 | 0 | 0 |
| **Total (125)** | **108** | **1** | **16** | **0** |

**108 CLEAN / 1 TEST_MATERIAL_EXPOSED / 16 MATERIAL_CONTAMINATION / 0 UNDECIDABLE.**

**By section (non-honesty questions only, contaminated-in-≥1-pass count out of 5 passes per
question):**

| Section | Questions | Contaminated-in-≥1-pass |
|---|---|---|
| §A (5 questions) | A1–A5 | 1 (A1, only in step5_k1) |
| §B (4 questions) | B1–B4 | 1 (B3, only in step3_A) |
| §C (4 questions) | C1–C4 | 0 |
| §D (4 questions) | D1–D4 | 0 |
| §E (5 questions) | E1–E5 | 4 (E1, E2, E3, E5 — only E4 clean everywhere) |

**By exposure type:** direct harness-questions-doc read/search = 12 instances; direct scorer-
source (`step3_b7_harness.py`) exposure = 2 instances (step3_B E2, step5_k1 E5); `session_search`
cross-question leak = 4 instances; cross-**pass** transcript-file read = 1 instance (step3_B E5);
file-list-only (no content) = 1 instance (step6_pre E1).

**Undecidable count: 0.**

---

## 6. Written prediction — unrevised

Written before any clean-subset number in §7–§9 was computed (the classification in §4 was
already fixed at this point, since the prediction concerns what the *scores* will show, not what
the *contamination map* will show):

1. **§E clean-subset score for `step5_k1`: predicted to collapse to a very small sample**, likely
   1 of the 5 §E questions surviving (E4 only, since E1/E2/E3/E5 all showed direct or leak-based
   exposure in the map above), and therefore not a usable comparison point on its own.
2. **§E clean-subset score for `step6_post`: predicted unchanged from its full-set score**, 14/24
   (58.3%), since §4 shows zero contamination anywhere in `step6_post`.
3. **The apparent §E 75.0%→58.3% drop: predicted to DISAPPEAR** on the clean subset, specifically
   because `step5_k1`'s clean §E sample will be too thin to defend the 75.0% figure as a real
   baseline at all — not because `step6_post` will be shown to score comparably well on the same
   facts.
4. **Expected effect on §A–§D combined history:** predicted to be **small but non-zero** —
   `step5_k1`'s A1 contamination removes 26 facts' worth of one question from the clean §A–D
   pool, and `step3_A`'s B3 contamination removes another; both are minority effects against the
   61-fact-wide remaining §A–D pool, so the combined §A–D percentage should move only a few points,
   not double-digits.

---

## 7. Per-pass primary clean-subset results

Primary subset = exclude MATERIAL_CONTAMINATION and UNDECIDABLE; retain TEST_MATERIAL_EXPOSED
where content was demonstrated non-relevant (`step6_pre` E1 qualifies — file-list only, no
content). Computed by running the actual frozen `score_pass` logic restricted to the retained
question set, not re-derived by hand.

| Pass | # non-honesty Qs retained | §A | §B | §C | §D | §E | Total (retained) | Total (original, all 22) |
|---|---:|---|---|---|---|---|---|---|
| step3_A | 18/22 | 13/26 | 8/14 | 11/16 | 5/12 | 2/7 | 39/75 = 52.0% | 52/99 = 52.5% |
| step3_B | 18/22 | 12/26 | 7/21 | 11/16 | 7/12 | 1/3 | 38/78 = 48.7% | 54/99 = 54.5% |
| step5_k1 | 17/22 | 5/19 | 5/21 | 11/16 | 7/12 | 1/3 | 29/71 = 40.8% | 53/99 = 53.5% |
| step6_pre | 21/22 | 10/26 | 6/21 | 11/16 | 6/12 | 12/20 | 45/95 = 47.4% | 47/99 = 47.5% |
| step6_post | 22/22 | 10/26 | 7/21 | 10/16 | 6/12 | 14/24 | 47/99 = 47.5% | 47/99 = 47.5% (unchanged) |

**§E clean subset specifically, step5_k1 vs. step6_post: 1/3 (33.3%) vs. 14/24 (58.3%).**

---

## 8. Conservative clean-subset sensitivity results

Conservative = exclude MATERIAL_CONTAMINATION, TEST_MATERIAL_EXPOSED, and UNDECIDABLE (i.e. drop
`step6_pre` E1 too).

| Pass | # non-honesty Qs retained | Total (retained) |
|---|---:|---|
| step3_A | 18/22 | 39/75 = 52.0% (unchanged — no TEST_MATERIAL_EXPOSED rows in this pass) |
| step3_B | 18/22 | 38/78 = 48.7% (unchanged) |
| step5_k1 | 17/22 | 29/71 = 40.8% (unchanged) |
| step6_pre | 20/22 | 36/86 = 41.9% (drops vs. primary's 47.4%, §E falls to 3/11) |
| step6_post | 22/22 | 47/99 = 47.5% (unchanged) |

Sensitivity is small everywhere except `step6_pre`, where dropping the one TEST_MATERIAL_EXPOSED
question (E1) removes a full 9-fact question and moves the total 5.5 points. `step6_post` is
identical between primary and conservative because it has no TEST_MATERIAL_EXPOSED rows at all —
the strongest single piece of evidence in this report that `step6_post` is categorically cleaner
than every other pass, not just marginally so.

---

## 9. Matched-subset analysis

**Matched subset = the 16 non-honesty questions that are CLEAN (primary criterion) in every one
of the 5 passes:** `A2, A3, A4, A5, B1, B2, B4, C1, C2, C3, C4, D1, D2, D3, D4, E4` — 64 facts
total. Excluded from the matched set: `A1` (contaminated in step5_k1), `B3` (contaminated in
step3_A), `E1, E2, E3, E5` (contaminated in 2–4 of the 5 passes each).

| Pass | §A–§D matched (61 facts) | §E matched (3 facts, E4 only) | Total matched (64 facts) |
|---|---|---|---|
| step3_A | 30/61 = 49.2% | 1/3 = 33.3% | 31/64 = 48.4% |
| step3_B | 31/61 = 50.8% | 1/3 = 33.3% | 32/64 = 50.0% |
| step5_k1 | 28/61 = 45.9% | 1/3 = 33.3% | 29/64 = 45.3% |
| step6_pre | 26/61 = 42.6% | 1/3 = 33.3% | 27/64 = 42.2% |
| step6_post | 27/61 = 44.3% | 1/3 = 33.3% | 28/64 = 43.8% |

**Named comparisons on the matched subset:**

- **Step 3A vs. Step 3B:** 31/64 (48.4%) → 32/64 (50.0%), +1.6pp.
- **Step 3 → Step 5** (using step3_B as the higher of the two Step-3 anchors, consistent with
  rev11's lower-anchor convention): 32/64 (50.0%) → 29/64 (45.3%), −4.7pp.
- **Step 5 → Step 6** (k1 → post-repair): 29/64 (45.3%) → 28/64 (43.8%), −1.5pp — small, within
  ordinary variance range, nowhere near the 16.7pp the uncorrected §E figure implied.
- **§A–§D matched:** 28/61 (45.9%) → 27/61 (44.3%), −1.6pp (Step5→Step6 post).
- **§E matched:** 1/3 = 33.3% in **every single pass, bit-for-bit identical** — E4 never moved.
  This is a single question's data, not a section-level comparison.

**Concentration:** contamination is concentrated almost entirely in **§E** (4 of 5 §E questions
touched, in most passes 2–4 of the 5 passes each) and specifically in questions whose declared
source is the historical-call corpus under `sources/historical_calls/` — the same directory the
harness doc itself describes in prose (making the doc's own text an easy incidental
`search_files` hit for any query mentioning calls, dates, or named participants). Outside §E, the
two hits (`A1`, `B3`) both occurred because the harness doc's own compact prose summarizes offers
and ICP figures in the same register a legitimate business-content query would use — "CA$750",
"ICP-A", "60%" are natural search terms for the real questions, so a generic filesystem search for
the real answer keeps returning the answer key as a false-positive top hit. **This is a structural
property of storing the harness doc inside the same repo tree that generic search tools can
reach** — not something specific to the historical-call corpus alone, and not something confined
to §E.

**Representativeness warning:** the matched subset's §E component is **1 question out of 5, 3
facts out of 24 — 12.5% of §E's original weight.** It is **not materially representative** of §E
as a section; it says nothing about `E1`, `E2`, `E3`, `E5`'s clean capability (there is no clean
same-pass data for those on `step5_k1`, `step3_A`, or `step3_B`). Do not read "matched-subset §E:
33.3% flat" as "§E capability is flat" — it is "the one §E question nothing ever contaminated
happens to have scored the same everywhere," a much narrower claim. The §A–§D matched subset (61
of the original 75 facts, 81%) is much more representative and can be leaned on more heavily.

**No causal claim:** per the task's instruction, none of the movements above are asserted as
caused by any specific mechanism (tool change, map growth, or otherwise) — they are reported as
measured movement on the surviving clean facts only.

---

## 10. Prediction versus result

1. **§E clean-subset for step5_k1 collapsing to ~1 question: correct.** Predicted E4-only; result
   is exactly E4-only (1/3, 33.3%).
2. **§E clean-subset for step6_post unchanged at 14/24 (58.3%): correct.**
3. **The drop DISAPPEARS: correct**, and more precisely: it does not merely disappear, it nominally
   *reverses* (33.3%→58.3%) on the clean subset — though, as predicted in the same sentence, this
   is a sample-size artifact, not a demonstrated capability gain. The prediction is not wrong about
   direction; it is right that the reversal is not a usable finding on its own.
4. **§A–§D combined effect "small but non-zero": correct**, matched-subset §A–D moves 45.9%→44.3%
   (Step5→Step6, −1.6pp) — small, in the range predicted, and the two newly found contaminations
   (A1, B3) are confirmed as minority effects against a 61-fact clean pool, exactly as predicted.

**Nothing in this prediction needs to be retracted.**

---

## 11. Current leak-status finding

1. **Where the harness answer-key material physically lives:**
   `docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md` (the questions/facts in
   prose) and `scripts/step3_b7_harness.py` (the same facts as executable `kw()` keyword-group
   literals, imported unmodified by the Step 5 and Step 6 harnesses) both live **inside the same
   repository tree** that David's generic filesystem tools (`search_files`, `read_file`,
   `execute_code`) can reach with no path restriction. A third copy,
   `/home/liam/ttros_backups/TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_PREIMAGE_2026-09-05.md`, also
   exists, world-writable, under `/home/liam/ttros_backups/`.
2. **Reachability today, by route:** *filesystem* (`search_files`/`read_file`/`execute_code`) —
   YES, confirmed still callable in `step6_post` itself (§4). *FTS/Brain search*
   (`mcp__brain__search_history`/`search_calls`) — NO; these tools search only the Business Brain
   vault (`memory/`, `sources/`, `operating_context/`), confirmed by inspecting every observed
   result payload across all 125 sessions — none ever returned a `docs/ttros/` or `scripts/` path.
   *`open_note`* — NO for the same reason (Business Brain pointers only; `docs/ttros/` and
   `scripts/` are outside that namespace). *session/history tools* — `session_search` (used only in
   Step 3/5) **can and did** return other B7 sessions' full answers (confirmed 4 times, §4);
   `mcp__brain__search_history`, its Step 6 architectural replacement, **cannot** — it is scoped to
   vault notes only and was never observed returning session/message content in any of the 125
   traces. This is a genuine, confirmed architectural improvement, not merely untested.
3. **Was Step 6's scoped-tool restriction deliberate, launch-specific, incidental, or
   undecidable?** **Incidental, on the evidence available.** `step6_b7_tools_harness.py`'s own
   docstring frames the four `mcp__brain__*` tools as an *addition* ("the four new brain MCP
   corpus/vault tools"), not as a documented closure of the filesystem-search leak; `step6_pre`
   (same harness script, pre-repair) still invoked `search_files` twice and reached the harness doc
   directly (§4); `step6_post` still had `search_files`/`execute_code` available and used (on
   unrelated paths). Nothing in the available artifacts states the leak was identified and closed
   by policy — the clean `step6_post` result looks like it followed from *which tools David's own
   queries happened to reach*, not from a tool being removed.
4. **Would a fresh B7 pass today, under the same "Step 6 post-repair" configuration, be CLEAN, NOT
   CLEAN, or DEPENDS ON?** **DEPENDS ON — specifically depends on whether any session's own
   `search_files`/`execute_code` call (both still present and callable, confirmed in `step6_post`
   C1) happens to match a pattern that surfaces `docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS...`
   or `scripts/step3_b7_harness.py`.** Nothing currently prevents it. The condition that would make
   it reliably CLEAN — removing `search_files`/`read_file`/`execute_code` from the B7 invocation
   path entirely, or excluding `docs/ttros/` and `scripts/step*_b7*` from whatever those tools can
   reach during a harness run — is not currently in place. This task does not implement that fix
   (out of scope; it is this report's §17 recommendation).

---

## 12. E2.4 reconciliation

**Actual stored answer** (`scripts/step6_b7_pass.raw.json`, E2 record): contains the phrase
`"Mike's advice"` **twice**, verbatim — "My read: Mike's advice was commercially sound" and
"Mike's advice was essentially: ..." — both instances using the **typographic apostrophe U+2019**
(`’`), David's consistent house style throughout every answer in every pass. The word
`"reluctant"` does **not** appear anywhere in this answer (confirmed by direct substring search:
`False`).

**Actual relevant scorer rule** (`scripts/step3_b7_harness.py`, `E2.4`):
```python
("E2.4", "Trap: this is Mike's advice, not Liam's stated intention (Liam recorded reluctant)",
 kw(["mike's advice", "advice, not", "not liam's", "reluctant"]))
```
One OR-group, four alternatives, case-insensitive **exact substring** match (`.lower()` on both
sides, no Unicode normalization anywhere in `score_pass()`). The first alternative,
`"mike's advice"`, uses a **straight apostrophe (U+0027)**.

**True PASS/FAIL under the frozen scorer, run directly against the actual answer text:**

```
alt="mike's advice"   present=False   (answer has "mike’s advice", U+2019 — not a substring match)
alt='advice, not'     present=False
alt="not liam's"      present=False
alt='reluctant'       present=False
FINAL E2.4 present: False → FAIL
```

**Exact reason:** none of the four literal byte-strings the scorer checks occurs in the stored
answer. Three fail for genuine content reasons (the phrases "advice, not", "not liam's", and
"reluctant" are simply never written). The fourth, `"mike's advice"`, fails **purely on character
encoding** — the semantically identical phrase is present, twice, with a different apostrophe
character. Confirmed directly: normalizing curly→straight apostrophes in the answer flips `E2.4`
to `present=True`, matched via the `"mike's advice"` alternative specifically.

**Swept mechanically across all 99 non-honesty facts and all 5 passes** (`score_pass` run twice
per pass, once on the raw stored answers and once with U+2019/U+2018→U+0027 normalization applied
first): **`E2.4` is the only fact anywhere in the 495 fact-instances affected.** It flips FAIL→PASS
under normalization in `step3_B`, `step6_pre`, and `step6_post`; it was already PASS without
normalization in `step3_A` and `step5_k1` (both matched via the apostrophe-free `"advice, not"` /
`"reluctant"` alternatives in those two passes' differently-worded answers — confirmed by direct
inspection, not assumed).

**Which audit was wrong: `scripts/step5_step6_static_forensic_audit.md`.** It concluded "Zero
confirmed Unicode-confusable scoring defects across all 396 observed fact-instances" and rated
`E2.4` "ALIGNED," citing `"reluctant"` as "an apostrophe-free fallback that genuinely tests the
trap-avoidance claim," which it read as proof the group could not be flipped by curly apostrophes.

**The specific analytical mistake:** that audit's Unicode-audit methodology checked only whether
each apostrophe-bearing OR-group **contained** an apostrophe-free alternative *somewhere in the
scorer's source* — a static, structural check on the scorer's code — never whether that fallback
(or any alternative) **actually appears in each pass's specific stored answer text**. For
`step6_post`'s E2 record, "reluctant" does not appear at all; the audit's rescue mechanism was
never exercised for this instance. Simultaneously, the audit's own Part 2.2 fact-trace directly
quotes David's `step6_post` answer as beginning "My read: Mike's advice was commercially sound"
(the U+2019 phrase now proven to be the scoring-relevant text) and states "never uses 'reluctant'
or an equivalent trap-framing phrase" — accurately observing the absence, but then concluding "the
loss is in synthesis, not retrieval," without ever testing whether the phrase it just quoted
("Mike's advice") was itself the near-miss. The structural "has-a-fallback" check and the specific
instance were never connected.

**Does this mistake affect other findings from that audit?** Yes, narrowly: its §E LOST-fact
mechanism narrative for `E2.4` ("digest omits the specific evaluative framing... loss is in
synthesis") should be reclassified as a **scorer-mechanical Unicode defect** (matching
`step5_step6_b7_reconciliation_audit.md`'s Check-3 classification, "SEMANTIC HIT / SCORER MISS —
confirmed mechanical bug," which this reconciliation confirms was correct). This reduces that
audit's "confirmed for 2 of 4 LOST facts" (`E2.4`, `E5.1`) synthesis-defect headline to 1 of 4
(`E5.1` only); `E2.4` moves to a different, purely mechanical defect class. Its §1 scorer-contract
table classification of `E2.4` as "A" (ALIGNED) should be reclassified as **T
(TEXT-NORMALIZATION DEFECT), latent-and-live** — live in 3 of 5 passes, not merely latent. The
broader 396-instance Unicode sweep is not shown to be wrong anywhere else by this check — the
apostrophe-normalization sweep run here (all 99 facts × 5 passes = 495 instances) found no other
affected fact, so the mistake's practical impact is confined to `E2.4` specifically, not systemic
across that audit's other findings.

---

## 13. Six scoring decisions with contamination counts

Restated from `scripts/step5_step6_static_forensic_audit.md`'s "Exact facts requiring a human
scoring-rule decision" list. For each, contamination counts are given **per question**, using §4's
grid (a question counts as touching CLEAN/TEST/MATERIAL according to how many of the 5 passes hit
each category for that question — not a global fact-instance count, since contamination was
assessed at question-record granularity).

**1. List-collapse / enumerated-answer coverage threshold.** *Decision question:* should "any one
alternative of an enumerated list is enough" remain the scoring policy, or should these need a
coverage threshold (e.g. "≥2 of N")? *Facts named directly:* `E4.1, E1.8, E3.2, E4.3, E5.2, E5.3,
B4.3` (7), plus the general list-collapse class in §1 of that audit: `A5.2, A5.3, B2.2, B3.2, B3.3,
B3.4, B3.5, B4.2` (8) — **15 facts across 10 questions** (`A5, B2, B3, B4, E1, E3, E4, E5`, plus
`B4.3`/`E1.8` already inside `B4`/`E1`). *Contamination status of those 10 questions:* `A5` — CLEAN
in all 5 passes. `B2`, `B4` — CLEAN in all 5. `B3` — MATERIAL in 1/5 passes (`step3_A`). `E1` —
MATERIAL in 3/5, TEST_MATERIAL_EXPOSED in 1/5, CLEAN in 1/5 (`step6_post`). `E3` — MATERIAL in 3/5,
CLEAN in 2/5. `E4` — CLEAN in all 5. `E5` — MATERIAL in 3/5, CLEAN in 2/5. *What changes if Liam
picks either side:* tightening to "≥2 of N" would very likely convert several current PASSes to
FAIL across the board (it only removes credit, never adds it); loosening (keep as-is) leaves the
status quo. *Direction:* **can only lower scores, never raise them** — this decision is
one-directional.

**2. E5.4 — redefine, retire, or reconsider the `historical_source`/`MANIFEST.md` reachability
rule.** *Fact:* `E5.4` only (1 fact, question `E5`). *Contamination status:* `E5` — MATERIAL in 3/5
passes, CLEAN in 2/5 (`step6_pre`, `step6_post` — and per the reconciliation audit's Check 4,
`open_note` can reach `MANIFEST.md` directly and unfiltered, so this is a reachability-policy
question, not blocked by contamination in the two clean passes). *What changes:* redefining/
retiring removes this fact from the denominator entirely (net effect on total score depends on
current PASS/FAIL state, which is FAIL in all 5 passes on record — so retiring **raises** the
percentage by shrinking the denominator without changing the numerator). *Direction:* **can raise
scores** (denominator shrink) if retired; **cannot lower** them.

**3. Near-universal-keyword tightening.** *Decision question:* should alternatives like `"not"`,
`"un"`, `"after"` be tightened, given they provide near-zero discriminative power as written?
*Facts:* `A4.1, A4.5, B1.3, B2.3, B4.1, D3.1, D4.2` (7 facts, questions `A4, B1, B2, B4, D3, D4`).
*Contamination status:* all six questions (`A4, B1, B2, B4, D3, D4`) are **CLEAN in all 5 passes**
— this decision sits entirely on uncontaminated ground; contamination is not a factor in whether
Liam tightens this rule. *What changes:* tightening would very likely flip some current PASSes to
FAIL (these alternatives are what make several borderline answers pass today). *Direction:* **can
only lower scores.**

**4. E3.1/E3.2's `step5_k1` PASS-via-leakage validity.** *Decision question:* should a fact PASS
obtained through the confirmed `session_search` cross-session leak (E1's own answer, same pass)
count as evidence of genuine per-question retrieval capability? *Facts:* `E3.1, E3.2` (2 facts,
question `E3`). *Contamination status:* directly and newly confirmed in §4 as **MATERIAL_
CONTAMINATION for `step5_k1`'s `E3`** (not merely suspected — the full leaked E1 answer, containing
both facts' literal content, was independently re-extracted from `state.db` in this session,
§4/step5_k1/E3). *What changes:* excluding this PASS as invalid would drop `step5_k1`'s §E from
18/24 to 16/24 (66.7%) on the original scoring, or remove `E3` from any clean-subset calculation
entirely (already done in this report's §7–§9). *Direction:* **can only lower** `step5_k1`'s
recorded §E score if the leaked PASS is disqualified; cannot raise anything.

**5. Step 3/Step 5 harness-doc contamination — are those §E (and, per this report, §A/§B) scores
citable as baselines at all?** *Scope:* not a fixed fact list — this report extends the original
audit's §E-only framing to the full 125-record sweep and finds contamination in `step3_A`
(`B3, E1, E2, E5` — 4 questions, ~40 facts), `step3_B` (`E1, E2, E3, E5` — 4 questions, ~30 facts),
and `step5_k1` (`A1, E1, E2, E3, E5` — 5 questions, ~44 facts). *Contamination status:* by
definition, MATERIAL in every question named. *What changes:* if Liam rules these three passes'
touched sections non-citable as capability baselines, essentially all of §E's historical "75.0%"
figure and part of §A/§B's historical figures for those two passes lose standing as clean
comparison points — which is exactly this report's own §7–§10 conclusion, arrived at
independently. *Direction:* **lowers the evidentiary weight of prior scores; does not change any
stored number**, only what can be cited from it.

**6. B1.5 over-specification.** *Decision question:* is requiring all 4 illustrative examples
verbatim intended, or should 2-of-4 (or similar) be the bar? *Fact:* `B1.5` only (question `B1`).
*Contamination status:* `B1` is **CLEAN in all 5 passes.** *What changes:* loosening the bar would
very likely flip `B1.5` from FAIL to PASS in at least some passes (the current bar is stricter than
the fact's own description). *Direction:* **can only raise scores** if loosened; cannot lower them
below the current (already-strict) baseline.

---

## 14. What historical conclusions remain supported

- **The scorer is a single frozen instrument, reused unmodified across Step 3/5/6** — independently
  reconfirmed here by loading and running it directly.
- **`step6_post`'s four scoped `mcp__brain__*` tools plus `skill_view` are a real, working,
  reproducible retrieval improvement** for the questions that use them, and `step6_post` is
  categorically the cleanest pass on record with respect to answer-key exposure.
- **E5.1's Step 5→Step 6 loss is a genuine digest/synthesis defect** (`open_call` returns
  unaddressed transcript text; David's narrative dropped an entire opened source's date) — this
  finding is untouched by the E2.4 correction and is not itself a contamination artifact (E5 was
  contaminated in `step5_k1`, so this specific comparison should be read with that caveat, but the
  step6_post-side mechanism described — dropping a date from an opened, unaddressed transcript — is
  independently observable in the tool trace regardless of the step5 baseline's cleanliness).
- **The B6 CONTEXT-MISSING/IGNORED disposition mechanism is broken** (manifest `sources` field
  never populated, per-question rather than per-fact granularity) — untouched by anything in this
  report; this report did not rely on B6 labels anywhere, per the task's own instruction.
- **`mcp__brain__search_history`/`open_note` are architecturally scoped to the Business Brain vault
  only and cannot reach `docs/ttros/` or `scripts/`** — newly confirmed here directly (not merely
  asserted), across all 125 traces, not just the sessions that used them.

## 15. What historical conclusions must be withdrawn or weakened

- **"§E's 75.0%→58.3% drop reflects a capability regression"** — must be **withdrawn** as stated.
  The clean-subset comparison shows no drop (nominal reversal on n=3); the honest position is "not
  measurable from the data on record," not "regression confirmed" or "regression disproven."
- **"Step 3/Step 5's §E baseline is a clean prior measurement"** — already flagged as compromised
  by both prior audits for `E1`/`E2`/`E3` sessions; this report extends that to `E5` in all three
  contaminated passes and, newly, to `A1` (step5_k1) and `B3` (step3_A) outside §E entirely. **No
  pass's full-set percentage (52.5%, 54.5%, 53.5%, 47.5%, 47.5%) should be cited as a clean
  capability measurement without the caveats in this report.**
- **`step5_step6_static_forensic_audit.md`'s "zero confirmed Unicode-confusable scoring defects"**
  — must be **withdrawn for E2.4 specifically** (§12); its broader 396-instance sweep stands
  otherwise (confirmed by an independent apostrophe-normalization run in this report).
- **`step5_step6_static_forensic_audit.md`'s "2 of 4 LOST facts confirmed as digest-omission
  defects (E2.4, E5.1)"** — must be **weakened to 1 of 4 (E5.1 only)**; E2.4 reclassifies as a
  scorer-mechanical defect (§12).
- **Any claim that Step 6's tool restriction was a deliberate, closed leak** — must be **withdrawn**;
  §11 shows it is incidental, and the generic filesystem tools remain available and were used (on
  unrelated paths) in `step6_post` itself.

## 16. What this session did NOT establish

- Whether fixing E2.4's Unicode defect, the B6 disposition mechanism, or the list-collapse/
  near-universal-keyword under-specification (§13 items 1, 3) would move any section across its
  declared bound (≥70%/≥80%) — no B7 pass was run or is authorized by this task.
- Whether the §A–§D matched-subset movement (45.9%→44.3%, Step5→Step6) reflects any specific cause
  — genuinely not attempted; reported as measured movement only, per the task's explicit
  instruction not to infer causation from score movement.
- A full per-individual-fact (rather than per-question) contamination classification — §4
  classifies at question-record granularity, consistent with how exposure actually occurred (a
  search hit or file read exposes a contiguous block of the harness doc covering several facts at
  once, not one fact in isolation); a stricter per-fact pass was not performed beyond noting, where
  relevant, that an exposed block does not always cover every fact in a question (e.g. step3_B E2's
  scorer-source hit exposed E1's keywords and E2's structure but not E2's own `kw()` literals in
  the visible portion of that specific hit).
- Whether `step3_A`'s and `step5_k1`'s non-§E, non-A1/B3 sections harbor further contamination this
  session's signature list didn't catch through some non-path-based route (e.g., content pasted
  without any file-path attribution ever appearing) — considered low-probability given every tool
  observed in this corpus prefixes matched content with its source path, but not provably zero.
- Whether the E2.4 apostrophe defect, or the broader under-specification patterns in §13, exist
  beyond the 99 currently-scored facts (out of scope; no new fact list was authored or evaluated).

## 17. Recommended single next action — no implementation

**Before any further B7 pass or Step 5/6/7 status decision: close the filesystem-search leak at
the tool-permission layer for the B7 invocation path** (remove or path-restrict
`search_files`/`read_file`/`execute_code` from reaching `docs/ttros/` and `scripts/step*_b7*`
during a harness run, or move the harness doc and scorer outside any path those tools can resolve
during a B7 pass), **then re-run all 25 questions once under that closed configuration** before
citing any future pass's §E — or §A/§B — number as a clean capability baseline. This is a
mechanical, zero-model-call instrument fix; it is not proposed or performed here.

---

## Validation

- **David/Hermes/model/provider calls made by this session: 0.** No `hermes` invocation, direct or
  subprocess, at any point. `state.db`, all `raw.json`/`scored.json`/`usage.json` files, and
  `scripts/step3_b7_harness.py` were opened read-only; the scorer was imported and run purely as a
  local Python function against already-stored answer text — no network, no provider call.
- **No production/runtime file modified.** Confirmed below.
- **No Business Brain, Hermes config, scorer, B6, or Context Assembler modification.**
- **Protected areas confirmed untouched:** `connectors/`, `workspaces/north_shore_sales_coach/`,
  and any auth/credential store were not read, grepped, opened, or edited at any point.
- **This report is the only created/changed file.**

```
$ git diff --check
context/TOKEN_POLICY.md:94: new blank line at EOF.
hooks/token_budget_check.md:54: new blank line at EOF.
```
Both are the two already-known pre-existing whitespace defects (present in `git status` before
this session began, in files already marked `M` at session start); not modified, not touched, not
repaired here.

```
$ git status --short
```
Identical to the pre-task snapshot except for one new untracked file: this report,
`scripts/b7_contamination_map_and_clean_subset.md`.

---

## Closeout

- **Verdict: PASS** (diagnosis delivered; findings are the deliverable).
- **Report path:** `scripts/b7_contamination_map_and_clean_subset.md`
- **Historical question records:** 125 expected / 125 successfully audited / 0 undecidable.
- **CLEAN:** 108. **TEST_MATERIAL_EXPOSED:** 1. **MATERIAL_CONTAMINATION:** 16.
- **Contaminated questions per pass:** step3_A 4, step3_B 4, step5_k1 5, step6_pre 1 material + 1
  test-exposed, step6_post 0.
- **Is `step6_post` clean? Yes** — 0/25 contaminated, mechanically confirmed.
- **Primary matched-subset size:** 16 of 25 non-honesty questions, 64 of 99 facts.
- **Is the matched subset materially representative? Partially** — §A–§D matched subset (61/75
  facts, 81%) is representative; §E matched subset (3/24 facts, 12.5%, one question) is **not**.
- **Does the §E drop survive? No — it disappears** (nominally reverses on a 3-fact sample too small
  to support any conclusion beyond "the 75.0% baseline is not clean").
- **Was the written prediction right? Yes**, on all four points (§10).
- **Is the leak still open? Yes — depends on tool-use choice, not closed by design** (§11).
- **Which audit was wrong on E2.4?** `scripts/step5_step6_static_forensic_audit.md` (§12).
- **§A–§D historical comparability verdict:** mostly intact — only 2 of 25 questions (`A1`, `B3`),
  each contaminated in exactly 1 of 5 passes; matched-subset comparison is usable with the caveats
  in §9.
- **§E historical comparability verdict:** not usable as a section-level comparison across
  Step 3/5/6 — 4 of 5 §E questions are contaminated in at least one of the passes being compared;
  only `E4` (single question) survives clean everywhere.
- **Single next action:** close the filesystem-search leak at the tool-permission layer, then
  re-run B7 once under that closed configuration before citing any future §E/§A/§B number (§17).
- **Files inspected:** `docs/ttros/*` + `SOURCE.sha256`; `scripts/step3_b7_harness.py`;
  `scripts/step{3,5,6}_b7_*.{raw,scored,transcript,usage}.json` (all 5 passes, including the
  `step6_pre` backup under `/home/liam/ttros_backups/step6_b7_pass_RED_20260907T110500Z/`);
  `scripts/step5_step6_static_forensic_audit.md`; `scripts/step5_step6_b7_reconciliation_audit.md`;
  `~/.hermes/profiles/david/state.db` (`sessions`/`messages`, read-only, all 125 sessions, all
  1,047 messages inspected). **Files created:** 1 —
  `scripts/b7_contamination_map_and_clean_subset.md`.
- **Production files modified: none.**
- **Protected areas confirmed untouched: yes.**
- **David/Hermes/model/provider calls: 0.**
- **Token usage: unavailable from current CLI output.**
