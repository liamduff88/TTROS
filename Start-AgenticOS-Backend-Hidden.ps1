$ErrorActionPreference = "SilentlyContinue"

$workspace = $PSScriptRoot
$env:AOS_ROOT = $workspace
$dashboard = Join-Path $workspace "dashboard"
$logs = Join-Path $workspace "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

if (Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue) {
  exit 0
}

Set-Location $dashboard
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 *>> (Join-Path $logs "dashboard_backend.log")
