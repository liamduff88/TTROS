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

# Backend: delegate to Start-AgenticOS-Backend-Auto.ps1, which runs the
# stale-worker preflight cleanup and then starts a single fresh instance.
# Always run it (not gated on Test-LocalPort) so a stale/orphaned worker
# from a prior session can't be mistaken for a healthy one and skipped.
& (Join-Path $workspace "Start-AgenticOS-Backend-Auto.ps1")
Start-Sleep -Seconds 4

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

