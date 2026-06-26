$ErrorActionPreference = "SilentlyContinue"

$workspace = "C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live"
$dashboard = Join-Path $workspace "dashboard"
$logsDir = Join-Path $workspace "logs"
$backendLog = Join-Path $logsDir "dashboard_backend.log"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

# If backend is already listening, do nothing.
$existing = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
  exit 0
}

Start-Process -FilePath "cmd.exe" `
  -WindowStyle Hidden `
  -WorkingDirectory $dashboard `
  -ArgumentList "/d /c python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 1>> `"$backendLog`" 2>>&1"
