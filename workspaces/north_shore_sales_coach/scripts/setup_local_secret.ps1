[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$RuntimeDirectory = Join-Path (Split-Path -Parent $PSScriptRoot) '.runtime'
$SecretFile = Join-Path $RuntimeDirectory 'north_shore_bot.env'
$SecureToken = Read-Host 'Enter the North Shore Telegram bot token' -AsSecureString
$SheetsWebAppUrl = Read-Host 'Enter the North Shore Apps Script Web App URL (optional)'
$SecureSheetsSecret = Read-Host 'Enter the North Shore Apps Script shared secret (optional)' -AsSecureString
$TokenPointer = [IntPtr]::Zero
$SheetsSecretPointer = [IntPtr]::Zero

function ConvertTo-ShellEnvValue {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + ($Value -replace "'", "'\''") + "'"
}

try {
    $TokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureToken)
    $Token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($TokenPointer)
    $SheetsSecretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureSheetsSecret)
    $SheetsSecret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($SheetsSecretPointer)

    if ([string]::IsNullOrWhiteSpace($Token)) {
        throw 'No token was entered. The local secret file was not changed.'
    }
    if ($Token -notmatch '^[0-9]+:[A-Za-z0-9_-]+$') {
        throw 'The token format is invalid. The local secret file was not changed.'
    }

    [IO.Directory]::CreateDirectory($RuntimeDirectory) | Out-Null
    $Lines = [Collections.Generic.List[string]]::new()
    $Lines.Add("NORTH_SHORE_TELEGRAM_BOT_TOKEN=$(ConvertTo-ShellEnvValue $Token)")
    if (-not [string]::IsNullOrWhiteSpace($SheetsWebAppUrl) -or -not [string]::IsNullOrWhiteSpace($SheetsSecret)) {
        if ([string]::IsNullOrWhiteSpace($SheetsWebAppUrl)) {
            throw 'A Sheets shared secret was entered without a Web App URL. The local secret file was not changed.'
        }
        if ($SheetsWebAppUrl -notmatch '^https://') {
            throw 'The Sheets Web App URL must start with https://. The local secret file was not changed.'
        }
        if ([string]::IsNullOrWhiteSpace($SheetsSecret)) {
            throw 'A Sheets Web App URL was entered without a shared secret. The local secret file was not changed.'
        }
        $Lines.Add('NORTH_SHORE_SHEETS_PROVIDER=apps_script_webapp')
        $Lines.Add("NORTH_SHORE_SHEETS_WEBAPP_URL=$(ConvertTo-ShellEnvValue $SheetsWebAppUrl)")
        $Lines.Add("NORTH_SHORE_SHEETS_WEBAPP_SECRET=$(ConvertTo-ShellEnvValue $SheetsSecret)")
        $Lines.Add('NORTH_SHORE_SHEETS_EXECUTION_ENABLED=true')
        $Lines.Add('NORTH_SHORE_SHEETS_WRITES_ENABLED=true')
        $Lines.Add('NORTH_SHORE_SHEETS_READS_ENABLED=false')
    }
    $Utf8WithoutBom = [Text.UTF8Encoding]::new($false)
    [IO.File]::WriteAllText(
        $SecretFile,
        (($Lines -join "`n") + "`n"),
        $Utf8WithoutBom
    )
    Write-Host 'North Shore local secrets saved to the gitignored secret file.'
    Write-Host "Sheets configured: $(-not [string]::IsNullOrWhiteSpace($SheetsWebAppUrl))"
}
finally {
    if ($TokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($TokenPointer)
    }
    if ($SheetsSecretPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($SheetsSecretPointer)
    }
    $Token = $null
    $SheetsSecret = $null
}
