# Post-WP12 Graphify Discovery — 2026-07-09
> Revisit: when Graphify is actually installed, or this note is superseded by a real setup pass. · Last touched: 2026-07-09.

## Finding: Graphify is a planned codename, not an installed tool

`git grep -n "Graphify\|graphify"` across the repo returns only:
- Design docs (`dashboard/design/00_DASHBOARD_DESIGN_SPEC.md`,
  `01_WIREFRAME_NOTES.md`, `02_BUILD_PROMPT_CODEX_ANTIGRAVITY.md`,
  `BLUEPRINT_V2_AMENDMENT_3_dashboard.md`) describing Graphify as a future
  sidebar page: "embedded graph visual + repo intelligence."
- `context/TTROS_AGENTIC_OS_CURRENT_MASTER_CONTEXT_2026-07-08.md:40` —
  explicitly logs "Graphify is not set up yet" as an open item.
- Frontend: [Sidebar.jsx:9](../dashboard/frontend/src/components/Sidebar.jsx)
  nav entry; [DashboardV1.jsx:415-418](../dashboard/frontend/src/views/DashboardV1.jsx)
  `GraphifyPage` — renders an honest `Unavailable` empty state with an inert
  `Launch Graphify` button (no `onClick`, does nothing — this is correct,
  not a bug).
- Backend: [main.py:4059-4066](../dashboard/backend/main.py) —
  `/api/dashboard/graphify` returns a static `{"available": false, "status":
  "Unavailable", ...}` stub. `main.py:3424` also lists `graphify` in the
  cockpit workbench-tile loop as an always-`Unavailable` tile until queue
  items exist for it.

**No local file names a concrete package, npm module, PyPI package, GitHub
repo, port, or CLI binary called "Graphify."** It is a design-doc codename
for a not-yet-chosen local repo-graph/knowledge-graph tool, referenced the
same way the docs reference "Hermes" or "Latitude" as named integrations —
except unlike those, no specific product was ever pinned down. Per task
constraints (identify only from local files; do not install unless the
official path is unambiguous), **no install path is unambiguous, so nothing
was installed.**

## What Graphify should do for TTROS (per design docs)

- Give a visual, filterable graph of the OS/repo knowledge structure: repos,
  files/modules as nodes, dependency/reference edges.
- Sit behind its own local page in the existing dashboard (sidebar item
  already present), embedded via iframe/webview to a locally-running
  instance — **not** re-implemented as dashboard-native code.
- Support the Repo Ingest pipeline's last stage ("Graphify index") — once a
  reconstituted repo is available, it gets indexed and becomes browsable
  here.
- Optional actions per the wireframe: analyze dependencies (⚡ token
  action), open node source file, create a queue task from a node,
  re-index a repo.

## What it must not do

- Must not become a second dashboard or replace/duplicate the existing
  cockpit (`rules/never.md` #5).
- Must not index or touch North Shore, Telegram bridge files,
  `queue/model_routes.json`, `queue/lane_profiles.json`, `.env`/secrets, or
  any `legacy_harvest/` / old-vault path.
- Must not execute anything from `ingest/quarantine/` — only reconstituted,
  provenance-noted copies are indexable.
- Must not silently fake a "Ready"/connected status — if not running, the
  tile stays `Unavailable` with a real local launch command, per the
  no-fake-data rule already implemented in `GraphifyPage`.
- Must not require a new Hermes install or a second queue/memory vault.

## Proposed install/use path (blocked pending a tool decision)

No install is safe to run yet because "Graphify" has never been pinned to
an actual package. Before any setup command runs, one decision is needed:
which concrete local tool plays the "Graphify" role. Candidates that match
the described shape (local, self-hosted, embeddable via iframe, indexes a
repo into a node/edge graph) are things like a local code-knowledge-graph
viewer or a dependency-graph visualizer — but naming one here would be
guessing, not discovery, so this note stops short of recommending a
specific package/URL.

Once Liam names or approves a specific tool, the safe install shape is:
- Install locally only (npm/pip package or a single local binary/container
  the dashboard can shell out to or reverse-proxy — no cloud account, no
  external API key requirement).
- Run on its own local port, not `:8010` (backend) or `:3010` (frontend).
- Dashboard integration stays limited to: (a) a `/api/dashboard/graphify`
  backend check for whether the local instance is reachable, and (b) the
  existing `GraphifyPage` iframe embed + `Launch Graphify` button pointing
  at the local URL. No new dashboard page, no schema change.

## Files/folders it may index

- `dashboard/` (frontend + backend source, for the "repo intelligence"
  self-view)
- Reconstituted repos only, under `ingest/reconstituted/<repo>/` (once that
  pipeline exists)
- Top-level TTROS Agentic OS Live source folders that are already
  git-tracked and non-secret (e.g. `skills/`, `workflows/`, `rules/`,
  `queue/*.md` docs) — read-only indexing, no writes back into these paths.

## Excluded paths

- `workspaces/north_shore_sales_coach/` (all of it)
- `connectors/telegram_bridge/`
- `.env`, `.env.*`, `*.secret*`, `secrets/`
- `queue/model_routes.json`, `queue/lane_profiles.json`
- `legacy_harvest/`, any old-vault/ZPC/legacy path
- `ingest/quarantine/` (pre-reconstitution — never indexed or executed)
- `context/*CONNECTION_MEMORY*.md` (already gitignored as local identity
  state)

## Dashboard role: launch/open only, plus a thin status check

Per the wireframe, the dashboard should not try to render or reimplement
the graph itself. It should:
- Show a real `Ready`/`Unavailable` status tile (already wired, currently
  honestly `Unavailable`).
- Offer a `Launch Graphify` local command button once a real launch command
  exists (currently correctly inert).
- Embed the running instance via iframe once it's reachable, rather than
  building graph rendering into the dashboard's own React code.

This keeps the "no second dashboard" and "small diffs" rules intact — the
dashboard stays a thin status/launch/embed shell around Graphify, not a
reimplementation of it.

## Next exact step

This is a decision, not a command, because the install path is still
ambiguous:

> Ask Liam to name (or approve a proposed) concrete local tool for the
> "Graphify" role — e.g. a specific local code-knowledge-graph package/repo
> he already has in mind — before any install command is run. Once named,
> re-run this discovery pass scoped to that one package to confirm a
> local-only, secret-free, non-destructive install command, then wire the
> existing `/api/dashboard/graphify` stub to a real reachability check.

No setup/install command is recommended in this pass.
