# Operator blocked-work UX — results against predictions

Written 2026-10-06 after validation. Predictions are in 00_pre_edit_state_and_predictions.md.

| # | Prediction | Result |
|---|---|---|
| P1 | AOS-2026-0528 -> system_failure, no Retry, actions [dismiss] | Held (live API + live browser). |
| P2 | AOS-2026-0923 -> finished, demands_operator false, [close_finished, dismiss] | Held (live API + live browser). |
| P3 | Live needsLiam 2 -> 1 | Held: Needs Me 1, sidebar badge 1, top bar "1 blocked". |
| P4 | Dismiss: step + stranded parent cancelled, no row/ID change, replay closes nothing | Held on fixtures (pytest) and on a scratch copy of the live queue (34 rows before/after, same IDs). |
| P5 | Close-finished: done via existing PASS receipt, no re-run, 409 without PASS | Held on fixtures and on the scratch copy. |
| P6 | New tests fail pre-edit | 6 of 7 new pytest tests fail on pre-edit code. The 7th (CLI supersede leaves the parent alone) passes on both by design: it guards backward compatibility. |
| P7 | No new suite failures | Held: identical 40 failing/erroring node IDs pre/post in the same worktree population; live root 9 failed = the 9 known failures. |

## Browser

- browser_live_readonly.txt: real live Work Queue, every queue POST/DELETE blocked and counted: 0.
- browser_click_proof.txt: dashboard/frontend/tests/blockedWorkAttentionBrowserProof.mjs, queue API
  fulfilled in-browser. Exactly one call per action (dismiss, close-finished, run), 4 items before
  and after. Negative rehearsal: with the parent run-button guard disabled, the proof failed with
  "parent offers no misleading run button"; guard restored.

## What a PASS licenses

The projection, both endpoints and the UI behave as specified on fixtures, a scratch copy of the
live queue, and the live dashboard (read-only). It does not license the post-click objective
continuation for AOS-2026-0922: "Close as finished" on a David objective step runs the existing
continuation, which makes the objective's normal final-synthesis model call and its normal
Telegram outcome report. That path was stubbed in tests and was not executed live.

## Live queue left untouched

AOS-2026-0528 and AOS-2026-0923 are still blocked; both are left for Liam's click-verification.
