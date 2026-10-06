#!/usr/bin/env bash
# Revisit: when authoritative state paths, backup exclusions, the external drive or retention change. · Last touched: 2026-10-06.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${AOS_ROOT:-$(cd -- "${SCRIPT_DIR}/.." && pwd)}"
BACKUP_ROOT="${AOS_BACKUP_ROOT:?Set AOS_BACKUP_ROOT to a Linux-native backup directory}"
# Off-machine copy on the My Passport drive. The directory must already exist: it lives on the drive,
# so an unplugged drive fails the run instead of writing the "external" copy onto the Linux disk.
EXTERNAL_ROOT="${AOS_EXTERNAL_BACKUP_ROOT:?Set AOS_EXTERNAL_BACKUP_ROOT to the external-drive backup directory}"
BRAIN_ROOT="${AOS_BRAIN_ROOT:?Set AOS_BRAIN_ROOT to the Business Brain vault}"
KEEP_LOCAL=7
export AOS_ROOT="$ROOT"
RECEIPT_PATH="${ROOT}/queue/receipts/linux-backups.jsonl"
started_epoch="$(date +%s)"
destination=""
external=""
pruned=0
failure="Linux backup command failed"
completed=0

write_receipt() {
  local status="$1" error_text="${2:-}" files_copied="${3:-0}" bytes_copied="${4:-0}"
  python3 - "$RECEIPT_PATH" "$status" "$BACKUP_ROOT" "$destination" "$ROOT" \
    "$started_epoch" "$files_copied" "$bytes_copied" "$error_text" \
    "$EXTERNAL_ROOT" "$external" "$BRAIN_ROOT" "$pruned" "$KEEP_LOCAL" <<'PY'
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

(path, status, target, snapshot, source, started, files, size, error,
 external_target, external_snapshot, brain, pruned, keep) = sys.argv[1:]
path = Path(path)
path.parent.mkdir(parents=True, exist_ok=True)
record = {
    "ts": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    "status": status,
    "authority": "linux",
    "target": target,
    "snapshot_path": snapshot or None,
    "external_target": external_target,
    "external_snapshot_path": external_snapshot or None,
    "sources": [{"name": "AgenticOSClean", "path": source}, {"name": "BusinessBrain", "path": brain}],
    "files_copied": int(files),
    "bytes_copied": int(size),
    "local_retention": {"keep": int(keep), "pruned": int(pruned)},
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
    write_receipt fail "$failure" || true
  fi
  exit "$rc"
}
trap on_exit EXIT

# Lists files whose content differs between a source tree and its copy; empty output means identical.
# --modify-window=1 absorbs NTFS timestamp rounding; directory-only attribute lines are ignored.
# An rsync error fails the caller's assignment rather than reading as "no differences".
content_diff() {
  local out
  out="$(rsync -rlt --checksum --dry-run --itemize-changes --modify-window=1 "$@")" || return 1
  grep -v '^\.d' <<<"$out" || true
}

PYTHONPATH="${ROOT}/tools${PYTHONPATH:+:${PYTHONPATH}}" python3 -c \
  'from aos_paths import assert_authoritative_root; import os; assert_authoritative_root(os.environ["AOS_ROOT"]); assert_authoritative_root(os.environ["AOS_BACKUP_ROOT"])'
# Keep snapshots out of ripgrep/fd searches of $HOME: an agent's home-wide content search otherwise
# reads every snapshot into page cache, which WSL holds as Vmmem memory on Windows.
mkdir -p "$BACKUP_ROOT"
printf '*\n' > "${BACKUP_ROOT%/}/.ignore"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
snapshot="${BACKUP_ROOT%/}/agentic-os-${stamp}"
# Copy into .partial and rename only once validated, so retention never counts a half-written snapshot.
destination="${snapshot}.partial"
mkdir -p "$destination"
rsync -a --exclude='.git/' --exclude='.venv*/' --exclude='node_modules/' --exclude='dist/' \
  --exclude='.vite/' --exclude='__pycache__/' --exclude='*.py[co]' --exclude='queue/locks/*.lock' \
  --exclude='*.tmp' --exclude='*.candidate*' --exclude='**/.env' --exclude='**/.env.*' \
  --exclude='workspaces/north_shore_sales_coach/' --exclude='connectors/telegram_bridge/' \
  "$ROOT/" "$destination/"
[[ -r "$destination/AGENTS.md" && -r "$destination/CODEX.md" && -r "$destination/tools/aos-linux-backup.sh" ]]
[[ ! -e "$destination/.env" && ! -e "$destination/workspaces/north_shore_sales_coach" && ! -e "$destination/connectors/telegram_bridge" ]]
mv -- "$destination" "$snapshot"
destination="$snapshot"
files_copied="$(find "$destination" -type f -printf '.' | wc -c)"
bytes_copied="$(du -sb "$destination" | awk '{print $1}')"

failure="external backup root missing (drive disconnected?): ${EXTERNAL_ROOT}"
[[ -d "$EXTERNAL_ROOT" ]]
failure="external backup copy or verification failed"
external="${EXTERNAL_ROOT%/}/$(date -d "@${started_epoch}" +%Y-%m-%d_%H%M)"
mkdir -- "${external}.partial"
rsync -rlt "$destination/" "${external}.partial/AgenticOSLive/"
rsync -rlt --exclude='**/.env' --exclude='**/.env.*' "$BRAIN_ROOT/" "${external}.partial/BusinessBrain/"
[[ -r "${external}.partial/AgenticOSLive/AGENTS.md" && -r "${external}.partial/BusinessBrain/README.md" ]]
repo_diff="$(content_diff "$destination/" "${external}.partial/AgenticOSLive/")"
[[ -z "$repo_diff" ]]
# The vault's .git churns under the brain-git-sweep timer, so only working files are compared.
brain_diff="$(content_diff --exclude='.git/' --exclude='**/.env' --exclude='**/.env.*' "$BRAIN_ROOT/" "${external}.partial/BusinessBrain/")"
[[ -z "$brain_diff" ]]
printf 'stamp=%s\nlocal_snapshot=%s\nrepo_source=%s\nbrain_source=%s\nrepo_files=%s\n' \
  "$stamp" "$destination" "$ROOT" "$BRAIN_ROOT" "$files_copied" > "${external}.partial/MANIFEST.txt"
mv -- "${external}.partial" "$external"

# Local retention runs only after both copies are verified: while the external copy is failing,
# older local snapshots are kept as the fallback. External snapshots are never pruned here.
failure="local retention failed"
mapfile -t snapshots < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -regextype posix-extended \
  -regex '.*/agentic-os-[0-9]{8}T[0-9]{6}Z' -printf '%f\n' | sort)
for ((i = 0; i < ${#snapshots[@]} - KEEP_LOCAL; i++)); do
  rm -rf -- "${BACKUP_ROOT%/}/${snapshots[i]}"
  pruned=$((pruned + 1))
done
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'agentic-os-*.partial' -mmin +1440 -exec rm -rf -- {} +

write_receipt success "" "$files_copied" "$bytes_copied"
completed=1
trap - EXIT
printf 'backup=%s\nexternal=%s\npruned=%s\n' "$destination" "$external" "$pruned"
