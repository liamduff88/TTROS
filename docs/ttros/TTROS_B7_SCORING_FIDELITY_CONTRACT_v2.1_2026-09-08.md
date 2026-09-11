# TTROS B7 Scoring + Fidelity Contract v2.1

**Date:** 2026-09-08
**Supersedes:** v1 and v2 (same date). Both are development material. **File only this document** —
two revisions of the same contract in the canonical set is a stop condition.
**Status:** Design contract. Writing only. No scorer implementation is authorized by this document.
**Zero model calls were made to produce it.**

---

## 1. Purpose

B7 exists to answer one question:

> **Can David faithfully answer what the business needs?**

The frozen B7 fact descriptions are the specification. The scorer is an implementation of that
specification. The scorer does not define what a fact means.

The objective of the repair is not to raise or lower historical scores. It is to make mechanical
scoring agree, as closely as is practical and deterministic, with the meaning already frozen in
the fact descriptions.

---

## 2. What this contract does not change

Unchanged: the 25 questions; the frozen fact descriptions; the question and section structure;
the B6/B7 distinction; the requirement to record CONTEXT-MISSING / IGNORED / UNDECIDABLE via B6;
the declared green threshold; the 0%-question investigation clause; the separate pass/fail
treatment of §F; the authoritative sources named by the frozen harness.

Bounds in force, unchanged:

* overall fact coverage **≥80% = PASS**;
* any individual question at **0% = investigate, regardless of total**;
* **§F honesty is PASS/FAIL, never partial.**

This work repairs the ruler. It does not move the marks on the ruler.

---

## 3. Evidence basis

Executable verification of all 99 non-honesty fact predicates against the real frozen `present()`
found:

| Classification | Count |
|---|---:|
| ALIGNED | 51 |
| UNDER-SPECIFIED | 45 |
| OVER-SPECIFIED | 0 |
| TEXT-NORMALIZATION defect | 2 |
| OTHER / source-contract mismatch | 1 |

Four demonstrated defect patterns inside the 45: list collapse (10 facts); near-universal /
disconnected keyword matching (5); dropped qualifier, name or secondary clause (24);
polarity / negation blindness (4). Facts may show more than one pattern.

A separate zero-model test proved the same polarity blindness in **all three §F honesty
questions**, in the opposite direction — see §12.

**A fifth piece of evidence, found independently.** During the U-CLOSE tool-surface verification, a
first-draft contamination detector built from harness fact-description prose and scorer `kw()`
literals produced 29 false positives against ordinary vault content in `memory/offers.md` and
`memory/positioning.md`. That is an independent mechanical demonstration that **the harness's
keyword vocabulary and the vault's real business vocabulary overlap heavily.** It is the mechanism
behind the 45: keyword sets drawn from fact-description prose will match legitimate business text
that does not assert the fact. Two unrelated instruments, from opposite directions, found the same
thing.

**This contract is not permission to rewrite all 99 predicates into a new framework.** The
structural finding that the machinery is assertion-blind must inform fidelity evaluation, but
implementation stays bounded to demonstrated or explicitly validated cases.

---

## 4. Governing fidelity principle

A fact passes only when David's answer communicates the **material meaning required by the frozen
fact description**.

Keyword occurrence is evidence of meaning. Keyword occurrence is not, by itself, proof of meaning.

The scorer must not award a fact where the matching text sits inside an answer whose material
meaning is incomplete, reversed, stale, misattributed, or otherwise inconsistent with the frozen
fact. Equally, a materially correct answer must not fail over an irrelevant difference of textual
representation.

**Both directions are live defects.** The 99 non-honesty facts fail by over-crediting; §F fails by
over-blaming. A repair that only tightens is only half a repair.

---

## 5. Scoring and fidelity vocabulary

Nine terms.

### 5.1 Normalization

Change of representation without change of semantic content: straight vs typographic apostrophes,
Unicode-equivalent punctuation, hyphen vs space where written meaning is unchanged, case,
harmless whitespace.

Normalization must never insert a missing fact, change a number, change polarity, change
attribution, change current/historical status, convert one business concept into another, or
supply a missing qualifier.

`B4.5` and `E2.4` remain explicit policy decisions (§8). This section defines what normalization
*is*; it does not decide those two.

### 5.2 List coverage

Applies where a frozen fact describes multiple distinct items as one fact.

A mechanical OR across a list is faithful only where the frozen fact genuinely defines those
members as alternatives. Where it does not, the coverage rule must be derived from the fact
description — required named elements, an N-of-M threshold, or essential elements plus optional
examples.

The threshold comes from the fact's intended meaning, never from whichever rule produces the
preferred historical score. **No threshold is selected here.**

### 5.3 Essential / composite qualifiers

A qualifier is **essential** when removing it materially changes what the frozen fact says.

Recurring essential classes: free vs paid; confirmed vs unconfirmed; current vs historical;
internal vs external; advice vs intention; broad market vs prospecting segment; allowed vs
prohibited; active vs benched; named actor; exception or limitation language; declared
uncertainty; sequence where sequence is part of the claim.

Mentioning the main noun or activity does not establish a composite fact when a material
qualifier is absent. The repair encodes only qualifiers actually required by each affected frozen
fact, and adds no requirement absent from the harness.

### 5.4 Attribution

Who said, decided, advised, intended, did, or owns the proposition.

*Mike Knapp advised niching down* and *Liam decided to niche down* are different facts. *A third
party said X* and *TTROS treats X as canonical business truth* are different claims. An answer
does not pass an attribution-sensitive fact by containing the proposition while assigning it to
the wrong actor.

### 5.5 Polarity / assertion

Distinguishes asserting X; denying X; stating not-X; quoting X without adopting it; describing X
as an obsolete view; stating uncertainty about X.

A positive keyword inside a denial is not evidence the positive claim was asserted. *"We do not do
X"* must not satisfy a fact requiring *"we do X"* because the words for X occur in both.

The fidelity detector must evaluate polarity. The deterministic scorer mechanism, and the bounded
set of predicates it is applied to, are decided after the withheld evaluation (§6, §8).

**This contract does not authorize a general natural-language understanding engine inside B7.**

### 5.6 Temporal / status validity

Current vs historical; settled vs open; confirmed vs provisional; active vs benched; outstanding
vs completed; stale internal review vs external follow-up owed; an old position vs a later
authoritative decision.

A historically accurate statement cannot satisfy a current-state fact where the frozen fact
requires the later state. An answer calling a settled decision "still unresolved" is not faithful
merely because the conflict once existed.

### 5.7 Prohibited opposites

A statement whose meaning materially contradicts the frozen fact.

Where both positive keywords and a prohibited opposite occur, the positive hit must not
automatically win. Conceptual pairs include confirmed/unconfirmed, chosen narrow niche/settled
broad scope, Liam's plan/another's advice, active/benched, external follow-up owed/not owed.

Rules are derived fact by fact from the frozen harness, never generated from a generic antonym
list.

### 5.8 Locality

The frozen `present()` matches substrings anywhere in an answer with **no proximity, ordering, or
co-reference requirement.** Two generic words satisfying a fact from opposite ends of a long
answer, attached to different subjects, is the disconnected-keyword defect
(`A4.1, B1.3, B2.3, B4.1, D4.2`).

Locality is a distinct failure from list coverage and from dropped qualifiers, and needs its own
rule: where a fact requires two or more elements to be *about the same thing*, the scorer must
require them to co-occur within a bounded span, or within the same sentence or clause, rather than
anywhere in the answer.

The §3 vocabulary-overlap finding makes this the highest-value single change: generic business
words drawn from fact-description prose are exactly the words a legitimate answer will contain
incidentally.

### 5.9 Source-contract defect

A frozen fact that cannot fairly test retrieval capability under the system's intended
source-access contract. Must be reported separately from CONTEXT-MISSING, IGNORED, and ordinary
scorer failure.

`E5.4` is confirmed in this class: its content lives in a `historical_source`-typed candidate
excluded from assembled context by the F-BRAINNOTES-1 filter **by design**, and is not among E5's
own declared `source_docs`. No retrieval capability can produce it as specified.

This contract does not decide whether E5.4 is redefined, retired, or made legitimately reachable
(§8). Until decided it stays visibly classified as a source-contract issue and is never reported
as a David retrieval failure.

---

## 6. Validation — what the 12-item set can and cannot prove

The 12-item historical-call set is twelve *candidate memory bullets derived from call sources*,
labelled against those sources (≈8 supported, ≈4 needing correction). Its items are
**(candidate claim, source document)** pairs. It measures **source → canonical fidelity**.

The B7 scorer operates on **(frozen fact, David's answer)** pairs. That is **answer → fact
fidelity** — a different chain.

The two chains share the five error types — attribution, scope, qualification, polarity, status —
which is why the set is worth using. **The vocabulary transfers; the input contract does not.** So
the validation splits in two.

### 6.1 Validation A — the 12-item set validates the vocabulary

**Inputs per item:** the candidate claim, and the source document it was derived from. Nothing
else. Not the human label. Not the prior audit's verdict.

**Outputs per item:**

* verdict — `SUPPORTED` / `NOT SUPPORTED`;
* zero or more reason tags — `normalization`, `list_coverage`, `essential_qualifier`,
  `attribution`, `polarity_assertion`, `temporal_status`, `prohibited_opposite`, `locality`,
  `source_contract`;
* evidence — the minimum span or proposition that caused the judgment.

**Declared threshold, fixed before the run and never moved:**

1. verdict agreement with the withheld human labels on **≥10 of 12**; **and**
2. on the ~4 known-unsupported items, a reason tag matching the human's named error type on
   **≥3 of them**.

Clause 2 is not decoration. The set is roughly 8 supported / 4 not, so a detector that answers
`SUPPORTED` every time scores 8/12 on clause 1 alone while proving nothing. Clause 2 is what makes
the run capable of failing.

**If either clause misses, the category vocabulary in §5 is wrong** and is revised before any
scorer rule is written. That is the result this run exists to be able to produce.

**What a pass licenses:** that the nine categories correctly name real distortions in TTROS
material. **What it does not license:** that any specific scorer rule is correct. That is
Validation B.

### 6.2 Validation B — the flip review validates the scorer rules

1. Freeze the proposed rules and record their SHA-256 **before** the re-score (§6.3).
2. Re-score `step6_post` under the old frozen scorer and the new rules, both deterministic, zero
   model calls.
3. Every fact whose result **flips** — and only those — is the review population.
4. Liam adjudicates each flip once against the frozen fact description: *correct flip* or
   *wrong flip*.
5. Wrong flips identify defective rules.

**What Validation B proves, stated precisely:** it validates the *effects introduced by the
repaired rules*, not the absolute correctness of the whole 99-fact scorer. That is sufficient here
because all 99 predicates have already been mechanically audited and the repair population is
known and bounded.

**Anti-tuning bound.** Adjudication may reject or narrow a rule. It may not silently retune one.
Any rule revised after seeing flips opens a declared second round: the revision, its reason, its
predicted effect, and a fresh hash, all recorded before the re-score is repeated. **Two rounds
maximum.** A third round is a signal that the rule set is wrong, not that it needs more iterations.

### 6.3 Freezing, and how freezing is proven

"The detector was frozen before the labels were revealed" is unverifiable unless it is recorded.
Before Validation A's single run, record the SHA-256 of the detector and of any prompt or rule
file it reads, in the transcript. Same for the rule set before Validation B. A claim of no tuning
without a pre-recorded hash is an assertion, not evidence.

### 6.4 Model-call budget

Validation A may be deterministic or model-assisted; that is an implementation choice.

* **If model-assisted:** hard cap **20 calls** total, covering 12 items plus rehearsal. The
  instrument counts its own calls, hard-stops at the cap, exits with an error rather than
  exceeding it, and writes the actual count against the declared cap into its transcript. A budget
  stated only in a prompt is not a budget.
* **Validation B is zero model calls** — deterministic scoring over stored answers.
* **The §13 step 2 prerequisite pass is zero model calls.**
* **No B7 pass is run anywhere in this contract.** The next B7 spend is the two-pass clean
  baseline at §13 step 9, separately authorized.

### 6.5 The repaired scorer stays deterministic

The scorer itself remains **deterministic, reproducible, and zero-model-call**, as the frozen
scorer is today. Every audit that got TTROS here depended on being able to re-run the scorer over
stored answers for free.

The fidelity detector may use judgment. Its role is to help *design* deterministic rules. It never
becomes the scorer. A B7 whose scoring requires a model call is not re-runnable, not free to
audit, and not comparable across passes.

---

## 7. Repair population

**UNDER-SPECIFIED (45):**
`A1.1, A1.2, A1.3, A1.4, A1.5, A1.6, A2.2, A4.1, A4.2, A4.5, A5.1, A5.2, A5.3, B1.2, B1.3, B1.5,
B2.2, B2.3, B3.1, B3.2, B3.3, B3.4, B3.5, B4.1, B4.2, B4.3, C1.1, C1.2, C1.3, C4.1, C4.2, C4.3,
D1.1, D1.4, D1.5, D2.3, D3.1, D4.1, D4.2, E2.3, E3.2, E4.1, E4.3, E5.2, E5.3`

**TEXT-NORMALIZATION (2):** `B4.5` (latent), `E2.4` (live).

**SOURCE-CONTRACT / OTHER (1):** `E5.4`.

### 7.1 Two facts are unclassified

The four named sub-patterns cover 43 of the 45. **`B1.2` and `B3.1` appear in the
UNDER-SPECIFIED list and in none of the four sub-pattern breakdowns.**

Nobody has recorded what is wrong with them. They cannot be repaired against an unnamed defect,
and they must not be quietly dropped from the denominator (§11). Before the repair, each is
classified into an existing category or given a named new one — a one-line finding per fact, zero
model calls, read directly off the frozen predicate. This is part of the §13 step 2 prerequisite
pass.

### 7.2 Expansion rule

An ALIGNED rule is not rewritten for consistency or elegance. If the fidelity work produces
concrete evidence that an apparently aligned rule is semantically defective — most plausibly
through polarity or locality — that specific rule joins the repair population. Evidence-based
expansion; not permission to rebuild 99.

§F honesty predicates are checked against this contract in both directions (§12).

---

## 8. Eight policy decisions reserved for Liam

The dropped-qualifier class is 24 of the 45 under-specified facts — more than list collapse,
disconnected keywords and polarity combined — and determining which qualifiers are essential is
the single most judgment-heavy call in the repair. It is decision 3.

1. **List-collapse threshold** — the 10 named list facts.
2. **Locality rule** — the 5 named disconnected-keyword facts. Span, sentence, or clause.
3. **Essential-qualifier standard** — the 24 dropped-qualifier facts. Which qualifier classes are
   material, and whether the standard is uniform or per fact.
4. **Scope and mechanism of polarity/assertion protection**, for the 99 and for §F.
5. **`E5.4` disposition** — redefine, retire, or make its source legitimately reachable.
6. **`B4.5` normalization** — hyphen/space.
7. **`E2.4` normalization** — typographic/straight apostrophe.
8. **Historical-baseline citability, including whether Step 5's closure stands.**
   **DECIDED AND RECORDED 2026-09-08 — see §15.** Decisions 1–7 remain open.

Before deciding each of 1–7, Liam records: the decision considered; the predicted direction of
score impact; the approximate number of facts and passes affected; and the reason derived from the
frozen fact's meaning.

Only after that prediction is fixed is the actual impact measured. This is what stops scorer
policy from being tuned retrospectively toward a preferred B7 result.

Decisions 1–3 are stated at the level of *fact class*, not per individual fact, unless a specific
fact genuinely diverges. Twenty-four separate rulings is the governance exercise this project does
not need.

---

## 9. Declared prediction before the re-score

**Predicted, and fixed now — a prediction, not an established result.** Every known defect class in
the 99 inflates the score; approximately three facts deflate it. Therefore:

> **Prediction P1:** the repair will lower `step6_post`'s §A–D coverage from its current 44–49%.
> **Prediction P2:** the true clean §A–D figure is **below 44%**.

P1 and P2 are predictions recorded before measurement. **Neither becomes an established result
until the repaired scorer has actually been run** (§13 step 8). Until then they are cited as
predictions and nothing is built on them as fact.

Consequences of holding them:

* A repair that **raises** coverage falsifies P1 and is a finding requiring explanation before it
  is accepted — the most likely explanation being that a rule was loosened rather than corrected.
* A lower number after repair is **not** evidence the repair went too far, and is not grounds for
  softening a rule. §A–D already sits at roughly half the declared ≥80% bound on the only clean
  pass, and **the bound failure is robust to every scoring decision in §8.** No combination of
  decisions 1–7 moves 44–49% to 80%.

**Separately:** the re-score must report per-question coverage, not only the total. The 0%-question
investigation clause has never fired in any pass. Whether that is because no question ever scored
0%, or because the clause was never evaluated, is unrecorded. The re-score settles it as a
by-product at no extra cost.

---

## 10. Historical baseline, and the two-pass requirement

Distinguish **answer-corpus usability** from **score-baseline validity**.

Contaminated Step 3 / Step 5 passes are not clean capability measurements and do not become clean
through scorer repair.

U-CLOSE established `step6_post` as the contamination-clean historical **answer corpus** —
verified on its full enumerated 7-tool, 46-call surface, on both the argument and the
returned-output side, at 100% output-retention coverage. That makes its answers usable for scorer
development. It does **not** make its old percentage trustworthy under a defective scorer.

Therefore: develop against `step6_post` answers; never optimize rules to reproduce its old score;
re-score it after the bounded repair; treat that as a repaired historical measurement.

### 10.1 The fresh baseline is two passes, not one

Rev11 defines B7's repeatability rule from **two independent complete passes**: the baseline anchor
is the lower of the two totals (and the lower value per question); the noise ceiling is a
two-pass total spread greater than 10 percentage points; and the **B7 noise allowance** — the one
number used everywhere B7 acts as a decision threshold — is the greater of the measured spread or
4 percentage points.

**Spread cannot be measured from a single pass.** A one-pass baseline therefore cannot produce a
noise allowance, and rev11 states plainly that without measured repeatability B7 cannot size Step
5, decide Step 7, or gate Step 9.

The existing allowance is also **derived from contaminated evidence**: Step 3's two passes are both
contaminated. Their agreement is not evidence of a quiet instrument — if both passes were reading
the same answer key, close agreement is what contamination would produce. The current allowance is
therefore not usable as a clean gate.

**So:** the fresh baseline is **two mechanically identical clean B7 passes**, same model, same
declared surface, same frozen questions and fact lists, same repaired scorer, fresh sessions each.
Anchor, spread and noise allowance are derived **only after both passes complete**, and are
declared before either runs. The pair is predicted in writing beforehand and is **not** compared to
step3, step5 or step6 — different scorer, different conditions, different instrument.

---

## 11. Anti-overfitting rules

The repair must not: rewrite a frozen fact because David answered it differently; add synonyms
because one historical answer used them; weaken requirements to raise coverage; strengthen
requirements to lower a suspiciously high score; tune against the 12 after labels are revealed;
treat `step6_post`'s existing score as a target; change B7 thresholds to accommodate the repaired
scorer; change B6 disposition to compensate for scorer behaviour; or silently alter the
denominator by dropping difficult facts — including `B1.2`, `B3.1` and `E5.4`.

Every repaired rule traces to: (1) a frozen fact description; (2) a demonstrated scorer or
fidelity defect; (3) an explicit Liam policy decision where judgment is required.

---

## 12. §F honesty — both directions

§F detects confident stale, unsupported, or falsely certain answers. Semantic fidelity takes
precedence over keyword presence. §F stays PASS/FAIL; no partial credit is created here.

**Direction 1 — over-blaming. This is the proven defect.** All three §F questions are reproducibly
polarity-blind in their `fail_if` clauses: the scorer penalises the answers it was designed to
reward, because an honest answer must *name* the false claim in order to reject it, and the
substring matcher cannot tell **use** from **mention**.

> A §F answer must not FAIL because it quotes, names, or restates the claim it is explicitly
> rejecting, correcting, or flagging as uncertain.

This is the §F repair. Every other §F change is secondary to it.

**Direction 2 — over-crediting.** A confident semantic opposite FAILS however many expected
keywords it contains. Required distinctions: settled vs unresolved; broad market vs narrow niche;
advice vs Liam's intention; confirmed vs unconfirmed pricing; approved public wording vs still-open
copy.

Because both directions run through the same `present()` machinery, a §F fix that only addresses
direction 2 will make the proven defect worse.

---

## 13. Sequence after this contract

1. Freeze this contract; record its SHA-256.

2. **Prerequisite pass — zero model calls.** Three items, one session:
   * classify `B1.2` and `B3.1` against the frozen predicates (§7.1);
   * **run the repaired three-way B6 disposition over `step6_post`'s stored records**, using the
     available provenance and actual-read evidence, and report CONTEXT-MISSING / IGNORED /
     UNDECIDABLE per unmet fact;
   * **record that B6 run as the missing Step 5 investigation** (§15).

   The B6 disposition has never functioned across any of the 125 records, so it has never been
   established whether a low §A–D figure means the facts did not arrive or means David did not use
   them. Rev11's own Step 3 prediction was *"CONTEXT-MISSING dominant."* If that holds, the scorer
   repair is aimed at the smaller of the two defects, and that is worth knowing before decisions
   1–7 are made.

3. Build the fidelity detector to §6.1; record its hash; labels withheld.
4. Run Validation A once. Reveal labels. Compare against the §6.1 threshold.
5. If the threshold misses, revise §5's categories before proceeding. If it holds, continue.
6. Liam makes decisions 1–7 (§8), recording predicted impact before measurement.
7. One bounded scorer repair. Record the rule-set hash.
8. Re-score `step6_post`; run Validation B's flip review; report per-question coverage. P1 and P2
   (§9) resolve here.
9. **Two mechanically identical clean B7 passes** (§10.1). Predicted in writing beforehand. Derive
   anchor, spread and noise allowance only after both complete.
10. If B7 is good enough, stop scorer work and resume the rev11 build.
11. Only once trustworthy measurement exists, decide the open memory-architecture question —
    including whether David keeps Hermes native memory enabled.

### 13.1 Step 6b remains blocked

Rev11: *"Step 6b — Delete the obsolete retrieval machinery. Only after Steps 5 and 6 are both
green."*

Step 6 is RED. Step 5 is now recorded as **CAPABILITY BOUND UNRESOLVED** (§15). **Step 6b is
therefore blocked on both, and stays blocked until each is genuinely green under repaired B6 and
repaired B7 evidence** — not under the historical figures, and not under a scorer since shown
defective. Recording Step 5's true status is correct, and it is not free: it adds a second gate in
front of 6b that did not appear to be there yesterday.

No broad scorer rebuild. No new audit cycle. No B7 before the scorer policy is settled.

---

## 14. Acceptance criteria

This contract is complete when it is agreed that:

* frozen B7 facts remain the source of scoring meaning, and thresholds are unchanged;
* meaning, not keyword occurrence alone, is the fidelity target, **in both directions**;
* normalization is separated from substantive meaning;
* list coverage, locality, qualifiers, attribution, assertion, temporal status and prohibited
  opposites are each handled explicitly;
* source-contract defects are never misreported as retrieval failures;
* the repair stays bounded to demonstrated defects, and `B1.2`/`B3.1` are classified rather than
  dropped;
* decisions 1–7 remain explicit, predicted-before-measured, and untuned; decision 8 is recorded
  in §15;
* Validation A carries a declared falsifiability threshold with a clause that defeats the
  degenerate always-`SUPPORTED` detector;
* Validation B is understood to validate the repair's effects, not the whole scorer;
* freezing is proven by recorded hash, not asserted;
* the repaired scorer remains deterministic and zero-model-call;
* `step6_post` is an answer corpus for repair, never a score target;
* P1 and P2 stand as predictions until §13 step 8 resolves them;
* the fresh baseline is two passes, and no noise allowance is derived from one.

---

## 15. Decision 8 — recorded 2026-09-08

**Status label, recorded now:**

> **STEP 5 — IMPLEMENTATION COMPLETE / CAPABILITY BOUND UNRESOLVED — INVESTIGATION REQUIRED.**

**Reason.** Rev11's Step 5 bound reads: *"B7 coverage on offers/positioning/pipeline/priorities
≥80%, or investigate."* Measured §A–D coverage was 49.3% (Step 3 pass A), 49.3% (Step 3 pass B),
46.7% (Step 5 closing pass), 44.0% (Step 6 pre) and 44.0% (`step6_post`). There is no record that
the required investigation was performed when Step 5 was closed. It could not have been performed
correctly in any case, because **B6's disposition was broken** — the `sources` key never emitted
across any of the 125 records, so the CONTEXT-MISSING / IGNORED split that the investigation
depends on had never once functioned.

The map-growth terminator that did fire during Step 5 was a different rule. It governed when to
stop adding map classes. **It did not waive the ≥80%-or-investigate capability bound.**

**What this label does and does not say.**

* It does **not** say the map implementation is broken, and it does not call for a revert. The Step
  5 build is complete and stands.
* It does **not** say the capability bound was breached and waived. It says the acceptance
  condition was **never evaluated**.
* It does say Step 5 is not a green capability closure and cannot be cited as one.

**Why this is safe to record before the scorer repair.** Predictions P1 and P2 (§9) hold that every
known defect class inflates the score, so repairing the scorer cannot plausibly raise 44–49% to
≥80% and is expected to lower it. The bound failure is therefore robust to all of decisions 1–7.
Recording the status now does not depend on the repair's outcome and does not pre-empt it.

**The investigation this label requires** is the §13 step 2 B6 disposition run over `step6_post`.
That run, and nothing else, discharges what Step 5 owed. Its result determines whether the low
§A–D figure is a retrieval failure or a reasoning failure — which are different defects with
different fixes, and which B7 exists to keep apart.

---

## Governing sentence

> **A B7 fact passes when David faithfully communicates the material meaning of the frozen fact
> description; it fails when the answer contains only matching words while materially omitting,
> reversing, misattributing or misstating that meaning — and it must not fail merely because the
> answer names the claim it is rejecting.**

---

## Appendix — revision history

**v2 → v2.1 (six folded changes, no other redesign):**

1. §15 added — Decision 8 recorded with the status label above.
2. §13 step 2 — new zero-model-call prerequisite pass: classify `B1.2`/`B3.1`, run repaired
   three-way B6 disposition over `step6_post`, record it as the missing Step 5 investigation.
3. §9 — P1 and P2 stated as predeclared predictions, explicitly not established results until
   §13 step 8.
4. §10.1 — fresh baseline changed from one pass to two mechanically identical clean passes, with
   the reason: rev11's noise allowance is defined from two-pass spread, and the existing allowance
   is derived from two contaminated passes.
5. §13.1 — Step 6b explicitly blocked until Steps 5 and 6 are both green under repaired B6/B7
   evidence.
6. §8 — decision 8 marked recorded; 1–7 remain open.

**v1 → v2:** corrected the 12-item set's input contract and split validation in two; added a
falsifiability threshold with a degenerate-detector guard; required freezing by recorded hash;
added a model-call budget; required the repaired scorer to stay deterministic and zero-model-call;
raised the reserved decisions from seven to eight by adding the 24-fact essential-qualifier class;
added locality as a vocabulary term; identified `B1.2` and `B3.1` as unclassified; added the
declared pre-repair prediction and the per-question 0%-clause check; corrected §F to address
over-blaming as the proven defect; recorded the 29-false-positive vocabulary-overlap finding.
