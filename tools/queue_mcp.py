#!/usr/bin/env python3
"""Scoped Hermes tools for delegating work to the local Agentic OS queue.

David proposes work. The orchestration runner executes it. This tool can only
CREATE and READ. It cannot claim, close, delete, or mutate status — keeping
proposal and execution separate is what stops a conversational agent from
corrupting queue state.

External actions stay outside this tool. Created items are constrained to
local_read / local_edit / local_test, matching the standing git boundary:
local work completes unattended, git and external actions remain gated.

Revisit: when queue lanes, allowed_actions, or the runner contract change. · Last touched: 2026-08-09.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

AOS_ROOT = Path("/home/liam/agentic-os-live")
QUEUE_CLI = AOS_ROOT / "tools" / "aos-queue.py"
PYTHON_BIN = AOS_ROOT / "dashboard" / "backend" / ".venv" / "bin" / "python"
TIMEOUT_SECONDS = 60

# Only local, reversible actions may be requested by a conversational agent.
PERMITTED_ACTIONS = ("local_read", "local_edit", "local_test")
DEFAULT_ACTIONS = "local_read,local_edit,local_test"

# The done-transition is refused by hooks/receipt_completeness_check.md when an item
# carries no stop_conditions, and the item lands in `blocked`. Since items auto-close,
# that is now a silent stall rather than something you would notice in human_review.
# David writes good stop_conditions when he remembers; this covers when he does not.
DEFAULT_STOP_CONDITIONS = (
    "Stop and escalate to the operator if: the definition of done cannot be reached using "
    "local_read, local_edit and local_test alone; an external action, git operation, network "
    "send or credential would be required; the same failure occurs twice in a row; or the work "
    "would expand materially beyond the stated title and context."
)

ITEM_ID_RE = re.compile(r"^AOS-\d{4}-\d{4}$")

# Who work can be handed to. Keys are what David says; values are the queue's
# owner/owner_type pair.
#
# owner_type accepts only "agent" or "workflow" — aos-queue.py rejects anything
# else. It must never be "workflow" here: next_async_item() in the orchestration
# runner explicitly excludes workflow-owned items from async dispatch.
#
# owner is validated against the agent registry by validate_agent(), and is then
# looked up as a lane key in queue/lane_profiles.json, which maps it to the
# Hermes profile at close-out. So owner must be the LANE name (e.g. "operations"),
# never the profile name (e.g. "aos-ops").
DELEGATION_TARGETS: dict[str, tuple[str, str]] = {
    "revenue": ("revenue", "agent"),
    "marketing": ("marketing", "agent"),
    "delivery": ("delivery", "agent"),
    "ops": ("operations", "agent"),
    "operations": ("operations", "agent"),
    "orchestrator": ("orchestrator", "agent"),
    "codex": ("codex", "agent"),
}

# The orchestration runner only ever considers items carrying this tag — see
# next_async_item() in tools/aos-orchestration-runner.py. Without it an item is
# created successfully and then sits in agent_todo forever, invisible to
# dispatch. Always applied; never optional.
ASYNC_DISPATCH_TAG = "async_dispatch"

# aos-queue.py takes --priority as an int, sorted highest-first.
PRIORITY_LEVELS = {"low": 1, "normal": 5, "high": 9}

mcp = FastMCP("queue")


def _run(args: list[str]) -> dict[str, Any]:
    """Invoke the queue CLI with an explicit argv. Never uses a shell."""
    cmd = [str(PYTHON_BIN), str(QUEUE_CLI), "--root", str(AOS_ROOT), *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            cwd=str(AOS_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"queue CLI exceeded {TIMEOUT_SECONDS}s"}
    except OSError as exc:
        return {"success": False, "error": f"queue CLI could not be executed: {exc}"}

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return {"success": False, "error": stderr or stdout or f"exit {proc.returncode}"}

    try:
        return {"success": True, "result": json.loads(stdout)}
    except (json.JSONDecodeError, ValueError):
        return {"success": True, "result": stdout}


@mcp.tool()
def delegate_task(
    title: str,
    context: str,
    definition_of_done: str,
    delegate_to: str,
    priority: str = "normal",
    tags: str = "",
    depends_on: str = "",
    stop_conditions: str = "",
) -> dict[str, Any]:
    """Hand a unit of work to another agent, to run unattended.

    This is for handing work OFF — to revenue, marketing, delivery, ops, the
    orchestrator, or codex. It is not how you talk to Liam.

    Do NOT use this to answer a question, give an opinion, recall something,
    look something up you already know, or hold a conversation. Those happen in
    the turn, for free, with no work item. Creating an item to reply to Liam is
    always wrong.

    DO use it when the work belongs to a different agent, or when it will take
    longer than a reply should, or when it should keep running after this
    conversation ends.

    The runner picks the item up within about five seconds and runs up to two
    concurrently. Do not wait for it and do not poll in the same turn — tell
    Liam it is queued, say who has it, and give him the item id.

    Write `context` and `definition_of_done` so the receiving agent, which has
    no memory of this conversation, could finish the task from them alone.

    Args:
        title: Short imperative summary of the work.
        context: Everything the receiving agent needs. Self-contained.
        definition_of_done: The observable condition that means it is finished.
        delegate_to: revenue | marketing | delivery | ops | orchestrator | codex.
        priority: low | normal | high.
        tags: Comma-separated tags, optional.
        depends_on: Comma-separated AOS item ids that must finish first, optional.
        stop_conditions: When the receiving agent should stop and escalate, optional.
    """
    title = str(title or "").strip()
    context = str(context or "").strip()
    definition_of_done = str(definition_of_done or "").strip()

    if not title:
        return {"success": False, "error": "title is required"}
    if len(title) > 200:
        return {"success": False, "error": "title must be 200 characters or fewer"}
    if not context:
        return {"success": False, "error": "context is required and must be self-contained"}
    if not definition_of_done:
        return {"success": False, "error": "definition_of_done is required"}
    priority = str(priority or "").strip().lower()
    if priority not in PRIORITY_LEVELS:
        return {"success": False, "error": "priority must be low, normal, or high"}
    priority_value = PRIORITY_LEVELS[priority]

    target = str(delegate_to or "").strip().lower()
    if target not in DELEGATION_TARGETS:
        return {
            "success": False,
            "error": f"delegate_to must be one of: {', '.join(sorted(DELEGATION_TARGETS))}",
        }
    owner, owner_type = DELEGATION_TARGETS[target]

    for item_id in [part.strip() for part in depends_on.split(",") if part.strip()]:
        if not ITEM_ID_RE.match(item_id):
            return {"success": False, "error": f"invalid dependency id: {item_id}"}

    args = [
        "create",
        "--title", title,
        "--context", context,
        "--definition-of-done", definition_of_done,
        "--allowed-actions", DEFAULT_ACTIONS,
        # create defaults to "inbox", and next_async_item() only ever considers
        # "agent_todo". An inbox item is created successfully and never runs.
        "--status", "agent_todo",
        "--priority", str(priority_value),
        "--owner", owner,
        "--owner-type", owner_type,
        "--requested-by", "david",
        "--source", "hermes:david",
    ]
    tag_list = [part.strip() for part in str(tags or "").split(",") if part.strip()]
    if ASYNC_DISPATCH_TAG not in tag_list:
        tag_list.insert(0, ASYNC_DISPATCH_TAG)
    args += ["--tags", ",".join(tag_list)]

    if depends_on.strip():
        args += ["--depends-on", depends_on.strip()]
    # Always present. An item without stop_conditions cannot pass the receipt
    # completeness check and would stall in `blocked` instead of closing.
    args += ["--stop-conditions", stop_conditions.strip() or DEFAULT_STOP_CONDITIONS]

    outcome = _run(args)
    if not outcome.get("success"):
        return outcome
    return {
        "success": True,
        "delegated": True,
        "delegated_to": owner,
        "allowed_actions": list(PERMITTED_ACTIONS),
        "external_action": False,
        "note": "Queued for the orchestration runner. Do not poll in this turn; tell Liam who has it and the id.",
        "result": outcome["result"],
    }


@mcp.tool()
def list_work(status: str = "", limit: int = 20) -> dict[str, Any]:
    """List work items in the Agentic OS queue.

    Use this to answer "what is running", "what is waiting on me", or
    "did that finish". Read-only.

    Args:
        status: Optional status filter, e.g. pending, in_progress, done.
        limit: Maximum items to return, 1-100.
    """
    try:
        limit = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        return {"success": False, "error": "limit must be an integer"}

    args = ["list"]
    if str(status or "").strip():
        args += ["--status", str(status).strip()]
    return _run(args) | {"limit": limit}


@mcp.tool()
def show_work(item_id: str) -> dict[str, Any]:
    """Show the full record for one work item, including status and receipts.

    Read-only.

    Args:
        item_id: An id of the form AOS-YYYY-NNNN.
    """
    item_id = str(item_id or "").strip()
    if not ITEM_ID_RE.match(item_id):
        return {"success": False, "error": "item_id must look like AOS-2026-0123"}
    return _run(["show", item_id])


@mcp.tool()
def queue_status() -> dict[str, Any]:
    """Report whether the queue tooling is reachable from this profile.

    Use this if a delegation fails and you need to tell Liam why.
    """
    return {
        "aos_root": str(AOS_ROOT),
        "queue_cli_present": QUEUE_CLI.is_file(),
        "python_present": PYTHON_BIN.is_file(),
        "permitted_actions": list(PERMITTED_ACTIONS),
        "dispatch_tag": ASYNC_DISPATCH_TAG,
        "can_create": True,
        "can_claim_close_or_delete": False,
        "note": (
            "This tool proposes work only; the orchestration runner executes it. "
            "Always delegate through delegate_task — items created any other way "
            "lack the async_dispatch tag and are never picked up."
        ),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
