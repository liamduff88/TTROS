#!/usr/bin/env python3
"""Bounded local tools for the Hermes operator-lean profile.

Revisit: when queue fields or the operator-lean tool contract changes. · Last touched: 2026-08-04.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer


ROOT = Path(os.environ.get("AOS_ROOT", "/home/liam/agentic-os-live")).resolve()
QUEUE_FILE = ROOT / "queue" / "work_items.jsonl"
TOKEN_FILES = (
    ROOT / "logs" / "token_usage.jsonl",
    ROOT / "queue" / "token_ledger.jsonl",
    ROOT / "token_ledger.jsonl",
)
ACTIVE_STATES = {"inbox", "agent_todo", "agent_working", "needs_input", "human_review", "blocked"}
REVIEW_STATES = {"needs_input", "human_review", "blocked"}
OperatorWorker = Literal["revenue", "marketing", "delivery", "operations", "codex", "claude"]
ITEM_ID_RE = re.compile(r"^AOS-\d{4}-\d{4}$")
MAX_TOOL_ROWS = 10
MAX_RECEIPT_CHARS = 2_000

mcp = MCPServer("operator-lean")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _items() -> list[dict[str, Any]]:
    return _read_jsonl(QUEUE_FILE)


def _item_ref(item: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(item.get("id") or ""),
        "title": str(item.get("title") or "")[:240],
        "state": str(item.get("status") or ""),
        "owner": str(item.get("owner") or "unassigned"),
    }


def _find_item(item_id: str) -> dict[str, Any] | None:
    target = str(item_id or "").strip().upper()
    return next((row for row in _items() if str(row.get("id") or "").upper() == target), None)


def _latest_receipt(item: dict[str, Any]) -> dict[str, Any] | None:
    receipts = item.get("receipts")
    if not isinstance(receipts, list):
        return None
    values = [row for row in receipts if isinstance(row, dict) and row.get("path")]
    return values[-1] if values else None


@mcp.tool()
def list_open_tasks(limit: int = 10) -> dict[str, Any]:
    """List active tasks; read-only."""
    bounded = max(1, min(int(limit), MAX_TOOL_ROWS))
    rows = [_item_ref(row) for row in reversed(_items()) if row.get("status") in ACTIVE_STATES]
    return {"count": len(rows), "items": rows[:bounded]}


@mcp.tool()
def list_review_queue(limit: int = 10) -> dict[str, Any]:
    """List tasks needing Liam, review, or unblock input; read-only."""
    bounded = max(1, min(int(limit), MAX_TOOL_ROWS))
    rows = [_item_ref(row) for row in reversed(_items()) if row.get("status") in REVIEW_STATES]
    return {"count": len(rows), "items": rows[:bounded]}


@mcp.tool()
def get_item_status(item_id: str) -> dict[str, Any]:
    """Get task metadata and its latest receipt path; read-only."""
    item = _find_item(item_id)
    if item is None:
        return {"found": False, "item_id": str(item_id or "")[:32]}
    latest = _latest_receipt(item)
    return {
        "found": True,
        **_item_ref(item),
        "latest_receipt": str((latest or {}).get("path") or ""),
    }


@mcp.tool()
def get_latest_receipt(item_id: str) -> dict[str, Any]:
    """Read a task's latest receipt, capped at 2,000 characters."""
    item = _find_item(item_id)
    if item is None:
        return {"found": False, "item_id": str(item_id or "")[:32]}
    receipt = _latest_receipt(item)
    relative = str((receipt or {}).get("path") or "")
    if not relative:
        return {"found": False, "item_id": item["id"], "reason": "no receipt"}
    target = (ROOT / relative).resolve()
    try:
        target.relative_to(ROOT)
        text = target.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return {"found": False, "item_id": item["id"], "path": relative, "reason": "unavailable"}
    return {
        "found": True,
        "item_id": item["id"],
        "path": relative,
        "content": text[:MAX_RECEIPT_CHARS],
        "truncated": len(text) > MAX_RECEIPT_CHARS,
    }


@mcp.tool()
def get_token_ledger(item_id: str = "", limit: int = 5) -> dict[str, Any]:
    """Get recorded usage for one task or recent tasks; read-only."""
    bounded = max(1, min(int(limit), MAX_TOOL_ROWS))
    target = str(item_id or "").strip().upper()
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in TOKEN_FILES:
        for row in reversed(_read_jsonl(path)):
            row_item_id = str(row.get("item_id") or row.get("task_id") or "")
            if target and target not in {row_item_id.upper(), str(row.get("task") or "").split(" | ", 1)[0].upper()}:
                continue
            usage = row.get("token_usage") if isinstance(row.get("token_usage"), dict) else row
            identity = str(
                usage.get("invocation_id")
                or usage.get("session_id")
                or f"{path.name}:{row.get('timestamp')}:{row_item_id}"
            )
            if identity in seen:
                continue
            seen.add(identity)
            records.append({
                "item_id": row_item_id or (target if target else ""),
                "component": str(row.get("agent") or row.get("component") or row.get("route") or ""),
                "model": usage.get("model"),
                "provider": usage.get("provider"),
                "available_input": usage.get("input_tokens", usage.get("total_input")),
                "cached_input": usage.get("cached_input_tokens", usage.get("cached_input")),
                "fresh_input": usage.get("fresh_input_tokens", usage.get("fresh_input")),
                "output": usage.get("output_tokens", usage.get("output")),
                "reasoning": usage.get("reasoning_tokens", usage.get("reasoning")),
                "api_calls": usage.get("api_calls"),
                "elapsed_seconds": row.get("elapsed_seconds"),
                "session_id": usage.get("session_id"),
                "invocation_id": usage.get("invocation_id"),
            })
            if len(records) >= bounded:
                return {"records": records}
    return {"records": records}


@mcp.tool()
def create_task(
    instruction: str,
    worker: OperatorWorker,
    delivery_id: str = "",
    reply_to: str = "",
) -> dict[str, Any]:
    """Refuse conversational task creation; /work is handled before this profile."""
    return {
        "created": False,
        "error": "Ordinary conversation cannot create work. Use an explicit /work request through the Telegram command route.",
    }


@mcp.tool()
def escalate_to_executive(message: str) -> str:
    """Keep sticky executive conversation direct; do not launch a nested turn."""
    return (
        "Executive conversation is already the active surface. "
        "Answer directly from the assembled One Brain context without nested escalation."
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
