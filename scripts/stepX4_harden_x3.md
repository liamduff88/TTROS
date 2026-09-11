# STEP X4 — harden X3 (zero model calls)

Session: single session, `/home/liam/agentic-os-live`, 2026-09-11. TTROS permission header and
`CLAUDE.md` read and acknowledged at session start. Every recursive search this session excluded
`connectors/` and `workspaces/north_shore_sales_coach/` from the first command. Model calls: 0.

## Verdict, plain English, first

**Yes — the fallback is now safe against stale files, and the shim is gone.** The X3 artifact
fallback (`dashboard/backend/main.py`, `_queue_artifact_at_workspace_divergence`) now only
accepts a fallback-location file whose mtime is at or after the current attempt's own recorded
start time; a stale or planted file with the right name is rejected exactly like an absent one.
`hooks/context_assembler_hook.py`'s X3 shim (the `sys.modules` alias) is deleted — the real fix
now lives at its source, `dashboard/backend/business_brain_graph.py`'s own import — and both of
X3's own offline positive/negative controls still hold with the shim gone.

Two corrections happened mid-session, both self-caught by the new regression tests before they
reached the suite: the first Part C attempt (copying X3's suggested try/except order verbatim)
did not actually fix anything, and the corrected version then broke three pre-existing tests
elsewhere in the suite. Both are detailed below. Final state: canonical suite 835 passed, 0
failed, 1 skipped (bar was >829/0-failed); Hermes-venv leg exactly X3's same 7 pre-existing
failures, 0 new ones.

## Part A — which location satisfied attempt 2's artifact check

X3's own prose report never states this explicitly; it had to be established from the evidence
X3's live run left behind (receipt + physical files), read fresh this session, not inferred:

- X3's own receipt (`queue/receipts/AOS-2026-0910.md`, read from the scratchpad copy X3 saved):
  `"Artifacts:\n- AVAILABLE: workflows/queue_artifacts/AOS-2026-0910_Execute_local_echo_command_and_capture_exact_out.md (697 bytes; sha256 f835c793b37bbc53f729b634be23e1401cb6322b2c57b84c879b5f45a2085c1e)"`
- Filesystem check of both candidate locations for that exact file: **absent** at the primary
  path (`BASE_DIR/workflows/queue_artifacts/...`); **present**, 697 bytes, at the fallback path
  (`/home/liam/workflows/queue_artifacts/AOS-2026-0910_....md`, i.e. `BASE_DIR.parent`).

**Answer: the X3 fallback satisfied the check for attempt 2 as well as attempt 1** — the same
worker-cwd divergence recurred on a second, independent run. The primary workspace path never
held either attempt's file.

The fallback directory (`BASE_DIR.parent`) is a single constant path, not parameterized by item
id — **shared across every queue item**, not per-item.

## Part B — bounding the fallback

Four controls declared in the transcript before anything ran: stale seed (mtime before attempt
start, primary absent) must BLOCK; fresh file (mtime at/after attempt start) must PASS; nowhere
path must BLOCK; primary hit must PASS unchanged. Prediction, recorded before running control 1:
**~0.7 that the hole is real** (current code accepts a stale fallback file).

**Run against the X3 preimage (current code, before any edit):** control 1 **FAILED** the "must
BLOCK" requirement — a stale file (mtime 5 minutes before attempt start) was returned
`available: True`. Controls 2/3/4 already passed (no mtime gate existed at all, so a fresh file
was never at risk, and the other two paths were untouched by this defect). **Prediction
confirmed — the hole was real.**

**Fix:** `_queue_artifact_at_workspace_divergence` gained a keyword-only `not_before` parameter;
it returns `None` (fails closed) when `not_before` is `None` or the candidate's mtime is earlier
than it. The caller supplies the attempt's own recorded start time —
`item["claim"]["claimed_at"]`, the timestamp `QueueStorage.claim_item` already writes when a
worker attempt begins — parsed via the existing `_parse_record_timestamp` helper (reused, not
reinvented). **Rerun of all 4 controls against the patched code: all 4 PASSED.**

## Part C — the bare import, and two self-caught corrections

**First attempt (wrong, self-caught):** copied the try/except pattern in the same order the step
suggested (bare first, `tools.`-qualified as fallback). Reran the new class-identity regression
test against this: **both tests still failed.** Cause: `business_brain_graph.py` itself
unconditionally pushes `TOOLS_DIR` onto `sys.path` two lines above the import, so a bare-first
try always succeeds locally and never falls through — copying the other file's order doesn't
close *this* file's split.

**Corrected fix:** reversed the try order — qualified (`tools.business_brain_scope`) first,
falling back to the bare name only on `ModuleNotFoundError` (needed for standalone CLI use,
`python3 dashboard/backend/business_brain_graph.py ...`, where repo root isn't on `sys.path`).
Confirmed standalone CLI still works (`--help` prints normally, exercising the fallback branch).
Reran the regression test: both passed.

**Second correction, found by the full suite (not by the targeted regression tests):** the full
canonical suite then showed 3 failures, all the same pattern — a bare-class `ClientScopeError`
escaping uncaught — in tests that build their scope registry via
`tests/business_brain_test_support.py::make_registry()`, an existing file bare-importing
`ClientScopeRegistry`. Before this fix, that bare fixture accidentally matched
`business_brain_graph.py`'s own bare import (both wrong together — exactly how X3's live defect
went unnoticed by the suite); after switching to qualified-first, the identity split just
inverted. Checked whether this matters live: `dashboard/backend/main.py` never calls
`business_brain_graph.query_targets` or constructs its service at all (0 hits) — the only real
caller is the Hermes-hook chain (always qualified, unaffected); the regression was suite-only.

Not authorized to edit the test fixture file this step, so the fix stays inside
`business_brain_graph.py`: it now also imports the *other* spelling's `ClientScopeError` and
catches a tuple of both identities in `add_candidate()`'s except clause (collapsed to one class
when they're already identical). This is more defensive than the step's literal one-line
suggestion — it catches an out-of-scope `ClientScopeError` regardless of which import spelling
produced the registry that raised it — and stays entirely inside the one authorized file/import
site. Reran the 3 previously-failing tests plus both new regression files: 47 passed, 0 failed.

**Other bare imports of `business_brain_scope`, searched and reported** (protected paths
excluded from the first command): `dashboard/backend/business_brain_graph.py:31` — fixed, on the
Hermes-hook chain. `dashboard/backend/main.py:68` — not on the Hermes-hook chain (main.py never
calls this graph code; it bare-imports `business_brain_scope` self-consistently alongside its
own other bare imports), left unchanged. `tests/test_business_brain_scope.py:11`,
`tests/test_step4_entity_relationships.py:11`, `tests/test_business_brain_search_scope.py:12`,
`tests/business_brain_test_support.py:4` — test-only, each inserting `tools/` onto `sys.path`
themselves (existing convention), not on the Hermes-hook chain, left unchanged.

**Shim disable/remove:** disabled (commented out) X3's `sys.modules` alias in
`hooks/context_assembler_hook.py`; reran X3's own offline positive control (real 6,379-char
decomposition prompt) and negative control (no `AOS_STEP6_WRAPPED`) in-process, same replication
X3 used. Positive: marker present, `joined_len=52317`. Negative: `results_count=0`, no marker,
0.287s — matches X3's own negative-control shape almost exactly. **Both held** → shim deleted
(not left commented). Confirmed via `diff` against the preimage that only the shim's
comment+two-line region changed; STEP T7's test-turn gate is byte-for-byte identical outside it.
Reran both controls again against the file with the shim fully deleted: identical results.

## Part D — regression tests and suites

Two new test files (both under the authorized "new regression test file(s)" scope):

- `tests/test_business_brain_graph_scope_import_identity.py` — the class-identity case: asserts
  `business_brain_graph.ClientScopeError is tools.business_brain_scope.ClientScopeError`, and
  exercises the real `validate_graph_target` call with a real (qualified) registry, asserting the
  resulting `ClientScopeError` is caught. Both fail on the X3 preimage (shown above), both pass
  after the fix.
- `tests/test_queue_artifact_workspace_divergence_fallback.py` — the 4 Part B controls, each
  calling the real `_queue_verified_artifacts_from_worker_result` against an isolated temp
  `BASE_DIR`/`BASE_DIR.parent` pair. Control 1 fails on the X3 preimage (shown above), all 4 pass
  after the fix.

**Canonical suite**
(`PYTHONPATH=/home/liam/ttros-testenv/pytest dashboard/backend/.venv/bin/python -m pytest`):
**835 passed, 0 failed, 1 skipped**, 223 subtests, 391.84s. Bar declared ("count rises above 829,
0 failed") — **met**.

**Hermes-venv leg**, run exactly as X3 ran it
(`/home/liam/.hermes/hermes-agent/venv/bin/python3 -m pytest --ignore=tests/test_telegram_conversational_routing.py`):
**7 failed, 813 passed, 1 skipped**, 218 subtests, 309.78s — the identical 7 names in
`tests/test_brain_memory_mcp_intake_passage.py::OpenNoteIntakePassageTests` X3 already confirmed
pre-existing and unrelated. **0 new failures.** Bar — **met**.

## Preimages and rollback (header rule 4/6)

All under `/home/liam/ttros_backups/stepX4_2026-09-11/` (working-tree preimages, never HEAD —
these files carry uncommitted T7/X3 work):

| File | Preimage sha256 |
|---|---|
| `dashboard/backend/main.py` | `67de64d5b5a3a8893dc2f0d44bd87e1097528109893f0fd4b4d32d699e1d2797` |
| `dashboard/backend/business_brain_graph.py` | `6ce8879c6dc0db59ed12c3eaf35b3b1342d27939c02a7c96ffca2c66fea208cf` |
| `hooks/context_assembler_hook.py` | `a7a82ad2ed2c0798e0d0f24304342874d7df0e69ab456ee3b5d76c06e28093c7` |

(`main.py` and `context_assembler_hook.py` preimage hashes match X3's own recorded "patched"
hashes exactly — the on-disk starting state for this step was confirmed to be exactly what X3
left.) Rollback for any file: `cp` the matching `.PREIMAGE` back over the live path.

Live sha256 after this step: `main.py` `584b5e81dd45f3d24720bacea83dfd78872d5c186b72b08c0401a5cace1d2924`;
`business_brain_graph.py` `29dd6a1de5a92639db8b8ae5274a2d39372db66bf9cfbe2323f4fc924ef709c9`;
`context_assembler_hook.py` `0dbb4ec6fc8dfd6fdd943b6033f5c7db0a473fe80b6235fc58f7e1115c5e97b7`.

## Exact diff locations (not full diffs — see transcript for the full diffs)

- `dashboard/backend/main.py`: `_queue_artifact_at_workspace_divergence` signature + body
  (added `not_before` gate), and `_queue_verified_artifacts_from_worker_result` (computes and
  threads `attempt_not_before`). ~line 5946 onward.
- `dashboard/backend/business_brain_graph.py`: import block, line 31 region (qualified-first
  try/except + dual-identity `_CLIENT_SCOPE_ERRORS` tuple), and the one `except` clause using it,
  ~line 543.
- `hooks/context_assembler_hook.py`: shim comment+two-line region only, ~lines 23-39 of the
  preimage; everything else byte-for-byte identical (confirmed by `diff`).

## Files changed

- `dashboard/backend/main.py` — Part B fix.
- `dashboard/backend/business_brain_graph.py` — Part C fix.
- `hooks/context_assembler_hook.py` — X3 shim removed.
- `tests/test_business_brain_graph_scope_import_identity.py` — new.
- `tests/test_queue_artifact_workspace_divergence_fallback.py` — new.

No other files edited. No commits, no push, no git action. Model calls: 0.

## What this licenses, and what it does not

**Licenses:** the artifact fallback can no longer be satisfied by a stale or planted file with
the right name — only a file written at or after the current attempt's own start time. The
Step 6 mandatory-context guard's fix now lives at its actual source
(`business_brain_graph.py`'s import) rather than a subprocess-local shim, proven equivalent
offline (both of X3's own controls hold), and is additionally robust to either import spelling
producing the scope-check exception, not just the one the hook-chain happens to use.

**Does not license:** a live re-run. No queue item was run, no service restarted, no Hermes
invocation made this session (0 model calls, as declared). The offline proof here (regression
tests + both offline hook controls + full suites) establishes that the STEP X3 live behavior
should be unaffected, but that is not the same as re-observing it live — if anything about this
step's changes turns out to alter behavior the X3 live run actually relied on, that would need
its own live check, which this step does not authorize and did not attempt.

Transcript beside this report: `scripts/stepX4_harden_x3.transcript.txt`.
