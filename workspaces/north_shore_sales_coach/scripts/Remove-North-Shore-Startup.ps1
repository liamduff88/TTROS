[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$StartupName = 'North Shore Sales Coach Bot.lnk'
$StartupDirectory = [Environment]::GetFolderPath('Startup')
$ShortcutPath = Join-Path $StartupDirectory $StartupName

if (Test-Path -LiteralPath $ShortcutPath -PathType Leaf) {
    Remove-Item -LiteralPath $ShortcutPath -Force
    Write-Host "Removed hidden North Shore startup shortcut: $ShortcutPath"
}
else {
    Write-Host "Hidden North Shore startup shortcut was not installed: $ShortcutPath"
}
