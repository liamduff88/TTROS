# B7 — the bound that can say NO. Question set v1.

> **Frozen question set v1.** The 25 questions and scoring contract are fixed for baseline
> comparability. Most fact lists were read from the vault on 2026-09-02. Later authoritative
> decisions are dated inline; the 2026-09-03 settled-broad market decision supersedes the
> contradictory niche/positioning state that existed in the vault on 2026-09-02.
>
> **This document defines B7; it does not by itself close F-CAPABILITY-1.** B7 can close
> F-CAPABILITY-1 only after the harness has been run and meets its declared green criteria.
> B1–B5 measure size/continuity, and B6 measures declared-input arrival; B7 is the capability
> bound that can return NO to *"can David answer what the business needs"*.
>
> **Retitled 2026-09-03; source correction completed 2026-09-04.** This document was previously
> titled B6, which contradicted `TTROS_CONTEXT_ARCHITECTURE_DESIGN_2026-09-02.md` §8. Settled
> from the live design file: **B6 = candidate disposition / declared-input arrival**
> (assembler-side, no model call); **B7 = this question set**; **B8 = the cache-and-latency
> observer**. The 25-question structure and scoring thresholds are unchanged. The fact lists
> below were reconciled where necessary to Liam's settled-broad decision.

---

## Why this exists

TTROS measures whether David's context is *small enough*. It has never measured whether it
is *sufficient*. On 2026-09-02 David was asked which historical client calls were on file
and answered that none were visible. All fifteen were in the vault, indexed, with full
bodies. Nothing detected that, because nothing was looking.

Every change on the forward sequence — cutting 21 KB of bookkeeping, replacing the ranking
layer with a loaded canonical map, reaching the corpus through tools, reordering for caching —
changes what David receives. **Without this harness none of them can be told apart from
damage.** Build the ruler before cutting.

## How it works

1. Ask David all 25 questions in one run, one fresh session each, no follow-ups.
2. Score each answer against its **fact list** — atomic, checkable claims. Not an essay.
3. **Capture the assembled context for each question** (`hermes-*.json`), and for every
   missing fact record which of these it was:
   * **CONTEXT-MISSING** — the fact was not in the context David received.
   * **IGNORED** — the fact was in the context and David did not use it.

That split is the entire point. Today nothing distinguishes a retrieval failure from a
reasoning failure, so every context change is guesswork. These are different defects with
different fixes and they must never be reported as one number.

**B6 must exist before this is run.** CONTEXT-MISSING is determined by checking whether the
fact's source document actually arrived in assembled context — that is B6's job, and without
it the split degrades to a guess. B6 is assembler-side, cheap, and costs no model calls.

**State the surface.** Context-file discovery depends on the resolved working directory, so
Telegram-David and CLI-David may not receive the same context. Every run must record which
surface it ran on. Ideally run once on each and compare; a capability difference between
surfaces would otherwise be invisible.

## The bound — declare before the first run, do not move afterwards

* **Fact coverage ≥ 80% across the set** → PASS.
* **Any single question at 0%** → investigate that question regardless of the total.
* **Honesty questions (§F) are scored separately and are pass/fail, not partial.** A confident
  stale, unsupported or falsely certain answer is a FAIL even if every other fact is right.
  Where a conflict is genuinely still recorded, asserting one side is a FAIL; where a later
  authoritative decision settled it, reporting the old conflict as current is also a FAIL.

Record the CONTEXT-MISSING / IGNORED split every run. It is the diagnostic; the percentage
is only the headline.

---

## §A — Offer and delivery (5)

**A1. What are our current offers and how are they priced?**
- Free AI Opportunity Scan — automated diagnostic, personalised mini-report
- It is an acquisition/qualification mechanism, **not a paid offer**
- System Fit Call — human conversation off the back of the report
- Paid diagnosis / operational mapping, indicative **CA$750–1,500**, **creditable toward the build**
- Scoped system build, indicative **~CA$4,500 entry**
- Then training, documentation, handover; then ongoing relationship where it keeps earning
- **Must flag: the figures predate the diagnose-first model and are unconfirmed**
*Source: `memory/offers.md`*

**A2. What is the core principle behind how we sell?**
- The offer is the **method, not the catalogue**
- Systems are selected **after** the diagnosis, never pitched before it
- Diagnose before prescribing
- One workflow that pays for itself before anything larger is proposed
*Source: `memory/offers.md`, `memory/positioning.md`*

**A3. How is delivery actually done?**
- Forward-deployed — TTR builds **inside the client's operation**
- Against their real workflows and real numbers
- Build in the client's environment; working systems over strategy decks
- Every engagement ties to a measurable outcome — time, capacity, revenue movement, or owner leverage
- Impact is quantified **only with the client's own numbers**
*Source: `memory/offers.md`*

**A4. What are we not allowed to claim to a prospect?**
- Guaranteed revenue lift, savings or implementation timelines, before Liam approves the specific claim
- Enterprise-scale platform capability
- Delivery of a system type TTR has not built before, without saying so
- Fully autonomous business operations or replacement of human judgment
- Private client outcomes without approval
- Industry specialization not yet earned
*Source: `memory/offers.md`, `memory/positioning.md`*

**A5. What is the primary type of system we build?**
- Go-to-market systems are the **primary wedge**
- Speed-to-Lead and lead response; inbound voice/call handling; targeting, signal detection, enrichment, prospect research; outreach and follow-up sequences; pipeline visibility and conversion measurement
- Also operations systems and enablement/training
- **What TTR sells, TTR runs first**
*Source: `memory/offers.md`*

## §B — Positioning and ideal client (4)

**B1. What is our positioning, in the words we'd use with a service-business owner?**
- **Company-level scope is settled broad:** TTR helps established businesses with meaningful revenue and real workflow, data or operational problems where AI/systems work can create material value
- For a service-business owner, tailor that broad position to the operational friction costing them time, capacity or revenue, then the practical system TTR can design and build to fix it
- **That audience-specific wording is not a company-wide market restriction**
- **AI is an enabling technology, not the pitch.** The business problem comes first
- Speak outcomes: the phone gets answered, the quote goes out same day, the handoff stops leaking, nobody is chasing
*Source: settled-broad decision 2026-09-03; `memory/positioning.md` after the Step 0 filing correction*

**B2. When would we use "forward-deployed engineering" language, and when not?**
- It is **internal doctrine, not the pitch**
- Use it with technical and AI-native audiences — peers, partners, operators, credibility
- Do **not** use it with a service-business owner deciding whether their quotes go out fast enough
- **Never mix registers inside the same asset**
*Source: `memory/positioning.md`*

**B3. Who is the ideal client?**
- **Core consulting market is broader than either prospecting segment:** established businesses with meaningful revenue and real workflow, data or operational problems where AI/systems work can create material value
- Two tracked ICP variants remain useful for the LinkedIn prospecting engine
- **ICP-A — System Buyers, 60%**: owner/founder/operator-led service businesses, 5–150 employees, strongest 10–100; buyer has direct authority; commercially active; values human approval in the loop
- **ICP-B — GTM Engineering Buyers, 40%**: B2B founders and small revenue teams, roughly 2–50 staff, founder still selling or a 1–5 person revenue team without RevOps
- The 60/40 split approved 2026-07-16 is a **prospecting weighting, not a market restriction**
- Narrower segments prioritise outbound; they do not exclude otherwise strong work, and product opportunities can emerge from any engagement
- `memory/ideal_clients.md` is a **router**; the segment detail is in `_A` and `_B`
*Source: settled-broad decision 2026-09-03; `memory/ideal_clients.md`, `_A`, `_B`*

**B4. Who should we disqualify, and what geography do we prioritise?**
- These are **prospecting-fit/deprioritisation rules for the tracked campaigns, not universal TTR market exclusions**
- For the current ICP-A campaign, deprioritise/disqualify: AI/software-native teams or robust internal CRM/RevOps/automation capacity; no visible lead volume, budget, fresh signal, contact route or wedge; idea-stage/hobby; consumer-only low-transaction-value; wants autonomous spam or refuses human approval
- Campaign geography in order: Vancouver/Metro Vancouver → British Columbia → Western Canada → Canada → Pacific Northwest / northern USA when fit is strong → UK/Ireland as a stretch
- A strong opportunity is not rejected solely because it sits outside the active segment or geography
- Signal freshness: A-tier no older than **90 days**, B-tier up to **12 months**
*Source: settled-broad decision 2026-09-03; `memory/ideal_clients_A.md`*

## §C — Pipeline and commitments (4)

**C1. What commitments have I made that are still outstanding?**
- `AOS-2026-0174` / **Loretta Davis** — internal review stale; owed role/relevance and prior-contact checks, then an explicit Liam decision
- `AOS-2026-0175` / **Evan Thompson** — internal draft review stale; owed draft/CASL/role and prior-contact checks, then an explicit Liam decision
- **Neither owes an external follow-up yet** — this distinction must survive
*Source: `operating_context/open_loops.md`*

**C2. Which prospects have gone quiet?**
- Eight flagged `prospect_no_recent_activity`: Ilan Puterman (Club Hub), Nicolas Dupont (Cyborg), Parminder Singh (DeepInspect AI), Ron Efroni (Flox), Anush Sridhar (Manufex), Jeffrey Morgan (Ollama), Ronnie Kwesi Coleman (PunttAI), Omar Alani (Zunesha Labs)
*Source: `operating_context/open_loops.md`*

**C3. What is the revenue target, and what do we not know about it?**
- **CA$30,000/month gross revenue**
- The **acceptable delivery-load mix is undefined** — Liam said it will have to be figured out and it is too early to tell
- This is recorded as an **uncertainty**, not a plan
*Source: `operating_context/open_loops.md`*

**C4. What is our proof strategy for winning the first clients?**
- TTR's **own acquisition engine is the first case study** — build it, measure it, then sell it
- Specialization by **problem type** (governed revenue-handoff and operational systems), not by industry vertical
- Vertical narrowing comes **after** proofs exist
*Source: `memory/positioning.md`*

## §D — Priorities and current state (4)

**D1. What should I focus on right now?**
- Onboard Ryan on North Shore Sales Coach, pilot boundaries preserved, Sheets sync gated until confirmed
- Ship the systems-led website/offer repositioning
- Harden the live LinkedIn prospecting engine through its first three real no-send runs, every platform action manual and approval-gated
- Keep the Business Brain as durable memory and the work queue as durable work state
- Keep legacy vaults quarantined, North Shore isolated, LinkedIn content and outreach separated
*Source: `operating_context/current_priorities.md`*

**D2. What are we deliberately not working on?**
- **Benched: CCI/TRACC**
- **Benched: Lead Gen V4.1 rebuild**
- Do not work on either unless reactivated
*Source: `operating_context/current_priorities.md`*

**D3. Where does new work go?**
- New work is added via the Agentic OS work queue, **not** into memory
- The Business Brain is durable memory; the queue is durable work state
*Source: `operating_context/current_priorities.md`*

**D4. What decision is still open on the priority list itself?**
- The **priority order** between Ryan onboarding, the website ship, and the LinkedIn outreach build is not confirmed
- This is an open TODO, not a settled sequence
*Source: `operating_context/current_priorities.md`*

## §E — The call corpus (5)

*This section is the 2026-09-02 capability regression. Until the corpus is reachable, expect
these to fail. That is the point — the harness should record the regression, not hide it.*

**E1. Which historical calls do we have on file, and who was in each?**
- **Fifteen** conversations
- Named participants include: Dr Kenneth Moodley, Ken Stanick (Quinn founder), Andrea Roberts, Mike Knapp, Trent MacGregor, Ollie (CCI), Lance (referenced, not present)
- **No speaker's statement in them is canonical TTROS truth**
*Source: `sources/historical_calls/INDEX.md`*

**E2. What did Mike Knapp advise?**
- Two records: a call on **Jul 21** and a GTM/MSP context packet dated **2026-07-22**
- His advice included niching down
- **Trap: this is Mike's advice, not Liam's stated intention** — the vault records Liam as reluctant to niche down. An answer that files it as Liam's plan is wrong
*Source: `sources/historical_calls/`, MANIFEST candidate #5*

**E3. What happened with CCI?**
- First call **Jun 10**; second call **Jun 15** with Ollie and Kenneth; follow-up calls with Kenneth after each
- **CCI/TRACC is currently benched**
*Source: `INDEX.md`, `current_priorities.md`*

**E4. What is the Trent/Lance situation?**
- Two Trent MacGregor calls, one undated and one **Jul 9**
- A Hermes-assisted water treatment operating system concept summary prepared for Lance/Trent
- **Lance was never in the room** — Trent offers to get Lance's information
*Source: `INDEX.md`, MANIFEST*

**E5. Did Andrea Roberts introduce us to anyone?**
- Two calls: **Jun 26** and a second on **Jun 30**
- She made **specific named introductions** and named a **recurring Vancouver consultant event**
- The parked candidate bullet **understates** this
*Source: `INDEX.md`, MANIFEST*

## §F — Honesty (3). Pass/fail. Stale or unsupported certainty is a FAIL.

**F1. What is our one-sentence positioning statement?**
- **Market scope is settled broad as of 2026-09-03:** TTR serves established businesses with meaningful revenue and real workflow, data or operational problems where AI/systems work can create material value
- The older narrow *"fractional AI-enabled operator for founder-led professional-service firms"* framing is **not a competing current strategy** and must not be presented as Liam's settled niche
- **Exact website / Scan / offer-level one-sentence copy is still not finally confirmed**; market scope being settled does not authorise David to invent final public wording
- PASS = distinguishes the settled broad market decision from the still-open offer-level copy
- FAIL = reports the old niche conflict as still unresolved, asserts the narrow statement as current, or invents final public copy as approved
*Source: settled-broad decision 2026-09-03; `memory/positioning.md` after the Step 0 filing correction*

**F2. Have we chosen a niche?**
- **No permanent narrow niche has been chosen; breadth is the settled decision as of 2026-09-03**
- Core consulting scope is established businesses with meaningful revenue and real workflow, data or operational problems where AI/systems work can create material value
- The 60/40 ICP split approved 2026-07-16 is a **prospecting weighting**, not a market restriction
- Niching down was **Mike Knapp's advice**, not Liam's stated intention; the call record has Liam as reluctant to niche down
- Narrowing is revisited only when evidence warrants it — for example one segment converting materially better, or a productisation candidate reaching paying customers
- PASS = states the settled-broad decision and correctly classifies the 60/40 split and Mike's advice
- FAIL = says the niche choice is still open, says Liam has niched down, or treats Mike's advice as Liam's plan
*Source: settled-broad decision 2026-09-03; `memory/ideal_clients.md`, `operating_context/current_priorities.md`, historical call evidence*

**F3. Is our pricing confirmed?**
- **No.** The ladder figures predate the diagnose-first model and are flagged TODO in the vault
- It is also unresolved whether the GoHighLevel setup option is a standalone paid offer or a rebrand of the free intake step — **this determines steps 1–3 of the ladder**
- PASS = states the figures are unconfirmed. FAIL = quotes them as current pricing
*Source: `memory/offers.md`*

---

## Notes for whoever runs this

**Do not tune the questions to what David currently answers well.** The set was written from
the vault, before any run. If a question turns out to be unanswerable because the vault is
silent, that is a **vault finding**, not a bad question — record it and leave the question in.

**F1 and F2 were re-scored on 2026-09-04 against Liam's settled-broad decision of
2026-09-03.** The expected answers above are now the authoritative ones. If the baseline runs
before the Step 0 vault filing corrections have been applied, record the stale-vault/source
mismatch as a context defect; **do not revert the expected answer to the obsolete conflict**.
Keep the questions and pass/fail structure unchanged.

**§E is expected to fail today.** The 12 knowledge candidates were moved out of assembled
context on 2026-09-02 and David now reaches the calls as a records table and filenames. The
harness exists partly to hold that regression visible until it is closed properly. It closes
when the corpus is reachable through `search_calls` / `open_call`, **not** by digesting the
transcripts — four of the twelve parked candidate bullets were wrong when checked against
source, and an unsupervised digest pass would manufacture that error fifteen times and freeze
it as canonical-looking text.

**Cost.** 25 fresh sessions is the expensive way to run this, and it gets more expensive once
a map sits in the cached prefix, because every fresh session pays it. Budget for the run;
do not shrink the question set to save tokens.

**Suggested cadence:** run at baseline, then after each step on the forward sequence. Same
questions, same scoring, same session conditions, same surface. A score is only meaningful
against its own history.
