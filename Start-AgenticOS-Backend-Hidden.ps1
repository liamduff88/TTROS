# Thin Windows-to-Linux adapter. Revisit: when Linux distro/root changes. Last touched: 2026-07-11.
$ErrorActionPreference = "Stop"
wsl.exe -d AgenticOSClean --user liam -- bash -lc 'export AOS_ROOT=/home/liam/agentic-os-live; cd "$AOS_ROOT"; exec bash tools/aos-linux-runtime.sh start'
exit $LASTEXITCODE
