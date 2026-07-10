#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$HOME/.composio:$PATH"

HOST="${HERMES_DASHBOARD_HOST:-127.0.0.1}"
PORT="${HERMES_DASHBOARD_PORT:-8081}"
URL="http://${HOST}:${PORT}/"
WORKSPACE="/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live"
LOG_DIR="${WORKSPACE}/logs"
LOG_FILE="${LOG_DIR}/hermes_dashboard_${PORT}.log"

usage() {
  echo "Usage: $0 {start|status|command}"
}

reachable() {
  curl -fsS --max-time 2 "$URL" >/dev/null 2>&1
}

supports_dashboard() {
  command -v hermes >/dev/null 2>&1 && hermes dashboard --help >/dev/null 2>&1
}

case "${1:-}" in
  command)
    echo "cd '$WORKSPACE' && HERMES_DASHBOARD_HOST='$HOST' HERMES_DASHBOARD_PORT='$PORT' $0 start"
    ;;
  status)
    if ! command -v hermes >/dev/null 2>&1; then
      echo "state=unsupported"
      echo "reason=hermes not found on PATH"
      echo "url=$URL"
      exit 0
    fi
    version="$(hermes --version 2>/dev/null | head -n 1 || true)"
    if ! supports_dashboard; then
      echo "state=unsupported"
      echo "reason=hermes dashboard command is unavailable"
      echo "version=$version"
      echo "url=$URL"
      exit 0
    fi
    if reachable; then
      echo "state=reachable"
    else
      echo "state=installed_stopped"
    fi
    echo "version=$version"
    echo "url=$URL"
    ;;
  start)
    cd "$WORKSPACE"
    mkdir -p "$LOG_DIR"
    if ! supports_dashboard; then
      echo "state=unsupported"
      echo "reason=hermes dashboard command is unavailable"
      echo "url=$URL"
      exit 0
    fi
    if reachable; then
      echo "state=reachable"
      echo "url=$URL"
      exit 0
    fi
    nohup hermes dashboard --host "$HOST" --port "$PORT" --no-open >"$LOG_FILE" 2>&1 &
    launcher_pid="$!"
    for _ in {1..20}; do
      if reachable; then
        echo "state=reachable"
        echo "pid=$launcher_pid"
        echo "url=$URL"
        echo "log=$LOG_FILE"
        exit 0
      fi
      if ! kill -0 "$launcher_pid" >/dev/null 2>&1; then
        echo "state=failed"
        echo "reason=hermes dashboard process exited before ${URL} became reachable"
        echo "url=$URL"
        echo "log=$LOG_FILE"
        exit 0
      fi
      sleep 0.5
    done
    if grep -qi "could not bind" "$LOG_FILE" 2>/dev/null; then
      echo "state=failed"
      echo "reason=hermes dashboard could not bind ${HOST}:${PORT}"
      echo "url=$URL"
      echo "log=$LOG_FILE"
      exit 0
    fi
    echo "state=starting"
    echo "pid=$launcher_pid"
    echo "url=$URL"
    echo "log=$LOG_FILE"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
