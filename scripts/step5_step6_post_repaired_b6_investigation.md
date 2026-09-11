# §13 step 2 prerequisite pass — B1.2/B3.1 classification + repaired B6 disposition over step6_post

Run date: 2026-09-08. Zero model / Hermes / David / provider calls made anywhere in this session.
Instrument: `scripts/step5_step6_post_repaired_b6_investigation_instrument.py`, teed transcript
`scripts/step5_step6_post_repaired_b6_investigation_instrument.txt`. `docs/ttros/SOURCE.sha256`
checked against the two mirrors used (`TTROS_B7_SCORING_FIDELITY_CONTRACT_v2.1_2026-09-08.md`,
`TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`) before use — both match.

---

## Part 1 — B1.2 and B3.1 classification

Contract §7.1: both facts appear in the 45-item UNDER-SPECIFIED list but in none of the repair
report's four named sub-patterns (list-collapse / disconnected-keyword / drops-a-qualifier /
polarity-blind), and nobody had recorded what is specifically wrong with them. Re-derived by
executing the real frozen predicate (`step3_b7_harness.py`'s `score_pass()`), the same method
`scripts/b6_leak_scorer_mechanical_repair_report.md` Part 3 used.

### B1.2

- Frozen fact: *"Tailored to the owner's operational friction (time/capacity/revenue) then the
  practical system."* Predicate: `kw(["friction"])` — one group, one alternative.
- Executed:
  - Positive control (states audience-tailoring + cost dimension + system-build clause) → **PRESENT**.
  - False positive (`"We sometimes see friction between the sales and delivery teams
    internally."`) → **PRESENT**, despite containing none of the fact's three required elements.
  - False negative (states the actual substance, omits the bare word "friction") → **ABSENT**.
- **Classification: UNDER-SPECIFIED. Contract §5 category: §5.3 Essential/composite qualifiers.**
  §5.3 states verbatim: *"Mentioning the main noun or activity does not establish a composite fact
  when a material qualifier is absent."* "friction" is the main noun; the audience-tailoring and
  system-build-follow-through clauses are the essential qualifiers the predicate drops entirely.
  Not repaired — repair is out of scope for this pass.

### B3.1

- Frozen fact: *"Core consulting market broader than either prospecting segment."* Predicate:
  `kw(["broader"])` — one group, one alternative.
- Executed:
  - Positive control → **PRESENT**.
  - False positive (`"Our client base is broader now than it was two years ago,
    geographically."`) → **PRESENT**, unrelated to prospecting segments entirely.
  - False negative (states the actual substance — market not limited to either ICP — without the
    word "broader") → **ABSENT**.
- **Classification: UNDER-SPECIFIED. Contract §5 category: §5.3 Essential/composite qualifiers.**
  §5.3's own list of recurring essential classes names **"broad market vs prospecting segment"
  verbatim** — B3.1 *is* that named class. The predicate drops the essential "vs prospecting
  segment" referent and accepts any incidental use of the comparative word "broader." Not repaired.

Neither fact turned out ALIGNED, so §7.2's expansion rule does not apply here — this run instead
discharges §7.1's requirement to name what's wrong with each, closing the "two unclassified facts"
gap without touching the repair population's size or the scorer.

---

## Part 2 — repaired three-way B6 disposition over step6_post

### B6 implementation identified

`scripts/step3_b7_harness.py` — the repair was made in place (root cause and fix: dead `sources`
key / whole-blob substring fallback replaced with real `provenance`+`actual_reads` reads, plus a
`FACT_SOURCE_OVERRIDES` map for 27 facts and a three-way `_disposition_for` rule), per
`scripts/b6_leak_scorer_mechanical_repair_report.md` Part 1. `scripts/step6_b7_tools_harness.py`
imports this exact file by path for `QUESTIONS`/`score_pass`/`extract_tool_reads`, so this is also
the scorer that produced `step6_b7_pass.scored.json` originally — except that file predates the
repair (file mtimes: `step6_b7_pass.scored.json` written before `step3_b7_harness.py`'s repair
commit), confirmed independently by its `source_arrived` field being a flat `{doc: true/false}`
map, not the repaired function's `{doc: {"arrived":, "evidence":, "drop_stage":}}` shape. **The
on-disk `step6_b7_pass.scored.json` is stale and was not used** — this run recomputes fresh via
`score_pass()` over `step6_b7_pass.raw.json`, using the loaded, current, repaired module.

- SHA-256 of `scripts/step3_b7_harness.py`:
  `2d2aef167321ae7bbf0ba639db027ab92320e0a3b9cd5ce3a46b2a061b1200d4`

### Rehearsal (before touching real data)

Three synthetic fixtures, using real question/fact structures with constructed manifests:

| Fixture | Question/fact | Manifest | Result |
|---|---|---|---|
| CONTEXT-MISSING | A4 / A4.1 | empty (no provenance, no actual_reads, no depth-tool reads) | `CONTEXT-MISSING` ✓ |
| IGNORED | A4 / A4.1 | `memory/offers.md` arrives live via provenance | `IGNORED` ✓ |
| UNDECIDABLE | E4 / E4.1 (3-doc fact-level override) | only 1 of 3 required docs arrives | `UNDECIDABLE` ✓ |

**All three dispositions demonstrated: yes.** The run is interpretable.

### Evidence-completeness finding (recorded, not acted on beyond what B6 needs)

`scripts/step6_post_full_tool_surface_verification.json` was expected to carry per-call
argument/output detail for depth-tool evidence. On inspection it contains only a `qid→session_id`
map, summary counts, and an **empty** `contaminated_candidates` list — the full per-call record
list that `step6_post_full_tool_surface_verification.py` builds is never persisted to JSON, only
the filtered contamination-candidate subset is. It therefore cannot supply resolved
document-identity evidence for the depth-tool arm as described. Rather than write a new state.db
parser, this run calls the repaired B6's own `extract_tool_reads(session_id)` function — the same
read-only, zero-model-call function `call_david()` already invokes live inside
`step3_b7_harness.py` — once per stored session_id (from the 25 `step6_b7_pass_*.usage.json`
files). This reuses the frozen instrument rather than re-deriving anything new.

### Predeclared predictions (recorded before the real disposition was computed)

- Rev11 Step 3 (predeclared, contract): **"CONTEXT-MISSING dominant."**
- This instrument's own predictions (recorded in the transcript before scoring): ~52 unmet facts,
  split roughly CONTEXT-MISSING ~30 / IGNORED ~12 / UNDECIDABLE ~10; evidence classes roughly
  override ~15 / manifest ~28 / depth-tool ~7 / no-evidence ~2; present-but-in-defect-population
  ~10–15.

### Population

Dispositions apply to facts **not** met under the current (unrepaired-predicate,
repaired-disposition) scorer — a subset of the true unmet set, since 24 currently-PRESENT facts
sit inside the 48-fact defect population and will re-enter the unmet set once the scorer itself is
repaired (see below).

- All non-honesty sections (A–E): 99 facts total, 47 present, **52 unmet**.
- Sections A–D only (the ≥80%-or-investigate bound's actual population — offers/positioning/
  pipeline/priorities, excludes E=call corpus and F=honesty): 75 facts total, 33 present, **42
  unmet**. 33/75 = 44.0%, exactly reconciling contract §15's cited `step6_post` figure.

### Three-way totals

**All sections A–E (52 unmet):**

| Disposition | Count | % |
|---|---:|---:|
| CONTEXT-MISSING | 27 | 51.9% |
| IGNORED | 21 | 40.4% |
| UNDECIDABLE | 4 | 7.7% |

**Sections A–D only (42 unmet):**

| Disposition | Count | % |
|---|---:|---:|
| CONTEXT-MISSING | 25 | 59.5% |
| IGNORED | 17 | 40.5% |
| UNDECIDABLE | 0 | 0.0% |

### Evidence-class breakdown (A–E, 52 unmet; precedence: fact-level override → manifest
provenance/actual_reads → depth-tool → no usable evidence; reconciles exactly to 52)

| Evidence class | Total | CONTEXT-MISSING | IGNORED | UNDECIDABLE |
|---|---:|---:|---:|---:|
| Fact-level source override (27 facts have one; 24 of them are unmet) | 24 | 12 | 10 | 2 |
| Manifest provenance / actual_reads (no override) | 9 | 0 | 9 | 0 |
| Depth-tool reads (no override, no manifest evidence) | 4 | 0 | 2 | 2 |
| No usable evidence at all | 15 | 15 | 0 | 0 |
| **Total** | **52** | **27** | **21** | **4** |

**Dominant evidence class: fact-level source override (24/52, 46%).** No single class carries a
bare majority on its own; override plus manifest-only evidence together account for 33/52 (63%),
and the "no usable evidence" bucket (necessarily 100% CONTEXT-MISSING by the disposition rule's
own construction — no evidence for any doc means `not any(flags)`) accounts for the next largest
share (15/52, 29%). Depth-tool evidence, despite step6_post's heavy use of the four new
`mcp__brain__*` tools (34 of 46 total tool calls per
`step6_post_full_tool_surface_verification.md`), resolved only 4 of 52 unmet facts — the tools
were used, but rarely for a document that was the SPECIFIC missing source of an otherwise-unmet
fact. This headline is not carried by a single weak arm; it is a mix, reported as such.

### Per-question disposition summary

| Q | Present | CONTEXT-MISSING | IGNORED | UNDECIDABLE |
|---|---:|---:|---:|---:|
| A1 | 6 | 0 | 1 | 0 |
| A2 | 0 | 4 | 0 | 0 |
| A3 | 1 | 4 | 0 | 0 |
| A4 | 0 | 6 | 0 | 0 |
| A5 | 3 | 1 | 0 | 0 |
| B1 | 2 | 3 | 0 | 0 |
| B2 | 3 | 1 | 0 | 0 |
| B3 | 0 | 0 | 7 | 0 |
| B4 | 2 | 3 | 0 | 0 |
| C1 | 3 | 0 | 0 | 0 |
| C2 | 6 | 0 | 2 | 0 |
| C3 | 1 | 0 | 1 | 0 |
| C4 | 0 | 3 | 0 | 0 |
| D1 | 1 | 0 | 4 | 0 |
| D2 | 3 | 0 | 0 | 0 |
| D3 | 1 | 0 | 1 | 0 |
| D4 | 1 | 0 | 1 | 0 |
| E1 | 9 | 0 | 0 | 0 |
| E2 | 1 | 0 | 3 | 0 |
| E3 | 2 | 2 | 0 | 0 |
| E4 | 1 | 0 | 0 | 2 |
| E5 | 1 | 0 | 1 | 2 |

### Currently-PRESENT-but-in-defect-population

**24 of the 47 currently-present facts** sit inside the 48-fact defect population (45
under-specified, 2 normalization, 1 source-contract): `A1.1, A1.2, A1.3, A1.4, A1.5, A1.6, A5.1,
A5.2, A5.3, B1.2, B1.5, B2.2, B2.3, B4.2, B4.3, C1.1, C1.2, C1.3, D1.1, D2.3, D3.1, D4.1, E2.3,
E5.2`. This bounds how far the aggregate can move once the scorer is repaired: half of everything
currently counted "present" is a false positive under a known-defective predicate, and each will
re-enter the unmet population — with its own, not-yet-computed B6 disposition — once repaired.
This run does not re-derive that larger true-unmet set; it reports the bound, as required.

### Verdict on the predeclared prediction

**"CONTEXT-MISSING dominant" is SUPPORTED, on both populations measured:**

- All sections A–E: CONTEXT-MISSING is the largest bucket (27/52, 51.9%) — a strict majority of unmet facts.
- Sections A–D only (the bound's actual population): CONTEXT-MISSING is the largest bucket (25/42, 59.5%) — a strict majority.

No UNDECIDABLE result and no single-label uniformity occurred in either population (compare: prior
runs where B6 could only ever emit one label). The rehearsal in Part 2 demonstrated the detector
can produce all three outcomes, and the real run in fact produced two of the three at high volume
(CONTEXT-MISSING and IGNORED) and the third (UNDECIDABLE) at low but non-zero volume in the
all-sections view (0 in A–D specifically, entirely from E4/E5's multi-doc call-transcript facts).

---

## What this resolves, and what it does not

**Resolves:**

- §7.1's two unclassified facts (B1.2, B3.1) are now classified — both UNDER-SPECIFIED, both §5.3
  Essential/composite qualifiers, by direct execution against the frozen predicate.
- Contract §13 step 2's second and third prerequisite items are complete: the repaired three-way
  B6 disposition has been run over `step6_post`'s stored records (a functioning three-way split,
  not the pre-repair "never functioned" state), broken down by evidence class as required, and this
  run is recorded as the missing Step 5 "≥80%-or-investigate" investigation per §15.
- It answers the specific question §15 posed: on `step6_post`, the low §A–D coverage figure (44.0%)
  is **predominantly a CONTEXT-MISSING (retrieval) defect, not an IGNORED (reasoning) defect** —
  25 of 42 A–D-unmet facts (59.5%) had no in-scope source document arrive at all, versus 17 (40.5%)
  where the document arrived and David simply didn't state the fact.

**Does not resolve / does not change:**

- Step 5's status label is unchanged: **IMPLEMENTATION COMPLETE / CAPABILITY BOUND UNRESOLVED**
  stands per §15. This investigation discharges what Step 5 owed; it does not turn Step 5 green,
  because the underlying scorer is still known-defective (48 of 99 facts) and no repair has been
  made.
- The 52/42-fact unmet populations measured here are **subsets of the true unmet population** —
  24 currently-PRESENT facts are false positives under the defective predicate and are not
  included in this disposition; the true population is larger and has not been measured.
- No scorer rule, predicate, threshold, or frozen fact was changed. No B7 pass was run. Validation
  A was not started.

---

## Zero-call statement

This session made **zero** model, Hermes, David, or provider calls. The only computation was
Python execution of the already-frozen `score_pass()`/`source_arrived()`/`extract_tool_reads()`
functions over stored JSON records and a read-only SQLite connection (`mode=ro`) to
`~/.hermes/profiles/david/state.db` for depth-tool-read resolution — no writes, no network, no
model invocation of any kind.

---

## Findings outside scope (recorded, not acted on)

- `step6_b7_pass.scored.json` on disk is stale (pre-repair `source_arrived` shape) and should not
  be cited as current B6 evidence by any future step until regenerated.
- `step6_post_full_tool_surface_verification.json`/`.md` do not themselves carry resolved per-call
  document identities despite being described that way; the full per-call record list their own
  script computes is never persisted, only a filtered (here: empty) contamination-candidate subset.
- E4 and E5 are the only two questions producing UNDECIDABLE dispositions (2 each, all sections);
  both are multi-document call-transcript facts under `FACT_SOURCE_OVERRIDES` with partial arrival.

---

## Reconciliation (2026-09-08, later session) — the depth-tool arm was non-compliant

**A follow-up trace proved that `extract_tool_reads()`, used above for the depth-tool-read
evidence arm, directly opens `~/.hermes/profiles/david/state.db` and executes a read-only SQLite
query for `messages.tool_calls`.** The task that commissioned this reconciliation required that
depth-tool arrival evidence NOT be re-derived from `state.db`. Part 2's disposition and
evidence-class figures above were therefore computed using a non-compliant evidence source. This
section corrects that, using only stored artifacts and source code — zero `state.db` access, zero
model/Hermes/David/provider calls — and does not touch Part 1 (B1.2/B3.1 classification), which
never used depth-tool evidence at all.

### Part 1 — candidate compliant stored artifacts, inspected

| # | Path | SHA-256 | Pre-exists this reconciliation? | Represents | Session identity? | Actual tool-call names? | Args/outputs? | Ties call→document identity? |
|---|---|---|---|---|---|---|---|---|
| 1 | `scripts/step6_post_full_tool_surface_verification.json` | `b3e8d23652738ebc4ee008e55ddf57f700cd9d03b4bfbabff4647657f5f4dcf6` | Yes — mtime 2026-09-08 15:27:59, before this reconciliation session began (17:21+) | `step6_post`'s 25 sessions, contamination sweep | Yes (`qid→session_id` map) | Only an aggregate `distinct_tool_names` list, not per-call | No — `contaminated_candidates` is an empty filtered list; the full per-call record array the script builds in memory is never persisted (confirmed by reading `.py` source, line ~246-267 vs the `json.dump` at line ~318, which serializes only the filtered subset) | No |
| 2 | `scripts/step6_post_full_tool_surface_verification.py` | `7778829c723cb0fffd97d60405bd40646b4fbcf624756b05de8cf711225b2047` | Yes — same run | Source of #1; documents what was and wasn't persisted | N/A (code) | N/A (code) | N/A (code) | N/A — confirms #1's limitation, doesn't cure it |
| 3 | `scripts/step6_post_full_tool_surface_verification.md` | `06da6f61ae7a0f2af3f42dd16cf48d92df6eba437dc69da7e09607c94a831b2a` | Yes — mtime 2026-09-08 15:30:13 | Narrative report of #1's run | Yes (session IDs referenced in prose) | Yes (7 tool names named and described) | Only in illustrative prose (e.g. "C1 session called `search_files`"), not as a structured, queryable per-fact record | No — its own Part F states the check is about contamination (test-material leakage), not about which document arrived for which fact |
| 4 | `scripts/step6_post_full_tool_surface_verification.txt` | `d8269761774f05bd89386dc9a95b0975342b2027cfb7c66f3cd5eb403f8318e9` | Yes — same run | Teed transcript of #1 | No (aggregate only) | Yes (aggregate list) | No — only summary line counts | No |
| 5 | `scripts/b7_contamination_map_and_clean_subset.md` | `812bbab515912086f81bda2b6749e58028544bdb3ab57e3edb250321af155280` | Yes — mtime 2026-09-07 19:17:17 (dated, prior session) | Cross-pass contamination sweep incl. `step6_post`, produced by directly querying `state.db` **at the time it was run** | Yes, in prose for specific cited examples | Yes, in prose for specific cited examples (e.g. "C1 session... called `search_files`") | Only for the handful of examples quoted in prose; not a structured per-call table for all 46 calls | No, not systematically — a few named examples only, not a resolvable index by fact ID |
| 6 | `scripts/b6_leak_scorer_mechanical_repair_report.md` | `bedaff2746d9e1cc8457a823a897488b23d081cb1a2cd320c0ca988e3b5c9f24` | Yes — mtime 2026-09-07 22:12 | B6 repair narrative; cites `step6_post`'s E2 record for one apostrophe example | N/A | N/A | No per-call detail | No |
| 7 | `scripts/step6_b7_pass.raw.json` | `9f1405baeeb2781f60731ca2138e59514dc5488a073e2796fac8efd6712c0dcd` | Yes — mtime 2026-09-07 13:53:43 | The harness's own stored per-question output: `usage.session_id`, `manifest.provenance`, `manifest.actual_reads`, final `answer` | Yes (`session_id` per question) | No — does not store a tool-call trace at all (by design; confirmed in `step6_post_full_tool_surface_verification.md` Part A) | `provenance`/`actual_reads` are themselves structured, resolved document-identity records — but only for documents that arrived via the **initial context assembly**, not via a mid-session depth-tool open | For docs that arrived via manifest: yes, directly and structurally. For docs that arrived only via a depth-tool call: no — this file structurally cannot see those (that's the entire reason `extract_tool_reads()` exists as a separate, additional arm) |
| 8 | `scripts/step3_b7_harness.py` | `2d2aef167321ae7bbf0ba639db027ab92320e0a3b9cd5ce3a46b2a061b1200d4` | Yes — the frozen B6 implementation, source code not evidence | `QUESTIONS`, `FACT_SOURCE_OVERRIDES`, `source_arrived()`, `score_pass()` — deterministic and reusable without calling `extract_tool_reads()` | N/A | N/A | N/A | N/A — used as computation, not as an evidence artifact |

**`step6_post_full_tool_surface_verification.json` judged by its actual contents (per the task's
explicit instruction), not by how the prior investigation's Part 2 note described it:** it is an
aggregate summary (session-id map + tool-name list + an empty contamination-candidate list). It
does not tie any specific stored tool call to a specific document/source identity for any
specific fact. A session-id map alone is insufficient per the governing sufficiency rule, and
that is exactly what artifacts #1 and #4 are.

**Sufficiency determination: no candidate artifact ties `step6_post session → actual stored tool
call → document/source identity` through explicit stored arguments or returned metadata.** The
one and only place that link exists on disk is `messages.tool_calls` inside `state.db` itself
(confirmed by reading `extract_tool_reads()`'s own implementation, `scripts/step3_b7_harness.py`
lines 691-746: it parses `tool_calls[].function.arguments` — `pointer` for `open_note`, `call_id`
for `open_call` — and that argument payload is not duplicated anywhere else on disk). **Branch B
applies: sufficient compliant stored evidence does NOT exist.**

### Part 2 — reconciliation method and an important correction to scope

Per Branch B, facts whose disposition depended on unavailable depth-tool arrival evidence must
either be resolved by another higher-precedence compliant arm (fact-level override docs list,
manifest provenance/actual_reads) or classified `UNDECIDABLE`. To find every such fact
mechanically — without calling `extract_tool_reads()` or opening `state.db` — a new instrument,
`scripts/step5_step6_post_repaired_b6_reconciliation_instrument.py` (SHA-256
`790f469537490f35d203d36b12b2aaddd800e31746adb476e32256d86f5428ea`), recomputes the exact same
`score_pass()` disposition over the exact same stored `step6_b7_pass.raw.json` records, with
`tool_reads` forced to `[]` for every record — `extract_tool_reads()` is never called. As a
fail-closed control, `sqlite3.connect()` is monkeypatched before the frozen B6 module is loaded to
raise if any path containing `state.db`, `.hermes`, or `profiles` is opened. **Per this repo's
evidence-discipline rule that a detector must be able to return both answers, the guard was
rehearsed against a real `extract_tool_reads(session_id)` call before being trusted**: the guard's
interceptor fired (confirmed by an invocation counter, before=0/after=1 — not by exception
propagation, since `extract_tool_reads()`'s own fail-soft contract catches every exception
internally, including `ForbiddenAccess`, and returns `frozenset()`; this swallow-all behavior is
itself recorded as a finding, not a defect in the guard). The instrument hard-stops if that
rehearsal does not show the counter incrementing. The real recompute below never calls
`extract_tool_reads()` at all (`tool_reads` is force-assigned `[]` directly), so the guard is a
belt-and-suspenders check, not the primary compliance mechanism — but it is now shown capable of
actually firing. SHA-256 of the instrument:
`790f469537490f35d203d36b12b2aaddd800e31746adb476e32256d86f5428ea`. Transcript:
`scripts/step5_step6_post_repaired_b6_reconciliation_instrument.txt` (SHA-256
`b3738ae7cd7b7d043d7b05723c9e015ce6d2f6c4bb95132f6f27f10e304396c9`).

**Finding that changes the scope of the correction:** the prior investigation's own
`classify_evidence()` checks `is_override` *before* inspecting per-doc evidence types, so a fact
with docs under `FACT_SOURCE_OVERRIDES` is always counted in the `fact_level_override` bucket for
reporting purposes — regardless of whether the arrival evidence behind that disposition was
`manifest_provenance` or `depth_tool`. The originally reported `depth_tool: total=4` row is
therefore **not** the complete set of facts whose disposition depended on depth-tool evidence; it
is only the subset that *also* happened to have no fact-level override. The compliant-only
recompute make this visible directly: comparing its per-question breakdown against the original
investigation's own published per-question table (transcribed verbatim into the new instrument,
not re-derived) shows **five** questions differ — `A1`, `B3`, `E2`, `E4`, `E5` — covering **16**
facts, not 4. This is recorded as a direct correction to the original investigation's evidence-class
scope, not a new B7 pass or a scorer change.

Of these 16:
- **4** were already visible under the original `depth_tool` evidence-class label: `A1.7`,
  `B3.6`, `E4.3`, `E5.4` (originally CONTEXT-MISSING=0, IGNORED=2, UNDECIDABLE=2 — matches exactly).
- **12** were hidden inside the original `fact_level_override` bucket (which totalled 24, of which
  12 were CONTEXT-MISSING and *unaffected* — those 12 have zero evidence under either compliant or
  non-compliant evaluation and are not touched by this correction): `B3.1`, `B3.2`, `B3.3`,
  `B3.4`, `B3.5`, `B3.7`, `E2.1`, `E2.2`, `E2.4`, `E4.1`, `E5.1`, `E5.3`.

For all 16, the compliant-only recompute shows **zero** surviving manifest evidence for any of
their declared source docs (their compliant disposition is uniformly `CONTEXT-MISSING`, i.e. "no
evidence for any doc") — no higher-precedence arm independently resolves any of them. Per Branch
B, all 16 are reclassified `UNDECIDABLE` rather than left at the mechanical `CONTEXT-MISSING`
fallback, because that fallback would silently assert "this document did not arrive," which this
reconciliation cannot support or refute compliantly — `UNDECIDABLE` is the honest label.

**Old vs. corrected disposition, every affected fact:**

| Fact | Old disposition | Evidence class (original label) | Corrected disposition | Evidence for correction |
|---|---|---|---|---|
| A1.7 | IGNORED | depth_tool | UNDECIDABLE | Compliant recompute: zero evidence for all docs_used once `tool_reads` removed |
| B3.1 | IGNORED | fact_level_override | UNDECIDABLE | Same |
| B3.2 | IGNORED | fact_level_override | UNDECIDABLE | Same |
| B3.3 | IGNORED | fact_level_override | UNDECIDABLE | Same |
| B3.4 | IGNORED | fact_level_override | UNDECIDABLE | Same |
| B3.5 | IGNORED | fact_level_override | UNDECIDABLE | Same |
| B3.6 | IGNORED | depth_tool | UNDECIDABLE | Same |
| B3.7 | IGNORED | fact_level_override | UNDECIDABLE | Same |
| E2.1 | IGNORED | fact_level_override | UNDECIDABLE | Same |
| E2.2 | IGNORED | fact_level_override | UNDECIDABLE | Same |
| E2.4 | IGNORED | fact_level_override | UNDECIDABLE | Same |
| E4.1 | UNDECIDABLE | fact_level_override | UNDECIDABLE (reason corrected) | Same — was already UNDECIDABLE, but for the wrong stated reason; now correctly grounded as depth-tool-dependent |
| E4.3 | UNDECIDABLE | depth_tool | UNDECIDABLE (reason corrected) | Same |
| E5.1 or E5.3 | one is IGNORED, the other UNDECIDABLE | fact_level_override | both UNDECIDABLE | Same. **Which of the two was originally IGNORED vs. UNDECIDABLE cannot be recovered from stored data** — the original report/transcript persisted only per-question aggregate counts (E5: present=1, IGNORED=1, UNDECIDABLE=2), not a per-fact disposition list. Both facts are independently confirmed depth-tool-dependent and both correct to UNDECIDABLE regardless of which held which label before. |
| E5.4 | UNDECIDABLE | depth_tool | UNDECIDABLE (reason corrected) | Same |

Net count movement (all 16 facts move out of CONTEXT-MISSING-eligible-by-default and into
UNDECIDABLE; none were originally CONTEXT-MISSING and none become CONTEXT-MISSING): **12 facts
move IGNORED → UNDECIDABLE; 4 facts were already UNDECIDABLE and are reconfirmed as such for the
correct (depth-tool-dependent, now-unresolvable) reason.**

### Corrected totals

**All sections A–E (52 unmet, unchanged population size):**

| Disposition | Old count | Old % | Corrected count | Corrected % |
|---|---:|---:|---:|---:|
| CONTEXT-MISSING | 27 | 51.9% | 27 | 51.9% (unchanged) |
| IGNORED | 21 | 40.4% | 9 | 17.3% |
| UNDECIDABLE | 4 | 7.7% | 16 | 30.8% |

**Sections A–D only (42 unmet, unchanged population size):**

| Disposition | Old count | Old % | Corrected count | Corrected % |
|---|---:|---:|---:|---:|
| CONTEXT-MISSING | 25 | 59.5% | 25 | 59.5% (unchanged) |
| IGNORED | 17 | 40.5% | 9 | 21.4% |
| UNDECIDABLE | 0 | 0.0% | 8 | 19.0% |

Both reconcile exactly to their populations (52 and 42 respectively; verified in the
reconciliation transcript). **CONTEXT-MISSING's count and percentage are unchanged in both
populations** — none of the 16 corrected facts were originally counted as CONTEXT-MISSING, and
none become CONTEXT-MISSING under correction (Branch B routes them to UNDECIDABLE, never to
CONTEXT-MISSING). Only the IGNORED/UNDECIDABLE split moves.

### Part 3 — the predeclared prediction, re-interpreted after correction

Predeclared wording: `CONTEXT-MISSING dominant`. No numeric threshold for "dominant" is defined
anywhere in the governing contract; the original investigation's own verdict already reported both
the plurality result and the >50% result separately rather than inventing a threshold, and this
reconciliation does the same.

- **All sections A–E:** CONTEXT-MISSING = 27/52 = 51.9%. Largest disposition by plurality: **yes**
  (9 IGNORED, 16 UNDECIDABLE, both smaller). Exceeds 50%: **yes** (strict majority).
- **Sections A–D only:** CONTEXT-MISSING = 25/42 = 59.5%. Largest disposition by plurality:
  **yes**. Exceeds 50%: **yes** (strict majority).

**These are numerically identical to the original investigation's figures for CONTEXT-MISSING
specifically**, because the correction only moved facts between IGNORED and UNDECIDABLE, never
into or out of CONTEXT-MISSING. **Verdict on the predeclared prediction: unchanged —
SUPPORTED (strict majority) on both populations.** This reconciliation does not overturn Step 5's
predeclared-prediction verdict; it corrects the IGNORED/UNDECIDABLE split beneath it and reveals
that a materially larger fraction of the unmet population (30.8% of A–E, 19.0% of A–D) is properly
`UNDECIDABLE` — genuinely unresolvable from compliant evidence — than the original investigation
reported (7.7% / 0.0%).

### B1.2 / B3.1 status

Part 1's classification finding is **unchanged**: both remain UNDER-SPECIFIED, §5.3
Essential/composite qualifiers, by direct predicate execution — that classification never used
depth-tool evidence and this reconciliation found no contradictory evidence about it. **B1.2 is
unaffected by this reconciliation entirely** — it is one of the 24 currently-PRESENT
defect-population facts and has no B6 disposition at all (present facts are never scored for
disposition). **B3.1 is a different matter at the disposition level**: it is separately one of the
52 unmet facts, and its B6 disposition (Part 2's 52-fact table) is corrected in this reconciliation
from IGNORED to UNDECIDABLE, per the table above. This does not contradict or reopen the Part 1
UNDER-SPECIFIED finding — that finding is about the fact's *predicate*, not about which document
arrived during `step6_post`.

### What this reconciliation resolves, and what it does not

**Resolves:**
- Confirms Branch B applies: no compliant stored artifact under `scripts/` ties a `step6_post`
  session to a specific opened document for any fact — the only place that link exists is
  `state.db` itself.
- Replaces the non-compliant depth-tool-derived dispositions for all 16 affected facts (not just
  the 4 originally labeled `depth_tool`) with `UNDECIDABLE`, using only stored `step6_b7_pass.raw.json`
  records and frozen B6 source code.
- Corrects the IGNORED/UNDECIDABLE totals for both the A–E and A–D populations; CONTEXT-MISSING is
  confirmed unchanged and the predeclared "CONTEXT-MISSING dominant" verdict is confirmed unchanged
  (SUPPORTED, strict majority, both populations).

**Does not resolve / remains unknown:**
- Whether any of the 16 facts' declared source documents actually arrived via a depth-tool call
  during `step6_post` is now genuinely unknown from compliant evidence — not "resolved to no," not
  "resolved to yes." `UNDECIDABLE` is exact.
- Which of `E5.1`/`E5.3` held which of the two original dispositions (IGNORED vs. UNDECIDABLE) —
  immaterial to any total, since both correct to UNDECIDABLE, but not recoverable from stored data.
- A deeper structural question this reconciliation surfaces but does not resolve: `FACT_SOURCE_OVERRIDES`
  membership (`fact_level_override`) is a *docs-list* precedence label, not an *evidence-type*
  guarantee — a future B6 pass could make this visible in its own evidence-class reporting (e.g. by
  tagging evidence type per doc even inside the override bucket) rather than relying on a follow-up
  reconciliation to discover it. Recorded as a finding, not acted on — no scorer change was made.
- Step 5's status is **unchanged**: `IMPLEMENTATION COMPLETE / CAPABILITY BOUND UNRESOLVED`. This
  reconciliation makes Part 2's depth-tool arm evidence-compliant; it does not turn Step 5 green,
  because the underlying scorer is still known-defective (48 of 99 facts) and no repair has been
  made. Validation A was not started.

### Zero-call statement (this reconciliation)

This reconciliation session made **zero** model, Hermes, David, or provider calls, and **zero**
accesses to `state.db` or any `~/.hermes/profiles/**` path — enforced by a fail-closed
`sqlite3.connect()` guard that raised no exception during the run (confirming the guard was never
triggered because the code path was genuinely never reached). All computation was Python execution
of the already-frozen `score_pass()`/`source_arrived()` functions over the stored
`step6_b7_pass.raw.json` records with `tool_reads` forced empty, plus static inspection of already
existing files. **This supersedes only the depth-tool-arm evidence and its downstream dispositions
in the prior investigation's Part 2** (specifically the "Zero-call statement" section's mention of
a live `state.db` connection, and the per-question/evidence-class/three-way tables above it); Part 1
and all other findings in the prior investigation stand as originally recorded.
