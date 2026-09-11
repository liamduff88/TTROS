# Phase 2B — declared change and rollback (written before editing, per CLAUDE.md rule 4)

## Exact change

Full rewrite of `scripts/validation_a_runs/blind_run/detector.py`: replace the model-assisted
(Hermes-subprocess) instrument — stopped per `phase2_instrument_defect_report.md`, per the
operator's 2026-09-09 ruling to use the deterministic option — with a deterministic, zero-model-
call, pure-Python implementation of the frozen §5/§6.1 contract vocabulary. Same output contract
(verdict, reason_tags, evidence), same `SOURCE_UNAVAILABLE` status convention, same
`ALLOWED_VERDICTS`/`ALLOWED_TAGS`/`FORBIDDEN_AS_VERDICT_OR_TAG` constants. No `subprocess`, no
`hermes`, no network, no call counter (§6.4's cap does not bind a zero-call instrument, per the
operator's ruling — the file drops `reserve_call`/`BudgetExceeded`/the Hermes CLI plumbing
entirely rather than keeping dead code armed at a ceiling of zero).

Authored with the 14 distinct source documents behind the 12 resolved candidates unreadable
(Phase 2A guard extension, rehearsed in both directions in
`phase2a_guard_extension_rehearsal.txt`). Rehearsed only against fixtures constructed for this
report — never against `blind_run_phase1_freeze.json`'s candidate claim text used as rule input,
and never against any of the 14 sealed sources, historical labels, adjudication, or prior reports.

## Rollback

Preimage saved before Phase 2A's first edit (covers this file too):

```
/home/liam/ttros_backups/validation_a_phase2_preimages_20260909T075922Z/detector.py.preimage
```

```
cp /home/liam/ttros_backups/validation_a_phase2_preimages_20260909T075922Z/detector.py.preimage scripts/validation_a_runs/blind_run/detector.py
```

`detector.py` is untracked in git (`git status --porcelain` confirms `??`), so no git rollback is
available — backup-only per CLAUDE.md rule 6.

## Scope

Local file rewrite only. No git add/commit/push. No network. No model call. No vault write.
