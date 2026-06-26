$ErrorActionPreference = "Stop"

$workspace = "C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live"
$bridgeDir = Join-Path $workspace "connectors\telegram_bridge"
$logsDir = Join-Path $workspace "logs"
$stdout = Join-Path $logsDir "telegram_bridge.stdout.log"
$stderr = Join-Path $logsDir "telegram_bridge.stderr.log"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

$workers = @(Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -like "*telegram_bridge.py*" })

if ($workers.Count -eq 1) {
  exit 0
}

if ($workers.Count -gt 1) {
  $workers | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 2
}

Set-Content -Path $stdout -Value "" -Encoding UTF8
Set-Content -Path $stderr -Value "" -Encoding UTF8

Start-Process -FilePath "py.exe" `
  -WorkingDirectory $bridgeDir `
  -WindowStyle Hidden `
  -RedirectStandardOutput $stdout `
  -RedirectStandardError $stderr `
  -ArgumentList @("-3", "-u", "telegram_bridge.py")
