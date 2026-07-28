#!/usr/bin/env python3
"""Six bounded local queue tools for the Hermes operator-lean profile.

Revisit: when queue fields or the operator-lean tool contract changes. · Last touched: 2026-07-28.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP


ROOT = Path(os.environ.get("AOS_ROOT", "/home/liam/agentic-os-live")).resolve()
QUEUE_FILE = ROOT / "queue" / "work_items.jsonl"
TOKEN_FILES = (
    ROOT / "logs" / "token_usage.jsonl",
    ROOT / "queue" / "token_ledger.jsonl",
    ROOT / "token_ledger.jsonl",
)
ACTIVE_STATES = {"inbox", "agent_todo", "agent_working", "needs_input", "human_review", "blocked"}
REVIEW_STATES = {"needs_input", "human_review", "blocked"}
ALLOWED_WORKERS = {"codex", "claude", "revenue", "marketing", "delivery", "operations"}
OperatorWorker = Literal["revenue", "marketing", "delivery", "operations", "codex", "claude"]
CODE_TASK_RE = re.compile(
    r"(?:^|[/\\])[\w.-]+\.(?:py|js|jsx|ts|tsx|json|yaml|yml|md|html|css|sh)\b"
    r"|\b(?:repo(?:sitory)?|code|file|script|test|backend|frontend|connector|routing|template)\b"
    r"|\bdeterministic\b[\s\S]{0,120}\b(?:response|route|handler)\b"
    r"|\b(?:open[- ]task|queue)\b[\s\S]{0,120}\b(?:response|format|metadata)\b",
    re.IGNORECASE,
)
ITEM_ID_RE = re.compile(r"^AOS-\d{4}-\d{4}$")
MAX_TOOL_ROWS = 10
MAX_RECEIPT_CHARS = 2_000
_task_created = False

mcp = FastMCP("operator-lean")


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


def _queue_module():
    path = ROOT / "tools" / "aos-queue.py"
    spec = importlib.util.spec_from_file_location("operator_lean_aos_queue", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("queue tool unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    """Create one local tracked task for this message."""
    global _task_created
    if _task_created:
        return {"created": False, "error": "create_task may be called only once per inbound message"}
    _task_created = True

    text = " ".join(str(instruction or "").split()).strip()
    owner = str(worker or "").strip().casefold()
    if not text or len(text.encode("utf-8")) > 4_000:
        return {"created": False, "error": "instruction must be 1-4,000 UTF-8 bytes"}
    if owner not in ALLOWED_WORKERS:
        return {"created": False, "error": f"worker must be one of {sorted(ALLOWED_WORKERS)}"}
    if owner == "codex" and not CODE_TASK_RE.search(text):
        return {"created": False, "error": "Codex is reserved for repository/code-file changes"}

    source = "telegram"
    stable = str(delivery_id or "").strip() or text.casefold()
    digest = hashlib.sha256(f"{source}\0{stable}".encode("utf-8")).hexdigest()
    small = len(text) <= 800 and "\n" not in text
    args = argparse.Namespace(
        title=text[:180],
        requested_by="Liam",
        owner_type="agent",
        owner=owner,
        status="agent_todo",
        priority=5,
        source=source,
        tags="async_dispatch,olmec,operator_lean" + (",small_task" if small else ""),
        context=text,
        sources="",
        allowed_actions="local_read,local_edit,local_test",
        stop_conditions="external_send,secrets_exposure,destructive_action_outside_scope,git_commit,git_push",
        definition_of_done="Complete the operator instruction and return truthful validation in the normal receipt.",
        parent_id=None,
        step_index=None,
        depends_on="",
        on_complete="human_review",
        workbench=owner if owner in {"codex", "claude"} else "lane",
        review="none",
        size="small" if small else None,
        source_binding=None,
        run_prompt_path=None,
        needs_me=None,
        idempotency_key=f"telegram-dispatch:{digest}",
        inbound_route="telegram:/api/wsl/hermes:operator-lean",
        delivery_id=str(delivery_id or "")[:160],
        reply_to=str(reply_to or "")[:80],
        idempotency_duplicate=False,
    )
    item = _queue_module().create_item(ROOT, args)
    return {
        "created": not bool(args.idempotency_duplicate),
        "duplicate": bool(args.idempotency_duplicate),
        **_item_ref(item),
        "size": item.get("size"),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
