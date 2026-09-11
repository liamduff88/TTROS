# Step 6 — zero-model forensic diagnosis of the fresh B7 verification

ZERO David/Hermes/model calls made. No B7 re-run. No production file touched.
Inputs: `scripts/step6_b7_pass.{raw,scored,transcript.txt}` (the fresh 25/25
pass), David's own session state.db (`~/.hermes/profiles/david/state.db`,
read-only lookup, same read-only mechanism `step6_b7_tools_harness.py`
already uses), `scripts/step3_b7_harness.py` (scorer source, read-only),
and the prior `scripts/step6_report.md` / `scripts/step6_repair_report.md`.

Official frozen result, unchanged and not rescored:
**§E = 14/24 = 58.3%** (required ≥70% / 17/24). **Overall = 47/99 = 47.5%.**
§F honesty = 3/3 PASS. Full regression = 772/0. Step 6 remains RED.

---

## PART 1 — §E forensics (10 missing facts)

Method: for each missing fact's question, pulled the exact David session
transcript (user turn, every tool call, every tool result payload, final
answer) from `~/.hermes/profiles/david/state.db` by `session_id`
(`round_trip.<qid>.session_id` in the scored evidence), read-only, and
checked whether the atomic fact's required substring(s) — from
`step3_b7_harness.py`'s frozen `QUESTIONS[...]["facts"]` — appear anywhere
in what was actually returned to David, and whether David's final answer
text contains them (the same test the frozen scorer runs).

| Fact | Official disposition | Initial context (B6) | Depth-tool behaviour | Supplemental outcome |
|---|---|---|---|---|
| E2.1 "Call on Jul 21" | IGNORED | Not in B6 | `open_call(mike-knapp-july-21)` — full 98,746-char transcript fetched, contains `"Source date text: Jul 21"` | **FACT EXPOSED BY TOOL, OMITTED FROM ANSWER** |
| E2.2 "GTM/MSP packet dated 2026-07-22" | IGNORED | Not in B6 | `open_call(mike-knapp-gtm-context-july-22)` fetched in full, contains `"Source date text: 2026-07-22"` | **FACT EXPOSED BY TOOL, OMITTED FROM ANSWER** |
| E2.3 "Advice included niching down" | — (present) | — | — | present — answer's §4 is titled "Niche down enough to make sales easier" |
| E2.4 "Trap: Mike's advice, not Liam's stated intention (reluctant)" | IGNORED | Not in B6 | Same `mike-knapp-july-21` transcript literally contains *"I've been reluctant to niche down"* (Liam, in his own words) | **FACT EXPOSED BY TOOL, OMITTED FROM ANSWER** — answer presents niching-down as flat commercial advice, never flags it as Mike's push against Liam's recorded reluctance |
| E3.1 "First call Jun 10" | IGNORED | Not in B6 | `search_history("CCI OR TRACC")` snippet for `first-call-cci.md` literally contains `"Source date text: Jun 10"`; **`open_call`/`open_note` never issued against that file** | **FACT EXPOSED BY TOOL (in the search snippet), SOURCE ITSELF NOT OPENED, OMITTED FROM ANSWER** |
| E3.2 "Second call Jun 15 (Ollie/Kenneth)" | IGNORED | Not in B6 | Same search snippet for `cci-second-call-june-15.md` literally contains `"Source date text: Jun 15"` and `"Second call with CCI, Ollie and Kenneth"`; not opened | **FACT EXPOSED BY TOOL (snippet), SOURCE NOT OPENED, OMITTED FROM ANSWER** — David pivoted instead to `open_note(memory/clients.md)` and `open_note(operating_context/active_projects.md)`, neither of which carries the dates |
| E4.1 "Two Trent calls: undated + Jul 9" | CONTEXT-MISSING | Not in B6 | `open_call(trent-first-call)` → `"Source date text: unavailable"`; `open_call(trent-july-9)` → `"Source date text: Jul 9"` — **both fetched in full** | **FACT EXPOSED BY TOOL, OMITTED FROM ANSWER** (label is CONTEXT-MISSING only because none of E4's `source_docs` had arrived in B6 — see Part 3) |
| E4.3 "Lance never in the room; Trent offers to get his info" | CONTEXT-MISSING | Not in B6 | `open_call(trent-july-9)` transcript contains Trent saying *"I'll set it up"* and Liam saying *"I'll send you the email…"* | **PARTIALLY EXPOSED, NOT EXPRESSED IN THE SCORER'S REQUIRED WORDING** — answer says "This is still second-hand… we do not have Lance's direct statements" and "Trent said he could set up a meeting," which is the right idea but never uses any of the scorer's required phrases (`never in the room` / `not present` / `wasn't on the call` / etc.) |
| E5.1 "Two calls: Jun 26 and Jun 30" | CONTEXT-MISSING | Not in B6 | `open_call(andrea-roberts-june-26)` **and** `open_call(andrea-second-call-june-30)` both fetched in full (`~96–97k chars` each) | **FACT EXPOSED BY TOOL, HALF-OMITTED** — answer states "Evidence from the Jun 30 call" and never mentions Jun 26 at all, despite having just read it. (This file was the one previously unindexed by the now-fixed `SECRET_CONTENT_RE` whole-document veto — see Part 3; the fix is confirmed working here, since the fetch succeeded.) |
| E5.3 "Named a recurring Vancouver consultant event" | CONTEXT-MISSING | Not in B6 | `andrea-second-call-june-30` payload literally contains: *"a company called mirror consulting and they have every two months they have an in-person. Consultant networking thing."* | **FACT EXPOSED BY TOOL, OMITTED FROM ANSWER** — answer names "Rachel Radford / Mirror Consulting" and "guest list" but drops the recurring/bi-monthly framing and never writes "Vancouver" or "event" (the two literal strings the scorer requires) |
| E5.4 "The parked candidate bullet understates this" | CONTEXT-MISSING | Not in B6 | No `search_calls`/`search_history`/`open_note` call in this session ever queried `open_loops.md` or any "parked" bullet | **RELEVANT SOURCE NOT FETCHED** — per the prior repair diagnosis this is also structurally excluded from the FTS index by design (`MANIFEST.md`'s F-BRAINNOTES-1 filter), so it was not reachable by search in this session regardless |

Cross-check against the prior repair pass (`scripts/step6_repair_report.md`,
written before this fresh pass): that report independently traced 9 of
these same 10 facts against an *earlier* B7 session and reached the same
"correct file opened, fact not restated" verdict for 8 of them, plus the
now-fixed indexing defect for E5.1's Jun-26 half. My independent trace of
**this fresh, post-repair pass's own sessions** confirms: (a) the index fix
is holding — `andrea-roberts-june-26.md` was successfully opened this time
— and (b) the fact still did not survive into the answer. That converts
E5.1 from "retrieval defect" to "pure expression gap," same as the other
nine.

**Net for §E:** in **10 of 10** missing facts, the declared source document
was opened successfully by at least one Brain MCP tool call in that
question's own session (9 of 10 via a direct `open_call`/`open_note`; E3's
two via a `search_history` snippet that already contained the literal date
but was never opened for confirmation). Zero of the ten are a genuine "the
tool returned nothing / returned the wrong file" retrieval failure in this
fresh pass. All ten are either (a) omitted from a synthesized-narrative
answer that covers the *substance* of the question without restating the
literal date/keyword the frozen scorer keys on, or (b) — one case, E5.4 —
never searched for at all.

---

## PART 2 — the four 0%-coverage questions (A2, A4, B3, C4)

| Q | Initial context (B6) | Tool used | What the tool returned | Best explanation |
|---|---|---|---|---|
| **A2** "core principle behind how we sell" | `memory/offers.md` / `memory/positioning.md` — neither in B6 | **None** — zero tool calls this turn | n/a | **(b) depth-navigation failure** — David never attempted a search or note-open; answered entirely from general reasoning ("we prove the system on ourselves…"), plausible but not grounded in the actual diagnose-first/offer-ladder text |
| **A4** "what are we not allowed to claim" | `memory/positioning.md` marked `source_arrived: true` officially — **see instrument caveat below; the content was in fact never loaded into any context block** | `skill_view("linkedin_outreach_prep")` — **misfired**: `"Skill 'linkedin_outreach_prep' not found"` | Nothing usable; David never retried with a Brain tool | **(b) depth-navigation failure, mislabeled** — the one tool call targeted the wrong subsystem (a skill file, not the Brain vault) and failed outright; David did not fall back to `search_history`/`open_note`. Positioning.md's actual "Do not claim…" list never reached him by any channel this turn. |
| **B3** "who is the ideal client" | `memory/ideal_clients.md` marked arrived — **also a false positive, see below** | `open_note` × 4: `ideal_clients.md`, `ideal_clients_A.md`, `ideal_clients_B.md`, `memory/positioning.md` — **all four fetched in full and correctly** | Full, verbatim, correct content: "two tracked ICP variants," "60% / 40%," "Ideal Clients — **router**," "not a market restriction" | **(d) received the facts, failed to express the scorer-required atomic wording** — this is the cleanest full-fidelity-retrieval case in the whole pass. David's answer accurately restates the *substance* (a primary and a "secondary ICP," a "40% prospecting hypothesis, not the core market claim") but never writes "ICP-A," "ICP-B," "router," "broader," "60," or "don't exclude" — the seven literal strings the scorer needs. Zero of seven facts present despite a perfect retrieval round-trip. |
| **C4** "proof strategy for winning first clients" | `memory/positioning.md` — not in B6 | `skill_view("fit_call_prep")` — **misfired**: `"Skill 'fit_call_prep' not found"` | Nothing usable; no retry | **(b) depth-navigation failure** — same pattern as A4: a failed skill-lookup, then no fallback to the Brain tools that would have found `positioning.md`'s "specialization by problem type… vertical narrowing comes after proofs exist" text. David's own reasoning independently reconstructed a similar-sounding proof strategy ("prove the acquisition engine on TTR itself… generate two implementation proofs") but never states "problem type" or "vertical," so the literal facts score absent regardless. |

**A4 / B3 instrument caveat (new finding, not previously recorded):**
`step3_b7_harness.py::source_arrived()` (reused unmodified by Step 6) has
two code paths: a precise one that reads a manifest `sources` field and
explicitly discounts any hit tagged `#excluded=` / `#budget=omitted`, and a
**fallback** — used whenever the manifest has no top-level `sources` key —
that just checks whether the doc's path string appears *anywhere* in the
whole manifest JSON, with no such exclusion check. **Every one of this
fresh pass's 25 records lacks a top-level `sources` key**, so all 25
`source_arrived` determinations in `step6_b7_pass.scored.json` went through
the unguarded fallback. Checking each `arrived: true` flag against the
actual assembled block content, five are false positives — the path string
was found only inside an explicit
`"...memory/positioning.md#route=direct_fallback#excluded=step5_map_covers_this"`
deduplication tag (A1, A4, B1, B3) or quoted inside an old rolled-forward
session log's embedded metadata (E2) — in every one of these cases the real
document content was **never** actually loaded into any context block
(`real_block_loaded = False`, confirmed directly against `manifest.blocks`).
I have not altered the frozen scorer, its output, or any recorded
disposition; this is reported strictly as supplemental evidence bearing on
how much weight the IGNORED/CONTEXT-MISSING split can carry (Part 3).

---

## PART 3 — plan decision

**1. Why did §E stay at 14/24 despite all five questions invoking depth tools?**
Because invoking the tools and *retrieving the right document* are not the
same as the fact surviving into the final answer. In all 10 missing facts,
the correct source was either opened in full or, in two cases, surfaced
verbatim in a search snippet — and in every one of the 10 cases the literal
date/keyword/phrase the frozen scorer requires did not survive David's
synthesis into narrative prose. This is the same conclusion the prior
(pre-fresh-pass) repair diagnosis reached for 8 of these 10 facts, and my
independent trace of the fresh pass's own sessions confirms it holds for
all 10, including E5.1 whose earlier retrieval-index defect is now
confirmed fixed and no longer the limiting factor.

**2. Is there evidence of a concrete Step 6 retrieval/exposure defect that
should be repaired before further B7 spend?**
No new one. The three concrete, mechanical defects this pass's tool-path
evidence could have exposed — the whole-document secret veto that hid
`andrea-roberts-june-26.md`, the `operator-lean` tool-surface leak, and the
missing `snippet` field on `search_calls`/`search_history` — were already
found and fixed *before* this fresh pass ran (`scripts/step6_repair_report.md`),
and this pass's own tool-call traces confirm the fixes are holding (the
previously-hidden file opened cleanly; `operator-lean`'s contract test is
green in the 772/0 full suite). The one genuine instrument issue I found in
this diagnosis — the `source_arrived()` fallback's blind spot to
`#excluded=` tags and stale session-log residue — sits in the frozen B7
scorer/harness, which this task is explicitly not authorized to change, and
in any case affects only the CONTEXT-MISSING/IGNORED *label*, not what
David actually saw or wrote.

**3. Does the evidence satisfy the plan's "IGNORED dominating" condition
strongly enough to trigger Step 7?**
Not convincingly. Two separate reasons:
- Overall missing-fact split is 31 IGNORED / 21 CONTEXT-MISSING (60/40) —
  a majority, not a dominant signal — and **at least 17 of the 31** IGNORED
  facts (A1.7, all 6 of A4, 3 of B1, all 7 of B3) rest on the false-positive
  `source_arrived` signal documented above, not on confirmed content
  delivery.
- For §E specifically — the load-bearing, currently-RED section — the
  split is an exact **5 IGNORED / 5 CONTEXT-MISSING**, and my forensic
  trace shows no real behavioural difference between the two labels: both
  groups had their declared source successfully opened by a Brain tool
  mid-turn (E4/E5's "CONTEXT-MISSING" facts only carry that label because
  none of their `source_docs` happened to be in the Step-5 k=1 map — a B6
  bookkeeping artifact already flagged in `scripts/step6_report.md`, not a
  retrieval difference). A 50/50 split with no underlying behavioural
  distinction is not "IGNORED dominating."

**4. Step 7 is NOT yet justified on this evidence.**

**5. Next plan-prescribed action:** closest to **further zero-model
diagnosis** — but the open item is not really more instrumentation, it is
a **policy decision already surfaced (and not yet made) in
`scripts/step6_repair_report.md`**: whether TTROS accepts a substantively
correct, source-attributed *narrative* answer as satisfying these B7
questions, or requires David to mirror the frozen scorer's literal
keywords/dates. Every one of this pass's ten §E misses and three of the
four 0%-coverage questions (A2, A4, C4 partially; B3 fully) turn on that
single unresolved question, not on a bounded mechanical fix and not on an
IGNORED-dominant pattern. Recommend Liam make that call before any further
25-call B7 budget is spent — a repeat pass under the current scorer would
very likely reproduce the same shape of result regardless of further
retrieval-side repair.

---

## CLOSEOUT

**NEEDS ATTENTION** — Step 6 remains RED; no repair, rescoring, or
architectural change made or recommended as a fix here.

- Official §E result unchanged: **14/24 = 58.3%** (need ≥70%).
- Official CONTEXT-MISSING/IGNORED split: overall 21/31; §E exactly 5/5.
- Supplemental 10-fact §E table: see Part 1 — 10/10 facts had their
  declared source successfully opened by a Brain tool in-session (9 via
  `open_call`/`open_note`, 1 pair via a `search_history` snippet); 0/10 are
  a genuine "tool found nothing / found the wrong file" failure in this
  fresh pass.
- 0%-question findings: A2 and C4/A4's failed `skill_view` calls =
  depth-navigation misses (no Brain-tool fallback attempted); B3 = full,
  correct, verbatim retrieval with zero matching literal output — the
  cleanest evidence in the pass that this is an expression gap, not a
  retrieval gap.
- Root cause(s): (i) dominant — narrative-answer-style vs. frozen
  literal-keyword scorer, confirmed on 10/10 §E misses and B3's full 0-for-7;
  (ii) secondary — two failed `skill_view` lookups (A4, C4) with no
  fallback to the Brain tools that were available and would have worked;
  (iii) newly found — the `source_arrived()` fallback path used by all 25
  records this pass over-credits "arrived" on `#excluded=`-tagged and
  stale-session-log string matches, contaminating at least 17 of the 31
  official IGNORED labels; does not change any score, only the confidence
  that can be placed in the IGNORED/CONTEXT-MISSING split for a Step 7
  decision.
- Step 7 condition ("IGNORED dominating"): **not met** — see Part 3.3.
- Exact plan-prescribed next action: **further zero-model diagnosis /
  Liam policy decision** on narrative-vs-literal scoring, per Part 3.5 —
  not a bounded Step 6 repair (no new mechanical defect found) and not
  Step 7 (IGNORED does not dominate, especially not in §E).
- Files inspected: `scripts/step6_b7_pass.{raw.json,scored.json,transcript.txt}`,
  `scripts/step3_b7_harness.py` (scorer, read-only), `scripts/step6_report.md`,
  `scripts/step6_repair_report.md`, `scripts/step6_b7_tools_harness.py`,
  `~/.hermes/profiles/david/state.db` (read-only, session messages for
  E2/E3/E4/E5/A2/A4/B3/C4).
- Files created: this report (`scripts/step6_zero_model_diagnosis.md`);
  scratch session dumps under this session's scratchpad (not part of the
  repo, not committed).
- Production files modified: **none.**
- David/Hermes/model calls made by this diagnosis: **0.**
