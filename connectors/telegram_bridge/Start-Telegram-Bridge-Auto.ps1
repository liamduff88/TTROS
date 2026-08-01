$ErrorActionPreference = "Stop"

# Windows is only the launcher. The canonical bridge and all runtime state stay
# on the Linux-native AgenticOSClean filesystem. The bridge owns its singleton
# lock, so this launcher never kills command-line matches.
$linuxCommand = 'export AOS_ROOT=/home/liam/agentic-os-live; cd /home/liam/agentic-os-live; exec python3 -u connectors/telegram_bridge/telegram_bridge.py >> logs/telegram_bridge.stdout.log 2>> logs/telegram_bridge.stderr.log'

# Windows PowerShell 5.1 exposes ProcessStartInfo.Arguments, not ArgumentList.
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = "wsl.exe"
$startInfo.Arguments = '-d AgenticOSClean --user liam -- bash -lc ' + '"' + $linuxCommand + '"'
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

$process = [System.Diagnostics.Process]::Start($startInfo)
if ($null -eq $process) {
  throw "Unable to start the canonical Linux Telegram bridge."
}
