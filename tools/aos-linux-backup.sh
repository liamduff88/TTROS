#!/usr/bin/env bash
# Revisit: when authoritative state paths or backup retention changes. · Last touched: 2026-07-11.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${AOS_ROOT:-$(cd -- "${SCRIPT_DIR}/.." && pwd)}"
BACKUP_ROOT="${AOS_BACKUP_ROOT:?Set AOS_BACKUP_ROOT to a Linux-native backup directory}"
export AOS_ROOT="$ROOT"
PYTHONPATH="${ROOT}/tools${PYTHONPATH:+:${PYTHONPATH}}" python3 -c \
  'from aos_paths import assert_authoritative_root; import os; assert_authoritative_root(os.environ["AOS_ROOT"]); assert_authoritative_root(os.environ["AOS_BACKUP_ROOT"])'
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
destination="${BACKUP_ROOT%/}/agentic-os-${stamp}"
mkdir -p "$destination"
rsync -a --exclude='.git/' --exclude='.venv*/' --exclude='node_modules/' --exclude='dist/' \
  --exclude='.vite/' --exclude='__pycache__/' --exclude='*.py[co]' --exclude='queue/locks/*.lock' \
  --exclude='*.tmp' --exclude='*.candidate*' "$ROOT/" "$destination/"
printf 'backup=%s\n' "$destination"
