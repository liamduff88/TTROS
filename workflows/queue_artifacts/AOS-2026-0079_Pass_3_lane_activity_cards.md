# Pass 3 — lane activity cards
> Revisit: with the dashboard lane/queue contract. · Last touched: 2026-07-12.

PASS

- Added five Cockpit queue drilldowns: Marketing, Revenue, Delivery, Operations, and Unassigned.
- Lane resolution uses `lane:*` tags first, then a lane owner, otherwise Unassigned. Owner, workbench, and status remain separate fields; no worker field is used.
- Cards expose current assigned work, last completed item, receipt, artifact, required status counts, exact-or-unavailable token usage, last successful run, and filtered queue shortcuts.
- Fixture proof from the live API: AOS-2026-0073 Marketing; AOS-2026-0074 Delivery; AOS-2026-0071 and AOS-2026-0075 Unassigned with their real Hermes/Codex owner-workbench labels because neither records a lane.
- Browser proof: `workflows/queue_artifacts/pass3-proof/browser-proof.json` and two viewport screenshots.

Token usage: unavailable from current CLI output.
