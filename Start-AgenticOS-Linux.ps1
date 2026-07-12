# Revisit: when the canonical Linux distro/root or dashboard URL changes. Last touched: 2026-07-11.
$ErrorActionPreference = "Stop"
wsl.exe -d AgenticOSClean --user liam -- bash -lc 'export AOS_ROOT=/home/liam/agentic-os-live; cd "$AOS_ROOT"; exec bash tools/aos-linux-runtime.sh start'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Start-Process "http://127.0.0.1:3010"
