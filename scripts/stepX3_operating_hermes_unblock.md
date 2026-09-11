# STEP X3 — Unblock Operating Hermes: root cause, fix, live re-run

Session: single session, `/home/liam/agentic-os-live`, 2026-09-11. TTROS permission header and
`CLAUDE.md` read and acknowledged at session start. Every search this session excluded
`connectors/` and `workspaces/north_shore_sales_coach/` from the first command.

## Verdict, plain English, first

**Yes — Operating Hermes now runs a David handoff through the real spine, end to end, with a
real terminal command executed and a truthful artifact-verified `done` closeout.** Two
independent, unrelated defects were blocking this, both found and fixed this session:

1. **The Step 6 mandatory-context guard defect (the one this step was opened to fix).** A module-
   identity split in the import chain meant `dashboard/backend/business_brain_graph.py`'s own
   out-of-scope-node safety net silently failed to catch what it was written to catch, so a
   normal-sized decomposition prompt crashed context assembly with an exception that got
   swallowed at three separate layers, leaving Hermes's native fail-closed guard to block the
   model call with no visible error. Fixed with a one-file, additive shim in
   `hooks/context_assembler_hook.py` — the authorized file for this defect.
2. **A second, unrelated defect found live in Part C attempt 1, fixed under your explicit
   authorization mid-session.** A worker session can genuinely write its required artifact file
   but land it one directory above the workspace root (a cwd-tracking divergence inside Hermes's
   own terminal/file tools — not something this repo's rules permit patching, per header rule 9,
   "Hermes stays unforked and unpatched"). The queue's own artifact-verification code only ever
   checked one location, so a truthful worker got the same "genuinely absent" block a lying one
   should get. Fixed with an additive, narrowly-scoped fallback check in
   `dashboard/backend/main.py`, proven not to weaken the block for a genuinely absent artifact.

Attempt 1 (after fix #1, before fix #2) reproduced fix #1 working — David handed off, decomposition
ran, the worker genuinely executed `echo HANDOFF_OK` and a reviewer session ran — but the item
landed on `blocked` because of defect #2. Attempt 2 (after both fixes, backend restarted) completed
cleanly: `status: done`, `honest_status: done`, review result `PASS`, artifact verified available,
`HANDOFF_OK` in the receipt. 9 of the declared 12 invocations used across both attempts, 0 stop-rule
triggers, 0 external sends.

---

## Part A — root cause, zero model calls

**Predictions (written before any check): H1 ~0.6, H2 ~0.3, other ~0.1.**

### H1 — env does not reach the hook

**Refuted.** Traced Hermes v0.21.1's shell-hook spawn call
(`agent/shell_hooks.py:_spawn`, `subprocess.Popen(argv, env=delegated_child_subprocess_env(), ...)`)
and confirmed `delegated_child_subprocess_env()` returns `None` (full env inheritance) unless a
delegated-child marker is present, which it never is for this path. Confirmed `hermes_cli/main.py`'s
`-p <profile>` handling (`_apply_profile_override()`) sets `os.environ["HERMES_HOME"]` as a real
env var (not just a context-local override) before any imports run.

**Decisive test (as the step specified):** drove Hermes's own hook-invocation function in-process —
`load_config()` → `discover_plugins()` → `agent.shell_hooks.register_from_config()` →
`hermes_cli.lifecycle.invoke_hook("pre_llm_call", ...)` — replicating the exact CLI startup order
from `hermes_cli/main.py`, with the coordinator's exact environment (`AOS_STEP6_WRAPPED=1`,
`AOS_STEP6_SCOPE_TYPE`, `AOS_STEP6_SCOPE_ID`, `HERMES_HOME=.../profiles/aos-orchestrator`),
first under my own shell, then re-run under a fully reconstructed clean chain
(`env -i` with exactly the `aos-backend.service` systemd environment, then `bash -lc` replicating
`WSL_ENV` + the coordinator's own `export` lines) to rule out an inherited-env artifact from my own
interactive shell. Both runs: variables arrived intact, the hook produced the
`TTROS_ASSEMBLED_CONTEXT_V1` marker. **H1 is refuted per the step's own refutation criterion.**

### H2 — a paused Step 6 scope latches

**Refuted.** Read `tools/step6_cost_control.py`: `record_unavailable_invocation()`'s own docstring
says it deliberately writes a row with no canonical token total specifically so the named scope
"fail[s] closed on the next preflight" — a genuine, real latch mechanism when it fires twice on the
*same* scope. But `_run_hermes_message()` (`dashboard/backend/main.py`) computes a fresh,
UUID-derived scope per call (`derive_step6_scope(session_id=context.session_id or invocation_id, ...)`),
so no dashboard-originated call ever collides with a prior one's scope. Checked the actual ledger
row for X2's failed scope (`session dashboard-243593f4da6a43bd8fee1410bb49b3a4`,
`queue/token_ledger.jsonl`): exactly one row exists, timestamped *after* the failure (the
`record-unavailable` side effect of the failure, not a pre-existing pause). **No pause record
existed for the scope the coordinator actually used before that call — H2 is refuted per the
step's own refutation criterion.**

### Onset and the real defect

With both named hypotheses refuted, drove the same in-process reproduction with the **real**
decomposition prompt (reconstructed via `dashboard.backend.main._hermes_decomposition_prompt()` +
`assemble_model_context()`, 6,379 chars — X2's own synthetic isolated-hook test used a ~40-char
message, which is why it looked healthy) instead of a short synthetic one. **This reproduced the
failure deterministically, offline, in ~10 seconds, zero model calls:**

```
Hook 'pre_llm_call' callback _pre_llm_call raised: TTROS Context Assembler hook failed
```

Called `evaluate()` directly (bypassing the JSON-only interface that discards tracebacks) to get
the real exception:

```
tools.business_brain_scope.ClientScopeError: Business Brain pointer does not belong to global:
business_brain:sources/intake/INDEX.md
  ...
  File ".../dashboard/backend/business_brain_graph.py", line 528, in query_targets
    add_candidate(node_id, score, "direct deterministic query match")
  File ".../dashboard/backend/business_brain_graph.py", line 519, in add_candidate
    scoped_path = gate.validate_graph_target(...)
  File ".../tools/business_brain_scope.py", line 148, in validate_graph_target
    canonical = self.validate_brain_pointer(...)
  File ".../tools/business_brain_scope.py", line 98, in validate_brain_pointer
    raise ClientScopeError(...)
```

`business_brain_graph.py`'s `add_candidate()` *already has* `try: ... except ClientScopeError:
return` around exactly this call — its own designed safety net for "this graph node belongs to a
scope this query can't see, skip it." The exception escaped anyway. Root cause, confirmed
empirically (`id()`/`sys.modules` inspection in-process):

```
tools.context_assembler.ClientScopeError  -> module 'tools.business_brain_scope'  (id A)
dashboard.backend.business_brain_graph.ClientScopeError -> module 'business_brain_scope' (id B)
same class? False
```

`dashboard/backend/business_brain_graph.py` line 31 does an **unconditional bare** `from
business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry` (it puts its own
`tools/` directory straight onto `sys.path`, by design, so it can run standalone from the dashboard
backend's own process where `TOOLS_DIR` is also bare-importable). Every other module reached from
the Hermes hook's process (`tools/context_assembler.py`, `tools/business_brain_context.py`) only
ever has the **repo root** on `sys.path`, so their own `try: from business_brain_scope import ...
except ModuleNotFoundError: from tools.business_brain_scope import ...` pattern falls through to
the **qualified** name. Python caches modules by exact import name, so `business_brain_scope` and
`tools.business_brain_scope` become two separate executions of the same file — two distinct
`ClientScopeError` classes. `business_brain_graph.py`'s own `except ClientScopeError` is bound to
the wrong one whenever it's reached via the Hermes-hook path, so it doesn't catch what it's raised.
The exception then propagates uncaught through `assemble()` → this hook's `main()` (catches broadly,
returns `{"error": "context assembly failed: ClientScopeError"}`, exit 1, no traceback) → the native
plugin's `_invoke()` (sees `payload.get("error")`, raises `RuntimeError("TTROS Context Assembler
hook failed")`) → Hermes's `PluginDispatchMixin.invoke_hook()` (catches per-callback, logs a
warning, continues) — three independent silent-swallow layers, which is exactly why nothing
diagnostic ever reached any log X1 or X2 checked. No context, no `TTROS_ASSEMBLED_CONTEXT_V1`
marker → Hermes's own native guard in `agent/turn_context.py` raises "mandatory assembled context
is absent" before any model call.

**Onset:** this is a data-shape trigger, not a Step-9-upgrade code regression — the bug's mechanism
(two import spellings of the same module) has likely existed since `business_brain_graph.py` was
written, but nothing in the graph ever surfaced an out-of-scope node to a global-scope
`aos-orchestrator` decomposition query until the `sources/intake/INDEX.md` node was indexed by the
recent STEP I1–I3 source-intake ingestion work (landed 2026-09-09 through 2026-09-11, the same
window as the three observed failures). STEP U's own smoke check 6 passed because it never
exercised a decomposition-shaped prompt against the post-ingestion graph.

**Named exception, decisively, per the step's own bar:** `tools.business_brain_scope.ClientScopeError`
vs. `business_brain_scope.ClientScopeError` — a Python module-identity split, not H1, not H2, not
"unknown."

---

## Part B — fix #1 (Step 6 guard), zero model calls

**Exact change:** `hooks/context_assembler_hook.py`, immediately after the `sys.path.insert` for
`ROOT` and before any `tools.*` import — pre-load `tools.business_brain_scope` and alias it under
the bare name in `sys.modules` before anything else can create a second, distinct copy:

```python
import tools.business_brain_scope as _tools_business_brain_scope
sys.modules.setdefault("business_brain_scope", _tools_business_brain_scope)
```

This restores `business_brain_graph.py`'s own existing `except ClientScopeError: return` to the
behavior it already has everywhere else in this repo — it does not touch, weaken, or bypass the
scope-enforcement check itself (`validate_brain_pointer` still raises for a genuinely out-of-scope
pointer; it's just now caught by the code that was written to catch it, exactly once, instead of a
second copy of the same class it can never match).

**Preimage (working tree, per header rule 4/6):**
`/home/liam/ttros_backups/stepX3_2026-09-11/context_assembler_hook.py.PREIMAGE`, sha256
`c92ac0bf843fd573dbdbe1b5d7268bc30fb5caa9693ae8bf6d0b2ed23e076339`.
**Rollback:** `cp` the preimage back over `hooks/context_assembler_hook.py`, `chmod 755`.

**Offline proof:**
- Positive: in-process reproduction with the real 6,379-char decomposition prompt, under the fully
  reconstructed clean-env chain — now yields a context marker (`joined_len=52255`).
- Negative control: same reproduction with `AOS_STEP6_WRAPPED` unset — still fails closed
  (`results_count=0`, no marker, 0.29s) — the wrapper guard is untouched.
- Suite, canonical env (`PYTHONPATH=.../ttros-testenv/pytest dashboard/backend/.venv/bin/python -m
  pytest`): **829 passed, 1 skipped, 0 failed** (this run's own count, not compared to the stale
  772/746/760 baselines).
- Suite, Hermes-venv leg (`/home/liam/.hermes/hermes-agent/venv/bin/python3 -m pytest`,
  `--ignore=tests/test_telegram_conversational_routing.py` — that one file can't even collect
  there: `ModuleNotFoundError: No module named 'tiktoken'`, a pre-existing dependency gap in
  Hermes's own venv, unrelated to anything touched this session): **807 passed, 7 failed, 1
  skipped.** The 7 failures, all in `tests/test_brain_memory_mcp_intake_passage.py::
  OpenNoteIntakePassageTests`:
  - `test_bare_pointer_without_extension_resolves`
  - `test_open_note_without_query_keeps_original_truncate_behavior`
  - `test_prefixed_pointer_with_extension_still_resolves`
  - `test_prefixed_pointer_without_extension_resolves`
  - `test_query_downweights_a_term_repeated_throughout_the_note`
  - `test_query_returns_bounded_passage_containing_match`
  - `test_query_with_verified_absent_term_returns_no_passage`

  **Confirmed pre-existing, not caused by this session's fix:** restored the working-tree file to
  the exact preimage bytes, re-ran the full suite under the Hermes venv again — **identical result,
  same 7 names, same counts** (`7 failed, 807 passed, 1 skipped`). Restored the fix afterward
  (verified sha256 back to `a7a82ad2ed2c0798e0d0f24304342874d7df0e69ab456ee3b5d76c06e28093c7`,
  mode 755). This venv gap is a Hermes-venv-specific environment difference (isolated in that one
  test file only, in isolation the same 10 tests pass in 0.77s), not a defect this session
  introduced or is authorized to chase further.
- David's 6 representative `pre_llm_call` cases (varied: short/long, with/without sticky key,
  execution-handoff-shaped, empty message), preimage vs. patched, byte-for-byte: **zero drift**
  once one pre-existing, unrelated wall-clock noise line (a detector's own "Fresh deterministic
  snapshot `<timestamp>`" stamp, present and varying by design in both preimage and patched runs) is
  normalized out.
- Hook mode: 755, unchanged.

**What this licenses:** the Step 6 mandatory-context guard now completes for a realistic
decomposition-shaped prompt on `aos-orchestrator` (and, by the identical code path, every other
`AOS_PROFILES` member) without weakening the guard, the `AOS_STEP6_WRAPPED` check, or the
`ClientScopeError` scope enforcement itself. **What it does not license:** a claim that this is the
"correct" long-term fix — see Recommendation below.

**Recommendation for a future step (not applied this session, per your instruction — the hook
shim is fine for now):** the durable fix is correcting the import at its actual source,
`dashboard/backend/business_brain_graph.py:31` — `from business_brain_scope import
ClientScopeError, ClientScopeRegistry, load_registry` — to the same try/qualified-fallback pattern
already used by `tools/context_assembler.py` and `tools/business_brain_context.py`:

```python
try:
    from business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry
except ModuleNotFoundError:
    from tools.business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry
```

That closes the identity split at its origin for every caller, not just the Hermes-hook path; the
`sys.modules` alias in `hooks/context_assembler_hook.py` is a correct, safe, working shim in the
meantime but is a symptom-side patch, not the root fix.

---

## Part B — fix #2 (artifact verification), found and fixed live during Part C, explicitly
authorized mid-session

Not part of the step's original Authorized file list; you explicitly widened scope in-session
("find why the worker claims an artifact that was never written... fix it now, same rules") after
Part C attempt 1 reproduced fix #1 working but landed the item on `blocked` for a second, unrelated
reason.

**What happened (attempt 1):** David handed off, decomposition created one child (AOS-2026-0900),
the worker (session `20260911_061111_82832e`) genuinely called `terminal` (`echo HANDOFF_OK`,
`exit_code 0`) then `write_file` for `workflows/queue_artifacts/AOS-2026-0900_....md`, and the
write tool reported success (`bytes_written: 656, verified: true`). The review
(`_queue_review_decision` in `dashboard/backend/main.py`) checks the worker's *claimed* "Files
touched" path against `BASE_DIR / path` only — but Hermes's own write tool's reported
`resolved_path` was `/home/liam/workflows/queue_artifacts/AOS-2026-0900_....md`, one directory
**above** `BASE_DIR` (`/home/liam/agentic-os-live`). Confirmed the file genuinely exists there
(656 bytes, content matches the claim exactly). This is Hermes's own documented failure class —
`tools/file_tools_paths.py`'s own docstrings name it "the worktree-cwd bug" / "workspace
divergence" and the write tool itself always reports the absolute `resolved_path` "so a wrong-cwd
mismatch is visible in the response instead of silently landing elsewhere." I could not pin down
*why* the terminal tool's session-cwd tracking diverged for that one invocation — direct,
zero-cost reproductions of the same tool-call sequence (`terminal_tool()` then `write_file_tool()`,
same profile, same fresh-env chain, both a `task_id="default"` case and one matching the real
session-id shape) resolved correctly every time, and attempt 2's worker (same code, same profile,
run minutes later) also resolved correctly on its own. This reads as a rare, non-deterministic
divergence inside Hermes's own terminal-tool cwd tracking, not a deterministic bug I could isolate
further without the full agentic-turn runtime context — and per header rule 9 ("Hermes stays
unforked and unpatched"), fixing Hermes's own tool internals is out of bounds regardless.

**The fix, entirely in this repo's own code:** `dashboard/backend/main.py`,
`_queue_verified_artifacts_from_worker_result()` — when the claimed path is absent at the canonical
`BASE_DIR`-relative location, check exactly one additional, narrowly-scoped, well-justified
location before concluding "genuinely absent": `BASE_DIR.parent / path` (new helper
`_queue_artifact_at_workspace_divergence()`). `path` has already passed
`_queue_normalize_artifact_path()` by this point (allowlisted prefix — `queue/receipts`, `results`,
`workflows`, `packets`, `logs` only; allowlisted extension — `.md`/`.txt`/`.json`/`.jsonl` only; no
`..` components), so the fallback can only ever reach the same narrow artifact directories one level
up — never a credential, config, or arbitrary filesystem path. **A claim missing at *both*
locations still returns unavailable and still blocks** — the check is not relaxed for a genuinely
false claim, only widened to recognize a genuinely true one that landed at Hermes's own documented
alternate location.

**Preimage:** `/home/liam/ttros_backups/stepX3_2026-09-11/main.py.PREIMAGE_artifactfix`, sha256
`e26333254d2db6d03a3046c1256cd8b8701d79b17f45e9afe084d0801a0f523b`.
**Rollback:** `cp` the preimage back over `dashboard/backend/main.py`.

**Offline proof (both directions, before any live use):**
- Positive: replayed AOS-2026-0900's exact worker-output text through
  `_queue_review_decision()` — now returns `("PASS", "PASS")` (was REVISE/"genuinely absent").
- Negative control: a fabricated claim for a path that exists at **neither** location
  (`AOS-9999-9999`, a made-up item id/title) — still returns `("REVISE", "Claimed canonical
  artifact is genuinely absent: ...")`. The block is intact for a real false claim.
- Suite, canonical env, both fixes combined: **829 passed, 1 skipped, 0 failed** — no regression
  from stacking the two fixes.

**Deployment:** this fix lives in `dashboard/backend/main.py`, imported once at
`aos-backend.service` startup (unlike the hook fix, which is re-read fresh per Hermes subprocess).
Checked no queue item was `claimed`/`running`/`agent_working` (0 in-flight), then `systemctl --user
restart aos-backend.service`; confirmed `active` and `/api/health` returned `200` before Part C
attempt 2.

**Disclosed, not cleaned up (permission denied, not forced):** one 13-byte throwaway diagnostic
file from testing this fix, `workflows/queue_artifacts/REPRO_TEST_ARTIFACT.md` — an `rm` to remove
it was denied, so it's left in place rather than retried. Harmless; safe to delete at your
convenience.

---

## Part C — live re-run

Before each attempt: saved vault-file **bytes** (not only hashes) of `sessions/thread_david.md` and
today's journal, per header rule 4/6. Checked `aos-backend`/`aos-runner` active and no in-flight
queue items before each send. Sent X2's message verbatim both times:

> "Please hand this to Operating Hermes: run the local command `echo HANDOFF_OK` in a terminal and
> report its output. It is a harmless connectivity test with no external effect."

### Attempt 1 (fix #1 only) — `POST /api/dashboard/ask-david`, 2026-09-11T13:09:40Z–13:11:01Z (80s)

Parent `AOS-2026-0899` / child `AOS-2026-0900` created (`source: dashboard/hermes_message`,
`queue_delta: 2`). Decomposition, worker, and reviewer sessions all ran on `aos-orchestrator` with
real messages and matching `queue/context_assemblies/hermes-*.json` files. Worker genuinely ran
`echo HANDOFF_OK` (`stdout: HANDOFF_OK`, `exit_code: 0`) — **this alone proves fix #1 unblocked the
Step 6 guard**, which is the defect this step exists to fix. Review returned `REVISE` on defect #2
(artifact genuinely absent at the checked location); the loop's own "claimed canonical artifact
genuinely absent" break condition stopped it there — item `blocked`, not `done`. 4 invocations used
(david, decomposition, worker, reviewer — all within the 6-per-attempt ceiling). No second child, no
stop-rule trigger. Cleaned David's residue through `tools/brain_memory.py::write_transaction`
(`expected_hashes` pinned to the exact contaminated bytes; verified `HANDOFF_OK` absent from both
vault files afterward, 0 matches).

**Between attempts:** diagnosed and fixed defect #2 (above), proved it offline, restarted
`aos-backend.service`.

**Vault moved on between attempts, independent of this step:** before re-baselining for attempt 2,
found the vault had a *new, legitimate* turn — a scheduled morning-brief David consultation
(session `20260911_080031_c824a9`, 2026-09-11T15:00:53Z, "This is a scheduled read-only morning
interpretation...") that ran on its own, unrelated to this session. Re-baselined bytes from the
*current* live files (not the stale pre-attempt-1 backup) before attempt 2, so the residue-cleanup
afterward would preserve that real turn rather than reverting past it.

### Attempt 2 (both fixes) — `POST /api/dashboard/ask-david`, 2026-09-11T18:55:51Z–18:57:01Z (70s)

Parent `AOS-2026-0909` / child `AOS-2026-0910` created (`source: dashboard/hermes_message`,
`queue_delta: 2`). All 8 acceptance criteria, each with evidence:

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | `execution_handoff` in David's reply | **PASS** | `david_note`/`handed_objective`/`scope_hint: single_step` in the `ask-david` response |
| 2 | Parent + child queue items, `source: dashboard/hermes_message` | **PASS** | `AOS-2026-0909` (parent, `done`) / `AOS-2026-0910` (child, `done`), both `source: dashboard/hermes_message` |
| 3 | Decomposition/worker/review sessions on `aos-orchestrator` have messages, matching `hermes-*.json` | **PASS** | 4 `aos-orchestrator` sessions (`20260911_115639_021842` decomposition, `20260911_115713_463fdc` worker, `20260911_115747_27adce` reviewer, `20260911_115804_ea5ddf` parent-closeout) each with a matching `queue/context_assemblies/hermes-<session-id>-*.json`; plus david's own `20260911_115605_7f5c0f` |
| 4 | `HANDOFF_OK` in the worker's receipt | **PASS** | Receipt: `Stdout: \`HANDOFF_OK\``, `Command run: \`echo HANDOFF_OK\`` |
| 5 | Review passed; child `done` | **PASS** | `Review result: PASS`; item `status: done`, `honest_status: done` |
| 6 | No Telegram or other external message sent | **PASS** | `logs/dashboard_backend.log` `telegram_close_hook` entries all dated July 2026, none from 2026-09-11, none referencing `AOS-2026-0909`/`0910` |
| 7 | Invocations within ceiling, per-invocation stats | **PASS** | 5 invocations this attempt (david 1 api call/18.0s; decomposition 1/19.9s; worker 3/23.7s; reviewer 1/12.2s; parent-closeout 1/9.8s — all `max_iterations` unbounded int64, relying on the 600s wall-clock kill); `queue/token_ledger.jsonl` shows 5 clean `model_invocation` rows in this window, all `accounting_status` unset (no "unknown"/unavailable, unlike X2's failed attempt) |
| 8 | David residue removed through the gated path, verified | **PASS** | `write_transaction`, `expected_hashes` pinned to the exact contaminated bytes; journal reduced from 2 turns to the 1 legitimate morning-brief turn; `grep -c "Turn ·"` → 1; `grep -i HANDOFF_OK` → 0 matches in both files; morning-brief content confirmed still present |

Both attempts combined: **9 of the declared 12 invocations used.** Stop rule never triggered in
either attempt (never more than one child, never a session beyond the per-attempt ceiling).

Attempt 1's items (`AOS-2026-0899`/`AOS-2026-0900`) are left as a historical `blocked` record,
superseded by attempt 2's clean `done` completion — nothing about a `blocked` item required
cancellation under this step's stop rule (that rule is for exceeding the invocation ceiling or
multiple children, neither of which happened).

---

## What this licenses, and what it does not

**Licenses:** Operating Hermes (`aos-orchestrator`, and by the identical code path every other
`AOS_PROFILES` member) can now complete a decomposition, worker, and review turn through the
production `ask-david` → `hermes_message` → `run_queue_item` spine for a realistic prompt, without
the Step 6 guard, the `AOS_STEP6_WRAPPED` wrapper check, or `ClientScopeError` scope enforcement
being weakened. A worker that genuinely produces its required artifact — including in the one
documented Hermes cwd-divergence pattern — can now reach `done`; a worker that does not produce it
anywhere real still gets blocked.

**Does not license:** a claim that `dashboard/backend/business_brain_graph.py`'s import is fixed at
its source (the hook shim works around it; see Recommendation above) — nor a claim that the
Hermes-internal terminal-tool cwd-tracking divergence itself is understood or fixed (it is worked
around at the verification layer, once, for the one alternate location it's documented to produce;
if Hermes ever diverges to some *other* location this fix will not catch it, and that would need
its own investigation, on Hermes's side, out of this repo's reach per header rule 9). Does not
license any claim about the 2026-09-09 14:13 PDT bulk config-rewrite event (X1/X2's own open
"unknown," untouched this session). Does not license git commit or push (none made; not
authorized this step).

## Invocations used against the declared ceiling

Part A: 0. Part B (both fixes, all offline proof): 0. Part C attempt 1: 4. Part C attempt 2: 5.
**Total: 9 of 12 declared.**

## Files changed this session

- `hooks/context_assembler_hook.py` — fix #1 (Step 6 guard). Preimage + sha256 above.
- `dashboard/backend/main.py` — fix #2 (artifact verification). Preimage + sha256 above.
- No other files edited. No commits, no push.

Transcript beside this report: `scripts/stepX3_operating_hermes_unblock.transcript.txt`.
