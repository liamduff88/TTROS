# STEP U-CLOSE — step6_post full tool-surface verification (input + output)

Run date: 2026-09-08. **No previous `scripts/step6_post_full_tool_surface_verification.md` existed
before this session** (checked first; none found) — nothing here is reused from an earlier
argument-only pass. **Model/Hermes/David/provider calls made by this session: 0.** The only
non-Python command executed against Hermes was `hermes --version` (local metadata printout, no
model/API call, confirms the live binary is v0.21.1 — not a B7 invocation, direct or subprocess).
No B7 pass was re-run. No harness question, scorer, guard, hook, profile config, or memory setting
was changed. `docs/ttros/SOURCE.sha256` recomputed against all five mirrors before use — all match.

---

## Part A — precondition: do the stored records retain OUTPUTS, or only arguments?

**Outcome: outputs are stored for every read-capable call in step6_post.**

The 25 `scripts/step6_b7_pass_*.usage.json` files give each question's own `session_id` (written
by the harness itself, not inferred). Each `session_id` resolves in
`~/.hermes/profiles/david/state.db`'s `messages` table, which stores, per row: `role`
(`user`/`assistant`/`tool`), `tool_calls` (the assistant's JSON tool-call list, arguments included),
and `content` (for `role='tool'` rows, the actual returned result). This is the same structure and
the same store the prior `scripts/b7_contamination_map_and_clean_subset.md` used.

Measured directly, not assumed: **46 of 46 tool calls across all 25 step6_post sessions have a
non-empty stored `content` field on their matching tool-role response — 100.0% output-retention
coverage.** Zero missing sessions, zero missing outputs. `step6_b7_pass.raw.json` (the harness's own
output artifact) does **not** itself contain a tool trace — it stores per-question `manifest.actual_reads`
(declared-source identities) and the final `answer`, not the call-by-call trace — so `state.db` is the
only, and a sufficient, source for this check. This licenses the full two-sided check in Part D; it
is not a partial-coverage or vacuous result.

---

## Part B — predictions (written before the corrected detector ran)

Recorded verbatim, before running the corrected Part D detector (a first, flawed detector run
preceded this — see the note in Part D):

- Distinct tool names: predicted 6–9, drawn from `mcp__brain__{open_note,open_call,search_calls,search_history}`,
  `skill_view`, `search_files`, `execute_code`. Not known in advance whether `terminal`/`process_manage`
  appear at all in step6_post itself.
- Read-capable: all four `mcp__brain__*` tools, `skill_view`, `search_files`, `execute_code`, and
  `terminal`/`process_manage` if present. Not read-capable: any pure-write or fixed-status tool.
- Output-retention coverage: predicted ~100%.
- Contaminated records expected: 0 — **carried forward from the prior audit's own finding, not an
  independent blind guess.** This is stated plainly rather than presented as first-look prediction.

---

## Part C — tool surface enumerated from the records (not a hardcoded list)

Enumerated directly from the 46 tool calls found in the 25 step6_post sessions' `tool_calls` /
`tool_name` fields — **7 distinct tool names, exactly as they appear in the stored data:**

| Tool | Read-capable? | Why |
|---|---|---|
| `mcp__brain__open_note` | Yes | Reads a named Business Brain vault note, returns its content. |
| `mcp__brain__open_call` | Yes | Reads a historical call transcript, returns its content. |
| `mcp__brain__search_calls` | Yes | Searches the historical-call corpus, returns matching content. |
| `mcp__brain__search_history` | Yes | Searches the Business Brain vault, returns matching content. |
| `search_files` | Yes | Generic filesystem content/path search — the confirmed leak vector in Step 3/5. |
| `execute_code` | Yes | Arbitrary code execution with filesystem access. |
| `skill_view` | Yes | Reads a named skill definition's content. |

**`terminal` and `process_manage`: both absent from step6_post's actual 46-call surface.** Neither
was invoked in any of the 25 step6_post sessions. This was checked directly against the enumerated
tool names, not assumed from the guard's blocked-list history.

Per the task's instruction not to classify `process_manage` from its name alone: its schema was read
directly from the live v0.21.1 install (`~/.hermes/hermes-agent/tools/process_registry.py`,
`PROCESS_SCHEMA`, read-only, zero model calls) — `process_manage`'s `log`/`poll`/`wait` actions
retrieve the accumulated stdout of a background process started by `terminal(background=true)`
("log: full output, paged"). It is read-capable by contract: a background `terminal` call naming a
blocked path (e.g. `cat scripts/step3_b7_harness.py &`) followed by `process_manage(action="log")`
would surface that content, exactly the residual gap the guard's 2026-09-08 comment describes.
**This is a live capability confirmed for the tool as it exists — it is not evidence that step6_post
was exposed through it, since step6_post never called it.**

**What a hardcoded list would have missed:** the four `mcp__brain__*` tools were not on the guard's
original `BLOCKED_TOOL_NAMES` list (that list only ever named generic filesystem/session tools) —
had this verification checked only the guard's list, it would have silently skipped 34 of the 46
calls in step6_post (every `mcp__brain__*` and `skill_view` call), because those tools were never
suspected, not because they were shown safe. Enumerating from the records themselves is what put
them in scope.

---

## Part D — the two-sided check

**Note on method correction, reported plainly:** a first version of this detector used harness-doc
prose lines and scorer `kw()` keyword literals as "content signatures." It produced 29 false-positive
hits (e.g. `"forward-deployed"`, `"measurable outcome"`, `"client's own"`) — all of it real, legitimate
content independently present in `memory/offers.md` / `memory/positioning.md`, because the harness
doc's fact descriptions and the scorer's keyword groups both paraphrase the same real vault
vocabulary the questions correctly retrieve. This is exactly the false-positive class the task's own
Part D warning names ("ordinary business search terms match the answer key incidentally"). The
detector was rebuilt on two narrower, structural signal classes instead:

1. **Path signatures** — literal filenames/paths of the harness doc, the three scorer scripts, any
   pass's `.raw.json`/`.scored.json`/`.transcript.txt`, or the `ttros_backups` preimage — checked in
   both the call arguments and the call's returned output text.
2. **Structural/meta signatures** — text that is part of the harness document's or scorer's own
   scaffolding and would not appear in genuine business content: the document's own title/section
   headers, the literal `Trap:` framing sentence, scorer code identifiers (`def score_pass`,
   `QUESTIONS = [`, `FACT_SOURCE_OVERRIDES`, `honesty=True,` / `honesty=False,`, `fail_if=`), and this
   task-family's own classification vocabulary (`MATERIAL_CONTAMINATION`, `TEST_MATERIAL_EXPOSED`).
3. **Cross-session leak** — checked structurally, not by fuzzy text match: whether any call's
   argument or output embeds a *different* step6_post question's own opaque `session_id` token
   verbatim. (A first version of this sub-check also used fuzzy 40-character substring matching
   against other questions' final answers and produced false positives from shared legitimate source
   documents — `company.md`, `INDEX.md` — that multiple questions independently and correctly cite.
   Session-ID strings are random per-run tokens with no legitimate reason to appear in unrelated
   content, so matching on the token itself removes that false-positive class entirely.)

**Result on the real, unmodified records: 0 of 46 tool calls hit on either side, and 0 cross-session
leak markers.** `step6_post` never invoked `session_search` at all (absent from Part C's enumerated
surface), so the leak *mechanism* the prior audit found elsewhere is structurally unavailable to it,
independent of the content check. Full per-call detail (all 46 calls, arguments/outputs/hits) is in
`scripts/step6_post_full_tool_surface_verification.json` and the teed transcript
`scripts/step6_post_full_tool_surface_verification.txt` — not pasted here.

---

## Part E — rehearsing the failing case, both directions

Performed on a **synthetic copy** of session `20260907_134442_11b488` (question A1)'s real calls,
written to the session scratchpad only (`/tmp/.../scratchpad/synthetic_copy_A1.json`), never to the
repo or `state.db`, and **deleted immediately after the rehearsal**:

1. **Argument-side positive:** injected `arguments = {"pattern": "ICP-A", "path":
   "scripts/step3_b7_harness.py"}` into one call. **Detected:** `PATH_SIG:step3_b7_harness.py`.
2. **Output-side positive, innocuous argument:** injected `arguments = {"pattern": "revenue target",
   "target": "content"}` (an ordinary business-term grep, no suspicious path) but set that call's
   `output_content` to include the literal harness text `"Trap: this is Mike's advice, not Liam's
   stated intention -- the vault records Liam as reluctant to niche down."`. **Detected on the output
   side** (`CONTENT_SIG:Trap: this is Mike's advice...`), confirmed the argument side alone stayed
   clean — proving the detector catches output-only exposure, not just suspicious arguments.
3. **Cross-session leak structural check:** injected a foreign session-id string into a call's
   output. **Detected:** `CROSS_LEAK_SESSION_ID_OF_X1:...`.
4. **Negative control:** the same session's real, unmodified calls were re-scanned immediately after
   — **zero hits**, confirming the detector isn't just permanently primed to fire.

All four assertions passed programmatically (script exited 0 with `ALL REHEARSALS PASSED`); the
synthetic copy was deleted immediately afterward. This satisfies the task's requirement that a
zero-contamination verdict not be trusted before the detector is shown capable of a non-zero result,
in both directions (argument-side and output-side-despite-innocuous-argument).

---

## Part F — verdict

**step6_post is CLEAN on its full enumerated tool surface (7 tools, 46 calls), on both the argument
and output side, at 100% output-retention coverage.**

What this PASS licenses:
- Every tool call step6_post's 25 sessions actually made, and everything each of those calls
  returned, was inspected — not sampled — for harness/scorer material and for cross-session leakage,
  and none was found.
- The specific gap STEP U found in the guard (`terminal`/`process_manage` never blocked) did not
  cause exposure in step6_post specifically, because step6_post never invoked either tool. This is a
  narrower and more defensible claim than "the gap didn't matter" — it only didn't matter *here*, on
  this historical pass, on the record as taken.
- The `mcp__brain__*` tools' Business Brain vault scoping (confirmed by the prior audit and
  unaffected by this check) plus the absence of `session_search` mean step6_post's clean result does
  not depend on inferred good behavior — it is verified content-by-content and structurally, on both
  input and output.

What this PASS does **not** license:
- It does not establish that a *future* B7 pass would be clean by design — `search_files` and
  `execute_code` remain generically capable and were not path-restricted at the time step6_post ran;
  a future pass's cleanliness still depends on where its own queries happen to land, exactly as the
  prior audit already concluded (§11, "DEPENDS ON, not CLEAN by design").
- It does not prove no contaminating activity occurred through any channel outside the 46 stored
  tool calls in `state.db` — this is the complete stored record for these 25 sessions, not a claim
  about unrecorded activity.
- It does not re-open or re-score anything — no B7 pass was run, no scorer or fact list was touched.

---

## Closeout

- **Is step6_post clean?** Yes — 0 of 46 tool calls, both sides, 100% output coverage.
- **Tool surface:** 7 tools enumerated from the records (`mcp__brain__open_note`,
  `mcp__brain__open_call`, `mcp__brain__search_calls`, `mcp__brain__search_history`, `search_files`,
  `execute_code`, `skill_view`). `terminal`/`process_manage`: confirmed absent from step6_post's
  actual calls; confirmed read-capable by live tool-contract inspection, not by name.
- **What enumeration found that a hardcoded list would have missed:** the four `mcp__brain__*` tools
  plus `skill_view` (34 of 46 calls) were never on the guard's blocked-list history and would have
  been skipped by a check that only re-checked the guard's own list.
- **Rehearsal:** both directions proven capable of a non-zero result, plus a negative control,
  before the real zero was trusted. Synthetic copy deleted.
- **Files touched:** `scripts/step6_post_full_tool_surface_verification.py` (new, throwaway
  instrument), `.txt` (teed transcript), `.json` (structured per-call output), this report (new).
  No repo file outside `scripts/` was modified by this part of the step.
- **Model/Hermes/provider calls: 0.**
- **Protected areas (`connectors/`, `workspaces/north_shore_sales_coach/`, credential stores):
  untouched.**
