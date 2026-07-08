$ErrorActionPreference = "SilentlyContinue"

$workspace = $PSScriptRoot
$env:AOS_ROOT = $workspace
$dashboard = Join-Path $workspace "dashboard"
$backend = Join-Path $dashboard "backend"
$venvDir = Join-Path $backend ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirements = Join-Path $backend "requirements.txt"
$logsDir = Join-Path $workspace "logs"
$stdoutLog = Join-Path $logsDir "backend-auto-stdout.log"
$stderrLog = Join-Path $logsDir "backend-auto-stderr.log"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

. (Join-Path $workspace "Stop-StaleAgenticOSBackend.ps1")

# Preflight: stop any prior Agentic OS backend (stale/orphaned or a normal
# earlier instance) so this run always ends up serving current code from a
# single fresh process, never a leftover worker on 8010.
Stop-StaleAgenticOSBackend -Port 8010 | Out-Null

# If port 8010 is still held after cleanup, it's something we found no
# evidence for -- leave it alone and don't start a second listener on top.
$stillListening = Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue
if ($stillListening) {
  exit 0
}

if (-not (Test-Path $venvPython)) {
  py.exe -3 -m venv $venvDir
  if (($LASTEXITCODE -ne 0) -or (-not (Test-Path $venvPython))) {
    exit 1
  }
}

& $venvPython -c "import jsonschema" 2>$null
if ($LASTEXITCODE -ne 0) {
  & $venvPython -m pip install -r $requirements --quiet
  if ($LASTEXITCODE -ne 0) {
    exit 1
  }
  & $venvPython -c "import jsonschema" 2>$null
  if ($LASTEXITCODE -ne 0) {
    exit 1
  }
}

$proc = Start-Process -FilePath $venvPython `
  -WindowStyle Hidden `
  -WorkingDirectory $backend `
  -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8010", "--log-level", "info") `
  -RedirectStandardOutput $stdoutLog `
  -RedirectStandardError $stderrLog `
  -PassThru

Start-Sleep -Seconds 3

try {
  Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/queue/summary" -TimeoutSec 5 -ErrorAction Stop | Out-Null
}
catch {
  Write-Host "Backend auto launch failed: health check http://127.0.0.1:8010/api/queue/summary did not succeed."
  if ($proc -and $proc.HasExited) {
    Write-Host "Backend process exited with code $($proc.ExitCode)."
  }
  if (Test-Path $stderrLog) {
    Write-Host "Last backend stderr lines:"
    Get-Content -Path $stderrLog -Tail 40
  }
  exit 1
}
