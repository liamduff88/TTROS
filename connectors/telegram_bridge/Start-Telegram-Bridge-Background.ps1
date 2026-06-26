$workspace = "C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live"
$bridgeDir = Join-Path $workspace "connectors\telegram_bridge"
$auto = Join-Path $bridgeDir "Start-Telegram-Bridge-Auto.ps1"

$alreadyRunning = Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -like "*telegram_bridge.py*" -and
    $_.CommandLine -like "*Agentic OS Live*"
  }

if ($alreadyRunning) {
  exit 0
}

Start-Process powershell.exe `
  -WindowStyle Hidden `
  -WorkingDirectory $bridgeDir `
  -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $auto
  )
