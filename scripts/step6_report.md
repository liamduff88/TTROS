# Step 6 -- corpus and vault behind tools -- result

One B7 rescoring pass (25/25 David calls, budget exactly met, no overage).
Compared against the Step 5 k=1 baseline (same map, same vault snapshot, same
surface, tools absent) -- `scripts/step5_b7_pass_k1.scored.json` vs.
`scripts/step6_b7_pass.scored.json`. Prediction fixed in advance in
`scripts/step6_prediction.md`; not revised after seeing this result.

## §E bound: FAIL

Predicted 75-92% (flat-to-improved vs. the 75.0% k=1 baseline). **Actual:
58.3% (14/24), down from 75.0% (18/24).** The step's stated bound (§E >= 70%)
is **not met**. This is the load-bearing result and it did not go the way
the step's own framing ("currently expected near zero") or my prediction
assumed -- both were wrong in different directions: §E was already well
above 70% before this step (via session-log leakage, not these tools), and
adding the tools made the keyword-scored total worse, not better.

Per-question detail (facts present/total, k1 -> step6):
- E1 9/9 -> 9/9 (flat)
- E2 2/4 -> 1/4
- E3 4/4 -> 2/4
- E4 1/3 -> 1/3 (flat)
- E5 2/4 -> 1/4

## Why, on inspection (instrument-first, per CLAUDE.md)

All five §E questions show `disposition: brain_tool` -- the new tools
(`search_calls`, `open_call`, `open_note`, `search_history`) were mechanically
used every time (verified read-only against David's own session state.db,
`~/.hermes/profiles/david/state.db`, not inferred from the answer text).
Reading the actual answers (`scripts/step6_b7_pass.raw.json`), the content is
substantively accurate and explicitly source-attributed ("Verified from
historical call evidence...") -- for example E5's answer correctly separates
completed introductions (Mike Knapp, Ken/Quinn AI) from merely-promised ones
(Mike Gardner, Rachel Radford), which the frozen fact list does not even ask
for. What it does not do is restate the literal keyword strings the frozen
scorer requires (exact calendar dates such as "Jul 21"/"Jun 15", the phrase
"recurring Vancouver consultant event", the word "understate"). The model
answered in synthesized narrative prose instead of a fact-sheet, and the
keyword scorer cannot see through that. **This is a real regression signal
(more than Step 3's own 4.0pp noise allowance on every affected question
except E4), not proof the tools returned bad information** -- but this
single pass cannot separate "tools returned the right file and the model
under-cited it" from "tools returned the wrong file." Both readings are
consistent with what was measured.

**A second, structural finding, worth recording in `00` at the next
opportunity (not fixed here -- out of this step's scope per CLAUDE.md rule
7):** B6's CONTEXT-MISSING/IGNORED split reads only the initial
context-assembly manifest's declared `sources`. It cannot see content a
tool fetched mid-conversation, so every §E fact this pass answered via
`open_call`/`open_note` still shows `source_arrived: false` -- identical to
k=1, even though the tool call happened. B6 cannot currently tell "the tool
fetched it and the model still missed the fact" apart from "nothing was ever
looked at." Any future B7 pass measuring tool-era retrieval needs B6 extended
to also credit tool-call reads, or CONTEXT-MISSING/IGNORED is meaningless for
tool-answered questions.

## Direct-answer vs. round-trip ratio (25 questions)

- **direct** (no tool call this turn): 12 (48%)
- **brain_tool** (one of the four new tools used): 10 (40%) -- all 5 of
  section E, plus A1, B1, B3, B4
- **other_tool** (a tool call happened, but not one of the four new ones --
  `skill_view`, a pre-existing generic Hermes tool): 3 (12%) -- A4, C2, D4
- unknown (session lookup failed): 0

Predicted 32-56% round-trip; actual 52% (13/25) -- within the predicted
range. Predicted concentration in E (4-5/5) and spreading into A/B; actual
matches: E 5/5, A 2/5, B 3/4, C 1/4, D 1/4.

## Latency added per round trip

- direct mean: 14.0s (n=12)
- brain_tool mean: 33.6s (n=10) -- **+19.6s vs. direct**
- other_tool mean: 17.8s (n=3) -- +3.8s vs. direct

Predicted +20-35s for a round trip; actual +19.6s for the new tools,
consistent with the prediction and with the pre-existing high-`api_calls`
latency tax already visible in k=1 (44.2s mean) before this step existed.

## What this implies about map size

Overall coverage also dropped, k=1 53.5% (53/99) -> step6 47.5% (47/99).
Section-by-section: A 46%->38%, B 24%->29%, C 69%->69% (flat), D 58%->50%,
E 75%->58%. Only C held flat; every other section moved, mostly down, by
more than a single pass can distinguish from the ~4.0pp inter-pass noise
Step 3 measured -- except E, whose 16.7pp drop is unambiguously outside that
band.

This does **not** support growing `.hermes.md` past its Step-5-determined
k=1 stopping point: the tools were used precisely where the map has gaps
(section E's raw call material was never a map-growth candidate; sections
A/B where `open_note` pulled `memory/offers.md`-class content the k=1 map
doesn't carry). That is the tools doing the job Step 5 deliberately left to
them, per the forward sequence. What it argues instead is that **the corpus/
vault tools, as measured today, are not a clean substitute for map coverage
on this frozen keyword scorer** -- the round-trip mechanism works (52% usage,
latency cost as predicted, right sections targeted) but the scored outcome
regressed. Before Step 6b (deleting the old ranking path) proceeds on the
strength of this step being "green," this §E regression needs to be resolved
or explicitly waived by Liam -- the step's own bound is not met.

## Budget accounting

Declared maximum: 25 David calls, one pass. Actual: 25/25, no overage, no
hard stop, no aborted run, no unexpected repo mutation (one transient
`queue/locks/*.candidate-*` lock file from concurrent systemd-timer activity
was observed and correctly excluded -- confirmed pre-existing, unrelated
noise, reproduced in a zero-call `--dry-run` before any real call was spent).

## Files

- Change/rollback record: `scripts/step6_transcript.txt`
- Prediction (written before the pass): `scripts/step6_prediction.md`
- Harness: `scripts/step6_b7_tools_harness.py`
- Raw/scored evidence: `scripts/step6_b7_pass.{transcript.txt,raw.json,scored.json}`
- Backups (pre-edit preimage): `/home/liam/ttros_backups/step6_20260907T175108Z/`
- Code changed: `tools/brain_memory.py` (3 new read-only functions),
  `tools/brain_memory_mcp.py` (4 new tools, reusing the existing
  `tools/aos_indexer.py` FTS index rather than building a second one)
