#!/usr/bin/env bash
# Revisit: when the operator-lean Hermes profile or one-shot CLI changes. · Last touched: 2026-08-01.
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
while (($# > 0)); do
  case "${1:-}" in
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

brief_generator="${AOS_ROOT}/tools/aos_executive_brief.py"
executive_header_file="${AOS_ROOT}/context/EXECUTIVE_HEADER.txt"
if ! python3 "$brief_generator"; then
  # A failed refresh deliberately leaves the last good brief and a stale header.
  :
fi
if [[ ! -f "$executive_header_file" ]]; then
  echo "NEEDS ATTENTION"
  echo "Blockers: Executive header is unavailable"
  exit 78
fi
executive_header="$(<"$executive_header_file")"
prompt="Executive header (read-only situational awareness):
${executive_header}

Operator message:
${prompt}"

# Running from the profile home prevents repository AGENTS.md and Business
# Brain pointers from entering this deliberately tiny one-shot context.
cd "$profile_home"
export HERMES_HOME="$profile_home"
escalation_reply_file="$(mktemp "${AOS_ROOT}/queue/run_prompts/operator_escalation_reply.XXXXXX")"
oneshot_output_file="$(mktemp "${AOS_ROOT}/queue/run_prompts/operator_lean_output.XXXXXX")"
cleanup_operator_files() {
  rm -f -- "$escalation_reply_file" "$oneshot_output_file"
}
trap cleanup_operator_files EXIT
export AOS_OPERATOR_ESCALATION_REPLY_FILE="$escalation_reply_file"
set +e
if [[ -n "$usage_file" ]]; then
  "$hermes_python" "$oneshot_entry" --usage-file "$usage_file" "$prompt" >"$oneshot_output_file"
  oneshot_status=$?
else
  "$hermes_python" "$oneshot_entry" "$prompt" >"$oneshot_output_file"
  oneshot_status=$?
fi
set -e
if [[ -s "$escalation_reply_file" ]]; then
  command cat "$escalation_reply_file"
else
  command cat "$oneshot_output_file"
fi
exit "$oneshot_status"
