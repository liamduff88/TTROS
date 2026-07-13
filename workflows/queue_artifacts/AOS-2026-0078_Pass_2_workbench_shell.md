# AOS-2026-0078 — Pass 2 workbench shell

> Revisit: after Liam completes designated visual checkpoint 1, or when the dashboard shell contract changes. · Last touched: 2026-07-12.

## Outcome

Pass 2 reshapes the existing dashboard only. It adds the approximately 180px grouped/collapsible sidebar, utility-only top bar, frontend-only IDE session tabs, queue focus mode, a collapsible one-click Needs Me strip, the locked two-axis workbench/lane colors, and the View Final Step selection/scroll repair. The Antigravity workbench remains reserved and unused.

The post-checkpoint live-data repair and replacement browser proof are recorded
in `workflows/queue_artifacts/AOS-2026-0078_Pass_2_visual_checkpoint_repair.md`.

The session ends at `human_review`. Liam's approval through the existing dashboard review path is the only authorized next transition. Pass 3 was not claimed, generated, executed, or implemented.

## Files changed for Pass 2

- `dashboard/frontend/package.json`
- `dashboard/frontend/src/App.jsx`
- `dashboard/frontend/src/components/DashboardKit.jsx`
- `dashboard/frontend/src/components/Sidebar.jsx`
- `dashboard/frontend/src/components/TopBar.jsx`
- `dashboard/frontend/src/shellState.js`
- `dashboard/frontend/src/views/Queue.jsx`
- `dashboard/frontend/tests/shellState.test.js`
- `decisions/DECISIONS.md`

## Shell behavior

- Sidebar groups preserve all 15 required destinations across Work, Knowledge, Evidence, and System.
- Expanded width is 180px; the icon rail is 56px and reopens with one click.
- The top bar contains status and genuine utilities only: launchers, copy prompts, search, tokens, date/time, and refresh. Primary navigation chips were removed.
- The practical narrow-width utility bar stays one row and scrolls horizontally rather than consuming the work area vertically.

## Session tabs

- Cockpit is immutable, pinned, and first.
- One unpinned preview tab is reused on navigation.
- Double-click pins a preview; non-Cockpit tabs close independently.
- Active state is exposed through `aria-selected` and a filled surface.
- Eight tabs is the enforced cap.
- State exists only in React memory; no API, queue, file, database, localStorage, or other durable store was added.

## Focus mode and Needs Me

- Focus mode expands the selected queue detail and collapses every other visible task into a recoverable mini rail.
- Each rail item carries task ID, a workbench/state color bar, and a state dot; clicking switches focus.
- Needs Me uses the existing live `cockpit.needs_me` state. It collapses to an always-visible amber count strip and reopens with one click, including at 1100px.

## Two-axis colors

- Card borders, selected-detail borders, Needs Me edges, mini-rail bars/dots, and session-tab edges use the exact locked workbench ramps at the correct state shade.
- Lane appears only as a small solid chip using the locked marketing/revenue/delivery/operations token.
- `human_review` and `needs_input` override the workbench shade with exact `--needs-review: #FFB020`.
- Text remains on neutral text tokens. The reserved Antigravity ramp is not activated.

## View Final Step repair

The action clears filtering, selects the real `final_item_id`, waits for the React selection to commit, resets the selected detail panel's internal scroll position, and scrolls that panel to the top of the work area. Finished-result, receipt, output-folder, and final-step controls remain enabled and functional.

## Validation

- Frontend unit tests: PASS, 4/4.
- Frontend production build: PASS, 1,644 modules transformed.
- Queue/orchestration/path/backend/prompt-template regressions: PASS, 189/189 in 36.400s.
- Python compilation: PASS for `dashboard/backend`, `tools`, and `tests`.
- `git diff --check`: PASS.
- Linux backend: PASS, `http://127.0.0.1:8010/api/health`, authoritative workspace `/home/liam/agentic-os-live`.
- Linux frontend: PASS, `http://127.0.0.1:3010`.
- Browser proof: PASS at 1440×1000 and 1100×850.
- Browser console errors: 0. Uncaught page errors: 0. HTTP error responses: 0. Required request failures: 0. Two result reads were benignly aborted because navigation replaced their view.
- `_buildout_package`: before/after SHA-256 and byte listings identical.
- Immutable fixture diff: no Git diff mentions for AOS-2026-0071/0073/0074/0075.
- Runner: stopped. Nothing staged, committed, or pushed.

## Automated browser proof

The Playwright proof covers all 15 sidebar destinations; expanded/collapsed sidebar; utility-only top bar; no duplicate primary navigation; preview reuse; pinning; closing; active tab; eight-tab cap; focus rail and switching; Needs Me collapse/reopen; workbench borders; lane chips; amber review override; final-result, receipt, output-folder, and final-step controls; correct final item selection; and selected-detail top scrolling.

Screenshots:

- `/tmp/aos-pass2-proof/desktop-1440.png`
- `/tmp/aos-pass2-proof/narrow-1100.png`
- `/tmp/aos-pass2-proof/final-human-review.png` (live amber checkpoint state)

## Protected boundaries

No protected path was read internally or modified. Path-level Git checks only were used for protected boundaries. No protected record was mutated. No external send, publish, deploy, credential change, stage, commit, push, or third-party service mutation occurred.

## Liam visual review

Open the real Linux dashboard at `http://127.0.0.1:3010`. Inspect the shell at an ordinary desktop width and a practical narrower width, then review AOS-2026-0078 through the existing dashboard Needs Me / Work Queue review path. Approve only if the grouped navigation, utility bar, tabs, focus rail, Needs Me strip, colors, and final-step behavior are visually acceptable. Do not manually unlock or execute Pass 3; the existing dependency logic may do that only after Liam approves this checkpoint.

Token usage: unavailable from current CLI output.
