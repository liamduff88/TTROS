# Optional idempotent Windows client/startup adapter installer.
# Revisit: when distro, Linux root, or startup filename changes. Last touched: 2026-07-11.
$ErrorActionPreference = "Stop"
$oldRoot = 'C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live'

Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^(python|pythonw|node)(\.exe)?$' -and
    $_.CommandLine -and $_.CommandLine.Contains($oldRoot)
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop }

$startup = [Environment]::GetFolderPath('Startup')
$adapter = Join-Path $startup 'AgenticOS-Linux-Hidden.vbs'
$body = @'
Set shell = CreateObject("WScript.Shell")
shell.Run "wsl.exe -d AgenticOSClean --user liam -- bash -lc ""export AOS_ROOT=/home/liam/agentic-os-live; cd """"$AOS_ROOT""""; exec bash tools/aos-linux-runtime.sh start""", 0, False
'@
if (-not (Test-Path $adapter) -or (Get-Content -Raw $adapter) -ne $body) {
    Set-Content -LiteralPath $adapter -Value $body -Encoding ASCII -NoNewline
}
Write-Output $adapter
