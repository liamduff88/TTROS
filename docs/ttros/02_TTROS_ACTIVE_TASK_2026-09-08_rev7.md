# 02 — TTROS active task and forward sequence

> The only file that changes often. Update it when the active task changes.
> Last touched: 2026-09-08, STEP U-CLOSE: STEP U completed the Hermes upgrade outside rev11 under
> explicit authorization; the rev11 sequence itself remains unchanged. `step6_post` is confirmed
> clean on its full enumerated tool surface, both input and output sides (see `00` rev7). The
> active task changes from "Step 0 filing corrections" (stale — later steps executed since) to a
> bounded scoring/fidelity integrity thread: repair the B7 scoring instrument's known defects
> before any future B7 pass is trusted as capability evidence. **No B7 or model-call spend is
> authorized by this update.**

## How to start from this file

**Act on the next action below. Do not open the session by restating what you just read.** If
something here is ambiguous, ask one specific question; otherwise begin.

**Authoritative file versions.** Project knowledge holds the current `00` (rev7), `01`, and `02`
(this file, rev7). In the folder, ignore these superseded copies: `00_TTROS_CURRENT_STATE.md`
(2026-08-14), `00_tmp.md`, `00_TTROS_CURRENT_STATE_v2026-09-01.md`,
`00_TTROS_CURRENT_STATE_v2026-09-02.md`, `00_TTROS_CURRENT_STATE_v2026-09-04_rev6.md`,
`01_TTROS_WORKING_METHOD.md` (write-locked, superseded by the `_v2026-09-02` file), and
`02_TTROS_ACTIVE_TASK_2026-09-04_rev6.md`.

**Do not read the ChatGPT context pack** under `chat GPTs context files on TTROS/`. Absorbed
into `00` on 2026-09-02; re-reading it was that session's largest avoidable cost.

**The design of record is `TTROS_BUILD_PLAN_2026-09-04_rev11.md`.** It carries the rationale,
bounds, delete list and open decisions. **STEP U (2026-09-08) performed rev11's own Step 9 (the
Hermes upgrade) out of its declared order, under Liam's explicit authorization — the rev11
document itself is not reopened, reordered or re-reviewed, and no rev 12 is proposed.** This file
carries status, the next action and the sequence only.

## EXACT NEXT ACTION — scoring/fidelity integrity work (post-STEP-U, 2026-09-08)

**Why this is the active task, ahead of resuming the rev11 forward sequence below:** STEP U-CLOSE
confirmed `step6_post` is the one clean historical B7 pass on record (see `00` rev7's STEP U
section), but the same work surfaced that the B7 *instrument itself* has known, unrepaired
defects — the scorer's polarity/negation blindness across all 99 non-honesty facts, and several
judgment-heavy scoring-rule questions never decided. Trusting a future B7 pass as capability
evidence before these are addressed would repeat the exact defect class this whole audit chain
exists to catch (a detector that can only print PASS). **This work is writing/design and one
bounded repair only — no B7 pass, no model call, until items 1–5 are complete and a separate
execution authorization is given.**

1. **Write the scoring + fidelity contract — writing only, no code.** Derived from the frozen
   harness fact descriptions (`TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`), not
   re-authored. Vocabulary: normalization, list coverage, essential qualifiers, attribution,
   polarity/assertion, temporal/status, prohibited opposites. Applied only to the ~40 facts the
   audit named (`scripts/b7_contamination_map_and_clean_subset.md` §13, `scripts/step5_step6_static_forensic_audit.md`),
   not as a schema over all 99.
2. **Fidelity detector on the known 12-item historical-call set**, labels withheld from the
   building session, one fresh evaluation afterwards.
3. **Judgment-heavy scorer rules** — Liam records his predicted effect before deciding each (see
   open operator decisions below for the specific rules pending).
4. **One bounded scorer repair.**
5. **Re-score `step6_post`** (the pass already confirmed clean of test-material contamination —
   this is a scoring-fidelity re-score, not a re-run of the pass itself).
6. **One clean B7 baseline, new condition regime — not compared to step3/step5/step6.** Records
   future sequencing only; not authorized by this update.
7. **Only then, memory architecture**, including whether David keeps native memory enabled (see
   `00` rev7's "Native Hermes memory" and "Memory-architecture direction" sections).

**No B7 or model-call spend is authorized by this update.** Item 6 records future sequencing only.
**A fresh B7 run requires separate execution authorization after items 1–5 are complete.**

### Open operator decisions — unresolved, carried forward

* **Whether Step 5's closure stands**, having been declared against a ≥80% bound while the only
  clean pass measures 44–49% on §A–D with the "any question at 0% → investigate" clause never
  firing.
* **The native-memory question** — whether native Hermes memory should remain enabled, be narrowed
  to orientation-only, or have its staged writes routed through the wider TTROS memory-governance
  path (`00` rev7, "Native Hermes memory — factual state").
* **The judgment-heavy scoring rules**, each with contamination counts and one-directional effect
  already surfaced in `scripts/b7_cleanup_pass_report.md` §5 and
  `scripts/b7_contamination_map_and_clean_subset.md` §13:
  1. List-collapse / enumerated-answer coverage threshold (10 questions, 15 facts named directly).
  2. `E5.4` — redefine, retire, or reconsider the `historical_source`/`MANIFEST.md` reachability
     rule (1 fact; retiring would raise the score by shrinking the denominator).
  3. Near-universal-keyword tightening (`"not"`, `"un"`, `"after"` — 7 facts, all on
     uncontaminated ground; can only lower scores).
  4. `E3.1`/`E3.2`'s `step5_k1` PASS-via-leakage validity (2 facts; can only lower `step5_k1`'s
     recorded score if disqualified).
  5. Step 3/Step 5 harness-doc contamination — are those passes' touched sections citable as
     baselines at all (lowers evidentiary weight; does not change any stored number).
  6. `B1.5` over-specification — 4-of-4 verbatim vs. a looser bar (1 fact, clean ground; can only
     raise scores if loosened).

**Proof — both clauses must pass when items 1–5 above are executed:** the scoring contract exists
in writing before any code changes; the one bounded scorer repair is applied only after a
demonstrable factual or mechanical error is shown (never motivated by which way a B7 pass's
numbers moved), consistent with `00` rev7's "FACT_SOURCE_OVERRIDES...frozen" rule.

**Rollback:** the canonical files are new files; rollback is deletion of rev7 and restoration of
rev6 as active (see `00` rev7 for the parallel note). Any future scorer repair must itself declare
its exact change and exact rollback in its own step transcript before executing, per the header
rules.

## PLATFORM QUESTION — CLOSED 2026-09-03

**TTROS is infrastructure for the consulting business, not a product.** Hermes stays, unforked
and unpatched. Vault, queue, runner, dashboard and assembler stay. Composio connects over MCP.
No rebuild, no second orchestrator, no memory service. **STEP U's upgrade replaces the Hermes
version; it does not license patching the source — see `00` rev7's design rules.**

Deciding facts: ChatGPT-plan OAuth is unofficial and revocable — Anthropic removed the
equivalent April 2026, Google February 2026, bans issued without appeal — so it cannot carry a
product; and TTR sells forward-deployed builds, not software. Demo-grade costs nothing extra and
is the case study. **Revisit only when a paying client asks to buy the system rather than a
build.**

**LOCAL-CONFIRMED 2026-09-03:** `context_file_max_chars` exists in v0.18.0 —
`agent/prompt_builder.py`, `agent/system_prompt.py`, `hermes_cli/config.py`. **Re-verify on
v0.21.1 before relying on it** — STEP U did not check this key on the upgraded version. The context
tier work is unblocked on the current version in principle. **The Hermes upgrade does not block
Steps 0–8 and TTROS does not depend on NVIDIA or FCC.**

## SEQUENCING — SHRINK FIRST, UPGRADE SECOND, PROVIDER RESILIENCE AFTER (2026-09-04, rev 11)

**Shrink the custom Hermes-bound layer first, then upgrade Hermes.** This was the rev11 design's
own sequencing. **STEP U performed the upgrade (rev11's Step 9) ahead of the shrink work (Steps
5/6/6b) under Liam's explicit 2026-09-08 authorization — a deliberate, approved reordering of
execution, not a rewrite of the rev11 design itself.** Steps 5 (stable-prefix map), 6 (corpus/vault
behind tools — evidenced as executed; see `scripts/step6_*`) and 6b (delete obsolete retrieval
machinery — status not confirmed by this step) were intended to reduce the Hermes-bound surface
before the upgrade; the upgrade ran first instead, by approval. Step 7 remains conditional and may
never be built. Steps 2, 3 and 4 are the instruments that decide whether the reductions are safe.

**The FCC-as-prerequisite claim is WITHDRAWN.** Rev 6 justified the upgrade's new importance by an
FCC/Hermes minimum-version dependency that was never confirmed — the same defect class as assuming
`post_api_request` exists from an upstream document. **Step 9 keeps its place on its own merits:** the
shrink work makes the re-attach small, the supported context-engine seam is a better home for the
assembler than a broad lifecycle-hook dependency, and native usage telemetry may make part of B8 a
reader rather than an instrument. At implementation time, live-check the installed version and the
latest supported upstream release; do not trust planning-time version numbers as runtime truth.

## PROVIDER RESILIENCE — DECIDED DIRECTION 2026-09-04

**Separate continuity, capacity and workbench convenience. TTROS must not depend on NVIDIA or FCC.**
Not revisited by STEP U.

1. **Primary:** existing OpenAI/Codex OAuth route.
2. **Continuity:** official OpenAI API fallback with a Liam-approved hard spend cap (D6). Reaching the
   cap never silently increases spend. If an optional NVIDIA route is explicitly enabled and proven for
   that workload, it may take over with full attribution; otherwise stop honestly and surface the
   condition to Liam/Needs Me.
3. **Optional additional OAuth:** after Step 9, live-prove whether supported Hermes can hold/use two
   ChatGPT/OpenAI OAuth credentials on David's real runner/Telegram surfaces. Use only if the exact use
   is supported by upstream Hermes **and provider terms**. Never build exhaust-one-then-rotate logic to
   evade usage limits. It is not the continuity foundation.
4. **Optional capacity/diversity:** NVIDIA NIM through native Hermes, gated by B7 + five worker tests.
5. **Workbench only:** FCC for Liam's Claude Code/Codex sessions; not on a TTROS execution path.

**Credential-pool cache rule:** if a multi-credential pool is ever enabled for David, use
`fill_first` / failover semantics (or a live-proven cache-safe equivalent). Never use round-robin or
random on David's stable-prefix path. Provider-side caches are credential/account scoped, so a slot
change can invalidate the cached prefix. **B8 must record provider, model, raw cache usage and a stable
opaque credential-slot identifier per pooled call.** If the serving slot cannot be attributed without
exposing secrets, the pool does not carry production work. This is why Step 9a stays after B8 and Step 5.

**Hard attribution bound:** every production model call records the provider/model that actually served
it; pooled/fallback paths also record the non-secret credential slot and attempted hops where safely
available. If attribution cannot be recorded, production TTROS work does not route through that path.

`fcc-hermes` remains optional/non-production because it proves an attached session rather than David's
runner/Telegram surfaces, a Hermes `/model` change leaves the FCC route, and FCC fallback can obscure
attribution. Nothing in TTROS may depend on it.

## D-NAMING — CLOSED 2026-09-03

Settled from `TTROS_CONTEXT_ARCHITECTURE_DESIGN_2026-09-02.md` §8, read live, unsuperseded:

* **B6 = candidate disposition / declared-input arrival.** Assembler-side. No model call.
  **Repaired and fact-aware over 27 facts as of STEP U (2026-09-08) — see `00` rev7.**
* **B7 = the fixed business-question capability set** (the 25-question harness). **Its guard's
  blocked-tool list was re-derived and its scorer's polarity blindness was found by STEP U — see
  `00` rev7 and the scoring/fidelity work above.**
* **B8 = the cache-and-latency observer.** New.

§8 sequencing preserved: **B6 before any change; B7 before any reduction is accepted as green.**

**B6 and B7 are different instruments, not one run seen twice.** B7's CONTEXT-MISSING / IGNORED
split **depends on B6** — CONTEXT-MISSING is determined by checking whether the fact's source
document arrived. **So B6 must exist before B7 is run**, not merely before changes are made.

**Harness source correction closed 2026-09-04; step 0 is filing-only:**
The corrected source is `TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`, titled
`# B7 — the bound that can say NO`, and it does not claim that the question set itself closes
F-CAPABILITY-1. **Step 0 now only confirms that exactly one active harness source exists and retires
any superseded B6-titled copy.** Do not change the 25 questions or scoring contract.

**B2 is NOT redefined.** It stays as total context ≤96,000 B with its breach history intact.
Fresh, cached, cache-write and latency are **B8** measurements. Adding instruments beats
mutating an established bound.

## MARKET SCOPE — SETTLED BROAD 2026-09-03

**Stated by Liam. Breadth is the decision, not an absence of one.** Do not treat it as open, and
do not ask him to narrow it to unblock a build step.

* **Core consulting ICP:** established businesses with meaningful revenue and real workflow, data
  or operational problems where AI/systems work creates material value.
* **Segment campaigns are prospecting instruments, not exclusions.** Narrower campaigns make
  outbound more effective. They do not restrict what work is accepted. The `ideal_clients.md`
  60/40 split (approved 2026-07-16) stands as a **prospecting weighting**, read that way.
* **Productisation thesis:** client delivery is the discovery mechanism. Find painful repeatable
  problems, prove the solution, and where appropriate turn it into a vertical product or
  mini-SaaS. **North Shore Honda is the live example** — if the sales-manager problem proves
  repeatable it may be productised for other dealerships and groups.
* **Product opportunities can emerge from any engagement regardless of ICP.**
* **Revisit trigger** (so breadth does not quietly become permanent): outbound data showing one
  segment converting materially better, or a productisation candidate reaching paying customers.

**Context hierarchy — what each layer is for.** ICP drives prospecting and outbound prioritisation
only. Current priorities drive executive briefs and focus. Career/life context contributes when
relevant. Client/project context governs delivery. Product opportunities cut across all of them.

**David must never assert that Liam has niched down.** Goes on the map's not-allowed-to-claim
list at step 5 (map in stable prefix).

## CAREER AND LIFE TIER — RULE SET 2026-09-03

TTROS is not only the TTR business OS. The end state is David as a true personal executive
assistant, so **career, income and job search are in scope** — Liam is actively pursuing
consulting / digital-strategy roles with firms such as MNP and Deloitte alongside TTR.

**Availability is not execution. The split is load-bearing:**

* **Available always** — durable career context is a short prefix entry: that a role search is
  active, at what level, and that it sits alongside TTR rather than replacing it. Cached, near
  zero marginal cost.
* **Surfaced when time-sensitive** — a dated interview, an application deadline or a follow-up
  commitment appears in the ordinary commitments/priorities suffix blocks, exactly like a client
  commitment. No separate career surface, no new block.
* **Executed only on demand** — an explicit request ("find me jobs"), an active goal/task, or a
  deadline that requires action. **Never a timer, never a background search.** Career search is
  explicitly *not* recurring work; it is the one standing exception to "anything recurring is a
  systemd user unit."

**B7 gains two honesty checks** when the personal section is written in step 10 (life and career tier): David must surface
a dated interview when asked what to focus on, and must **not** propose or launch continuous job
search unprompted. Both can return either answer.

## Forward sequence (rev11 design of record — unchanged; resumes after the scoring/fidelity work above)

**This is rev11's own sequence, carried forward unmodified.** STEP U executed Step 9 (the Hermes
upgrade) out of order, under explicit authorization (see above); Steps 0, 2, 3, 5 and 6 have
evidence of execution in `scripts/` (`step3_b7_*`, `step5_b7_*`, `step6_b7_*`); this step does not
audit or re-certify the status of Steps 1, 4, 6b, 7, 8, 9a–9d, and none of that status is asserted
here beyond what `00` rev7 already records. Do not re-derive step completion from this list alone.

0. **Step 0 — filing corrections (four vault edits + harness filing check).**
1. **Step 1 — remote access, tested before built.** Cloudflare Tunnel + Zero Trust Access in front
   of the existing dashboard; confirm the Telegram gateway reaches David. Settles R7, which drove
   the rebuild question and has never been tested. Nothing in TTROS changes.
2. **Step 2 — B6 candidate disposition / declared-input arrival.** Assembler-side, no model calls.
   For every declared input and candidate, record whether it arrived and, if not, at which stage it
   was dropped. Must be able to report **both** arrival and non-arrival. Re-run after every later
   step.
3. **Step 3 — B7 baseline.** Score the CONTEXT-MISSING / IGNORED split via B6 and **state the
   surface**. Same pass: inter-request gap distribution against cache TTL. **Measure repeatability
   before any later upgrade bound depends on it:** run two independent full B7 passes on the same
   premium model, same surface, same frozen questions/fact lists/scorer, each with fresh sessions.
   Record both totals, the absolute total-score spread and per-question deltas. **Predeclare the
   acceptance rule now:** the Step 9 baseline anchor is the **lower of the two total scores**, and the
   per-question anchor is the **lower score for that question across the two passes**. If the two-pass
   total spread is **greater than 10 percentage points**, B7 is not repeatable enough to **size Step 5,
   decide Step 7, or gate Step 9**: stop, record an instrument finding and investigate B7; do **not**
   convert high noise into a wider licence. If spread is ≤10 points, define one **B7 noise allowance**
   equal to the
   greater of the measured spread or **4 percentage points**. These values are fixed before baseline
   execution and may not be loosened after results are seen. **Sizes step 5 (map in stable prefix) and
   decides whether step 7 (Context Navigator, conditional) is built.**
4. **Step 4 — B8 cache-and-latency observer.** Use a plugin lifecycle hook actually present on
   v0.18.0; `post_api_request` must be confirmed before use. Log the raw provider usage object plus
   normalised cached-token fields and wall-clock latency. **Also run, in the same step, the D-STALENESS
   sentinel check and the protected instruction/context-file check** — a forced approval on the
   `.hermes.md` write settles D-STALENESS on its own, so it cannot be left until step 5.
5. **Step 5 — map in stable prefix; old ranker disabled behind a flag, not deleted.** Generate one
   map class at a time and stop growth when the incremental B7 gain fails to exceed the Step 3 **B7
   noise allowance**, or B2 headroom falls below 10,000 B. If Step 3 spread exceeded 10 points, B7
   cannot size the map until the instrument is repaired. A noisier-but-usable B7 therefore predicts a
   smaller map; this is deliberate, not a threshold to relax mid-run.
   `.hermes.md` from `canonical.manifest`; pin `context_file_max_chars`; archive each generated map
   immutably with timestamp, source manifest and SHA-256, refusing to overwrite. Working state
   remains in the suffix. **Rollback is flipping the flag.**
6. **Step 6 — corpus and vault behind tools.** Extend the existing `brain` MCP server with
   `search_calls`, `open_call`, `open_note`, `search_history`; record direct-answer versus tool
   round-trip ratio and latency.
6b. **Step 6b — delete obsolete retrieval machinery.** Only after Step 5 (map in stable prefix) and
    Step 6 (corpus/vault tools) are both green. Remove ranking path, `direct_fallback` keyword table,
    post-truncation class filter, reserved-slot and passage-extraction designs; re-run B6 and B7.
    **Carry `session_search`/FTS5 and any B8/native-telemetry overlap as post-Step-9 deletion candidates
    only; do not delete them before the upgrade proves their replacements.**
7. **Step 7 — Context Navigator, CONDITIONAL.** Build only if B6/B7 show IGNORED dominating **by more
   than the Step 3 B7 noise allowance**. If Step 3 spread exceeded 10 points, B7 cannot decide Step 7
   until the instrument is repaired.
   Inside the existing assembler, deterministic-first, **suffix only**.
8. **Step 8 — cut the bookkeeping.** Morning findings (13,166 B) and skills/workflows (8,494 B)
   move to a digest or behind tools where the request does not need them.
9. **Step 9 — Hermes upgrade, gated.** **Executed by STEP U, 2026-09-08, out of order, under
   explicit authorization — see above and `00` rev7.** Re-check the protected instruction/context-
   file approval behaviour after upgrade (not yet done). **B7 bound:** use the lower of the two Step 3 total scores as
   the baseline anchor and the lower per-question score as each question's anchor. If Step 3 spread was
   **>10 percentage points**, B7 is not repeatable enough to size Step 5, decide Step 7 or gate the
   upgrade until the instrument is resolved. Otherwise the **B7 noise allowance** is the greater
   of the measured spread or **4 percentage points**. No anchored question that was at or above the
   coverage threshold may fall to zero, and total B7 may not fall from the lower baseline anchor by more
   than that allowance. Do not change the ceiling, anchor or allowance after seeing upgrade results.
9a. **Step 9a — continuity first: funded OpenAI API fallback; optional multi-OAuth proof.** After Step 9
    is green, configure/prove an official OpenAI API fallback with Liam's hard spend cap. When that cap
    is reached, never silently raise it: use NVIDIA only if Step 9b is explicitly enabled for that
    workload and attribution is intact; otherwise stop and surface the condition. Separately prove
    multiple ChatGPT/OpenAI OAuth credentials only if Hermes and provider terms support the exact use.
    Any pool uses `fill_first` / failover, never round-robin/random, and B8 must attribute credential
    slot + provider/model/cache usage per call. Do not use automatic account rotation to evade limits.
9b. **Step 9b — optional NVIDIA NIM capacity/cross-provider diversity.** Only if Liam wants the extra
    capacity. Register NVIDIA as a named native Hermes provider through the secret boundary. TTROS must
    work with NVIDIA absent. B7 + five worker tests gate production use. If OpenAI API cap is hit,
    NVIDIA may take over only for explicitly enabled/proven workloads with full attempted-hop and final
    serving attribution; otherwise stop honestly.
9c. **Step 9c — FCC on the Claude Code and Codex workbenches.** `fcc-claude` and `fcc-codex` for Liam's
    own workbench capacity only. Native `claude`, native Codex and Claude CoWork remain available and
    untouched. FCC is not a TTROS provider dependency. OpenAI/ChatGPT OAuth through FCC stays deferred;
    do not migrate TTROS OAuth into FCC or assume multi-account rotation there.
9d. **Step 9d — `fcc-hermes` experiment. OPTIONAL, time-boxed, non-production.** State the surface.
    It produces a finding, not an adoption. Nothing in TTROS may depend on it; no permanent FCC daemon
    is added to the TTROS spine.
10. **Step 10 — life and career tier.** `life/` namespace, Persistent Goals, B7 extended with a
    personal section. **Carries the availability-vs-execution rule above** — durable career context
    in the prefix, deadlines through the ordinary commitments block, execution on demand only.

**Map sizing is incremental with two terminators.** Add missing canonical fact classes one at a
time, re-score B7 after each, and stop at whichever comes first: the incremental gain fails to exceed
the Step 3 **B7 noise allowance**, or
**B2 headroom falls below 10,000 B**. With B2 held at 96,000 B, the map's ceiling is roughly
75–80 KB after identity, working state, thread and request — full canonical only just fits.

## D-STALENESS — OPEN, gated on a measurement

The map lives in the cached system prompt, assembled at session start; the vault changes by
promotion. **If context files are never re-read into an existing session**, automatic
regeneration on promotion is safe — new sessions get the new map, old sessions stay internally
consistent. **If they are re-read on a compression-triggered rebuild**, a session can silently
change its own beliefs mid-conversation and explicit approval is safer.

**The check in step 4 (B8 cache-and-latency observer), and it can return both answers:** regenerate the map with a unique
sentinel string mid-session, trigger compression, ask David to repeat the sentinel. He can =
re-read. He cannot = not re-read.

**Do not choose the policy before this runs.** Either way the suffix carries one line — *"map
generated `<date>`; N promotions since"* — so David flags staleness rather than asserting old
truth. ~80 bytes/turn.

**F-COMMIT-1 is desirable, not blocking — on one condition.** Each generated map must be
archived at generation time with timestamp, source manifest and SHA-256, and the archive must
**refuse to overwrite**. That answers "what did David receive on date X", which is the question
that matters; git answers "what did the vault say", which is related but different. **Without
the refuse-to-overwrite behaviour it is not evidence** and F-COMMIT-1 becomes blocking again.

## Retired by build plan rev 4, still retired in rev 5

* **T0d — RETIRED, not deferred.** It measured the ranking of a ranker the plan removes.
* **Reserved-slot retrieval — deleted.** Three runs never settled it; the architecture removes
  the question.
* **Deterministic passage extraction — do not build.**
* **Digesting the call corpus — deleted, not deferred.** Four of twelve parked candidates were
  wrong against source; a digest pass manufactures that error fifteen times and freezes it as
  canonical-looking text. Tools read the actual words instead (step 6 — corpus and vault behind tools).
* **Design rev 2 §5 projection, §6 distillation, §7 Graphify** — no longer active work.
  Graphify's remaining scope is the corpus only, and only if step 7 (Context Navigator, conditional) is justified.
* **D-BOUNDSEMANTICS — withdrawn.** B2 is not redefined.

## Checks that will bite if missed

* **Surface divergence.** Context-file discovery depends on the resolved working directory;
  gateway and CLI may differ, so Telegram-David and CLI-David could receive different maps. B7
  must state its surface; ideally run once on both and compare.
* **B8 is a plugin hook, not a gateway hook** — gateway hooks do not fire in the CLI.
* **Does `post_api_request` exist on the live Hermes version at all?** Never confirmed on v0.18.0;
  **not re-checked on v0.21.1 by STEP U either.** Step 4 (B8 cache-and-latency observer) specifies
  a hook that may not be present on the pinned build. **Same class as "verify the ceiling, not just
  the key."** Confirm locally before step 4; if absent, B8 attaches to whatever lifecycle hook the
  live version actually invokes, and that is a result, not a failure.
* **Never build a background or scheduled career/job search.** Execution is on demand only.
* **The map's not-allowed-to-claim list must include "Liam has niched down."**
* **Protected instruction/context-file approval is checked in step 4, not step 5.** A forced approval
  settles D-STALENESS on its own, so checking it later would let step 4 decide something step 5
  invalidates. Use the supported approval path if required; never bypass the protection. **Re-test
  after the STEP U upgrade — not yet done.**
* **Unattended promotion meets the protected write.** Nightly hygiene runs under systemd with no human
  present. Assert against the silent-failure case rather than assuming it away. **`aos-nightly-
  hygiene.service` is currently failing (STEP U finding, `00` rev7) — this check cannot be
  exercised live until that's fixed.**
* **A route that cannot record the actual serving path per call does not carry production work.**
  Record provider/model for every production call; for pooled/fallback routes also record the non-secret
  credential slot and attempted hops where safely available. Silent substitution makes B7, B8 and every
  receipt ambiguous.
* **State the surface for any provider or FCC route**, exactly as B7 must, and as B8 must for hooks.
* **Confirm one harness source, not two.** The correction is done; a superseded B6-titled copy beside
  the corrected file is the surviving risk, which is why the step-0 check is folder-scope.
* **One B7 noise rule governs Steps 5, 7 and 9.** Step 3 anchors the baseline to the lower of the two
  totals (and lower per-question values) and defines the **B7 noise allowance** as the greater of the
  measured spread or 4 percentage points when spread is ≤10 points. If spread is >10 points, B7 cannot
  size Step 5, decide Step 7 or gate Step 9 until the instrument is repaired. High noise is a finding,
  never a wider licence. **The instrument now has two further known defects (guard gap — fixed; scorer
  polarity blindness — open) beyond noise; see the scoring/fidelity work above.**
* **Is `context_file_max_chars` per-profile or global?** If global, raising it for David also
  raises it for worker profiles and any repo `AGENTS.md`. Confirm before step 5 (map in stable prefix).
* **Build the map from canonical notes only, never raw transcript text.** Context files pass a
  prompt-injection scan; quoted prospect speech is the likeliest thing to trip it, and dropped
  content is silent. **Assert the surviving byte count** — same class as the vacuous
  `MANIFEST-excluded : 0 == 0` gate that voided the F-INDEXSHAPE-1 confirmation.
* **One project context type loads per session** (`.hermes.md` beats `AGENTS.md`) — one file,
  one SHA-256.
* **Verify the ceiling, not just the key.** The config key exists on v0.18.0; its ceiling does
  not follow from that, and it has not been re-verified on v0.21.1. Read the constant during the
  dry run for step 5 (map in stable prefix).
* **Workers do not inherit the map.** Profile-level split; a five-child fan-out would otherwise
  pay five copies before any work began.
* **Composio writes go through `pre_tool_call` returning `{"action": "approve"}`.**

## Open questions — carried forward

* **Assembly count 38 → 9** (F-RETENTION-2). Unchanged, still blocks B3.
* **Brain documents in the index: 47.** `00` recorded 52; F-INDEX-1 recorded 33 of 37 on
  2026-08-15; the vault holds 87 markdown files. Moved three times, unexplained.
* The neutral `hi david` re-fence still outstanding — settles the VOID F-INDEXSHAPE-1
  confirmation. Cheap; fold into step 1 (remote access) or step 3 (B7 baseline).
* Graphify live state unconfirmed. Only matters if step 7 (Context Navigator, conditional) is justified.
* **Whether Step 5's closure stands** — see open operator decisions above.
* **The native-memory question** — see open operator decisions above and `00` rev7.
* **The judgment-heavy scoring rules** — see open operator decisions above.

## Closed — do not reopen, do not re-derive

* **Platform question** — closed 2026-09-03. **D-NAMING** — closed 2026-09-03.
* **D2 / D3 (positioning, niche)** — closed 2026-09-03 as **settled broad**, stated by Liam.
  Not deferred, not open. Reopen only on the recorded revisit trigger.
* **Career/life in scope, execution on demand** — decided 2026-09-03.
* **F-INDEXSHAPE-1 vault split** — applied green 2026-09-02T07:21Z. Live confirmation VOID.
* **Stage 2 review-tier promotion** — closed 2026-08-15.
* **F-RECENCY-1** — closed green 2026-08-16.
* **ICM-1 provenance compaction** — closed green. Do not reopen provenance.
* **F-BRAINNOTES-1 retriever fix** — applied green 2026-09-01T17:52.
* **F-NOTEBUDGET-1 byte budget** — closed green, confirmed live 2026-09-01T23:31. Becomes an
  assertion rather than a truncator at step 5 (map in stable prefix).
* **Backend restart + live B1/B2 confirmation** — closed green 2026-09-01T18:46.
* **The B7 guard's `terminal`/`process_manage` gap** — closed 2026-09-08 (STEP U). See `00` rev7.
* **`step6_post`'s test-material contamination status** — confirmed clean on its full enumerated
  tool surface, both input and output sides, 2026-09-08 (STEP U-CLOSE). See `00` rev7. Does not
  authorize a new B7 pass.

Durable facts and all open findings live in `00`. Do not restate them here.

## Constraints in force

* **Suite population is 808 passed / 0 failed** (STEP U, 2026-09-08). **772, 760 and 746 are all
  stale.**
* Patch `context_assembler.py` **anchor-gated**, not hash-gated (F-ASSEMBLERDRIFT-1).
* Protected, never opened: `connectors/`, `workspaces/north_shore_sales_coach/`, auth stores.
* No commit, no push, no external action without explicit approval. Rollback is backup-only
  under `/home/liam/ttros_backups/`.
* Claude Code executes directly in this repo (no WSL relay) — evidence discipline, token
  discipline and reporting still apply exactly as below. The relay rules immediately following
  this section describe how `01`/`02` are used by tools without a direct execution channel; they
  do not apply to a Claude Code session working in this repo.
* `_ttros_mirror/` is 2026-08-12 and predates the filter entirely. Architecture shape only,
  never evidence of current code.

## Relay rules

* From PowerShell 7, wrapped: `wsl -d AgenticOSClean -- bash -lc "…"`.
* **Shell variables do not survive the relay.** Literal absolute paths only — no `$`, no `$(…)`.
  Outer PS double quotes, inner bash single quotes. Script internals are fine.
* Every measurement script tees a `.txt` transcript beside itself and **refuses to overwrite**
  without `--overwrite`.

## Instrument rules — every one of these was paid for

The 2026-09-01 and 2026-09-02 sets stand (never gate on a hand-counted literal; `jq length`
counts characters not bytes; fence before measuring; numeric gates must assert their input is a
number; `journalctl --since` reads local time; `find -exec` substitutes every `{}`; count rank
the same way in every comparing script; measure the population the production code uses; ask a
ranking question of the ranker; key a prior figure by the query that produced it; disclose
confirmatory runs; `test -w` is not a writability check on the Windows mount). Added 2026-09-03:

* **A bare identifier is not a name.** `B6` meant two different things across two project files
  and nothing in `00`, and it took a live read of design §8 to settle. **When a detector is
  created, define it in `00` at that moment, or use a descriptive name until it is.** Same class
  as the ICM mis-expansion.
* **A document's title is an assertion and can be wrong.** The harness file's own title
  contradicted the design document that defined the term.
* **Disable before deleting.** Prove the replacement path green, then remove the old one. A flag
  is a better rollback than a backup restore.

Added 2026-09-08 (STEP U):

* **A detector that can only print PASS proves nothing — rehearse the negative case.** The B7
  guard's `terminal`/`process_manage` gap and the scorer's polarity blindness were both found by
  asking "can this instrument return the other answer", not by trusting a clean run. Any future
  scorer repair must be shown capable of failing before its passes are trusted.
* **Vocabulary overlap with legitimate content is not evidence of exposure.** The
  `step6_post_full_tool_surface_verification.py` instrument's first draft flagged 29 false
  positives by matching harness-doc prose and scorer keyword literals directly — content that
  legitimately also lives in the real vault documents the harness describes. Signal on the test
  material's own structural/meta scaffolding (titles, code identifiers, classification vocabulary)
  or on unfakeable tokens (session IDs, file paths), never on paraphrased business vocabulary.
