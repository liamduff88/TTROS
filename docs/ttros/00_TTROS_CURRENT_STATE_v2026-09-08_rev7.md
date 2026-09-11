# 00 — TTROS current state

> Cold-start reference. What exists, what is proven, where things live, what is off-limits.
> **Last touched: 2026-09-08.** Supersedes `00_TTROS_CURRENT_STATE_v2026-09-04_rev6.md`, which is
> retained unchanged as the prior version.
>
> **What changed in this version:** STEP U-CLOSE. STEP U completed the Hermes upgrade outside
> rev11 under explicit authorization; the rev11 sequence itself remains unchanged. This version
> records the durable facts STEP U proved (Hermes v0.21.1 live, suite population 808/0, the B7
> guard's blocked-tool list re-derived after it was found never to have blocked `terminal`/
> `process_manage`, B6's disposition repair, the scorer's polarity/negation blindness across all 99
> facts, and `step6_post`'s full-tool-surface contamination verification), the factual state of
> native Hermes memory (decided nothing), a memory-architecture direction recorded as a design
> constraint on future work (not implemented), and the STEP U findings still open. **Nothing in
> this version reopens or reorders the rev11 design of record**, changes the harness's 25
> questions, or authorizes a new B7 pass.

---

## What TTROS is

An agentic operating system for a solo consulting business (Time to Revenue). Three parts:

* **Agentic OS** — the execution spine. A queue plus a runner that consumes queued work items,
  with a Dashboard front end. Lives in WSL.
* **David** — an advisory persona consulted through the Hermes CLI. Not an executor. He is asked
  questions ("what should I focus on today"), answers with business context assembled for him,
  and can hand work off to the queue.
* **Business Brain** — a markdown vault holding business context, rules, decisions and session
  journals. It is inside the connected Windows folder and is read directly.

**What the system is for.** Liam wants to talk to an adviser that knows his business fully and can
recommend what to do. David is that adviser; the orchestrator runs the work. **A change that reduces
tokens while leaving David unable to answer a real business question has failed, however green its
numbers.**

**The end state is wider than TTR.** David is intended to become a true personal executive
assistant, so career, income and life context are in scope, not out of it.

## Business scope — SETTLED BROAD 2026-09-03

Stated by Liam. **Breadth is the decision, not an absence of one.** Do not record it as open and
do not make any build step wait on narrowing it.

* **Core consulting ICP:** established businesses with meaningful revenue and real workflow, data
  or operational problems where AI/systems work creates material value.
* **Narrower segments are prospecting instruments, not exclusions.** The `ideal_clients.md` 60/40
  split (approved 2026-07-16) stands as a **prospecting weighting**. It does not restrict what
  work is accepted.
* **Productisation thesis:** client delivery is the discovery mechanism for painful repeatable
  problems; prove the solution, then where appropriate build a vertical product or mini-SaaS.
  **North Shore Honda is the live example.** Product opportunities can emerge from any engagement
  regardless of ICP.
* **Revisit trigger:** outbound data showing one segment converting materially better, or a
  productisation candidate reaching paying customers.
* **David must never assert that Liam has niched down.** This belongs on the map's
  not-allowed-to-claim list.

**Layer hierarchy.** ICP drives prospecting and outbound prioritisation only · current priorities
drive executive briefs and focus · career/life context contributes when relevant · client/project
context governs delivery · product opportunities cut across all of them.

**Career and life tier — availability is not execution.** Liam is actively pursuing consulting /
digital-strategy roles (MNP, Deloitte and similar) alongside TTR. Durable career context is a
short **prefix** entry. Time-sensitive career items — a dated interview, an application deadline —
surface through the ordinary commitments and priorities blocks, with no separate surface. Career
execution happens **only** on an explicit request, an active goal or task, or a deadline requiring
action. **No timer and no background search, ever.** This is the one standing exception to
"anything recurring is a systemd user unit."

## ICM — what the acronym means, and the hybrid boundary

**ICM is Interpretable Context Methodology** (Van Clief & McDermott, Eduba / Edinburgh). It is used
as a bare acronym in this file and in `02`, and was silently mis-expanded as "the context-efficiency
workstream" by a session on 2026-09-02, costing a working day. Paper and context pack:
`TTROS Reviews/chat GPTs context files on TTROS/`.

**TTROS is a deliberate hybrid and adopted only part of it.** Adopted: explicit
Inputs/Process/Outputs/Verify; small readable intermediate artifacts; **stable reference material
separated from working state**; deterministic mechanical steps; fix the source rather than the
model's wording; **every ContextBlock justifies itself per surface**.

**Explicitly NOT adopted — do not propose these:** numbered ICM folders, replacing Hermes,
replacing the queue/runner, a human gate at every stage, a second memory system, a second
orchestration framework. Context is still *retrieved* (pointer / search / Graphify), not *located*
by path, and proposing otherwise is inventing a new architecture, which the prime rule forbids.

**The Context Assembler is the enforcement point** for the hybrid ICM discipline. Context defects
are fixed there, not by restructuring the repo or the vault around them.

---

## STEP U — Hermes upgrade outside rev11 (2026-09-08)

**STEP U completed the Hermes upgrade outside rev11 under explicit authorization. The rev11
sequence itself remains unchanged.** The upgrade changed runtime reality, not the design-of-record
sequence — `TTROS_BUILD_PLAN_2026-09-04_rev11.md` is not reopened, reordered or re-reviewed by
anything in this section, and no rev 12 is proposed.

### Durable facts newly proven

* **Hermes v0.18.0 → v0.21.1, in place and live.** Confirmed directly (`hermes --version`, local
  metadata only, no model/API call): `Hermes Agent v0.21.1 (2026.9.7) · upstream b2aa855b`.
* **Suite population is now 808 passed / 0 failed.** 772, 760 and 746 are all stale — do not cite
  any of them as the current baseline. (804 pre-existing + 4 new tests added by the B7 guard's
  `NormalDavidIsUnaffectedTests`, per `scripts/b7_cleanup_pass_report.md` §6.)
* **`memory.write_approval: true`** is set on the `david` Hermes profile. Native-memory writes
  stage for review rather than applying silently — see "Native Hermes memory" below for what this
  does and does not settle.
* **The B7 guard's blocked-tool list was re-derived after being found incomplete.**
  `hooks/b7_test_material_guard.py`'s `BLOCKED_TOOL_NAMES` never blocked `terminal` or
  `process_manage` (renamed from `process` in the v0.21.1 tool registry) — both can read arbitrary
  file content (`terminal` directly; `process_manage(action="log"/"poll"/"wait")` by retrieving the
  accumulated output of a background `terminal` process). The list now includes
  `search_files`, `read_file`, `execute_code`, `session_search`, `terminal`, `process_manage`,
  gated to fire only during an active B7 run (`TTROS_BRAIN_ROOT` env-scoped, so normal David use is
  unaffected — proven by `tests/test_b7_test_material_guard.py`'s `NormalDavidIsUnaffectedTests`).
* **B6's three-way disposition mechanism was repaired and is fact-aware over 27 facts.**
  `FACT_SOURCE_OVERRIDES` in `scripts/step3_b7_harness.py` is frozen at 27 fact→source-document
  mappings (hash `19bfababbcf53048e9301bab62bfbc9188b8c25eed42c7afdfaeb0cbfc3b4d86`, scorer file
  pinned at `2d2aef167321ae7bbf0ba639db027ab92320e0a3b9cd5ce3a46b2a061b1200d4`) and **must not be
  tuned after seeing a future B7 disposition result** — any change requires a demonstrable factual
  error in the mapping itself, reported before being changed.
* **The scorer's polarity/negation blindness is confirmed across all 99 non-honesty facts.**
  `score_pass()`'s fact-presence check is pure case-insensitive substring containment with no
  negation awareness: a synthetic answer that wraps every required keyword group in explicit denial
  language ("It is NOT the case that X... the opposite is true") still scores every one of the 99
  facts PRESENT. Concretely, a real answer asserting the *opposite* of `E2.4` ("this was Liam's own
  eager idea, not reluctant, and not Mike's advice at all") would score `E2.4` PRESENT via the bare
  substring `"reluctant"`, despite explicitly denying the fact. §F's `fail_if` mechanism uses the
  identical substring-containment primitive and is **plausibly subject to an analogous blindness —
  flagged as an unmeasured risk, not confirmed either way** (not exercised by this sweep).
* **`step6_post`'s full-tool-surface verification result: CLEAN.** `scripts/step6_post_full_tool_surface_verification.md`
  (STEP U-CLOSE, 2026-09-08) enumerated step6_post's actual tool surface directly from the stored
  records — 7 distinct tools across 46 tool calls in the 25 stored sessions (`mcp__brain__open_note`,
  `mcp__brain__open_call`, `mcp__brain__search_calls`, `mcp__brain__search_history`, `search_files`,
  `execute_code`, `skill_view`) — and found **zero contamination on either the argument or the
  output side, at 100% output-retention coverage (46/46 calls)**. `terminal`/`process_manage` were
  confirmed absent from step6_post's actual calls, so the guard gap above did not cause exposure in
  this specific historical pass — a narrower and more defensible claim than "the gap didn't
  matter." This is the fifth-pass corroboration of `scripts/b7_contamination_map_and_clean_subset.md`'s
  earlier finding that `step6_post` is the one clean historical B7 pass on record; the STEP U-CLOSE
  check additionally covered tool OUTPUTS (not just arguments) and enumerated the surface from the
  records rather than from any hardcoded/suspected list — the four `mcp__brain__*` tools plus
  `skill_view` (34 of 46 calls) were never on the guard's blocked-list history and would have been
  skipped by a check that only re-verified that list.
* **The frozen v0.18 baseline survived the upgrade**, re-confirmed present after v0.21.1 went live:
  95 files intact under `/home/liam/ttros_baselines/hermes_v018_2026-08-13/assemblies` (file count
  checked directly, read-only). See "The frozen v0.18 baseline" below — it must survive any
  cleanup **and any upgrade**.

### Native Hermes memory — factual state (decided nothing)

David currently has Hermes native `MEMORY.md`/`USER.md` enabled alongside the Business Brain. This
is a parallel always-on memory surface that is **not currently covered by Business Brain
provenance/fidelity controls**. `memory.write_approval: true` contains new-write risk because
writes stage for review. **Whether native memory should remain enabled, be narrowed to
orientation-only memory, or have its staged writes routed through the wider TTROS
memory-governance path remains an open design decision** — see `02`'s open operator decisions.

### Memory-architecture direction — a design constraint on upcoming work, NOT implemented here

Recorded as a constraint the scoring/fidelity work in `02` must design around, not a change made in
this step:

**Direction: one TTROS memory experience for David with deterministic routing underneath.** Likely
role separation to evaluate:
* Native `MEMORY.md`/`USER.md` — tiny, always-on **orientation only**: stable operating preferences
  and durable interaction conventions.
* Hermes `session_search` — conversational/episodic recall.
* Business Brain — authoritative business/project/client knowledge, with provenance.

**Authority hierarchy stays:** original evidence → Business Brain canonical knowledge → Context
Assembler / retrieved context → David. Neither session history nor native memory silently overrides
source-backed Brain knowledge. Longer term the model-facing interface may simplify toward
`recall_conversation` / `recall_business` / `open_source` / `remember` with deterministic routing
underneath, rather than exposing overlapping stores and expecting David to reason about which to
trust. **Record it; do not build it.**

---

## Instruments — B1 to B8, defined here

**Definitional home. A bare identifier is not a name** — `B6` meant two different things across
two project files and nothing in `00`, and it took a live read of the design document to settle.
**When a detector is created, define it here at that moment, or use a descriptive name until it
is.**

| id | name | what it measures | model call |
|---|---|---|---|
| B1 | session recency bound | recency block ≤ 16,384 B/turn | no |
| B2 | total context bound | total assembled context ≤ 96,000 B/turn | no |
| B3 | longitudinal drift | growth over a measured window ≤ +8,000 B | no |
| B4 | thread cap | rolling thread < 2,000 of 2,500 chars | no |
| B5 | continuity | the thread feeds every turn | no |
| B6 | candidate disposition / declared-input arrival | for each declared input and candidate: did it arrive in assembled context, and if not at which stage was it dropped | no |
| B7 | business-question capability set | the fixed 25 questions, scored against fact lists, CONTEXT-MISSING vs IGNORED per missing fact | yes |
| B8 | cache-and-latency observer | raw provider usage object plus normalised cached / cache-write tokens and wall-clock latency per call | no (observes) |

**Sequencing:** B6 before any change; **B6 must exist before B7 is run**, because B7's
CONTEXT-MISSING / IGNORED split is determined by whether the fact's source document arrived.
B7 before any reduction is accepted as green.

**B7 repeatability rule for the forward build:** Step 3 defines one B7 noise allowance as the greater
of 4 percentage points or the measured two-pass spread, provided spread is ≤10 points. If spread is
>10 points, B7 is not repeatable enough to size Step 5, decide Step 7 or gate Step 9 until the instrument
is repaired. The same allowance is used everywhere; the old Step-5 3-point terminator is retired.

**B2 is not redefined.** It stays total context ≤ 96,000 B with its breach history intact. Fresh,
cached, cache-write and latency are **B8** measurements. Adding instruments beats mutating an
established bound.

**Harness naming/source correction closed 2026-09-04; Step 0 is filing-only:**
The corrected capability harness is `TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`,
titled `# B7 — the bound that can say NO`, and it no longer claims that the question set's existence
closes F-CAPABILITY-1. **What remains is to confirm that exactly one active harness source exists and
to retire any superseded B6-titled copy.** Do not change the 25 questions or scoring contract. A
corrected file sitting beside an obsolete conflicting copy recreates the same defect on the next cold
read.

**B7's own instrument is now known to have two further defects, recorded above under STEP U and not
yet repaired:** the guard's blocked-tool list (fixed, run-scoped, 2026-09-08) and the scorer's
polarity/negation blindness (found, not yet repaired — see `02`).

## Continuity acceptance — CLOSED 2026-08-13

Proofs 0–10 and Recon PASS. Proof 2b remains SPLIT on a separately recorded `/status` issue.
Patches A–D applied and proven live.

Proof 10 measured 9 real consultations over ~23.5 h against bounds declared before measuring:

| bound | threshold | observed |
|---|---|---|
| B1 session recency | ≤ 16,384 B/turn | max 10,686 B |
| B2 total context | ≤ 96,000 B/turn | max 81,717 B |
| B3 longitudinal drift | ≤ +8,000 B | +316 B |
| B4 thread cap | < 2,000 of 2,500 chars | 1,109 chars |
| B5 continuity | thread feeds every turn | 9/9 |

Integrity clean: 95/95 artifacts parsed, no byte-count disagreements, single schema and assembler
version.

> **This table is a Proof-10 historical record, not the live picture. Do not quote its B2 figure
> as current.** The live figure is below.

Decision 7 stands: David's journal is **not** excluded from relevant session recency.

Do not reopen closed proofs without contradictory evidence. Do not rebuild proof scaffolding that
already exists.

## Context size — the live picture

**B2 was breached 2026-08-17 → 2026-09-01, undetected for 15 days. Fixed and confirmed live.**

* **The breach.** Measured 2026-09-01 across the 38 surviving `hermes-*` assemblies: **26 of 38
  exceeded the 96,000 B bound**, worst **226,338 B = 2.4×**, first breach 2026-08-17T20:56:09.
  Cause was **F-BRAINNOTES-1**, not continuity: `scoped canonical Brain notes` jumped
  11,574 → 165,035 B in a two-minute window when the historical call transcripts were imported.
* **After the retriever fix, 2026-09-01T18:46:** `total_bytes` **55,963 B**, down from 209,858 —
  a 73% reduction. Note block 11,575 B. Turn attribution proven by fence.
* **After the byte budget, 2026-09-01T23:31:** `total_bytes` **45,804 B**. Note block **4,429 B**.
  Composition reconciles exactly (43,149 blocks + 2,655 request). **45,804 B is the current live
  B2 value.** The honestly attributable saving is the note block alone, **7,146 B**; the rest is
  ordinary query-dependent variation. Do not quote the headline as the budget's effect.
* **The byte budget is IN FORCE and FROZEN.** `NOTE_DOC_BUDGET` 4,096 B, `NOTE_BLOCK_BUDGET`
  12,288 B, `NOTE_DECLARATION_RESERVE` 256 B, derived against the measured 38-assembly
  distribution. **Do not reopen the budget.**

## Retrieval — measured for the first time, 2026-09-02

Read-only, against the live index and live code. Transcripts in `TTROS Reviews/`:
`ttros_t0_ranking.txt` (rev 1, INSTRUMENT SUSPECT by design), `ttros_t0_ranking_rev2.txt`,
`ttros_t0b_recall.txt`, `ttros_t0c_stopwords.txt`.

* **The loader discards essentially every search hit.** `ScopedBrainLoader.retrieve()` returned
  **0 documents on four of six frozen queries and 1 on the other two** — and that one was always
  the `direct_fallback`, which comes from a hardcoded five-keyword table, not from retrieval.
  Controlled: built with and without `search_db_path`, **A == B on all six**, so this is not an
  instrument construction defect. Cause unread; leading hypothesis is that
  `discovery_mode="explicit"` honours only explicit pointers and the fallback, with the search
  route reachable only under `relationship_dependent`.
* **All 8 expected-relevant documents ARE indexed, with full bodies** (`offers.md`: 2,289 chars of
  2,355 bytes). Zero fell in the indexer-gap category — **F-INDEX-1 does not extend to them.**
* **No match-region snippet capability exists.** `snippet(` and `highlight(` occur **zero** times
  in `tools/aos_indexer.py`. The stored `snippet` column is `body[:600]` computed at index time and
  is query-independent. Any passage-extraction design must build this, deterministically.
* **The index is fresh.** `last_scan_time` 2026-09-02T08:31:04Z. The 2026-07-09
  `last_ingestion_receipt` is a separate mechanism and is not evidence of staleness.
* **Assembler confirmed at `4240b7ab9d0fdaedc2e19b9ef5000221` / 1,528 lines** — exact match to the
  F-NOTEBUDGET-1 postimage, so **no drift since 2026-09-01T23:09**. `historical_source` occurs
  twice; `NOTE_DOC_BUDGET` four times.
* **`canonical_truth` is declared nowhere outside `sources/historical_calls/`.** Measured across all
  87 vault markdown files. Any classification rule that requires it explicitly — as it must, or
  untyped files derive to canonical and get inlined whole — leaves **~30 canonical notes needing
  backfill**, not the five untyped `operating_context/` documents alone.
* **NOT established — do not quote:** any per-document *rank depth* from the T0b or T0c transcripts.
  Those runs computed depth two different ways (bucket-concatenation order vs true rank order) and
  T0c measured across all 3,204 documents rather than the 47 Brain ones. **Membership findings from
  both are order-independent and stand; depth figures do not.**

---

## Architecture and authoritative paths

* WSL distro `AgenticOSClean`. Repo `/home/liam/agentic-os-live`.
* Backend `127.0.0.1:8010`, frontend `127.0.0.1:3010`. Services: `aos-backend`, `aos-bridge`,
  `aos-runner`, `aos-frontend`, `aos-north-shore`, plus `aos-nightly-hygiene.timer` and
  `aos-gmail-capture.timer` (user systemd). **`aos-nightly-hygiene.service` is currently failing —
  recorded by STEP U, not yet acted on.** See Open findings.
* **SYSTEMD IS THE RUNTIME AUTHORITY.** Decided by Liam 2026-08-15. Anything recurring is a user
  unit. **`tools/aos-linux-runtime.sh` no longer exists** — deleted 2026-08-15 after the census
  proved zero code-surface callers. Backup: `/home/liam/ttros_backups/capture_retire_2026-08-15/`.
* **Backend root `/` returns 404 by design.** Health is `/api/health` → 200. Probing root proves
  nothing.
* **Running the tests.** pytest is deliberately **not** installed in any venv. It lives at
  `/home/liam/ttros-testenv/pytest`. Correct invocation from the repo root:
  `PYTHONPATH=/home/liam/ttros-testenv/pytest dashboard/backend/.venv/bin/python -m pytest`.
  The runtime venv being unable to import pytest unaided is the **designed** state —
  **never pip-install pytest into it** to satisfy an instrument.
* **The full-suite baseline is 808 passed, 0 failed**, measured 2026-09-08 (STEP U zero-model
  cleanup pass, `scripts/b7_cleanup_pass_report.md` §6). **772, 760 and 746 are all stale — derive
  the population in the same run that uses it.** Never compare a `tests/` figure to a root figure —
  a prediction written against the wrong population is not a threshold.
  **The working tree is suite-green, so any failure is a real regression.**
* **"Full suite" has meant two things and the records conflated them.** `ttros_build_test_env.sh
  --full` runs `tests/` only — 487 tests. A bare `python -m pytest` from the repo root collects
  751 (pre-STEP-U figure; not re-measured against the current 808 population by this step). **The
  other 229 (of the pre-STEP-U figure) are unaccounted for and remain an OPEN QUESTION** — they
  pass today but have never been part of any declared baseline.
* **Context assemblies:** `/home/liam/agentic-os-live/queue/context_assemblies`.
  * `hermes-*.json` — written by the assembler **hook**. What the model actually received.
    **Authoritative for any context proof.**
  * `ctx-*.json` — written by `main.py`. Describes a context that was never sent (F3).
    **A proof reading `ctx-*` proves nothing.**
  * Directory is capped at **400 files and actively evicts** (F-RETENTION-1). **Eviction behaviour
    is UNVERIFIED against observation** — see F-RETENTION-2.
* **`tools/context_assembler.py` is `4240b7ab9d0fdaedc2e19b9ef5000221` / 1,528 lines**, confirmed
  live 2026-09-02T08:45Z. Patch it **anchor-gated**, not hash-gated, while F-ASSEMBLERDRIFT-1
  stands.
* **Context assembler plugin** — installed by `tools/install_hermes_context_assembler.py`. Binds to
  Hermes' `pre_llm_call` / `post_llm_call` contract. `PROFILE_ROOT` is `/home/liam/.hermes/profiles`;
  David's profile is `/home/liam/.hermes/profiles/david/` (interior never inspected — unverified).
* **Hermes v0.21.1 is the current live version, upgraded from v0.18.0 by STEP U (2026-09-08),
  outside the rev11 sequence, under explicit authorization.** The rev11 design of record (which had
  the upgrade as its own Step 9, after the shrink work in Steps 5/6/6b) is not reordered or
  rewritten by this — the upgrade simply ran early, deliberately, by Liam's approval. See "STEP U"
  above for the durable facts proved by it.
* **Provider resilience — DECIDED DIRECTION 2026-09-04, not revisited by STEP U.** The existing OpenAI/Codex OAuth path remains primary. The **continuity fallback is an official OpenAI API route with a Liam-approved hard spend cap**; reaching that cap never silently raises spend. Post-upgrade, multiple ChatGPT/OpenAI OAuth credentials may be live-proven only if the selected Hermes release and provider terms support the exact use on David's actual runner/Telegram surfaces; this is optional additional availability, not the continuity foundation, and no custom/exhaust-one-then-rotate limit-bypass machinery is built. **Any David credential pool must use cache-preserving `fill_first`/failover semantics, never round-robin/random, and B8 must record non-secret credential-slot + provider/model/cache attribution per call.** NVIDIA NIM is optional extra capacity/cross-provider diversity only; if the API cap is hit, NVIDIA may receive a workload only when explicitly enabled/proven for it and attribution is intact, otherwise TTROS stops honestly and surfaces the condition. FCC is scoped to Liam's Claude Code/Codex workbenches and sits on no TTROS execution path; `fcc-hermes` remains an optional attached-session experiment because it does not prove David's production surfaces and its routing/fallback can obscure attribution. **No API fallback configuration, second OAuth proof, NVIDIA registration, FCC install or benchmark has been performed.**
* **Business Brain vault** — `TTROS Business Brain/` inside the connected folder. 87 markdown files
  (pre-STEP-U count; not re-measured by this step).
  * `sessions/thread_david.md` — rolling continuity thread, superseded every turn. **Untracked.**
  * `rules/david_thread_contract.md` — stable reference contract, never rewritten.
  * `decisions/DECISIONS.md` — decision log.
  * `sources/historical_calls/` — 15 transcripts (665,468 B, **64.8% of all vault markdown**),
    plus `INDEX.md` (records, 3,741 B) and `MANIFEST.md` (audit + 12 candidates, 8,688 B,
    typed `historical_source` deliberately).
* **Scripts and transcripts** — `TTROS Reviews/`. Every instrument is a `.sh` (plus `.py` where
  needed) that tees its transcript to a `.txt` beside it and refuses to overwrite an existing one.
* **Backups** — `/home/liam/ttros_backups/`.

## The frozen v0.18 baseline — preserve

95 `hermes-*.json`, 95/95 verified byte-for-byte against source sha256, covering
2026-08-09 12:48 → 2026-08-13 15:30:47 local. Includes the ninth Proof-10 consultation, so the
accepted continuity window is frozen outside retention.

* WSL: `/home/liam/ttros_baselines/hermes_v018_2026-08-13/assemblies`
* Windows: `TTROS Reviews/_baseline_hermes_v018/hermes_v018_baseline_2026-08-13.tar.gz`

It is the before-picture for the context-efficiency work. **It must survive any cleanup and any
upgrade.** Re-confirmed present (95 files, file count only) after the STEP U Hermes v0.21.1 upgrade,
2026-09-08.

---

## Business Brain promotion — proven 2026-08-14

The promotion engine works end-to-end. A real write went through `PromotionWriter.apply()`
(`write_id 2df393caab5060e6219b20f3`) and the applied file matched the dry run's predicted
postimage sha **exactly**. Only one automatic class is enabled — `generated_marker_section` into
`business_brain:index/MEMORY_INDEX.md`, marker `block-2-outcome-index`. Everything else is
review-tier or refused.

* **Provenance must be registered evidence identities**, not paths. Global has four, all indexed.
  Adding one is a registry change, therefore review-tier.
* **Marker durability is proven over six weeks in production.**
* **Promotion leaves derived indexes behind** — `search: pending`, `graphify: stale`. New entries
  are retrievable by pointer immediately, **not by search until hygiene runs**.
* **AUTOMATIC PROMOTION FIRES CORRECTLY WHEN HYGIENE RUNS.** Stated narrowly: when
  `nightly_knowledge_hygiene.run()` executes, deterministic automatic promotion fires and refreshes
  search and Graphify. No human in the loop. `MEMORY_INDEX.md` moved to **exactly** the predicted
  postimage. Receipt `brain-promotion-47c93135ff182226019ae452.json`.
  * **Search-route retrieval is PROVEN**, not just pointer-route. Route proven independently first
    against a July-indexed line, so the chunk 2 check tested only the *new* line.
  * **Double-fire safety is proven behaviourally.** `idempotent` was never asserted and **cannot
    be** — it is added to the writer's returned dict, never persisted, and the hygiene wiring
    discards `promotion_result`. The flag is decorative. **Do not build a detector on it.**
  * `mark_refresh_complete()` ran in production for the first time.
* **Ignition was WIRED 2026-08-14.** Automatic promotion runs inside hygiene, not via a work item.
  Work items are the **review-tier** path.
* **The client scope registry is the render source.** `evidence_identities` is authoritative for
  membership and order; `evidence_index_entries` supplies rendered text.
  `tools/machine_outcome_index.py` renders the **full** block every run and refuses on drift — it
  never appends a delta, so a partial render would **erase** approved lines.
* **Ordering is load-bearing.** `scopes.<name>` has `additionalProperties: false`, so any registry
  field must be added to the **schema first**; data-first breaks all 15 `load_registry()` callers.
  `brain_memory._transaction_lock()` is the vault mutex and **must not be nested** inside
  `write_transaction()`. Promotion runs before `build_plan()`, taking and releasing its own lock.
* **`mark_refresh_complete()` is proven but its receipt self-heals nothing.** Hygiene's freshness
  detectors are content-derived; the receipt is not. **Never build a detector on `refresh_state`.**

## Review-tier promotion — BUILT and PROVEN 2026-08-15

Stage 2 is closed. A proposal can be filed, deduped, read back, presented, approved by Liam, and
applied through the existing `PromotionWriter`. Nothing auto-applies, and that is structural.

* **`approval_state` is a single-valued enum** (`awaiting_liam_review`) and `auto_apply` is
  `const: false`. Nothing can mark its own proposal approved. Liam's approval lives in the receipt's
  `approval_reference`. **A filed proposal still reads `awaiting_liam_review` after it has been
  applied — that is correct, not a bug.**
* **The schema only bites because a test asserts it.** Nothing in the runtime validates work items
  against `work_item.schema.json`. Do not claim a runtime guarantee.
* **Real proof: AOS-2026-0535.** Filed, deduped, read back, approved, applied.
  `business_brain:memory/agentic_os.md` 955 B → 1,778 B, **matching the postimage sha declared
  before the write.**
* **Queue filing is invisible to porcelain** — `work_items.jsonl` and `receipts/*.json` are
  gitignored. Measure by queue depth and receipt count.
* **`graphify/` is NOT gitignored**, unlike receipts and the search db. A Graphify rebuild CAN move
  repo porcelain.
* Backup: `/home/liam/ttros_backups/stage2_review_tier_2026-08-15/`. **The vault change is
  uncommitted.**

## Nightly hygiene is SCHEDULED — proven 2026-08-15, currently FAILING (STEP U, not yet acted on)

Two systemd user units, ~25 lines total. That is the whole delivered change.

* `aos-nightly-hygiene.timer` — `OnCalendar=*-*-* 03:15:00` local (America/Vancouver),
  `Persistent=true`, `RandomizedDelaySec=300`.
* `aos-nightly-hygiene.service` — `Type=oneshot`,
  `ExecStart=dashboard/backend/.venv/bin/python -m tools.nightly_knowledge_hygiene`.
  **`is-enabled` is `static` by design**: no `[Install]`, so it is timer-driven only. No `Restart=`.
  `TimeoutStartSec=900`. **STEP U recorded this service as currently failing — recorded, not
  diagnosed or fixed by this step.** See Open findings.
* **The timer firing the service was measured, not assumed** — `LastTriggerUSec` moved and exactly
  one hygiene payload appeared in a window with no start command issued.
* **Why an unattended commit is safe:** `write_transaction` stages and commits pathspec-limited.
  No `add -A`. It cannot sweep the dirty Brain entries.
* **The vault mutex is a blocking `flock` with no timeout.** If David holds it when the timer
  fires, the run waits. Not yet observed under real contention.
* **NOT proven: behaviour across a powered-off night.** `Persistent=true` is configuration, not
  evidence.
* `tools/nightly_knowledge_hygiene.py` runs as a script only because `morning_brief_detector.py`
  inserts the repo root into `sys.path` at import time. Benign but implicit; the unit uses `-m`.

## Gmail capture is SCHEDULED and the launcher is GONE — proven 2026-08-15

* `aos-gmail-capture.timer` — `OnCalendar=*:0/15`, `RandomizedDelaySec=60`. **No `Persistent=`**:
  for a 15-minute cadence a catch-up is pointless and it contaminated the first measurement.
* `aos-gmail-capture.service` — `Type=oneshot`, `static`, `TimeoutStartSec=180`. Capture runs on
  **system Python, not the venv** — the legacy wrapper's own choice, preserved. `PATH` must include
  `/home/liam/.composio`; that IS load-bearing. **`AOS_ROOT` is NOT** and is deliberately omitted.
* **Capture invokes no model, and this is measured.** The poll receipt's `token_usage_text`,
  `external_actions`, `gmail_mutations` and friends are **hardcoded constants** — narration.
  **Never gate on them.** The real detector is the canonical token ledger: 310 of 310 capture rows
  read `none` or `local-deterministic-stub` while the same reader sees 250 named-model rows
  off-lane.
* **Porcelain is VACUOUS for capture output** — `capture/runtime/`, `capture/gmail/`, `*.jsonl` and
  `queue/receipts/*.json` are gitignored. Measure by receipt, ledger, evidence-file and work-item
  deltas.
* **Timer proven by an unassisted run**, not a forced one: receipt 409 at 2026-08-15T04:03:01Z.
* Each poll costs ~90 s wall, ~78 s CPU, 405 MB peak. Recorded, not actioned.
* **Coverage honestly lost.** Five launcher process-supervision tests were deleted, not replaced.
  One WAS replaced: `test_aos_capture_live.py` now asserts the two unit files.

---

## Design rules in force

* **The production system stays small and boring.** The scheduler that took a full session to land
  is two unit files, ~25 lines. Proof scaffolding is disposable; the running system is not.
  **If a change needs a permanent new component to keep working, question the change.**
* **Recurring work is a systemd user unit.** No cron, no wrapper scripts, no launchers.
* **Proportionality is a real constraint.** Match the proof to the risk. Reuse instruments that
  already exist rather than rebuilding them.
* **Aim: David manages routine jobs, Liam does not supervise shell plumbing.** Not built yet; do
  not build it speculatively. It is the reason to keep units uniform and boring.
* **Hermes stays unforked and unpatched.** STEP U's upgrade replaces the version; it is not a
  licence to patch the source. No permanent new component if a native capability already exists.

## Protected boundaries

* `connectors/` — do not read, grep or patch. Ever.
* `workspaces/north_shore_sales_coach/` and auth stores — never opened.
* `_ttros_mirror/` is **2026-08-12** and **predates the historical_source filter entirely** —
  `grep historical_source` returns nothing in it. Useful for architecture shape, **never evidence
  of current code.**
* Every **vault write** goes through a gated relayed script. Vault *reads* are direct.
* No connector, browser, Telegram, GitHub or direct WSL access from Claude.
* Only one folder is accessible: `C:\Users\Admin\Documents\A-Time to revenue`.
* No commit, no push, no external action without explicit approval. Rollback is backup-only.

## Numbers worth knowing

Live `total_bytes` **45,804 B** against the 96,000 B2 bound (pre-STEP-U measurement; not
re-measured against the current v0.21.1 runtime by this step). Note block 4,429 B.
`deterministic morning findings` **13,166 B**, double the 6,569 on record. `matching
skills/workflows` **8,494 B**. `relevant current commitments` **794 B**. Search index: **3,204
documents, 47 of them `business_brain:`**. Vault: 87 markdown files, 1,026,818 B, of which the 15
call transcripts are 665,468 B. Queue depth 418 as of 2026-08-13, not rechecked. Cancel-guard
high-water **AOS-2026-0522**. **Suite baseline is now 808 passed / 0 failed** (STEP U, 2026-09-08;
supersedes 772/760/746 above).

---

## Open findings — do not fix opportunistically

Record new evidence against them and continue.

### STEP U findings — recorded, not acted on

* **Broken cross-profile `session_search`.** Recorded by STEP U as broken; not diagnosed or
  repaired by this step. `mcp__brain__search_history` is the Step 6 vault-scoped replacement and is
  unaffected (confirmed working, vault-scoped-only, across all traced B7 sessions).
* **`tools/queue_mcp.py` is missing** (deleted from the working tree — confirmed by `git status`
  showing it as `D`). Not restored, not diagnosed further, by this step.
* **`aos-nightly-hygiene.service` is currently failing.** Recorded by STEP U; not diagnosed or
  fixed by this step. See the Nightly hygiene section above.
* **The B7 guard's path-pattern anchoring assumption.** `hooks/b7_test_material_guard.py`'s
  defense-in-depth `TEST_MATERIAL_PATH_PATTERNS` anchors on `docs/ttros`/`scripts` appearing at the
  start of a value or immediately after `/` — a value like `"cat scripts/step3_b7_harness.py"`
  (command name + space, not `/` or start-of-string) breaks that anchor. The tool-name block
  (`BLOCKED_TOOL_NAMES`, including `terminal`) is the primary defense and does not depend on this
  pattern; the path-pattern block is described in the guard's own comments as defense-in-depth only,
  and this anchoring gap is recorded, not repaired, by this step.

### Material

* **F-STOPWORD-1 (NEW 2026-09-02) — the FTS query is a pure OR of every token, stopwords
  included.** Printed from live code: `"What" OR "are" OR "our" OR "current" OR "offers" OR "and"
  OR "how" OR "are" OR "they" OR "priced"`. Nearly every document contains "and", so nearly
  everything matches and bm25 ranks on **stopword profile**. Verbatim transcripts are saturated
  with function words; canonical notes written in headings and bullets are not. Direct evidence:
  the single term `offers` returns 63 hits with `memory/offers.md` reachable, while the full
  sentence pushes it far down. **The stopword list already exists** —
  `context_assembler._query_terms()` carries `what/which/who/are/should/have/about` — and is used
  only for entity-pointer matching, never for the search query. Applying it moves an existing
  filter one stage earlier; it is not new machinery.
* **F-INDEXSCOPE-1 (NEW 2026-09-02) — Brain notes compete against the OS's own source.** The index
  holds 3,204 documents, **47** of them `business_brain:`. On several frozen queries the entire
  post-filter top-5 was `agentic_os_live:` paths — SKILL files, proofs, workflow artifacts. The
  note block only ever wants Brain documents; retrieval is not scoped to them.
* **F-FILTERSTARVE-1 (NEW 2026-09-02, UNRESOLVED — architectural) — the F-BRAINNOTES-1 filter can
  starve the note block to nothing, silently.** It excludes on `type == historical_source`
  (`tools/context_assembler.py` ~line 480). Measured 2026-09-02T07:31Z: "Which historical calls do
  we have on file, and who was in each one?" → block 2,441 B, **one** note (`memory/offers.md`,
  `direct_fallback`), zero of fifteen record slugs, David answering *"no verified historical
  client/prospect calls with participant lists are visible here."*
  * **The indexer is healthy and is NOT the cause.** 3,204 documents indexed, corpus reachable.
  * **This is the F-REFRESH-1 / capture-narration defect class again:** the system asserts a state
    it does not have. A block that silently drops its candidate set is indistinguishable, from the
    model's side, from a business with no history.
  * **CAUSATION IN DOUBT, 2026-09-02T08:45Z. Do not cite the mechanism above as settled.** With
    **no type filter anywhere in the path**, the loader returned 0 documents on four of six frozen
    queries and 1 on the other two — always the `direct_fallback`. Controlled, A == B. The
    `route=direct_fallback`-with-one-document signature therefore reproduces **without** the
    filter, and the filter may be removing documents from an already-empty set.
  * **One thing does not reconcile and blocks closure either way:** the replay produced
    `direct_fallback: None`, yet the 07:31Z turn returned `memory/offers.md` *via* direct_fallback.
    Either the live `_scoped_note_block` carries a fallback path the mirror lacks, or the message
    differed. **Settle by reading the live function.**
  * **Do not fix by weakening the filter.** Inlining 660 KB of transcripts is what it exists to
    stop. The candidate fix is a **projection**, not an exclusion, and it must declare itself
    in-band the way F-NOTEBUDGET-1 already does.
* **F-CAPABILITY-1 — nothing measures whether David's context is sufficient, only whether it is
  small enough.** B1–B5 are all size or continuity bounds. There is no bound that can return NO to
  "can David answer what the business needs". Concretely: 15 transcripts, 665,468 B of what real
  prospects said, reach David as **filenames only**. Composition 2026-09-01 23:31: TTROS's own
  bookkeeping ≈43% of context; business substance ≈16%. **This is size evidence, not content
  evidence.** Build the bound before the next context cut. **B7 is the harness answering this; its
  own instrument defects (guard gap, scorer polarity blindness) are tracked under STEP U above and
  in `02`'s active task, not here.**
  * **KNOWN CAPABILITY REGRESSION, TAKEN KNOWINGLY, 2026-09-02.** The F-INDEXSHAPE-1 split moved
    the 12 knowledge candidates — the only existing distillation of the corpus — out of assembled
    context and into the manifest. **From 2026-09-02 David reaches the historical calls as a
    records table and filenames only.** Liam approved this on the explicit condition that it is
    recorded as a dated regression, **not a clean close**, and closed by promoting the candidates
    into canonical memory (F-CANDIDATES-1), not by reverting the split.
  * **The parked material was checked against the transcripts. Eight of twelve bullets hold as
    written; four must be corrected before promotion.**
    * **#5 niching** — filed as `liam_intention`, but on Jul 21 it is **Mike's advice**, and Liam's
      own words are that he has been "reluctant to niche down". Promoting it would put an intention
      in canonical memory the source shows him resisting.
      **CORRECTION AUTHORISED 2026-09-03.** Retype to advice received — Mike Knapp advised niching
      down; Liam recorded as reluctant; scope kept deliberately broad. A factual filing fix, not a
      business decision, and it stands independently of the settled-broad scope above.
    * **#6 unpaid work** — flattens a real tension. Jun 30 has Liam refusing to give work away;
      Jun 18 has him proposing "the hook of something free" for zero-exposure prospects. A
      segment-specific offer, not a principle.
    * **#7 CCI ICP** — "food and beverage chemicals and pharma" is verbatim and corroborated.
      **"UK targeting" is an under-read** — the same call says "focus on America, UK and Europe".
    * **#8 Kenneth on quantifying time savings** — the personalisation half is in his own words;
      the time-savings half is not corroborated. Not disproven, not promotable on current evidence.
    * Two bullets **understate** their sources: Andrea made specific named introductions and named
      a recurring Vancouver consultant event; Trent offers to *get* Lance's information, which is
      the clearest proof Lance was never in the room.
* **F-COMMIT-1 — nothing commits a promotion.** Every promoted fact, automatic and review-tier
  alike, lives only in the working tree. Brain HEAD is still `86bc119` (2026-08-13).
  * `PromotionWriter.apply()` replaces vault bytes atomically and does not commit. Hygiene's
    `write_transaction` commits only `plan.documents`, and the vault is not a watch root.
  * **`write_transaction` cannot be used to commit an existing promotion.** It is a WRITE tool: it
    calls `apply_provenance()`, inserting a `hermes_last_write` block. **Committing through it would
    commit bytes Liam never approved.** Recommended in-session and withdrawn before it ran.
  * **Do not describe a promotion as committed.**
* **F-INDEX-1 — four registered Business Brain documents are absent from the search index.**
  Missing: `memory/agentic_os.md`, `memory/company.md`, `operating_context/old_vault_archive_plan.md`,
  `operating_context/protected_paths.md`. Predates Stage 2.
  * **The obvious explanation is wrong.** `business_brain_read_index_only: true` does **not** mean
    only `MEMORY_INDEX.md` is ingested — 33+ documents including most of `memory/` are indexed.
    Measured false; do not repeat the inference.
  * **Frontmatter is not the discriminator either.** Cause remains **unknown**.
  * **Does not extend to the operating notes** — all 8 tested 2026-09-02 are present with full
    bodies.
  * **The Brain document count has now moved three times and nobody has explained it:** 33 of 37
    (2026-08-15), 52 (2026-09-02 morning), **47** (2026-09-02 08:48Z), against 87 vault markdown
    files.

### Other open findings

* **F-RETENTION-2 (UNRESOLVED)** — the assembly directory held **9** `hermes-*.json` at 18:44
  against the **38** recorded as surviving the 400-file cap. Timers do not explain it. Either
  eviction is far more aggressive than F-RETENTION-1 records, or the 38 was measured against a
  different glob. **Blocks B3** and puts a retention horizon under every past B2 proof.
* **F-ASSEMBLERDRIFT-1** — `context_assembler.py` drifted +166 lines unrecorded against the
  2026-08-16 gated figure. Patches must be **anchor-gated**, not hash-gated, until explained.
  (No further drift since 2026-09-01T23:09, confirmed 2026-09-02.)
* **F-THREADSCOPE-1 / F-THREADWIPE-1** — `rules/david_thread_contract.md` says *"at the very end of
  every reply"*, so the user-facing continuity warning is **specified behaviour, not leakage**.
  Worse than the warning: a trivial turn that *complies* **overwrites parked work** — the live
  thread was reduced to "Auth/check-in only" by an availability check. Fix is a **change-triggered**
  contract, which repairs both at once.
* **F-CODEXBUNDLE-1** — the uncommitted David-latency repair is 386 insertions / 50 deletions
  carrying ≥4 separable changes, including a routing-semantics swap and a safety-guard narrowing.
  **It cannot be accepted or rejected as a unit.** Split it.
* **F-REFRESH-1** — `mark_refresh_complete()` closed a receipt to `search: current` for a document
  not in the search index at all. First observed case of `refresh_state` being affirmatively false
  rather than merely stale. Receipt left as written, pending Liam's decision.
* **F-DUPMODULE-1** — `tools/` is on `sys.path`, so modules are importable under two names and
  Python builds **two distinct class objects** for each exception. `except PromotionError` written
  against the wrong namespace silently fails to catch. **The pattern is repo-wide.** Not fixed.
* **There is no `conftest.py` anywhere in the repo.** `tools/` reaches `sys.path` purely as a side
  effect of importing `dashboard/backend/business_brain_graph.py`. A test file that does not import
  it cannot use `tests/business_brain_test_support.py`.
* **F-RETENTION-1 (contained)** — the 400-file cap still destroys history silently. Acute pressure
  is off now the baseline is frozen.
* **F-STAGED-1** — one consultation produced no journal turn and no Brain commit. **Brain-side
  records are not a reliable "did a consultation happen" detector — the assemblies are.**
* **F-ASSEMBLY-1** — no `profile` field persisted in the assembly manifest, so population selection
  is still a text heuristic. Persisting it would make every future regression an exact match.
* **`_buildout_package/` is GITIGNORED and untracked** yet contributes **35 tests**.
  **Porcelain cannot speak for anything under it** — an untracked-and-ignored path emits no
  porcelain entry whether it changed or not. Use file mtime against a known event window, and
  negatively control it.
* **Three untracked Layer-3 files, no version history:** `sessions/thread_david.md`,
  `rules/david_thread_contract.md`, `rules/david_execution_handoff.md`.
* F3 evidence surface shows a context never sent · AskDavid `queue_created` caption renders
  `route.matched` and ignores `route.confidence` · delegation trust gap (Proof 6 F/G), F-STATUS-1,
  F-STATUS-2 · **AOS-2026-0522 blocked, cause unresolved** · `_session_recency_block` duplicate-source
  emission · `stop_conditions` comma-mangling · recovery receipt hardcodes `Attempts used: 0` ·
  8 of 22 `workflow.md` files lack a parseable Done line · journal frontmatter hardcodes
  `Last touched: 2026-08-04` · Telegram operator-lean sticky key / profile identity unification ·
  live `AOS_HERMES_TIMEOUT_SECONDS` unknown · Hermes `session_search` / FTS5 (parked until the
  planned post-shrink Hermes upgrade — **the upgrade has now happened via STEP U; `session_search`
  is separately recorded above as currently broken cross-profile**).

---

## Closed — do not reopen, do not re-derive

* **F-RECENCY-1 — CLOSED GREEN 2026-08-16.** Recency had been pinned to the 2026-08-12 journal at
  exactly 9,789 B because `_session_recency_block` had **no time term at all** — it ranked turns
  purely by query-term overlap, and two 08-12 turns had transcribed the operator preamble verbatim,
  matching ~95% of every request. Fixed by recency-first selection with a 10% relevance floor.
  First live turn: **3,613 B**.
* **ICM-1 provenance compaction — CLOSED GREEN.** 8,786 → 4,606 B (−47.6%), sources 58 → 58, David
  still named exact sources and routes when asked. **Do not reopen provenance.**
* **F-BRAINNOTES-1 retriever fix — APPLIED GREEN 2026-09-01T17:52**, 12 gates, 0 missed. Block
  165,035 → 11,575 B, `historical_source` docs 4 → 0, suite 772/0 (stale figure; see current
  808/0 baseline above). **CONFIRMED LIVE 18:46.**
  Backup: `/home/liam/ttros_backups/brainnotes_2026-09-01/`.
* **F-NOTEBUDGET-1 byte budget — CLOSED GREEN, CONFIRMED LIVE 2026-09-01T23:31.** 14 gates on
  apply, 7 on confirmation, attribution proven on exactly one fenced assembly. `render()` no longer
  emits the unconditional literal *"No selected block was truncated"* — narration in the same class
  as capture's hardcoded receipt constants, and affirmatively false the moment a budget existed. It
  now states the budgets and declares every cut in-band, naming path and sha256, so nothing becomes
  unreachable. Backup: `/home/liam/ttros_backups/notebudget_2026-09-01/`.
* **F-INDEXSHAPE-1 vault split — APPLIED GREEN 2026-09-02T07:21Z**, 16 gates, 0 missed.
  `INDEX.md` records-only **3,741 B**; `MANIFEST.md` new, **8,688 B**, typed `historical_source`
  deliberately so the existing filter excludes it rather than a new mechanism doing so. 15 record
  rows, 16 inventory rows, 16 SHA-256 literals, 12 candidate bullets conserved. No commit.
  * **Expect no material byte saving and do not claim one.** 4,096 B truncated → 3,741 B whole.
    The change is which bytes survive, not how many.
  * **LIVE CONFIRMATION IS VOID, NOT FAILED.** The confirming message asked directly about
    historical calls, which favours the excluded tier, and the `MANIFEST-excluded : 0 == 0` gate
    passed **vacuously** — the manifest was absent because the whole folder was absent. A gate that
    cannot distinguish "correctly excluded" from "everything excluded" is not a control.
    **One neutral-message re-fence (`hi david`) settles whether the split cost anything.**
* **F-TELEGRAM-1 — CLOSED 2026-08-15.** Repaired test-side with one added keyword;
  `connectors/` was never read. The gate required the test to FAIL first before repairing it.
  * **A named keyword was used, not `**kwargs`.** Both fix the failure; `**kwargs` would also
    swallow every future signature drift, which is how this stayed invisible for six days.
  * **Limitation, recorded not hidden:** the stub accepts `reply_tag` and asserts **nothing about
    its value**. The contract is restored; its meaning is not tested.
* **F-BUILDOUT-1 — found and REPAIRED 2026-08-14.** `make_real_root()` copied a **hardcoded** list
  of tools modules into a synthetic root. Broken for six days, invisible because the only harness
  anyone ran was `tests/`. Repaired by **deriving** the copy set from the CLI's `ast` import
  closure, old list retained as a seed so the set can only grow. The fixture's own comment records
  that it had already fallen out of contract once and was "fixed" by extending the list —
  **extending a hardcoded list is what guarantees the next occurrence.**
* **Backend restart + live B1/B2 confirmation — CLOSED GREEN 2026-09-01T18:46.**
* **Ownership audit v2, footprint pass, authority trace — 2026-08-14.** All passed their negative
  controls. Of 180 spine source files: 152 live, 25 documentary-only, 2 unproven, 1 dead.
  A documentary mention is history, not ownership.
* **The B7 guard's `terminal`/`process_manage` gap — CLOSED 2026-09-08 (STEP U).** Re-derived
  `BLOCKED_TOOL_NAMES` to include both, run-scoped to an active B7 run via `TTROS_BRAIN_ROOT`,
  proven not to affect normal David use. See STEP U above.
* **`step6_post`'s cleanliness — CONFIRMED on its full enumerated tool surface, both input and
  output sides, 2026-09-08 (STEP U-CLOSE).** See STEP U above and
  `scripts/step6_post_full_tool_surface_verification.md`. Does not itself authorize a new B7 pass
  or re-open the scoring question — see `02`.
