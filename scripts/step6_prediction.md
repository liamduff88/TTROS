# Step 6 -- prediction, written before the rescoring pass

Written (UTC): 2026-09-07, before `scripts/step6_b7_tools_harness.py run-pass` is invoked.
Per CLAUDE.md evidence discipline: fixed here, not moved after seeing the result.

## Prior evidence this prediction is allowed to use

Step 5 k=1 (map_bytes=1788, 1/9 classes, brain MCP server WITHOUT the four new
tools) already scored (`scripts/step5_b7_pass_k1.scored.json`):

- Overall: 53.5% (53/99)
- Section E (historical calls): **18/24 = 75.0%**, entirely via
  `episodic_recency`/`episodic_activity` session-log leakage -- every
  declared `sources/historical_calls/*.md` source shows `source_arrived:
  false` in the B6 manifest check for every E question. David is already
  reaching E content some other way (session continuity notes, and/or an
  existing generic tool -- `api_calls` for E1/E2/E5 were 8/5/5 respectively,
  vs. a 1-2 baseline for most other questions, meaning David already made
  extra agentic-loop round trips on those three questions using whatever
  toolset was already available, before this step existed).
- Per-section k=1 coverage: A 46% (12/26), B 24% (5/21), C 69% (11/16),
  D 58% (7/12), E 75% (18/24).
- Latency confound already visible pre-Step-6: questions with `api_calls<=2`
  averaged 16.9s; questions with `api_calls>2` averaged 44.2s (n=5: A1, E1,
  E2, E5, F3).

## Prediction

**§E score:** the ≥70% bound is already met pre-tools. Prediction for THIS
pass (tools added): **75-92%**, i.e. flat-to-improved, not a regression --
the new tools give a source-attributable path (`search_calls`/`open_call`)
to the same E2/E4/E5 gaps (call dates, Lance detail, the Vancouver event,
the understated introduction) that k=1 left CONTEXT-MISSING/IGNORED at
50%/33%/50% respectively. I do not predict a jump to 100%: E4/E5's missing
facts are specific phrasings a keyword scorer may still miss even if the
right file is opened.

**Direct-answer vs. round-trip ratio (of 25 questions):** predict **8-14
questions (32-56%)** show a tool round trip (operationalized as
`sessions.tool_call_count > 0` for that question's `session_id`, read
read-only from Hermes's own `state.db`, cross-checked against the
`api_calls>2` proxy already visible in k=1). Predict round trips concentrate
in section E (4-5 of 5) and, newly, in sections A/B where the k=1 map
(class 1 of 9 only) leaves real gaps against canonical facts that
`open_note` can now fetch directly (e.g. `memory/offers.md`,
`memory/positioning.md`) instead of nothing. Sections C/D predicted to stay
mostly direct (open_loops.md and current_priorities.md already arrive via
existing `current_commitment`/`episodic_activity` retrieval routes per the
k=1 manifests).

**Latency added per round trip:** predict round-trip questions average
**35-55s**, direct questions stay near the k=1 direct-question mean of
~17s -- i.e. a round trip adds roughly **+20-35s** over a direct answer,
consistent with the pre-existing high-`api_calls` questions in k=1 (mean
44.2s) which already paid a similar tax without these tools.

**What this implies about map size, predicted before seeing it:** if the
round-trip rate lands in the predicted 32-56% range with §E holding at or
above baseline, that is evidence the k=1 map is UNDER-sized for sections
A/B specifically (real gaps a tool must now cover one file at a time) while
being adequately sized for the historical-call material in §E (which was
never a map-growth candidate -- raw transcripts don't belong in a token
budget prefix). It would NOT by itself argue for regrowing the map past
k=1, because Step 5's own stopping rule (incremental B7 gain vs. the 4.0pp
noise allowance) already tested that and stopped; it would instead argue
that Step 6's tools are doing the job Step 5 deliberately left to them.
