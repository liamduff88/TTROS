# Phase 2 — instrument defect: no clean model-assisted call path currently reachable

**Status: STOPPED before real rehearsal, per Phase 2.3's own instruction** ("if any verdict
direction or required reason tag cannot be exercised, STOP before freeze and report an instrument
defect, with your diagnosis"). This is that report.

## What was attempted

Call #0 of the declared rehearsal plan (`phase2_rehearsal_plan.md`) — a trivial wiring shakedown,
not a fixture — was sent through `hermes chat --query-file ... --oneshot --ignore-user-config
--ignore-rules -Q -t "" --max-turns 1 --reasoning medium --provider openai-codex -m gpt-5.5
--source tool --run-budget 180`.

## What happened

The call failed locally, before any provider/network call, with:

```
RuntimeError: TTROS model call blocked: mandatory assembled context is absent
```

Raised from `agent/turn_context.py:910` inside `build_turn_context`, in the installed Hermes
agent (`/home/liam/.hermes/hermes-agent`). Full traceback captured in
`scripts/validation_a_runs/blind_run/detector_calls_transcript.jsonl` (call_index 1).

## Diagnosis

This repo has a real, already-tested, fail-closed native guard: every Hermes model call must
carry assembled context injected by a registered plugin (`hooks/hermes_context_assembler_plugin.py`,
registered via `agent.shell_hooks.register_from_config` against a profile's `config.yaml`) before
`build_turn_context` will proceed (`tests/test_hermes_context_plugin.py`,
`tools/validate_unbound_runtime.py`). `--ignore-rules` (used to keep the detector call clean of
AGENTS.md/SOUL.md/memory/skill injection, for blindness) also prevents this plugin registration
from happening for a bare `hermes chat` subprocess call, so the native guard trips and blocks the
call outright — correctly, by design, not a bug in the guard.

The one existing pattern in this repo for making a real, bounded Hermes model call that
**does** satisfy this guard is `tools/operator_lean_oneshot.py`: it calls
`agent.shell_hooks.register_from_config(load_config())` then `hermes_cli.oneshot.run_oneshot(...)`
directly via the Python API (not the `hermes chat` CLI), inside the Hermes agent's own venv. But
that path is contractually bound to one specific profile ("operator-lean") and one specific,
already-hardcoded, exact 9-tool `EXPECTED_TOOLS` set (`mcp__operator__*`, `mcp__brain__*`) — a
persona and tool contract built for the operator-triage assistant, not for an isolated,
tool-free, context-free fidelity judge. Reusing it as-is would hand the detector business-facing
operator/brain tools and whatever context that profile's plugin assembles — inputs beyond
contract §6.1's "the candidate claim, and the source document it was derived from. Nothing else,"
which is its own fidelity risk, arguably worse than the plain call failure.

**No existing, clean, tool-free, context-minimal Hermes call path was found in this repo that
both satisfies the mandatory native context-assembly guard and stays within Validation A's
"nothing else" input contract.** Building one is a real, non-trivial infrastructure change (a new
plugin registration / profile, or a change to the guard's registration conditions) — squarely
outside this step's scope per CLAUDE.md rule 7 ("fix in-scope defects required to complete the
current step; record unrelated findings without expanding scope").

## What this does not block

Contract §6.4 itself: "Validation A may be deterministic or model-assisted; that is an
implementation choice." A deterministic detector (a rule-based, zero-model-call implementation of
the nine §5 categories in Python, scored against the same 12 frozen items, same thresholds, same
output vocabulary) remains fully within the contract and sidesteps this infrastructure gap
entirely — at the cost of needing careful, honest rule design instead of relying on model
judgment.

## Budget spent

1 of 20 calls (the failed shakedown). It failed inside the local Hermes process before reaching
any provider network call, so no provider/subscription usage was actually consumed — but it
still counts against the declared instrument budget, per this run's own counting rule (every
invocation attempt is counted, success or failure). 19 remain.

## What I need from Liam

A choice between:

1. Switch Validation A to a **deterministic** detector (zero model calls; implement the nine §5
   rules directly, no infra work needed, but the resulting PASS/FAIL says less about whether a
   *model* can apply the vocabulary — it says whether the vocabulary itself is mechanically
   sound).
2. Authorize the infrastructure work to give the model-assisted path a clean, isolated call
   route (a new minimal plugin registration/profile with zero tools and no business-context
   injection) — real scope growth beyond this step, likely a separate step.
3. Point me at an existing clean call path I haven't found.

No sealed path was touched. No candidate/source content was sent to any model. 19 of 20 calls
remain. `TTROS_VALIDATION_A_RUN` will be unset and the guard reconfirmed inert before I report.
