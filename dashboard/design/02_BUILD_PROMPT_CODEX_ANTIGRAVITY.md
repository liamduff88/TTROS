# Build Prompt — Dashboard v1 (Codex primary · Antigravity for visual polish)

> **Owner:** Liam Duff / Time to Revenue
> **Use:** paste into Codex (implementation) or Antigravity (UI/app build). One bounded pass, not micro-patches.
> **Revisit:** replace with a v2 prompt after the first implementation receipt. · Last touched: 2026-07-07

---

## Permission header (required, unchanged)

```text
SCOPE: dashboard frontend/backend only, inside
C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live
(WSL: /mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live)

ALLOWED: read/edit/create files under the dashboard app folders; add backend
routes on the existing FastAPI service (:8010); add frontend routes/components
on the existing React app (:3010); read queue, receipts, artifacts,
token_ledger.jsonl, skill_trust.jsonl, workflow/*.md, skill/*.md,
TTROS Business Brain (read-only).

NOT ALLOWED: external sends/writes/publishes; touching the Telegram bridge
code; new queue system; new Hermes install; any old-vault/legacy path;
executing anything from ingest/quarantine; storing or displaying secrets.

STOP FOR LIAM: any external action, any schema change to the queue,
anything requiring the Telegram bridge to change, any dependency install
beyond npm/pypi standard packages.
```

## Task

Implement Dashboard v1 per `dashboard/design/00_DASHBOARD_DESIGN_SPEC.md` and `01_WIREFRAME_NOTES.md`. Before writing code, inspect the existing app and report (7 answers, then proceed):

```text
1. Current frontend route/layout/sidebar structure?
2. Reusable sidebar/layout component present?
3. Existing backend routes for queue/artifacts/receipts/tokens/connectors?
4. What is frontend-only?
5. What needs new backend routes?
6. What to defer (list, don't build)?
7. Smallest change that makes it feel like the cockpit?
```

Reshape the existing app where possible; build fresh components only where the existing ones can't carry the design. Liam will diff against the current dashboard afterward — keep old routes working until told to remove them.

## Build order (stop after any stage if budget/scope pressure)

```text
Stage 1 — Frame: sidebar (12 items per spec §4), top bar, Token Rail shell,
          status-chip vocabulary, action colour language (⚡/🔒).
Stage 2 — Cockpit: Needs Me hero, queue snapshot, workbench tiles,
          recent output, slide-in detail panel component (reused everywhere).
Stage 3 — Work Queue page (Kanban + detail + create form + close actions,
          Telegram reply hook on close for source: telegram items —
          call existing bridge send function; do NOT modify bridge).
Stage 4 — Results & Receipts + Tokens & ROI (read token_ledger.jsonl;
          'unavailable' handling exactly per spec — never fake values).
Stage 5 — Workflow Bench + Skills Board (read workflow/skill files +
          skill_trust.jsonl; Run = create queue item, never direct call).
Stage 6 — Memory Board (read-only Brain views + promotion queue stub),
          Connections grid, Prompt Library.
Stage 7 — Graphify embed page + Repo Ingest stepper. Reconstitute step is
          a documented ⚡ action that creates a queue item — do not wire a
          live model call in this pass.
```

## Hard rules

- Shneiderman on every page: overview first → click-through pre-filtered → slide-in details. No page navigation to view details.
- Zero-token by default: only buttons marked ⚡ may ever trigger model spend, and in this pass ⚡ buttons create queue items rather than calling models directly.
- 🔒 actions render a typed-confirm modal but remain stubbed (no external writes wired).
- No fake data anywhere: missing token values display `unavailable`; missing services display `Unavailable` tile + local launch button.
- No old-vault/legacy paths; Business Brain access is read-only.
- Dark mode, graphite/champagne/ivory palette, dense-but-readable; no heavy animation, no chartjunk (one chart total, on Tokens & ROI).

## Validation

```text
- App boots on :3010/:8010 with existing data files present.
- Cockpit answers "needs me + spend" with zero clicks.
- Every count on Cockpit deep-links to its filtered page.
- Queue item created on dashboard appears with correct fields in the
  existing queue store (round-trip test).
- Closing a source:telegram test item calls the bridge send function
  (mock/log acceptable in this pass).
- Token Rail matches token_ledger.jsonl sums for today.
- No console errors; no secret values rendered.
```

## Closeout (required)

```text
PASS/NEEDS ATTENTION

Work item:
- Dashboard v1 pass, stages completed: ...

Files touched:
- ...

Artifacts:
- ...

Validation:
- ...

Token usage:
- ... (or: unavailable from current CLI output)

Blockers:
- ...

Next action:
- ...
```

## Antigravity variant

Same permission header and rules. Scope narrowed to: visual system (palette tokens, chips, Token Rail styling, tile design, slide-in panel polish) on top of Codex's Stage 1–2 output. No backend work. Same closeout.
