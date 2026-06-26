$ErrorActionPreference = "SilentlyContinue"

$workspace = "C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live"
$dashboard = Join-Path $workspace "dashboard"
$frontend = Join-Path $dashboard "frontend"
$bridgeDir = Join-Path $workspace "connectors\telegram_bridge"
$bridgeAuto = Join-Path $bridgeDir "Start-Telegram-Bridge-Auto.ps1"
$logs = Join-Path $workspace "logs"

New-Item -ItemType Directory -Force -Path $logs | Out-Null

# Clear only the dashboard ports. This removes the bad 3010/8010 listeners.
foreach ($port in 8010,3010) {
  Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}

Start-Sleep -Seconds 2

# Start backend hidden from the correct dashboard folder.
$backendLog = Join-Path $logs "dashboard_backend.log"
Start-Process -FilePath "cmd.exe" `
  -WindowStyle Hidden `
  -WorkingDirectory $dashboard `
  -ArgumentList "/d /c python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 1>> `"$backendLog`" 2>>&1"

Start-Sleep -Seconds 4

# Start frontend hidden from the correct frontend folder.
$frontendLog = Join-Path $logs "dashboard_frontend.log"
Start-Process -FilePath "cmd.exe" `
  -WindowStyle Hidden `
  -WorkingDirectory $frontend `
  -ArgumentList "/d /c npm run dev -- --host 127.0.0.1 --port 3010 1>> `"$frontendLog`" 2>>&1"

Start-Sleep -Seconds 5

# Start Telegram bridge hidden if it is not already running. Do not patch the bridge.
$telegramRunning = Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -like "*telegram_bridge.py*" -and
    $_.CommandLine -like "*Agentic OS Live*"
  }

if (-not $telegramRunning -and (Test-Path $bridgeAuto)) {
  $telegramLog = Join-Path $logs "telegram_bridge_task.log"
  Start-Process -FilePath "powershell.exe" `
    -WindowStyle Hidden `
    -WorkingDirectory $bridgeDir `
    -ArgumentList @(
      "-NoProfile",
      "-ExecutionPolicy", "Bypass",
      "-File", "`"$bridgeAuto`""
    )
}

Start-Sleep -Seconds 6
Start-Process "http://127.0.0.1:3010"

