# BLUEPRINT V2 — AMENDMENT 3: DASHBOARD UNFROZEN

> **Owner:** Liam Duff / Time to Revenue
> **Applies to:** `TTROS_AGENTIC_OS_SYSTEM_BLUEPRINT_V2.md` — append to the end of §0 PRIME DOCTRINE, or keep as a sibling file. Amendment order: 1 = pre-seeded playbooks, 2 = token efficiency, 3 = this.
> **Date:** 2026-07-07
> **Revisit:** when Dashboard v1 first implementation receipt lands, or if the dashboard spec is superseded. · Last touched: 2026-07-07

---

**Amendment 3 — the dashboard is unfrozen and has its own design authority.**

V2 froze the dashboard ("Freeze. Out of scope. Back end gets dashboard-ready token endpoints only," §0 constraint / §1 inventory / §8.5). That freeze is lifted as of 2026-07-07. Four changes:

**3.1 — Design authority split.** The dashboard is now governed by its own design set:

```text
dashboard/design/00_DASHBOARD_DESIGN_SPEC.md      (product spec — authoritative for the cockpit layer)
dashboard/design/01_WIREFRAME_NOTES.md            (page-by-page wireframes)
dashboard/design/02_BUILD_PROMPT_CODEX_ANTIGRAVITY.md (implementation prompt)
```

This blueprint remains authoritative for architecture, orchestration, doctrine, phases, and data contracts. The design spec is authoritative for dashboard UX, pages, and layout. If they conflict on a data contract (queue schema, receipt format, token ledger fields), **the blueprint wins**; if they conflict on UI behavior, **the spec wins**.

**3.2 — "Model-silent" superseded.** The dashboard is no longer model-silent by default. Replacement rule: every action in the dashboard is one of three marked classes — neutral (local, zero-token), **⚡ model-invoking** (cost lands in the token ledger; in the v1 build ⚡ actions create queue items rather than calling models directly), or **🔒 external write** (typed confirm required; consistent with the standing explicit-external-actions constraint, which is unchanged). Zero-token remains the default for all review/status/navigation.

**3.3 — Phase placement.** Dashboard v1 becomes its own build phase, sequenced **after Phase 3 (routing + token metering)**, because the Tokens & ROI page and Token Rail read directly from the §8 ledger. Graphify embed and Repo Ingest pages within the dashboard remain gated on Phase 5 (Graphify install); they ship as `Unavailable`-state tiles until then. The Telegram close-loop (reply-to-Telegram on item close) reuses the existing bridge send path and does **not** modify the bridge — the Phase 5 bridge re-point constraint stands.

**3.4 — Inventory row updated.** §1 inventory line for Dashboard changes from:

```text
Freeze. Out of scope. Back end gets dashboard-ready token endpoints only (§8.5)
```

to:

```text
Rebuild per dashboard/design spec (Amendment 3). One bounded pass, staged;
existing routes kept working until diffed and merged. Still one dashboard —
the no-second-dashboard constraint is unchanged.
```

Everything else in V2 — one Hermes install, orchestration structure, skills doctrine (Amendments 1–2), memory substrate, protected paths, anti-rot, phase plan — carries forward unmodified. The Dreaming/recommendations layer from the 2026-07-07 dashboard context doc is explicitly **not** adopted.
