#!/usr/bin/env bash
# Revisit: when backend/frontend ports or the existing runner contract changes. · Last touched: 2026-07-11.
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
BACKEND_URL="http://127.0.0.1:8010/api/health"
FRONTEND_URL="http://127.0.0.1:3010/"
RUNNER_INTERVAL="${AOS_RUNNER_INTERVAL_SECONDS:-5}"

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

start() {
  authority_check
  if ps -eo args= | grep -F '/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live' | grep -Ev 'grep|rg|codex|aos-linux-runtime\.sh' >/dev/null; then
    echo "old Windows-mounted Agentic OS process detected; refusing dual runtime" >&2
    exit 1
  fi
  mkdir -p "$RUNTIME_DIR"
  "$PYTHON" -c 'import fastapi, uvicorn, jsonschema' >/dev/null
  command -v npm >/dev/null

  if ! pid_alive "$BACKEND_PID"; then
    (
      cd "$ROOT/dashboard"
      exec "$PYTHON" -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 --log-level info
    ) >>"${RUNTIME_DIR}/backend.log" 2>&1 &
    echo "$!" >"$BACKEND_PID"
  fi

  if ! pid_alive "$FRONTEND_PID"; then
    (
      cd "$ROOT/dashboard/frontend"
      exec npm run dev
    ) >>"${RUNTIME_DIR}/frontend.log" 2>&1 &
    echo "$!" >"$FRONTEND_PID"
  fi

  if ! pid_alive "$RUNNER_PID"; then
    (
      cd "$ROOT"
      exec "$PYTHON" "$ROOT/tools/aos-orchestration-runner.py" --root "$ROOT" \
        --skip-telegram-escalation --watch --interval "$RUNNER_INTERVAL"
    ) >>"${RUNTIME_DIR}/runner.log" 2>&1 &
    echo "$!" >"$RUNNER_PID"
  fi

  if ! wait_http "$BACKEND_URL" backend; then
    stop
    return 1
  fi
  if ! wait_http "$FRONTEND_URL" frontend; then
    stop
    return 1
  fi
  status
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

status() {
  local result=0
  status_one backend "$BACKEND_PID" || result=1
  status_one frontend "$FRONTEND_PID" || result=1
  status_one runner "$RUNNER_PID" || result=1
  curl --noproxy '*' -fsS --max-time 2 "$BACKEND_URL" >/dev/null 2>&1 && echo "backend_ready=yes" || { echo "backend_ready=no"; result=1; }
  curl --noproxy '*' -fsS --max-time 2 "$FRONTEND_URL" >/dev/null 2>&1 && echo "frontend_ready=yes" || { echo "frontend_ready=no"; result=1; }
  return "$result"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop || true; start ;;
  status) status ;;
  *) echo "Usage: $0 {start|stop|restart|status}" >&2; exit 2 ;;
esac
