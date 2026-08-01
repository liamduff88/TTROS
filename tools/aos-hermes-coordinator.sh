#!/usr/bin/env bash
# Revisit: when Hermes per-invocation profile selection changes. · Last touched: 2026-07-31.
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$PATH"

profile="aos-orchestrator"
prompt_file=""
provider_requested=""
model_requested=""
usage_file=""
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
    *)
      break
      ;;
  esac
done

case "$profile" in
  aos-orchestrator|aos-revenue|aos-marketing|aos-delivery|aos-ops) ;;
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

if [[ "$profile" == "aos-orchestrator" ]]; then
  script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
  aos_root="${AOS_ROOT:-$(dirname -- "$script_dir")}"
  brief_generator="${aos_root}/tools/aos_executive_brief.py"
  executive_brief_file="${aos_root}/context/EXECUTIVE_BRIEF.md"
  if ! python3 "$brief_generator"; then
    # Continue only with the generator's retained last-good stale brief.
    :
  fi
  if [[ ! -f "$executive_brief_file" ]]; then
    echo "NEEDS ATTENTION"
    echo "Blockers: Executive brief is unavailable"
    exit 78
  fi
  executive_brief="$(<"$executive_brief_file")"
  prompt="Executive brief (read-only situational awareness; do not auto-escalate):
${executive_brief}

Coordinator task:
${prompt}"
fi

# Native Hermes owns tool choice and delegation. Web/search, scrape,
# Firecrawl, and Composio requests are not pre-routed around Hermes.
if [[ -n "$provider_requested" && -n "$model_requested" ]]; then
  route_pair="${provider_requested}|${model_requested}"
  if [[ "$route_pair" =~ \<[^\>]+\>|[Ee][Xx][Aa][Cc][Tt][_[:space:]-]*(provider|model)|[Ff][Aa][Kk][Ee]|[Pp][Ll][Aa][Cc][Ee][Hh][Oo][Ll][Dd][Ee][Rr]|[Uu][Nn][Ii][Tt][_[:space:]-]*(provider|model) ]]; then
    echo "NEEDS ATTENTION"
    echo "Blockers: Refusing placeholder provider/model route; using explicit flags requires real configured values"
    exit 2
  fi
  if [[ -n "$usage_file" ]]; then
    exec hermes -p "$profile" --provider "$provider_requested" --model "$model_requested" --usage-file "$usage_file" --oneshot "$prompt"
  fi
  exec hermes -p "$profile" --provider "$provider_requested" --model "$model_requested" --oneshot "$prompt"
fi
if [[ -n "$usage_file" ]]; then
  exec hermes -p "$profile" --usage-file "$usage_file" --oneshot "$prompt"
fi
exec hermes -p "$profile" --oneshot "$prompt"
