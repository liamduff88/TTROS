#!/usr/bin/env bash
# Revisit: when backend/frontend ports or the existing runner contract changes. · Last touched: 2026-07-19.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${AOS_ROOT:-$(cd -- "${SCRIPT_DIR}/.." && pwd)}"
if [[ -x "${ROOT}/dashboard/backend/.venv/bin/python" ]]; then
  DEFAULT_PYTHON="${ROOT}/dashboard/backend/.venv/bin/python"
else
  DEFAULT_PYTHON="python3"
fi
PYTHON="${AOS_PYTHON:-$DEFAULT_PYTHON}"
RUNTIME_DIR="${ROOT}/logs/runtime"
BACKEND_PID="${RUNTIME_DIR}/backend.pid"
FRONTEND_PID="${RUNTIME_DIR}/frontend.pid"
RUNNER_PID="${RUNTIME_DIR}/runner.pid"
RUNNER_SCRIPT="${ROOT}/tools/aos-orchestration-runner.py"
BACKEND_URL="http://127.0.0.1:8010/api/health"
FRONTEND_URL="http://127.0.0.1:3010/"
RUNNER_INTERVAL="${AOS_RUNNER_INTERVAL_SECONDS:-5}"

CAPTURE_SCRIPT="${ROOT}/tools/aos_capture_live.py"
CAPTURE_PYTHON="${AOS_CAPTURE_PYTHON:-/usr/bin/python3}"
CAPTURE_TIMEOUT_SECONDS=180

export AOS_ROOT="$ROOT"
export PYTHONDONTWRITEBYTECODE=1
export AOS_DISABLE_TELEMETRY="${AOS_DISABLE_TELEMETRY:-1}"
export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$HOME/.composio:$PATH"

authority_check() {
  "$PYTHON" -c 'from aos_paths import assert_authoritative_root; import os; assert_authoritative_root(os.environ["AOS_ROOT"])' \
    2>/dev/null || {
      PYTHONPATH="${ROOT}/tools${PYTHONPATH:+:${PYTHONPATH}}" "$PYTHON" -c \
        'from aos_paths import assert_authoritative_root; import os; assert_authoritative_root(os.environ["AOS_ROOT"])'
    }
}

pid_alive() {
  local pid_file="$1" pid
  [[ -f "$pid_file" ]] || return 1
  pid="$(<"$pid_file")"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  local cwd
  cwd="$(readlink -f "/proc/${pid}/cwd" 2>/dev/null || true)"
  [[ "$cwd" == "$ROOT" || "$cwd" == "$ROOT/"* ]] || \
    tr '\0' ' ' <"/proc/${pid}/cmdline" 2>/dev/null | grep -F -- "$ROOT" >/dev/null
}

wait_http() {
  local url="$1" label="$2"
  for _ in {1..60}; do
    if curl --noproxy '*' -fsS --max-time 1 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  echo "$label failed readiness: $url" >&2
  return 1
}

has_arg() {
  local expected="$1"
  shift
  local arg
  for arg in "$@"; do
    [[ "$arg" == "$expected" ]] && return 0
  done
  return 1
}

has_arg_pair() {
  local expected_key="$1" expected_value="$2"
  shift 2
  local previous="" arg
  for arg in "$@"; do
    if [[ "$previous" == "$expected_key" && "$arg" == "$expected_value" ]]; then
      return 0
    fi
    [[ "$arg" == "${expected_key}=${expected_value}" ]] && return 0
    previous="$arg"
  done
  return 1
}

is_protected_process() {
  local joined="${*,,}"
  [[ "$joined" == *north_shore_bot_runner* ||
     "$joined" == *'/workspaces/north_shore_sales_coach/'* ||
     "$joined" == *hermes* ]]
}

classify_desktop_process() {
  local cwd="$1"
  shift
  local -a args=("$@")
  local arg executable="${args[0]:-}"

  is_protected_process "${args[@]}" && return 1

  if has_arg "$RUNNER_SCRIPT" "${args[@]}" ||
     { [[ "$cwd" == "$ROOT" ]] && has_arg 'tools/aos-orchestration-runner.py' "${args[@]}"; }; then
    printf '%s\n' 'orchestration runner'
    return 0
  fi

  if has_arg 'backend.main:app' "${args[@]}" &&
     has_arg_pair '--port' '8010' "${args[@]}" &&
     [[ "$cwd" == "$ROOT" || "$cwd" == "$ROOT/"* || "$executable" == "$ROOT/dashboard/backend/"* ]] &&
     { [[ "${executable##*/}" == uvicorn ]] || has_arg_pair '-m' 'uvicorn' "${args[@]}"; }; then
    printf '%s\n' 'dashboard backend (uvicorn :8010)'
    return 0
  fi

  for arg in "${args[@]}"; do
    if [[ "$arg" == "$ROOT/dashboard/frontend/node_modules/"*'/vite/bin/vite.js' ||
          "$arg" == "$ROOT/dashboard/frontend/node_modules/.bin/vite" ]]; then
      if has_arg_pair '--port' '3010' "${args[@]}"; then
        printf '%s\n' 'dashboard frontend (vite :3010)'
        return 0
      fi
    fi
    if [[ "$arg" == "$ROOT/dashboard/frontend/node_modules/"*'/bin/esbuild' ]] &&
       has_arg '--ping' "${args[@]}"; then
      printf '%s\n' 'dashboard frontend (esbuild for vite :3010)'
      return 0
    fi
  done

  if [[ "$cwd" == "$ROOT/dashboard/frontend" ]]; then
    if [[ "${args[0]:-}" == 'npm run dev' || "${args[0]:-}" == 'npm run dev --strictPort' ]] ||
       { [[ "${args[0]##*/}" == npm ]] && [[ "${args[1]:-}" == run ]] && [[ "${args[2]:-}" == dev ]]; }; then
      printf '%s\n' 'dashboard frontend launcher (npm run dev)'
      return 0
    fi
    if [[ "${args[0]##*/}" == sh && "${args[1]:-}" == -c &&
          ( "${args[2]:-}" == 'vite --host 127.0.0.1 --port 3010' ||
            "${args[2]:-}" == 'vite --host 127.0.0.1 --port 3010 --strictPort' ) ]]; then
      printf '%s\n' 'dashboard frontend launcher (vite :3010 shell)'
      return 0
    fi
  fi
  return 1
}

canonical_runner_pid() {
  local proc pid cwd
  local -a args=() matches=()
  for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    [[ "$pid" != "$$" ]] || continue
    cwd="$(readlink -f "$proc/cwd" 2>/dev/null || true)"
    [[ "$cwd" == "$ROOT" ]] || continue
    mapfile -d '' -t args <"$proc/cmdline" 2>/dev/null || continue
    ((${#args[@]})) || continue
    is_protected_process "${args[@]}" && continue
    if { has_arg "$RUNNER_SCRIPT" "${args[@]}" || has_arg 'tools/aos-orchestration-runner.py' "${args[@]}"; } &&
       has_arg_pair '--root' "$ROOT" "${args[@]}" && has_arg '--watch' "${args[@]}"; then
      matches+=("$pid")
    fi
  done
  if ((${#matches[@]} == 1)); then
    printf '%s\n' "${matches[0]}"
    return 0
  fi
  if ((${#matches[@]} > 1)); then
    echo "multiple canonical orchestration runners detected; refusing ambiguous adoption" >&2
    return 2
  fi
  return 1
}

process_running() {
  local pid="$1" cmdline
  [[ -d "/proc/$pid" ]] || return 1
  cmdline="$(tr '\0' ' ' 2>/dev/null <"/proc/$pid/cmdline" || true)"
  [[ -n "$cmdline" ]]
}

process_start_time() {
  local pid="$1" stat
  IFS= read -r stat 2>/dev/null <"/proc/$pid/stat" || return 1
  stat="${stat##*) }"
  set -- $stat
  printf '%s\n' "${20:-}"
}

desktop_cleanup() {
  local proc pid cwd label priority start_time current_start_time index
  local -a args=() pids=() labels=() priorities=() start_times=() signaled=()

  for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    [[ "$pid" != "$$" ]] || continue
    cwd="$(readlink -f "$proc/cwd" 2>/dev/null || true)"
    mapfile -d '' -t args <"$proc/cmdline" 2>/dev/null || continue
    ((${#args[@]})) || continue
    if label="$(classify_desktop_process "$cwd" "${args[@]}")"; then
      start_time="$(process_start_time "$pid" 2>/dev/null || true)"
      [[ -n "$start_time" ]] || continue
      pids+=("$pid")
      labels+=("$label")
      case "$label" in
        *esbuild*) priority=10 ;;
        *'(vite :3010)'*) priority=20 ;;
        *shell*) priority=30 ;;
        *npm*) priority=40 ;;
        *) priority=50 ;;
      esac
      priorities+=("$priority")
      start_times+=("$start_time")
    fi
  done

  # Signal every snapshotted PID before waiting, so child processes are each
  # accounted for even when terminating their parent would also reap them.
  for priority in 10 20 30 40 50; do
    for index in "${!pids[@]}"; do
      [[ "${priorities[$index]}" == "$priority" ]] || continue
      pid="${pids[$index]}"
      current_start_time="$(process_start_time "$pid" 2>/dev/null || true)"
      if [[ "$current_start_time" == "${start_times[$index]}" ]] && kill -TERM "$pid" 2>/dev/null; then
        signaled[$index]=1
      elif [[ -z "$current_start_time" ]]; then
        # A related child/parent signal may already have reaped this member of
        # the snapshotted frontend tree; it was still removed by this cleanup.
        signaled[$index]=2
      else
        signaled[$index]=0
      fi
    done
  done

  for _ in {1..40}; do
    local any_running=0
    for index in "${!pids[@]}"; do
      [[ "${signaled[$index]}" == 1 ]] || continue
      process_running "${pids[$index]}" && any_running=1
    done
    ((any_running)) || break
    sleep 0.05
  done

  for index in "${!pids[@]}"; do
    [[ "${signaled[$index]}" == 1 ]] || continue
    pid="${pids[$index]}"
    process_running "$pid" && kill -KILL "$pid" 2>/dev/null || true
  done

  for index in "${!pids[@]}"; do
    [[ "${signaled[$index]}" != 0 ]] || continue
    pid="${pids[$index]}"
    if process_running "$pid"; then
      echo "cleanup failed pid=$pid process=${labels[$index]}" >&2
      return 1
    fi
    echo "cleanup killed pid=$pid process=${labels[$index]}"
  done

  rm -f "$BACKEND_PID" "$FRONTEND_PID" "$RUNNER_PID"
}

preflight() {
  if ps -eo args= | grep -F '/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live' | grep -Ev 'grep|rg|codex|aos-linux-runtime\.sh' >/dev/null; then
    echo "old Windows-mounted Agentic OS process detected; refusing dual runtime" >&2
    exit 1
  fi
  mkdir -p "$RUNTIME_DIR"
  "$PYTHON" -c 'import fastapi, uvicorn, jsonschema' >/dev/null
  command -v npm >/dev/null
}

start_backend() {
  if ! pid_alive "$BACKEND_PID"; then
    (
      cd "$ROOT/dashboard"
      [[ ! -e "/proc/$BASHPID/fd/9" ]] || exec 9>&-
      exec nohup setsid "$PYTHON" -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 --log-level info
    ) >>"${RUNTIME_DIR}/backend.log" 2>&1 </dev/null &
    echo "$!" >"$BACKEND_PID"
  fi
}

start_frontend() {
  if ! pid_alive "$FRONTEND_PID"; then
    (
      cd "$ROOT/dashboard/frontend"
      [[ ! -e "/proc/$BASHPID/fd/9" ]] || exec 9>&-
      exec nohup setsid npm run dev -- --strictPort
    ) >>"${RUNTIME_DIR}/frontend.log" 2>&1 </dev/null &
    echo "$!" >"$FRONTEND_PID"
  fi
}

start_runner() {
  local discovered rc
  if ! pid_alive "$RUNNER_PID"; then
    if discovered="$(canonical_runner_pid)"; then
      printf '%s\n' "$discovered" >"$RUNNER_PID"
      return 0
    else
      rc=$?
      ((rc != 2)) || return 1
    fi
    (
      cd "$ROOT"
      [[ ! -e "/proc/$BASHPID/fd/9" ]] || exec 9>&-
      exec nohup setsid "$PYTHON" "$RUNNER_SCRIPT" --root "$ROOT" \
        --skip-telegram-escalation --watch --interval "$RUNNER_INTERVAL"
    ) >>"${RUNTIME_DIR}/runner.log" 2>&1 </dev/null &
    echo "$!" >"$RUNNER_PID"
  fi
}

wait_dashboard() {
  if ! wait_http "$BACKEND_URL" backend; then
    stop
    return 1
  fi
  if ! wait_http "$FRONTEND_URL" frontend; then
    stop
    return 1
  fi
}

start() {
  authority_check
  preflight
  start_backend
  start_frontend
  start_runner
  wait_dashboard
  status
}

desktop_start() {
  authority_check
  mkdir -p "$RUNTIME_DIR"
  exec 9>"${RUNTIME_DIR}/dashboard-launch.lock"
  flock 9
  desktop_cleanup
  preflight
  start_backend
  start_frontend
  wait_dashboard
  pid_alive "$BACKEND_PID"
  pid_alive "$FRONTEND_PID"
  if pid_alive "$RUNNER_PID"; then
    echo "runner unexpectedly active after desktop cleanup" >&2
    return 1
  fi
  status_one backend "$BACKEND_PID"
  status_one frontend "$FRONTEND_PID"
  echo "runner=stopped root=$ROOT"
}

stop_one() {
  local name="$1" pid_file="$2" pid
  if ! pid_alive "$pid_file"; then
    rm -f "$pid_file"
    echo "$name=stopped"
    return
  fi
  pid="$(<"$pid_file")"
  kill "$pid"
  for _ in {1..40}; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.1
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL "$pid"
  fi
  rm -f "$pid_file"
  echo "$name=stopped"
}

stop() {
  authority_check
  stop_one runner "$RUNNER_PID"
  stop_one frontend "$FRONTEND_PID"
  stop_one backend "$BACKEND_PID"
}

status_one() {
  local name="$1" pid_file="$2"
  if pid_alive "$pid_file"; then
    echo "$name=running pid=$(<"$pid_file") root=$ROOT"
  else
    echo "$name=stopped root=$ROOT"
    return 1
  fi
}

status_runner() {
  local discovered rc
  if pid_alive "$RUNNER_PID"; then
    status_one runner "$RUNNER_PID"
    return
  fi
  if discovered="$(canonical_runner_pid)"; then
    echo "runner=running pid=$discovered root=$ROOT supervisor=external"
    return 0
  else
    rc=$?
    echo "runner=stopped root=$ROOT"
    ((rc != 2)) || echo "runner_health=duplicate" >&2
    return 1
  fi
}

status() {
  local result=0
  status_one backend "$BACKEND_PID" || result=1
  status_one frontend "$FRONTEND_PID" || result=1
  status_runner || result=1
  curl --noproxy '*' -fsS --max-time 2 "$BACKEND_URL" >/dev/null 2>&1 && echo "backend_ready=yes" || { echo "backend_ready=no"; result=1; }
  curl --noproxy '*' -fsS --max-time 2 "$FRONTEND_URL" >/dev/null 2>&1 && echo "frontend_ready=yes" || { echo "frontend_ready=no"; result=1; }
  return "$result"
}

# Phase 6B production commands. The poller enforces activation, kill-switch,
# metadata-only provider access, cursor durability, and its own non-overlap lock.
# Revisit: after the observation window or a scheduler contract change. · Last touched: 2026-07-16.
capture_poll() {
  authority_check
  exec "$CAPTURE_PYTHON" "$CAPTURE_SCRIPT" poll "$@"
}

capture_scheduled() {
  authority_check
  exec /usr/bin/timeout --signal=TERM "$CAPTURE_TIMEOUT_SECONDS" \
    "$CAPTURE_PYTHON" "$CAPTURE_SCRIPT" poll --scheduled "$@"
}

capture_status() {
  authority_check
  exec "$CAPTURE_PYTHON" "$CAPTURE_SCRIPT" status
}

case "${1:-}" in
  capture-poll) shift; capture_poll "$@" ;;
  capture-scheduled) shift; capture_scheduled "$@" ;;
  capture-status) capture_status ;;
  start) start ;;
  desktop-start) desktop_start ;;
  desktop-cleanup) desktop_cleanup ;;
  stop) stop ;;
  restart) stop || true; start ;;
  status) status ;;
  *) echo "Usage: $0 {start|desktop-start|desktop-cleanup|stop|restart|status}" >&2; exit 2 ;;
esac
