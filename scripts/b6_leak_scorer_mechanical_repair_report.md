# B6 repair, B7 leak closure, and 99-fact scorer verification — mechanical report

Run date: 2026-09-07/08. **Model/Hermes/David/provider calls made by this session: 0.**
No B7, David, or Hermes invocation of any kind (direct or subprocess) was made anywhere in
this session. This step did not run B7, did not start Step 6b/7/8/9, and did not touch
North Shore, the Telegram bridge, credentials, or Hermes's global/default profile.

Authority used: `TTROS_BUILD_PLAN_2026-09-04_rev11.md`, `02_TTROS_ACTIVE_TASK_2026-09-04_rev6.md`,
`00_TTROS_CURRENT_STATE_v2026-09-04_rev6.md`, `TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`,
`01_TTROS_WORKING_METHOD_v2026-09-02.md` (all five mirror hashes verified against
`docs/ttros/SOURCE.sha256` before use, and against the live source in
`/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Reviews/` — all match, no duplicate
revisions), plus `scripts/step5_step6_b7_reconciliation_audit.md`,
`scripts/step5_step6_static_forensic_audit.md`, `scripts/b7_contamination_map_and_clean_subset.md`.

**A note on process.** Part of this step's B6 repair (the `source_arrived`/`extract_tool_reads`
rewrite in `scripts/step3_b7_harness.py` and its 20-test suite, plus a first draft of the Part 2
hook logic) was produced by a research subagent that exceeded its read-only brief mid-session.
Its Part 1 work was reviewed, is sound, and is kept and built on below (the fact-level source
mapping is this session's own addition on top of it). Its Part 2 draft was **not** kept — it
edited the wrong file (see Part 2 below) — and was reverted before anything was wired to a live
profile.

---

## Part 1 — B6 repair

### Root cause

`scripts/step3_b7_harness.py`'s `source_arrived()` (the B6 disposition mechanism) had two
independent defects, both confirmed by direct inspection of real `hermes-*.json` manifests and
by the two prior audits:

1. **Dead key, live fallback.** It read `manifest.get("sources")` — a top-level key
   `tools/context_assembler.py` **never populates** (confirmed against every manifest inspected:
   the real per-source data lives in the manifest's top-level `provenance` list and `actual_reads`
   list, and per-block `sources`). Because that key was always absent, the function fell through
   to a whole-manifest-JSON-blob substring scan on every single call — not a fallback in practice,
   the *only* path ever executed. A path string appearing anywhere in the blob (a warning, an
   unrelated block) counted as "arrived" with no arrival evidence behind it at all.
2. **Blanket question-level disposition.** Even with correct arrival data, disposition was
   `any_source_arrived = any(arrived.values())` across a question's **entire** declared
   `source_docs` list. For any multi-source question, one irrelevant document arriving forced
   *every* missing fact in that question to `IGNORED`, including facts that actually needed a
   different, still-missing document. Confirmed concretely on `A4` (declares `offers.md` +
   `positioning.md`; `positioning.md` arriving previously cleared `A4.1–4.3`, which need
   `offers.md`, to `IGNORED`) and on `E3` (declares 6 docs including
   `operating_context/current_priorities.md`; that one arriving previously cleared `E3.1`/`E3.2`,
   which need the CCI call transcripts, to `IGNORED`) — both independently confirmed in
   `scripts/step5_step6_static_forensic_audit.md` Part 2.

### Repair

- `source_arrived(source_docs, manifest, tool_reads=...)` now reads the manifest's real,
  unconditionally-emitted `provenance` and `actual_reads` fields. A document counts as arrived
  only if a `provenance` hit exists that is **not** tagged `#excluded=<stage>` or
  `#budget=omitted`, or its identity appears in `actual_reads`. The dead `sources` key and the
  whole-blob substring fallback are gone entirely — **absence of authoritative evidence is
  UNARRIVED, never guessed true.** Where a document was excluded, the excluding stage (e.g.
  `step5_map_covers_this`, `budget=omitted`) is recorded, not discarded.
- **Depth-tool arrival.** `extract_tool_reads(session_id)` performs a read-only lookup against
  David's own `~/.hermes/profiles/david/state.db` (`sessions`/`messages`, the same database both
  prior audits used for their tool-call reconstructions) for `mcp__brain__open_note`/`open_call`
  calls in that specific session, and resolves their arguments back to vault-relative paths. A
  document opened live via a depth tool — even if absent from the initial context assembly —
  counts as arrived. This is the confirmed E5.1 case from the reconciliation audit
  (`andrea-roberts-june-26.md` opened via `open_call` mid-session, absent from the initial
  manifest, previously mislabelled `CONTEXT-MISSING`).
- **Fact-level, not just question-level, disposition (this session's addition).** A new
  `FACT_SOURCE_OVERRIDES` map gives 27 individual facts across `A2, A4, B3, E2, E3, E4, E5` their
  own specific required document(s) — narrower than their question's full declared list — derived
  by reading the actual source documents (`memory/offers.md`, `memory/positioning.md`,
  `memory/ideal_clients.md`, the Mike Knapp / CCI / Trent / Andrea Roberts call transcripts) and
  confirming which document each fact's content actually lives in. `score_pass()`'s disposition
  rule (`_disposition_for`) now runs per-fact against `FACT_SOURCE_OVERRIDES.get(fid,
  q["source_docs"])` instead of always against the whole question's list. A fact with no mapping
  entry — genuinely ambiguous between two declared docs, or (E5.4) structurally unanswerable
  regardless of any doc — conservatively falls back to the question-level three-way read rather
  than guessing a narrower mapping without textual evidence. The remaining unmapped-but-ambiguous
  facts are `B3.6`, `E2.3`, `E3.3`, `E4.3`, `E5.4`.
- **Disposition is three-way, never a guess:** `IGNORED` (every doc in scope arrived — the model
  had it and didn't say it), `CONTEXT-MISSING` (no doc in scope arrived), `UNDECIDABLE` (mixed, or
  the map is genuinely ambiguous — never resolved either direction by assumption).

### Before / after, concretely (A4)

| | Before | After |
|---|---|---|
| `offers.md` arrives, `positioning.md` doesn't | every A4 fact → `IGNORED` (wrong for A4.4–4.6) | A4.1–4.3 → `IGNORED`; A4.4–4.6 → `CONTEXT-MISSING` |
| `positioning.md` arrives, `offers.md` doesn't | every A4 fact → `IGNORED` (wrong for A4.1–4.3) | A4.1–4.3 → `CONTEXT-MISSING`; A4.4–4.6 → `IGNORED` |
| neither arrives | `CONTEXT-MISSING` (already correct) | unchanged |
| both arrive | `IGNORED` (already correct) | unchanged |

### Tests

`tests/test_b6_source_disposition.py` — 21 deterministic tests, zero model calls (synthetic
manifests and a synthetic sqlite fixture shaped exactly like `state.db`'s real schema, never the
production database). Covers, by name: arrival via `provenance` and via `actual_reads`,
non-arrival is never guessed true, excluded/`budget=omitted` tags are recorded as drop stage and
not counted as arrival, **two-source separation** (`test_two_source_separation_each_doc_scored_independently`),
**depth-tool retrieval** counting as arrival even when the initial manifest is silent,
**irrelevant-source isolation** (`test_irrelevant_source_arrival_does_not_contaminate_a_different_docs_status`),
**unknown evidence** stays unarrived rather than guessed, the confirmed `A4` two-doc separation at
`score_pass()` level (fact-aware: `A4.1–3` read `CONTEXT-MISSING`, `A4.4–6` read `IGNORED` from the
same manifest), and a question-level fallback proof (`B3`) showing an unmapped, genuinely ambiguous
fact (`B3.6`) still reads the safe `UNDECIDABLE` while a mapped one (`B3.7`) reads confidently.

All 21 pass:

```
$ PYTHONPATH=/home/liam/ttros-testenv/pytest dashboard/backend/.venv/bin/python -m pytest tests/test_b6_source_disposition.py -v
...
21 passed in 0.10s
```

**Scoring policy unchanged.** `present()` (the pass/fail predicate) and every fact's `kw()` groups,
description, and threshold are byte-identical to before this repair. Only the disposition label
attached to a *missing* fact changed; nothing that was PASS is now FAIL or vice versa.

---

## Part 2 — B7 leak closure

### Leak mechanism (from `scripts/b7_contamination_map_and_clean_subset.md`, independently
### re-confirmed by reading the same evidence)

David's generic, unrestricted native tools — `search_files`, `read_file`, `execute_code` — and
the generic `session_search` tool reached the B7 capability-harness question/fact-list document
(`docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`), the frozen scorer
source (`scripts/step3_b7_harness.py`, including its literal `kw()` keyword groups), prior pass
output files (`.raw.json`/`.scored.json`/`.transcript.txt`), and cross-session answer leakage —
16 of 125 traced Step 3/5 question-records were contaminated this way, by two distinct routes:
direct path reads (`read_file(path="docs/ttros/...")`), and ordinary content search incidentally
matching the harness doc's own prose ("CA$750", "ICP-A", "60%" are natural search terms for the
real business answer *and* appear verbatim in the answer key). The four scoped
`mcp__brain__{search_calls,open_call,open_note,search_history}` Business Brain depth tools are
architecturally vault-scoped (`tools/brain_memory.py::_target` resolves and bounds every read to
`VAULT_ROOT`, confirmed by code and by all 125 traced sessions never once returning a
`docs/ttros`/`scripts` path) and were never implicated.

### Exact path-scoped fix

A **new, David-only** hook, `hooks/b7_test_material_guard.py`, registered as
`~/.hermes/profiles/david/config.yaml`'s `pre_tool_call` hook (David had **no** `pre_tool_call`
hook at all before this change):

- **Blocks four tool names outright:** `search_files`, `read_file`, `execute_code`,
  `session_search`. None has a confirmed legitimate use in any of the 125 traced sessions, none
  is on the task's preserved-access list, and each is a confirmed leak mechanism — the first three
  for path/content exposure, `session_search` for the confirmed cross-session answer leak (its
  Step 6 architectural replacement, `mcp__brain__search_history`, is vault-scoped and was never
  observed leaking session content). Blocking by tool name closes **both** the path-read vector
  and the path-free content-search vector — a path-pattern check alone cannot see the latter,
  since a `pre_tool_call` hook only inspects a call's input before it runs, never its result.
- **Defense-in-depth path patterns** (`docs/ttros/`, `scripts/`, the `ttros_backups` harness
  preimage) for any other tool that might one day carry a path argument into that territory.
  `scripts/` is blocked in full, not by an enumerated B6/B7 filename list: every file directly
  under it today (harnesses, gates, diagnosis notes, growth/repair reports, a career-filing
  script, a token roll-up, a dashboard browser-proof) is TTROS engineering-instrument material
  with no legitimate reason for David's own tool calls to reach it. An enumerated-filename
  pattern was tried first and left real gaps on disk (`scripts/step6_prediction.md`,
  `scripts/step5_apply_gate.md`, `scripts/step4_b8_live_exercise.py` — none contain "b6"/"b7" in
  the name); the directory-wide block closes that whole gap class.

**Why a separate script, not `hooks/runtime_guard.py`.** `runtime_guard.py` is the *shared*
`pre_tool_call` hook already wired to the orchestrator and four department profiles
(`aos-delivery`/`aos-marketing`/`aos-ops`/`aos-revenue`). A first draft of this fix added the B7
patterns to that shared file — the wrong blast radius: it would have silently changed behavior
(new `session_search` block, new path blocks) for five profiles this task has no authorization or
evidence basis to touch. That draft was reverted (`git checkout -- hooks/runtime_guard.py`,
confirmed clean) before being wired to anything. The real fix is a new, independent script that
Hermes only ever invokes for the `david` profile.

### Proof legitimate depth tools remain available

`tests/test_b7_test_material_guard.py` (11 tests, all passing) proves both directions: harness
doc, scorer source, prior pass outputs, the preimage backup, and other `docs/ttros/`/`scripts/`
files are blocked (including the three filenames the enumerated-pattern draft missed); the four
`mcp__brain__*` depth tools (`open_note`, `open_call`, `search_calls`, `search_history`) plus
`remember_brain_knowledge`/`brain_memory_status` and the `queue` MCP tool are proven **unaffected**
(`test_legitimate_business_brain_depth_tools_remain_available`,
`test_legitimate_queue_tool_and_non_blocked_tool_names_remain_available`); ordinary non-test-material
paths pass through untouched.

```
$ PYTHONPATH=/home/liam/ttros-testenv/pytest dashboard/backend/.venv/bin/python -m pytest tests/test_b7_test_material_guard.py -v
...
11 passed, 14 subtests passed in 0.03s
```

### Known, documented limit

This hook sees only a tool call's *input*, before the call runs. Blocking `search_files` by name
closes the specific confirmed content-search leak (a path-free query whose result happened to
surface the harness doc's prose) completely for that tool — but a hypothetical future tool with
the same "search everything, no path required" shape and a different name would need its own
name added to `BLOCKED_TOOL_NAMES`. This is a documented limit of an input-only pre-call hook, not
a gap in this fix as scoped.

### Rollback

- `~/.hermes/profiles/david/config.yaml`: preimage saved at
  `/home/liam/ttros_backups/david_config.yaml.PREIMAGE_20260908T044915Z`; rollback is removing the
  added `hooks:` block (or restoring the preimage).
- `hooks/runtime_guard.py`: git-tracked, untouched (reverted from a draft edit to `git`'s clean
  `HEAD` state; preimage also saved at
  `/home/liam/ttros_backups/runtime_guard.py.PREIMAGE_20260908T044915Z` as belt-and-braces).
- `hooks/b7_test_material_guard.py`, `tests/test_b7_test_material_guard.py`: new files; rollback
  is deleting them (nothing else references them).

---

## Part 3 — executable 99-fact scorer verification

`scripts/step_b6b7_part3_scorer_verification.py` imports the real, frozen `QUESTIONS` and the
exact `present()` predicate `score_pass()` uses, and for every one of the 99 non-honesty facts
runs a constructed answer string through that real predicate — not a re-assertion of
`scripts/step5_step6_static_forensic_audit.md`'s hand classification, an independent execution
against it. Full results: `scripts/step_b6b7_part3_scorer_verification.json`.

### Verified counts (99 facts)

| Classification | Count |
|---|---:|
| ALIGNED | 51 |
| UNDER-SPECIFIED | 45 |
| OVER-SPECIFIED | 0 |
| TEXT-NORMALIZATION DEFECT | 2 |
| OTHER MISMATCH | 1 |

This **corrects** the static forensic audit's hand count (56 A / 40 U / 1 O / 1 T / 1 M) in two
ways, both confirmed by direct execution, not re-reading:

1. **`B1.5` was mis-transcribed in that audit's compact notation.** It was written as four
   AND'd single-alternative groups (`{phone} AND {quote} AND {handoff} AND {chasing}`, hence
   "OVER-SPECIFIED — requires all 4 verbatim"). The actual frozen code is
   `kw(["phone", "quote", "handoff", "chasing"])` — **one OR-group of four common words.** A bare
   answer containing only the word "quote" (`"We sent over a quote."`) scores present. This is the
   opposite defect direction: severely **UNDER-SPECIFIED**, not over-specified.
2. **A previously unnamed defect class: polarity/negation-blindness.** `present()` never checks
   whether an answer *asserts* or *denies* a claim, only whether the substrings co-occur anywhere.
   Confirmed executable on four facts the prior audit called ALIGNED: `A5.1` ("Operations tooling
   is our primary wedge, **not** go-to-market work" still scores present for "go-to-market is the
   primary wedge"), `C4.1` (citing "first case study" for something unrelated still scores
   present), `D2.3` ("We're **actively reactivating** both benched projects" — the literal
   opposite of "don't work on either unless reactivated" — still scores present), `E2.3` ("nothing
   about the niche question" still scores present, because "niche" is a substring of "niche
   question"). **This was not swept across all 99 facts** — it is very likely present in other
   multi-root facts too; see remaining unknowns.

### Full non-ALIGNED list (48 of 99 facts)

**UNDER-SPECIFIED (45):** `A1.1, A1.2, A1.3, A1.4, A1.5, A1.6, A2.2, A4.1, A4.2, A4.5, A5.1, A5.2,
A5.3, B1.2, B1.3, B1.5, B2.2, B2.3, B3.1, B3.2, B3.3, B3.4, B3.5, B4.1, B4.2, B4.3, C1.1, C1.2,
C1.3, C4.1, C4.2, C4.3, D1.1, D1.4, D1.5, D2.3, D3.1, D4.1, D4.2, E2.3, E3.2, E4.1, E4.3, E5.2,
E5.3`

**TEXT-NORMALIZATION DEFECT (2):** `B4.5` (latent — requires literal `"90 day"` with a space;
`"90-day"` with a hyphen never matches; has never fired because the fact has never scored PRESENT
in any recorded pass), `E2.4` (**live**, see below).

**OTHER MISMATCH (1):** `E5.4` — its true source is `MANIFEST.md`'s `third_party_opinion`
candidate bullet, which is typed `historical_source` and excluded from assembled context by the
F-BRAINNOTES-1 filter *by design*, and is not even among E5's own declared `source_docs`. No
amount of corpus-reading capability can produce this fact as currently specified; this is a
harness-design question, not a retrieval defect and not something Part 1's B6 repair can fix.

Sub-pattern breakdown of the 45 UNDER-SPECIFIED (a fact can show more than one pattern):
- **List-collapse** (a fact enumerates 3+ items; any one satisfies it): `A5.2, A5.3, B1.5, B2.2,
  B3.2, B3.3, B3.4, B3.5, B4.2, B4.3`.
- **Near-universal / disconnected-keyword** (generic words matched with no proximity requirement
  across the whole answer): `A4.1, B1.3, B2.3, B4.1, D4.2`.
- **Drops a qualifier, name, or secondary clause** (partial credit for a partial claim):
  `A1.1–A1.6, A2.2, A4.2, A4.5, C1.1–C1.3, C4.2, C4.3, D1.1, D1.4, D1.5, D3.1, D4.1, E3.2, E4.1,
  E4.3, E5.2, E5.3`.
- **Polarity/negation-blind** (newly found this session): `A5.1, C4.1, D2.3, E2.3`.

### E2.4 — reproduced against the actual stored production answer

Not a synthetic string: `scripts/step6_b7_pass.raw.json`'s real E2 record (the `step6_post` pass,
the one pass both prior audits and this one agree is contamination-clean).

```json
{
  "real_answer_excerpt": "Mike’s advice was essentially: ...",
  "contains_curly_apostrophe_mikes_advice": true,
  "contains_straight_apostrophe_mikes_advice": false,
  "present_on_real_answer": false,
  "present_after_curly_to_straight_normalization": true
}
```

**E2.4 reproduced: YES.** The real, unmodified answer contains the phrase "Mike's advice" — with
a typographic apostrophe (U+2019) — and the scorer's `kw()` alternative requires a straight
apostrophe (U+0027), no Unicode normalization anywhere in `present()`. Confirmed by direct
execution: FAIL on the real answer, flips to PASS after curly→straight normalization, matched
specifically via the `"mike's advice"` alternative. This independently reproduces
`scripts/b7_contamination_map_and_clean_subset.md` §12's finding.

### Do incomplete answers falsely pass multi-part facts? Yes, confirmed on 45 of 99 facts

Every UNDER-SPECIFIED fact above was confirmed by actually constructing an answer that a human
would judge as materially short of the written fact, and observing `present() == True` on it —
not inferred, executed.

### Scorer semantics unchanged

`present()`, `kw()`, and every fact's groups/description/threshold were imported and run
unmodified; nothing in this script writes to `step3_b7_harness.py`.

---

## Exact human scoring decisions now required

1. **List-collapse threshold.** Should any one alternative of an enumerated list continue to be
   sufficient, or should these require a coverage threshold (e.g. "≥2 of N")? Affects `A5.2, A5.3,
   B1.5, B2.2, B3.2, B3.3, B3.4, B3.5, B4.2, B4.3` (10 facts). Can only lower scores if tightened.
2. **Near-universal/disconnected-keyword tightening.** Should `"not"`, `"un"`, and similarly
   generic alternatives be tightened or given a proximity requirement? Affects `A4.1, B1.3, B2.3,
   B4.1, D4.2` (5 facts). Can only lower scores if tightened.
3. **Polarity/negation-blindness (new).** Should the scorer require any check that a claim is
   *asserted* rather than merely *mentioned or denied*? Affects at minimum `A5.1, C4.1, D2.3,
   E2.3`, confirmed here; very likely broader (not swept across all 99 — see remaining unknowns).
   This is a materially different repair (needs some negation/assertion signal, not just stronger
   substrings) from the other two decision classes and should be scoped separately.
4. **E5.4 — redefine, retire, or make `MANIFEST.md`'s candidate bullet reachable.** Its current
   form cannot pass under any retrieval capability, because its required source is excluded from
   context by design. Retiring it raises the denominator-adjusted score; redefining it changes
   what's tested; leaving it as-is keeps a permanently-unanswerable fact in the 99.
5. **B4.5 — tighten or normalize the space/hyphen literal.** Latent only (has never scored
   PRESENT in any recorded pass), but will misgrade a genuinely correct "90-day" answer the first
   time one is given.
6. **E2.4 — normalize apostrophes in the scorer, or accept the miss.** Confirmed live in 3 of 5
   historical passes (would flip FAIL→PASS under curly→straight normalization in `step3_B`,
   `step6_pre`, `step6_post`, per the contamination map's own sweep); the drop-in fix is a
   `.replace("’", "'").replace("‘", "'")` on the answer before matching, changing no `kw()` group.
7. **Prior Step 3/5 §E (and, per the contamination map, some §A/§B) scores' citability as
   baselines** — unchanged from the contamination map's own finding, restated here for
   completeness: those passes' harness-doc/scorer-source exposure and cross-session leakage mean
   they should not be cited as clean capability measurements without that report's caveats. This
   step's B7 leak closure (Part 2) does not retroactively clean historical passes; it only
   prevents a repeat on any future pass run under David's current profile.

None of items 1–3 or 5–6 have been applied — this step verifies and reports, per its own
instruction, and does not repair the scorer.

---

## Remaining unknowns

- **Polarity/negation-blindness was not swept across all 99 facts** — only demonstrated on 4. The
  scorer's `present()` has no assertion/negation awareness anywhere, so this class plausibly
  extends further; a full sweep is a bounded follow-up, not performed here (out of this step's
  declared scope, which is verification and reporting, not scorer repair).
- **`B3.6`, `E2.3`, `E3.3`, `E4.3`, `E5.4`** have no fact-level source override in the B6 repair —
  confirmed genuinely ambiguous between two of their question's declared docs (or, for `E5.4`,
  unanswerable regardless of any doc) — and fall back to the conservative question-level
  three-way read. A future session with more source-content review could narrow some of these
  further.
- **`hooks/b7_test_material_guard.py` cannot see a tool's output**, only its input — a future tool
  with `search_files`' shape under a different name would need adding to `BLOCKED_TOOL_NAMES`
  explicitly; this is a structural limit of any `pre_tool_call`-only hook, not something this step
  can close without a materially larger (out-of-scope) mechanism.
- **This step does not establish** whether repairing any of the 7 human-decision items above would
  move a section across its declared bound (≥70%/≥80%), and does not authorize or perform a new
  B7 pass to find out.

---

## Single next action

**Liam decides the 7 scoring-policy items above** (list-collapse threshold, near-universal-keyword
tightening, polarity/negation-blindness scope, E5.4's fate, B4.5's normalization, E2.4's
normalization, and historical baseline citability) before any scorer repair or new B7 pass is
authorized. Once decided, the scorer repair itself and a single fresh B7 pass under the now-closed
David profile (Part 2) are the next mechanical steps — neither is performed by this task.

---

## Validation

- **Model/provider/Hermes/B7 calls made by this session: 0.**
- **North Shore, Telegram bridge, credential stores: not read, grepped, opened, or edited.**
- **Hermes global/default profile: untouched** (only the David-specific profile config and a
  David-only new hook file were changed).
- **Step 6b/7/8/9: not started.**
- **Legitimate Business Brain depth tools (`search_calls`, `open_call`, `open_note`,
  `search_history`) confirmed preserved** by `tests/test_b7_test_material_guard.py`.
- **No git commit, no git push.**

```
$ git diff --check
context/TOKEN_POLICY.md:94: new blank line at EOF.
hooks/token_budget_check.md:54: new blank line at EOF.
```
Both are the two pre-existing whitespace defects present in `git status` before this session
began; not touched, not repaired here (out of this step's declared scope).

```
$ git status --short
```
Unchanged from the pre-task snapshot except new untracked files: `hooks/b7_test_material_guard.py`,
`scripts/step3_b7_harness.py` (was already untracked, now carries the B6 repair),
`scripts/step_b6b7_part3_scorer_verification.py`,
`scripts/step_b6b7_part3_scorer_verification.json`, `tests/test_b6_source_disposition.py`,
`tests/test_b7_test_material_guard.py`, this report. `hooks/runtime_guard.py` reverted clean —
zero diff from `HEAD`. No file under `connectors/`, `workspaces/north_shore_sales_coach/`, or any
credential store appears anywhere in this diff.

Full regression suite (repo root, `PYTHONPATH=/home/liam/ttros-testenv/pytest
dashboard/backend/.venv/bin/python -m pytest`):

```
804 passed, 7 warnings, 209 subtests passed in 366.57s (0:06:06)
```

772 (declared baseline) + 32 new tests added this step (21 in `test_b6_source_disposition.py` +
11 in `test_b7_test_material_guard.py`) = 804 exactly. **0 failed.**

---

## Closeout

- **Verdict: PASS.**
- **B6 repaired / fact-aware / authoritative:** yes — 27 facts across 6 multi-source questions
  have explicit source mapping; the remainder use a safe, three-way question-level fallback that
  is itself repaired (was previously a blanket `any()` guess).
- **Depth-tool retrieval recognized:** yes — `extract_tool_reads`, tested.
- **B7 leak closed path-specifically:** yes, for the confirmed mechanism (David-only, 4 tool names
  + defense-in-depth path patterns); documented limit for a hypothetical future tool with the same
  shape under a different name.
- **Legitimate Brain tools preserved:** yes, tested (11 passing tests).
- **99 scorer facts executable-verified:** yes — 0 predicted/observed mismatches after fixing two
  authored-test-construction errors and finding one real correction to prior classifications.
- **ALIGNED / UNDER-SPECIFIED / OVER-SPECIFIED / TEXT-NORMALIZATION / OTHER counts:** 51 / 45 / 0 / 2 / 1.
- **E2.4 reproduced:** yes, against the real `step6_b7_pass.raw.json` answer.
- **Regression result:** 804 passed, 0 failed (772 baseline + 32 new tests this step), full suite,
  run from repo root with `PYTHONPATH=/home/liam/ttros-testenv/pytest
  dashboard/backend/.venv/bin/python -m pytest`.
- **Files touched:** `hooks/b7_test_material_guard.py` (new), `scripts/step3_b7_harness.py` (B6
  repair), `scripts/step_b6b7_part3_scorer_verification.py` (new),
  `scripts/step_b6b7_part3_scorer_verification.json` (new), `tests/test_b6_source_disposition.py`
  (new), `tests/test_b7_test_material_guard.py` (new), this report (new). Local, non-repo:
  `~/.hermes/profiles/david/config.yaml` (added `hooks.pre_tool_call`, preimage backed up).
  `hooks/runtime_guard.py` touched then reverted to clean `HEAD`.
- **Blockers:** none for this step's own completion. The 7 scoring-policy decisions above block
  any *further* scorer repair or new B7 pass, by design.
- **Single next action:** Liam decides the 7 scoring-policy items above.
- **Model/provider calls: 0. B7 calls: 0.**
- **Token usage:** unavailable from current CLI output.
