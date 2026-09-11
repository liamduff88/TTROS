# Step 5 / Step 6 / B7 reconciliation audit — ZERO MODEL CALLS

Scope: read-only diagnosis, authorized to create only this file. No David/Hermes/runtime/provider
model calls made or requested. No production code, vault, index, scorer, or fact list changed.
No B7 pass run. No Step 6b or Step 7 run or built.

Mirror verification (done first, per instructions): `docs/ttros/SOURCE.sha256` recomputed against
both the mirror files and their source copies in `/mnt/c/Users/Admin/Documents/A-Time to
revenue/TTROS Reviews/`. All five hashes match exactly. Exactly one revision of each named
canonical file exists in the source folder. Mirror is current; proceeding.

---

## Executive verdict

**MIXED, with the instrument problem load-bearing enough that neither Step 5 nor Step 6's numbers
can currently be taken at face value.**

1. **Repairs were live.** Not inferred from code — proven from David's own session tool-call
   traces (`~/.hermes/profiles/david/state.db`) for the actual fresh Step 6 pass. The four depth
   tools were invoked 34 times across the 25 questions; search responses carried the `snippet`
   field in 11 of 12 search calls; the previously index-vetoed file
   (`andrea-roberts-june-26.md`) was returned by search and successfully opened via `open_call`
   inside the E5 session itself. Verdict: **REPAIRS LIVE**, not ambiguous.

2. **Step 5's own declared bound has never been met, at any measured B7 pass, including the pass
   Step 5 was closed on — and there is no record of the "or investigate" clause ever firing.**
   Combined §A–§D ("offers/positioning/pipeline/priorities") coverage: Step 3 pass A 49.3%, pass B
   49.3%, Step 5 k=1 (the closing pass) 46.7%, Step 6 pre-repair 44.0%, Step 6 post-repair 44.0%.
   The declared bound is ≥80%, or investigate. It has been roughly half the bound every single
   time it has been measured, and Step 5 was closed on a different, narrower rule (the incremental
   map-growth noise terminator) without this bound being separately satisfied or investigated.

3. **Despite the repairs being live, Section E's fact-for-fact result is bit-for-bit identical
   between the pre-repair and post-repair Step 6 passes — 0 of 24 facts changed.** The overall
   total (47/99 both times) hides 4 facts of 99 that did flip (2 up, 2 down, net zero) elsewhere in
   the set — so the two runs are not identical fact-for-fact overall, only in Section E specifically.

4. **The CONTEXT-MISSING/IGNORED disposition that Steps 3, 5 and 6 all depend on has never worked
   as designed, in any pass measured** (confirmed by direct code and data inspection, not
   inference): the manifest field the scorer reads (`sources`) has never once been populated by
   the current Context Assembler in 125 combined B7 call records across five passes; every single
   disposition call has silently fallen back to a substring-match heuristic. On top of that, the
   heuristic is computed once per **question**, not per fact or per specific document, so a
   question with two declared source documents is labelled IGNORED (not CONTEXT-MISSING) the
   moment *either* document's path text appears anywhere in the manifest blob — even when the
   specific document the failing fact actually needs never arrived and was never fetched. Direct
   session tracing shows this produces both false CONTEXT-MISSING labels (A4, several §E facts:
   the correct file was fetched mid-session via a Brain tool, invisible to the manifest-only
   check) and questions where the disposition is IGNORED for the wrong reason (an irrelevant
   always-present map file happened to satisfy the "any document arrived" test).

5. **Most of the specific misses this audit could resolve are not retrieval failures.** For every
   §E miss traced (E2, E3 partially, E4, E5) except one (E5.4, addressed below) and for B3 in
   §B, David's own session actually opened the exact correct source file — confirmed from the raw
   tool-call trace, not from the answer text — and then answered in synthesized narrative prose
   that never restates the literal date, label, or phrase the frozen keyword scorer requires. One
   of these (E2.4) is a confirmed **scorer-mechanical bug**: the answer states "Mike's advice" with
   a typographic apostrophe (’, U+2019); the scorer's literal string uses a straight apostrophe
   (', U+0027); the substring check silently fails on Unicode alone despite the content being
   exactly, unambiguously correct.

6. **The negative-case rehearsal found real false positives, not zero.** Of 13 blindly sampled
   PASS facts across §A–§E, 2 were spurious: the scorer's keyword groups check a materially weaker
   claim than the fact's own written description promises (B4.3, D1.1 — detailed below). This
   settles the audit's own methodological question: the classification procedure **can** produce a
   negative result, and did.

7. **One correction to the existing diagnosis artifacts:** `scripts/step6_b7_section_e_source_relevance_audit.md`
   concludes E5.4 is "structurally unreachable by design" because `MANIFEST.md` is excluded from the
   FTS search index. That exclusion is real and independently confirmed, but it only blocks the
   *search-discovery* path (`search_calls`/`search_history`). Direct code and a live, zero-model
   invocation of `read_vault_note()` (the function `open_note` calls) confirm `open_note` performs an
   unfiltered direct file read with no exclusion logic at all — it successfully returned the full
   8,794-byte `MANIFEST.md` content when called directly. E5.4 is reachable; David's E5 session simply
   never called `open_note` on it, even though its pointer is visible in `INDEX.md`'s own "Elsewhere"
   wikilink, which David's E1 session demonstrably reads. This is a session tool-use gap, not an
   architectural impossibility.

**Bottom line for the four-way question:** D — MIXED. A real, unaddressed Step 5 bound failure and
a real, unaddressed B6/instrument disposition defect both stand independently of each other and of
Step 6. Step 6's specific 58.3% §E number is contaminated by at least one confirmed scorer bug, a
confirmed disposition-granularity defect, and a dominant narrative-vs-keyword mismatch pattern; it
should not be read as a clean measurement of corpus/vault-tool capability until those are addressed
or explicitly waived.

---

## Check 1 — were the Step 6 repairs actually live?

**Method:** rather than trust `tools/brain_memory_mcp.py`'s current code or `~/.hermes/profiles/david/config.yaml`'s
current contents (both could have been touched after the fact), the fresh pass's 25 sessions were
located directly in `~/.hermes/profiles/david/state.db` by timestamp (`started_at` between
2026-09-07T13:43 and 13:54:30 local, matching `scripts/step6_b7_pass.raw.json`'s recorded call
window) — 25 sessions found, one per question, none missing or extra.

- **A. Index rebuild live?** YES. 12 of the fresh pass's `search_calls`/`search_history` tool
  *responses* (not the answer text) were pulled directly from `messages.content` in `state.db`.
  7 of those 12 responses mention `andrea-roberts-june-26.md` by pointer — the exact file the
  whole-document `SECRET_CONTENT_RE` veto had been silently dropping from the index before the
  repair. The E5 session went further: it called
  `mcp__brain__open_call({"call_id":"andrea-roberts-june-26"})` and received the file's full
  content back, including its `source_sha256` and body. This could not happen against a
  pre-repair index. (Caveat: `search/os_index.db`'s file mtime is later still, 16:16, i.e. rebuilt
  again after this pass and after the 15:10 section-E audit — the live database is not proof of
  what existed at 13:44–13:53; the session-content evidence above is.)
- **B. `AOS_BRAIN_DEPTH_TOOLS=1` live for these sessions?** YES, directly evidenced, not inferred
  from config: the four gated tools (`mcp__brain__search_calls`, `open_call`, `open_note`,
  `search_history`) would not exist as callable functions at all if the flag were unset — and they
  were called 34 times across the 25 sessions (counted below).
- **C. Snippet field present in these sessions' actual payloads?** YES. 11 of 12
  `search_calls`/`search_history` responses in the fresh pass contain a `"snippet"` key with
  real body text (the 12th returned zero matches, so had no snippet to include).
- **D. Four depth tools actually invoked?** YES, counted directly from `messages.tool_calls` /
  `messages.tool_name` across the 25 fresh-pass sessions: `mcp__brain__open_note` ×14,
  `mcp__brain__search_history` ×8, `mcp__brain__open_call` ×8, `mcp__brain__search_calls` ×4 — 34
  depth-tool invocations total, plus 9 `skill_view` calls (a pre-existing generic tool, 3 of which
  targeted skills that do not exist and returned errors) and isolated `execute_code`/`search_files`
  calls.

**Verdict: REPAIRS LIVE.** All four sub-checks confirmed from the actual fresh-pass session
content in `state.db`, not from current code or config alone. The fresh §E number (58.3%,
identical to the pre-repair number) **is** a measurement of the repaired system — it is not
invalidated by a not-live repair. What it shows instead is that a live, real, working retrieval
repair produced **zero measurable change** in the scored §E outcome (see Check 2b).

---

## Check 2 — exact B7 section scores across stages

**Runs enumerated on disk** (none assumed; each independently loaded and checked before use):

| Run | Date/time (local) | Surface | Conditions | Scorer |
|---|---|---|---|---|
| `step3_b7_pass_A` | 2026-09-06 ~17:18–17:28 | CLI, openai-codex/gpt-5.5 | Pre-map baseline, no depth tools | frozen `step3_b7_harness.py::score_pass`, unmodified since |
| `step3_b7_pass_B` | 2026-09-06 ~17:29–17:55 | same | Second independent baseline pass (repeatability pair) | same |
| `step5_b7_pass_k1` | 2026-09-07 ~10:29–10:37 | same | Step 5 k=1 map live (`.hermes.md`, 1,788 B), no depth tools | same (imported by path) |
| `step6_b7_pass` **(pre-repair, RED)** | 2026-09-07 ~10:56–11:05 | same | Step 5 map + Step 6 tools, **before** indexer/tool-scoping/snippet fixes | same |
| `step6_b7_pass` **(post-repair, fresh)** | 2026-09-07 13:44–13:53 | same | Step 5 map + Step 6 tools, **after** all three repairs | same |

The pre-repair run's canonical-path artifacts were moved (not deleted or overwritten) to
`/home/liam/ttros_backups/step6_b7_pass_RED_20260907T110500Z/` before the fresh pass wrote new
files at the same canonical path — confirmed present, all 28 files, per
`scripts/step6_b7_fresh_pass_transcript.txt`'s own recorded change/rollback. Both runs are
therefore fully recoverable at the per-fact level; nothing here required NOT RECOVERABLE.

**Per-section table** (facts present/total, from each run's own `scored.json`, no re-scoring):

| Run | §A (Offer) | §B (Positioning) | §C (Pipeline) | §D (Priorities) | §E (Corpus) | §F (Honesty) | Total |
|---|---|---|---|---|---|---|---|
| step3_A | 13/26 = 50.0% | 8/21 = 38.1% | 11/16 = 68.8% | 5/12 = 41.7% | 15/24 = 62.5% | 3/3 | 52/99 = 52.5% |
| step3_B | 12/26 = 46.2% | 7/21 = 33.3% | 11/16 = 68.8% | 7/12 = 58.3% | 17/24 = 70.8% | 3/3 | 54/99 = 54.5% |
| step5_k1 | 12/26 = 46.2% | 5/21 = 23.8% | 11/16 = 68.8% | 7/12 = 58.3% | 18/24 = 75.0% | 3/3 | 53/99 = 53.5% |
| step6_pre | 10/26 = 38.5% | 6/21 = 28.6% | 11/16 = 68.8% | 6/12 = 50.0% | 14/24 = 58.3% | 3/3 | 47/99 = 47.5% |
| step6_post | 10/26 = 38.5% | 7/21 = 33.3% | 10/16 = 62.5% | 6/12 = 50.0% | 14/24 = 58.3% | 3/3 | 47/99 = 47.5% |

Delta from previous run (total): step3_A→B +2.0pp; step3_B→step5_k1 −1.0pp (the +1.0pp figure
quoted in the task's "CURRENT VERIFIED STATE" is step3's **lower anchor** (52.5%) to step5_k1
(53.5%), per rev11's own lower-anchor rule — both numbers are consistent, just anchored
differently); step5_k1→step6_pre −6.0pp; step6_pre→step6_post 0.0pp (net; see Check 2b for the
non-zero internal churn this nets out).

### Step 5 bound evaluation — rule quoted verbatim

From `TTROS_BUILD_PLAN_2026-09-04_rev11.md`, the Step 5 entry:

> "Bounds: B7 coverage on offers/positioning/pipeline/priorities ≥80%, or investigate; **map
> growth uses the Step 3 B7 noise allowance from §2 and is unavailable if Step 3 spread exceeded
> 10 points**; B2 total ≤96,000 B; fresh bytes per turn below today's 45,804 B equivalent; latency
> not worse than the 25.9s baseline — the last two from B8, or revert."

§A/§B/§C/§D map exactly to the frozen harness's own section titles (`TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`:
"§A — Offer and delivery", "§B — Positioning and ideal client", "§C — Pipeline and commitments",
"§D — Priorities and current state") — this is not an inferred mapping.

**Combined §A+§B+§C+§D coverage, computed fresh in this audit from each run's own scored facts:**

| Run | A+B+C+D present/total | % | vs. 80% bound |
|---|---|---|---|
| step3_A | 37/75 | 49.3% | **FAIL** |
| step3_B | 37/75 | 49.3% | **FAIL** |
| step5_k1 (Step 5's own closing pass) | 35/75 | 46.7% | **FAIL** |
| step6_pre | 33/75 | 44.0% | **FAIL** |
| step6_post | 33/75 | 44.0% | **FAIL** |

**Explicit answers:**

- **Is current §A–§D capability below Step 5's declared bound?** Yes — 44.0%, against a declared
  ≥80% bound, a 36-point shortfall.
- **Was it below the bound when Step 5 was closed?** Yes — the k=1 pass Step 5 was actually closed
  on measured 46.7%, also far below 80%.
- **Does the Step 5 → Step 6 movement exceed the declared 4.0pp noise allowance?** Total score:
  step5_k1 → step6_pre is −6.0pp (53.5%→47.5%), which exceeds the 4.0pp allowance. On the
  §A+§B+§C+§D subset specifically: 46.7%→44.0% is −2.7pp, inside the allowance. §E alone moved
  75.0%→58.3%, a −16.7pp drop, far outside the allowance — this is the single largest, cleanest
  signal in the whole comparison, already flagged in `scripts/step6_report.md`.
- **If yes, what does rev11 require: PASS, investigate, or something else?** For the §A–§D bound
  specifically, the rule's own text is unconditional: **"≥80%, or investigate."** Coverage has
  never reached 80% at any measured pass, including the pass Step 5 was closed on. No artifact
  found in this audit records that investigation ever having been triggered or performed against
  this specific bound — Step 5's closing evidence (`k=1 expansion run; B7 52.5%→53.5% (+1.0pp);
  4.0pp noise terminator fired`) cites only the separate, narrower incremental-map-growth
  terminator, which is a different rule governing *when to stop adding map classes*, not whether
  the ≥80% floor was met. **Rev11's own text requires investigation; this audit found none
  recorded.** This is a finding for Liam's decision, not a status change made here.

---

## Check 2b — per-fact churn, pre-repair vs. post-repair Step 6

Both runs recovered in full (see Check 2). Compared fact-by-fact across all 99 non-honesty facts
using each run's own `fact_results[].present` boolean — no re-scoring, no re-running B7.

| | Count |
|---|---|
| Both PASS | 45 |
| Both FAIL | 50 |
| PASS → FAIL | 2 (A1.7, C4.3) |
| FAIL → PASS | 2 (A5.1, B2.3) |
| **Total churn (either direction)** | **4 / 99 = 4.0%** |
| Net (signed) | 0 |

**Section E alone:** 14 both-PASS, 10 both-FAIL, **0 PASS→FAIL, 0 FAIL→PASS — bit-for-bit
identical across all 24 facts**, including the individual fact (E5.1, "Jun 26 + Jun 30 dates")
that the repair report explicitly targeted and confirmed newly retrievable.

**Which does the evidence support?**

Neither of the two pure alternatives cleanly. The overall set shows **substantial-enough,
coincidental-total churn** (4 facts moved, exactly cancelling): this rules out "identical
fact-for-fact" as a description of the whole 99-fact set, and rules out treating the matching
99/47 totals as proof nothing changed. But **Section E specifically — the only section the repairs
directly targeted — is identical fact-for-fact**, which is the sharper and more decision-relevant
result: **combined with Check 1's REPAIRS LIVE finding, this means B7's §E scoring is insensitive
to the specific retrieval-quality improvement made**, not that the repair wasn't live. The
mechanism is now independently understood (Check 3, Check 5): the repair fixed *retrieval reach*
(the file becomes findable and readable), but every §E miss traced in this audit shows retrieval
was never the bottleneck for the model's *answer* — the model already reached the correct
documents via tools before the repair in the cases traced, and the literal keyword/date/label the
scorer needs was never written into the final answer either before or after. A repair that fixes
reach cannot move a score whose failures are downstream of reach.

**Empirical noise estimate vs. the declared 4.0pp allowance:** the overall 4/99 = 4.0% gross
per-fact flip rate happens to numerically coincide with the declared 4.0pp floor, but it is not
the same measurement — Step 3's allowance is defined on **total-score spread** (a signed,
netting-out number), not gross per-fact flip count. Read as total-score spread, this pair shows
**0.0pp** (47/99 both times) — i.e., by the actual defined metric, this comparison shows *less*
noise than the declared floor, not more. The real finding is methodological, not a bigger number:
**a total-score-spread measurement can look like zero noise while masking real, bidirectional
per-fact movement**, because gains and losses net out. This is worth recording as a caveat on the
Step 3 methodology itself, not as evidence that the true noise floor exceeds 4.0pp.

**Caveat on which case applies, stated per the task's own instruction:** Check 1 established the
repairs were live for this specific comparison, so this is **not** a clean same-conditions noise
pair — it mixes a live, confirmed-real repair effect (on retrieval reach) with ordinary session
variance, and gross per-fact churn here is an **upper bound** on noise, not a clean estimate.
Given the repair's confirmed zero effect on the one section it targeted, the practical
consequence is muted regardless: **there is no evidence in this pair that the true noise floor
materially exceeds the declared 4.0pp allowance.** No recommendation to reopen Step 5's
terminator or the allowance follows from this pair; recorded per the task's instruction as a
finding only.

---

## Check 3 — classification of current misses

### Classification rules (verbatim from the task)

- **SEMANTIC HIT / SCORER MISS** — David communicated the source-supported factual proposition
  accurately, but the scorer failed on literal wording or label matching.
- **EVIDENCE RECEIVED / TRUE OMISSION** — David received the relevant supported fact and did not
  communicate it.
- **EXPECTED FACT NOT SUPPORTED BY CITED SOURCE** — the required fact is absent from, or stronger
  than, the substantive cited source.
- **CANONICAL / VAULT FIDELITY DEFECT** — the Business Brain/index/manifest asserts something its
  underlying source does not support.
- **AMBIGUOUS** — only where evidence genuinely cannot distinguish.

### Written prediction (before reading remaining answer text)

Prediction, made after Check 1's tracing (which necessarily required reading the E5 session and
answer to verify repair-liveness — disclosed as a limitation below) but before reading A2, A4, B3,
C4, E1, E2, E3, E4 in detail: given Check 1 proved the four depth tools are being invoked
extensively and successfully retrieving named source files, the majority of the 10 §E misses were
predicted to classify as **EVIDENCE RECEIVED / TRUE OMISSION** (tool fetched the right file, model
under-cited it in narrative prose) rather than retrieval failures, consistent with
`scripts/step6_repair_report.md`'s own prior finding that 8 of 10 §E misses showed this pattern.
A2/A4/B3/C4 were predicted to split differently from §E, because they are §A–§D "core map"
questions that Step 6's tools do not target: some predicted as genuine **CONTEXT-MISSING /
Step-5-map-coverage gaps** (not fitting cleanly into the four given categories, which are oriented
around retrieval-tool-era facts) rather than tool-era omissions.

**Disclosed limitation:** E5's full answer and tool trace were read during Check 1 to verify
repair-liveness, before this prediction was written. This is an unavoidable consequence of Check 1
requiring the same session evidence Check 3 classifies; E5's classification below is therefore
not a blind result, and E5.1/E5.3/E5.4 in particular were already known before the prediction.

### Classification table

| Fact | Expected atomic fact | Cited source | What David actually received (session trace) | What David answered | Classification | Evidence |
|---|---|---|---|---|---|---|
| A2.1–A2.4 | Diagnose-before-prescribe method sequence | `memory/offers.md`, `memory/positioning.md` | **Nothing** — `source_arrived` false for both docs; A2's session made **zero tool calls** (`tool_call_count=0` in `state.db`) | A different, more abstract framing ("revenue is an engineered operating system"); never mentions diagnosis sequencing | **Not classifiable under the four given categories** — this is a genuine Step-5 map-coverage gap (CONTEXT-MISSING with zero tool activity), outside the four categories' tool-era framing | `state.db` session `20260907_134507_5fccf5`: 0 tool calls, 2 messages only |
| A4.1–A4.6 | The specific "not-allowed-to-claim" list | `memory/offers.md`, `memory/positioning.md` | Session made exactly 1 tool call: `skill_view("linkedin_outreach_prep")`, which **failed** ("Skill not found"); no brain tool ever called; `offers.md` never fetched | A long, substantively similar but independently-reasoned "do not claim" list, using different wording throughout (e.g. "we have not earned" for A4.6's "specializ...not yet earned"; no mention of "autonomous"/"human judg" at all for A4.4) | **CONTEXT-MISSING, mislabeled IGNORED** by the harness (disposition is computed per-question as "any of offers.md/positioning.md arrived" — positioning.md's unrelated arrival flips the whole question to IGNORED even though the specific needed document, offers.md, never arrived and was never fetched). A4.6 alone reads as **SEMANTIC HIT/SCORER MISS** (near-paraphrase); A4.4 is a genuine omission of untouched content. | `state.db` session `20260907_134542_f255fa`: 1 failed `skill_view` call, no brain tool |
| B3.1–B3.7 | ICP-A/ICP-B naming, 60/40 split, "router" framing, prospecting-weighting-not-restriction | `memory/ideal_clients.md`, `_A.md`, `_B.md` | **The literal required content**, verbatim: `open_note` on all three files returned text containing "ICP-A — System Buyers ... 60%", "ICP-B — GTM Engineering Buyers ... 40%", "# Ideal Clients — router", "prospecting weighting for the internal outreach engine, not a market restriction" | A complete rewording as "priority lanes" and "secondary ICP", dropping every literal ICP-A/ICP-B/60-40/router marker | **EVIDENCE RECEIVED / TRUE OMISSION**, unambiguous — the exact literal text was in the session and not reproduced | `state.db` session `20260907_134642_0a9414`: 4 `open_note` calls, full canonical text confirmed present in tool responses (quoted above) |
| C4.1 | "TTR's own acquisition engine is the first case study" | `memory/positioning.md` | Session's one tool call (`skill_view("fit_call_prep")`) **failed**; `positioning.md` never fetched | "Prove the acquisition engine on TTR itself" — semantically near-identical, not a literal match | **AMBIGUOUS, leaning SEMANTIC HIT/SCORER MISS** — the idea is right but was not demonstrably sourced this session (no tool fetch), so it cannot be confirmed as source-grounded vs. general reasoning | `state.db` session `20260907_134917_c626dd` |
| C4.2, C4.3 | Specialization-by-problem-type doctrine; vertical narrowing after proofs | `memory/positioning.md` | Same as C4.1 — never fetched | Entirely different content (proof-sequencing tactics); "problem type" and "vertical"/"narrow" concepts not addressed at all | **CONTEXT-MISSING** — genuine gap, source never arrived or fetched, and answer topic doesn't even brush against it | Same session |
| E2.1, E2.2 | "Jul 21" / "2026-07-22" call dates | `mike-knapp-july-21.md`, `mike-knapp-gtm-context-july-22.md` | Both files **opened via `open_call`**, with the dates literally in their filenames/pointers | Extensive, accurate synthesis of the calls' content; **no calendar date stated anywhere** | **EVIDENCE RECEIVED / TRUE OMISSION** | `state.db` session `20260907_135056_46bab8`: `open_call("mike-knapp-gtm-context-july-22")`, `open_call("mike-knapp-july-21")` both succeeded |
| E2.4 | "Mike's advice, not Liam's intention" trap | same | Same session, both files opened | States "Mike's advice was essentially..." verbatim — but with a **typographic apostrophe (’)**, not the scorer's straight apostrophe (') | **SEMANTIC HIT / SCORER MISS — confirmed mechanical bug.** `"mike's advice" in answer.lower()` → `False`; `"mike’s advice" in answer.lower()` → `True`. Content is exactly correct. | Direct Python string check against `scripts/step6_b7_pass.raw.json`'s E2 answer |
| E3.1, E3.2 | "Jun 10" first call; "Jun 15" second call w/ Ollie+Kenneth | `first-call-cci.md`, `cci-second-call-june-15.md` | **Neither file was opened this session** — search queries ("CCI OR TRACC", "Loss Mirror OR Stage 1a...") surfaced only canonical *notes* (`memory/clients.md`, `active_projects.md`), never the call transcripts, despite both being present and unexcluded in the live search index | Names Ollie/Graham/Kenneth Moodley correctly (from `memory/clients.md`) but states no call dates | **AMBIGUOUS between CONTEXT-MISSING and a retrieval-behavior gap** — the files exist, are indexed, and are not excluded, but were not surfaced by these specific queries; cannot fully distinguish "the search ranking failed to surface an exact-keyword match" from "David should have queried more specifically" from the evidence available | Confirmed via `search/os_index.db` direct query: both files present, `documents` table membership verified; `state.db` session `20260907_135132_84f585` shows 4 search calls, 2 `open_note` calls, zero `open_call` on the CCI transcripts |
| E4.1 | "Two Trent MacGregor calls: undated + Jul 9" | `trent-first-call.md`, `trent-july-9.md` | Both files **opened via `open_call`**, including the one literally named `trent-july-9` | Full narrative synthesis of both calls' content; **no calendar date stated** | **EVIDENCE RECEIVED / TRUE OMISSION**, and see Check 4 for a separate, independent defect in the fact's own provenance | `state.db` session `20260907_135201_1089b8`: `open_call("trent-first-call")`, `open_call("trent-july-9")` both succeeded |
| E4.3 | "Lance never in the room; Trent offers to get Lance's info" | same | Same two files opened | "We do not have Lance's direct statements" — strongly implies but never asserts Lance's absence from the call itself | **AMBIGUOUS, leaning SEMANTIC HIT/SCORER MISS** — close paraphrase, not a literal match, and not clearly a stronger/weaker claim than source | Same session |
| E5.1 | "Two calls: Jun 26 and Jun 30" | `andrea-roberts-june-26.md`, `andrea-second-call-june-30.md` | The Jun 26 file was **opened via `open_call`** (`{"call_id":"andrea-roberts-june-26"}`) and its content returned in full | Synthesizes only from the Jun 30 call; Jun 26 content never referenced | **EVIDENCE RECEIVED / TRUE OMISSION** — labeled CONTEXT-MISSING by the harness, but the source demonstrably arrived via tool mid-session; the manifest-only disposition check cannot see this (Check 5) | `state.db` session `20260907_135229_432043`, full trace quoted in Check 1 |
| E5.2 | Named specific completed introductions | same | Same session | Correctly separates completed (Ken, Mike Knapp) from merely-discussed (Mike Gardner, Rachel Radford) introductions | PASS in both runs — not a miss | — |
| E5.3 | "Named a recurring Vancouver consultant event" | `andrea-second-call-june-30.md` | Same session, same file open | Discusses "Mirror Consulting" (Rachel Radford's recurring bi-monthly event) accurately, but never writes "Vancouver" or "event" | **CANONICAL/HARNESS FIDELITY DEFECT in the fact list itself**, corroborating and correcting `scripts/step6_b7_section_e_source_relevance_audit.md`: "Vancouver" occurs 7 times total across both Andrea transcripts (not "exactly once" as that artifact states), but none of the occurrences are adjacent to the Mirror Consulting passage — they describe an unrelated company ("Quin AI is a Vancouver based tech company") and unrelated asides. The keyword pair `vancouver`+`event` does not co-occur with the fact's actual substance anywhere in source. A fully accurate, complete answer about Mirror Consulting cannot pass this fact's scorer without the model independently supplying words the source never attaches to that content. | Direct grep of both source transcripts (counts and line numbers recorded); confirms the prior artifact's substantive conclusion, corrects its occurrence count |
| E5.4 | "The parked candidate bullet understates this" | `MANIFEST.md` (not one of E5's declared `source_docs`) | **Reachable but never attempted.** Independently verified (see Check 4): `open_note("sources/historical_calls/MANIFEST.md")` succeeds via a direct, unfiltered `read_vault_note()` call — confirmed live, zero model calls, returned the full 8,794-byte file. David's E5 session never called `open_note` on it. | Not addressed | **EVIDENCE RECEIVED / TRUE OMISSION** (available-but-not-sought) — **correcting** the prior artifact's "structurally unreachable by design" / "architecturally guaranteed never to reach him" conclusion, which conflated search-index exclusion with tool-level unreachability | Live invocation of `tools.brain_memory.read_vault_note('sources/historical_calls/MANIFEST.md')` in this audit; `search/os_index.db` confirms it is absent from the FTS index (search path only) |

### Negative-case rehearsal

**Sample selected before reading any answer text** (recorded verbatim, then answers pulled):
`A1.1, A1.4, A3.1, A5.1, B1.2, B2.1, B4.3, C1.1, C2.5, C3.1, D1.1, D2.1, E1.4` — 13 facts, spanning
all five sections.

| Fact | Description | Required scorer groups | Genuine or spurious? |
|---|---|---|---|
| A1.1 | Free AI Opportunity Scan, personalized mini-report | matches description in full | **Genuine** |
| A1.4 | Paid diagnosis, CA$750–1,500, creditable | matches description in full | **Genuine** |
| A3.1 | Forward-deployed, inside client's operation | matches description in full | **Genuine** |
| A5.1 | GTM systems primary wedge | "Go-to-market and operations engineering systems" stated directly | **Genuine** |
| B1.2 | Tailored to operational friction, then practical system | matches description throughout | **Genuine** |
| B2.1 | Internal doctrine, not the pitch | matches description explicitly and repeatedly | **Genuine** |
| B4.3 | **Full 6-tier geography chain**: Vancouver→BC→Western Canada→Canada→Pacific NW/US→UK/Ireland | Scorer only checks 3 of 6 terms: `vancouver` AND (`british columbia`/`bc`) AND `western canada` | **SPURIOUS.** Answer states only 2 of the 6 described tiers (Vancouver/Lower Mainland, then BC/Western Canada) and never mentions Canada, Pacific NW/US, or UK/Ireland at all — yet passes because the scorer's proxy is materially narrower than the fact's own description. |
| C1.1 | AOS-2026-0174/Loretta Davis, stale, role/relevance + prior-contact checks | exact literal match in answer | **Genuine** |
| C2.5 | Anush Sridhar/Manufex | exact literal match | **Genuine** |
| C3.1 | CA$30,000/month gross revenue | exact literal match, including "gross" clarification | **Genuine** |
| D1.1 | Onboard Ryan on North Shore, **pilot boundaries preserved, Sheets sync gated** | Scorer only checks 2 of 3 described elements: `ryan` AND `north shore` | **SPURIOUS.** D1's answer mentions "Ryan/North Shore" but never mentions "Sheets," "sync," or "pilot boundaries" anywhere — 2 of the fact's 3 described components are neither checked nor present, yet it passes. |
| D2.1 | Benched: CCI/TRACC | exact literal match | **Genuine** |
| E1.4 | Andrea Roberts named | exact literal match in table row | **Genuine** |

**Result: 2 of 13 sampled PASS facts (≈15%) were spurious** — not zero. Per the task's own
framing, this settles the question on evidence: **the scorer produces real false positives**
(B4.3, D1.1), not merely "the classification procedure cannot produce a negative result." The
mechanism in both spurious cases is identical and generalizable: the fact's **description** states
a multi-part or multi-tier claim, but the scorer's **keyword groups** check only a strict subset of
those parts, so a partial, incomplete answer that happens to hit the checked subset scores as if
the full description were verified. This is a distinct defect class from the false-negative issues
found in the miss analysis above (apostrophe encoding, disposition granularity) — it runs in the
opposite direction and was found by deliberately testing the scorer against its own PASS labels,
exactly as the task's negative-case-rehearsal instruction intends.

---

## Check 4 — E4.1 / E5.3 / E5.4 provenance

**E4.1 — "Jul 9" date field.** Traced from source to index. The underlying file
`sources/historical_calls/trent-july-9.md` declares in its own frontmatter:
`source_date_text: "Jul 9"` and, critically, `metadata_basis: "filename and speaker labels"` —
the vault's own record self-declares this is filename-derived import metadata, not a verified
event date (the original filename was `"trent call transcript july 9th.txt"`). `INDEX.md`'s
column header is itself neutrally titled **"Date text"** (not "Call date" or "Event date"), and
the file carries the caveat "Yearless dates remain yearless. Any participant not named in embedded
metadata is explicitly a title/filename/speaker-label inference." The vault and index are
appropriately hedged. **Verdict: scorer/harness-fact-list defect, not a vault/index fidelity
defect.** The harness's fact list (E4.1: "Two Trent MacGregor calls: undated + Jul 9") requires
David to state this filename-derived label as if it were verified fact, promoting metadata the
vault itself carefully flags as unverified into an expected "known" answer. This matches the
task's own diagnostic framing exactly: the column asserts a record label, and the harness
promoted it to event truth.

**E5.3 — "recurring Vancouver consultant event" / Mirror Consulting.** See the classification
table above. Independently confirmed by direct grep of both Andrea Roberts source transcripts:
the Mirror Consulting passage (line 251 of `andrea-second-call-june-30.md`: "another company
called mirror consulting and they have every two months they have an in-person consultant
networking thing") never uses the words "Vancouver" or "event" in its vicinity. Every occurrence
of "Vancouver" in either transcript (7 total, corrected from the prior artifact's "exactly once")
attaches to unrelated content (an unrelated tech company, a mortgage-broker anecdote, a developer's
location). **Verdict: scorer/fact-list keyword-choice defect, not a vault/index overstatement.**
The Business Brain and index make no explicit "recurring Vancouver consultant event" assertion
anywhere audited; the defect is that the frozen harness's keyword pair for this fact does not
co-occur with the fact's actual substance in the cited source, making it structurally hard to pass
even with a fully accurate, complete answer.

**E5.4 — `MANIFEST.md` reachability.** Checked read-only, directly, not assumed from context
exclusion. `search/os_index.db`'s `documents` table was queried directly: no row for
`business_brain:sources/historical_calls/MANIFEST.md` exists (the FTS-index exclusion is real and
confirmed — this is the F-BRAINNOTES-1-class filter the prior artifact correctly identified).
However, `tools/brain_memory_mcp.py::open_note()` calls `tools/brain_memory.py::read_vault_note()`
directly — read closely, this function contains **no exclusion check of any kind**: it normalizes
the pointer and does a direct `Path.read_text()`. This was verified live in this audit (zero model
calls): `read_vault_note('sources/historical_calls/MANIFEST.md')` succeeded and returned the full
8,794-byte file. **Verdict: reachable through `open_note`, not inaccessible-unwinnable.** The
prior artifact's "structurally unreachable by design" conclusion conflated exclusion from the
*search-discovery* path with exclusion from the *tool* surface as a whole — exactly the pitfall
this task's own instructions warned against. David's E5 session never attempted `open_note` on
this pointer, even though `INDEX.md`'s own "Elsewhere" section links to it by exact path, and
David's E1 session (which reads `INDEX.md`-derived content) demonstrates that link is visible to
him. This reclassifies E5.4 from an instrument-design problem to a session tool-use gap.

---

## Check 5 — B6 sources/assembler evidence

**Where the evidence should originate:** `tools/context_assembler.py`'s `manifest` property (read
directly, lines 252–275). It emits `marker, schema_version, assembler_version, invocation_id,
surface, session_id, classification, client_scope, created_at, request, request_bytes,
request_tokens, blocks, total_bytes, total_tokens, warnings, provenance, actual_reads,
retrieval_hierarchy, whole_vault_default, source_discovery_token_usage`. **It has never, in the
current code, emitted a `sources` key.**

**Does the harness expect it anyway?** Yes — `scripts/step3_b7_harness.py::source_arrived()`
(shared, unmodified, imported by path into the Step 5 and Step 6 harnesses) reads
`manifest.get("sources")` first, and only falls back to a substring-in-JSON-blob heuristic
(`doc in json.dumps(manifest)`) when that key is empty.

**Is it dropped before the harness record is written, or never emitted at all?** Never emitted.
Checked directly across all 125 non-honesty question records currently on disk (25 records × 5
runs: step3 A/B, step5 k1, step6 pre/post): **0 of 125 have a non-empty `sources` key.** This is
not a Step-6-specific regression — it is true of every B7 pass measured since Step 3. **Every
CONTEXT-MISSING/IGNORED disposition ever recorded by this harness has been computed by the
substring-fallback heuristic, never by the intended clean field.**

**Does the fallback itself introduce defects beyond "it's a heuristic"?** Yes, a second,
independent defect, found by tracing specific facts (A4, E3 above): `score_pass()` computes
`any_source_arrived = any(arrived.values())` **once per question**, then applies that single
disposition to every fact in the question, even when a question declares multiple source documents
of unequal relevance to different facts. A4 illustrates this exactly: `positioning.md` (largely
irrelevant to the "not-allowed-to-claim" list) registers as "arrived" via the blob fallback, which
flips the *entire* question's disposition to IGNORED — masking that `offers.md` (the actually
relevant document) never arrived and was never fetched. This means IGNORED and CONTEXT-MISSING
counts are unreliable in **both directions**: false IGNORED (as in A4, E3) when an irrelevant
declared document happens to satisfy the blob-substring test, and false CONTEXT-MISSING (as in
E5.1, and per `scripts/step6_repair_report.md`'s own E4 finding) when a Brain tool successfully
fetches the needed content mid-session but the initial-manifest-only check cannot see it.

**Can `#excluded=`/stale-residue tags cause false positives?** Not observed in this data — the
`sources` list this logic checks for is never populated at all in the current assembler output, so
the `#excluded=`/`#budget=omitted` tag-parsing branch of `source_arrived()` is currently dead code
against live data. It remains a latent risk if `sources` is ever populated without also auditing
this parsing path, but is not the active defect here.

**Is this a new issue or already recorded in `00`?** Not found recorded in `00_TTROS_CURRENT_STATE_v2026-09-04_rev6.md`
under this description. `00` records F-ASSEMBLERDRIFT-1 (unrelated: +166 lines of undocumented
drift in `context_assembler.py`) and the general B6/B7 dependency design in the D-NAMING section
of `02`, but neither artifact records that the specific `sources` field the harness's B6 check
depends on has never been emitted. **This is a new finding for `00` at the next opportunity, not
a duplicate of an existing one.**

**Answer: can current B6 evidence reliably determine whether IGNORED dominates? NO.** Not
PARTIALLY-AMBIGUOUS — the mechanism has a confirmed, code-level root cause (a manifest field that
has never been populated, papered over by a heuristic with two independently-confirmed failure
directions), traced to specific, named facts on both sides of the failure. **Per the task's own
instruction, Step 7 must be recorded as UNDECIDED, not as disproven** — not because the evidence
is ambiguous, but because the instrument that would decide it is confirmed broken.

---

## Step 5 vs. Step 6 vs. instrument diagnosis

**D — MIXED.** Two independently real problems stand, plus a confirmed instrument defect that
prevents either from being cleanly separated from noise:

1. **Instrument/B6 disposition defect (Check 5)** — confirmed broken since Step 3, affects every
   B7 pass on record, not created by Step 6. Rank this **first**: it is the cheapest to fix (a
   manifest-field/scoring-granularity mechanical bug, zero model calls to repair or re-verify),
   and until it is fixed, no CONTEXT-MISSING/IGNORED-dependent claim about *any* step — including
   Step 5's own closure and any future Step 7 decision — rests on reliable evidence.
2. **Step 5's unmet, apparently uninvestigated ≥80% §A–§D bound (Check 2)** — real, measured
   directly from Step 5's own closing pass, independent of anything Step 6 touched. Rank this
   **second**: rev11 gates Step 6's own meaningfulness on Step 5 ("must be investigated before
   Step 6 can be meaningfully closed" is the task's own framing of this exact scenario).
3. **Step 6's specific §E RED result (58.3%, unchanged by a live, real, confirmed repair)** — real
   as a measured number, but this audit found the number is contaminated by at least one confirmed
   scorer-mechanical bug (E2.4's apostrophe mismatch) and a dominant, well-evidenced
   narrative-vs-literal-keyword mismatch pattern (7 of 10 §E misses traced show the correct source
   was opened and read this session). Rank this **third**: re-measuring or deciding Step 6/6b/7 on
   the current number, before 1 and 2 are addressed, risks making a step-status decision on a
   number this audit cannot certify as clean.

**Does rev11 require Step 5 to be investigated on the current evidence?** Yes, per the rule's own
unconditional text ("≥80%, or investigate") and the measured 44–49% coverage at every pass on
record, including Step 5's own closing pass. This audit recommends investigation; it does not
declare Step 5's status changed — that is Liam's call, per the task's own instruction.

**Should Step 6 remain RED?** Yes, mechanically — the declared §E ≥70% bound is not met (58.3%)
and this audit did not run a new B7 pass to check whether a corrected scorer/disposition would
change that. Recorded alongside: the number is contaminated by confirmed instrument defects, so a
"remains RED" status should not be read as "Step 6's tools don't work" — Check 1 and Check 3 show
the tools are working and correctly retrieving the right documents; the measurement apparatus
around them is what needs repair before the number can be trusted either way.

**Is Step 7 justified, not justified, or currently undecidable?** **UNDECIDABLE**, per Check 5's
own instruction: B6 cannot currently distinguish real IGNORED-dominance from disposition-mechanism
artifacts in either direction. Recorded as UNDECIDED, not disproven, per the task's explicit
instruction.

**Is Step 6b still blocked?** Yes. Rev11 requires Steps 5 *and* 6 both green before Step 6b. Step
6 is RED by its own declared bound, and Step 5's own bound is unmet and (on this audit's evidence)
uninvestigated. Blocked on both counts independently.

**Single next implementation or decision action after this diagnosis:** Repair the B6 disposition
mechanism (Check 5) — restore or replace the `sources` field `context_assembler.py` never emits,
and change `source_arrived`'s disposition computation from per-question to
per-fact-relevant-document — as a standalone, zero-model, mechanical fix, before spending any
further B7 budget on Step 5 investigation, Step 6b, or Step 7. This is a recommendation for
Liam's authorization, not a decision or a rev 12 proposal; no new architecture is implied — this is
a bug fix to an existing, already-designed dependency (rev11's own "B6 must exist before B7 is
run" requirement, which currently is not being met in substance despite running mechanically).

---

## What this audit did NOT establish

- Whether fixing the B6 disposition mechanism, the apostrophe-normalization gap, or the
  keyword-group under-specification (Check 3's negative-case findings) would actually move any
  section's score across the ≥70%/≥80% bounds — no B7 pass was run or is authorized by this task.
- Whether E3.1/E3.2's failure to surface the CCI call transcripts (marked AMBIGUOUS above) is a
  search-ranking defect, a query-construction limitation on David's part, or both — this would
  require either a code-level trace of the FTS ranking function against these exact queries or
  further session sampling, neither performed here.
- Full per-fact classification of every one of §A–§D's 33 present and 42 absent facts — this audit
  fully resolved the four zero-coverage questions named in the task (A2, A4, B3, C4) and all ten
  §E misses, plus a 13-fact blind PASS sample, per the task's stated minimum; it did not exhaustively
  classify every remaining fact in §A–§D.
- B2 total bytes, fresh-bytes-per-turn, and latency sub-bounds from Step 5's full bound list — this
  audit verified the §A–§D coverage sub-bound in depth (the one with decisive, available evidence)
  but did not re-derive B8's byte/latency figures from raw evidence; those are cited from existing
  artifacts, not independently re-measured here.
- Whether `operator-lean`'s tool-contract policy question (flagged open in `step6_repair_report.md`,
  unrelated to §E) has been decided — out of this audit's scope, not touched.
- Any live state as of a time after this audit's own measurements (e.g., `search/os_index.db`'s
  16:16 mtime shows at least one further rebuild after the fresh B7 pass and after the 15:10
  section-E audit; this audit does not know what changed in that rebuild).

---

## Files inspected (representative, not exhaustive)

`docs/ttros/*` (all five canonical files + SOURCE.sha256); source copies in
`/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Reviews/`; `scripts/step3_b7_pass_{A,B}.{raw,scored}.json`;
`scripts/step5_b7_pass_k1.{raw,scored}.json`; `scripts/step6_b7_pass.{raw,scored}.json` (post-repair);
`/home/liam/ttros_backups/step6_b7_pass_RED_20260907T110500Z/step6_b7_pass.{raw,scored}.json` (pre-repair);
`scripts/step6_b7_fresh_pass_transcript.txt`; `scripts/step6_report.md`; `scripts/step6_repair_report.md`;
`scripts/step6_zero_model_diagnosis.md`; `scripts/step6_b7_section_e_source_relevance_audit.md`;
`scripts/step3_b7_harness.py` (QUESTIONS, `source_arrived`, `score_pass` — read only, not modified);
`tools/aos_indexer.py` (current state, `SECRET_CONTENT_RE` line only); `tools/context_assembler.py`
(`manifest` property); `tools/brain_memory.py` (`read_vault_note`); `tools/brain_memory_mcp.py`
(`open_note`, `search_history`); `~/.hermes/profiles/david/state.db` (sessions/messages tables,
read-only, queried directly, not modified); `search/os_index.db` (documents table, read-only);
`sources/historical_calls/{INDEX.md,MANIFEST.md,trent-july-9.md,andrea-roberts-june-26.md,
andrea-second-call-june-30.md,first-call-cci.md,cci-second-call-june-15.md}` (direct vault reads,
read-only, via the Windows-mount source copy). `connectors/`, `workspaces/north_shore_sales_coach/`,
and Telegram bridge files were not read, grepped, or opened at any point.

## Files created

`scripts/step5_step6_b7_reconciliation_audit.md` (this file). No other file in `scripts/` was
created, edited, or overwritten. Scratch analysis scripts used to compute the tables above were
written to this session's private scratchpad directory (outside the repo), not to `scripts/`, per
this task's read-only scope.

## Production files modified: none

## David/Hermes/model calls: 0

Confirmed by design (no `hermes` subprocess invoked by this audit) and by evidence (all
session/answer content used above was read from pre-existing `state.db` and `raw.json` records
created by prior, already-authorized sessions).
