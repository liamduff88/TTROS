#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$PATH"

if (($# == 0)); then
  echo "NEEDS ATTENTION"
  echo "Blockers: No coordinator task provided"
  exit 2
fi

# Native Hermes owns tool choice and delegation. Web/search, scrape,
# Firecrawl, and Composio requests are not pre-routed around Hermes.
exec hermes --oneshot "$*"
