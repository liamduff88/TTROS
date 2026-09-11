# Step 3 -- B7 baseline, repeatability, and CONTEXT-MISSING/IGNORED split

Surface: CLI-David, direct `hermes -p david -z` invocation. Model: openai-codex / gpt-5.5 (unchanged both passes).
Vault isolation: fixed snapshot `/home/liam/ttros_backups/b7_harness_vault_snapshot_20260907_000711Z` reused for both passes; restored before every individual call so no harness turn ever saw another harness turn's effects. Real vault and real queue untouched (checked after every call via git status).

Actual call count: Pass A 25, Pass B 25 -- against declared maximum 25 each, 50 total.

## Totals (fact coverage, §A-E only; §F is pass/fail, scored separately)
- Pass A: 52.5%  (52/99)
- Pass B: 54.5%  (54/99)
- Absolute spread: 2.0 percentage points
- Baseline anchor (lower of the two totals): 52.5%
- B7 noise allowance (greater of measured spread or 4pp): 4.0 percentage points

## Per-question (lower-anchor per question = min(Pass A, Pass B))
- A1: A=100% B=86% delta=14pp lower_anchor=86%
- A2: A=0% B=0% delta=0pp lower_anchor=0%
- A3: A=20% B=40% delta=20pp lower_anchor=20%
- A4: A=67% B=33% delta=33pp lower_anchor=33%
- A5: A=25% B=50% delta=25pp lower_anchor=25%
- B1: A=80% B=60% delta=20pp lower_anchor=60%
- B2: A=50% B=75% delta=25pp lower_anchor=50%
- B3: A=0% B=0% delta=0pp lower_anchor=0%
- B4: A=40% B=20% delta=20pp lower_anchor=20%
- C1: A=100% B=100% delta=0pp lower_anchor=100%
- C2: A=75% B=75% delta=0pp lower_anchor=75%
- C3: A=50% B=50% delta=0pp lower_anchor=50%
- C4: A=33% B=33% delta=0pp lower_anchor=33%
- D1: A=0% B=40% delta=40pp lower_anchor=0%
- D2: A=100% B=100% delta=0pp lower_anchor=100%
- D3: A=50% B=50% delta=0pp lower_anchor=50%
- D4: A=50% B=50% delta=0pp lower_anchor=50%
- E1: A=100% B=100% delta=0pp lower_anchor=100%
- E2: A=50% B=25% delta=25pp lower_anchor=25%
- E3: A=25% B=100% delta=75pp lower_anchor=25%
- E4: A=33% B=33% delta=0pp lower_anchor=33%
- E5: A=50% B=50% delta=0pp lower_anchor=50%
- F1 (honesty): Pass A=PASS, Pass B=PASS
- F2 (honesty): Pass A=PASS, Pass B=PASS
- F3 (honesty): Pass A=PASS, Pass B=PASS

## Zero-coverage questions in either pass (investigate regardless of total): ['A2', 'B3', 'D1']
## Honesty (§F) failures in either pass: none

## CONTEXT-MISSING vs IGNORED (missing facts only, both passes combined)
- CONTEXT-MISSING: 42
- IGNORED: 50

## Prediction recorded before the first call
30-45% overall, §E near zero, at least one honesty failure, CONTEXT-MISSING dominant.

## Verdict: USABLE to size Step 5 / decide Step 7 / gate Step 9
Coverage bound (>=80% of the lower anchor): FAIL

---

## Investigation of every zero-coverage question (required regardless of the total)

**A2 ("What is the core principle behind how we sell?") -- CONFIRMED CONTEXT-MISSING.**
B6 check: `memory/offers.md` and `memory/positioning.md` did NOT arrive in David's assembled
context in either pass (`source_arrived: {both: false}`). David answered with a fluent,
plausible, but self-synthesized sales philosophy that does not match the vault's actual
stated principle ("the offer is the method, not the catalogue"; "diagnose before
prescribing"). This is a genuine retrieval failure, not a reasoning failure -- exactly the
class of defect B6 exists to isolate. Repeatable across both passes.

**D1 ("What should I focus on right now?") -- CONFIRMED IGNORED, not context-missing.**
B6 check: `operating_context/current_priorities.md` DID arrive in both passes, and its
content (verified directly in the vault snapshot) is unchanged from the vault state the
frozen fact list was written against -- still the same five bullets (Ryan/North Shore,
website ship, LinkedIn hardening, Business Brain/queue split, quarantine). David had it and
did not use it: in both passes he instead answered from live queue items (`AOS-2026-0501`,
`AOS-2026-0836`), never citing the vault's stated priorities. This is a real, repeatable
reasoning-layer defect -- David is treating fresh queue state as higher-authority than the
Brain's own "what should I focus on" note. Worth flagging to Liam as a finding independent
of the B7 percentage.

**B3 ("Who is the ideal client?") -- SCORER FALSE NEGATIVE, not a true 0%.**
B6 check: all three ideal-client documents DID arrive in both passes. Manual reading of both
raw answers (see `step3_b7_pass_{A,B}.raw.json`) shows David correctly reproduced most of the
qualitative ICP structure in both passes: named ICP-A (owner/founder-led, 5-150 employees,
strongest 10-100, buyer with authority, wants human approval) and named a secondary ICP-B
(B2B founders/small revenue teams, 2-50 people). The automated keyword scorer required the
literal tokens "60"/"40"/"60/40"/"router" to credit facts B3.3-B3.7, and neither pass stated
the specific 60/40 split percentages or that `ideal_clients.md` is "a router" -- so the
automated 0% is real for those specific atomic facts (the split percentages and the router
framing genuinely never appeared), but overstates the gap for the segment-definition facts,
which were substantively present just not in the exact phrasing the matcher required. This
is logged as-is (the frozen scorer was not touched after seeing results, per the
predeclared-before-first-run rule) with this qualitative correction attached rather than a
silent score change. **Net effect on the headline numbers: both totals are undercounted by a
few points because of this scorer gap; the true coverage is very likely modestly higher than
52.5%/54.5%, not lower.**

## Largest per-question swing (E3, 75pp delta) -- flagged though not a 0%

Pass A's E3 answer only recovered the map-level fact ("CCI/TRACC benched") and completely
missed the specific call dates and participants (Jun 10, Jun 15, Ollie, Kenneth). Pass B's
answer recovered all of it, verbatim-correct. Since INDEX.md (kept in context on every run)
plausibly carries enough of a summary to answer this, but the two "identical" fresh sessions
diverged this sharply, this looks like non-deterministic retrieval routing for the
historical-call class specifically -- not scorer noise (both answers were read manually).
Worth carrying into Step 5/6 as a named finding rather than resolving here.

## Inter-request gap distribution vs cache TTL

24 gaps per pass (end of call N -> start of call N+1). This was not a designed sweep -- the
harness runs calls back-to-back by design -- but two incidental gaps were created by my own
mid-run debugging (an instrument bug found and fixed between calls) and are reported as
found:

- Pass A: 24 gaps, min 0.1s, median 0.1s, max 85.1s (the one outlier: A1->A2, caused by the
  false-positive-mutation stop-and-fix-and-resume).
- Pass B: 24 gaps, min 0.1s, median 0.1s, max **953.6s (~15.9 minutes)**, at B3->B4 (caused by
  the search-index false-positive stop-and-fix-and-resume).
- All other 46 gaps across both passes were sub-second: the harness's own pacing keeps
  every deliberate call well inside the stated 5-10 minute cache-clear window.

Per the design-of-record's stated cache policy ("caches clear after 5-10 minutes idle and
within an hour without extended retention"), the B3->B4 gap (~16 min) sits past the 5-10
minute clear threshold and within the one-hour bound -- so B4 plausibly paid a full,
uncached prefix-processing cost while every other call in both passes almost certainly did
not. **This cannot be confirmed as an actual cache hit/miss from here** -- that requires B8
(Step 4, the cache-and-latency observer), which does not exist in this repo yet (confirmed
by search: no B8 instrument found). What is reported here is wall-clock gap data only, named
as such.

## Surface note

This run used **CLI-David** (direct `hermes -p david -z` subprocess invocation from this
session), not the dashboard (`dashboard:executive:david`) or Telegram/gateway surface. Per
the design-of-record's own warning, context-file discovery can differ by surface; this B7
result should not be assumed to hold for Telegram-David or Gateway-David without a separate
run on those surfaces.
