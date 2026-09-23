# Step L1 — David latency decomposition (Dashboard route). MEASURE ONLY.

Surface: `dashboard/backend/main.py` → `_execute_named_profile_consultation("David","david",...)`
→ `assemble_model_context()` (pre-launch) → `_run_hermes_message()` → `_run_wsl_supervised()`
→ `tools/aos-hermes-coordinator.sh` → `hermes -p david --oneshot` → `hooks/context_assembler_hook.py`
(`pre_llm_call` / `post_llm_call`).

This document is written incrementally, in step order, so predictions are on record before any
instrumented or live result is seen.

---

## PHASE A — mined from existing evidence, zero model calls

**A1 — B8 status.** B8 (cache-and-latency observer) does **not exist** as a live/persistent
instrument on any surface. It exists only as a one-off **live exercise** run once on 2026-09-06:
`scripts/step4_b8_live_exercise.py` (3 live `hermes -p david -z` CLI calls, budget-enforced),
with outputs `scripts/step4_b8_observer.jsonl`, `scripts/step4_b8_live_exercise.txt`,
`scripts/step4_b8_transcript.txt`, `scripts/step4_usage_call{1,2,3}.json`. That exercise's own
JSONL records `"platform": "cli"` — it measured **CLI-David, not Dashboard-David**, and it is not
wired into the runtime as an ongoing hook. `hooks/context_assembler_hook.py` (the actual live
lifecycle hook) contains no latency/cache/B8 code. Per `00`, Step 4 (B8) is listed among steps
"not audited/re-certified" post-upgrade. **Conclusion: B8 is not reusable in usable form for this
step's surface; a new, temporary, additive instrument is required and is built in Phase B,
scoped only to this diagnostic.**

Exact paths searched: `hooks/context_assembler_hook.py`, `tools/*.py`, `scripts/step4_b8_*`,
`docs/ttros/*.md` (grep for `B8`).

**A2 — Locating the cedar-glass-482 turn.** Found in
`/home/liam/.hermes/profiles/david/state.db` (messages table, `content LIKE '%cedar-glass%'`):

- Turn 1 (the "stored" turn): session `20260913_150653_bde324`, user row content opens
  "Dashboard executive consultation. Answer the operator directly...", assistant reply "stored"
  plus a `<<<TTROS_THREAD` block recording the sentinel.
- Turn 2 (the recall turn, next turn): session `20260913_150729_b0a26f`, assistant reply contains
  `cedar-glass-482` — continuity worked.

Both sessions have `source='cli'` in the DB even though they are Dashboard turns — **the DB
`source` column does not distinguish Dashboard-invoked Hermes from raw CLI-invoked Hermes**,
because the Dashboard backend always shells out to the real `hermes` binary
(`tools/aos-hermes-coordinator.sh`). Dashboard turns are identified by session `title`
("Dashboard executive consultation…", "Answer executive dashboard consultation", "Answer operator
with David judgment") — an LLM-generated title, not a structural field. Likewise the assembler's
own `surface` field inside every `queue/context_assemblies/hermes-*.json` reads `hermes:cli` for
every single sample examined (35/35), Dashboard included — **`surface` as recorded is not a
reliable Dashboard-vs-CLI discriminator either.** This is itself a finding (see below).

Retention caveat (F-RETENTION-2) does not bite here: both `hermes-*.json` files for these two
sessions still exist on disk.

**A3 — Per-turn table.** 3 most recent *other* ordinary Dashboard-David turns identified by
session title pattern, ordered by `started_at` (most recent first):
`20260913_080104_ddcce3`, `20260912_080037_99a721`, `20260911_221326_c88616`.

| session_id | title | started_at (UTC epoch) | wall (ended−started, s) | PROVIDER ROUND TRIPS (assistant rows) | api_call_count (DB) | tool_call_count | in tok | out tok | cache_read | cache_write | reasoning tok | ctx total_bytes | ctx total_tokens | tool schemas attached | queue delta |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20260913_150653_bde324 | Answer executive dashboard consultation ("stored" turn) | 1789337214.336 | 15.469 | 1 | 1 | 0 | 22060 | 219 | 0 | 0 | 96 | 65443 | 14275 | no | none observed |
| 20260913_150729_b0a26f | Answer operator with David judgment (recall turn) | 1789337249.737 | 19.522 | 1 | 1 | 0 | 15922 | 249 | 4608 | 0 | 237 | 60153 | 12970 | no | none observed |
| 20260913_080104_ddcce3 | Executive consultation with David #3 | 1789311665.601 | 25.617 | 1 | 1 | 0 | 20556 | 882 | 0 | 0 | 122 | 59130 | 12909 | no | none observed |
| 20260912_080037_99a721 | Dashboard executive consultation. Answer the… | 1789225238.385 | 27.325 | 1 | 1 | 0 | 20637 | 912 | 0 | 0 | 236 | 61423 | 13231 | no | none observed |
| 20260911_221326_c88616 | Dashboard executive consultation #5 | 1789190007.439 | 23.179 | 1 | 1 | 0 | 17308 | 336 | 0 | 0 | 58 | 50301 | 10570 | no | none observed |

Notes:
- PROVIDER ROUND TRIPS = count of `role='assistant'` rows in `messages` for the session, per
  instruction (not `api_call_count`). For all 5 sampled turns the two agree (both = 1); the gap
  `api_call_count` is known to miss (the grace request after a cap) is **not observed in this
  sample** — recorded as absence-of-evidence, not proof it never happens (T6/T7 already showed
  1-vs-6 round trips on the same question elsewhere).
- "tool schemas attached": checked by loading the `request` string embedded in the matching
  `hermes-*.json` and searching for `"tools"`/`function`/`tool_choice`/`"schema"` — absent in all
  5. `sessions.tool_names` is NULL for all 5. Consistent with `tool_call_count=0` throughout.
- Context block set is **identical across all 5 turns** (15 named blocks: identity/company,
  current priorities, executive_view, deterministic morning findings, scoped canonical Brain
  notes, recent receipts and outcomes, relevant session recency, relevant open loops, relevant
  current commitments, matching skills/workflows, conversation summary, action boundaries,
  execution handoff contract, queue reference validity, provenance) regardless of how trivial the
  turn's actual ask is.
- Queue delta: not independently re-derived from `queue/work_items.jsonl` timestamps for the
  historical 5 (out of scope for a zero-model-call pass); the live turn in Phase C checks this
  directly per instruction C2/C3.

**A4 — Code path read from source (once).**
`dashboard/backend/main.py:_execute_named_profile_consultation()` (≈L4284) is the exact Dashboard
David entry point (called from the `/api/...` handler at L7952: `_execute_named_profile_consultation("David","david",text,request_id)`).
It:
1. Builds `consultation_prompt` (adds David-only handoff/thread clauses).
2. Calls `assemble_model_context(consultation_prompt, surface=f"dashboard:executive:{profile}", session_id=request_id, session_key=...)`
   — this is **not a separate lighter function**; `assemble_model_context` is imported directly as
   `from tools.context_assembler import assemble as assemble_model_context` (main.py:75). This is
   the *same* deterministic-assembly code the Hermes hook calls.
3. Calls `_run_hermes_message(assembled, profile="david", launcher=HERMES_COORDINATOR, ...)`
   (≈L4336), which writes the prompt to a temp file, shells out via `_run_wsl_supervised()`
   (plain `bash -lc`, no WSL-to-WSL re-hop) to `tools/aos-hermes-coordinator.sh`, and already
   captures `elapsed_seconds` = wall-clock of the **entire** coordinator subprocess
   (`time.monotonic()` around `Popen`+`communicate()`, main.py:1295/1322) — an existing,
   previously-uncollected-for-this-purpose timing value, reused rather than re-instrumented.
4. `aos-hermes-coordinator.sh`: validates the profile, resolves `~/.hermes/profiles/<profile>`,
   runs `step6_cost_control.py preflight` as a **separate python subprocess**, exports
   `AOS_STEP6_WRAPPED=1`, then runs `hermes -p david --usage-file ... --oneshot "$prompt"`
   (the real CLI, real provider round trip), then runs `step6_cost_control.py record-usage` as
   **another separate python subprocess**.
5. Inside the `hermes` process, `hooks/context_assembler_hook.py:evaluate()` fires on
   `pre_llm_call`: for profile `david` (in `BRAIN_CONTEXT_PROFILES`) it calls
   `tools.context_assembler.assemble(message, surface="hermes:cli", session_id, session_key, profile, invocation_id=f"hermes-{session_id}-{turn_id}")`
   — **the same assemble() call again**, this time keyed by Hermes's own session id, and this
   result (`context.render()`) is what Hermes actually prepends to the API call — this is the
   file recorded as `queue/context_assemblies/hermes-<session_id>-<session_id>:<uuid>:<hash>.json`,
   authoritative per `00`'s own rule.
6. On `post_llm_call`, the hook splits the `<<<TTROS_THREAD…TTROS_THREAD>>>` block, writes
   `thread_david.md` via `write_thread()` (atomic vault write) and appends a session journal
   entry via `append_session_turn()` — both synchronous, fire-and-forget-on-error, before the
   hook returns and before the coordinator script's `record-usage` subprocess runs.

**Double context-assembly finding (new, not previously named in `00`).** Step 2
(`assemble_model_context` in main.py, pre-launch) does **not** pass an explicit `invocation_id`,
so `tools/context_assembler.py:assemble()` defaults to `invocation = f"ctx-{uuid.uuid4().hex}"`
(context_assembler.py:1572) — one of the **365** `ctx-*.json` files sitting in
`queue/context_assemblies/` (vs. only **35** `hermes-*.json`). This is exactly the "ctx-*.json
describes a context that was never sent" standing fact in `00` — confirmed directly for this
surface: `ctx-c35d2656494c4283b46cd78eb33f68e0.json` (74,956 B) was written at
2026-09-13 15:06:50.85, **3.49s before** Hermes session `20260913_150653_bde324` started
(15:06:54.336); `ctx-b18994c842e34b3c989711b6874ef18f.json` (73,677 B) was written at
2026-09-13 15:07:27.10, **2.64s before** session `20260913_150729_b0a26f` started (15:07:29.737).
Every Dashboard David turn therefore pays for **two full deterministic context assemblies**:
one thrown away (`ctx-*.json`, produced in the FastAPI process before the subprocess is even
spawned) and one authoritative (`hermes-*.json`, produced inside the Hermes hook). **This step
does not repair it** — named here as the leading repair candidate, decided after Phase C.

**A5 — F-CODEXBUNDLE-1 status: ABSENT from the current working tree.**
`00` describes it as "the uncommitted David-latency repair, 386 insertions / 50 deletions,
≥4 separable changes including a routing-semantics swap and a safety-guard narrowing."
Current `git diff --stat` (working tree at session start): **9 files, 1383 insertions(+),
494 deletions(-)** — `context/EXECUTIVE_HEADER.txt`, `dashboard/backend/main.py` (92 lines),
`dashboard/backend/test_composio_hermes.py`, `dashboard/frontend/src/App.jsx`,
`dashboard/frontend/src/components/HumanReviewCard.jsx`, `dashboard/frontend/src/queueState.js`,
`dashboard/frontend/src/views/Queue.jsx`, plus a deleted `dashboard/frontend/tests/queueScope.test.js`
and new untracked `dashboard/frontend/src/artifactPreview.js`,
`dashboard/frontend/src/components/ArtifactViewer.jsx`, two new test files. The `main.py` diff
(the only backend file touched) is entirely queue-artifact binary/image support and receipt-prose
summarization — **no routing-semantics or safety-guard content, no shape match to 386/50.**
Neither total size nor content matches F-CODEXBUNDLE-1. It is not split, reverted, or built on in
this step, per instruction — only reported: **absent**, most likely superseded by commits made
since `00`'s 2026-09-08 date (`9baec17 Restore proven Telegram David and orchestrator routing`,
`f74298c Stabilize current TTROS repository state` — titles consistent with a routing-related
fix having landed), though this step did not audit git history further to confirm that lineage.

---

## PHASE B — predictions (written BEFORE instrumentation; not editable after results are seen)

Basis for these numbers: the 5-turn table above (Dashboard-David, all single-round-trip, no
tools), and the one existing CLI-only B8 exercise (different surface, cited only as a rough
per-call provider-latency prior: 2.4s–17.4s wall per `hermes -oneshot` call there).

Predictions for the Phase C live trivial turn ("Reply with one word: stored"):

| stage | predicted | unit |
|---|---|---|
| total wall clock (Dashboard endpoint in → response out) | 14 | seconds |
| Hermes process/session start (coordinator startup + step6 preflight subprocess + hermes binary init, up to first hook call) | 2.5 | seconds |
| deterministic context assembly, BOTH passes combined (pre-launch `ctx-*` + in-hook `hermes-*`) | 3.0 | seconds |
| tool/MCP schema discovery or attachment | 0.2 | seconds (predict negligible — no tools configured for `david`, `tool_names` NULL in every sampled session) |
| number of provider round trips | 1 | count |
| provider time, this one round trip | 6.5 | seconds |
| post-response thread/journal handling (`write_thread` + `append_session_turn`, both synchronous atomic vault writes) | 0.8 | seconds |
| unaccounted residual | 1.0 | seconds |

**Predicted dominant stage: D — provider time per request**, narrowly ahead of A (deterministic
context assembly, because it is paid twice). E (number of round trips) is predicted **not**
dominant — every sampled Dashboard turn, trivial or not, showed exactly 1 round trip; nothing in
the evidence suggests this one will differ, though T6/T7's 1-vs-6 result on a similarly "trivial"
question elsewhere means this is not guaranteed and the live turn is only one sample.

(Recorded before instrumentation is written or run. Not to be edited after Phase C.)

---

## PHASE B2 — instrumentation built (additive, log-only, gated on `TTROS_STEPL1_TIMING=1`)

Preimages taken from the working tree first, sha256-verified equal to the live files, in
`/home/liam/ttros_backups/stepL1_2026-09-13/{dashboard/backend,tools,hooks}/*.preimage`
(recorded in `preimage.sha256` there) — before any edit, per working-tree safety.

Three files edited, each with a no-op-unless-env-var-set guard:
1. `dashboard/backend/main.py` — `_stepl1_timing_log()` helper + marks in
   `_execute_named_profile_consultation()` around the pre-launch `assemble_model_context()` call
   and around `_run_hermes_message()`. Also reuses `result.get("elapsed_seconds")`, an
   **already-existing** wall-clock measurement (`_run_wsl_supervised`, `time.monotonic()` around
   the whole coordinator subprocess) that was computed but never logged for this purpose.
2. `tools/aos-hermes-coordinator.sh` — `_stepl1_mark()` bash function + marks at script start,
   before/after the Step 6 preflight subprocess, before/after the `hermes --oneshot` call itself,
   before/after the Step 6 record-usage subprocess.
3. `hooks/context_assembler_hook.py` — timing around the `assemble()` call in `pre_llm_call`
   (the authoritative in-hook context assembly) and around the `write_thread`/`append_session_turn`
   block in `post_llm_call`. Writes to a side file only, never stdout (which Hermes parses as this
   hook's JSON payload). `import time` added; no other import changes.

**Rehearsed offline first, no model call, per B3**, confirming each instrument returns **both**
answers (marks absent when the env var is unset, present when it is set) before spending the live
turn: hook (`_stepl1_mark`), coordinator script (`_stepl1_mark` sourced standalone), and a
byte-for-byte logic mirror of main.py's `_stepl1_timing_log` (main.py itself was not imported for
this rehearsal, to avoid FastAPI-app side effects; the mirror is the identical function body).
Rehearsal control lines were written then cleared from the three `scripts/stepL1_timing_*.jsonl`
files before Phase C so they would not contaminate the live capture.

Executable bit on `hooks/context_assembler_hook.py` checked immediately after editing: unchanged
(`-rwxr-xr-x`).

---

## PHASE C — the one live turn

**Method note (surface honesty).** The live turn was **not** sent over HTTP to the running
`aos-backend.service` (systemd, port 8010). Reaching that live process with
`TTROS_STEPL1_TIMING=1` would have required adding a systemd drop-in under
`~/.config/systemd/user/` and restarting the shared backend service — outside this step's stated
`WORK ONLY IN /home/liam/agentic-os-live` scope, and a needless disruption to a running shared
process for a diagnostic env var. Instead, `scripts/stepL1_live_turn.py` imports
`dashboard/backend/main.py` **as the exact same module** (`backend.main`, same package path
`uvicorn` itself imports, run from the same `dashboard/` working directory with the same venv
interpreter) and calls `_execute_named_profile_consultation("David", "david", "Reply with one
word: stored", request_id)` directly — the identical function, with identical behaviour, that the
live HTTP endpoint calls. This is the real Dashboard-David code path, exercised in-process rather
than through the shared HTTP server. Import-only dry run confirmed clean before spending the
budgeted call (no side effects, no queue mutation import-time code found).

**Budget: MAX_CALLS = 1, enforced in `scripts/stepL1_live_turn.py`. ACTUAL CALL COUNT: 1.**
Full transcript: `scripts/stepL1_live_turn.txt`.

Prompt sent (verbatim, per instruction C1): `"Reply with one word: stored"`.
Reply received: `"stored"`.
Hermes session created: `20260913_153240_2d084c`. Invocation id: `hermes-42fd0a83c3bb4e2da045cdc18edd2000`.

### C2 — captured facts

- **Wall clock, end to end** (function-call boundary, `_execute_named_profile_consultation` entry
  to return): **34.805s** (main.py-side timer) / 34.815s (outer script timer around the same call
  — the 0.01s gap is the script's own negligible call overhead).
- **Provider round trips**: **1**, confirmed three independent ways — `messages` table assistant-row
  count for session `20260913_153240_2d084c` = 1; DB `sessions.api_call_count` = 1;
  `token_usage.api_calls` from the Hermes usage file = 1. All three agree; the api_call_count gap
  the instruction warns about (missing a grace request after a cap) is not observed on this turn.
- **Tool-call count**: 0. `tool_calls` column NULL on both messages. `sessions.tool_names` NULL.
  **Tool schemas attached despite triviality**: checked the authoritative `hermes-*.json` context
  file's embedded `request` string for `"tools"`/`function`/`tool_choice`/`"schema"` — **absent**,
  same as every historical sample in Phase A. No tool exposure cost on this turn.
- **Token fields** (from the Hermes usage report, exact): input_tokens=19761, output_tokens=216,
  cache_read_tokens=0, cache_write_tokens=0, reasoning_tokens=106, total_tokens=19977, api_calls=1.
- **Assembled bytes/blocks** (authoritative, in-hook pass): total_bytes=50144, total_tokens=10316,
  same 15 named blocks as every Phase A sample, but **smaller in absolute size** than all 5
  historical samples (59,130–65,443 B there vs. 50,144 B here) — same block set, less content
  matched this turn (e.g. "recent receipts and outcomes" was 54 B here). Recorded as a finding
  (below), not investigated further.
- **Queue delta**: none. `queue_effect.items_created = 0`, before/after snapshot sha256 identical
  (`ed59427b...`). Confirms the "no queue work" instruction in the consultation prompt held.
- **Rolling working thread rewrite**: **yes, rewritten.** Captured before/after (see below).

### C2 continued — stage decomposition (measured, from the three timing files)

All three files corroborate: `scripts/stepL1_timing_main.jsonl`, `scripts/stepL1_timing_coordinator.jsonl`,
`scripts/stepL1_timing_hook.jsonl`.

| stage | measured | unit | source |
|---|---|---|---|
| **total wall clock** | **34.805** | s | main.py timer, endpoint-equivalent function entry→return |
| pre-launch context assembly (main.py `assemble_model_context`, discarded `ctx-*.json`) | **11.881** | s | main.py timer around the call |
| gap after pre-launch assembly, before the `hermes` subprocess is launched (prompt-file write, tempfile create, `Popen` setup) | 0.000 | s (<0.5ms) | main.py timer |
| coordinator subprocess total (bash script start → exit) | 22.787 | s | main.py's `_run_wsl_supervised` (pre-existing `elapsed_seconds`, reused) |
| — of which: coordinator startup → preflight start | 0.001 | s | coordinator marks |
| — of which: Step 6 preflight subprocess | 0.078 | s | coordinator marks |
| — of which: gap preflight→hermes call | 0.001 | s | coordinator marks |
| — of which: **`hermes --oneshot` binary, start to exit** | **22.535** | s | coordinator marks |
| — — of which: **in-hook context assembly** (`pre_llm_call`, authoritative `hermes-*.json`) | **12.183** | s | hook marks |
| — — of which: **thread/journal handling** (`post_llm_call`: `write_thread` + `append_session_turn`) | 1.641 | s | hook marks |
| — — of which: **unaccounted residual inside the `hermes` binary** (Hermes process/session start before the hook fires, the hook subprocess's own spawn+import overhead paid twice, the actual provider round trip, and Hermes's internal response handling — not separable further without patching Hermes, forbidden by header rule 9) | **8.711** | s | derived: 22.535 − 12.183 − 1.641 |
| — of which: gap hermes→record-usage | 0.001 | s | coordinator marks |
| — of which: Step 6 record-usage subprocess | 0.161 | s | coordinator marks |
| top-level residual (FastAPI-side post-processing after `_run_hermes_message` returns: queue snapshot, thread-block split, `_david_thread_persisted` read, response-dict build) | 0.137 | s | derived: 34.805 − 11.881 − 0.000 − 22.787 |
| tool/MCP schema discovery or attachment | ~0 (architecturally not exercised) | — | no `tools` key in request; `tool_names` NULL |
| provider round trips | 1 | count | 3-way confirmed (above) |

**Deterministic context assembly total (both passes): 11.881 + 12.183 = 24.064s — 69.1% of the
34.805s total wall clock**, for a turn whose entire task was to echo one word.

### C2 continued — rolling working thread, before / after

Before (from message id 1387 in `state.db`, the last real David turn's thread write, session
`20260913_150653_bde324` — the intervening recall turn, session `20260913_150729_b0a26f`,
produced **no** thread block at all, so per the hook's fail-closed rule it changed nothing):

```
## Current thread
Continuity benchmark: remember temporary phrase cedar-glass-482 for the next turn only.

## Decisions made
No queue work, delegation, tools, external service, or external action was requested or taken.

## Open questions
On the next turn, use the temporary phrase if continuity is being tested, then drop it.

## Return to
Morning executive interpretation remains parked: Liam's active bottleneck is Gmail capture
digests in human_review; two Lead Gen Agent local no-send objectives remain blocked and
system-owned.
```

After (this diagnostic turn, written by the real `write_thread()` path exactly as any other David
turn would trigger it):

```
## Current thread
Continuity benchmark completed; the temporary phrase cedar-glass-482 has now been used for the
intended next-turn test and should be dropped.

## Decisions made
No queue work, delegation, tools, external service, or external action was requested or taken.

## Return to
Morning executive interpretation remains parked: Liam's active bottleneck is Gmail capture
digests in human_review; two Lead Gen Agent local no-send objectives remain blocked and
system-owned.
```

No real parked work was lost (the model carried the "Return to" section forward faithfully), but
this is a live reproduction of F-THREADSCOPE-1/F-THREADWIPE-1: a trivial, non-conversational
turn overwrote the genuine continuity thread. **Left as-is, not reverted** — see C3 and Findings.

### C3 — residue removal

Per instruction, only the `sessions/` journal residue was targeted (matching the established
`scripts/stepT8A_residue_cleanup.md` precedent, which explicitly treated `thread_david.md` as
**out of scope** for this kind of cleanup — a separate, already-tracked finding, not something a
diagnostic step reverts ad hoc).

- **Target**: `sessions/2026-09-13_hermes-cli_7cd4569d6fe3.md` in the Business Brain vault
  (`/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain/sessions/...`) — this
  diagnostic turn appended a fourth `### Turn · 2026-09-13T22:32:58...` entry to a file that
  already held three genuine turns from today (a scheduled morning brief and the two cedar-glass
  turns).
- **Preimage**: `/home/liam/ttros_backups/stepL1_2026-09-13/business_brain/sessions/2026-09-13_hermes-cli_7cd4569d6fe3.md.preimage`,
  sha256 `8bd64be90cf8d0094dc4fb5fa721f11b4c44636f273d9735f22804285272d4ab`, verified equal to the
  live file before the write.
- **Exact change**: removed only the fourth (diagnostic) turn block; the three genuine turns and
  the file's frontmatter/preamble were preserved byte-for-byte apart from the mechanical
  `hermes_last_write` re-stamp `write_transaction` always applies.
- **Exact rollback**: `tools.brain_memory.write_transaction({relative: <PREIMAGE bytes>},
  source=..., session_id=..., expected_hashes={relative: "e4d88dda1b54507cc008d92b3b7cb3a2611d69a27fbe22ec74d722d81feac558"})`
  (the file's post-cleanup hash) through the same gated script.
- **Written through the gated script**: yes — `tools/brain_memory.py::write_transaction`, no
  editor/sed/redirect. Local vault commit `b1dd7624ff78c464b4c415e871b1dc60586f5cae` (vault's own
  git repo; not this repo; not pushed).
- **Verified removed**: `grep -c "Reply with one word: stored"` → 0; the three genuine
  `### Turn ·` headers remain, in order, unchanged content.
- **Re-indexed**: `python3 tools/aos_indexer.py scan` → `{"status": "success", "indexed": 4534,
  "skipped": 1501, "failures": []}`.

---

## PHASE D — close-out

**D1 — instrumentation removed, files restored to preimage.** All three edited files
(`dashboard/backend/main.py`, `tools/aos-hermes-coordinator.sh`, `hooks/context_assembler_hook.py`)
copied back from their `/home/liam/ttros_backups/stepL1_2026-09-13/*.preimage` copies and verified
byte-identical by sha256 (matches the pre-edit hashes exactly). None of the added timing code is
kept in place — it was diagnostic-only, gated behind an env var nothing else sets, and this step
builds no repair, so nothing durable was left in the runtime code. The three captured
`scripts/stepL1_timing_*.jsonl` files (gitignored, `*.jsonl`) are kept on disk as the raw evidence
for this write-up, not as a running instrument.

**D2 — executable bit** on `hooks/context_assembler_hook.py`: rechecked after restore —
`-rwxr-xr-x`, unchanged throughout.

**D3 — canonical suite.** Run via the external pytest path (header item 8):
`PYTHONPATH=/home/liam/ttros-testenv/pytest dashboard/backend/.venv/bin/python -m pytest -q`.
**Result: 842 passed, 1 skipped, 223 subtests passed, 0 failed** (373.9s). **This does not match
the stated baseline of 829 passed / 0 failed** — 0 failures agrees, but the total (842 vs. 829)
and the 1 skip do not. This is recorded, not reconciled: `dashboard/backend/main.py` and
`dashboard/backend/test_composio_hermes.py` were both already modified in the working tree before
this session began (see git status at session start, unrelated to Step L1's own edits, which were
independently verified restored to their own preimages by sha256 before this run). The likeliest
explanation is that the 829 baseline predates that pre-existing uncommitted work, making 829 a
stale figure for the *current* working tree — consistent with `00`'s own warning that other
historical suite figures (746, 760) are stale. Not re-derived further in this step; flagged rather
than silently accepted or forced to match.

**D4 — protected paths.** `connectors/`, `workspaces/north_shore_sales_coach/`, Hermes global/default
profile config, David's Hermes *profile config* (not its runtime `state.db`, which this step read
directly and which gained one new session row as the intrinsic, expected result of the one
authorized live call), the Telegram bridge/launchers, and `queue/model_routes.json` /
`queue/lane_profiles.json` were never opened, read, grepped, or written by any tool call in this
session — confirmed by the session's own action log, not by inspecting those paths directly (per
header rule 1, which forbids even a read-only check "in passing"). The only writes outside the
three preimaged-and-restored repo files were: (a) new files under `scripts/` (this document, the
live-turn script/transcript, the three now-cleared-of-rehearsal-content timing jsonl files), and
(b) the one gated vault write in Phase C3, to `sessions/2026-09-13_hermes-cli_7cd4569d6fe3.md`
only.

**Token usage (exact, from the one live call's Hermes usage report):** input 19,761 / output 216 /
cache read 0 / cache write 0 / reasoning 106 / total 19,977 / api_calls 1.

---

## PREDICTED VS MEASURED

| stage | predicted | measured | verdict |
|---|---|---|---|
| total wall clock | 14s | **34.805s** | miss — 2.5× higher |
| Hermes process/session start (coordinator-side, outside the `hermes` binary) | 2.5s | 0.081s (preflight + gaps only; the portion of "process start" that happens *inside* the `hermes` binary before the hook fires is folded into the 8.711s unaccounted residual, not separable) | miss, but largely a bucketing error, not a real 2.5s of coordinator-side startup |
| deterministic context assembly (both passes combined) | 3.0s | **24.064s** | **miss — 8× higher; this was the real story** |
| tool/MCP schema discovery or attachment | 0.2s | ~0 | correct direction, close enough |
| number of provider round trips | 1 | 1 | **correct** |
| provider time per round trip | 6.5s | not separable — bounded within the 8.711s residual bucket alongside Hermes startup and hook-subprocess overhead | can't confirm or refute cleanly |
| thread/journal handling | 0.8s | 1.641s | miss — ~2× higher, same order of magnitude |
| unaccounted residual | 1.0s | 0.137s (top-level) + 8.711s (inside the `hermes` binary, see above) | miss — the single "residual" bucket predicted turned out to need splitting into two, and the inner one absorbed most of what should have been "provider time" |
| **dominant stage** | **predicted D (provider time)** | **measured A (deterministic context assembly) — 69.1% of total wall clock, done twice** | **prediction was wrong** |

---

## What this measurement licenses, and what it does not

**Licenses:** for this one trivial turn on the Dashboard David route, deterministic context
assembly — paid twice, once discarded and once authoritative — consumed the large majority
(69.1%) of total wall clock, and did so independently of how trivial the actual request was (same
15-block structure as every non-trivial historical sample). The number of provider round trips was
1, matching every other sampled Dashboard turn; nothing in this sample suggests round-trip count
is the latency driver here. Tool/schema exposure cost nothing measurable because none was
attached.

**Does not license:** any claim that context assembly *always* dominates, that 24s (or 69%) is a
stable fraction, or that the 8.711s residual bucket is "provider time" — it is an upper bound on
provider time plus several uninstrumented local costs bundled together. **This is one live sample.**
The task's own precedent (T6/T7) showed the same kind of "trivial" question producing 1 round trip
on one occasion and 6 on another; this run happening to land on 1 is not evidence the turn-to-turn
variance T6/T7 found is gone. The two assembly-pass durations (11.881s, 12.183s) are also not
proven stable — Phase A's own historical sample showed authoritative context size varying
50–65KB turn to turn with the identical block set, so per-pass duration should be expected to vary
with content volume, not just be a fixed constant.

## Recommended next repair (one paragraph, scoped to the dominant cost only — no implementation)

Remove the redundant pre-launch call: `dashboard/backend/main.py:_execute_named_profile_consultation()`
calls `assemble_model_context()` (→ `tools/context_assembler.py:assemble()`) once before ever
launching Hermes, producing a `ctx-*.json` file that this step confirmed (A4) is architecturally
discarded — Hermes's own `hooks/context_assembler_hook.py:pre_llm_call` unconditionally
re-assembles from scratch for every `david`-profile turn regardless of what was already baked into
the prompt text, and that second pass is the one whose output the model actually receives
(`hermes-*.json`, authoritative per `00`). This session measured both passes costing roughly the
same (~12s each) for the same underlying work. Eliminating the first pass — either by not calling
`assemble_model_context()` in `main.py` at all and passing the operator's raw text straight through
to `_run_hermes_message`, or by explicitly suppressing the pre-launch call's expensive branch when
the Hermes-side hook is known to re-assemble anyway — would plausibly remove close to one of the
two ~12-second passes with no loss of context reaching the model, since the discarded pass's
rendered output is never what gets sent. This is a repair to the call structure in `main.py`, not
to `context_assembler.py:assemble()` itself, and should be sized and verified against B7/B2 before
being accepted as green, per `00`'s own sequencing rule.

## Findings recorded, not fixed

1. **Double deterministic context assembly, every Dashboard David turn** — confirmed
   architecturally (A4: `assemble_model_context` is a direct alias for the same `assemble()` the
   hook also calls) and by direct timing (this turn: 11.881s discarded + 12.183s authoritative =
   24.064s of 34.805s, 69.1%). Not previously named as a distinct finding in `00`.
2. **F-CODEXBUNDLE-1 status: ABSENT** from the current working tree (A5) — current uncommitted
   diff (9 files, 1383 insertions/494 deletions, all dashboard-frontend/queue-artifact content) does
   not match the recorded 386/50 routing-semantics-plus-safety-guard shape. Likely superseded by
   commits `9baec17`/`f74298c` (titles consistent with a routing fix landing); git history was not
   audited further to confirm that lineage, per this step's scope.
3. **Neither `sessions.source` nor the assembler's own `surface` field distinguishes Dashboard
   from raw-CLI Hermes turns** — both read `'cli'` / `'hermes:cli'` for every sample checked
   (35/35 `hermes-*.json` files, all 6 sessions examined in this step). Only the LLM-generated
   session `title` happened to distinguish them in this sample, which is not a structural
   guarantee. Anyone building a Dashboard-specific measurement on `source` or `surface` alone will
   silently include CLI turns and vice versa.
4. **F-THREADSCOPE-1/F-THREADWIPE-1 reproduced live**: this diagnostic turn overwrote
   `thread_david.md` exactly as the existing finding describes. No real parked work was lost this
   particular time (the model preserved "Return to"), but the file is left in the diagnostic
   turn's post-state — not reverted, per this step's no-repair scope and the established
   T8A precedent that `thread_david.md` sits outside a residue-cleanup's target. Liam may want it
   manually restored; the pre-turn content is recorded verbatim above (C2) if so.
5. **Suite baseline stale for the current working tree**: 842 passed / 1 skipped / 0 failed
   measured against a stated 829 passed / 0 failed baseline. Zero failures, and this step's own
   edits are independently verified fully reverted (sha256), so the mismatch predates this
   session — flagged, not reconciled.
6. **Authoritative context size varies turn to turn** even with an identical 15-block structure:
   50,144 B / 10,316 tokens this turn vs. 59,130–65,443 B / 12,909–14,275 tokens across the 5
   historical Dashboard samples. Not investigated further; relevant to whether the ~12s in-hook
   assembly cost is closer to fixed overhead or scales with matched content volume.
7. **The 8.711s in-`hermes`-binary residual is an unresolved bundle**, not a clean measurement of
   provider time: it contains Hermes process/session start (before `pre_llm_call` fires), the
   hook subprocess's own spawn+import overhead (paid twice — once per lifecycle event), the actual
   provider network round trip, and Hermes's internal response handling. Separating these further
   would require instrumenting Hermes itself, which header rule 9 forbids (Hermes stays unforked
   and unpatched). Reported as an upper bound, not a decomposition.

## Protected paths and suite status

`connectors/`, `workspaces/north_shore_sales_coach/`, `queue/model_routes.json`,
`queue/lane_profiles.json`, Telegram bridge/launchers, Hermes global/default profile, David's
Hermes profile config: untouched (confirmed by this session's own action log; not independently
inspected, per header rule 1). Suite: 842 passed / 1 skipped / 0 failed / 223 subtests passed —
see D3 for the baseline-mismatch finding.

## Next action

Liam reviews this decomposition and decides the repair. Nothing beyond the diagnostic itself was
begun.
