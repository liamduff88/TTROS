$ErrorActionPreference = "SilentlyContinue"

$workspace = $PSScriptRoot
$env:AOS_ROOT = $workspace
$dashboard = Join-Path $workspace "dashboard"
$frontend = Join-Path $dashboard "frontend"
$logs = Join-Path $workspace "logs"

New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Test-LocalPort {
  param([int]$Port)
  $listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $listener) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  }
  return [bool]$listener
}

# Start only missing dashboard services, then open the cockpit.
$backendLog = Join-Path $logs "dashboard_backend.log"
if (-not (Test-LocalPort 8010)) {
  Start-Process -FilePath "cmd.exe" `
    -WindowStyle Hidden `
    -WorkingDirectory $dashboard `
    -ArgumentList "/d /c python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 1>> `"$backendLog`" 2>>&1"

  Start-Sleep -Seconds 4
}

$frontendLog = Join-Path $logs "dashboard_frontend.log"
if (-not (Test-LocalPort 3010)) {
  Start-Process -FilePath "cmd.exe" `
    -WindowStyle Hidden `
    -WorkingDirectory $frontend `
    -ArgumentList "/d /c npm run dev 1>> `"$frontendLog`" 2>>&1"

  Start-Sleep -Seconds 6
}

# Telegram bridge startup is owned separately by connectors\telegram_bridge\Start-Telegram-Bridge-Auto.ps1.

Start-Process "http://127.0.0.1:3010"

