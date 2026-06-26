#!/usr/bin/env bash
# Guarded Nous Portal Tool Gateway setup. This script never starts interactive setup.

set -uo pipefail

AUDITED_PROVIDER="openai-codex"
SNAPSHOT_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.hermes_portal_tools_provider.snapshot"
MODE="${1:---check}"

case "$MODE" in
  --check|--prepare|--verify) ;;
  *)
    echo "Usage: $0 [--check|--prepare|--verify]" >&2
    exit 2
    ;;
esac

if ! command -v hermes >/dev/null 2>&1; then
  echo "ERROR: hermes is not available on PATH." >&2
  exit 1
fi

portal_info="$(hermes portal info 2>&1)"
portal_info_rc=$?
portal_tools="$(hermes portal tools 2>&1)"
portal_tools_rc=$?
hermes_status="$(hermes status 2>&1)"
hermes_status_rc=$?

current_provider="$(printf '%s\n' "$portal_info" | sed -nE 's/^[[:space:]]*Model:[[:space:]]*currently[[:space:]]+([^[:space:]]+).*/\1/p' | head -n 1)"
if [[ -z "$current_provider" ]]; then
  provider_label="$(printf '%s\n' "$hermes_status" | sed -nE 's/^[[:space:]]*Provider:[[:space:]]*(.+)$/\1/p' | head -n 1)"
  case "$provider_label" in
    "OpenAI Codex") current_provider="openai-codex" ;;
    *) current_provider="unknown" ;;
  esac
fi

if printf '%s\n' "$portal_info" | grep -Eqi 'Auth:[[:space:]]+not logged in'; then
  portal_auth="missing"
elif printf '%s\n' "$portal_info" | grep -Eqi 'Auth:'; then
  portal_auth="present"
else
  portal_auth="unknown"
fi

firecrawl_line="$(printf '%s\n' "$portal_tools" | grep -Ei 'Web search.*Firecrawl' | head -n 1 || true)"
if [[ -z "$firecrawl_line" ]]; then
  firecrawl_status="unknown"
elif printf '%s\n' "$firecrawl_line" | grep -Eqi 'not configured|missing|disabled'; then
  firecrawl_status="missing"
else
  firecrawl_status="active"
fi

if [[ "$firecrawl_status" == "active" ]]; then
  tool_gateway="active"
elif [[ "$portal_auth" == "missing" ]] && printf '%s\n' "$portal_tools" | grep -Eqi 'not configured'; then
  tool_gateway="missing"
else
  tool_gateway="unknown"
fi

if [[ "$current_provider" == "$AUDITED_PROVIDER" ]]; then
  model_takeover="no"
else
  model_takeover="yes"
fi

echo "Current model provider: $current_provider"
echo "Portal auth: $portal_auth"
echo "Tool Gateway: $tool_gateway"
echo "Firecrawl/web: $firecrawl_status"
echo "Model takeover: $model_takeover"
echo
echo "Safe manual setup command: hermes tools"
echo "In the interactive tool configuration, choose only Tool Gateway / Nous Subscription"
echo "for Web Search & Extract or Firecrawl. Do not run 'hermes setup --portal',"
echo "'hermes portal', or 'hermes model', and do not select a Nous inference model."

if (( portal_info_rc != 0 || portal_tools_rc != 0 || hermes_status_rc != 0 )); then
  echo "ERROR: one or more read-only Hermes status commands failed." >&2
  exit 1
fi

if [[ "$MODE" == "--prepare" ]]; then
  if [[ "$model_takeover" == "yes" ]]; then
    echo "ERROR: provider differs from the audited provider; snapshot refused." >&2
    exit 1
  fi
  umask 077
  printf '%s\n' "$current_provider" > "$SNAPSHOT_FILE"
  echo "Provider snapshot saved. Run this script with --verify after manual setup."
elif [[ "$MODE" == "--verify" ]]; then
  if [[ ! -f "$SNAPSHOT_FILE" ]]; then
    echo "ERROR: no provider snapshot. Run this script with --prepare first." >&2
    exit 1
  fi
  before_provider="$(head -n 1 "$SNAPSHOT_FILE")"
  if [[ "$current_provider" != "$before_provider" ]]; then
    echo "ERROR: model provider changed: $before_provider -> $current_provider" >&2
    exit 1
  fi
  echo "PASS: model provider is unchanged from the pre-setup snapshot."
else
  echo "Check mode only: no configuration was changed."
fi

if [[ "$model_takeover" == "yes" ]]; then
  exit 1
fi
