#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$PATH"

prompt_file=""
provider_requested=""
model_requested=""
usage_file=""
while (($# > 0)); do
  case "${1:-}" in
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
    exec hermes --provider "$provider_requested" --model "$model_requested" --usage-file "$usage_file" --oneshot "$prompt"
  fi
  exec hermes --provider "$provider_requested" --model "$model_requested" --oneshot "$prompt"
fi
if [[ -n "$usage_file" ]]; then
  exec hermes --usage-file "$usage_file" --oneshot "$prompt"
fi
exec hermes --oneshot "$prompt"
