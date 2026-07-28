#!/usr/bin/env python3
"""Fail-closed Hermes oneshot entrypoint for the six-tool operator profile.

Revisit: when Hermes oneshot or MCP startup semantics change. · Last touched: 2026-07-28.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


EXPECTED_TOOLS = frozenset(
    {
        "mcp__operator__list_open_tasks",
        "mcp__operator__list_review_queue",
        "mcp__operator__get_item_status",
        "mcp__operator__get_latest_receipt",
        "mcp__operator__get_token_ledger",
        "mcp__operator__create_task",
    }
)
TOOL_UNAVAILABLE_EXIT = 78


def require_operator_tools(
    discover: Callable[[], list[str]] | None = None,
) -> tuple[str, ...]:
    """Synchronously discover and validate the complete operator tool snapshot."""
    if discover is None:
        from tools.mcp_tool import discover_mcp_tools

        discover = discover_mcp_tools

    discovered = frozenset(discover())
    if discovered != EXPECTED_TOOLS:
        missing = sorted(EXPECTED_TOOLS - discovered)
        unexpected = sorted(discovered - EXPECTED_TOOLS)
        detail = []
        if missing:
            detail.append(f"missing={','.join(missing)}")
        if unexpected:
            detail.append(f"unexpected={','.join(unexpected)}")
        raise RuntimeError("; ".join(detail) or "empty tool snapshot")
    return tuple(sorted(discovered))


def run_operator_oneshot(
    prompt: str,
    *,
    usage_file: str = "",
    discover: Callable[[], list[str]] | None = None,
    runner: Callable[..., int] | None = None,
) -> int:
    """Discover first, then let Hermes construct and run the oneshot agent."""
    try:
        require_operator_tools(discover)
    except Exception as exc:
        print(
            f"TOOL_UNAVAILABLE: operator-lean requires exactly six queue tools ({exc}). "
            "No model was called and no task was queued.",
            file=sys.stderr,
        )
        return TOOL_UNAVAILABLE_EXIT

    if runner is None:
        from hermes_cli.oneshot import run_oneshot

        runner = run_oneshot
    return runner(prompt, toolsets=["operator"], usage_file=usage_file or None)


def inspect_loaded_preamble() -> dict[str, Any]:
    """Return the real post-discovery system prompt and six schemas; no API call."""
    names = require_operator_tools()
    from agent.system_prompt import build_system_prompt
    from hermes_cli.prompt_size import _build_inspection_agent

    agent = _build_inspection_agent("cli")
    return {
        "tool_names": list(names),
        "system_prompt": build_system_prompt(agent),
        "tools": agent.tools,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file")
    parser.add_argument("--usage-file", default="")
    parser.add_argument("--inspect-preamble", action="store_true")
    parser.add_argument("prompt", nargs="*")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.inspect_preamble:
        print(json.dumps(inspect_loaded_preamble(), ensure_ascii=False))
        return 0

    if args.prompt_file:
        try:
            prompt = Path(args.prompt_file).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Blockers: Prompt file unavailable: {exc}", file=sys.stderr)
            return 2
    else:
        prompt = " ".join(args.prompt).strip()
    if not prompt:
        print("Blockers: No operator message provided", file=sys.stderr)
        return 2
    return run_operator_oneshot(prompt, usage_file=args.usage_file)


if __name__ == "__main__":
    raise SystemExit(main())
