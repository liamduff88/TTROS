# Dot-source this file to get Stop-StaleAgenticOSBackend.
# Only stops processes with clear evidence of being this workspace's
# uvicorn backend (python/py + "uvicorn" + "backend.main:app" or
# "main:app" + the target port on the command line). Anything else listening on the port is left
# alone, even if it is the only thing reported by the TCP table.

function Stop-StaleAgenticOSBackend {
  param([int]$Port = 8010)

  $stopped = 0
  $portPattern = "--port\s+$Port\b"
  $appPattern = '(^|\s)(backend\.)?main:app(\s|$)'

  $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  $ownerPids = $conns | Select-Object -ExpandProperty OwningProcess -Unique

  foreach ($ownerPid in $ownerPids) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue

    if ($proc) {
      $isPython = $proc.Name -match '^(python|pythonw|py)\.exe$'
      $isThisBackend = $proc.CommandLine -and
        $proc.CommandLine -match 'uvicorn' -and
        $proc.CommandLine -match $appPattern -and
        $proc.CommandLine -match $portPattern

      if ($isPython -and $isThisBackend) {
        Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
        $stopped++
      }
      # No match -> leave the process alone; we don't have evidence it's ours.
    }
    else {
      # PID from the TCP table could not be enumerated directly (already
      # exited, or a child spawned by a cmd.exe wrapper that owns the
      # listening socket). Fall back to searching all python workers for
      # command-line evidence instead of touching the reported PID blind.
      $candidates = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
          $_.Name -match '^(python|pythonw|py)\.exe$' -and
          $_.CommandLine -match 'uvicorn' -and
          $_.CommandLine -match $appPattern -and
          $_.CommandLine -match $portPattern
        }
      foreach ($candidate in $candidates) {
        Stop-Process -Id $candidate.ProcessId -Force -ErrorAction SilentlyContinue
        $stopped++
      }
    }
  }

  if ($stopped -gt 0) {
    Start-Sleep -Milliseconds 500
  }

  return $stopped
}
