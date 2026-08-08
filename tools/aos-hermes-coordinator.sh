#!/usr/bin/env bash
# Revisit: when Hermes profile selection or Step 6 usage changes. · Last touched: 2026-08-04.
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$PATH"
export AOS_ROOT="${AOS_ROOT:-/home/liam/agentic-os-live}"

profile="aos-orchestrator"
prompt_file=""
provider_requested=""
model_requested=""
usage_file=""
scope_type=""
scope_id=""
cost_dial=""
invocation_id=""
while (($# > 0)); do
  case "${1:-}" in
    --profile)
      if (($# < 2)); then
        echo "NEEDS ATTENTION"
        echo "Blockers: --profile requires a profile name"
        exit 2
      fi
      profile="$2"
      shift 2
      ;;
    --prompt-file)
      if (($# < 2)); then
        echo "NEEDS ATTENTION"
        echo "Blockers: --prompt-file requires a path"
        exit 2
      fi
      prompt_file="$2"
      shift 2
      ;;
    --provider)
      if (($# < 2)); then
        echo "NEEDS ATTENTION"
        echo "Blockers: --provider requires a Hermes provider name"
        exit 2
      fi
      provider_requested="$2"
      shift 2
      ;;
    --model)
      if (($# < 2)); then
        echo "NEEDS ATTENTION"
        echo "Blockers: --model requires a Hermes model name"
        exit 2
      fi
      model_requested="$2"
      shift 2
      ;;
    --usage-file)
      if (($# < 2)); then
        echo "NEEDS ATTENTION"
        echo "Blockers: --usage-file requires a path"
        exit 2
      fi
      usage_file="$2"
      shift 2
      ;;
    --scope-type|--scope-id|--cost-dial|--invocation-id)
      if (($# < 2)); then
        echo "NEEDS ATTENTION"
        echo "Blockers: $1 requires a value"
        exit 2
      fi
      case "$1" in
        --scope-type) scope_type="$2" ;;
        --scope-id) scope_id="$2" ;;
        --cost-dial) cost_dial="$2" ;;
        --invocation-id) invocation_id="$2" ;;
      esac
      shift 2
      ;;
    *)
      break
      ;;
  esac
done

case "$profile" in
  aos-orchestrator|aos-revenue|aos-marketing|aos-delivery|aos-ops|david) ;;
  *)
    echo "NEEDS ATTENTION"
    echo "Blockers: Profile '${profile}' is not an Agentic OS runtime profile"
    exit 2
    ;;
esac
profile_home="${HOME}/.hermes/profiles/${profile}"
if [[ ! -d "$profile_home" ]]; then
  echo "NEEDS ATTENTION"
  echo "Blockers: Required Hermes profile '${profile}' is unavailable at ${profile_home}"
  exit 78
fi

if [[ -n "$prompt_file" ]]; then
  if [[ ! -f "$prompt_file" ]]; then
    echo "NEEDS ATTENTION"
    echo "Blockers: Prompt file not found: $prompt_file"
    exit 2
  fi
  prompt="$(<"$prompt_file")"
elif (($# == 0)); then
  echo "NEEDS ATTENTION"
  echo "Blockers: No coordinator task provided"
  exit 2
else
  prompt="$*"
fi

if [[ -z "$scope_id" ]]; then
  if [[ "$prompt" =~ TTROS\ sticky\ session\ key:\ ([A-Za-z0-9_-]{8,128}) ]]; then
    scope_type="session"
    scope_id="${BASH_REMATCH[1]}"
  elif [[ "$prompt" =~ (AOS-[0-9]{4}-[0-9]{4}) ]]; then
    scope_type="work_item"
    scope_id="${BASH_REMATCH[1]}"
  else
    scope_type="session"
    scope_id="${profile}-direct"
  fi
fi
[[ "$scope_type" == "work_item" || "$scope_type" == "session" ]] || { echo "Blockers: invalid Step 6 scope type"; exit 2; }
invocation_id="${invocation_id:-hermes-${profile}-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
python_bin="${HOME}/.hermes/hermes-agent/venv/bin/python3"
if [[ ! -x "$python_bin" ]]; then python_bin="python3"; fi
preflight_args=(--root "$AOS_ROOT" preflight --scope-type "$scope_type" --scope-id "$scope_id")
if [[ -n "$cost_dial" ]]; then preflight_args+=(--cost-dial "$cost_dial"); fi
"$python_bin" "$AOS_ROOT/tools/step6_cost_control.py" "${preflight_args[@]}" >/dev/null || exit 78
export AOS_STEP6_WRAPPED="1"
export AOS_STEP6_SCOPE_TYPE="$scope_type"
export AOS_STEP6_SCOPE_ID="$scope_id"
export AOS_STEP6_INVOCATION_ID="$invocation_id"

internal_usage_file=""
if [[ -z "$usage_file" ]]; then
  internal_usage_file="$(mktemp "${AOS_ROOT}/queue/run_prompts/coordinator_usage.XXXXXX.json")"
  usage_file="$internal_usage_file"
fi
cleanup_step6_usage() { rm -f -- "$internal_usage_file"; }
trap cleanup_step6_usage EXIT

# Native Hermes owns tool choice and delegation. Its pre-LLM hook supplies
# mandatory assembled One Brain context and the runtime fails closed without it.
if [[ -n "$provider_requested" && -n "$model_requested" ]]; then
  route_pair="${provider_requested}|${model_requested}"
  if [[ "$route_pair" =~ \<[^\>]+\>|[Ee][Xx][Aa][Cc][Tt][_[:space:]-]*(provider|model)|[Ff][Aa][Kk][Ee]|[Pp][Ll][Aa][Cc][Ee][Hh][Oo][Ll][Dd][Ee][Rr]|[Uu][Nn][Ii][Tt][_[:space:]-]*(provider|model) ]]; then
    echo "NEEDS ATTENTION"
    echo "Blockers: Refusing placeholder provider/model route; using explicit flags requires real configured values"
    exit 2
  fi
fi
set +e
if [[ -n "$provider_requested" && -n "$model_requested" ]]; then
  hermes -p "$profile" --provider "$provider_requested" --model "$model_requested" --usage-file "$usage_file" --oneshot "$prompt"
else
  hermes -p "$profile" --usage-file "$usage_file" --oneshot "$prompt"
fi
hermes_status=$?
set -e
record_args=(--root "$AOS_ROOT" record-usage --scope-type "$scope_type" --scope-id "$scope_id" --invocation-id "$invocation_id" --usage-file "$usage_file" --surface "hermes:${profile}")
if [[ -n "$cost_dial" ]]; then record_args+=(--cost-dial "$cost_dial"); fi
if ! "$python_bin" "$AOS_ROOT/tools/step6_cost_control.py" "${record_args[@]}" >/dev/null 2>&1; then
  "$python_bin" "$AOS_ROOT/tools/step6_cost_control.py" --root "$AOS_ROOT" record-unavailable --scope-type "$scope_type" --scope-id "$scope_id" --invocation-id "$invocation_id" --reason "Hermes usage report missing or corrupt" --surface "hermes:${profile}" >/dev/null 2>&1 || true
  echo "NEEDS ATTENTION: exact Hermes usage unavailable; Step 6 scope paused" >&2
  exit 78
fi
exit "$hermes_status"
