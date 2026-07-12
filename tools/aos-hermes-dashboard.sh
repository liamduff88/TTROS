#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$HOME/.composio:$PATH"

HOST="${HERMES_DASHBOARD_HOST:-127.0.0.1}"
PORT="${HERMES_DASHBOARD_PORT:-8081}"
URL="http://${HOST}:${PORT}/"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${AOS_ROOT:-$(cd -- "${SCRIPT_DIR}/.." && pwd)}"
export AOS_ROOT="$WORKSPACE"
LOG_DIR="${WORKSPACE}/logs"
LOG_FILE="${LOG_DIR}/hermes_dashboard_${PORT}.log"
RUNTIME_DIR="${LOG_DIR}/runtime"
PID_FILE="${RUNTIME_DIR}/hermes_dashboard_${PORT}.pid"
HERMES_AGENT_ROOT="${HERMES_AGENT_ROOT:-${HOME}/.hermes/hermes-agent}"
WEB_DIST="${RUNTIME_DIR}/hermes-web-dist"
BUILD_LOG="${RUNTIME_DIR}/hermes-web-build.log"

usage() {
  echo "Usage: $0 {start|status|command}"
}

reachable() {
  curl -fsS --max-time 2 "$URL" >/dev/null 2>&1
}

supports_dashboard() {
  command -v hermes >/dev/null 2>&1 && hermes dashboard --help >/dev/null 2>&1
}

dashboard_pid() {
  local pid cwd command
  [[ -f "$PID_FILE" ]] || return 1
  pid="$(<"$PID_FILE")"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  cwd="$(readlink -f "/proc/${pid}/cwd" 2>/dev/null || true)"
  command="$(tr '\0' ' ' <"/proc/${pid}/cmdline" 2>/dev/null || true)"
  [[ "$cwd" == "$WORKSPACE" && "$command" == *"hermes"* && "$command" == *"dashboard"* ]] || return 1
  printf '%s\n' "$pid"
}

web_dist_stale() {
  [[ -f "${WEB_DIST}/index.html" ]] || return 0
  [[ "${HERMES_AGENT_ROOT}/package-lock.json" -nt "${WEB_DIST}/index.html" ]] && return 0
  find "${HERMES_AGENT_ROOT}/web" -type f \
    \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx' -o -name '*.css' -o -name '*.html' -o -name 'package.json' \) \
    -newer "${WEB_DIST}/index.html" -print -quit | grep -q .
}

ensure_web_dist() {
  web_dist_stale || return 0
  local vite config hash build_root
  vite="${HERMES_AGENT_ROOT}/node_modules/.bin/vite"
  config="${HERMES_AGENT_ROOT}/web/vite.config.ts"
  if [[ ! -x "$vite" || ! -f "$config" || ! -d "${HERMES_AGENT_ROOT}/node_modules" ]]; then
    echo "Current Hermes web dependencies are incomplete under ${HERMES_AGENT_ROOT}." >&2
    echo "Repair that install with: cd '${HERMES_AGENT_ROOT}' && npm install --workspace web" >&2
    return 1
  fi
  (
    cd "$HERMES_AGENT_ROOT"
    npm run typecheck --workspace web
  )
  hash="$(sha256sum "${HERMES_AGENT_ROOT}/package-lock.json" "$config" | sha256sum | cut -c1-16)"
  build_root="${RUNTIME_DIR}/hermes-web-build-${hash}"
  mkdir -p "${build_root}/web" "${build_root}/node_modules"
  if [[ ! -f "${build_root}/web/vite.config.ts" ]]; then
    cp "$config" "${build_root}/web/vite.config.ts"
  fi
  if [[ ! -e "${build_root}/apps" ]]; then
    ln -s "${HERMES_AGENT_ROOT}/apps" "${build_root}/apps"
  fi
  if [[ ! -e "${build_root}/web/src" ]]; then
    ln -s "${HERMES_AGENT_ROOT}/web/src" "${build_root}/web/src"
  fi
  if [[ ! -e "${build_root}/node_modules/vite" ]]; then
    cp -as "${HERMES_AGENT_ROOT}/node_modules/." "${build_root}/node_modules/"
  fi
  "$vite" build "${HERMES_AGENT_ROOT}/web" \
    --config "${build_root}/web/vite.config.ts" \
    --outDir "$WEB_DIST" --emptyOutDir
  [[ -f "${WEB_DIST}/index.html" ]]
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
    pid="$(dashboard_pid 2>/dev/null || true)"
    if reachable; then
      echo "state=reachable"
    elif [[ -n "$pid" ]]; then
      echo "state=starting"
    else
      echo "state=installed_stopped"
    fi
    echo "version=$version"
    echo "url=$URL"
    echo "root=$WORKSPACE"
    echo "dist=$WEB_DIST"
    if [[ -n "$pid" ]]; then
      echo "pid=$pid"
    fi
    ;;
  start)
    cd "$WORKSPACE"
    mkdir -p "$RUNTIME_DIR"
    if ! supports_dashboard; then
      echo "state=unsupported"
      echo "reason=hermes dashboard command is unavailable"
      echo "url=$URL"
      exit 0
    fi
    if reachable; then
      echo "state=reachable"
      echo "url=$URL"
      echo "root=$WORKSPACE"
      if pid="$(dashboard_pid 2>/dev/null)"; then
        echo "pid=$pid"
      fi
      exit 0
    fi
    if pid="$(dashboard_pid 2>/dev/null)"; then
      echo "state=starting"
      echo "pid=$pid"
      echo "url=$URL"
      echo "root=$WORKSPACE"
      echo "log=$LOG_FILE"
      exit 0
    fi
    rm -f "$PID_FILE"
    if ! ensure_web_dist >"$BUILD_LOG" 2>&1; then
      echo "state=failed"
      echo "reason=current Hermes web workspace failed typecheck/build preparation"
      echo "url=$URL"
      echo "root=$WORKSPACE"
      echo "build_log=$BUILD_LOG"
      exit 0
    fi
    nohup env HERMES_WEB_DIST="$WEB_DIST" hermes dashboard --host "$HOST" --port "$PORT" --no-open --skip-build >"$LOG_FILE" 2>&1 &
    launcher_pid="$!"
    printf '%s\n' "$launcher_pid" >"$PID_FILE"
    for _ in {1..60}; do
      if reachable; then
        echo "state=reachable"
        echo "pid=$launcher_pid"
        echo "url=$URL"
        echo "root=$WORKSPACE"
        echo "dist=$WEB_DIST"
        echo "log=$LOG_FILE"
        exit 0
      fi
      if ! kill -0 "$launcher_pid" >/dev/null 2>&1; then
        rm -f "$PID_FILE"
        echo "state=failed"
        echo "reason=hermes dashboard process exited before ${URL} became reachable"
        echo "url=$URL"
        echo "root=$WORKSPACE"
        echo "log=$LOG_FILE"
        exit 0
      fi
      sleep 0.25
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
    echo "root=$WORKSPACE"
    echo "dist=$WEB_DIST"
    echo "log=$LOG_FILE"
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
