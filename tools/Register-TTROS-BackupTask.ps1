# Revisit: when the Linux backup path, distro, or task name changes. Last touched: 2026-07-31.
[CmdletBinding()]
param(
    [string]$TaskName = "TTROS Automated Backup",
    [string]$Distro = "AgenticOSClean",
    [string]$LinuxUser = "liam",
    [string]$AosRoot = "/home/liam/agentic-os-live",
    [string]$BackupRoot = "/home/liam/agentic-os-backups"
)

$ErrorActionPreference = "Stop"

foreach ($path in @($AosRoot, $BackupRoot)) {
    if (-not $path.StartsWith("/") -or $path.StartsWith("/mnt/")) {
        throw "Backup paths must be Linux-native absolute paths: $path"
    }
}

# This activation repairs the existing daily task in place. It intentionally
# refuses to create a second scheduler entry when the expected task is absent.
Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop | Out-Null
$arguments = @(
    "-d", $Distro,
    "--user", $LinuxUser,
    "--exec", "env",
    "AOS_ROOT=$AosRoot",
    "AOS_BACKUP_ROOT=$BackupRoot",
    "bash", "$AosRoot/tools/aos-linux-backup.sh"
) -join " "
$action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument $arguments

Set-ScheduledTask -TaskName $TaskName -Action $action | Out-Null

$updated = Get-ScheduledTask -TaskName $TaskName
[pscustomobject]@{
    TaskName = $updated.TaskName
    Execute = $updated.Actions[0].Execute
    Arguments = $updated.Actions[0].Arguments
    Trigger = $updated.Triggers[0].StartBoundary
}
