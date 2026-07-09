<#
TTROS WP7 scheduled backup registration helper.

This script does not run automatically. Liam/operator runs it explicitly from
Windows PowerShell after validating a real backup:

  cd "C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live"
  powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Register-TTROS-BackupTask.ps1

Default schedule: daily at 18:00 local time.
Task name: TTROS Automated Backup
#>
[CmdletBinding()]
param(
    [string]$At = "18:00"
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backupScript = Join-Path $workspaceRoot "tools\Backup-TTROS.ps1"
$taskName = "TTROS Automated Backup"

if (-not (Test-Path -LiteralPath $backupScript)) {
    throw "Backup script not found: $backupScript"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument ("-NoProfile -ExecutionPolicy Bypass -File `"{0}`"" -f $backupScript) -WorkingDirectory $workspaceRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 6)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Daily TTROS copy-only backup to D:\TTROS_Backups." -Force | Out-Null

Write-Host "Registered or updated scheduled task: $taskName"
Write-Host "Backup script: $backupScript"
Write-Host "Schedule: daily at $At local time"
Write-Host ""
Write-Host "Operator command:"
Write-Host 'cd "C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live"'
Write-Host 'powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Register-TTROS-BackupTask.ps1'
