# Dashboard Wireframe Notes — page by page

> **Owner:** Liam Duff / Time to Revenue
> **Pairs with:** 00_DASHBOARD_DESIGN_SPEC.md (doctrine, Token Rail, chip vocabulary apply globally)
> **Convention per page:** Primary question · Overview zone · Zoom/filter · Details-on-demand · Actions (⚡ = model, 🔒 = external write)
> **Revisit:** after first implementation pass; mark anything unused after 2 weeks for cut. · Last touched: 2026-07-07

Global frame on every page: left sidebar · top command bar · Token Rail (right, collapsible) · main content.

---

## 1. Cockpit (Home)

**Primary question:** *What needs me right now, and what is the OS doing/spending?*

```text
┌─────────────────────────────────────────────────────┬──────────┐
│ NEEDS ME (hero row — largest element on screen)     │ TOKEN    │
│ [3 Needs Me] [1 Blocked] [2 Needs Input]            │ RAIL     │
│  → top 5 cards: title · lane · age · [Review] btn   │          │
├──────────────────────────┬──────────────────────────┤ today    │
│ QUEUE SNAPSHOT           │ WORKBENCH TILES          │ totals + │
│ counts per status,       │ Hermes·Codex·Claude·     │ per-tool │
│ each count clickable →   │ ClaudeCode·Antigravity·  │ bars     │
│ filtered Queue page      │ Connectors·Graphify      │          │
│                          │ tile: status·last task·  │ highest- │
│                          │ tokens today·[Open]      │ cost task│
├──────────────────────────┴──────────────────────────┤          │
│ RECENT OUTPUT (last 5 artifacts/receipts,           │          │
│ click → slide-in preview)                           │          │
└─────────────────────────────────────────────────────┴──────────┘
```

- "Needs Me" cards act inline: Approve / Close / Needs Input / Open detail — no navigation for the common case.
- Telegram-sourced items show a `TG` chip; closing them fires the Telegram reply (spec §6).
- Empty state: "Nothing needs you. Next recommended: <oldest inbox item>."

## 2. Work Queue

**Primary question:** *What work exists and where is it stuck?*

- Overview: Kanban columns = Inbox · Todo · Working · Needs Input · Needs Me · Blocked · Done (Done collapsed by default).
- Filter bar (standard): lane · workbench · source (TG/dashboard/ChatGPT) · priority · text.
- Card: title · lane chip · owner · age · token cost (if any) · TG chip.
- Detail slide-in: full item fields per Blueprint schema (ID, context, allowed actions, stop conditions, DoD, receipts, artifacts, route/model metadata, token usage, next action).
- Actions: [Run via Hermes ⚡] · [Copy Codex prompt] · [Copy Claude prompt] · [Close: done/needs_input/blocked + note] · [Recover stuck (timeout only)].
- Create form = the Blueprint queue-item field set; lane + title required, everything else progressive-disclosure ("More fields ▾").

## 3. Workflow Bench

**Primary question:** *What repeatable workflows do I have, and how do I run one now?*

- Overview: workflow cards grouped by lane (Revenue · Marketing · Delivery · Operations · OS/Build). Card: name · last run · success streak · avg tokens/run.
- Seeded from real workflow files: speed_to_lead, voice_agent_setup, lead_gen_agent, client_memory, fit_call_prep, quick_win_scan, business_efficiency_assessment, marketing_content, weekly_review, ai_operations_support.
- Detail slide-in: workflow steps (read from the `__workflow.md` file) · linked skill · run history (receipts) · token cost per run.
- Actions: [Run → creates pre-filled queue item ⚡ on execution] · [Open workflow file] · [View last receipt].
- A "run" is never a direct model call from this page — it always creates a queue item first (durability rule).

## 4. Skills Board

**Primary question:** *Which skills are earning their keep?*

- Overview: Kanban — `v0 (pre-seeded)` → `Earning (1–2 real uses)` → `Earned (3+ uses)` → `Stale (90d unused / demote candidate)`.
- Cards auto-placed from skill_trust.jsonl + receipts: name · lane · uses · last used · avg tokens.
- Per Blueprint Amendment 1: the four delivery playbooks (Speed-to-Lead, Voice Agent, Client Memory, Lead Gen Agent) start in v0 with a `core-offer` chip and are never auto-demoted — demotion for those is a flagged suggestion only.
- Detail: SKILL.md preview · linked workflow · use log.
- Actions: [Open SKILL.md] · [Promote/Demote (writes skill_trust entry)] · [Create task using this skill].

## 5. Memory Board

**Primary question:** *Is the Business Brain current, and what's waiting to be promoted?*

- Overview, three columns:
  1. **Brain status** — memory root path check, memory_index freshness, protected-paths OK/violation, file count.
  2. **Promotion queue** — receipts/decisions flagged for promotion (from memory_promotion policy); card: source receipt · proposed target file · [Promote ⚡] · [Dismiss].
  3. **Recently touched memory** — last 10 memory files changed, with `Revisit:` dates surfaced; overdue revisits get amber chips.
- Detail: markdown preview of any memory file, read-only from the dashboard except via Promote flow.
- Hard rule rendered as a banner if triggered: no old-vault paths ever appear here; a path outside TTROS Business Brain shows `🔒 blocked path`.

## 6. Graphify

**Primary question:** *What does the OS/repo knowledge structure look like?*

- Overview: **embedded Graphify graph visual** (iframe/webview to local Graphify instance) filling the main area — repos, nodes, dependency clusters.
- Left mini-panel: indexed repos/projects list · node count · last analyzed date.
- Zoom/filter: native Graphify controls inside the embed; repo picker above it.
- Actions: [Analyze dependencies ⚡] · [Open node source file] · [Create queue task from node] · [Re-index repo].
- If Graphify isn't running: tile shows `Unavailable` + [Launch Graphify] local command button. Never a broken iframe.

## 7. Repo Ingest

**Primary question:** *How do I get an outside GitHub repo safely into my system?*

Pipeline rendered as a horizontal stepper:

```text
[1 Fetch] → [2 Quarantine] → [3 Reconstitute ⚡] → [4 Graphify index] → [5 Available]
```

- **Fetch:** paste GitHub URL → clone into `ingest/quarantine/<repo>` (read-only staging, outside live paths).
- **Quarantine:** local static scan summary (file types, size, scripts present, anything executable flagged). Zero-token.
- **Reconstitute ⚡:** runs the reconstitution skill — model reads quarantined source and rebuilds a clean, understood copy into `ingest/reconstituted/<repo>` (no blind copy of executables/CI hooks/secrets; provenance note written). This is the safety gate.
- **Graphify index:** reconstituted copy indexed; appears on Graphify page.
- Table below stepper: all ingested repos · stage · date · tokens spent · [View provenance note].
- 🔒 nothing from quarantine is ever executed or moved into live workspace paths without the reconstitute step passing.

## 8. Results & Receipts

**Primary question:** *What happened, and is it safe to close?*

- Overview: unified reverse-chron list (receipts + artifacts interleaved), grouped by day.
- Filter bar: queue item · lane · workbench · date · text.
- Row: PASS/NEEDS ATTENTION chip · title · queue ID · workbench · tokens · time.
- Detail slide-in: full compact receipt (Blueprint format) · artifact preview (md/html/pdf inline) · [Open folder] · [Copy closeout] · [Close linked queue item].

## 9. Tokens & ROI

**Primary question:** *Where is my token money going and is it worth it?*

- Overview: Today / Week / Month toggle · one spend-over-time chart · totals.
- Breakdown table (from token_ledger.jsonl): by task · lane · workbench · model · provider · workflow. Sort by cost. "Unavailable" rows counted separately, never zero-filled.
- ROI panel (clearly labelled *Estimated*): inputs editable in Settings (hourly value, time-saved per task tag, subscription costs) → est. time saved · est. $ value · cost · net ROI.
- No fake precision: flat-rate tools show tokens only.

## 10. Connections / Spine

**Primary question:** *What can the OS reach, and what's safe to do?*

- Overview: connector grid (Gmail, Calendar, Drive, Docs, Sheets, GitHub, LinkedIn, YouTube, Instagram, Maps, Agent Mail, Reddit, GHL-later): status dot · last used · scope chip (`read-ok` / `write-gated 🔒`).
- Actions per connector: [Check status] · [Prepare draft ⚡] · [Create queue task]. No raw write buttons exist — writes only via queue items with explicit allowed-actions.
- Never display token/OAuth values.

## 11. Prompt Library

**Primary question:** *What stored prompt do I reuse instead of rewriting?*

- Overview: cards by category (Codex impl · Claude Code polish · Antigravity build · Hermes ops · lane prompts · connector prep · memory update).
- Card: title · target tool · lane · last used.
- Detail: full prompt with permission header · allowed files · stop conditions · closeout format.
- Actions: [Copy] · [Create queue item from prompt] · [Edit metadata]. Copy is the fallback path; queue is the main path.

## 12. Settings / Launchers

- Local launch commands (Hermes, Graphify, workbenches) as copy/run buttons.
- ROI inputs · Token Rail preferences · Telegram bridge status (read-only) · protected paths list (read-only) · theme.
- North Shore status tile toggle (default off).
