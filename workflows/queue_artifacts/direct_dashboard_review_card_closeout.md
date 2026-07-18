# Direct dashboard review-card closeout
> Revisit: when the dashboard human-review card or review-close contract changes. · Last touched: 2026-07-18.

## Result

PASS

## Files touched

- `dashboard/backend/test_composio_hermes.py`
- `dashboard/frontend/src/App.jsx`
- `dashboard/frontend/src/components/DashboardKit.jsx`
- `dashboard/frontend/src/components/HumanReviewCard.jsx`
- `dashboard/frontend/src/reviewCardState.js`
- `dashboard/frontend/src/views/Queue.jsx`
- `dashboard/frontend/tests/reviewCard.test.js`
- `dashboard/frontend/tests/reviewCardBrowserProof.mjs`
- `workflows/queue_artifacts/direct-dashboard-review-card-proof/desktop-1440x1000.png`
- `workflows/queue_artifacts/direct-dashboard-review-card-proof/narrow-760x900.png`
- `workflows/queue_artifacts/direct_dashboard_review_card_closeout.md`

## Validation

- `node --test tests/reviewCard.test.js` — PASS, 5/5 focused frontend tests.
- Review-close, frontend-label, and completion-card backend selections — PASS, 8/8 affected tests.
- `cd dashboard/frontend && npm test` — PASS, 28/28.
- `python3 -m unittest -q tests.test_aos_queue tests.test_aos_paths dashboard.backend.test_composio_hermes` — PASS, 237/237.
- `cd dashboard/frontend && npm run build` — PASS, Vite production build.
- `git diff --check` — PASS.
- Backend `127.0.0.1:8010` and frontend `127.0.0.1:3010` listened after the required canonical runtime start.
- `/api/health` returned status `ok`; `/api/queue/items` returned successfully with 167 items.

## Conflict resolution

- Live `HEAD` exactly matched base `bcfcdd70b1cca4a11e436aabe2045e130cfb2d05`; the linked clean worktree exactly matched repair `b6e3067ba557bea5f345cc2d606ab0418ac3dba9`.
- `Queue.jsx` was merged semantically, not replaced. Existing live sorting, readable-title, detail-loading, needs-input answer, artifact expansion, handoff, and receipt-history changes remain.
- Only the legacy human-review state, handler, progress banner, and Approve / Needs changes / Reject panel were removed; the compact card now owns review close.
- Existing live changes in `App.jsx` and `test_composio_hermes.py` also remain outside the intended repair hunks.

## Live browser proof

- The browser loaded the canonical repository at `http://127.0.0.1:3010` against the canonical backend at `http://127.0.0.1:8010`.
- Independent compact cards were asserted for `AOS-2026-0135` and `AOS-2026-0155`, including their distinct real titles and default `done` selector state.
- Every asserted card had exactly one receipt textarea, one selector with `done`, `needs_input`, and `blocked`, and one Save/Attach button; excluded review clutter and legacy controls were absent.
- Pre-existing blocked item `AOS-2026-0020` rendered the existing detailed queue pane and no compact card.
- Saving `AOS-2026-0135` as `blocked` produced one HTTP 200 POST to the existing `/api/queue/items/{id}/review-close` endpoint. After a full reload its receipt and selector state persisted and the Save/Attach control remained disabled.
- Desktop and narrow screenshots were captured from the canonical dashboard and visually inspected.

## Behavior changed

- One human-review item renders as one compact card.
- The permanent body is receipt, valid review-close selector, and Save/Attach.
- Non-review items without a retained local review draft keep the detailed queue view.
- The shared save helper invokes the existing review-close client exactly once per save.

## Unrelated work preserved

- No wholesale file replacement was used.
- Unrelated staged state was empty before integration.
- Unrelated dirty and untracked files remain present and unstaged; overlapping live hunks remain in the working tree after intended-hunk staging.

## Protected areas

- No North Shore, Telegram bridge, route-contract JSON, `.env`, secret/token/credential/authentication, legacy runtime, or Hermes global/default-profile file was inspected internally or modified.
- Protected queue IDs `AOS-2026-0071`, `AOS-2026-0073`, `AOS-2026-0074`, `AOS-2026-0075`, `AOS-2026-0161`, `AOS-2026-0162`, `AOS-2026-0164`, `AOS-2026-0166`, and `AOS-2026-0167` were not mutated.
- Browser persistence used non-protected harmless self-test item `AOS-2026-0135`.
- No GitHub push or third-party external action occurred.

## Blockers

None.

## Next action

No action required. Keep the canonical dashboard running; do not push.

## Token usage

Token usage: unavailable from current CLI output.
