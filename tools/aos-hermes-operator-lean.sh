#!/usr/bin/env bash
# Revisit: when the operator-lean Hermes profile, one-shot CLI, or Step 6 usage contract changes. · Last touched: 2026-08-04.
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$PATH"
export AOS_ROOT="${AOS_ROOT:-/home/liam/agentic-os-live}"

profile="operator-lean"
profile_home="${HOME}/.hermes/profiles/${profile}"
hermes_python="${HOME}/.hermes/hermes-agent/venv/bin/python3"
oneshot_entry="${AOS_ROOT}/tools/operator_lean_oneshot.py"
if [[ ! -d "$profile_home" ]]; then
  echo "NEEDS ATTENTION"
  echo "Blockers: Required Hermes profile '${profile}' is unavailable at ${profile_home}"
  exit 78
fi
if [[ ! -x "$hermes_python" || ! -f "$oneshot_entry" ]]; then
  echo "NEEDS ATTENTION"
  echo "Blockers: operator-lean oneshot runtime is unavailable"
  exit 78
fi

prompt_file=""
usage_file=""
consultation="false"
scope_type=""
scope_id=""
cost_dial=""
invocation_id=""
while (($# > 0)); do
  case "${1:-}" in
    --consultation)
      consultation="true"
      export AOS_OPERATOR_CONSULTATION="1"
      shift
      ;;
    --prompt-file)
      [[ $# -ge 2 ]] || { echo "Blockers: --prompt-file requires a path"; exit 2; }
      prompt_file="$2"
      shift 2
      ;;
    --usage-file)
      [[ $# -ge 2 ]] || { echo "Blockers: --usage-file requires a path"; exit 2; }
      usage_file="$2"
      shift 2
      ;;
    --scope-type|--scope-id|--cost-dial|--invocation-id)
      [[ $# -ge 2 ]] || { echo "Blockers: $1 requires a value"; exit 2; }
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

if [[ -n "$prompt_file" ]]; then
  [[ -f "$prompt_file" ]] || { echo "Blockers: Prompt file not found: $prompt_file"; exit 2; }
  export AOS_OPERATOR_CONTEXT_FILE="$prompt_file"
  prompt="$(<"$prompt_file")"
elif (($# > 0)); then
  prompt="$*"
else
  echo "Blockers: No operator message provided"
  exit 2
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
    scope_id="operator-lean-direct"
  fi
fi
[[ "$scope_type" == "work_item" || "$scope_type" == "session" ]] || { echo "Blockers: invalid Step 6 scope type"; exit 2; }
invocation_id="${invocation_id:-hermes-operator-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
step6_args=(--root "$AOS_ROOT" preflight --scope-type "$scope_type" --scope-id "$scope_id")
if [[ -n "$cost_dial" ]]; then step6_args+=(--cost-dial "$cost_dial"); fi
if ! "$hermes_python" "$AOS_ROOT/tools/step6_cost_control.py" "${step6_args[@]}" >/dev/null; then
  echo "NEEDS ATTENTION"
  echo "Blockers: Step 6 token fuse blocked this named scope"
  exit 78
fi
export AOS_STEP6_WRAPPED="1"
export AOS_STEP6_SCOPE_TYPE="$scope_type"
export AOS_STEP6_SCOPE_ID="$scope_id"
export AOS_STEP6_INVOCATION_ID="$invocation_id"

if [[ "$consultation" == "true" ]]; then
  prompt="Dashboard consultation mode: answer directly from mandatory assembled Brain context. Do not create work or escalate to another profile.

${prompt}"
fi

# The native pre-LLM hook supplies mandatory, relevance-selected One Brain
# context and the runtime blocks the call if that object is missing.
cd "$profile_home"
export HERMES_HOME="$profile_home"
escalation_reply_file="$(mktemp "${AOS_ROOT}/queue/run_prompts/operator_escalation_reply.XXXXXX")"
oneshot_output_file="$(mktemp "${AOS_ROOT}/queue/run_prompts/operator_lean_output.XXXXXX")"
internal_usage_file=""
if [[ -z "$usage_file" ]]; then
  internal_usage_file="$(mktemp "${AOS_ROOT}/queue/run_prompts/operator_usage.XXXXXX.json")"
  usage_file="$internal_usage_file"
fi
cleanup_operator_files() {
  rm -f -- "$escalation_reply_file" "$oneshot_output_file" "$internal_usage_file"
}
trap cleanup_operator_files EXIT
export AOS_OPERATOR_ESCALATION_REPLY_FILE="$escalation_reply_file"
set +e
"$hermes_python" "$oneshot_entry" --usage-file "$usage_file" "$prompt" >"$oneshot_output_file"
oneshot_status=$?
set -e
record_args=(--root "$AOS_ROOT" record-usage --scope-type "$scope_type" --scope-id "$scope_id" --invocation-id "$invocation_id" --usage-file "$usage_file" --surface "hermes:operator-lean")
if [[ -n "$cost_dial" ]]; then record_args+=(--cost-dial "$cost_dial"); fi
if ! "$hermes_python" "$AOS_ROOT/tools/step6_cost_control.py" "${record_args[@]}" >/dev/null 2>&1; then
  "$hermes_python" "$AOS_ROOT/tools/step6_cost_control.py" --root "$AOS_ROOT" record-unavailable --scope-type "$scope_type" --scope-id "$scope_id" --invocation-id "$invocation_id" --reason "Hermes usage report missing or corrupt" --surface "hermes:operator-lean" >/dev/null 2>&1 || true
  oneshot_status=78
  printf '\nNEEDS ATTENTION\nBlockers: exact Hermes usage was unavailable; the named Step 6 scope is paused\n' >>"$oneshot_output_file"
fi
if [[ -s "$escalation_reply_file" ]]; then
  command cat "$escalation_reply_file"
else
  command cat "$oneshot_output_file"
fi
exit "$oneshot_status"
