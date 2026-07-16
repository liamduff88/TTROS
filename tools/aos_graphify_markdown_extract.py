"""Invoke Graphify's installed deterministic Markdown extractor without an LLM.

This wrapper compensates for graphify 0.9.11 requiring an API-backed semantic
pass for the documents CLI even though its structural Markdown extractor is
local and complete enough for TTROS note/link projection.

Revisit: when Graphify exposes a no-LLM documents CLI mode. · Last touched: 2026-07-15.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from graphify.extract import extract


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    paths = sorted(
        path
        for path in root.rglob("*.md")
        if path.is_file() and "_backups" not in {part.lower() for part in path.relative_to(root).parts}
    )
    result = extract(paths, cache_root=root, parallel=False)
    result["ttros_wrapper"] = {
        "mode": "installed_graphify_structural_markdown",
        "source_count": len(paths),
        "input_tokens": int(result.get("input_tokens") or 0),
        "output_tokens": int(result.get("output_tokens") or 0),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
