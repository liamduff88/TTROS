# B7 zero-model cleanup pass — report

Run date: 2026-09-08. **Model/Hermes/David/provider/B7 calls made by this session: 0.** No B7,
David, or Hermes invocation of any kind (direct or subprocess) was made. Did not start Step
6b/7/8/9, did not touch North Shore, Telegram, or credentials, did not change Hermes's
global/default profile, did not commit or push, spawned 0 subagents.

Authority used: `TTROS_BUILD_PLAN_2026-09-04_rev11.md`, `02_TTROS_ACTIVE_TASK_2026-09-04_rev6.md`,
`00_TTROS_CURRENT_STATE_v2026-09-04_rev6.md`,
`TTROS_CAPABILITY_HARNESS_QUESTIONS_v1_UPDATED_2026-09-04.md`,
`01_TTROS_WORKING_METHOD_v2026-09-02.md`, `scripts/b6_leak_scorer_mechanical_repair_report.md`,
`scripts/b7_contamination_map_and_clean_subset.md`. `docs/ttros/SOURCE.sha256` verified against
all five mirrors before use — all five report `OK`.

---

## 1. B7 guard — run-scoped

**Before:** `hooks/b7_test_material_guard.py`'s `evaluate()` ran its full block logic
(`BLOCKED_TOOL_NAMES` = `search_files`/`read_file`/`execute_code`/`session_search`, plus the
`docs/ttros`/`scripts`/`ttros_backups` path patterns) unconditionally, on every David invocation —
wired into `~/.hermes/profiles/david/config.yaml`'s `hooks.pre_tool_call` with no run-type check.
Normal David use and an actual B7 harness pass were indistinguishable to the hook, so David lost
`search_files`/`read_file`/`execute_code`/`session_search` and all `docs/ttros`/`scripts` access
permanently, not just during B7.

**After:** added `_b7_run_active()` — `bool(os.environ.get("TTROS_BRAIN_ROOT", "").strip())` — as
the first check in `evaluate()`; when false, the hook returns `{}` (no-op) before any blocking
logic runs.

**Mechanism chosen and why (smallest existing mechanism, no new framework):** `TTROS_BRAIN_ROOT`
is set in exactly three places in the repo — the `env["TTROS_BRAIN_ROOT"] = str(WORK_VAULT)` line
in each of `scripts/step3_b7_harness.py`, `scripts/step5_b7_growth_harness.py`, and
`scripts/step6_b7_tools_harness.py` — immediately before each script's
`subprocess.run([HERMES_BIN, "-p", "david", ...], env=env, ...)` call. It is read nowhere else
except `tools/brain_memory.py` (vault-root resolution). No normal-David invocation path
(dashboard backend, gateway, direct CLI) sets it — confirmed by grep (`connectors/` excluded, per
protected-path rule; `dashboard/backend/main.py` has zero matches for
`TTROS_BRAIN_ROOT`/`AOS_OPERATOR_CONSULTATION`/direct `-p david` invocation). A hook process
spawned by Hermes inherits the parent's environment, so this is the same
read-`os.environ`-in-a-hook pattern `hooks/context_assembler_hook.py` already uses
(`AOS_OPERATOR_CONSULTATION`, `TTROS_NATIVE_CONTEXT_PLUGIN_REGISTERED`) — reused, not invented.
`~/.hermes/profiles/david/config.yaml` was not touched (out of repo scope); the hook still fires
on every call, it is just a no-op unless the B7 env signal is present.

**Proof normal David is unaffected:** `tests/test_b7_test_material_guard.py`'s new
`NormalDavidIsUnaffectedTests` class runs the identical inputs that `B7LeakClosureTests` proves
get blocked — `search_files`/`read_file`/`execute_code`/`session_search`, `docs/ttros/...`,
`scripts/step3_b7_harness.py`, a prior pass's `.scored.json` — with no `TTROS_BRAIN_ROOT` in the
environment, and asserts `{}` (pass-through) for every one. `B7LeakClosureTests` was rewired to
wrap every case in a new `_b7_env()` context manager (sets `TTROS_BRAIN_ROOT` for the call, mirrors
exactly what the three harness scripts do) so it now proves both halves: guard active with the
signal present, guard inactive without it. 15 tests, 21 subtests, all pass (see §6).

**B7 leak protection preserved during an active run:** unchanged block logic, now reached correctly
— `test_legitimate_business_brain_depth_tools_remain_available` proves
`mcp__brain__{search_calls,open_call,open_note,search_history}` (plus
`remember_brain_knowledge`/`brain_memory_status`) stay available even *with* `TTROS_BRAIN_ROOT` set
(i.e., during an active B7 run, not just when the guard is off).

## 2. Independent revert check

**`hooks/runtime_guard.py`:** `git diff HEAD -- hooks/runtime_guard.py` → **no output, clean.**
Independently confirmed by content hash: `git show HEAD:hooks/runtime_guard.py | sha256sum` and
`sha256sum hooks/runtime_guard.py` both give
`2071731ee1941dda4fbfe13ba74a65e071c5a3da7e68e382429242b46f7b8be8` — byte-identical to the
committed version. A preimage exists at
`/home/liam/ttros_backups/runtime_guard.py.PREIMAGE_20260908T044915Z` (saved 04:49:15Z today,
before this session started) — diffing it against the current file shows the preimage is the
**rogue state**: it contains a `TEST_MATERIAL_PATH_PATTERNS`/`BLOCKED_TOOL_NAMES` block and
matching `evaluate()` logic that the current (and HEAD) file does **not** have. This matches
`scripts/b6_leak_scorer_mechanical_repair_report.md`'s own account: "a first draft of the Part 2
hook logic was produced by a research subagent that exceeded its read-only brief... it edited the
wrong file... and was reverted before anything was wired to a live profile." Independently
verified here as fully reverted, not just self-reported.

**The five unrelated profiles (aos-delivery, aos-marketing, aos-ops, aos-orchestrator,
aos-revenue):** each profile's `config.yaml` still wires
`command: /home/liam/agentic-os-live/hooks/runtime_guard.py` under `hooks.pre_tool_call` (visual
confirmation, all five). Filesystem mtimes on all five `config.yaml` files: **2026-08-04
21:50:45–47** — over a month before both the rogue-subagent incident (2026-09-07/08, per the
mechanical-repair report) and this session. No preimage backup exists for any of the five
`config.yaml` files (none was needed — they were never edited), so there is no independent
pre-incident content hash to diff against; the mtime evidence is what's available. **Verdict:
unchanged, on mtime evidence** (not a byte-hash comparison against a captured pre-incident
snapshot, because none was taken — none of the five profile configs was itself the file the rogue
edit touched). Not modified in this session to "make the check pass," per instruction.

## 3. Polarity sweep — all 99 facts, real frozen scorer

Method: imported `scripts/step3_b7_harness.py` as a module (zero model/Hermes calls — read-only
import of its `QUESTIONS`/`FACT_SOURCE_OVERRIDES` data and the `kw()` helper). For each of the 99
non-honesty facts, reused `score_pass()`'s exact fact-presence predicate verbatim —
`present = all(any(alt.lower() in answer_lower for alt in group) for group in groups)` — against a
synthetic answer built from that fact's own real keyword groups, each one wrapped in an explicit
denial: `"It is NOT the case that <alt>. That is false -- the opposite is true, and <alt> never
happened and was explicitly denied."` Script: (run from scratchpad, not committed — a bounded
one-off measurement per Evidence Discipline, not a new permanent instrument).

**Prediction, written before running:** all 99 facts would still score PRESENT, because
`present`'s only operation is case-insensitive substring containment — there is no negation-aware
logic anywhere in `score_pass()`, so wrapping a required substring in denial language cannot
change whether that substring is present.

**Result — prediction confirmed exactly:**
- **Exact affected fact count: 99 of 99** (100%). `NON_HONESTY_FACT_COUNT` read live from the
  module also equals 99, confirming no facts were missed or double-counted.
- **Exact IDs (all 99):** A1.1–A1.7, A2.1–A2.4, A3.1–A3.5, A4.1–A4.6, A5.1–A5.4, B1.1–B1.5,
  B2.1–B2.4, B3.1–B3.7, B4.1–B4.5, C1.1–C1.3, C2.1–C2.8, C3.1–C3.2, C4.1–C4.3, D1.1–D1.5,
  D2.1–D2.3, D3.1–D3.2, D4.1–D4.2, E1.1–E1.9, E2.1–E2.4, E3.1–E3.4, E4.1–E4.3, E5.1–E5.4 — every
  single non-honesty fact ID that exists.
- **§F/honesty scoring: not affected by this finding.** §F (F1/F2/F3) is `honesty: True` for all
  three questions and is scored by a structurally separate mechanism (`fail_if` groups checked
  against `q["fail_if"]`, not `q["facts"]`) — none of the 99 swept facts belong to §F, and this
  sweep did not touch or exercise the `fail_if` code path. **Observation, not a measured finding:**
  `fail_hit` uses the identical raw substring-containment primitive
  (`any(alt.lower() in answer_lower for alt in group) ...`), so §F is plausibly subject to an
  analogous blindness by the same structural pattern — this was not measured here (out of this
  task's "99 facts" scope, and repairing scorer semantics is explicitly out of scope for this
  pass) and should not be read as confirmed either way.
- **E2's "Mike's advice, not Liam's intention" fact (E2.4): affected — yes.** `E2.4`'s groups are
  a single OR-group `("mike's advice", "advice, not", "not liam's", "reluctant")` (any one
  alternative satisfies it). The synthetic denial embeds `"mike's advice"` verbatim inside `"It is
  NOT the case that mike's advice..."`, so it still scores PRESENT. Concretely and more starkly: a
  real answer asserting the *opposite* of E2.4 — e.g. "this was Liam's own eager idea, not
  reluctant, and not Mike's advice at all" — contains the bare substring `"reluctant"` (inside "not
  reluctant") and would score this fact PRESENT even though the sentence explicitly denies it. This
  is the concrete case the task named, and it reproduces.

Full machine-readable output (all 99 records, each with its groups and synthetic negated answer):
written to the scratchpad, not the repo (bounded one-off, not committed evidence per this task's
DO-NOT list — no scorer files were changed).

## 4. FACT_SOURCE_OVERRIDES — frozen

Source: `scripts/step3_b7_harness.py` lines 406–470 (`FACT_SOURCE_OVERRIDES: dict[str, list[str]]`,
frozen by the prior session's B6 repair, per `scripts/b6_leak_scorer_mechanical_repair_report.md`
Part 1). Read only — not modified.

**Count: 27** (verified programmatically: `len(FACT_SOURCE_OVERRIDES) == 27`, matches the task's
stated count exactly).

**Deterministic hash:** `sha256(json.dumps(FACT_SOURCE_OVERRIDES, sort_keys=True,
separators=(',',':')))` = `19bfababbcf53048e9301bab62bfbc9188b8c25eed42c7afdfaeb0cbfc3b4d86`.

**Version pin (whole scorer file):** `sha256sum scripts/step3_b7_harness.py` =
`2d2aef167321ae7bbf0ba639db027ab92320e0a3b9cd5ce3a46b2a061b1200d4`.

**The 27 mappings, fact ID → source document(s) → basis** (basis text drawn from the script's own
inline comments at time of freeze):

| Fact ID | Source document(s) | Basis |
|---|---|---|
| A2.1 | `memory/offers.md` | Single-doc already given A2's own text; listed for explicitness/testability |
| A2.2 | `memory/offers.md` | Same |
| A2.4 | `memory/offers.md` | Same |
| A2.3 | `memory/positioning.md` | Same |
| A4.1 | `memory/offers.md` | Confirmed two-source-separation case (reconciliation_audit.md Check 5) |
| A4.2 | `memory/offers.md` | Same |
| A4.3 | `memory/offers.md` | Same |
| A4.4 | `memory/positioning.md` | Same |
| A4.5 | `memory/positioning.md` | Same |
| A4.6 | `memory/positioning.md` | Same |
| B3.1 | `memory/ideal_clients.md` | `ideal_clients.md` (the router) alone states the 60/40 split, both ICP names, its own "router" self-description |
| B3.2 | `memory/ideal_clients.md` | Same |
| B3.3 | `memory/ideal_clients.md` | Same |
| B3.4 | `memory/ideal_clients.md` | Same |
| B3.5 | `memory/ideal_clients.md` | Same |
| B3.7 | `memory/ideal_clients.md` | Same |
| E2.1 | `sources/historical_calls/mike-knapp-july-21.md` | The two source docs are dated to different calls; only the July 21 transcript carries this date |
| E2.2 | `sources/historical_calls/mike-knapp-gtm-context-july-22.md` | Dated to the July 22 context packet |
| E2.4 | `sources/historical_calls/mike-knapp-july-21.md` | Only the raw July 21 transcript contains Liam's own "reluctant" framing |
| E3.1 | `sources/historical_calls/first-call-cci.md` | Call-date-specific |
| E3.2 | `sources/historical_calls/cci-second-call-june-15.md` | Call-date-specific |
| E3.4 | `operating_context/current_priorities.md` | Benched status is unrelated to the call corpus entirely (static_forensic_audit.md Part 3) |
| E4.1 | `sources/historical_calls/trent-first-call.md`, `sources/historical_calls/trent-july-9.md`, `sources/historical_calls/INDEX.md` | Cardinality/dates need both call files plus INDEX.md, which also encodes both dates |
| E4.2 | `sources/historical_calls/hermes-water-treatment-summary-trent.md`, `sources/historical_calls/INDEX.md` | Separate summary document |
| E5.1 | `sources/historical_calls/andrea-roberts-june-26.md`, `sources/historical_calls/andrea-second-call-june-30.md`, `sources/historical_calls/INDEX.md` | Both dates confirmed in INDEX.md too |
| E5.2 | `sources/historical_calls/andrea-roberts-june-26.md`, `sources/historical_calls/andrea-second-call-june-30.md` | Specific introductions confirmed transcript-body-only in both audits |
| E5.3 | `sources/historical_calls/andrea-roberts-june-26.md`, `sources/historical_calls/andrea-second-call-june-30.md` | Vancouver consultant event confirmed transcript-body-only |

**Deliberately excluded (question-level fallback, not a gap):** `B3.6`, `E2.3`, `E3.3`, `E4.3`
(genuinely ambiguous between two declared docs) and `E5.4` (structurally unreachable regardless of
source docs — true source is a MANIFEST.md-excluded bullet not even in E5's declared list). No
factual error was found in the 27 existing mappings during this pass; none were added, removed, or
changed.

**These 27 mappings are FROZEN as of this pass (2026-09-08, hash
`19bfababbcf53048e9301bab62bfbc9188b8c25eed42c7afdfaeb0cbfc3b4d86`) and must not be tuned after
seeing any future B7 disposition result.** Any future change requires a demonstrable factual error
in the source-document mapping itself, reported before being changed — never a change motivated by
which way a B7 pass's numbers moved.

## 5. Remaining human scoring decisions

These are decisions this pass surfaces but does not make (explicitly out of scope — "do not repair
scorer semantics yet"):

1. **Whether/how to repair `present`'s polarity blindness** — all 99 facts are affected structurally;
   a real David answer that denies or inverts a fact currently scores identically to one that
   affirms it. No repair proposal is offered here.
2. **Whether §F's `fail_if` mechanism has the same blindness in practice** — flagged as a plausible,
   structurally analogous, but *unmeasured* risk (§3 above), not evaluated in this pass.
3. **B3.6 / E2.3 / E3.3 / E4.3 / E5.4** — the five facts with no source-document mapping, still
   resting on the conservative question-level fallback; a human call on whether any can be
   narrowed with more textual evidence remains open.

## 6. Regression

```
git diff HEAD -- hooks/runtime_guard.py       # no output (clean)
PYTHONPATH=/home/liam/ttros-testenv/pytest dashboard/backend/.venv/bin/python -m pytest -q
  → 808 passed, 7 warnings, 216 subtests passed in 347.68s
git diff --check
  → context/TOKEN_POLICY.md:94: new blank line at EOF.
  → hooks/token_budget_check.md:54: new blank line at EOF.
  (both pre-existing modifications from before this session, per `git status --short` on those
  two paths — neither touched by this pass; not fixed, per "do not fix unrelated pre-existing
  whitespace issues")
```

808 ≥ 804 (this pass's own floor), and matches exactly: 804 pre-existing + 4 new tests added in
`NormalDavidIsUnaffectedTests` = 808. 0 failed.

---

## CLOSEOUT

**PASS**

- B7 guard run-scoped: **yes** (`TTROS_BRAIN_ROOT` env gate in `hooks/b7_test_material_guard.py::_b7_run_active()`)
- normal David capability preserved: **yes** (`NormalDavidIsUnaffectedTests`, 4 tests, all pass)
- B7 leak protection preserved: **yes** (`B7LeakClosureTests`, 11 tests wrapped in active-B7-env, all pass; depth tools proven available during an active run)
- `runtime_guard.py` unchanged: **yes** (`git diff HEAD` empty; sha256 identical to `git show HEAD`)
- five unrelated profiles unchanged: **yes, on mtime evidence** (all five `config.yaml` last modified 2026-08-04, predating the incident by a month; no pre-incident hash exists to diff — none was needed since they were never edited)
- polarity sweep complete: **yes**
- polarity-blind facts: **99 of 99** — all IDs listed in §3
- §F affected: **no** (structurally separate mechanism, not exercised by this sweep; analogous risk flagged as unmeasured observation)
- E2 attribution fact (E2.4) affected: **yes**
- FACT_SOURCE_OVERRIDES frozen: **yes** — count 27, hash `19bfababbcf53048e9301bab62bfbc9188b8c25eed42c7afdfaeb0cbfc3b4d86` (scorer file pin: `2d2aef167321ae7bbf0ba639db027ab92320e0a3b9cd5ce3a46b2a061b1200d4`)
- regression result: **808 passed, 0 failed** (804 pre-existing + 4 new)
- files touched: `hooks/b7_test_material_guard.py` (edit), `tests/test_b7_test_material_guard.py` (edit), `scripts/b7_cleanup_pass_report.md` (new, this file). Preimages of both edited files saved at `/home/liam/ttros_backups/step_b7_cleanup_preimages/*.PREIMAGE_20260908T162441Z` before editing (both were untracked, no git history to roll back to).
- blockers: none
- next action: human decision on whether/how to repair the scorer's polarity blindness (§5.1) before any future B7 pass is treated as evidence of capability, since a denied or inverted fact currently scores identically to an affirmed one
- Subagents: 0
- Model/provider/B7 calls: 0
- Token usage: unavailable from current CLI output.
