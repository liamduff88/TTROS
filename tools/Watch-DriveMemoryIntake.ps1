# Revisit: when DriveFS mount or the WSL staging contract changes. Created 2026-09-23.
# Windows only reads DriveFS and copies stable bytes to AgenticOSClean.
param(
    [switch]$Ingest,
    [switch]$Once,
    [string]$FileName,
    [ValidateRange(5, 3600)][int]$PollSeconds = 20
)

$ErrorActionPreference = 'Stop'
$Inbox = 'G:\My Drive\TTROS Memory Intake\Inbox'
$WslRoot = '\\wsl.localhost\AgenticOSClean\home\liam\agentic-os-live'
$Staging = Join-Path $WslRoot 'queue\inbox\staging\drive'
$Helper = '/home/liam/agentic-os-live/tools/drive_memory_intake.py'
$Python = '/home/liam/agentic-os-live/.venv/bin/python'
$Supported = @('.md', '.txt', '.docx', '.pdf')
$Seen = @{}
$Completed = @{}
$Passes = 0

function Invoke-IntakeHelper([string]$Action, [string]$Digest, [string]$Suffix, [string]$Name) {
    $encodedName = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Name))
    $output = & wsl.exe -d AgenticOSClean -u liam -- $Python $Helper $Action --sha256 $Digest --suffix $Suffix --name-b64 $encodedName
    if ($LASTEXITCODE -ne 0) { throw "WSL intake helper failed: $output" }
    return ($output | Select-Object -Last 1 | ConvertFrom-Json)
}

if (-not (Test-Path -LiteralPath $Inbox -PathType Container)) {
    throw "DriveFS inbox unavailable: $Inbox"
}
if ($PSBoundParameters.ContainsKey('FileName') -and
    ([string]::IsNullOrWhiteSpace($FileName) -or $FileName -match '[\\/:]' -or $FileName -in @('.', '..'))) {
    throw '-FileName must be one exact filename in the Drive Memory Intake Inbox'
}

do {
    $Passes++
    if ($PSBoundParameters.ContainsKey('FileName')) {
        $selectedPath = Join-Path $Inbox $FileName
        $selectedFile = Get-ChildItem -LiteralPath $Inbox -File |
            Where-Object { $_.Name -ceq $FileName } |
            Select-Object -First 1
        if ($null -eq $selectedFile) {
            if (Test-Path -LiteralPath $selectedPath -PathType Leaf) {
                throw "Selected Drive Memory Intake file does not exist with exact name: $FileName"
            }
            throw "Selected Drive Memory Intake file does not exist: $FileName"
        }
        $candidates = @($selectedFile)
    } else {
        $candidates = Get-ChildItem -LiteralPath $Inbox -File
    }
    $candidates | ForEach-Object {
        $file = $_
        $suffix = $file.Extension.ToLowerInvariant()
        if ($Supported -notcontains $suffix -or $file.Name.StartsWith('.') -or $file.Name.StartsWith('~$') -or
            $file.Name -match '(?i)(~\$|\.tmp$|\.partial$|\.crdownload$)' -or
            ($file.Attributes -band [IO.FileAttributes]::ReparsePoint)) { return }
        $identity = "$($file.Length):$($file.LastWriteTimeUtc.Ticks)"
        if ($Completed[$file.FullName] -eq $identity) { return }
        if ($Seen[$file.FullName] -ne $identity) {
            $Seen[$file.FullName] = $identity
            return
        }
        try {
            $fresh = Get-Item -LiteralPath $file.FullName
            if ($fresh.Length -ne $file.Length -or $fresh.LastWriteTimeUtc.Ticks -ne $file.LastWriteTimeUtc.Ticks) { return }
            $digest = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            $check = Invoke-IntakeHelper 'check' $digest $suffix $file.Name
            if ($check.status -eq 'reconciled') {
                Write-Output "Reconciled $($file.Name) sha256:$digest"
                $Completed[$file.FullName] = $identity
                return
            }
            if (-not $Ingest) {
                Write-Output "Eligible $($file.Name) sha256:$digest (reconciliation only)"
                $Completed[$file.FullName] = $identity
                return
            }
            $folder = Join-Path $Staging $digest
            New-Item -ItemType Directory -Path $folder -Force | Out-Null
            $target = Join-Path $folder "source$suffix"
            if (-not (Test-Path -LiteralPath $target)) {
                $temporary = Join-Path $folder ("source$suffix." + [guid]::NewGuid().ToString('N') + '.partial')
                try {
                    Copy-Item -LiteralPath $file.FullName -Destination $temporary
                    if ((Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant() -ne $digest) {
                        throw 'staged copy SHA-256 mismatch'
                    }
                    Move-Item -LiteralPath $temporary -Destination $target
                } finally {
                    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
                }
            }
            $result = Invoke-IntakeHelper 'ingest' $digest $suffix $file.Name
            Write-Output "$($result.status) $($file.Name) sha256:$digest"
            $Completed[$file.FullName] = $identity
        } catch {
            Write-Warning "Drive intake retry pending for $($file.Name): $($_.Exception.Message)"
        }
    }
    if (-not $Once -or $Passes -lt 2) { Start-Sleep -Seconds $PollSeconds }
} while (-not $Once -or $Passes -lt 2)
