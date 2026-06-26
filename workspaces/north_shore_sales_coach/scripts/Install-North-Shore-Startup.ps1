[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$StartupName = 'North Shore Sales Coach Bot.lnk'
$PackageDirectory = Split-Path -Parent $PSScriptRoot
$HiddenLauncher = Join-Path $PSScriptRoot 'Start-North-Shore-Sales-Coach-Bot-Hidden.vbs'
$StartupDirectory = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $StartupDirectory $StartupName

if (-not (Test-Path -LiteralPath $HiddenLauncher -PathType Leaf)) {
    throw "North Shore hidden startup launcher was not found: $HiddenLauncher"
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = 'wscript.exe'
$Shortcut.Arguments = "//B //Nologo `"$HiddenLauncher`""
$Shortcut.WorkingDirectory = $PackageDirectory
$Shortcut.WindowStyle = 7
$Shortcut.Description = 'Starts the package-local North Shore Sales Coach Telegram bot runner through WSL AgenticOSClean.'
$Shortcut.Save()

Write-Host "Installed hidden North Shore startup shortcut: $ShortcutPath"
Write-Host 'It is separate from any Agentic OS Telegram startup entry.'
