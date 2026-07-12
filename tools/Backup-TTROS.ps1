# Native Windows backup is retired. Revisit: when Linux backup contract changes. Last touched: 2026-07-11.
$ErrorActionPreference = "Stop"
if (-not $env:AOS_BACKUP_ROOT) { throw "Set AOS_BACKUP_ROOT to a Linux-native path before backup." }
$backupRoot = $env:AOS_BACKUP_ROOT.Replace("'", "'\"'\"'")
wsl.exe -d AgenticOSClean --user liam -- bash -lc "export AOS_ROOT=/home/liam/agentic-os-live; export AOS_BACKUP_ROOT='$backupRoot'; cd \"`$AOS_ROOT\"; exec bash tools/aos-linux-backup.sh"
exit $LASTEXITCODE
