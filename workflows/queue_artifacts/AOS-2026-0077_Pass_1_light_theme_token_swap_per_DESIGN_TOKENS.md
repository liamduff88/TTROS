# AOS-2026-0077 — Pass 1 light-theme token implementation

> Revisit: only if Liam approves a palette change or the dashboard theme pipeline changes. · Last touched: 2026-07-12.

## Purpose

Implement Pass 1 only: replace the active dark dashboard palette with the permanent locked light palette from `_buildout_package/DESIGN_TOKENS.md`, without changing layout, routing, queue behavior, review behavior, previews, launchers, or backend contracts.

## Files changed for Pass 1

- `dashboard/frontend/index.html`
- `dashboard/frontend/tailwind.config.js`
- `dashboard/backend/main.py` (honest unavailable-token rollup repair)
- `dashboard/backend/test_composio_hermes.py` (token-basis regression test)
- `dashboard/frontend/src/index.css`
- `dashboard/frontend/src/components/DashboardKit.jsx`
- `dashboard/frontend/src/components/Sidebar.jsx`
- `dashboard/frontend/src/views/AgentWorkbench.jsx`
- `dashboard/frontend/src/views/Connectors.jsx`
- `dashboard/frontend/src/views/DashboardV1.jsx` (token-unavailable display repair; pre-existing reconciliation behavior change preserved)
- `dashboard/frontend/src/views/PacketCreator.jsx`
- `dashboard/frontend/src/views/Queue.jsx` (color-token references only; pre-existing reconciliation behavior changes were preserved)
- `dashboard/frontend/src/views/Tracker.jsx`
- `decisions/DECISIONS.md` (behavior-change record for unavailable token display)

## Exact design tokens implemented

```css
--surface-0: #FFFFFF;
--surface-1: #F7F8FA;
--surface-2: #EFF1F4;
--hairline: #E5E7EB;
--text: #17181C;
--text-dim: #5B616E;
--wb-claude-working: #A03E1E;
--wb-claude-queued: #D85A30;
--wb-claude-done: #F5CDBD;
--wb-claude-dark: #7A2E15;
--wb-codex-working: #1F5FA8;
--wb-codex-queued: #378ADD;
--wb-codex-done: #C9E2F8;
--wb-codex-dark: #16456F;
--wb-hermes-working: #B87413;
--wb-hermes-queued: #EF9F27;
--wb-hermes-done: #FBE6C2;
--wb-hermes-dark: #7C4E0C;
--wb-anti-working: #147A66;
--wb-anti-queued: #1FA98C;
--wb-anti-done: #C4EDE3;
--wb-anti-dark: #0E5546;
--lane-marketing: #2E9E5B;
--lane-revenue: #7C5CD6;
--lane-delivery: #D6559A;
--lane-operations: #6B7280;
--needs-review: #FFB020;
--needs-review-text: #4A3000;
```

## Obsolete theme values replaced

Active references to `#111315`, `#0D1418`, `#F7F3EA`, `#D8D0C2`, `#B89B63`, `#2B2F32`, `#7A746A`, `#4E5A50`, `#52616B`, `#A56C53`, `#1b1110`, and `#171B1D` were replaced by the locked CSS custom properties. Legacy black translucent wells were replaced with `--surface-2`. Tailwind opacity variants now compile through token-backed `color-mix`, so translucent borders, cards, hovers, and shadows remain functional without reintroducing dark hexes.

## Tests and build

- `python3 -m unittest tests.test_aos_queue` — PASS, 38 tests.
- `python3 -m unittest tests.test_aos_paths` — PASS, 7 tests.
- `python3 -m unittest tests.test_aos_orchestration` — PASS, 16 tests.
- `python3 -m unittest tests.test_aos_search` — PASS, 7 tests.
- `python3 -m unittest dashboard.backend.test_composio_hermes` — PASS, 117 tests.
- `npm run build` in `dashboard/frontend` — PASS, 1,643 modules transformed.
- Automated DESIGN_TOKENS/source comparison — PASS, 28/28 exact names and values.
- Obsolete active dark-hex/source check — PASS, no matches.
- `git diff --check` — PASS.

One combined Python invocation exposed test-process contamination (`fastapi.__spec__` left unset by an earlier module stub); each required suite passed in a clean process, confirming no application failure. Final clean-process total: 185 tests.

## Browser proof

Real Linux dashboard: `http://127.0.0.1:3010` backed by `http://127.0.0.1:8010`.

- `/tmp/ttros-pass-1-proof/after-cockpit.png`
- `/tmp/ttros-pass-1-proof/after-work-queue.png`
- `/tmp/ttros-pass-1-proof/after-needs-me.png`
- `/tmp/ttros-pass-1-proof/after-receipt-artifact-preview.png`
- `/tmp/ttros-pass-1-proof/after-pass-1-receipt-preview.png`
- `/tmp/ttros-pass-1-proof/after-token-reconciliation.png`

Automated Playwright proof navigated Cockpit → Work Queue → AOS-2026-0075 receipt preview → Cockpit/Needs Me. Result: PASS; `BROWSER_RUNTIME_ERRORS=[]`. The real UI shows white page surfaces, light-grey rails/cards/wells, hairline borders, near-black/dim text, readable queue/review content, working navigation, and a readable receipt/artifact preview. No active dark surface or unintended layout change was observed.

## Known limitations

- Exact Codex session input/output/total tokens are not exposed by the current CLI output. No number was estimated or invented.
- Pass 2 shell/layout/two-axis application work was not opened or begun.

## Protected-boundary and external-action evidence

- Path-level Git checks found no changes under the protected paths named in the authorization. Their contents were not inspected.
- Package definitions, package state/journal/closeout, loader, manifest, schema, and audit files were not changed by Pass 1.
- Immutable fixtures AOS-2026-0071/0073/0074/0075 were read only and not mutated.
- No external send, publish, CRM/Gmail/Calendar/Drive/LinkedIn/GitHub mutation, deployment, commit, push, credential change, or money movement occurred.

## Token-reporting evidence

- Codex CLI: `codex-cli 0.144.1`; session input/output/total values unavailable.
- Model identity associated with exact usage: unavailable because no exact usage report was emitted.
- Receipt: `queue/receipts/AOS-2026-0077-pass-1.md` states the unavailable condition explicitly.
- Sidecar `queue/receipts/AOS-2026-0077.token_usage.json`: orchestrator/subagent/workbench components unavailable; structural numeric fields remain zero only under an explicit non-empty `unavailable` list.
- Token ledger: one `AOS-2026-0077` record at `2026-07-12T19:18:32Z`, `model_requested=Codex workbench session`, `model_confirmed=unavailable`, with the same unavailable block as the sidecar.
- Dashboard defects found and repaired: Tokens & ROI formerly rendered structural placeholder totals as `0` and counted all-zero unavailable blocks as known. Ledger rows now label the total `unavailable`; the backend excludes all-zero unavailable blocks from known totals; mixed periods say `known + gaps`; the current-day Pass 1 rollup is `unavailable`, never exact zero.

Token usage: unavailable from current CLI output.
