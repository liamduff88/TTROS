# STEP X2 — One live David handoff through the real spine, end to end

Session: single session, `/home/liam/agentic-os-live`, 2026-09-11. TTROS permission header and
`CLAUDE.md` read and acknowledged at session start. Current state carried forward from
`scripts/stepX1_execution_path_proof.md` (code trace, not re-derived here).

Every search this session excluded `connectors/` and `workspaces/north_shore_sales_coach/` from
the first command.

---

## Part 0 — free, before any call

### 1. The 2026-09-09 14:13 PDT config rewrite — attribution

`aos-orchestrator`, `aos-revenue`, `aos-marketing`, `aos-delivery`, `aos-ops` `config.yaml` mtimes,
confirmed again this session (`stat`):

```
aos-orchestrator  2026-09-09 14:13:48.446595192 -0700
aos-revenue       2026-09-09 14:13:48.890399951 -0700
aos-marketing     2026-09-09 14:13:49.330057003 -0700
aos-delivery      2026-09-09 14:13:49.786304887 -0700
aos-ops           2026-09-09 14:13:50.234257356 -0700
```

Surfaces checked this session, beyond what X1 checked:

- **`/home/liam/ttros_backups/`**: no directory or file dated 2026-09-09 14:xx PDT. The nearest
  entries are `validation_a_phase2_preimages_20260909T075922Z` (00:59 PDT, unrelated files —
  `detector.py`, `validation_a_seal_guard.py`, `test_validation_a_seal_guard.py`) and
  `hermes_upgrade_20260908` (Sep 8, 12:15–12:57 PDT — a full day earlier, and its own preimage
  set — `david_profile_snapshot`, `state.db.PREIMAGE_20260908`, `unrelated_profiles*.sha256` —
  does not touch the five worker/orchestrator profile configs).
- **`scripts/`**: no report under `scripts/` timestamped in that window (`find -newermt "2026-09-09
  13:00" -not -newermt "2026-09-09 16:00"` on `scripts/*` returns only unrelated I1 files dated
  outside that window on inspection — none of the four hits are from that afternoon).
- **Claude Code session logs** (`~/.claude/projects/-home-liam-agentic-os-live/*.jsonl`) — not
  checked by X1. Ten transcripts contain the literal strings `aos-orchestrator/config.yaml` /
  `aos-revenue/config.yaml` / `aos-marketing/config.yaml` somewhere in their history, but **none of
  those ten has any message timestamped between 2026-09-09T20:00Z and 2026-09-09T22:00Z** (the
  14:13 PDT rewrite is ≈21:13Z) — checked by extracting every `2026-09-09T2[01]` timestamp from
  each candidate file. The mentions are from other sessions investigating these files afterward
  (X1 itself among them), not from a session active at the moment of the rewrite. This rules out a
  Claude Code CLI session in this project directory as the direct writer during that ~2-second
  window; it does not rule out a script invoked from an earlier/later session, a manual edit, or a
  process outside this project's Claude Code logs (Codex, Antigravity, or a bare shell).
- **Codex session logs**: `~/.codex/` holds only cache/tool directories, no session transcripts
  with content to search for this repo's paths.

**Conclusion: unknown, surfaces named.** No preimage, no step report, and no Claude Code session
transcript places a specific actor at that rewrite. The clustering (~2s apart, all five
worker/orchestrator profiles, none of `david`'s three T-series rewrites the same day) is most
consistent with a single scripted bulk-write process, but nothing recovered this session or in X1
identifies which one. Reported as "unknown," per the instruction that this is an acceptable answer.

### 2. Invocation ceiling — from code

Traced in `dashboard/backend/main.py`, `run_queue_item()` (`:10055`) and its helpers:

- `orchestration_child = _is_hermes_orchestration_child(item)` (`:10072`) requires tag
  `hermes_orchestration_child` **and** `owner == "codex"` (`:9776-9782`). A David-handoff child
  carries tags `async_dispatch, executive_objective_child, hermes_chain` and `owner="hermes"`
  (X1 A1 step 6) — so `orchestration_child` is **False** for this run.
- `executive_objective_child = _is_executive_objective_child(item)` (`:10073`, `:9785-9790`) is
  **True** (tag present, has `parent_id`, `review == "model"` — hardcoded by
  `_create_executive_objective`, X1 A1 step 9).
- `max_attempts = 3 if orchestration_child else 2` (`:10146`) → **2** for this item.
- Loop (`:10166-10250`): each attempt runs one worker invocation; if the worker reports success,
  one review invocation follows (`_queue_review_required` is unconditionally true here because
  `review == "model"`); the loop `break`s immediately on `PASS`, on a hard worker failure/timeout
  (`final_status == "blocked"`), or on the "claimed canonical artifact genuinely absent" case —
  it only proceeds to a second attempt when the first attempt's review returned `REVISE` without a
  hard failure.
- **Per-child ceiling: 2 worker invocations + 2 review invocations = 4 sub-invocations**, on top of
  (1) David's decision turn and (2) the decomposition turn that creates the item. **Worst-case
  total for one child reaching a terminal state: 6 invocations** (base 4 assuming one clean pass,
  +2 if a revision round is needed).
- **Decomposition step count is not capped in code.** `_normalize_chain_proposal()` (`:4709`)
  iterates every entry in the `steps` list the decomposition model emits with no upper bound, and
  `_create_executive_objective()` turns each into its own child queue item. Only `children[0]` is
  auto-dispatched synchronously by the `ask-david` request (`_accept_async_queue_runner(children[0])`,
  X1 A1 step 7); further children would need `depends_on` to clear and would then be picked up by
  `aos-runner.service`'s own poll loop (confirmed running `--watch --interval 5`, so it is a live,
  continuous picker — not idle). **This is not a bounded "retry"; it is a model-behavior risk, not
  a code-capped one.** The message given to David describes one harmless single-line shell command,
  so one step is the expected decomposition output, but nothing in code forces that. This is why
  the step's own stop rule (watch every coordinator-addressable profile's `state.db`; stop through
  the queue API if a session starts beyond the ceiling) is the actual control here, not a code cap.
- **Declared ceiling for this run: 6 invocations for the one expected child**, watched live against
  the possibility of more than one child being created.

### 3. Stop mechanism

- The queue's only supported stop surface reachable from here is `POST
  /api/queue/items/{item_id}/status` with `status="cancelled"` (`_queue_validate_status` accepts
  `cancelled`, `main.py:5027`). **This does not interrupt an invocation already in flight.**
  `run_queue_item()`'s attempt loop (`:10166`) does not re-read the item's status between the start
  and end of a worker/review call, and `_queue_heartbeat_loop()` (`:9404`) only renews the claim
  lease — it carries no cancellation check. So "stopping the item through the queue's supported
  API" prevents a **further** attempt/dispatch from starting; it cannot abort one already running.
- **The 600s wall-clock kill (`HERMES_EXECUTION_TIMEOUT_SECONDS`, default 600, `main.py:784-786`)
  applies per invocation.** Each worker call and each review call is its own
  `_run_wsl_supervised()` subprocess with its own `process.communicate(timeout=...)` and its own
  `_terminate_process_group()` on expiry (X1 A6) — not one timer for the whole item.
- **Consequence for the Authorized stop action in this step:** if a session appears beyond the
  ceiling, the status-API call will stop the *item* from progressing further once its current
  invocation ends (or times out at 600s), but cannot kill a Hermes session already mid-turn. This
  is accepted as the step's own authorized mechanism — no process kill is authorized here.

### 4. Baselines (2026-09-11, this session)

- `aos-backend.service`: **active**, running since 2026-09-09 09:46:26 PDT, `uvicorn 127.0.0.1:8010`.
  `GET /api/health` → `{"status":"ok", ...}`. Backend root `/` → **404** (standing fact, confirmed).
- `aos-runner.service`: **active**, running since 2026-09-09 09:46:26 PDT,
  `aos-orchestration-runner.py --watch --interval 5` — a live 5-second poll loop.
- Vault: no `sessions/2026-09-11_hermes-cli_*.md` journal exists yet today (directory listing
  checked; latest is `2026-09-10_hermes-cli_7cd4569d6fe3.md`) — baseline is **absence**, not a hash.
- `thread_david.md` sha256 (baseline, before Part B):
  `21cc5b8f6f8edb54b7dfa6d4b60d7f0694c2030280023eb35ece8e3c8bb91bd8`
  (`/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain/sessions/thread_david.md`)
- Queue item count baseline: `queue/work_items.jsonl` = **791 lines**,
  sha256 `ef5f3a74334af50a81769acc3307d235f73087df1a70a61e59fe526e7a0fd644`.
- Latest `started_at` in `david` `state.db`: session `20260911_000551_4b41e7`,
  **2026-09-11T07:05:54.056336Z** (this is X1's own T9 Part 0b probe turn — not a production
  ask-david call).
- Latest `started_at` in `aos-orchestrator` `state.db`: session `20260909_135449_e27b0f`,
  **2026-09-09T20:54:50.971433Z** — one of the two failed-at-startup sessions X1 found; **no
  aos-orchestrator session has started since then.** Any new row here after this baseline is
  attributable to this step's Part B call.

### 5. Predictions (written before Part B)

- David emits a fenced `execution_handoff` JSON block on the first turn: **likely (~0.75)** — the
  message is an explicit, unambiguous "please hand this to Operating Hermes" instruction matching
  the clear-execution-intent branch of `rules/david_execution_handoff.md` exactly.
- Decomposition produces **exactly one child step** (not more): **likely (~0.8)** — the task is one
  trivial shell command with no natural sub-steps.
- Invocations used, if it succeeds cleanly: **4** (David + decomposition + 1 worker + 1 review), well
  under the 6-invocation ceiling.
- If it fails, most likely failure point: **`aos-orchestrator` startup**, consistent with both prior
  2026-09-09 failures and the STEP U fail-closed guard shape X1 found (zero messages/tool calls/API
  calls, immediate close) — this is a repeat of X1's own prediction, now being tested live for the
  first time since 09-09.
- No Telegram or other external message will be sent regardless of outcome (source stays
  `dashboard/hermes_message`, X1 A6).

---

## Verdict, plain English, first

**No — David's request reached Operating Hermes, but Operating Hermes did not run.** David
correctly emitted the `execution_handoff` JSON block on the first turn (prediction confirmed).
The dashboard backend correctly tried to hand it to `aos-orchestrator` for decomposition. That
decomposition call was blocked before it ever reached the model, by Hermes's own native
fail-closed context guard ("TTROS model call blocked: mandatory assembled context is absent").
No queue item was ever created, no worker ran, no review ran, `HANDOFF_OK` never executed. This is
the **same failure signature** as the two unexplained `aos-orchestrator` sessions from 2026-09-09
that X1 found only circumstantial evidence for — **this run reproduces it live, for the first
time with direct evidence of the actual blocking message**, not just a zero-message session-row
shape. This is a standing production defect blocking every coordinator-addressable AOS profile
(`aos-orchestrator`, `aos-revenue`, `aos-marketing`, `aos-delivery`, `aos-ops`), not specific to
this task.

Only 1 of the declared-ceiling 6 invocations was used, and the one that was used (David's turn)
cost real tokens; the failed decomposition attempt was blocked pre-model-call and cost nothing.
No external message was sent. The one real David turn this run left in the vault was found,
removed through the gated path, and verified gone.

---

## Part B — one live handoff (executed)

**Call:** `POST http://127.0.0.1:8010/api/dashboard/ask-david`, body
`{"text": "Please hand this to Operating Hermes: run the local command \`echo HANDOFF_OK\` in a
terminal and report its output. It is a harmless connectivity test with no external effect."}`,
2026-09-11T10:13:59Z → 10:15:00Z (61.0s), HTTP 200.

**What happened, in order:**

1. David's turn ran on profile `david` (session `20260911_031416_dad6f0`, model `gpt-5.5` /
   `openai-codex`, 1 real API call, 20,672 input / 280 output / 56 reasoning tokens, 22.985s). Its
   reply, read directly from `state.db` message id 1347:

   > Handing this to Operating Hermes as a single-step local connectivity test.
   >
   > ```json
   > {"execution_handoff":{"objective":"Run the local command `echo HANDOFF_OK` in a terminal and
   > report its output.","scope_hint":"single_step","source_refs":[]}}
   > ```

   — a well-formed `execution_handoff` block, exactly the clear-intent branch predicted.
   `max_iterations` for this session: `9223372036854775807` (effectively unbounded — the CLI's
   `--oneshot` invocation relies on the 600s wall-clock kill, not a turn cap, matching X1 A6).

2. `_hermes_objective_from_handoff()` correctly parsed it and called `hermes_message()` with
   `force_objective=True`, which called `_run_hermes_message(profile="aos-orchestrator")` for
   decomposition. A new `aos-orchestrator` session was created — `20260911_031449_9c0c2a`, started
   2026-09-11T10:14:51Z — with **`message_count=0`, `api_call_count=0`, `end_reason="agent_close"`**.
   This is the identical fingerprint to both 2026-09-09 failures X1 found (A5). **No
   `queue/context_assemblies/hermes-*.json` file was written for this session** — confirmed by
   directory listing; only David's own context assembly
   (`hermes-20260911_031416_dad6f0-...json`) exists from this run. Per X1's A5 finding, a genuine
   dashboard-driven call always writes this file first; its absence here means the context
   assembly step itself never completed.
3. The coordinator script's captured output (`main.py`'s `error.message`, and reproduced exactly
   in `stderr`/`stdout`/`output`):
   ```
   hermes -z: agent failed: TTROS model call blocked: mandatory assembled context is absent
   NEEDS ATTENTION: exact Hermes usage unavailable; Step 6 scope paused
   ```
   `returncode=78`, `timed_out=False`, `elapsed_seconds=13.921`.
4. `queue_effect` in the response: `{"items_created": 0, "before": {"count": 791}, "after":
   {"count": 791}, "unchanged": true}` — **no queue item was ever created.** Top-level
   `"success": false`.
5. No further sessions started on `aos-revenue`, `aos-marketing`, `aos-delivery`, or `aos-ops` —
   checked against the pre-call baseline for all five profiles; only the one `aos-orchestrator`
   session appeared. **The stop rule was never triggered** — one session, at the expected profile,
   well inside the ceiling.

### Root-cause diagnosis (read-only, this boot's evidence, before it ages out)

`hooks/context_assembler_hook.py:evaluate()`, `pre_llm_call` branch for an `AOS_PROFILES` member
(`aos-orchestrator` included, `:180-186`):
```python
if profile in AOS_PROFILES and os.environ.get("AOS_STEP6_WRAPPED") != "1":
    raise RuntimeError("Step 6 protected model runner requires the canonical accounting/fuse wrapper")
if profile in AOS_PROFILES:
    scope_type = os.environ.get("AOS_STEP6_SCOPE_TYPE", "")
    scope_id = os.environ.get("AOS_STEP6_SCOPE_ID", "")
    preflight(Scope(scope_type, scope_id), root=ROOT)
context = assemble(...)
```
`main()` (`:239-251`) catches any exception here and returns `{"error": "context assembly failed:
<ExceptionType>"}` with **no further detail** — by design, per its own comment, so a failure here
prevents the model call rather than degrading it. Hermes's own native runtime then sees no
`context` marker and raises the exact message this run captured.

Two isolated, read-only reproductions of this same hook **succeeded** just now, using
representative env vars (`AOS_STEP6_WRAPPED=1`, `HERMES_HOME=.../profiles/aos-orchestrator`, both
`AOS_STEP6_SCOPE_TYPE=work_item` and the fallback `session`/`aos-orchestrator-direct` shape a
prompt with no work-item ID or sticky key would actually produce) — the hook code itself is not
trivially broken. This narrows the cause to something specific to the **real** subprocess chain
(`main.py` → `tools/aos-hermes-coordinator.sh` → `hermes -p aos-orchestrator` → Hermes's own
spawned hook subprocess) that my synthetic, directly-invoked probe does not reproduce — most
likely an environment-inheritance gap between what the coordinator script exports and what Hermes
actually passes through to the hook process it spawns, or a transient condition tied to the real
prompt/session identity. **No log anywhere captures the hook's own stderr for the failing
invocation** — `journalctl --user -u aos-backend.service` for this exact window contains only the
one `INFO` line for the HTTP request/response; nothing under `~/.hermes` was written in this
window either. This is the same diagnostic dead-end X1 hit for the two 2026-09-09 failures, now
confirmed a third time running.

**What this licenses:** `aos-orchestrator` (and by the same code path, every other AOS profile)
cannot currently complete a decomposition, worker, or review turn through the production
`ask-david` → `hermes_message` → `run_queue_item` spine — the fail-closed guard blocks it before
any model call, 3 out of 3 observed attempts since 2026-09-09. **What it does not license:** a
claim that the guard itself, or `AOS_STEP6_WRAPPED`/Step 6 accounting, is the defect — the
isolated reproduction succeeding means the simplest version of that theory is not sufficient by
itself; the actual trigger in the live subprocess chain remains unidentified.

### Minimal repair plan (not applied)

**Exact change (proposed, for a future step to apply and validate):** add one line to
`hooks/context_assembler_hook.py:main()`'s `except Exception as exc:` block — when
`os.environ.get("AOS_DEBUG_HOOK") == "1"`, append `f"{type(exc).__name__}: {exc}"` plus the
current `AOS_STEP6_WRAPPED`/`AOS_STEP6_SCOPE_TYPE`/`AOS_STEP6_SCOPE_ID`/`HERMES_HOME` env values to
a small append-only debug file (e.g. `logs/runtime/context_assembler_hook_debug.log`), still
returning the same `{"error": ...}` payload and exit code so production behavior is unchanged.
Gate it behind an env var so it is opt-in and cannot leak into normal operation. Then re-run this
exact step's Part B once with `AOS_DEBUG_HOOK=1` set on `aos-backend.service` to capture the actual
exception on the next failure.
**Exact rollback:** revert the one-line diff (or `git checkout -- hooks/context_assembler_hook.py`
if committed); delete the debug log file if created.
**Why not applied now:** this step's Authorized section does not include code edits; diagnosing
without repairing is what it asks for. This is also a defect with a blast radius larger than this
step (it blocks all five AOS profiles, not just a test item), so a fix belongs to its own step
with its own validation, not folded into X2's one-attempt scope.

---

## Acceptance criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | David's reply contains a fenced `execution_handoff` JSON block | **PASS** | `david` `state.db` message id 1347, quoted above |
| 2 | A parent and child queue objective were created (`source` `dashboard/hermes_message`) | **FAIL** | `queue_effect.items_created = 0`; `work_items.jsonl` unchanged at 791 lines, same sha256 before/after |
| 3 | Decomposition/worker sessions on `aos-orchestrator` have messages, matching `hermes-*.json` context assembly exists | **FAIL** | Session `20260911_031449_9c0c2a`: `message_count=0`; no context-assembly file for it in `queue/context_assemblies/` |
| 4 | `HANDOFF_OK` appears in the worker's receipt | **FAIL** (no worker ran — no queue item existed) | — |
| 5 | Review passed, child reached `done` | **FAIL** (no child existed) | — |
| 6 | No Telegram or other external message sent | **PASS** | No queue item was ever created, so no completion/Telegram path could fire (X1 A6 gates apply and never engaged) |
| 7 | Invocations within ceiling, per-invocation stats | **PASS** | 1 real model invocation used (David) vs. ceiling 6; decomposition attempt blocked pre-model-call (0 API calls, per `token_usage.available=False`). David: `max_iterations` unbounded (int64 max, relies on 600s wall-clock), 22.985s wall-clock, 1 assistant message. Orchestrator attempt: `max_iterations` unbounded, 13.921s wall-clock, 0 assistant messages. |
| 8 | David residue turn removed through the gated path, verified | **PASS** | See below |

### Criterion 8 — residue removal

- Found: David's real (non-test) turn landed in `sessions/thread_david.md` (thread block
  overwritten) and created a brand-new `sessions/2026-09-11_hermes-cli_7cd4569d6fe3.md` (the
  vault's first journal entry for today).
- **Process gap, disclosed:** this session recorded only the sha256 of `thread_david.md` before
  Part B (Part 0 baseline), not its bytes — a preimage should have been saved before the
  consequential call, per header rule 4/6, and was not. Recovered anyway: the untouched vault
  snapshot `/home/liam/ttros_backups/b7_harness_vault_snapshot_20260910_015654Z/sessions/
  thread_david.md` hashes to `21cc5b8f6f8ed…`, an exact match to the Part 0 baseline hash, proving
  it is byte-identical to the true pre-Part-B state (no legitimate thread update happened between
  that snapshot and this run). Used as the verified preimage.
- Preimages of the **post-Part-B** (contaminated) bytes saved first, refused-if-clobbered, under
  `/home/liam/ttros_backups/stepX2_2026-09-11/`:
  `thread_david.md.PREIMAGE_postB_20260911T101451Z` (sha256 `f819b5cd…`, matches the live file
  exactly) and `2026-09-11_hermes-cli_7cd4569d6fe3.md.PREIMAGE_postB` (sha256 `daa03990…`, matches
  the live file exactly).
- **Written through the gated path only:** `tools/brain_memory.py::write_transaction`, same as
  T8-A, `expected_hashes` pinned to the exact contaminated bytes (refuses on any concurrent
  change), `source="stepX2-residue-cleanup"`. `thread_david.md` restored to the verified
  pre-Part-B content; `2026-09-11_hermes-cli_7cd4569d6fe3.md` reduced to frontmatter + title +
  revisit line + empty `## Conversation` heading (T8-A's pattern for a file whose only turns are
  the ones being removed). Local vault commit `436f5f616377ef4518d053054a61da9bd64167c5`, no push.
- **Verified:** `grep -c "Turn ·"` on the journal file → `0`; `grep -i HANDOFF_OK` across both
  files → no matches. Both files now contain nothing to surface, so no mechanism reading vault
  files off disk (recency block included, per T8-A's finding that it reads `sessions/*.md`
  directly) can return this turn.
- **Exact rollback available**, if this cleanup itself needs undoing: re-run `write_transaction`
  with the two `.PREIMAGE_postB*` files above, `expected_hashes` pinned to the current (cleaned)
  hashes (`9ff625a8…` for the thread, `ce7ca1db…` for the journal).

---

## Invocations used vs. ceiling

**Declared ceiling (Part 0): 6.** Used: **1 real model invocation** (David's turn). The
decomposition attempt was blocked before any model call and consumed 0 API calls. No worker or
review invocation was ever reached. Well within budget in both directions — the shortfall is a
production defect, not a budget overrun.

## What this licenses / does not license

**Licenses:**
- David's `execution_handoff` mechanism itself works correctly end-to-end as far as David's own
  turn — confirmed live, not just in code (X1 already showed this in code; this run is the first
  live confirmation of David's half).
- `aos-orchestrator` (and, by the same guarded code path, every AOS profile) cannot currently
  complete any decomposition/worker/review turn through the production spine — this is now
  directly evidenced (the actual blocking message), not circumstantial, and is a live production
  defect independent of this task.
- The runaway-turn and stop-rule mechanisms X1 described were never exercised (nothing ran long
  enough or multiplied children), so this run adds no new evidence about them either way.
- The gated vault-write path (`write_transaction`) correctly refuses to touch a document whose
  hash has changed underneath it (`expected_hashes` guard) — exercised and confirmed working here.

**Does not license:**
- Any claim identifying the exact line/exception inside `context_assembler_hook.py` that fails in
  production — the isolated reproduction succeeded, which rules out the simplest theory but does
  not name the real one.
- Any claim about whether decomposition would create exactly one child for this task — decomposition
  never ran.
- Any claim that this defect is new — it matches both 2026-09-09 failures exactly; this run's only
  addition is direct evidence of the mechanism, not a new occurrence count.
- Any claim that the residue-cleanup precedent (T8-A's pattern) is validated for files that predate
  the turn being removed and were never a preimage target before this step — this is the first time
  it has been applied to a same-day-created journal file and to `thread_david.md`.

## Model calls made this session: 1 (David's turn). Declared ceiling: 6. No second attempt made.

---
