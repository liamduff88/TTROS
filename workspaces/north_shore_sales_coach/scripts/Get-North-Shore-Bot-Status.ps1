[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Distro = 'AgenticOSClean'
$LinuxUser = 'liam'
$RunnerPattern = 'python3[[:space:]]+-m[[:space:]]+src\.north_shore_bot_runner'

$BashCommand = @"
set -euo pipefail
count="`$(pgrep -u "`$(id -u)" -f '$RunnerPattern' 2>/dev/null | wc -l | tr -d '[:space:]')"
if [ "`$count" = "0" ]; then
    printf 'North Shore bot runner: stopped\n'
    exit 1
fi
printf 'North Shore bot runner: running (%s process%s)\n' "`$count" "`$([ "`$count" = "1" ] || printf 'es')"
if [ "`$count" != "1" ]; then
    printf 'Expected exactly one North Shore runner for the bot token.\n'
    exit 2
fi
"@

& wsl.exe -d $Distro --user $LinuxUser -- bash -lc $BashCommand
exit $LASTEXITCODE
