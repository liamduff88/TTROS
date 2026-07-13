# AOS-2026-0078 — Pass 2 visual checkpoint repair

> Revisit: after Liam completes the designated Pass 2 visual checkpoint, or when queue-shell data ownership changes. · Last touched: 2026-07-12.

## Outcome

PASS. The existing dashboard now renders the canonical live operator-action
set in Needs Me and keeps queue-card selection, Selected Item details, controls,
receipts, artifacts, and final-step context on one identity. AOS-2026-0078
remains unclaimed `human_review`; Pass 3 remains untouched.

## Root causes

### Needs Me zero / count mismatch

Work Queue reads the lightweight queue endpoints, but Needs Me depended only on
`GET /api/dashboard/cockpit`. That endpoint also aggregates unrelated token,
backup, output, Latitude, and workbench data. A backend outage or the shared
five-second Axios timeout caused App to replace Cockpit state with `{error:
true}`, and the rail converted missing data to an empty array even while Work
Queue retained or reloaded canonical queue data. Live reproduction showed the
frontend serving on `:3010` with `:8010` down, and a later saturated Cockpit
request exceeding 30 seconds while `/api/queue/summary` completed in about
0.026 seconds.

There was also an independent truncation bug: Cockpit returned
`needs_me[:8]` while reporting the full count (nine). The rail displayed
`items.length`, making payload, label, and canonical count disagree.

Repair: the rail now refreshes from the existing read-only
`/api/queue/summary`, retains the last good set on a transient failure, polls
that lightweight source, normalizes only `human_review`, `needs_input`, and
`blocked`, and renders the full derived set. Cockpit also returns the full set.
No queue mutation, new endpoint, or new state store was introduced.

### Selected card / Selected Item mismatch

The panel and card already rendered from one `selectedId`, but
`refreshQueue(preferredId = selectedId)` captured an earlier render's selected
ID. A late status/items/next response could reapply that stale preferred ID
after a newer route or card selection. Concurrent refreshes had no request
ordering guard. Status-colored borders also made hover/status emphasis easy to
confuse with selection without a machine-readable selected marker.

Repair: selection is committed immediately to a ref plus revision counter,
overlapping refreshes are request-sequenced, and response application resolves
against the latest selection before falling back. Cards expose `aria-pressed`
and `data-queue-card-id`; the detail exposes the same selected ID. Focus mode,
route/tab remount, refresh, and View Final Step use the same selection path.

## Files changed for this repair

- `dashboard/backend/main.py`
- `dashboard/backend/test_composio_hermes.py`
- `dashboard/frontend/src/App.jsx`
- `dashboard/frontend/src/components/DashboardKit.jsx`
- `dashboard/frontend/src/queueState.js`
- `dashboard/frontend/src/views/Queue.jsx`
- `dashboard/frontend/tests/queueState.test.js`
- `decisions/DECISIONS.md`
- `workflows/queue_artifacts/pass2-repair-proof/browser-proof.json`
- three screenshots under `workflows/queue_artifacts/pass2-repair-proof/`
- this artifact and `queue/receipts/AOS-2026-0078-pass-2-visual-checkpoint-repair.md`

## Automated validation

- Frontend Node tests: PASS, 10/10. Cases cover review/input/blocked inclusion,
  inbox/done/cancelled exclusion, real-shaped AOS-2026-0078 data, full count
  equality, queue-summary recovery, refresh preservation, late-response race
  rejection, safe selection fallback, existing shell tabs, and amber override.
- Relevant Python suite: PASS, 210/210 in 38.413s:
  `tests.test_aos_queue`, `tests.test_aos_paths`,
  `tests.test_aos_orchestration`, `tests.test_aos_search`,
  `tests.test_aos_workflow_shell`, `tests.test_workflow_prompt_templates`, and
  `dashboard.backend.test_composio_hermes`.
- Focused backend Needs Me cases: PASS, 3/3, including no nine-item truncation.
- Python compilation: PASS for `dashboard/backend`, `tools`, and `tests`.
- Frontend production build: PASS, 1,645 modules transformed.
- `git diff --check`: PASS.

The protected Telegram-bridge test module was not run because the bridge is
explicitly outside this task's inspect boundary.

## Live API and runtime proof

- Backend `GET http://127.0.0.1:8010/api/health`: HTTP 200, workspace
  `/home/liam/agentic-os-live`.
- Frontend `GET http://127.0.0.1:3010/`: HTTP 200; Vite process cwd
  `/home/liam/agentic-os-live/dashboard/frontend`.
- Backend process cwd: `/home/liam/agentic-os-live/dashboard`.
- `/api/queue/summary`: Needs Liam 9, nine rendered public items,
  AOS-2026-0078 `human_review` / codex.
- `/api/dashboard/cockpit`: `needs_me_count` 9 and payload length 9 after repair.
- Runner process search: zero; runner remains stopped.

## Real browser proof

Playwright Chromium drove the real `http://127.0.0.1:3010` dashboard at
1440×1000 and 1100×850. It proved:

- Work Queue `Active 32 / Needs Liam 9 / Total 85` beside `9 active` and nine
  rendered Needs Me cards.
- AOS-2026-0078 appears as `human_review` with computed border
  `rgb(255, 176, 32)` (`#FFB020`).
- Collapse/reopen, lightweight refresh, full reload, and narrow width retain
  all nine items.
- AOS-2026-0078's selected card and detail both expose AOS-2026-0078.
- A delayed older queue-items request cannot overwrite rapid selections ending
  on AOS-2026-0078.
- Tab switch/return and focus entry/exit preserve the identity.
- Preview reuse, pin, close, and active-tab visibility remain functional; the
  existing pure-state cap test remains green.
- View Final Step on AOS-2026-0071 selects AOS-2026-0074 and resets the detail
  panel to scroll top after render.
- Copy-prompt, Pass 2 artifact preview, finished-result preview, final-receipt
  preview, and local output-folder requests were exercised successfully; the
  worker control remained enabled but intentionally unclicked to preserve the
  stopped-runner/Pass 3 boundary. All controls remained tied to the displayed
  selected panel.
- Cockpit/sidebar access and utility-only top bar remain present.
- Console errors: 0; page errors: 0; HTTP error responses: 0.

Screenshots:

- `workflows/queue_artifacts/pass2-repair-proof/desktop-1440-needs-me-and-selection.png`
- `workflows/queue_artifacts/pass2-repair-proof/narrow-1100-needs-me-and-selection.png`
- `workflows/queue_artifacts/pass2-repair-proof/final-pass2-human-review.png`

Machine-readable evidence:
`workflows/queue_artifacts/pass2-repair-proof/browser-proof.json`.

## Token-display regression

The AOS-2026-0078 selected panel rendered the canonical exact values unchanged:
input 239411, output 27876, total 267287, cached input 4384768, reasoning output
5547, model unavailable. The sidecar matches. The token ledger contains one
exact `codex_process_exit` row for session
`019f5807-db02-7202-927e-ab90c361db20` plus the separate pre-existing
no-agent orchestration row; no exact row was duplicated.

## Queue, package, and protected-boundary proof

- Final chain: one workflow parent (AOS-2026-0076, inbox), nine normal children,
  zero correction children, and ten package-tagged items total.
- AOS-2026-0077 is done. AOS-2026-0078 is unclaimed `human_review`.
  AOS-2026-0079 through AOS-2026-0085 are inbox and unclaimed.
- No Pass 3 artifact or execution receipt exists. No queue POST request was made.
- Package loader was not run. No `_buildout_package` file was changed.
- Definition hash recomputed directly from the two canonical JSON definitions:
  `6fc38321d2c5c7f38a481b0bc1c3802b3833f0cd00773e35af3e57680ca3b320`,
  exactly matching `package_manifest.json` and the package identity tags.
- Immutable AOS-2026-0071/0073/0074/0075 queue-row hashes all match their
  locked known values; Git diff mentions for those IDs: zero.
- Protected paths were not opened internally or modified. No external action,
  send, publish, deploy, credential change, stage, commit, push, queue creation,
  approval, or runner start occurred.

## Review boundary

Pass 2 is ready for Liam's designated visual checkpoint. Leave
AOS-2026-0078 at `human_review`; do not mark it done and do not start Pass 3.

Token usage: unavailable from current CLI output.

## Final Pass 2 checkpoint repair and Liam-authorized additions

PASS. Item 1 was the remaining original Pass 2 defect repair. Items 2 and 3
were Liam-authorized checkpoint additions. No Pass 3–9 feature was
implemented; non-blocking future ideas remain post-Pass-9 backlog.

### Root cause and behavior changed

- Initial selection had two owners across component boundaries: Queue kept the
  selected ID only in component-local state while App retained the session
  tab's earlier route parameters. A tab unmount/return or full refresh could
  reconstruct from stale parameters, and parameter restoration and list
  resolution ran in separate effects. The selected ID now writes back into the
  existing session-tab parameters and a validated session snapshot. One
  resolver chooses routed/restored/current/next/fallback identity, while the
  prior request-sequence and selection-revision click-race guards remain.
- Token aggregation concatenated the queue and legacy ledgers, then returned
  the final 100 insertion rows without event-time sorting. Root-ledger append
  position, duplicate timestamps, and malformed timestamps could therefore
  masquerade as chronology. Rows now use the first valid authoritative field
  from `timestamp`, `ts`, `event_timestamp`, `completed_at`, `updated_at`, or
  `created_at`, normalize aware offsets to UTC, sort newest-first, use
  invocation/effect identity plus a canonical-content digest only as a stable
  non-chronological tie-breaker, and place invalid/missing times last.
- Invocation source uses only explicit `invocation_source`/`invocation_tool`, a
  `token_usage.workbenches[]` entry whose `source` is `reported`, or non-zero
  persisted `token_usage.orchestrator` usage. Owner, lane, profile, workbench
  classification, prompt, title, and model are never used as source evidence.
- Workflow names previously used `_markdown_title`, which returned the first
  non-empty line and therefore accepted `---`. One backend naming function now
  applies metadata title, metadata name, meaningful identifier, first Markdown
  heading, then cleaned filename. Duplicate names remain separate by ID/path.
- Workflow writes accept a workflow ID, not a path. The backend resolves it
  against exactly two approved roots: canonical `workflows/*/workflow.md` and
  `dashboard/test-fixtures/workflows/*/workflow.md`. It rejects invalid IDs,
  absolute/traversal input, outside-root resolution, symlinks, protected names,
  directories, unsupported shapes/extensions, oversized/NUL/blank content,
  and stale revisions. Existing same-directory fsync + atomic replace now
  preserves file mode before publication. Save verifies exact persisted text
  and returns `executed: false`; it has no runner or workflow-execution call.

### Token attribution report

Across 56 effective rows after exact-over-placeholder reconciliation:

- exact rows with explicit invocation source: 4 (Codex 2, Hermes 2);
- exact rows remaining honestly Unattributed: 1
  (`AOS-2026-PHASEA-EXACT`, 1,205 tokens);
- unavailable rows: 8, all Unattributed;
- genuine deterministic no-agent-invocation rows: 34;
- legacy estimate rows: 9, all Unattributed and excluded from exact totals.

AOS-2026-0077 and AOS-2026-0078 both have authoritative persisted Codex
identity through `workbenches[].tool=codex` with `source=reported`. Their exact
values remain respectively 407724/38245/445969 and
239411/27876/267287. AOS-2026-0078 retains session
`019f5807-db02-7202-927e-ab90c361db20`, cached input 4384768 separately,
reasoning output 5547 as a subset of output, and model unavailable.

### Validation and real proof

- Dashboard backend: 127/127 tests passed.
- Queue/path/orchestration/search/workflow regressions: 90/90 passed.
- Frontend shell/queue tests: 15/15 passed. Total: 232 tests.
- Python compilation passed for every touched Python file; frontend production
  build passed with 1,645 modules; `git diff --check` passed.
- Canonical backend/frontend health returned HTTP 200. Backend cwd is
  `/home/liam/agentic-os-live/dashboard`; frontend cwd is
  `/home/liam/agentic-os-live/dashboard/frontend`; runner process count is zero.
- Real Chromium proof passed at 1440×1000 and 1100×850 with zero console errors,
  page errors, failed requests, or page HTTP errors. Clean load and refresh
  coherently selected AOS-2026-0021; selecting AOS-2026-0078 remained coherent
  through rapid clicks, pinned-tab return, and focus entry/exit. View Final
  Step selected AOS-2026-0074 from AOS-2026-0071 with panel scrollTop 0.
- Workflow editor load/save/reload used only
  `dashboard/test-fixtures/workflows/pass2_editor_fixture/workflow.md` and
  persisted `proof_value: browser-save-2026-07-12`. The PDF-branding registry
  source remained visibly read-only with no edit action. Traversal and absolute
  workflow IDs returned HTTP 400.
- Machine proof and eight screenshots are under
  `workflows/queue_artifacts/pass2-final-proof/`.

### Preservation and final boundary

- Production workflow before/after manifest: identical, SHA-256
  `4f63796d8e0e213d61beafb979e795410bc475760ba5d97ba057b0c033ee5e0f`
  across 20 canonical workflow files.
- Queue, AOS-2026-0077/0078 sidecars, queue ledger, and root ledger manifest:
  identical, SHA-256
  `45aa23a2ed3df9d257dc613b78d83812638ae6d517b6d4ef720d3fd00491bad6`.
- `_buildout_package` plus immutable AOS-2026-0071/0073/0074/0075 records:
  identical, SHA-256
  `9be586fa785e63e643cf18f664dcbcd9cdbf78653aa6ca1729fa7438af5dabfa`.
- Final chain remains one parent, nine normal children, zero corrections:
  AOS-2026-0076 inbox; 0077 done; 0078 unclaimed human_review; 0079–0085
  unclaimed inbox. No Pass 3 artifact/receipt, loader rerun, queue mutation,
  runner start, external action, stage, commit, or push occurred.

Ready for Liam's final Pass 2 visual decision. Keep AOS-2026-0078 at
`human_review`; do not mark done and do not start Pass 3.
