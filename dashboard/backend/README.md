# Dashboard Backend
> Revisit: when the backend launch or authority boundary changes. · Last touched: 2026-08-10.

The one supported backend runs on Linux from the canonical `AOS_ROOT` (currently
`/home/liam/agentic-os-live`). The backend, frontend and runner are started by systemd user units
(`aos-backend`, `aos-frontend`, `aos-runner`); inspect or control them with
`systemctl --user status|start|stop <unit>`. Native Windows FastAPI and
Windows-mounted authoritative storage are retired. Windows launchers are thin WSL adapters only.

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

## Remote PC

`remote_pc.py` serves `/api/remote-pc/*`: Windows PowerShell, file browse/download/upload,
Explorer reveal, desktop-host status and receipts. Every route verifies the operator at the
backend — a Cloudflare Access JWT (pinned by `TTROS_DASHBOARD_ACCESS_AUD`) on the Cloudflare
path, or the Tailscale Serve `Tailscale-User-Login` header on the tailnet path — against
`TTROS_REMOTE_PC_IDENTITIES`, and requires the `X-TTROS-Remote-PC: 1` header so no other site
can drive it from a browser. Funnel requests are refused. PowerShell runs and uploads need a
prepare → run round trip whose single-use token is bound to the exact command (and timeout)
or upload target and size. Receipts and refused attempts are written to
`queue/receipts/remote_pc/` (git-ignored). Execution is WSL interop → Windows PowerShell 5.1
as the signed-in Windows user at medium integrity; it cannot elevate.
