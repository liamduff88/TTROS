#!/usr/bin/env bash
# Revisit: when Graphify extract/tree CLI arguments change. · Last touched: 2026-07-13.
set -uo pipefail

export PATH="/home/liam/.local/bin:/home/liam/.local/npm/bin:$PATH"
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/false

if [[ $# -ne 3 ]]; then
  echo "usage: aos-graphify-ingest.sh <validated-clone-path> <validated-output-path> <owner/repository>" >&2
  exit 64
fi

clone_path="$(realpath -e -- "$1")" || exit 65
output_path="$(realpath -m -- "$2")" || exit 65
project_label="$3"

case "$clone_path/" in
  /home/liam/graphify-brain/intake/cloned-repos/*/) ;;
  *) echo "clone path is outside the canonical intake root" >&2; exit 65 ;;
esac
case "$output_path/" in
  /home/liam/graphify-brain/repo_graphs/*/) ;;
  *) echo "output path is outside the canonical repository graph root" >&2; exit 65 ;;
esac
if [[ ! "$project_label" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "invalid internal repository label" >&2
  exit 65
fi

mkdir -p -- "$output_path"
graphify extract "$clone_path" --code-only --out "$output_path"
extract_rc=$?
if [[ $extract_rc -ne 0 ]]; then
  exit "$extract_rc"
fi

mapfile -t graph_candidates < <(find "$output_path" -type f -path '*/graphify-out/graph.json' -print | LC_ALL=C sort)
if [[ ${#graph_candidates[@]} -ne 1 ]]; then
  echo "expected exactly one emitted graphify-out/graph.json; found ${#graph_candidates[@]}" >&2
  exit 66
fi
graph_json="${graph_candidates[0]}"
python3 -c 'import json,sys; value=json.load(open(sys.argv[1], encoding="utf-8")); assert isinstance(value,dict) and isinstance(value.get("nodes"),list)' "$graph_json" || exit 66

tree_output="$(dirname -- "$graph_json")/GRAPH_TREE.graphify.html"
graphify tree --graph "$graph_json" --output "$tree_output" --root "$clone_path" --label "$project_label"
tree_rc=$?
if [[ $tree_rc -ne 0 || ! -s "$tree_output" ]]; then
  echo "graphify tree did not emit a non-empty artifact" >&2
  exit 67
fi

printf 'graph_json=%s\n' "$graph_json"
printf 'graphify_tree=%s\n' "$tree_output"
