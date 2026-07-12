# Native Windows backend cleanup is retired. Revisit: when Linux distro/root changes. Last touched: 2026-07-11.
function Stop-StaleAgenticOSBackend {
    param([int]$Port = 8010)
    wsl.exe -d AgenticOSClean --user liam -- bash -lc 'export AOS_ROOT=/home/liam/agentic-os-live; cd "$AOS_ROOT"; exec bash tools/aos-linux-runtime.sh stop'
    return $LASTEXITCODE
}
