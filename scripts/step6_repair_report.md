# Step 6 repair -- result

Repair of the Step 6 RED result in `scripts/step6_report.md` (B7 §E = 58.3% vs.
required ≥70%). ZERO David/Hermes model calls used. Diagnosis was done entirely
by reading the frozen `scripts/step6_b7_pass.{raw,scored}.json`, querying
David's own session history read-only (`~/.hermes/profiles/david/state.db`),
and inspecting the live search index (`search/os_index.db`) and vault files
read-only. Per the task's instruction, B7 was NOT re-run.

## Verdict: NEEDS ATTENTION (Step 6 remains RED pending a fresh, explicitly
approved B7 pass) — see "Addendum 2026-09-07T19:07:31Z" at the end of this file
for the follow-on repair that fixed the operator-lean tool-contract regression
this report originally left open, restoring the full suite to 772/0.

One genuine, general retrieval defect was found and fixed. It cannot by
itself be proven to move §E to ≥70% without a new 25-call B7 pass, which this
repair is explicitly not authorized to spend. A second, unrelated, pre-existing
regression against the 772/0 test baseline was also found (not caused by this
repair) and is reported, not fixed, because fixing it is a policy call about
a fail-closed safety-bounded profile, not a mechanical bug fix.

## Root cause (the one fixed)

`tools/aos_indexer.py::document_from_path()` ran a whole-document veto,
`SECRET_CONTENT_RE` (`api_key|authorization|bearer|password|private_key|
credential`), against the entire raw file text. Any single incidental match
anywhere in a file caused the *whole document* to be silently dropped from
the FTS index used by the four new `mcp__brain__*` tools -- no error, no log,
counted only as an undifferentiated "skipped" number.

This veto was redundant with, and strictly more destructive than, the
line-level scrub the same function already runs on the retained body
(`sanitize_text()` / `SENSITIVE_LINE_RE`, a strict superset of the same
keywords plus "secret"/"token"/"north_shore"). Line-level scrubbing already
removes any individual secret-bearing line before indexing; the whole-document
veto added no protection beyond that and only produced false-positive total
data loss when a long-form conversational transcript happened to use one of
these words in ordinary English with no actual secret nearby.

Confirmed concretely: `sources/historical_calls/andrea-roberts-june-26.md`
(the Jun 26 Andrea Roberts call -- required source for B7 E5) contains the
word "password" once, in casual conversation about a government website, and
`sources/historical_calls/meeting-ken-stanick.md` contains "authorization"
once, similarly casual. Both files were completely absent from
`search/os_index.db` as a result -- confirmed by direct query -- and
therefore could never be returned by `search_calls`/`search_history`/
`open_call` regardless of David's query. Traced David's actual E5 session
(session `20260907_110402_96d8f5`, read-only): he ran three
search_history/search_calls queries including `"Andrea Roberts"`, and the
tool's own returned match list never contained the Jun 26 file in any of the
three calls. This is a retrieval-surface miss, not a query or model-behavior
problem.

## Per-miss classification (all 10 of §E's missing facts)

- **E5.1 (Jun 26 + Jun 30 dates) -- RETRIEVAL MISS.** Fixed (see below). The
  Jun 30 half of this fact was already stated correctly in the answer; only
  the Jun 26 half was unretrievable, because its source file was never in the
  index.
- **E2.1, E2.2, E2.4, E3.1, E3.2, E4.1, E4.3, E5.3 (8 facts) -- correct
  evidence returned, David omitted/underused it.** Verified per-question via
  the session tool-call trace: in every one of these cases the exact source
  file named in the question's `source_docs` was opened successfully
  (`mcp__brain__open_call`/`open_note`) in that question's own session. E5's
  answer even correctly uses "Jun 30" and describes Mike's "consultant happy
  hour" event in Vancouver -- from the very file that was opened -- but never
  writes the literal words "Vancouver" or "event" the frozen scorer requires.
  This is a narrative-answer-style vs. frozen-keyword-scorer mismatch, not a
  retrieval or tool defect. Per the task's explicit instruction, no code
  change was made for these 8 facts -- doing so would mean hardcoding
  question-specific wording.
- **E5.4 ("the parked candidate bullet understates this") -- structurally
  unretrievable by design, not a Step-6 defect.** The only vault text
  resembling a "parked candidate bullet" for Andrea's introductions is in
  `MANIFEST.md`, which is intentionally excluded from
  `tools/aos_indexer.py` search by the existing client-scope registry gate,
  per the F-BRAINNOTES-1 filter already documented in `MANIFEST.md`'s own
  header. Reopening that filter is out of this repair's scope and would risk
  the contamination it exists to prevent. No code change made.

## Fix applied

`tools/aos_indexer.py`, `document_from_path()`: removed the 2-line
whole-document `SECRET_CONTENT_RE` early return. The narrower, already-broader
line-level `sanitize_text()`/`SENSITIVE_LINE_RE` scrub is unchanged and
continues to strip any individual secret-bearing line before it reaches the
index. `SECRET_PATH_RE` (filename-based exclusion) and all other exclusion
logic (`is_excluded`, `PROTECTED_SEGMENTS`, `PROTECTED_PATH_PARTS`, the
client-scope registry gate) are untouched. This is a general fix to the
shared retrieval instrument Step 6 reuses, not a B7-specific patch -- no
question wording, date, or literal phrase was hardcoded anywhere.

Rebuilt `search/os_index.db` via the existing `tools.aos_indexer.scan()` entry
point (no new script). Result: `sources/historical_calls/andrea-roberts-
june-26.md` and `sources/historical_calls/meeting-ken-stanick.md` are now
indexed (16/17 files under `sources/historical_calls/`; `MANIFEST.md` remains
correctly excluded by design). Verified read-only: a search for
`"Andrea Roberts"` now returns the Jun 26 file; a search for the literal word
"password" against the live index returns 0 hits (the sensitive line is still
scrubbed, only the rest of the document is no longer destroyed).

## What this fix does and does not establish

It repairs the confirmed retrieval-surface defect that made the Jun 26 file
unreachable. It does **not** by itself prove E5.1 will score PRESENT on a
future pass -- that also requires David to open the now-discoverable file and
state "Jun 26" literally in his answer, which is model behavior this ZERO-call
repair cannot test. Per the task's explicit instruction, no B7 pass was run to
check this.

## Step-6 diagnostic evidence (B6 limitation, recorded not fixed)

Confirms and extends the finding already recorded in `scripts/step6_report.md`:
B6's CONTEXT-MISSING/IGNORED split reads only the initial context-assembly
manifest's declared `sources`, so it cannot see a source a Brain-MCP tool
fetched mid-turn. This repair's own tracing shows the practical effect: for
E4, all three correct source files were opened via `open_call` mid-session,
yet every missing E4 fact is labeled CONTEXT-MISSING (not IGNORED) purely
because none of E4's declared `source_docs` happened to also be in the
Step-5 k=1 map -- an artifact of manifest-only bookkeeping, unrelated to
whether the tool actually fetched the content. B6 is not redefined here; this
is recorded as Step-6 diagnostic evidence per the task's instruction, for `00`
at the next opportunity.

## Unrelated pre-existing regression found (not fixed, out of this repair's scope)

Full regression suite: **771 passed / 1 failed** (772 total collected,
matching the declared baseline count) both **before and after** this repair's
one-line fix -- confirmed by reverting `tools/aos_indexer.py` to its
pre-repair state and re-running the single failing test, which failed
identically. **This regression is not caused by this repair.**

Failing test: `tests/test_telegram_conversational_routing.py::
TelegramConversationalRoutingTests::
test_live_loaded_operator_preamble_has_exact_bounded_tools_under_budget`.

Cause: Step 6's *original* change added four tools
(`search_calls`/`open_call`/`open_note`/`search_history`) to the shared
`tools/brain_memory_mcp.py` server. That same server file is also registered
under the **`operator-lean`** Hermes profile (`~/.hermes/profiles/
operator-lean/config.yaml`), a separate fail-closed bounded-tool surface
whose `tools/operator_lean_oneshot.py::EXPECTED_TOOLS` allowlist hard-fails
(exit 78 / RuntimeError) on any tool-set mismatch, by design. Adding the four
tools to the shared server silently widened `operator-lean`'s live tool
surface beyond its declared, safety-bounded contract -- a blast-radius leak
from David's intended scope into a different, more tightly bounded profile.

This is a genuine Step-6 defect, but fixing it means making a policy decision
(should `operator-lean` gain these four read-only tools too, or should they
be scoped away from that profile) about a fail-closed safety boundary, not a
mechanical bug fix. Per CLAUDE.md rule 7 ("record unrelated findings without
expanding scope") and rule 5 (stop for anything the step didn't
pre-authorize), this repair does not touch `operator_lean_oneshot.py` or
`brain_memory_mcp.py`'s registration and instead reports it for Liam's
decision.

## Targeted tests

`tests/test_aos_search.py`, `tests/test_business_brain_search_scope.py`,
`tests/test_business_brain_full_loop.py`, `tests/test_business_brain_context.py`
-- 16/16 passed, including the existing secret-content test
(`test_business_brain_is_read_only_and_no_secret_content_surfaces`), which
still passes because the secret line is still line-scrubbed, not because the
whole document is dropped.

## Files touched

- `tools/aos_indexer.py` -- the fix (2 lines removed, nothing else)
- `search/os_index.db` -- rebuilt derived index (untracked, not a vault write)
- `scripts/step6_repair_transcript.txt` -- exact change/rollback, written
  before the edit
- `scripts/step6_repair_report.md` -- this file
- Backup (pre-edit preimage): `/home/liam/ttros_backups/step6_repair_20260907T184435Z/aos_indexer.py`

## Next action

Stop and wait, per the task's instruction: Step 6 remains RED. A new,
explicitly approved 25-call B7 verification budget is required before Step 6
can be declared green -- the frozen B7 contract requires a fresh pass for
comparable revalidation, and the prior Step-6 25-call budget is already
consumed. Separately, Liam should decide whether `operator-lean`'s bounded
tool contract is intentionally widened to include the four new brain tools
(update `EXPECTED_TOOLS`) or whether those tools need to be scoped away from
that profile -- this is unrelated to §E and was not touched here.

---

## Addendum 2026-09-07T19:07:31Z — operator-lean tool-scoping fix, 772/0 restored

ZERO David/Hermes model calls used. B7, Step 6b and Step 7 were not run.

### Root cause

`tools/brain_memory_mcp.py` is one shared `FastMCP("brain")` server. Every
Hermes profile's `config.yaml` (`david`, `aos-delivery`, `aos-marketing`,
`aos-ops`, `aos-orchestrator`, `aos-revenue`, `operator-lean`) points its
`brain` `mcp_servers` entry at this exact same script, with no per-profile
scoping. Step 6 registered its four new tools (`search_calls`/`open_call`/
`open_note`/`search_history`) unconditionally on that shared server, so every
profile's client saw them -- including `operator-lean`, a separate, fail-closed,
safety-bounded surface whose exact 9-tool contract
(`operator_lean_oneshot.py::EXPECTED_TOOLS`) does not include them.
`require_operator_tools()` correctly rejected the resulting 11-tool snapshot as
an unexpected-tool-set mismatch (fail-closed, exit 78), which is what made
`tests/test_telegram_conversational_routing.py::
test_live_loaded_operator_preamble_has_exact_bounded_tools_under_budget` fail:
771 passed / 1 failed, matching the task's stated starting point.

### Fix applied (generic, no per-question or per-profile-name hardcoding of
scorer content)

1. `tools/brain_memory_mcp.py` -- gated the four depth tools behind a single
   explicit opt-in read once at import, `AOS_BRAIN_DEPTH_TOOLS` (env var:
   `"1"`/`"true"`/`"yes"`). Unset/false (the default for every profile that
   does not ask for it): only `remember_brain_knowledge` and
   `brain_memory_status` register, exactly the pre-Step-6 surface --
   `operator-lean`'s `EXPECTED_TOOLS` is untouched and not widened. True:
   all six tools register, unchanged from Step 6. This is a generic capability
   flag any MCP client config can set via the existing
   `mcp_servers.<name>.env` mechanism (confirmed in
   `~/.hermes/hermes-agent/tools/mcp_tool.py`, which already reads
   `config["env"]` for stdio MCP servers) -- not a new mechanism, not a patch
   to Hermes.
2. `~/.hermes/profiles/david/config.yaml` (live profile config, not a repo
   file, not a protected path) -- added `env: {AOS_BRAIN_DEPTH_TOOLS: "1"}`
   under the existing `mcp_servers.brain` entry. David is the one profile the
   design of record calls for here (`TTROS_BUILD_PLAN_..._rev11.md` "Step 6 --
   corpus and vault behind tools" is framed entirely around David; separately,
   `install_hermes_context_assembler.py::PERSONAL_PROFILES = ("david",)`
   already singles David out for Brain-adjacent capability checks). No other
   profile's config was touched -- `operator-lean` and the five `aos-*` worker
   profiles keep the pre-Step-6 two-tool surface, which nothing in the design
   or the test suite asks them to have.
   `context_file_max_chars: 40000` and every other line in david's config are
   unchanged.

Verified directly (zero model calls, no Hermes process): importing
`brain_memory_mcp` with `AOS_BRAIN_DEPTH_TOOLS` unset registers exactly
`{brain_memory_status, remember_brain_knowledge}`; with it set to `1`,
registers all six, including `open_call`, which round-tripped
`sources/historical_calls/andrea-roberts-june-26.md` correctly (confirming the
earlier indexer fix and this fix compose without conflict).

### Second fix -- Step-6 tool-result path (result-shaping defect, requested by
this task's instruction to look for a general reason David may underuse
retrieved evidence)

`tools/aos_indexer.py::search()`/`public_row()` already computes and returns a
`snippet` field (a plain, non-secret content preview) for every matched
document, but `brain_memory_mcp.py::search_calls()` and `search_history()`
discarded it when building their `matches` list -- callers saw only
`call_id`/`pointer`/`title`/`modified`, never any of the document's actual
text. That forces David to guess which of several same-named-entity candidates
actually contains a given fact and then open the full document (up to 60,000
chars via `open_call`/`open_note`) to locate it by reading, with no pointer to
where in the document the fact lives -- a generic mechanism, independent of
any specific question, under which an exact date or named entity can be read
past without being reproduced verbatim in the final answer. This matches the
task's own diagnosis that in 8 of §E's 10 misses the correct source was opened
successfully but the exact fact was still omitted.

Fix: added `"snippet": m.get("snippet")` to both tools' per-match dict. No new
computation, no keyword table, no question-specific logic -- reuses a field
the shared indexer already produces for every query, for both this instrument
and any other current or future consumer of `aos_indexer.search()`.

This is offered as a plausible generic contributor, not a proven cause -- per
the task's explicit instruction, no B7 pass was run to test whether it moves
§E. It does not touch retrieval (which document is found), only what is
visible about a found document before a full open.

### Preserved unchanged

Step-5 map / `.hermes.md`; `context_file_max_chars` (40000, david); old ranker
flag; David = `openai-codex` / `gpt-5.5`; B6 definition; Hermes unforked/
unpatched; `operator-lean`'s `EXPECTED_TOOLS` (9 tools, untouched);
`tools/aos_indexer.py`'s earlier one-line fix from this file's original
report.

### Files touched (this addendum)

- `tools/brain_memory_mcp.py` -- opt-in gate for the 4 depth tools; `snippet`
  added to `search_calls`/`search_history` results.
  Backup: `/home/liam/ttros_backups/step6_operator_lean_repair_20260907T190731Z/brain_memory_mcp.py.orig`
- `/home/liam/.hermes/profiles/david/config.yaml` -- added
  `mcp_servers.brain.env.AOS_BRAIN_DEPTH_TOOLS: "1"`.
  Backup: `/home/liam/ttros_backups/step6_operator_lean_repair_20260907T190731Z/david_config.yaml.orig`
- `scripts/step6_repair_transcript_2.txt` -- exact change/rollback, written
  before editing.
- `scripts/step6_repair_report.md` -- this addendum.

### Targeted tests

`tests/test_telegram_conversational_routing.py` -- 24 passed, 5 subtests
passed (previously-failing operator-lean preamble test now passes: exactly 9
tools, none of the 4 depth tools present).
`tests/test_aos_search.py`, `test_business_brain_search_scope.py`,
`test_business_brain_full_loop.py`, `test_business_brain_context.py`,
`test_business_brain.py`, `test_business_brain_vault.py`,
`test_business_brain_scope.py` -- 27 passed, 8 subtests passed.

### Full regression result

**772 passed, 0 failed**, 195 subtests passed (354.02s) -- exact declared
baseline restored.

### Ready for a fresh B7 verification?

Yes, mechanically: the regression that would have contaminated a B7 run
(operator-lean's tool contract breaking) is fixed, and the earlier indexer fix
plus this addendum's two changes are all reused-instrument, non-hardcoded
repairs. Whether to spend a fresh, explicitly approved 25-call B7 budget now is
Liam's call, not this repair's -- it was not run and is not authorized by this
task.

### Blockers

None for this task's own scope. Open, for Liam's decision only: whether the
8-fact narrative-vs-frozen-keyword-scorer gap recorded in the original report
above needs a product decision (accept narrative answers as correct, or expect
David to mirror exact scorer phrasing) -- no code fix was made or is proposed
for that, since either direction is a policy call, not a defect.

### Next action

Stop and wait: Step 6 is mechanically ready, but declaring it green requires a
fresh, explicitly authorized B7 pass, which this task did not authorize and
this repair did not spend.
