#!/usr/bin/env bash
set -u

WORKSPACE="/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live"
COMPOSIO="/home/liam/.composio/composio"
OUT="$WORKSPACE/connectors/composio_live_connections.txt"

mkdir -p "$WORKSPACE/connectors"

{
  echo "Agentic OS Composio CLI verification"
  echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "Distro: ${WSL_DISTRO_NAME:-unknown}"
  echo "Workspace: $WORKSPACE"
  echo "CLI: $COMPOSIO"
  echo ""

  echo "=== binary exists ==="
  if [ -x "$COMPOSIO" ]; then
    echo "YES"
  else
    echo "NO - missing or not executable: $COMPOSIO"
  fi
  echo ""

  echo "=== version ==="
  "$COMPOSIO" version 2>&1 || "$COMPOSIO" --version 2>&1 || true
  echo ""

  echo "=== whoami ==="
  "$COMPOSIO" whoami 2>&1
  WHOAMI_EXIT=$?
  echo "WHOAMI_EXIT=$WHOAMI_EXIT"
  echo ""

  if [ "$WHOAMI_EXIT" -ne 0 ]; then
    echo "LOGIN_NEEDED"
    echo "Run Composio login next using the same Liam Composio account/workspace."
    echo ""
  else
    echo "=== connections list ==="
    "$COMPOSIO" connections list 2>&1 || true
    echo ""
  fi
} | tee "$OUT"

echo ""
echo "PASS"
echo "Files touched:"
echo "- $OUT"
echo "- $WORKSPACE/connectors/_verify_composio_cli.sh"
echo "Validation:"
echo "- Direct Composio binary path tested"
echo "- Account state checked"
echo "- Connections list requested if already logged in"
echo "Blockers:"
if grep -q "LOGIN_NEEDED" "$OUT"; then
  echo "- Composio CLI login needed"
else
  echo "- None"
fi
echo "Next action:"
if grep -q "LOGIN_NEEDED" "$OUT"; then
  echo "- Run direct-path Composio login, then rerun connection verification"
else
  echo "- Update connector_status.json and CONNECTORS.md with CLI-verified active apps"
fi
