# Direct dashboard queue lifecycle closeout
> Revisit: when Work Queue scope, queue-read recovery, or review-close behavior changes. · Last touched: 2026-07-18.

## PASS / NEEDS ATTENTION

PASS

## Files touched

- `dashboard/backend/main.py`
- `dashboard/backend/test_composio_hermes.py`
- `dashboard/frontend/src/api.js`
- `dashboard/frontend/src/queueState.js`
- `dashboard/frontend/src/views/Queue.jsx`
- `dashboard/frontend/tests/queueScope.test.js`
- `dashboard/frontend/tests/queueLifecycleBrowserProof.mjs`
- `workflows/queue_artifacts/direct-dashboard-queue-lifecycle-proof/desktop-1440x1000.png`
- `workflows/queue_artifacts/direct-dashboard-queue-lifecycle-proof/narrow-760x900.png`
- `workflows/queue_artifacts/direct_dashboard_queue_lifecycle_closeout.md`

## Validation

- Focused backend queue tests: 3 passed.
- Focused frontend queue/review-card tests: 17 passed.
- Related frontend status/shell tests: 8 passed.
- Affected backend queue/path/dashboard suite: 238 passed.
- Frontend production build: passed (`vite build`, 1,649 modules).
- Browser lifecycle proof: passed with one review-close request, session-scope restoration, non-review detail, and both screenshots.
- `git diff --check`: passed for intended changes; final repository check completed before commit.

## Measured API behavior

Pre-change unfiltered baseline: HTTP 200, 0.045236 seconds, 167 items, 114,746 bytes. The live queue contained 76 terminal records.

Post-change canonical runtime, five requests per scope:

| Scope | HTTP | Items | Bytes | Min seconds | Average seconds | Max seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Active | 200 | 91 | 79,747 | 0.862015 | 1.022943 | 1.159409 |
| History | 200 | 76 | 35,202 | 0.019899 | 0.031660 | 0.061412 |
| All | 200 | 167 | 114,832 | 0.612468 | 0.839378 | 1.038536 |

Active was 35,085 bytes smaller than All while terminal records existed. The legacy no-query request remained HTTP 200 and returned all 167 valid items.

## Queue lifecycle behavior

- Active is the default and contains only inbox, agent_todo, agent_working, needs_input, human_review, and blocked.
- History contains only done and cancelled; All contains every valid record.
- The Active / History / All control is visible and the chosen scope persists in session storage across reloads.
- Global status counts, total count, and Needs Me count come from the all-record summary rather than the scoped list.
- Scope reads are deterministic, read-only, and leave `queue/work_items.jsonl` byte-for-byte unchanged.
- Browser fixture proof showed a done review item leaving Active and appearing in History and All; another active item remained present.
- The compact human-review card retained the AOS ID/title, one receipt textarea, valid close selector, and Save/Attach. Save issued exactly one review-close request.
- A non-human-review item retained the detailed metadata view.

## Reliability/root cause

The reproduced defect was malformed JSONL handling: one incomplete line caused the dashboard read to discard all valid records. Dashboard reads now stream the existing authoritative file, skip malformed/non-object lines, keep valid records usable, and return only a bounded `invalidRecordCount` diagnostic without line contents.

The current canonical logs showed repeated HTTP 200 queue reads and no relevant exception. HTTP 500 was not treated as a 500-millisecond timeout. The measured response times stayed within the existing operation-specific 5-second frontend timeout, so no timeout was changed. Authoritative mutations retain the existing queue-tool lock and durable replacement contract; the read path does not create, rewrite, archive, or compact records.

## Live browser proof

- Canonical dashboard origin: `http://127.0.0.1:3010`.
- Desktop screenshot: `workflows/queue_artifacts/direct-dashboard-queue-lifecycle-proof/desktop-1440x1000.png`.
- Narrow screenshot: `workflows/queue_artifacts/direct-dashboard-queue-lifecycle-proof/narrow-760x900.png`.
- Browser mutation was fixture-routed in memory; no authoritative queue item or protected ID was changed.

## Commit

- Message: `Add active and history queue views`
- Local only; no GitHub push.

## Unrelated work preserved

The expected dirty/untracked worktree remains. Only intended queue lifecycle, focused-test, screenshot, and closeout hunks are staged for this commit; unrelated edits and artifacts remain unstaged.

## Protected areas

No protected path was inspected internally or modified. None of the protected queue IDs was mutated.

## Blockers

None.

## Next action

None required.

## Token usage

Token usage: unavailable from current CLI output.
