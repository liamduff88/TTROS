# TTROS — end state and build plan, rev 11

**2026-09-04.** Supersedes rev 10, same day. **No core architecture changed, nothing reopened,
and nothing in this revision starts implementation.** Rev 11 makes the B7 noise rule single and
self-consistent across every place that uses B7, and separates provider **continuity**, **capacity** and
**workbench convenience** so no optional provider becomes a hidden dependency.

**Changes from rev 10**

1. **One B7 noise allowance now governs every B7-dependent decision.** Step 3 defines the allowance as
   `max(4 percentage points, measured two-pass spread)` when spread is ≤10 points. If spread is >10
   points, B7 is declared insufficiently repeatable and cannot size Step 5, decide Step 7, or gate Step 9
   until the instrument is repaired. Step 5's old 3-point terminator is removed.
2. **Provider resilience is layered by failure mode.** Existing OpenAI/Codex OAuth remains primary. A
   budget-capped **official OpenAI API fallback** is the continuity path. NVIDIA NIM is optional
   capacity/cross-provider diversity. If the API cap is reached, NVIDIA is used only when explicitly
   enabled and proven for that workload; otherwise TTROS stops honestly and surfaces the condition.
3. **A second ChatGPT/OpenAI OAuth credential is optional, not the continuity foundation.** After the
   Hermes upgrade, Step 9a may prove supported multi-OAuth behavior on David's real surfaces, but only
   if the provider terms and upstream mechanism support that exact use. Never configure automatic
   exhaust-one-then-rotate behavior to evade usage limits.
4. **Credential-pool cache behavior is now load-bearing.** If any multi-credential pool is enabled for
   David, use cache-preserving `fill_first` / failover semantics — never round-robin or random — unless
   live evidence proves an equivalent cache-safe strategy. B8 must record a stable, non-secret
   credential-slot identifier plus provider/model and raw cache usage per call. No attribution = no
   production pool.
5. **FCC remains workbench-only and its Hermes caveats are restored.** `fcc-hermes` is an attached-session
   experiment; changing provider with Hermes `/model` leaves the FCC route, and fallback can make
   attribution ambiguous. It remains non-production. Post-upgrade deletion candidates explicitly carry
   forward Hermes `session_search`/FTS5 overlap and any custom B8 telemetry made redundant by native
   usage telemetry.

---

## 0. Changes from rev 3

1. **D-NAMING — CLOSED.** `TTROS_CONTEXT_ARCHITECTURE_DESIGN_2026-09-02.md` §8 read on the live
   machine, unsuperseded. **B6 = candidate disposition / declared-input arrival. B7 = the fixed
   business-question capability set. B8 = the new cache-and-latency observer.** Sequencing from
   §8 preserved: B6 before any change; B7 before any reduction is accepted as green.
   **Action — DONE 2026-09-04.** The harness source now reads
   `# B7 — the bound that can say NO`, and its body states that the document defines B7 and does not
   by itself close F-CAPABILITY-1. The 25 questions and scoring contract are unchanged.
   **What remains is a filing check, not a correction:** confirm that exactly one harness source
   exists in the folder and retire any superseded copy still titled B6. A corrected file sitting
   beside an uncorrected one is the same collision, one cold read later.
2. **D-BOUNDSEMANTICS — WITHDRAWN.** B2 stays as total context ≤96,000 B, unchanged, with its
   breach history intact. Fresh, cached, cache-write and latency become **B8** measurements.
   Adding instruments beats mutating an established bound. **Consequence in §2.**
3. **D-SESSIONS — downgraded from gate to input.** Provider prefix caching is keyed on prefix
   bytes and TTL, not on Hermes session identity. B8 telemetry is the deciding evidence.
4. **D-STALENESS — a mechanism check now precedes the policy choice.** See §3.
5. **F-COMMIT-1 — back to desirable, not blocking**, conditional on an immutable map archive.
6. **Step 4 disables the ranker behind a flag; deletion moves to Step 6b**, after both the map
   and the depth tools are green.

**B6 and B7 are different instruments, not one run seen twice.** B6 is assembler-side — for each
declared input, did it arrive? No model call, cheap, repeatable. B7 is model-side — can David
answer? The harness's CONTEXT-MISSING / IGNORED split **depends on B6**, because CONTEXT-MISSING
is determined by checking whether the fact's source document arrived at all. **So B6 must exist
before B7 is run**, not merely before changes are made.

---

## 1. Settled — do not reopen

**TTROS is infrastructure for the consulting business, not a product.** ChatGPT-plan OAuth is
unofficial and revocable (Anthropic removed the equivalent April 2026, Google February 2026,
bans without appeal — RESEARCHED), so it cannot carry a product; and TTR sells forward-deployed
builds, not software. Demo-grade costs nothing extra and is the case study. Revisit only when a
paying client asks to buy the system rather than a build.

Hermes stays, unforked and unpatched. Vault, queue, runner, dashboard, assembler stay. Composio
connects over MCP. No second orchestrator, no memory service, no Navigator unless B6 justifies
one.

**LOCAL-CONFIRMED:** `context_file_max_chars` exists on v0.18.0 (`agent/prompt_builder.py`,
`agent/system_prompt.py`, `hermes_cli/config.py`). The tier work is unblocked on the current version.
**The Hermes upgrade does not block Steps 0–8, and TTROS does not depend on NVIDIA or FCC.** After the
shrink work, Step 9 upgrades Hermes and proves the existing system first; Step 9a then tests whether the
selected supported release can host the later **continuity/capacity experiments** on David's real
surfaces. **Shrink the custom Hermes-bound layer first, then upgrade** — for the reasons in §1b, not for
any provider integration.

---

## 1a. Business scope — settled BROAD, and the life tier

**Stated by Liam 2026-09-03. Breadth is the decision.** Core consulting ICP: established businesses
with meaningful revenue and real workflow, data or operational problems where AI/systems work
creates material value. Narrower segments are **prospecting instruments, not exclusions** — the
60/40 `ideal_clients.md` split is a weighting for outbound, not a market restriction.
**Productisation thesis:** client delivery discovers painful repeatable problems; prove the
solution, then productise where appropriate (North Shore Honda is the live example). Product
opportunities can emerge from any engagement regardless of ICP. Revisit trigger: one segment
converting materially better, or a productisation candidate reaching paying customers.

**Hierarchy:** ICP → prospecting priority only · current priorities → executive briefs and focus ·
career/life → contributes when relevant · client/project → governs delivery · product
opportunities → cut across all.

**Career and life are in scope. Availability is not execution.** Liam is pursuing consulting /
digital-strategy roles (MNP, Deloitte and similar) alongside TTR. Durable career context sits in
the **prefix**, tiny and cached. Dated interviews and deadlines surface through the ordinary
commitments/priorities suffix blocks — no new surface, no new block. Execution happens only on an
explicit request, an active goal or task, or a deadline requiring action. **No timer, no
background search.** Career search is the one standing exception to "anything recurring is a
systemd user unit."

**Consequences for the build:** the map carries a short career entry and a not-allowed-to-claim
line — *Liam has not niched down*; B7's fact lists must not be written as though a single niche
exists; B7's personal section (Step 10) gains two honesty checks — surface a dated interview when
asked what to focus on, and never propose or launch continuous job search unprompted. No cost,
latency, capability or maintenance change.

## 1b. Sequencing — shrink first, upgrade second, resilience by failure mode after

This is the controlling interpretation of Steps 5–9d. **Do not move the Hermes upgrade ahead of the
custom-layer reduction.** The upgrade cost is proportional to the amount of TTROS code coupled to
Hermes internals. The current review measured the assembler at roughly 1,528 lines; live-check the
current number before implementation rather than treating that planning figure as permanent.

The sequence is deliberate:

```text
B6/B7/B8 instruments
→ Step 5: stable-prefix map; old ranker disabled
→ Step 6: corpus/vault depth behind tools
→ Step 6b: delete obsolete ranking/retrieval machinery
→ Step 7 only if B6/B7 justify it
→ Step 8: remove remaining bookkeeping/context weight
→ Step 9: upgrade Hermes and prove TTROS behavior
→ Step 9a: funded OpenAI API continuity fallback; optional policy-compatible multi-OAuth proof
→ Step 9b: optional NVIDIA native-provider capacity/cross-provider diversity, gated by B7 + worker tests
→ Step 9c: FCC on Claude Code / Codex workbenches only
→ Step 9d: fcc-hermes experiment — optional, time-boxed, non-production
```

Step 9c touches no TTROS component and can run when a session suits, but it must not delay Steps 0–9b.
Steps 5, 6 and 6b are primarily **net removals/simplifications**. Step 7 may never be built. Steps 2,
3 and 4 are the instruments that say whether the simplification worked. The goal is to arrive at Step 9
with the smallest practical custom seam to re-attach — ideally the supported context-engine/context-file
seam rather than a broad lifecycle-hook dependency.

**Protected instruction/context-file boundary:** Step 5 generates `.hermes.md`. **The check runs in
Step 4, not Step 5** — see §3. If the build treats that file class as protected and requires explicit
approval, use the supported approval path; do not bypass, patch out, or weaken the gate. Step 9 repeats
the check after upgrade because upstream semantics may have changed.

**Provider resilience boundary — separate continuity from capacity.** TTROS must remain operational
on its existing OpenAI/Codex OAuth route whether or not any optional provider is configured. The
**continuity fallback is an official OpenAI API route with a Liam-approved hard spend cap** (D6), not a
second subscription account. After Step 9 is green, Step 9a also live-checks the selected supported
Hermes release on **David's real runner/Telegram surfaces** for supported multiple-OAuth behavior. A
second ChatGPT/OpenAI OAuth credential may be used only if the provider terms and Hermes mechanism
support that exact use; it is convenience/additional availability, not the continuity foundation, and
TTROS must never configure automatic account rotation to evade provider usage limits.

**Optional free-capacity boundary — NVIDIA only if useful.** Step 9b may add NVIDIA NIM as a named
native Hermes provider for evidence-supported workloads, but NVIDIA is not the default authority and is
never required for TTROS to function. Hosted/free availability is dynamic; catalog, rate limits and
model identifiers are live-discovered. If the official API fallback reaches its spend cap, TTROS may
fall through to NVIDIA **only when NVIDIA is explicitly enabled for that workload and every serving hop
is attributable**; otherwise stop honestly and surface the condition to Liam. No silent substitution.

**Why not a proxy in front of TTROS.** `00`'s design rule fires directly: *if a change needs a permanent
new component to keep working, question the change.* **FCC is therefore scoped to the workbenches**
(Step 9c), where it is useful without becoming another TTROS runtime dependency. Native `claude`,
native Codex and Claude CoWork remain available.

**FCC boundary:** FCC does not replace David, Operating Hermes, the Context Assembler, Business Brain,
queue/runner, receipts, dashboard, search, Graphify, systemd, Claude Code or Claude CoWork. **It is not
on any TTROS execution path.** `fcc-hermes` survives only as the optional Step 9d experiment and must
never become a dependency of anything.

## 2. B2 is now the binding constraint on map size

Keeping B2 at 96,000 B total has a consequence worth stating rather than discovering: 96,000
minus identity, working state, rolling thread and the request leaves roughly **75–80 KB for the
map**. Full canonical inclusion only just fits, with essentially no headroom.

**So the incremental growth rule gets a second terminator.** Step 3 first establishes the single
**B7 noise allowance**. Add missing canonical fact classes one at a time, re-score B7 after each, and
**stop at whichever comes first**:
* a class fails to improve B7 by **more than the declared B7 noise allowance**, or
* B2 headroom falls below 10,000 B.

This has a predeclared consequence: a noisier but still usable B7 produces a more conservative/smaller
map. If Step 3 spread is >10 points, B7 is not repeatable enough to size the map at all; Step 5 cannot
use B7 for sizing until the instrument finding is resolved. Do not silently revert to the old 3-point
terminator.

This is a real limit, not a preference, and it is a good argument for the map being a genuine
map — durable knowledge, settled decisions, entities, taxonomy and pointers — rather than the
vault inlined.

---

## 3. D-STALENESS — mechanism check before policy choice

**Open. Now gated on a measurement rather than a judgement.**

The map lives in the cached system prompt, assembled at session start. The vault changes by
promotion. If context files are **never re-read into an existing session**, then automatic
regeneration on promotion is safe: new sessions get the new map, existing sessions stay
internally consistent, and the whole problem shrinks. If they **are** re-read on a
compression-triggered rebuild, a session can silently change its own beliefs mid-conversation
and explicit approval becomes the safer policy.

**The check, and it can return both answers:** regenerate the map with a unique sentinel string
in it, mid-session; trigger compression; ask David to repeat the sentinel. If he can, context
files are re-read. If he cannot, they are not. Read-only against production data; costs one
model call.

**Do not choose the policy before this runs.** Rev 3 recommended explicit approval on reasoning
alone; that recommendation is suspended pending the check.

**The protected-file check runs in the same step, and it can override the sentinel.** If the pinned
build classifies `.hermes.md` as a protected instruction/context file and forces approval on every
write, then automatic regeneration is impossible unattended **whatever the sentinel returns** — the
platform has decided the policy, not the measurement. Running this check in Step 5, as rev 6 had it,
would let Step 4 settle a decision that Step 5 then invalidates. Two cheap checks, one step, one
decision.

**And it reaches further than the map.** Nightly hygiene promotes automatically under systemd with no
human present. If map regeneration is ever wired to promotion and the write requires approval, the timer
either blocks on the vault mutex or fails silently. **The second is the failure mode this project keeps
finding, so it must be asserted against rather than assumed away.**

**Either way**, the volatile suffix carries one line — *"map generated `<date>`; N promotions
since"* — so David can flag staleness rather than assert old truth confidently. ~80 bytes/turn.

**F-COMMIT-1 is desirable, not blocking, on one condition.** Each generated map is archived
immutably at generation time with timestamp, source manifest and SHA-256, and the archive
**refuses to overwrite** — the same discipline as the measurement transcripts. That
independently answers "what did David receive on date X", which is the question that matters.
Git would answer "what did the vault say", which is related but different. **Without the
refuse-to-overwrite behaviour it is not evidence**, and F-COMMIT-1 becomes blocking again.

---

## 4. The design

**Prefix — stable, cached, byte-identical turn to turn**
* `SOUL.md` — identity and rules, slot #1.
* **The map** — one generated context file: business model, offers, delivery, ICP, the
  not-allowed-to-claim list, key entities and projects, **settled** decisions, and the Brain
  taxonomy with pointers to where deeper evidence lives.

**Suffix — variable, per turn, uncached by design**
* Rolling thread, current priorities, open loops, **changing** decisions, the map-staleness
  line, today, the request, and any evidence retrieved for this specific turn.

**Depth — zero bytes until asked for**
* `brain` MCP tools: `search_calls`, `open_call`, `open_note`, `search_history`.

**Product test:** David already knows the business and can immediately identify where to dig
deeper. That is *map + pointers + tools*. Neither half requires guessing what David needs before
he has seen the question.

**Maintenance argument:** no ranker to drift, no classifier to mistrain, no new component. Every
defect measured this month came from a component deciding on David's behalf.

**Prediction, recorded before the run** (JUDGEMENT): CONTEXT-MISSING dominates and IGNORED is
rare, because the evidence is absence rather than misuse — zero documents returned on six of six
frozen queries, and David reporting no calls on file when fifteen were indexed with full bodies.
**If IGNORED dominates, this diagnosis is wrong, the Navigator is the right build, and Step 7
becomes the priority.**

---

## 5. Profiles

Children spawned by `delegate_task` **do not inherit the map** — a five-child fan-out would
otherwise pay five copies before any work began. David's profile carries the map; worker
profiles get a task brief plus tools and pull business facts through `brain`.

Executor boundaries: durable work → your queue and runner (receipts, approvals, survives
restart). Hermes `delegate_task` → short in-session parallel reads only. Codex / Claude Code →
separate subprocesses, inherit nothing.

---

## 6. The build plan

Assumptions: you drive Codex or Claude Code, you approve rather than review, units are
half-days. Rollback is backup-only under `/home/liam/ttros_backups/` unless stated.

**Step 0 — Filing corrections (four vault edits + one harness filing check).** 1 hour, no code,
**no decision pending and not a blocker** — Step 1 (remote access) may run first. Five corrections:

1. `memory/positioning.md` records the settled broad scope and revisit trigger in place of the
   `CONFLICT — unresolved` block, with the narrower framing in the Strategic Foundations and First
   Offer briefs reconciled to it.
2. `memory/ideal_clients.md` keeps 60/40, retitled as a prospecting weighting rather than a market
   restriction.
3. `operating_context/current_priorities.md` stops reading the market-scope choice as open.
4. **Candidate #5 is retyped from `liam_intention` to advice received** — Mike Knapp advised
   niching, Liam recorded as reluctant; scope remains deliberately broad.
5. **The harness source correction is DONE (2026-09-04); what remains is a filing check.** The
   corrected file is titled `# B7 — the bound that can say NO` and states that it defines B7 without
   closing F-CAPABILITY-1. Confirm that **exactly one** harness source exists in the folder, and
   retire or delete any superseded copy still titled B6. Note the filename divergence deliberately:
   the plan long referred to `TTROS_CAPABILITY_HARNESS_QUESTIONS_v1.md` while the corrected file is
   `TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`. **Two files, one corrected and one
   not, is the same collision one cold read later.** Do not alter the 25 questions or scoring
   contract.

**Proof has two independent clauses:**
* Vault: no `CONFLICT — unresolved` marker remains and `current_priorities.md` no longer reads the
  market-scope choice as open.
* Harness: **folder-scope, not file-scope.** No heading or body line anywhere in the folder labels
  the capability harness B6, no line claims that the question set's existence closes F-CAPABILITY-1,
  and exactly one harness source survives. The check must be able to fail if either stale assertion
  remains anywhere, or if two harness sources are found.

**Rollback:** vault edits use the existing gated vault-write path and their normal git rollback.
Before changing the harness source, confirm whether that path is git-tracked. If tracked, rollback
is git; if untracked, save an immutable preimage under `/home/liam/ttros_backups/` and restore from
that preimage if needed. Do not assert git rollback for an untracked file.

Unresolved strategy elsewhere is represented honestly in the Brain and does not gate the build.

**Step 1 — Remote access, tested before built.** Half a day; nothing in TTROS changes.
Cloudflare Tunnel plus Zero Trust Access in front of the existing dashboard; confirm the
Telegram gateway reaches David. Predictions recorded now: dashboard works first attempt;
Telegram reaches David with poor UX. Proof: from your phone on mobile data, dashboard loads
behind a login and David answers in Telegram. Rollback: delete the tunnel.

**Step 2 — B6: candidate disposition / declared-input arrival.** Half a day, assembler-side, no
model calls. For every declared input and candidate document, record whether it arrived in
assembled context and, if not, at which stage it was dropped. **This must exist before B7 is
run**, because CONTEXT-MISSING is determined by it. Cheap, repeatable, re-run after every later
step. Detector requirement: it must be able to report both arrival and non-arrival — a check
that can only report "arrived" is broken.

**Step 3 — B7 baseline, repeatability, plus the session and gap measurement.** 1 day. Run **two
independent complete B7 passes** on the same premium model and the same declared surface, with the same
frozen 25 questions, fact lists and scorer, each in fresh sessions. Record both total scores, the
**absolute total-score spread**, and per-question deltas.

**Predeclared repeatability and acceptance rule — fixed before either pass runs:**

* **Baseline anchor:** the **lower of the two total scores**. For per-question comparisons, use the
  **lower score for that question across the two passes**.
* **Noise ceiling:** if the two-pass total spread is **greater than 10 percentage points**, B7 is not
  repeatable enough to **size Step 5, decide Step 7, or gate Step 9**. Stop and record an instrument
  finding; investigate B7 before using it for any of those three decisions. **Do not convert high noise
  into a wider licence.**
* **B7 noise allowance:** if spread is ≤10 points, define one number used everywhere B7 acts as a
  decision threshold: the greater of the measured spread or **4 percentage points**. The allowance,
  10-point ceiling and lower-anchor rule are declared now and may not be loosened after results are seen.

If the second complete pass cannot be obtained, Step 3 may still produce descriptive evidence, but
**B7 cannot size Step 5, decide Step 7, or gate Step 9 until repeatability is measured.**

**State the surface the harness runs on** — currently unspecified, and gateway and CLI may resolve
context files differently. In the same pass, pull the **inter-request gap distribution against cache
TTL** (caches clear after 5–10 minutes idle and within an hour without extended retention — RESEARCHED);
turns-per-session is the weaker question. Bounds declared now, not moved: ≥80% coverage = PASS; any
question at 0% investigated regardless of total; honesty questions pass/fail. Prediction: 30–45%
overall, §E near zero, at least one honesty failure, CONTEXT-MISSING dominant. **This step sizes Step
5's map and decides whether Step 7 is built.**

**Step 4 — B8: cache-and-latency observer.** Half a day, instrumentation-only. Use a **plugin
lifecycle hook actually present on the pinned v0.18.0 build** — not a gateway hook, which would not
fire in the CLI. Confirm `post_api_request` locally before using it; if it is absent, attach B8 to the
actual supported lifecycle equivalent and record that as the result. Log the **raw provider usage
object** alongside normalised `cached_tokens` / `cache_write_tokens` and wall-clock latency per call. The unknown: OpenAI prefix caching is documented for the API
(automatic above 1,024 tokens, cache reads at 0.25–0.5× input, extended retention to 24 hours —
RESEARCHED), but **whether the Codex OAuth path surfaces cache telemetry at all is not
established**. Bound: if the field is absent or always zero, the amortisation argument is void
and the map is sized for absolute cost. Both outcomes are results. **Also make B8 credential-aware now:**
record the serving provider/model and, where Hermes safely exposes it, a stable opaque credential-slot
identifier per call. Never log credential values. This is required before any Step 9a pool proof because
provider-side prompt caches are credential/account scoped; an invisible slot change would otherwise make
cache-hit and latency measurements uninterpretable.
**Also run here, both cheap and both able to return either answer:**
* The D-STALENESS sentinel check (§3).
* **The protected instruction/context-file check.** Does the pinned build classify `.hermes.md` as a
  protected file requiring write approval? Moved forward from Step 5 because a positive answer settles
  D-STALENESS on its own, regardless of the sentinel. If protected, record the supported approval path
  and never plan around bypassing it.

**Step 5 — The map goes in the prefix, ranker disabled not deleted.** 1–2 days. Generate the map
deterministically from `canonical.manifest` into a single `.hermes.md`; pin
`context_file_max_chars`. **The protected-file question is already answered in Step 4; carry that
answer into the write path and re-assert it at the apply gate rather than re-deciding it here. If the
file is protected, use the supported approval path and never bypass it.** Then **put the old canonical ranking path behind a flag, default off**.
Archive each generated map immutably with timestamp, source manifest and SHA-256, refusing to
overwrite. Working state stays on the per-turn path. Bounds: B7 coverage on
offers/positioning/pipeline/priorities ≥80%, or investigate; **map growth uses the Step 3 B7 noise
allowance from §2 and is unavailable if Step 3 spread exceeded 10 points**; B2 total ≤96,000 B; fresh
bytes per turn below today's 45,804 B equivalent; latency not worse than the 25.9s baseline — the last
two from B8, or revert. Apply gate **asserts the surviving byte count** after the injection scan.
**Rollback is flipping the flag**, not restoring a backup.

**Step 6 — Corpus and vault behind tools.** 1 day; extends the existing `brain` MCP server.
`search_calls`, `open_call`, `open_note`, `search_history`. Bound: B7 §E ≥70%, currently expected
near zero. **Also record**: questions answered from map plus working context alone versus those
needing a tool round-trip, and the latency each adds. That ratio is the signal for whether the
map is under- or over-sized.

**Step 6b — Delete the obsolete retrieval machinery.** Half a day. **Only after Steps 5 and 6
are both green.** Remove the ranking path, the `direct_fallback` keyword table, the
post-truncation class filter, and the reserved-slot and passage-extraction designs. Re-run B6
and B7 to confirm nothing depended on them. **Carry two named post-upgrade deletion candidates forward,
not into this pre-upgrade delete:** Hermes `session_search`/FTS5 if the supported post-upgrade retrieval
seam makes it redundant, and any custom B8 telemetry shim that native post-upgrade usage telemetry
fully replaces. Delete either only after Step 9 proves the replacement on David's real surfaces.

**Step 7 — Context Navigator — CONDITIONAL.** 2–3 days. **Do not build unless B6/B7 showed
IGNORED dominating.** If justified: inside the existing Context Assembler, not as a new
component; deterministic-first (entity and domain pointers → Graphify relationships → exact
search → canonical fallback); **suffix only**. The moment it touches the prefix, the cache is
lost on exactly the turns that matter most. **Decision gate uses the single Step 3 B7 noise rule:** if
spread was >10 points, B7 cannot decide whether this step is built until the instrument is repaired; if
usable, the evidence for IGNORED dominance must exceed the declared B7 noise allowance. Bound once
built: B7 must rise by more than the allowance and B8 must show the saving that motivated it.

**Step 8 — Cut the bookkeeping.** Half a day. Morning findings (13,166 B) and skills/workflows
(8,494 B) to a digest or behind tools; skills load only when the request needs that class of
action. Bound: B7 must not fall more than 2 points and B8 must show a cost or latency
improvement.

**Step 9 — Hermes upgrade, gated.** 0.5–1 day. Still **not a blocker for Steps 0–8**, and deliberately
remains after the shrink work. TTROS continues to operate on its existing OpenAI/Codex route regardless
of whether NVIDIA or FCC is configured. The upgrade earns its place because Steps 5–6b make the
re-attach small, the supported context-engine seam is a better home for the assembler than a broad
lifecycle-hook dependency, and native usage telemetry may simplify B8. **Those are the reasons for the
upgrade.** Any newer credential-pool/provider behavior is a downstream capability to test later, not a
justification for moving or performing the upgrade. Live-check the installed version and latest
supported upstream release at execution time; do not hard-code planning-time version assumptions. Copy
the profile; never upgrade the only live profile in place.

Upgrade Hermes **alone**, then prove TTROS before adopting downstream changes: David, Context
Assembler/context-engine seam, rolling continuity, semantic execution handoff, Operating Hermes
profiles, queue/runner, MCP, systemd-owned services, and fresh `hermes-*.json` evidence with the expected
block set. Re-check protected instruction/context-file approval behavior for `.hermes.md`.

**B7 acceptance bound — fully predeclared in Step 3.** The baseline anchor is the **lower of the two
Step 3 total scores**; each per-question anchor is the **lower score for that question across the two
passes**. If the Step 3 spread was **greater than 10 percentage points**, B7 is too noisy to gate the
upgrade and Step 9 cannot be accepted on B7 until the instrument is resolved. If spread is ≤10 points,
the **B7 noise allowance** is the greater of the measured spread or **4 percentage points**. No
anchored question that was at or above the coverage threshold may fall to zero, and the post-upgrade
total may not fall from the lower baseline anchor by more than that allowance. Do not change the anchor,
allowance or 10-point ceiling after seeing upgrade results. B6/B8 must remain interpretable; no silent
loss of context blocks or execution handoff.

Do not adopt new Hermes features in this step merely because they exist. **A separate later pass decides
what the upgrade lets TTROS delete.**

**Why Step 9 stays here:** Steps 5, 6 and 6b reduce the custom layer that must survive/re-attach across
the upgrade. The goal is the smallest supported seam. The upgrade is **not required for TTROS to keep
operating** and is not justified by NVIDIA/FCC; it is the point after which the newer native provider
and credential mechanisms can be tested safely against a smaller custom layer.

**Step 9a — continuity first: funded OpenAI API fallback; optional multi-OAuth proof.** 0.5–1 day
after Step 9 is green and after Step 5/B8 cache value is known.

The existing OpenAI/Codex OAuth path remains primary. **Continuity is provided by an official OpenAI API
route with a Liam-approved hard spend cap (D6).** Configure it through the normal secret boundary, prove
one controlled failover without manufacturing real account exhaustion, and prove the cap/stop behavior.
When the API cap is reached, the default is **not** silent substitution: fall through to NVIDIA only if
Step 9b has been explicitly enabled for that workload and attribution is intact; otherwise stop the
model route, surface the condition to Liam/Needs Me, and preserve queued work for retry.

Separately, live-confirm on the selected supported Hermes release and on David's actual production
surfaces (runner-invoked CLI and Telegram gateway) whether Hermes can hold/use two ChatGPT/OpenAI OAuth
credentials for the same provider. If the exact use is supported by both upstream Hermes and provider
terms, a second credential may be proven as optional convenience/additional availability. **Do not
configure automatic exhaust-one-then-rotate behavior to evade usage limits, and do not make the second
OAuth credential the continuity foundation.** If unsupported or policy-unclear, record the finding and
keep the single-OAuth route. Do not build custom account-switching machinery. Never print or commit
credentials.

**Cache-preserving pool bound:** if any multi-credential pool is enabled for David, deliberately use
`fill_first` / failover semantics (or a live-proven equivalent that keeps the same credential until it
actually becomes unavailable). **Never use round-robin or random for David's stable-prefix path.**
Provider-side prompt caches are credential/account scoped, so changing slots invalidates the cached
prefix. B8 must record provider, model, cache usage and a stable opaque credential-slot identifier for
every pooled call. If the serving slot cannot be attributed without exposing secrets, the pool does not
carry production TTROS work. This is why Step 9a remains after B8 is running and after Step 5 has
measured what the prefix cache is worth.

Rollback: remove the API fallback route and/or second OAuth credential independently; the existing
primary OAuth route remains unchanged. No duplicate calls, no secret values in evidence.

**Step 9b — optional NVIDIA NIM capacity and cross-provider diversity.** 0.5 day, only if Liam wants
additional free/low-cost capacity or a separately governed cross-provider route.

Register NVIDIA NIM as a **named native Hermes provider**, using the normal secret boundary. Never print
or commit the key. Live-query the current NVIDIA catalog, identifiers and rate limits rather than
hard-coding planning-time names. **TTROS must remain fully functional when NVIDIA is absent, rate-limited
or unavailable. NVIDIA is not a prerequisite and never becomes the sole production path.**

Before routing production work through NVIDIA, reuse the existing 25-question B7 harness against the
NVIDIA model and compare it with the Step 3 premium baseline on the same declared surface. Alongside it,
run this fixed worker set: (1) Business Brain read/summarise, (2) routine queue item end-to-end,
(3) document extraction/summarisation, (4) two-round-trip MCP tool task, and (5) instruction-following
with an explicit do-not-change constraint. Score pass/fail on correctness, instruction following, tool
use and unnecessary changes. If tool-use or instruction-following fails, it is not a worker regardless
of B7.

Only then may the existing TTROS routing architecture use NVIDIA for evidence-supported workloads.
NVIDIA is a capacity/diversity option, not a silent continuation of an exhausted OpenAI route. If the
OpenAI API fallback hits its spend cap, NVIDIA may receive the work only when that workload has been
explicitly approved for NVIDIA and **provider/model/credential-route attribution is present before and
after the handoff**. Otherwise stop honestly and surface the condition.

**Hard attribution bound:** every production model call records the provider and model that actually
served it; pooled routes additionally record the non-secret credential slot where available. If a
fallback path can consume multiple providers/credentials before success, record the attempted hops as
well as the final serving hop. If this cannot be done, do not route production work through that path.
Rollback is removing the NVIDIA provider entry; TTROS remains operational.

**Step 9c — FCC on the Claude Code and Codex workbenches.** 0.5 day. **Touches no TTROS component.**

Install FCC only for Liam's own workbench capacity. Name and pin the source repository explicitly. Use
`fcc-claude` and `fcc-codex` when useful; native `claude`, native Codex and Claude CoWork remain
available and untouched. Switching is explicit, never a rewrite of an existing workbench's
configuration.

FCC's OpenAI/ChatGPT OAuth capability stays deferred. Do not migrate TTROS's OpenAI/Codex OAuth into
FCC, and do not assume multi-account rotation inside FCC. The two-account resilience question belongs
to Hermes Step 9a first.

**Step 9d — `fcc-hermes` experiment. OPTIONAL, time-boxed, non-production.** Half a day, once, and only
if there is a session to spare. State the surface. It produces a recorded finding, not an adoption.
The documented launcher proves an **attached Hermes session**, not David's runner/Telegram production
surfaces; a Hermes `/model` provider change leaves the FCC route, and FCC fallback can obscure which
provider/model actually served or consumed a failed attempt. Those are the reasons it is non-production.
Nothing in TTROS may depend on `fcc-hermes`, and no permanent FCC daemon is added to the TTROS spine.

**Step 10 — The life and career tier.** 2–3 days. `life/` namespace: goals, people, health,
commitments, calendar, **career**. Same promotion machinery, same approval path, same tiers. Wire
Persistent Goals. Extend B7 with a personal section written before the tier is populated.
**Carries the §1a rule:** durable career context in the prefix; deadlines through the ordinary
commitments block; execution on demand only, never scheduled. Bound: the two honesty checks in
§1a must both be able to fail, and must pass.

**Existing Steps 0–10 remain roughly 9–14 working days. Steps 9a–9d add roughly 1.5–2 working days**
— 9a half, 9b half, 9c half, 9d an optional half — **for a planning total of about 10.5–16 working days
across 3–5 weeks**, stoppable after any step with the value banked. **Step 9c is independent of the spine. Step 9a follows Step 9 because provider resilience is adopted
only after the upgrade has proved the smaller TTROS seam, and because B8/Step 5 must first establish the
cache value that any credential pool could disturb. Step 9b is optional NVIDIA capacity/diversity and
may be skipped entirely. Step 9d may never be taken at all.

---

## 7. Checks that will bite if missed

* **Confirm one harness source, not two.** The source correction is done; the surviving risk is a
  superseded B6-titled copy sitting beside the corrected file. The Step 0 check is folder-scope for
  exactly this reason. Otherwise D-NAMING recurs on the next cold read.
* **Surface divergence.** Context-file discovery depends on the resolved working directory;
  gateway and CLI may differ, so Telegram-David and CLI-David could receive different maps. B7
  must state its surface, and ideally run once on both and compare.
* **B8 is a plugin hook, not a gateway hook** — gateway hooks do not fire in the CLI.
* **Does `post_api_request` exist on v0.18.0 at all?** The hook demotion
  (`pre_llm_call` → `pre_api_request`/`post_api_request`) is UPSTREAM-DOC at `main` and has never
  been confirmed on the pinned build. Step 4 currently specifies a hook that may not be there.
  Confirm locally before Step 4; if absent, attach B8 to whichever lifecycle hook v0.18.0 actually
  invokes and record that as the result. **The same class of error as assuming a config key's
  ceiling from the key's existence.**
* **Protected instruction/context-file approval is checked in Step 4, not Step 5.** A forced approval
  settles D-STALENESS on its own, so checking it after the sentinel would let Step 4 decide something
  Step 5 invalidates. Use the supported approval path if required; never bypass the gate. Step 9 repeats
  the check after upgrade because upstream semantics may differ.
* **Unattended promotion meets the protected write.** Nightly hygiene runs under systemd with no human
  present. If map regeneration is ever wired to promotion and the write needs approval, the timer blocks
  or fails silently. Assert against the silent case; do not assume it away.
* **An optional provider route with unrecorded attribution is not usable.** If the provider and model
  that served a production call cannot be recorded per call, TTROS work does not go through that path.
  Failover that silently substitutes a model makes B7, B8 and every receipt ambiguous. For pooled
  credentials, record a stable opaque credential slot and attempted hops where safely available.
* **Credential rotation can destroy the prefix cache.** Do not accept Hermes's pool default blindly.
  For David's stable-prefix path, use `fill_first` / failover semantics and never round-robin/random
  unless live evidence proves the alternative does not rotate credentials across normal turns. B8 must
  make any slot change visible beside cache-read/write telemetry.
* **State the surface for any FCC or provider route.** `fcc-hermes` is documented as an attached-session
  launcher and the FCC route is left by a Hermes `/model` change. David runs through the runner-invoked
  CLI and the Telegram gateway. A proof on the wrong surface proves nothing.
* **Name and pin the FCC source repository.** Several near-identical forks exist, and the tool holds
  every provider key. An unpinned install of a credential-holding proxy is a supply-chain decision, not
  a convenience.
* **Is `context_file_max_chars` per-profile or global?** If global, raising it for David also
  raises it for worker profiles and any repo `AGENTS.md`. Confirm before Step 5.
* **Build the map from canonical notes only, never raw transcript text.** Context files pass a
  prompt-injection scan; quoted prospect speech is the likeliest thing to trip it, and dropped
  content is silent. Assert the surviving byte count — the same class as the vacuous
  `MANIFEST-excluded : 0 == 0` gate that voided the F-INDEXSHAPE-1 confirmation.
* **One project context type loads per session** (`.hermes.md` beats `AGENTS.md`), so the map is
  one generated file. One file, one SHA-256.
* **Verify the ceiling, not just the key.** The config key exists on v0.18.0; its ceiling and
  scaling behaviour do not follow from that. Read the constant in Step 5's dry run.
* **Composio writes go through `pre_tool_call` returning `{"action": "approve"}`.**

---

## 8. Decisions still open

| # | Decision | What settles it |
|---|---|---|
| D-STALENESS | Automatic regeneration versus explicit approval | The sentinel check in Step 4. Not judgement. |
| D4 | Map membership | `canonical.manifest`. You approve the list once. |
| D5 | Whether the Navigator is built | B6/B7 disposition split, Step 3. |
| D6 | Official OpenAI API fallback spend cap | **Required before Step 9a.** Liam sets the hard cap; reaching it never silently increases spend. NVIDIA may take over only for an explicitly enabled/proven workload with full attribution; otherwise stop and surface the condition. |
| D8 | Optional NVIDIA shortlist and routing scope | Step 9b: only if Liam wants the capacity; B7 against the Step 3 premium baseline plus five recorded worker tests. NVIDIA is additive capacity, not a dependency or substitute for the primary OpenAI path. |
| D9 | Whether `fcc-hermes` is ever more than an experiment | Step 9d, on the correct surface, with per-call attribution. Default answer is no. |

Closed: D-NAMING, D-BOUNDSEMANTICS (withdrawn), D-SESSIONS (downgraded to a B8 input), D1
(infrastructure), D7 (Composio through the approval gate), **D2/D3 (settled broad, §1a)**, and
**provider resilience direction — decided 2026-09-04 as layered by failure mode: existing
OpenAI/Codex OAuth remains primary; an official budget-capped OpenAI API route is continuity fallback;
optional multi-OAuth behavior is only proven/used when supported and policy-compatible; NVIDIA is
optional capacity/cross-provider diversity; FCC is scoped to the workbenches.**

---

## 9. What this does not attempt

Replace the engine · migrate to the native Hermes queue · multi-tenancy, billing or auth for
others · digest the transcripts · adopt a memory service (trigger: life-tier journal >200 KB, or
a temporal B7 section that fails) · build custom account-rotation machinery · run T0d · fork or patch Hermes ·
redefine B2 · replace Claude Code or Claude CoWork · make any free provider a single point of failure ·
promise unlimited/free-token capacity · migrate all OpenAI OAuth into FCC before it is proven ·
**put a proxy on a TTROS execution path** · **route production work through any path that cannot record
the provider and model per call** · **let anything in TTROS depend on `fcc-hermes`** · **add a permanent
new daemon to the spine to obtain a capability Hermes already offers natively.**

---

## 10. Where this is thin

* **Market scope is now stated by you (§1a); offer-level copy is not.** Positioning at the level
  of website and Scan wording is still assembled rather than yours, and Step 0 does not fix that.
* **UPSTREAM-DOC claims describe Hermes at `main`, and the pinned build is v0.18.0.** The size of that
  delta is not recorded here because no sourced figure exists for it; rev 6 carried an unattributed
  "8,090 local commits" that was keyed to nothing and has been removed. **Step 9 live-checks the
  installed version and current upstream behaviour instead of assuming the delta**, which is the correct
  handling either way.
* **Native multi-OAuth support is a moving/upstream capability.** Step 9a must prove it on the selected
  supported Hermes version and on David's actual production surfaces; documentation alone is not proof.
  The pool strategy is also part of the proof because credential rotation changes provider-side cache
  identity; `fill_first` / failover is the required default for David unless live evidence disproves the
  cache risk.
* **NVIDIA's free tier is a moving surface.** If Step 9b is taken, model catalog, availability,
  identifiers and rate limits must be live-discovered; planning-time names and limits are not guarantees.
* **FCC is a moving third-party surface with several near-identical forks.** Anything relying on it is
  confined to Steps 9c and 9d, off every TTROS execution path, with the source named and pinned.
* **Caching under Codex OAuth is unverified.** Step 4 exists solely to settle it.
* **The baseline and CONTEXT-MISSING predictions are guesses**, written down so they can fail.
* **B2 headroom at 10,000 B is a judgement, not a measurement.** If Step 5 shows working state
  and thread running larger than modelled, that terminator binds earlier than expected and the
  map shrinks. Measure, do not assume.
