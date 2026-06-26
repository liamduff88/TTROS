#!/usr/bin/env bash
set -euo pipefail

package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
secret_file="${NORTH_SHORE_SECRET_FILE:-$package_dir/.runtime/north_shore_bot.env}"
runner_pattern='python3[[:space:]]+-m[[:space:]]+src\.north_shore_bot_runner'

if command -v pgrep >/dev/null 2>&1 && pgrep -u "$(id -u)" -f "$runner_pattern" >/dev/null 2>&1; then
    printf '%s\n' \
        'North Shore bot runner is already active; refusing to start a second runner.' \
        'Stop the existing python3 -m src.north_shore_bot_runner process before starting another.' >&2
    exit 3
fi

if [[ -f "$secret_file" ]]; then
    set -a
    # This file is created locally by setup_local_secret.ps1 and is gitignored.
    # shellcheck disable=SC1090
    source "$secret_file"
    set +a
fi

if [[ -z "${NORTH_SHORE_TELEGRAM_BOT_TOKEN:-}" ]]; then
    printf '%s\n' \
        'North Shore bot token is not configured.' \
        'Run scripts/setup_local_secret.ps1 from PowerShell, then retry.' >&2
    exit 2
fi

printf 'North Shore launcher ready: token_length=%s' "${#NORTH_SHORE_TELEGRAM_BOT_TOKEN}"
if [[ -n "${NORTH_SHORE_SHEETS_PROVIDER:-}" ]]; then
    printf ', sheets_provider=%s' "$NORTH_SHORE_SHEETS_PROVIDER"
fi
webapp_url="${NORTH_SHORE_SHEETS_WEBAPP_URL:-}"
webapp_secret="${NORTH_SHORE_SHEETS_WEBAPP_SECRET:-}"
printf ', sheets_url_length=%s, sheets_secret_length=%s' \
    "${#webapp_url}" \
    "${#webapp_secret}"
printf ', sheets_execution_enabled=%s, sheets_writes_enabled=%s, sheets_reads_enabled=%s\n' \
    "${NORTH_SHORE_SHEETS_EXECUTION_ENABLED:-}" \
    "${NORTH_SHORE_SHEETS_WRITES_ENABLED:-}" \
    "${NORTH_SHORE_SHEETS_READS_ENABLED:-}"

cd "$package_dir"
exec python3 -m src.north_shore_bot_runner
