# TTROS Dashboard BUILD Specification
> Revisit: when this overhaul is implemented or the dashboard's operator jobs materially change. · Last touched: 2026-09-13.

Status: definitive implementation specification for the current dashboard. `TTROS_DASHBOARD_OVERHAUL_CONTEXT_2026-09-13.md` was not present; this specification uses the current working tree as authority.

## Fixed boundary

Reshape the existing React/Vite dashboard and FastAPI backend only. David stays the executive/advisory interface; genuine execution is handed to Operating Hermes through the existing queue/orchestrator. Reuse the current queue, runner, receipts, Business Brain index/search, Graphify, review actions, and artifact paths. Do not create another dashboard, backend, datastore, queue, orchestrator, Telegram bridge, or North Shore change.

## B — Business purpose

The dashboard is Liam's operating cockpit. Within seconds it must answer:

1. **What needs me?** Show review, input, and genuinely operator-owned blockers with the exact decision/action.
2. **What is working?** Show live queued/running work, honest status, and visible progress or stalling.
3. **What finished?** Show recently completed work as business outcomes, not receipt rows.
4. **What did it produce?** Put the primary readable result and deliverables one click away.
5. **What should I do next?** State the next operator action or the next system-owned step; never imply Liam must act on a system-owned failure.

Surface decisions:

| Surface | Decision supported |
|---|---|
| David | Ask, understand, decide, or hand a genuine execution objective to Operating Hermes. |
| Needs Me | Approve, request changes, answer, reject/block, or open the result needed to decide. |
| Active Work | Verify work is progressing; inspect only when status or age suggests attention. |
| Recent Results | Read the outcome, open the primary result, and decide the next business action. |
| Work Queue | Triage, filter, select, review, run/resume, and inspect one logical piece of work. |
| Search | Find Business Brain knowledge, queue work, receipts, workflows, and artifacts without model spend. |
| System | Diagnose dashboard/runner/index/connector health and inspect technical evidence on demand. |

## U — Underlying data

No new datastore. UI state may use the existing session/local storage patterns; durable truth stays in current files exposed by current APIs.

| Visible component | Existing authority and API/state |
|---|---|
| David conversation | `POST /api/dashboard/ask-david`; attachments through `POST /api/uploads`; visible thread and unsent draft through `aos.dashboard.david.thread.v1` and `aos.dashboard.david.draft.v1` in `sessionStorage`. Preserve deterministic-read, David-reply, ingestion, failure, and `queue_created` response kinds. |
| Hermes handoff | Existing David backend routing and queue creation only. The UI must say that David handed work to Operating Hermes; David is not displayed as the executor. |
| Needs Me count/list | `GET /api/queue/summary` (`needsMeItems`, counts) with the existing 15-second shell poll; detailed review data from `GET /api/queue/items/{id}`. Statuses are `human_review`, `needs_input`, and only blockers/reasons the backend already classifies as needing Liam. |
| Review/input actions | Existing `/api/queue/items/{id}/review-note`, `/review-close`, `/receipt`, `/status`, and outreach-event routes. Preserve `HumanReviewCard` draft persistence in `localStorage`. |
| Active Work | `GET /api/queue/summary` (`activeItems`, `nextItem`) or the already-loaded `/api/dashboard/cockpit.queue_items`; authoritative records remain `queue/work_items.jsonl`. Running/stalled meaning comes from existing status, claim/heartbeat, attribution, and System Watch projection. |
| Queue list/counts/detail | `GET /api/queue/status`, `/api/queue/items?scope=all`, and `/api/queue/items/{id}`. Keep compact list rows plus on-demand rich detail and current record-hash merge behavior. |
| Parent/child workflow | Existing `parent_id`, `step_index`, `depends_on`, objective plan, orchestration events, and backend `pipeline`/`final_result`; never infer a second run from similar titles. |
| Recent Results | `GET /api/dashboard/results` and Cockpit `recent_output`, linked back to queue detail where an item ID exists. Outcome copy comes from `summary_for_operator`; files come from `primary_artifact`, `run_artifacts`, and `final_result`. |
| Artifact/report reader | Existing `GET /api/queue/artifact` and `/api/queue/receipt`; keep Markdown/text/code/JSON/image/PDF support. Open-folder remains optional desktop utility through the existing endpoint, never the primary reading action. |
| Search | `GET /api/search`, `/api/search/status`, `/api/artifacts`; existing reindex and ingest-tick actions. Business Brain remains part of the current index and scope contract. |
| Graphify | Existing `/api/dashboard/graphify` and `/api/graphify/*` routes, reached as a local Search workspace tab, not as a new global product. |
| System Watch | `GET /api/dashboard/system-watch`, `/api/health`, existing backup, Latitude, connection, queue tooling, schedule, and log-tail projections. |
| Shell/tab state | Extend the existing `aos.dashboard.shell.v1`; keep queue artifact-tab and accordion keys from `queueState.js`. Add only session-scoped view/item/tab scroll positions, keyed by stable IDs/paths. |

Backend responses may receive additive presentation fields only when the current projection cannot supply a title, outcome, or linked item ID cheaply. Do not change queue records or schemas for presentation.

### Internal Outreach Daily classification

`AOS-2026-0497` and `AOS-2026-0498` are one logical workflow, not duplicate execution:

- `0497` is the `owner_type: workflow` Hermes parent, created `2026-09-12T01:53:48Z`, source `dashboard/hermes_message`.
- `0498` is its only planned/executed Revenue child, created one second later, with `parent_id: AOS-2026-0497`, `step_index: 1`, and workflow tag `workflow:internal_outreach_daily`.
- Their dispatch keys share one executive-objective lineage; `0498` appends `:stage:1`.
- The child receipt/artifact completed at `01:57:24Z`; the parent synthesis receipt followed at `01:57:59Z`, and the orchestration completion event names `0498` as the sole child.

Required treatment: render one top-level **Internal Outreach Daily** work card, show overall outcome/status from the parent plus the child's primary review package, and expose parent/child IDs only in Steps/Technical Details. No queue or runner change is justified.

## I — Information hierarchy

### Desktop

1. Global shell: **David | Work Queue | Results | Search | System**.
2. David/Cockpit first viewport: dominant David surface plus Needs Me.
3. Immediately below: Active Work and Recent Results.
4. System health, specialist consultation, tokens, receipts, provenance, and raw metadata are secondary and reached by disclosure or the System surface.

### Mobile

Order is **David, Needs Me, Active Work, Results, Search**. Use a fixed, safe-area-aware five-item bottom navigation. Never render the desktop sidebar, global right rail, wide top utility row, kanban, or horizontally scrolling control strip on mobile. Technical/System access remains the fifth nav item; Search stays the fourth.

### Primary versus secondary

- Primary: human title, operator status, outcome, primary result, requested decision, next action.
- Secondary: lane, owner, relative age, step progress, other deliverables.
- Technical disclosure: AOS IDs, source, workbench, timestamps, receipts, token usage, logs, hashes, safety/execution evidence, workflow definition, raw artifacts.
- Safety evidence must remain available and exact, but never precede or visually outweigh the useful business result.

### Work Queue and result hierarchy

Queue card: human title → operator status/age → one outcome or next-action line → step count. No visible AOS ID in the normal card.

Selected work: human title/status → **What happened** → **Primary Result** with a strong Open action → **Deliverables** → **What you need to do now** → Steps → Technical Details → Receipts & Execution Evidence.

Result card: human title → outcome sentence → completion time/status → **Open result**. Receipt path and token line belong in Technical Details, not the feed row.

### Parent/child presentation

- Group only by an authoritative resolvable `parent_id`; retain the current display-only grouping approach.
- A parent is one top-level work card. Children appear as ordered steps with their own honest status and selectable detail.
- Filters match the parent or any folded child, but results remain one grouped card.
- Overall status uses the active decision point: Needs Me if a child needs Liam, Running if any child runs, Blocked if the chain is blocked, Done only when the recorded chain is complete.
- The primary business artifact may come from the producing child while the selected logical work remains the parent.

### Title rules

Use the backend's current `operator_task_title` normalization, then apply display rules consistently:

1. Prefer the parent objective's concise operator title for a grouped workflow.
2. Remove command wrappers and redundant verbs such as `Run` only when meaning is unchanged; never invent a business claim.
3. Never prefix a normal surface with an AOS ID. Put IDs in Technical Details and copy/deep-link affordances.
4. Artifact tabs use semantic role + human work title/document heading + `Report`, `Result`, or `Evidence`; raw filenames are fallback only.
5. If no trustworthy human title exists, show `Untitled work item`, not an ID masquerading as a title.

## L — Layout/design

### Global navigation and shell

- Desktop: a compact persistent left navigation with exactly five destinations. Active state must be unmistakable. Move launchers, connections, tokens, workflows, skills, memory intake, and specialist/system tools into local workspace tabs or disclosures under the nearest destination.
- Mobile: bottom navigation with icon + label, 44px minimum targets, `env(safe-area-inset-bottom)`, and no sideways scroll. Keep content clear of the bar.
- Replace the current always-wide utility bar with a compact header: current surface, backend/Needs Me indicator, and overflow menu for launchers/status utilities. Search lives in Search, not as a squeezed global input on narrow screens.
- Session tabs are not global navigation. On desktop they may remain a secondary workspace history. On mobile replace them with the current surface title plus a compact report/tab switcher when needed.
- Preserve browser back/forward. Extend the existing history/state router with stable routes for the five destinations and selected work; do not add a routing dependency.

### Local report/workspace tabs

- Work Queue owns `Work Queue` plus dynamically opened artifact/receipt tabs.
- Results owns `Recent Results | Artifacts | Receipts`.
- Search owns `Search | Memory | Graphify | Add to Memory` using existing views/APIs.
- System owns `System Watch | Connections | Workflows/Skills | Tokens | Settings` using existing views.
- Desktop tabs may scroll only as a tab rail when genuinely necessary; mobile uses a select/menu or wrapped two-row control. Document content and page controls must never require horizontal scrolling.

### Cockpit

- Desktop first row: David at roughly two-thirds width; Needs Me at one-third and sticky only within the viewport when useful.
- Second row: Active Work and Recent Results as equal outcome-oriented panels. Each shows 3–5 items and a clear `View all` action.
- Remove Queue Snapshot, backup, lane, and workbench tiles from the primary reading path. Keep concise health exceptions in System Watch; keep specialist consultations collapsed beneath core cockpit content.

### David

- Make the conversation/composer the strongest visual surface, with a readable line length and at least 40–50vh useful space on desktop when history exists.
- Keep thread visible above the composer, draft/attachment states explicit, and the composer reachable without losing context.
- Distinguish `David answered`, `local lookup`, `sent to Operating Hermes`, and `failed` in plain language. A queued handoff links directly to the visible selected work.
- Preserve visible-chat and draft persistence exactly; never clear a failed submission or imply it was sent.

### Work Queue and Results

- Desktop Queue is a master/detail workspace; collapsed list uses human titles, not IDs. Mobile is list → full-width detail with a clear Back to Work Queue action; never two squeezed columns.
- Keep status-tile filtering and show every active filter/sort as a removable chip plus result count.
- Results is an outcome feed, not the existing seven-column receipt table. Selecting a result opens the readable result in the same persistent report workspace.
- Reuse the current ArtifactViewer for Markdown/text/image/PDF. Markdown outline becomes a compact disclosure on mobile; tables wrap into stacked rows or contained content scrolling, never page-level overflow.

### Sticky geometry and responsive behavior

- Make the main scroll root edge-to-edge; put page padding in an inner wrapper. The Queue/report tab bar is `sticky; top: 0` in that scroll root, with no negative-offset hack.
- The sticky tab bar and content panel share one border seam: tab bar bottom border removed, content top border removed, zero margin/gap between them.
- Selected content has `scroll-margin-top` equal to the sticky bar height. After selection/detail hydration/final-step navigation, scroll the main scroll root to the selected heading, not an inert child panel.
- Breakpoints: `<768px` mobile single-column/bottom nav; `768–1199px` compact single-column or deliberate master/detail; `≥1200px` full desktop cockpit/master-detail. At 320px CSS width, no page-level horizontal overflow is allowed.

## D — Dynamics/trust

### State feedback

- Initial loading uses stable skeleton/placeholder geometry; do not blank previously loaded data during polling.
- Running shows the actual work title, owner, honest status, elapsed/last-updated time, and a visible refresh state. Disable duplicate run submission.
- Success is attached to the action and says what changed, where the result is, and the resulting status. It persists until the user dismisses it or navigates meaningfully.
- Error is attached to the failed action, preserves user input/selection, shows a useful reason, and offers Retry where safe. Background refresh failure keeps stale data visible with `Last updated` and `Refresh failed`.
- Every clickable action must immediately show pressed/busy state and conclude with success/error. Folder-open must report refusal/failure rather than appearing inert.

### Filters, review, persistence, and navigation

- Status tiles toggle filters as today. Persist filter/sort/selected item in shell session and URL/history state; show active state on the tile and chip.
- Needs Me cards state the exact question/decision first, then outcome/result, then Approve / Needs changes / Block or Answer & resume. Notes remain optional for approve and required where current mechanics require them.
- After a review action, update the card and counts immediately, announce the new status, keep the result open, and move focus to the confirmation/next item only when the operator chooses.
- Preserve David thread/draft, internal result/report tabs, active report tab, per-item accordions, and per-view/item/tab scroll. Never persist raw artifact contents.
- Any link from David, Needs Me, Active Work, Recent Results, a parent step, or `View Final Step` must: activate Work Queue, clear only conflicting filters, select the exact item, open Overview, wait for rich detail, scroll it below the sticky bar, and visibly highlight/announce the selection.

### Browser/click acceptance criteria

- One click from any Cockpit item lands on visibly selected content; no hidden selection below the fold.
- One click on Primary Result opens a persistent internal tab and readable content; returning restores overview scroll, reopening restores report scroll.
- Browser Back/Forward restores global surface, local tab, selected item, and filters without a blank state.
- Refresh/polling never collapses rich detail, resets filters, closes tabs/accordions, or jumps scroll.
- All interactive controls are keyboard reachable with visible focus; async messages use `role=status`/`role=alert`; focus moves into opened mobile detail and returns to its originating card on Back.
- No control that is enabled can complete with no visible feedback.

## Components/files

### Change

- `dashboard/frontend/src/App.jsx` — five-destination shell, responsive navigation placement, view composition, route/selection landing, remove global squeeze from right rail.
- `dashboard/frontend/src/components/Sidebar.jsx` — refactor to the five desktop destinations; share nav metadata with mobile navigation.
- `dashboard/frontend/src/components/TopBar.jsx` — replace the horizontally scrolling utility row with compact header + overflow utilities.
- `dashboard/frontend/src/views/DashboardV1.jsx` — refactor Cockpit and `ResultsReceipts` to the required outcome hierarchy and local Result tabs.
- `dashboard/frontend/src/components/AskDavid.jsx` — dominant responsive conversation layout and handoff/status language; preserve behavior.
- `dashboard/frontend/src/components/DashboardKit.jsx` — refactor `NeedsMeRail` into reusable Cockpit/panel/drawer presentation; improve result/work cards and feedback primitives.
- `dashboard/frontend/src/views/Queue.jsx` — mobile list/detail, title/ID hierarchy, logical workflow selection, sticky geometry, scroll landing, and feedback.
- `dashboard/frontend/src/queueState.js` — retain grouping/deliverable logic; add logical-work status/title selection and persisted scroll helpers with focused tests.
- `dashboard/frontend/src/shellState.js` — five-route mapping, backward-compatible lane route handling, local tab/selection/filter state.
- `dashboard/frontend/src/components/ArtifactViewer.jsx` and `dashboard/frontend/src/artifactPreview.js` — reuse and refine reader hierarchy/mobile overflow only.
- `dashboard/frontend/src/views/WorkbenchV3.jsx` — Search/System responsive states and reuse Artifacts/Graphify/System Watch under local tabs.
- `dashboard/frontend/src/index.css` — shell sizing, safe areas, focus treatment, sticky-height token, and overflow guards.
- `dashboard/frontend/src/api.js` — change only if an existing endpoint wrapper or timeout is missing; no parallel API client.
- `dashboard/backend/main.py` — preferably unchanged; permit only additive, deterministic presentation projections proven necessary by frontend acceptance.

Update/add focused tests in the existing frontend test directory for shell routes, mobile navigation, grouping, title hierarchy, persistent tabs/scroll/accordions, action feedback, and selection landing. Extend `dashboard/backend/test_composio_hermes.py` only if an additive response contract changes.

### Reuse

Reuse `AskDavid`, `HumanReviewCard`, `ArtifactViewer`, `StatusChip`, `ActionButton`, queue compact/rich-detail merge, `groupWorkflowChildren`, `resolvePrimaryDeliverable`, artifact title/parsing helpers, `askDavidState`, review-card state, shell history/session state, and every existing backend route listed above.

### Refactor/replace

- Replace the current many-group global navigation model and horizontally scrolling mobile shell.
- Refactor, do not duplicate, Needs Me card rendering shared by Cockpit and Work Queue.
- Replace the receipt-led `ResultsReceipts` row layout with outcome-led result cards while keeping receipts as a local technical tab.
- Replace the brittle Queue `-top-6` sticky correction with correct scroll-root geometry.
- Do not replace queue mechanics, review mechanics, David routing, ArtifactViewer parsing, search/indexing, or System Watch.

### Dependencies

Add none. React, Tailwind, Lucide, Axios, native History API, CSS sticky/grid, `sessionStorage`, and `localStorage` cover the build. Consider a router or Markdown package only after an acceptance failure demonstrates the current stack cannot meet a specific requirement; document that failure before adding it.

## Implementation order

1. Lock focused state tests for current persistence, grouping, deliverable resolution, review mechanics, and duplicate-looking outreach classification.
2. Build the five-destination shell, stable routes, desktop/sidebar and mobile/bottom navigation; eliminate global horizontal overflow.
3. Recompose Cockpit around David, Needs Me, Active Work, and Recent Results using existing data.
4. Refactor Work Queue logical-work cards, mobile list/detail, title hierarchy, exact selection landing, and flush sticky report tabs.
5. Rebuild Results as outcome-led cards and connect all result/artifact opens to the shared persistent reader.
6. Fit Search/Memory/Graphify and System tools into local tabs; add complete loading/error/retry states.
7. Add persisted scroll/focus restoration and finish async action feedback/accessibility.
8. Run focused unit tests, production build, existing backend tests, then browser/click proofs at desktop and mobile widths. Codex performs the adversarial verification after the implementation workbench finishes.

## Desktop acceptance checklist

- [ ] Exactly five global destinations: David, Work Queue, Results, Search, System.
- [ ] David dominates the first viewport; Needs Me, Active Work, and Recent Results answer the five operator questions without opening System.
- [ ] Queue status tiles filter correctly and active filter/sort state is visible.
- [ ] `AOS-2026-0497/0498` displays as one Internal Outreach Daily workflow with ordered steps and one primary result.
- [ ] Normal queue/result cards use human titles; AOS IDs appear only in Technical Details/deep-link utilities.
- [ ] Selected work leads with outcome, Primary Result, Deliverables, and Next Action; receipts/safety/token evidence is secondary.
- [ ] Markdown, text, image, and PDF artifacts open internally and are readable.
- [ ] Queue/report sticky bar pins flush to its content with no top gap or seam.
- [ ] Tabs, active report, accordions, filters, selection, and scroll restore after navigation and polling.
- [ ] David queue handoff and every final-step/result link visibly lands on the selected detail.
- [ ] Loading, running, success, refresh failure, action failure, and folder-open failure are unmistakable.
- [ ] Search and System Watch retain current capability; no existing review/queue action is lost.

## Mobile acceptance checklist

- [ ] At 320, 375, and 430px widths there is no page-level horizontal scrolling.
- [ ] Bottom navigation exposes all five destinations, honors safe area, and has at least 44px targets.
- [ ] David, Needs Me/actions, Active Work, Results, and Search are comfortable single-column surfaces in that order.
- [ ] Desktop sidebar, utility strip, session-tab rail, right Needs Me rail, tables, and master/detail columns do not squeeze into mobile.
- [ ] Queue uses list → full-width detail; Back restores the exact list position and focus.
- [ ] Approve, Needs changes, Block, and Answer & resume remain fully usable with visible busy/success/error feedback.
- [ ] Result/report tabs use a compact switcher; opened artifacts remain persistent and readable.
- [ ] Markdown tables/content cannot overflow the page; image/PDF previews fit the viewport.
- [ ] Selecting from David/Needs Me/Results or a final step scrolls to and announces the selected content.
- [ ] Browser Back/Forward, reload, soft navigation, and background refresh preserve the documented state.

## Definition of done

The overhaul is done only when the existing dashboard passes both checklists with focused automated tests plus representative real browser clicks, while the existing queue/runner/receipts, David→Operating Hermes boundary, Business Brain/search/Graphify, review mechanics, and System Watch remain intact. Technical elegance without fast answers to the five operator questions is not acceptance.
