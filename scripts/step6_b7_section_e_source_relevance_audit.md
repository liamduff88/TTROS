# Step 6 — B7 §E source-document relevance and provenance audit

ZERO David/Hermes/model calls made. B7 harness unchanged. No scores changed. No
scoring re-run. No production file touched. Inputs: every §E source document
read in full from the live vault
(`/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain/`),
`sources/historical_calls/INDEX.md`, `sources/historical_calls/MANIFEST.md`,
`operating_context/current_priorities.md`, `operating_context/open_loops.md`,
the frozen fact list in `scripts/step3_b7_harness.py` (`QUESTIONS[...]`,
section E, read-only), the human-readable question sheet
`docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`
(mirror hash verified against `docs/ttros/SOURCE.sha256` before use), and
`scripts/step6_zero_model_diagnosis.md`.

---

## 1. Executive finding

§E's 24 atomic facts are **mostly sound but not uniformly trustworthy**. Of
the 24: **20 are CORE** (genuinely important, well-grounded), **2 are USEFUL**
(supported but non-essential), **1 is METADATA-ONLY** (the tested date exists
only in a filename / import metadata, not in the transcript body the question
is nominally testing), and **1 is UNSUPPORTED** (its comparison target — a
"parked candidate bullet" in `MANIFEST.md` — is a document the context
assembler deliberately excludes from what David ever receives, and it is not
even listed among that question's own declared source documents).

That is a small number of facts, but they are not evenly distributed: they
cluster in exactly the two hardest-hit questions in the fresh Step 6 pass —
**E4** (1 of 3 facts METADATA-ONLY) and **E5** (1 of 4 facts UNSUPPORTED,
plus a second fact, E5.3, whose two required literal keywords do not actually
co-occur with the tested content in any source document). Separately, the
document substance underneath E2, E3, and E4 is far richer than what is
tested — all three skew heavily toward dates and attribution and leave the
single most emphasized strategic content in their own source documents
(Mike Knapp's implementation-vs-strategic-CTO distinction; CCI's commercial
funnel and Kenneth's commission arrangement; the water-treatment concept
summary's five-system architecture and retainer pricing) completely
untested.

**Verdict: §E is partially mis-specified, not materially mis-specified.**
The 83% (20/24) CORE share means the section is broadly measuring the right
thing and the current RED result is not an artifact of a broken ruler. But
at least 2–3 of 24 facts (8–12%) are unwinnable or unreliable by construction
regardless of David's retrieval or reasoning quality, which is enough score
mass to matter at a 70% bar, and the design skew toward
dates/attribution over strategic substance means §E is a weaker "does David
understand the corpus" test than it could be even where it is technically
sound.

---

## 2. Source-document-by-source-document summary

All fifteen historical call files, `INDEX.md`, and `MANIFEST.md` live at
`sources/historical_calls/` in the Business Brain vault. Below, only the ten
files actually assigned as §E source_docs in the frozen scorer, plus
`current_priorities.md`, are summarized (E1 uses only `INDEX.md`).

| Document | Kind | What it actually is |
|---|---|---|
| `INDEX.md` | index | A 15-row table: source title, date text, participants, kind, link. States "Fifteen historical conversations... No speaker's statement here is canonical TTROS truth" up front. Short, structural, fully reachable. |
| `MANIFEST.md` | audit/promotion inbox | Import inventory (byte counts, SHA-256s), a curated list of "knowledge candidates" (short one-line summaries per theme), review-tier holds, and open loops. **Explicitly typed `historical_source` so the context assembler's F-BRAINNOTES-1 filter keeps it out of assembled context by design.** Not a call transcript — it is *about* the calls. |
| `mike-knapp-july-21.md` | call transcript | Full verbatim transcript, ~34KB. Liam and Mike Knapp discuss positioning (implementation vs. "AI-enabled CTO"), niching, MSP partnership as a distribution channel, the Sanjay introduction, and a "come back in a month" commitment. Contains Liam's own words: *"I've been reluctant to niche down."* |
| `mike-knapp-gtm-context-july-22.md` | post-meeting synthesis | A 15-section, ~45KB strategic memo written the next day: MSP definitions, partnership models, an 8-category MSP-archetype list, retainer/fee ranges, a 30-day plan, 14 explicit "Decisions Made," and 12 "Open Questions." |
| `first-call-cci.md` | call transcript | CCI's first call. CCI's ABM/lead-gen tooling (Salesforce, Pardot, Sales Navigator, Outreach), the "accelerate then track" product structure, and Liam's proposed pilot roadmap. |
| `cci-second-call-june-15.md` | call transcript | CCI's revenue targets ($7–8M/team, 36 SQLs needed, $750K avg deal), Kenneth's referral-commission structure, pilot scoping, and pricing negotiation ("what would this cost me?"). |
| `call-kenneth-after-first-cci.md` | call transcript, undated | Debrief immediately after the first CCI call — Kenneth's own commission interest (15%), plans to share a first-draft report with CCI ("Lambert/Lamb Weston" candidate), and unrelated SME/social-media side-work. |
| `call-dr-kenneth-after-second-cci.md` | call transcript, undated | Debrief after the second CCI call — quantifying time-savings, a phased pilot pitch, Kenneth's own boot-camp/course monetization idea, and next-step commitments. |
| `trent-first-call.md` | call transcript, undated | Trent explains a water-treatment RFP/estimating/invoicing workflow for "Lance" (never a speaker in this or any Trent call), frames AI as replacing an estimator and an admin role, discusses retainer economics. |
| `trent-july-9.md` | call transcript | Continues the Lance water-treatment concept; Trent offers to set up a meeting with Lance and separately introduces two other referrals (Ray, Jason) and a financial-advisor contact (Corey Boyne). No date string appears anywhere in the transcript body. |
| `hermes-water-treatment-summary-trent.md` | concept summary | A structured 15-section proposal: a five-system Hermes-coordinated architecture (Tender Radar, RFP/estimating, job tracking, technician input, invoicing), a staged build plan, and explicit retainer pricing tiers (CA$750–1,500 / 1,500–3,500 / 3,500–7,500+ per month). |
| `andrea-roberts-june-26.md` | call transcript | Andrea introduces Ken Stanick (Quinn AI founder); discusses her own Rascal HR-compliance SaaS in detail; Liam pitches an AI-driven legal-update concept for it. |
| `andrea-second-call-june-30.md` | call transcript | Andrea confirms Ken agreed to an intro, introduces Mike Knapp (via his "consultants happy hour") and Mike Gardner (Property Fox), and separately names Rachel Radford's "Mirror Consulting" bi-monthly in-person networking group. |
| `current_priorities.md` | operating state | States plainly: "Benched, do not work on unless reactivated: CCI/TRACC." |

---

## 3. Table of all 24 §E facts

Provenance classes: **T-body** = stated in the verbatim transcript/document
body; **INDEX** = stated in `INDEX.md`; **MANIFEST** = stated only in
`MANIFEST.md`; **filename/meta** = only in the import filename or Hermes
frontmatter, not in any body text; **inferred** = a safe inference from
source structure, not a literal statement.

| ID | Expected fact (as scored) | Exact source(s) | Provenance | Provenance class | Relevance | Reachable via Step 6 depth surface? | Audit note |
|---|---|---|---|---|---|---|---|
| E1.1 | Fifteen conversations | `INDEX.md` | "Fifteen historical conversations, preserved as evidence." (body, line 15) | T-body/INDEX | CORE | Yes — `INDEX.md` is directly `open_note`-able | Clean. |
| E1.2 | Dr Kenneth Moodley | `INDEX.md` | Participants column, two rows | INDEX | CORE | Yes | Clean. |
| E1.3 | Ken Stanick (Quinn founder) | `INDEX.md` | Row: "AI consulting opportunity ... with Quinn founder \| ... \| Ken Stanick" | INDEX | CORE | Yes | "Quinn founder" is a title/participant juxtaposition, not an explicit apposition — a light, safe inference. |
| E1.4 | Andrea Roberts | `INDEX.md` | Two rows, full name in one | INDEX | CORE | Yes | Clean. |
| E1.5 | Mike Knapp | `INDEX.md` | Two rows | INDEX | CORE | Yes | Clean. |
| E1.6 | Trent MacGregor | `INDEX.md` | Two rows | INDEX | CORE | Yes | Clean. |
| E1.7 | Ollie (CCI) | `INDEX.md` | Row: "...including Ollie and Kenneth; mapping unavailable" | INDEX | USEFUL | Yes | Even `INDEX.md` itself flags Ollie's role as unattributed ("mapping unavailable") — real but thin. |
| E1.8 | Lance (referenced, not present) | `INDEX.md` (E1's *only* declared source) | Row: "...references Lance and Trent" | INDEX (name only) | CORE | Yes, for the name | The scored substring is just `"lance"` (line 299 of the scorer) — the parenthetical "not present" in the human-readable question is **not enforced** by the scorer and is not established anywhere in `INDEX.md`; it only becomes true once E4's Trent transcripts are read. Scope mismatch between the descriptive fact text and E1's declared source. |
| E1.9 | No speaker's statement is canonical TTROS truth | `INDEX.md` | Same line 15 sentence as E1.1 | T-body/INDEX | CORE | Yes | The single most load-bearing epistemic-caution fact in §E — governs how every other E-fact should be handled. Well chosen. |
| E2.1 | Call on Jul 21 | `mike-knapp-july-21.md` | "Date: Jul 21" (transcript header, body) | T-body | CORE | Yes | Clean. |
| E2.2 | GTM/MSP packet dated 2026-07-22 | `mike-knapp-gtm-context-july-22.md` | "**Date:** 2026-07-22" (body, §header block) | T-body | USEFUL | Yes | Establishes there are *two* related records (a live call and a next-day synthesis) — a real distinction, but the literal date itself is a bookkeeping fact, not substance about what Mike advised. |
| E2.3 | Advice included niching down | `mike-knapp-july-21.md` / GTM packet | Entire §4.5 "Niche down because specificity improves sales"; also stated repeatedly in the raw transcript | T-body | CORE | Yes | Richly, repeatedly supported. |
| E2.4 | Trap: Mike's advice, not Liam's stated intention (reluctant) | `mike-knapp-july-21.md` | Liam, verbatim: *"I've been reluctant to niche down but I think it's in the back of my head..."* | T-body | CORE | Yes | The single best-designed §E fact — a genuine attribution/nuance test with an exact quoted anchor. |
| E3.1 | First call Jun 10 | `first-call-cci.md` | "Date: Jun 10" (body) | T-body | CORE | Yes | Clean. |
| E3.2 | Second call Jun 15 with Ollie and Kenneth | `cci-second-call-june-15.md`, `INDEX.md` | "Date: Jun 15" (body); document's own frontmatter says `participants_text: "...mapping unavailable"` and the transcript itself labels speakers only "Me"/"Them" | T-body (date) + INDEX/filename (participant attribution) | CORE | Yes | Date is solid; the Ollie/Kenneth attribution rests on `INDEX.md` + filename, corroborated only loosely by "Ollie" and "Kenneth" being addressed by name inside the dialogue. |
| E3.3 | Follow-up calls with Kenneth after each | `call-kenneth-after-first-cci.md`, `call-dr-kenneth-after-second-cci.md` | Both files are undated (`source_date_text: "unavailable"`); the "after first/second CCI call" framing comes from the filename/title, corroborated by the calls' own content (both immediately debrief a just-completed CCI meeting) | filename/title + content corroboration | CORE | Yes | Substantively true and well corroborated by content, but neither transcript body contains an explicit "this call happened right after the CCI call" sentence — it is evident from context, not a stated fact. |
| E3.4 | CCI/TRACC currently benched | `current_priorities.md` | "Benched, do not work on unless reactivated: CCI/TRACC." | T-body | CORE | Yes | The single most decision-relevant fact in E3 — direct and unambiguous. |
| E4.1 | Two Trent MacGregor calls: undated + Jul 9 | `trent-first-call.md`, `trent-july-9.md`, `INDEX.md` | Scored substring is only `"jul 9"`/`"july 9"`. This string appears in `INDEX.md`'s date column and in the *filename* `trent call transcript july 9th.txt` (per `MANIFEST.md`'s inventory). **It does not appear anywhere in the transcript body of `trent-july-9.md`** — the call itself is never self-dated in the dialogue. | filename → MANIFEST inventory → INDEX date column; **not in transcript body** | CORE (substance) | Partially — the date component is metadata-only | **This is the audit's clearest metadata-vs-truth finding.** `trent-first-call.md` is also undated. The only document that states "Jul 9" as a fact is `INDEX.md`, whose own date column for this row traces back to the operator-assigned import filename, not to anything said on the call. Per the audit's own governing rule, a filename date is metadata, not automatically conversation truth, and nothing in this corpus independently corroborates it. |
| E4.2 | Water treatment operating-system concept summary prepared for Lance/Trent | `hermes-water-treatment-summary-trent.md` | Title: "Hermes-Assisted Water Treatment Operating System — Concept Summary for Lance / Trent"; body: "Prepared for: Time to Revenue" | T-body | CORE | Yes | Clean, unambiguous. |
| E4.3 | Lance never in the room; Trent offers to get Lance's info | `trent-first-call.md`, `trent-july-9.md` | Lance is discussed exclusively in the third person across both Trent calls; no "Lance" speaker turn exists in either transcript. Trent (July 9): *"...if you want to have that conversation with them, I'll set it up."* | **inferred** from transcript structure (absence of a Lance speaker turn); no source uses any of the scorer's five literal required phrases (`never in the room` / `not in the room` / `not present` / `wasn't on the call` / `not on the call`) | CORE | Yes, structurally | The underlying claim is true and a legitimate capability test (can David notice a participant is discussed but never speaks), but the scorer's required literal phrasing does not occur verbatim in *any* source document — it was authored by whoever wrote the fact list, not lifted from the corpus. A David who correctly explained the nuance in different words would score 0 on this fact regardless of accuracy. Also note: the description "offers to get Lance's info" overstates the source — Trent offers to *set up a meeting* with Lance, not specifically to obtain his contact information. |
| E5.1 | Two calls: Jun 26 and Jun 30 | `andrea-roberts-june-26.md`, `andrea-second-call-june-30.md` | "Date: Jun 26" / "Date: Jun 30" (both bodies) | T-body | CORE | Yes | Clean. |
| E5.2 | Made specific named introductions | Both Andrea transcripts | Ken Stanick (Quinn AI), Mike Knapp (via the "consultants happy hour"), Mike Gardner (Property Fox), Rachel Radford (Mirror Consulting) | T-body | CORE | Yes | Richly, abundantly supported — the strongest single fact in E5. |
| E5.3 | Named a recurring Vancouver consultant event | `andrea-second-call-june-30.md` | "...another company called mirror consulting and they have every two months they have an in-person. Consultant networking thing." | T-body (substance); **required keywords absent** | CORE (substance) | Yes for substance; **no** for the literal scorer keywords | Scored as `kw(["vancouver"],["event"])` — an AND of two literal substrings. Neither word co-occurs with this sentence. `"Vancouver"` appears exactly once across both Andrea transcripts, and it describes an unrelated company (*"Quin AI is a Vancouver based tech company"*). `"event"` never appears attached to Mirror Consulting at all (the source calls it a "networking thing"); the word "events" appears once, generically, at the very end of the June 30 call, unconnected to Mirror Consulting. **A perfectly accurate, well-sourced answer naming Rachel Radford, Mirror Consulting, and the bi-monthly cadence will not satisfy this fact's scorer unless David independently supplies both words himself.** This revises the prior zero-model diagnosis's "expression gap" framing for E5.3: the gap is not purely expressive — the required keywords are not organically present in the source text being tested. |
| E5.4 | The parked candidate bullet understates this | `sources/historical_calls/MANIFEST.md`, `third_party_opinion` bullet: *"Andrea encouraged network-building and offered introductions."* — **not** among E5's declared `source_docs` in the scorer (`andrea-roberts-june-26.md`, `andrea-second-call-june-30.md`, `INDEX.md` only) | MANIFEST | MANIFEST-only; structurally unreachable | **UNSUPPORTED** | **No, by design** | `MANIFEST.md`'s own header states it is "typed `historical_source` so the context assembler's F-BRAINNOTES-1 filter keeps it out of assembled context by design," and the prior zero-model diagnosis independently confirmed it is excluded from the FTS search index. This fact asks David to judge that a specific document's summary bullet "understates" the calls — but that document is architecturally guaranteed never to reach him, and it is not even one of E5's own declared source documents for B6 CONTEXT-MISSING tracking. This is the single clearest structural defect in §E: a fact whose correctness cannot be established from anything David is designed to see. |

---

## 4. Per-question narrative: substance vs. what is tested

### E1 — "Which historical calls do we have on file, and who was in each?"

**What the document is really about:** `INDEX.md` is a compact, 15-row
manifest — exactly the shape of document this question should test.

**Most important facts:** (1) there are fifteen calls; (2) none of their
content is canonical TTROS truth; (3) the named, attributable participants
across the set; (4) that some participants (Ollie, the "second call with
Andrea" counterpart) are only partially attributed even in the index itself.

**How well the frozen question represents them:** Very well. This is the
best-designed question in §E — every fact is short, explicit, and drawn from
the one document the question is actually about. No date/attribution
over-weighting problem here because the whole document *is* dates and
attribution. The only soft spot is E1.8, whose full descriptive text implies
more ("not present") than either its declared source or its actual scored
substring test.

### E2 — "What did Mike Knapp advise?"

**What the document is really about:** A single 20-minute call (advice on
positioning, niching, and an MSP-partner introduction) followed by a
~45KB, deliberately structured strategic memo the next day, containing an
executive summary, a "Decisions Made" list of 14 items, an "Open Questions"
list of 12 items, and a full MSP-partnership playbook.

**Most important facts actually in the document:** (1) the
implementation-vs-"AI-enabled-CTO" distinction — described in the packet as
"the most important distinction of the meeting" and repeated four separate
times across the two documents; (2) niche down, but as advice conditioned on
Liam's own experience and industries with money/overhead, not a random
market; (3) Liam's own recorded reluctance to niche down (the trap); (4) MSP
partnership as the recommended distribution channel, including the Sanjay
introduction and a concrete illustrative pilot fee range (CA$3,000–5,000);
(5) a scheduled follow-up commitment (~2026-08-21).

**How well the frozen question represents them:** Partially. E2.3 and E2.4
correctly capture facts (2) and (3) above and are well designed. But E2 never
tests fact (1) — the document's own self-declared central insight — nor the
MSP-partnership strategy, nor the concrete next-step commitments. Half of
E2's four facts (E2.1, E2.2) are just call/document dates. A David who
perfectly explained the implementation-vs-CTO distinction and the MSP
strategy but forgot the exact calendar dates would score 2/4; a David who
recited both dates and "niche down" but never engaged with the actual
strategic content would score 3–4/4. The question over-weights bookkeeping
relative to the document's declared substance.

### E3 — "What happened with CCI?"

**What the documents are really about:** Two CCI calls plus two Kenneth
debrief calls — CCI's revenue math ($7–8M target, 36 SQLs needed, ~$750K
average deal), Kenneth's 15% commission arrangement, a specific candidate
company ("Lamb Weston"/"Lambert"), a proposed low-risk external pilot scoped
to avoid CCI's internal security constraints, and active price negotiation.

**Most important facts:** (1) the two call dates and the follow-up cadence
with Kenneth; (2) CCI's own sales-funnel economics and why a pilot was being
scoped; (3) the specific candidate company and Kenneth's stake in it landing;
(4) that the whole line of work is now benched with no stated reason in this
corpus.

**How well the frozen question represents them:** Partially. All four E3
facts are legitimate and well-sourced, but three of four (E3.1–E3.3) are
dates/attribution, and the fourth (E3.4) is a status flag with no "why."
None of the substantial commercial content — CCI's funnel math, the
commission structure, the specific pilot proposal — is tested at all, despite
being the actual content of ~400KB of transcript. A David who never engaged
with any of it, but reported the two dates and "it's benched," scores 4/4;
a David who explained the commercial arrangement in detail but missed one
date scores 3/4 or worse.

### E4 — "What is the Trent/Lance situation?"

**What the document set is really about:** Trent explaining a prospective
AI-assisted operating system for Lance's water-treatment company (estimator
and admin-role automation, tender monitoring), then a structured concept
summary proposing a five-workflow Hermes-coordinated architecture with
explicit staged retainer pricing (CA$750–7,500+/month tiers) — notably, a
close structural preview of the retainer-pricing logic TTR itself would
later need for its own business.

**Most important facts:** (1) two Trent calls exist, one undated; (2) Lance
himself never speaks in either — everything about him is second-hand through
Trent; (3) the concept summary's five-system architecture and its
"AI drafts, humans approve" governance principle (which mirrors TTR's own
doctrine); (4) the concrete retainer-pricing tiers; (5) Trent's separate
referrals (Ray, Jason, a financial advisor) offered in the same calls.

**How well the frozen question represents them:** Partially, with one clear
defect. E4.2 and E4.3 are reasonable, if E4.3's literal phrasing is
unsourced. E4.1's "Jul 9" component is the audit's cleanest metadata-only
finding — the date is never spoken on the call, only assigned via the import
filename. And the richest content in the whole set — the five-system
architecture and the retainer-pricing tiers, arguably the most reusable
strategic content in all of §E for TTR's own future pricing conversations —
is entirely untested.

### E5 — "Did Andrea Roberts introduce us to anyone?"

**What the documents are really about:** Two calls in which Andrea makes
several concrete, named introductions (Ken Stanick/Quinn AI, Mike
Knapp/Incrementa, Mike Gardner/Property Fox, Rachel Radford/Mirror
Consulting) and gives detailed incorporation/GST/liability-insurance
business advice.

**Most important facts:** (1) the two call dates; (2) the specific named
introductions, which are the actual point of the question; (3) the Mirror
Consulting bi-monthly networking group; (4) that MANIFEST's own
one-line summary of this material ("encouraged network-building and offered
introductions") is far thinner than the actual transcripts.

**How well the frozen question represents them:** Well for E5.1/E5.2 —
these are strongly, directly supported and correctly test the actual point
of the question. E5.3 correctly identifies genuinely important content
(the recurring Mirror Consulting event) but its scorer keywords do not
co-occur with that content anywhere in source. E5.4 is the audit's other
clear structural defect: it tests David's judgment against a document
(`MANIFEST.md`) that the system is built to keep from him, and which is not
even declared as this question's own source for CONTEXT-MISSING tracking.

---

## 5. Counts across all 24 facts

| Class | Count | Facts |
|---|---:|---|
| CORE | 20 | E1.1–E1.6, E1.8, E1.9, E2.1, E2.3, E2.4, E3.1–E3.4, E4.2, E4.3, E5.1, E5.2, E5.3 |
| USEFUL | 2 | E1.7, E2.2 |
| INCIDENTAL | 0 | — |
| METADATA-ONLY | 1 | E4.1 |
| UNSUPPORTED | 1 | E5.4 |
| **Total** | **24** | |

---

## 6. §E v1 verdict

**Partially mis-specified.** The overwhelming majority (20/24, 83%) of facts
are CORE, well-grounded, and reachable through the depth-tool surface Step 6
actually used. The section is not a broken ruler in the aggregate, and
the prior zero-model diagnosis's central finding — that the fresh Step 6 pass
opened the correct source for all ten of its missing facts — stands
unchallenged by this audit. But two facts (E4.1, E5.4) and one further
keyword-mismatch (E5.3) are defective independently of anything David does,
concentrated specifically in the two weakest-scoring questions (E4, E5) in
the fresh pass. At a fixed ≥70% (17/24) bar, three compromised facts out of
24 is enough to move the outcome, and all three cluster exactly where the
score is already weakest.

Separately, and independent of correctness: E2, E3, and E4 systematically
under-test the strategic substance of their own source documents in favor of
dates and attribution. This is a design-quality issue, not a
correctness defect — every date/attribution fact that exists is legitimately
sourced — but it means §E currently rewards a "who and when" recitation over
genuine understanding of what TTR actually learned or was offered in these
calls, which is a weaker test of "does David understand the historical
corpus" than the section's stated purpose calls for.

---

## 7. Date-provenance findings

- **E1, E2, E3, E5 dates are well-grounded.** Every date fact in E1
  (via `INDEX.md`), E2 (`mike-knapp-july-21.md`, `mike-knapp-gtm-context-july-22.md`),
  E3.1 (`first-call-cci.md`), and E5.1 (both Andrea transcripts) is stated
  explicitly in the transcript or document body itself — the strongest form
  of evidence per this audit's own governing rule.
- **E3.2's date is body-stated; its participant attribution is not.** The
  "Jun 15" date is in the transcript body; the "with Ollie and Kenneth"
  qualifier rests on `INDEX.md` plus filename plus loose in-dialogue
  corroboration, since the transcript's own frontmatter records
  `participants_text: "...mapping unavailable"`.
- **E4.1's "Jul 9" is the one genuine metadata-only date in §E.** It is
  absent from the transcript body of `trent-july-9.md` in its entirety and
  exists only via the import filename (`trent call transcript july 9th.txt`,
  per `MANIFEST.md`'s inventory table) propagating into `INDEX.md`'s date
  column. `INDEX.md` is a legitimate declared source for E4, so the fact is
  not baseless — but nothing in this corpus independently corroborates the
  filename-derived date against anything said on the call, which is exactly
  the failure mode this audit's governing rules warn against.
- No date in §E rests on filesystem ctime/mtime; all date evidence traces to
  either transcript body text or the deliberately maintained `INDEX.md`
  table.

---

## 8. Can the current Step 6 RED be trusted as a pure retrieval/capability signal?

**Not fully — with a caveat that the shortfall is small relative to the gap
to green.** §E scored 14/24 (58.3%) against a 17/24 (≥70%) bar, a 3-fact
gap. This audit finds:

- **At least 1 of 24 facts (E5.4) is structurally unwinnable.** No retrieval
  improvement and no expression improvement by David can make this fact
  present, because its true comparison source (`MANIFEST.md`) is
  intentionally kept out of assembled context and out of search, by design,
  and is not even declared as E5's own source document.
- **At least 1 of 24 facts (E5.3) requires David to supply two literal
  words that are not organically present in the source content being
  tested**, which the prior zero-model diagnosis characterized purely as
  an "expression gap" but which this audit's direct source read shows is at
  least partly a fact/scorer-design gap: even a source-faithful paraphrase
  will not trigger the scorer.
- **At least 1 of 24 facts (E4.1) tests a date that exists only as import
  metadata**, not as anything spoken on the call it is nominally testing.

Combined, that is 3 of 24 facts (12.5% of §E, and 3 of the 10 facts the
fresh Step 6 pass actually missed) whose absence from a "perfect" David
answer would not indicate any retrieval or reasoning defect at all. Removing
those three from the denominator changes the picture only modestly — the
fresh pass's real, defensible miss count on genuinely well-specified facts
is 7 of 21 (66.7%), still short of a 70%-equivalent bar, and the prior
zero-model diagnosis's "expression gap, not retrieval gap" conclusion for
the remaining seven is not disturbed by this audit (this audit deliberately
did not re-examine David's answers; it evaluated the fact list against
source independent of his performance, per the task's instructions).

**Conclusion: the current RED result is directionally credible — §E's
design defects are not large enough to flip RED to GREEN on their own — but
it should not be reported or acted on as a clean capability measurement
until the design issues in E4.1, E5.3, and E5.4 are resolved.** A section
that is 12.5% structurally compromised is not yet a fully trustworthy ruler
for the pass/fail decision it is being asked to carry, even though it is
close enough to trustworthy that Step 6's overall RED conclusion is unlikely
to be wrong in direction.

---

## CLOSEOUT

**NEEDS ATTENTION**

- §E source-design verdict: **partially mis-specified** (not materially
  mis-specified — 20/24 facts are CORE and well-grounded).
- Counts: **CORE 20 · USEFUL 2 · INCIDENTAL 0 · METADATA-ONLY 1 ·
  UNSUPPORTED 1** (total 24).
- Date-provenance findings: all §E dates except one trace to transcript body
  text or the actively maintained `INDEX.md`; **E4.1's "Jul 9" is
  metadata-only**, sourced only via the import filename propagating through
  `MANIFEST.md`'s inventory into `INDEX.md`'s date column, never stated on
  the call itself.
- Is §E a trustworthy ruler for Step 6 as currently written: **mostly, not
  fully.** 20/24 facts (83%) are sound. E5.4 is structurally unwinnable by
  design (its comparison source is deliberately excluded from context and
  not declared as that question's own source). E5.3's required keywords do
  not co-occur with the tested content in any source document. E4.1 tests a
  metadata-only date. These three facts sit inside the two
  weakest-scoring questions in the fresh Step 6 pass.
- Exact recommended next decision (not implementation): **Liam should decide
  whether to authorize a bounded, version-tracked correction to the three
  flagged facts (E4.1, E5.3, E5.4) — as a fact-list-quality fix, separate
  from and prior to the still-open narrative-vs-literal-scoring policy
  question already surfaced in `scripts/step6_zero_model_diagnosis.md`** —
  before spending further B7 budget on a re-run. This audit does not
  recommend which fix, does not propose replacement wording, and does not
  touch the frozen harness.
- Files inspected: `docs/ttros/TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`
  (hash-verified against `docs/ttros/SOURCE.sha256`), `scripts/step3_b7_harness.py`
  (§E `QUESTIONS` entries, read-only), `scripts/step6_zero_model_diagnosis.md`,
  and every §E source document in the live vault: `sources/historical_calls/INDEX.md`,
  `sources/historical_calls/MANIFEST.md`, `mike-knapp-july-21.md`,
  `mike-knapp-gtm-context-july-22.md`, `first-call-cci.md`,
  `cci-second-call-june-15.md`, `call-kenneth-after-first-cci.md`,
  `call-dr-kenneth-after-second-cci.md`, `trent-first-call.md`,
  `trent-july-9.md`, `hermes-water-treatment-summary-trent.md`,
  `andrea-roberts-june-26.md`, `andrea-second-call-june-30.md`,
  `operating_context/current_priorities.md`, `operating_context/open_loops.md`.
- Files created: this report,
  `scripts/step6_b7_section_e_source_relevance_audit.md`.
- Production files modified: **none.**
- David/Hermes model calls: **0.**
