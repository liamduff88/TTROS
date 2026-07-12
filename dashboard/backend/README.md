# Dashboard Backend
> Revisit: when the backend launch or authority boundary changes. · Last touched: 2026-07-11.

The one supported backend runs on Linux from the canonical `AOS_ROOT` (currently
`/home/liam/agentic-os-live`). Start the existing backend, frontend, and runner
with `tools/aos-linux-runtime.sh start`; inspect or stop them with `status` and
`stop`. Native Windows FastAPI and Windows-mounted authoritative storage are
retired. Windows launchers are thin WSL adapters only.

## Latitude Telemetry

Latitude telemetry is fail-open. Dashboard, queue, search, backup, and runner
routes must keep working when Latitude is not configured or unreachable.

Required runtime variables:

- `LATITUDE_API_KEY`
- `LATITUDE_PROJECT_SLUG` preferred. `LATITUDE_PROJECT` is also accepted as a
  slug alias, or use `LATITUDE_PROJECT_ID` if Latitude provides an ID.
- `LATITUDE_ENDPOINT`

Optional runtime variable:

- `LATITUDE_WORKSPACE_URL`

Do not commit real values. Add them only to the local backend process
environment or an untracked local `dashboard/backend/.env` file. Until the
required variables are present, `/api/latitude/status` reports degraded state
and `/api/latitude/heartbeat` sends nothing.
