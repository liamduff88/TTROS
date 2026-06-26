[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Distro = 'AgenticOSClean'
$LinuxUser = 'liam'
$PackageDirectoryWindows = Split-Path -Parent $PSScriptRoot
$BashLauncherWindows = Join-Path $PSScriptRoot 'start_north_shore_bot.sh'
$LogsDirectory = Join-Path $PackageDirectoryWindows 'logs'
$LogFile = Join-Path $LogsDirectory 'north_shore_bot.log'

function ConvertTo-BashSingleQuoted {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + ($Value -replace "'", "'\''") + "'"
}

if (-not (Test-Path -LiteralPath $BashLauncherWindows -PathType Leaf)) {
    throw "North Shore bash launcher was not found: $BashLauncherWindows"
}

[IO.Directory]::CreateDirectory($LogsDirectory) | Out-Null

$PackageDirectoryWsl = (& wsl.exe -d $Distro --user $LinuxUser -- wslpath -a $PackageDirectoryWindows).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($PackageDirectoryWsl)) {
    throw "Could not resolve the North Shore package path in $Distro."
}

$QuotedPackageDirectory = ConvertTo-BashSingleQuoted $PackageDirectoryWsl
$QuotedLogFile = ConvertTo-BashSingleQuoted 'logs/north_shore_bot.log'
$BashCommand = @"
set -euo pipefail
cd $QuotedPackageDirectory
mkdir -p logs
printf '[%s] North Shore startup launcher invoked.\n' "`$(date -Is)" >> $QuotedLogFile
exec scripts/start_north_shore_bot.sh >> $QuotedLogFile 2>&1
"@

& wsl.exe -d $Distro --user $LinuxUser -- bash -lc $BashCommand
exit $LASTEXITCODE
