#!/usr/bin/env bash
# Revisit: when the operator-lean Hermes profile or one-shot CLI changes. · Last touched: 2026-07-28.
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
  prompt="$(<"$prompt_file")"
elif (($# > 0)); then
  prompt="$*"
else
  echo "Blockers: No operator message provided"
  exit 2
fi

# Running from the profile home prevents repository AGENTS.md and Business
# Brain pointers from entering this deliberately tiny one-shot context.
cd "$profile_home"
export HERMES_HOME="$profile_home"
if [[ -n "$usage_file" ]]; then
  if [[ -n "$prompt_file" ]]; then
    exec "$hermes_python" "$oneshot_entry" --usage-file "$usage_file" --prompt-file "$prompt_file"
  fi
  exec "$hermes_python" "$oneshot_entry" --usage-file "$usage_file" "$prompt"
fi
if [[ -n "$prompt_file" ]]; then
  exec "$hermes_python" "$oneshot_entry" --prompt-file "$prompt_file"
fi
exec "$hermes_python" "$oneshot_entry" "$prompt"
