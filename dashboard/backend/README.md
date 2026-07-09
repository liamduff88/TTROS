# Dashboard Backend

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
