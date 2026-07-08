# TTROS Agentic OS Dashboard — Product Design Spec v1

> **Owner:** Liam Duff / Time to Revenue
> **Layer:** Dashboard / cockpit (Blueprint V2 §1 — dashboard was frozen; this spec unfreezes it as a designed pass, not micro-patches)
> **Audience:** Codex / Claude Code / Antigravity implementing against the existing FastAPI :8010 / React :3010 dashboard. Build standalone-comparable; Liam will diff against the current app and merge.
> **Revisit:** after first full week of daily cockpit use, or when Hermes/Graphify integration lands. · Last touched: 2026-07-07

---

## 1. One-line definition

The Agentic OS Dashboard is the single local cockpit where Liam creates, routes, launches, monitors, reviews, and closes all TTR work — across Hermes, Codex, Claude, Claude Code, Antigravity, connectors, Graphify, skills, memory, receipts, and token spend — without leaving the app. Telegram is the only other surface: task in via Telegram → response back to Telegram, with the same work visible in the cockpit.

## 2. Design doctrine (revised from 2026-07-07 context doc)

**Kept:**
- One dashboard. No second dashboard, no second queue, no second memory vault, no new Hermes install.
- Local-first, fast, dark-mode mission-control aesthetic (graphite / champagne / ivory / warm stone).
- Explicit external actions only: read/search/status/draft free; send/write/publish/delete/mutate gated behind an explicit confirm.
- Never fake token data. If unavailable, display `Token usage: unavailable`.
- No old-vault / legacy runtime paths anywhere.
- North Shore stays isolated (optional status tile only, off by default).

**Dropped:**
- ~~Model-silent by default~~ — the dashboard may invoke models for its own features (e.g. repo reconstitution skill, Graphify analysis) as long as every model-invoking button is visually marked (⚡ token badge) and cost lands in the ledger.
- ~~Dreaming / recommendations layer~~ — out of scope entirely for v1.
- ~~"No dashboard change" freeze~~ — superseded by this spec.

## 3. Governing UX law — Shneiderman's mantra

**"Overview first, zoom and filter, then details-on-demand."** Applied everywhere:

| Level | Pattern |
|---|---|
| Overview | Home cockpit: one glance answers "what needs me?" + "what is it costing?" No page requires scrolling to answer its primary question. |
| Zoom | Every card/tile clicks through to its page pre-filtered (e.g. click "3 in Human Review" → Queue page filtered to human_review). |
| Filter | Every list page has the same filter bar: lane · workbench · status · date · text search. Identical placement on all pages. |
| Details on demand | Detail panels slide in from the right (never navigate away). Artifact/receipt preview inline. Raw file open is one more click. |

Supporting best practices baked in:
- **5-second rule:** every page's primary question is answerable in 5 seconds.
- **Consistency:** one status-chip vocabulary everywhere: `Ready · Running · Needs Me · Blocked · Done · Unavailable`. "Needs Me" replaces "human_review" in the UI (maps to queue status `human_review`).
- **Progressive disclosure:** default views show counts + top items, not full tables.
- **Direct manipulation:** close/approve/route from the detail panel; no page hops to act.
- **Cost visibility:** a persistent right-edge **Token Rail** (§5) on every page.
- **No chartjunk:** charts only where a trend is the answer (token spend over time). Everything else is counts and chips.

## 4. Information architecture (left sidebar)

```text
1. Cockpit (Home)
2. Work Queue
3. Workflow Bench        ← workflows + runs in one bench
4. Skills Board          ← Kanban: v0 → earned → stale/demote
5. Memory Board          ← Business Brain management
6. Graphify              ← embedded graph visual + repo intelligence
7. Repo Ingest           ← GitHub in → reconstitute skill → Graphify
8. Results & Receipts
9. Tokens & ROI
10. Connections / Spine
11. Prompt Library
12. Settings / Launchers
```

Workbenches (Hermes, Codex, Claude, Claude Code, Antigravity) do **not** get top-level pages in v1 — they appear as tiles on the Cockpit and as launch targets everywhere (reduces sidebar to 12 items; workbench pages in the old context doc were mostly buttons, which belong on tiles).

Sidebar badges: count of "Needs Me" items per page, ⚡ if a model-invoking action is available on that page.

## 5. Token Rail (global component)

Collapsible right-edge strip, visible on every page (the "spending side tab"):

```text
TODAY
Total est. tokens / est. cost
Per main tool:
  Hermes      ▓▓▓░ 41k · $0.62
  Codex       ▓▓░░ 28k · flat-rate
  Claude Code ▓░░░ 12k · flat-rate
  Antigravity —    unavailable
  Connectors  ▓░░░  3k · $0.04
Highest-cost task today (click → detail)
Unavailable-data count
[Open Tokens & ROI →]
```

Rules: exact ledger values only; flat-rate plans show tokens without $; collapsed state shows a single cost chip in the top bar.

## 6. Telegram round-trip (contract, not UI)

```text
Telegram (Olmec) → bridge → Work Queue item (source: telegram, reply_to: chat_id)
→ routed/executed per normal queue flow
→ on status change to done / needs_input / blocked:
   receipt summary + artifact link posted back to the same Telegram chat
→ dashboard shows the item like any other (source chip: TG)
```

Dashboard requirement: queue items carry `source` and `reply_to`; the close/approve action triggers the Telegram reply. No Telegram panel page in v1 — Telegram items are just queue items with a TG chip. Existing bridge is extended, not replaced.

## 7. Top bar

- Global command bar: `Create task · Ask Hermes ⚡ · Search everything` (search spans queue, results, prompts, skills, memory index — local, zero-token).
- Collapsed token chip (today's cost).
- Global status dot: green (nothing needs me) / amber (Needs Me > 0) / red (Blocked > 0).

## 8. Action colour language

```text
Neutral button  = local, zero-token (open, filter, preview, copy)
⚡ badge        = invokes a model (cost lands in ledger)
🔒 badge        = external write/send/publish — requires typed confirm
```

## 9. What v1 explicitly does not include

Dreaming layer · North Shore routing · new queue system · new permission system · connector-by-connector bespoke UIs · always-on agent loops · second dashboard.

## 10. File map for this batch

```text
dashboard/design/00_DASHBOARD_DESIGN_SPEC.md    ← this file
dashboard/design/01_WIREFRAME_NOTES.md          ← page-by-page wireframes
dashboard/design/02_BUILD_PROMPT_CODEX_ANTIGRAVITY.md ← implementation prompt
```
