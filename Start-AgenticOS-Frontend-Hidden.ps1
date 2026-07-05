$ErrorActionPreference = "SilentlyContinue"

$workspace = $PSScriptRoot
$env:AOS_ROOT = $workspace
$frontend = Join-Path $workspace "dashboard\frontend"
$logs = Join-Path $workspace "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

if (Get-NetTCPConnection -LocalPort 3010 -State Listen -ErrorAction SilentlyContinue) {
  exit 0
}

Set-Location $frontend
npm run dev *>> (Join-Path $logs "dashboard_frontend.log")
