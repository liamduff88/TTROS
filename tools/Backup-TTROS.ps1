<#
TTROS WP7 local backup runner.

Default real run:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Backup-TTROS.ps1

Dry-run validation:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Backup-TTROS.ps1 -DryRun

Test target validation:
  powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Backup-TTROS.ps1 -DryRun -TargetRoot "C:\temp\TTROS_Backup_Test"

Safety:
  Copy-only dated snapshots. No /MIR, no /PURGE, no source deletion.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$TargetRoot = "D:\TTROS_Backups",
    [switch]$DryRun,
    [switch]$AllowUnexpectedTargetLabel
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

$started = Get-Date
$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$businessBrainRoot = Join-Path (Split-Path $workspaceRoot -Parent) "TTROS Business Brain"
$receiptPath = Join-Path $workspaceRoot "queue\receipts\backups.jsonl"
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$snapshotPath = Join-Path $TargetRoot $stamp
$logPath = Join-Path (Join-Path $workspaceRoot "queue\receipts") ("backup-$stamp.log")
$warnings = New-Object System.Collections.Generic.List[string]
$errors = New-Object System.Collections.Generic.List[string]
$filesCopied = $null
$bytesCopied = $null
$targetDrive = $null
$targetLabel = $null

function Write-BackupLog {
    param([string]$Message)
    $line = "{0} {1}" -f ((Get-Date).ToString("s")), $Message
    $dir = Split-Path $script:logPath -Parent
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Add-Content -LiteralPath $script:logPath -Value $line -Encoding UTF8
    Write-Host $Message
}

function ConvertTo-JsonLine {
    param([hashtable]$Record)
    return ($Record | ConvertTo-Json -Depth 8 -Compress)
}

function Write-BackupReceipt {
    param([string]$Status)
    $duration = [Math]::Round(((Get-Date) - $script:started).TotalSeconds, 2)
    $receipt = @{
        ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        status = $Status
        target = $script:TargetRoot
        target_drive = $script:targetDrive
        target_label = $script:targetLabel
        snapshot_path = $script:snapshotPath
        sources = @(
            @{ name = "AgenticOSLive"; path = $script:workspaceRoot },
            @{ name = "BusinessBrain"; path = $script:businessBrainRoot }
        )
        files_copied = $script:filesCopied
        bytes_copied = $script:bytesCopied
        duration_s = $duration
        log_path = $script:logPath
        dry_run = [bool]$script:DryRun
        errors = @($script:errors)
        warnings = @($script:warnings)
        token_usage_text = "Token usage: no agent invocation"
    }
    $dir = Split-Path $script:receiptPath -Parent
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Add-Content -LiteralPath $script:receiptPath -Value (ConvertTo-JsonLine $receipt) -Encoding UTF8
}

function Get-DriveLabel {
    param([string]$DriveLetter)
    try {
        if (Get-Command Get-Volume -ErrorAction SilentlyContinue) {
            $volume = Get-Volume -DriveLetter $DriveLetter.TrimEnd(":") -ErrorAction Stop
            return $volume.FileSystemLabel
        }
    } catch {}
    try {
        $disk = Get-WmiObject Win32_LogicalDisk -Filter ("DeviceID='{0}'" -f $DriveLetter.TrimEnd("\"))
        return $disk.VolumeName
    } catch {}
    return $null
}

function Invoke-SafeRobocopy {
    param(
        [string]$Source,
        [string]$Destination
    )
    $excludeDirs = @(".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", "dashboard\frontend\node_modules", "dashboard\backend\.venv")
    $excludeFiles = @(".env", ".env.*", "*secret*", "*secrets*", "*token*", "*tokens*", "*credential*", "*credentials*")
    $args = @(
        "`"$Source`"",
        "`"$Destination`"",
        "/E",
        "/COPY:DAT",
        "/DCOPY:DAT",
        "/R:1",
        "/W:1",
        "/NP",
        "/TEE",
        "/LOG+:`"$script:logPath`"",
        "/XD"
    ) + $excludeDirs + @("/XF") + $excludeFiles

    Write-BackupLog ("robocopy {0} {1}" -f $Source, $Destination)
    $process = Start-Process -FilePath "robocopy.exe" -ArgumentList $args -NoNewWindow -Wait -PassThru
    if ($process.ExitCode -ge 8) {
        throw "robocopy failed for $Source with exit code $($process.ExitCode)"
    }
    return $process.ExitCode
}

try {
    $targetRootFull = [System.IO.Path]::GetFullPath($TargetRoot)
    $TargetRoot = $targetRootFull.TrimEnd("\")
    $snapshotPath = Join-Path $TargetRoot $stamp
    $targetDrive = [System.IO.Path]::GetPathRoot($TargetRoot)
    if ([string]::IsNullOrWhiteSpace($targetDrive)) {
        throw "TargetRoot does not include a drive/root: $TargetRoot"
    }
    $targetDrive = $targetDrive.TrimEnd("\")
    $drivePath = $targetDrive + "\"
    $targetLabel = $null

    if (-not (Test-Path -LiteralPath $drivePath)) {
        throw "Target drive is absent or inaccessible: $targetDrive"
    }

    $driveLetter = $targetDrive.TrimEnd(":")
    $targetLabel = Get-DriveLabel $driveLetter
    if ([string]::IsNullOrWhiteSpace($targetLabel)) {
        $warnings.Add("Target volume label unavailable; continuing without label confirmation.") | Out-Null
    } elseif ($targetDrive -ieq "D:" -and $targetLabel -ne "My Passport" -and -not $AllowUnexpectedTargetLabel) {
        throw "D: volume label is '$targetLabel', expected 'My Passport'. Re-run with -AllowUnexpectedTargetLabel only if this is intentional."
    }

    if (-not (Test-Path -LiteralPath $workspaceRoot)) {
        throw "Agentic OS Live source missing: $workspaceRoot"
    }
    if (-not (Test-Path -LiteralPath $businessBrainRoot)) {
        throw "TTROS Business Brain source missing: $businessBrainRoot"
    }

    if ($DryRun -or $WhatIfPreference) {
        Write-BackupLog "DRY RUN: would create snapshot $snapshotPath"
        Write-BackupLog "DRY RUN: would copy $workspaceRoot to AgenticOSLive"
        Write-BackupLog "DRY RUN: would copy $businessBrainRoot to BusinessBrain"
        Write-BackupReceipt "success"
        exit 0
    }

    New-Item -ItemType Directory -Path $snapshotPath -Force | Out-Null
    $logPath = Join-Path $snapshotPath "backup.log"
    Write-BackupLog "Starting TTROS backup snapshot: $snapshotPath"

    $codes = @()
    $codes += Invoke-SafeRobocopy -Source $workspaceRoot -Destination (Join-Path $snapshotPath "AgenticOSLive")
    $codes += Invoke-SafeRobocopy -Source $businessBrainRoot -Destination (Join-Path $snapshotPath "BusinessBrain")
    $filesCopied = $null
    $bytesCopied = $null
    $warnings.Add(("robocopy exit codes: {0}" -f ($codes -join ", "))) | Out-Null
    Write-BackupReceipt "success"
    Write-BackupLog "Backup completed successfully."
    exit 0
} catch {
    $errors.Add($_.Exception.Message) | Out-Null
    Write-BackupLog ("FAIL: {0}" -f $_.Exception.Message)
    Write-BackupReceipt "fail"
    exit 1
}
