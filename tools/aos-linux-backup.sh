#!/usr/bin/env bash
# Revisit: when authoritative state paths or backup exclusions change. · Last touched: 2026-07-31.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${AOS_ROOT:-$(cd -- "${SCRIPT_DIR}/.." && pwd)}"
BACKUP_ROOT="${AOS_BACKUP_ROOT:?Set AOS_BACKUP_ROOT to a Linux-native backup directory}"
export AOS_ROOT="$ROOT"
RECEIPT_PATH="${ROOT}/queue/receipts/linux-backups.jsonl"
started_epoch="$(date +%s)"
destination=""
completed=0

write_receipt() {
  local status="$1" error_text="${2:-}" files_copied="${3:-0}" bytes_copied="${4:-0}"
  python3 - "$RECEIPT_PATH" "$status" "$BACKUP_ROOT" "$destination" "$ROOT" \
    "$started_epoch" "$files_copied" "$bytes_copied" "$error_text" <<'PY'
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

path, status, target, snapshot, source, started, files, size, error = sys.argv[1:]
path = Path(path)
path.parent.mkdir(parents=True, exist_ok=True)
record = {
    "ts": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    "status": status,
    "authority": "linux",
    "target": target,
    "snapshot_path": snapshot or None,
    "sources": [{"name": "AgenticOSClean", "path": source}],
    "files_copied": int(files),
    "bytes_copied": int(size),
    "duration_s": round(max(0.0, time.time() - int(started)), 3),
    "dry_run": False,
    "errors": [error] if error else [],
    "warnings": [],
    "exclusions": [
        ".git", ".venv*", "node_modules", "dist", ".vite", "__pycache__",
        "*.py[co]", "queue/locks/*.lock", "*.tmp", "*.candidate*", ".env*",
        "workspaces/north_shore_sales_coach", "connectors/telegram_bridge",
    ],
    "readable_proof": status == "success",
    "token_usage_text": "Token usage: no agent invocation",
}
raw = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
try:
    os.fchmod(fd, 0o600)
    os.write(fd, raw)
    os.fsync(fd)
finally:
    os.close(fd)
PY
}

on_exit() {
  local rc=$?
  if ((rc != 0 && completed == 0)); then
    write_receipt fail "Linux backup command failed" || true
  fi
  exit "$rc"
}
trap on_exit EXIT

PYTHONPATH="${ROOT}/tools${PYTHONPATH:+:${PYTHONPATH}}" python3 -c \
  'from aos_paths import assert_authoritative_root; import os; assert_authoritative_root(os.environ["AOS_ROOT"]); assert_authoritative_root(os.environ["AOS_BACKUP_ROOT"])'
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="${BACKUP_ROOT%/}/agentic-os-${stamp}"
mkdir -p "$destination"
rsync -a --exclude='.git/' --exclude='.venv*/' --exclude='node_modules/' --exclude='dist/' \
  --exclude='.vite/' --exclude='__pycache__/' --exclude='*.py[co]' --exclude='queue/locks/*.lock' \
  --exclude='*.tmp' --exclude='*.candidate*' --exclude='**/.env' --exclude='**/.env.*' \
  --exclude='workspaces/north_shore_sales_coach/' --exclude='connectors/telegram_bridge/' \
  "$ROOT/" "$destination/"
[[ -r "$destination/AGENTS.md" && -r "$destination/CODEX.md" && -r "$destination/tools/aos-linux-backup.sh" ]]
[[ ! -e "$destination/.env" && ! -e "$destination/workspaces/north_shore_sales_coach" && ! -e "$destination/connectors/telegram_bridge" ]]
files_copied="$(find "$destination" -type f -printf '.' | wc -c)"
bytes_copied="$(du -sb "$destination" | awk '{print $1}')"
write_receipt success "" "$files_copied" "$bytes_copied"
completed=1
trap - EXIT
printf 'backup=%s\n' "$destination"
