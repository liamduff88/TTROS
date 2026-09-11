# Validation A seal manifest -- category breakdown

Paths and seal reasons only. No content, no excerpts. Source:
`scripts/validation_a_runs/seal_manifest.json`.

**Reconciliation correction (this revision):** the previous version of this report stated
"46 + 1 = 47 sealed paths," double-counting the adjudication file. It is **one of the 46**
entries in `files[]` (`file_count: 46`, confirmed 46 unique paths) -- the manifest's
top-level `adjudication_file` block merely *also* surfaces its path/hash prominently for
convenience (per the step instruction: "so the blind session never needs to touch that file
before reveal"). It is not a distinct 47th path. **Reconciled total: 46 sealed paths.** No
other file is double-counted across categories; the one file that legitimately fits two
category descriptions (see the B6/"Validation A" note below) is counted once, in the group
that matches how it was actually sealed.

## Known-in-advance adjudication (1 of the 46)

- `/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Reviews/00_TTROS_CURRENT_STATE_v2026-09-01.md`
  -- the historical Validation A adjudication. Present in `files[]` like every other sealed
  path, and additionally mirrored in the manifest's top-level `adjudication_file` block.

## CATEGORY: 00_*CURRENT_STATE* -- all reachable revisions (5, beyond the adjudication above)

- `TTROS Reviews/00_TTROS_CURRENT_STATE.md`
- `TTROS Reviews/00_TTROS_CURRENT_STATE_v2026-09-02.md`
- `TTROS Reviews/00_TTROS_CURRENT_STATE_v2026-09-04_rev6.md`
- `TTROS Reviews/00_TTROS_CURRENT_STATE_v2026-09-08_rev7.md`
- `agentic-os-live/docs/ttros/00_TTROS_CURRENT_STATE_v2026-09-08_rev7.md` (mirror)

## CATEGORY: 02_*ACTIVE_TASK* -- all reachable revisions (4)

- `TTROS Reviews/02_TTROS_ACTIVE_TASK.md`
- `TTROS Reviews/02_TTROS_ACTIVE_TASK_2026-09-04_rev6.md`
- `TTROS Reviews/02_TTROS_ACTIVE_TASK_2026-09-08_rev7.md`
- `agentic-os-live/docs/ttros/02_TTROS_ACTIVE_TASK_2026-09-08_rev7.md` (mirror)

## CATEGORY: project review briefs (3)

- `TTROS Reviews/TTROS_ARCHITECTURE_REVIEW_BRIEF_2026-09-02.md`
- `TTROS Reviews/TTROS_EXTERNAL_REVIEW_RESPONSE_2026-09-02.md`
- `TTROS Reviews/TTROS_PLATFORM_DECISION_BRIEF_2026-09-02.md` (added on the confirmed
  Windows-side category re-run; not on the original content-pattern pass)

## CATEGORY: indexsplit provenance (9)

- `TTROS Reviews/ttros_indexsplit.sh`
- `TTROS Reviews/ttros_indexsplit.txt`
- `TTROS Reviews/ttros_indexsplit_applied.txt`
- `TTROS Reviews/ttros_indexsplit_confirm.sh`
- `TTROS Reviews/ttros_indexsplit_confirm.txt`
- `TTROS Reviews/ttros_indexsplit_diag.sh`
- `TTROS Reviews/ttros_indexsplit_diag.txt`
- `TTROS Reviews/ttros_indexsplit_diag2.sh`
- `TTROS Reviews/ttros_indexsplit_diag2.txt`

## CATEGORY: prior B6 / B6-B7 scorer reports (filename token `b6`) (12)

- `agentic-os-live/scripts/b6_leak_scorer_mechanical_repair_report.md`
- `agentic-os-live/scripts/step5_step6_post_repaired_b6_investigation_instrument.py`
- `agentic-os-live/scripts/step5_step6_post_repaired_b6_investigation_instrument.txt`
- `agentic-os-live/scripts/step5_step6_post_repaired_b6_reconciliation_instrument.py`
- `agentic-os-live/scripts/step5_step6_post_repaired_b6_reconciliation_instrument.txt`
- `agentic-os-live/scripts/step_b6b7_part3_scorer_verification.json`
- `agentic-os-live/scripts/step_b6b7_part3_scorer_verification.py`
- `agentic-os-live/tests/test_b6_source_disposition.py`
- `TTROS Reviews/ttros_step2_b6_change_record.txt`
- `TTROS Reviews/ttros_step2_b6_disposition.py`
- `TTROS Reviews/ttros_step2_b6_disposition.sh`
- `TTROS Reviews/ttros_step2_b6_disposition.txt`

## Content-pattern matched: "Validation A" phrase (3)

- `agentic-os-live/docs/ttros/TTROS_B7_SCORING_FIDELITY_CONTRACT_v2.1_2026-09-08.md`
- `TTROS Reviews/TTROS_B7_SCORING_FIDELITY_CONTRACT_v2.1_2026-09-08.md`
- `agentic-os-live/scripts/step5_step6_post_repaired_b6_investigation.md` (also B6-category)

## Content-pattern matched: "X of 12" count phrasing -- precautionary (5)

- `agentic-os-live/scripts/step3_b7_pass_A.raw.json`
- `agentic-os-live/scripts/step3_b7_pass_B.raw.json`
- `agentic-os-live/scripts/step5_b7_pass_k1.raw.json`
- `agentic-os-live/scripts/step6_b7_pass.raw.json`
- `agentic-os-live/scripts/step5_step6_b7_reconciliation_audit.md`

Note: these four `*.raw.json` files are raw B7 (25-question harness) pass output, a
different instrument from Validation A's 12-candidate population. The "X of 12" match
is most likely a coincidental subsection count, not confirmed independent of the
sealed adjudication -- sealed anyway per the completeness-over-precision instruction.

## Content-pattern matched: "12 candidates" (1, beyond the CURRENT_STATE family above)

- `TTROS Reviews/TTROS_CONTEXT_ARCHITECTURE_DESIGN_2026-09-02.md`

## Content-pattern matched: "candidate" (1)

- `TTROS Reviews/TTROS_BUILD_PLAN_BRIEF_2026-09-02.md`

## Content- and filename-pattern matched: "validation_a" + "12 candidates" (2)

- `agentic-os-live/scripts/validation_a_fidelity_detector_report.md`
- `agentic-os-live/scripts/validation_a_fidelity_detector_transcript.txt`

## Reconciliation arithmetic

1 (adjudication) + 5 (CURRENT_STATE family) + 4 (ACTIVE_TASK family) + 3 (review briefs)
+ 9 (indexsplit) + 12 (B6 reports) + 3 ("Validation A" phrase) + 5 ("X of 12" precautionary)
+ 1 ("12 candidates" other) + 1 ("candidate") + 2 ("validation_a" + "12 candidates")
= **46**, matching `file_count: 46` and 46 unique paths in `files[]`. No path appears in
more than one bucket above.

---

## Location-judgment flag (filename/location only -- no sealed file opened)

None of the 46 sealed paths sit under a Business Brain vault shape (`memory/*.md`,
`sources/historical_calls/*.md`, `sources/**`, `inbox/**`) or use a call-transcript
naming convention (person-name + date, e.g. `trent-july-9.md`). By filename and
location alone, none of the 46 plausibly *are* historical call material or Business
Brain source notes themselves -- they are review-cycle documents, state/task
snapshots, and B6/B7 scorer instruments and reports, all rooted in `TTROS Reviews/`,
`agentic-os-live/scripts/`, `agentic-os-live/tests/`, or `agentic-os-live/docs/ttros/`.

Six sealed paths are dated 2026-09-02 and are therefore the plausible *origin*
documents a 2026-09-02 index bullet could cite (review-cycle output on the
architecture/platform candidate decision, not source material about it):

- `TTROS Reviews/00_TTROS_CURRENT_STATE_v2026-09-02.md`
- `TTROS Reviews/TTROS_ARCHITECTURE_REVIEW_BRIEF_2026-09-02.md`
- `TTROS Reviews/TTROS_BUILD_PLAN_BRIEF_2026-09-02.md`
- `TTROS Reviews/TTROS_CONTEXT_ARCHITECTURE_DESIGN_2026-09-02.md`
- `TTROS Reviews/TTROS_EXTERNAL_REVIEW_RESPONSE_2026-09-02.md`
- `TTROS Reviews/TTROS_PLATFORM_DECISION_BRIEF_2026-09-02.md`

This is a location/date judgment only -- no sealed file was opened to reach it.
