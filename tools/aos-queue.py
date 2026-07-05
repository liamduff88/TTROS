#!/usr/bin/env python3
"""Local Agentic OS work queue.

This tool only moves work items through local JSONL files. It does not call
external services, run agents, start schedulers, or update dashboards.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from aos_paths import aos_root

DEFAULT_ROOT = aos_root()
QUEUE_DIR = Path("queue")
WORK_ITEMS_PATH = QUEUE_DIR / "work_items.jsonl"
REGISTRY_PATH = QUEUE_DIR / "agent_registry.json"
RECEIPTS_DIR = QUEUE_DIR / "receipts"
LOCKS_DIR = QUEUE_DIR / "locks"
SCHEMAS_DIR = QUEUE_DIR / "schemas"

APPROVED_STATUSES = {
    "inbox",
    "agent_todo",
    "agent_working",
    "needs_input",
    "human_review",
    "done",
    "blocked",
    "cancelled",
}
AVAILABLE_STATUSES = {"inbox", "agent_todo"}
STARTER_AGENTS = ["hermes", "codex", "claude", "revenue", "marketing", "delivery", "operations"]


class QueueError(Exception):
    """Raised when a local queue operation cannot continue."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_queue(root: Path) -> None:
    queue = root / QUEUE_DIR
    queue.mkdir(parents=True, exist_ok=True)
    (root / RECEIPTS_DIR).mkdir(parents=True, exist_ok=True)
    (root / LOCKS_DIR).mkdir(parents=True, exist_ok=True)
    (root / SCHEMAS_DIR).mkdir(parents=True, exist_ok=True)
    work_items = root / WORK_ITEMS_PATH
    if not work_items.exists():
        work_items.write_text("", encoding="utf-8")
    registry = root / REGISTRY_PATH
    if not registry.exists():
        registry.write_text(
            json.dumps(
                {
                    "version": 1,
                    "agents": [{"id": agent, "name": agent.title()} for agent in STARTER_AGENTS],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry(root: Path) -> dict:
    ensure_queue(root)
    registry = read_json(root / REGISTRY_PATH)
    if not isinstance(registry.get("agents"), list):
        raise QueueError("Agent registry must contain an agents list")
    return registry


def agent_ids(root: Path) -> set[str]:
    return {agent["id"] for agent in load_registry(root)["agents"]}


def validate_agent(root: Path, agent_id: str) -> None:
    if agent_id not in agent_ids(root):
        raise QueueError(f"Unknown agent: {agent_id}")


def validate_status(status: str) -> None:
    if status not in APPROVED_STATUSES:
        raise QueueError(f"Invalid status: {status}")


def load_items(root: Path) -> list[dict]:
    ensure_queue(root)
    items = []
    for line_number, line in enumerate((root / WORK_ITEMS_PATH).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise QueueError(f"Invalid JSONL at line {line_number}: {exc}") from exc
        items.append(item)
    return items


def save_items(root: Path, items: list[dict]) -> None:
    ensure_queue(root)
    text = "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in items)
    (root / WORK_ITEMS_PATH).write_text(text, encoding="utf-8")


def find_item(items: list[dict], item_id: str) -> dict:
    for item in items:
        if item.get("id") == item_id:
            return item
    raise QueueError(f"Work item not found: {item_id}")


def next_id(items: list[dict], created_at: str) -> str:
    year = created_at[:4]
    prefix = f"AOS-{year}-"
    max_number = 0
    for item in items:
        item_id = str(item.get("id", ""))
        if item_id.startswith(prefix):
            try:
                max_number = max(max_number, int(item_id.rsplit("-", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}{max_number + 1:04d}"


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def create_item(root: Path, args: argparse.Namespace) -> dict:
    validate_status(args.status)
    if args.owner and args.owner_type == "agent" and args.owner != "unassigned":
        validate_agent(root, args.owner)
    items = load_items(root)
    timestamp = now_iso()
    item = {
        "id": next_id(items, timestamp),
        "title": args.title,
        "status": args.status,
        "priority": args.priority,
        "requested_by": args.requested_by,
        "owner_type": args.owner_type,
        "owner": args.owner,
        "source": args.source,
        "tags": split_csv(args.tags),
        "context": args.context,
        "sources": split_csv(args.sources),
        "allowed_actions": split_csv(args.allowed_actions),
        "stop_conditions": split_csv(args.stop_conditions),
        "definition_of_done": args.definition_of_done,
        "claim": {"claimed_by": None, "claimed_at": None},
        "receipts": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    items.append(item)
    save_items(root, items)
    return item


def list_items(root: Path, status: str | None = None, owner: str | None = None) -> list[dict]:
    if status:
        validate_status(status)
    items = load_items(root)
    if status:
        items = [item for item in items if item.get("status") == status]
    if owner:
        items = [item for item in items if item.get("owner") == owner]
    return sorted(items, key=lambda item: (-int(item.get("priority", 0)), item.get("created_at", ""), item.get("id", "")))


def claim_item(root: Path, item_id: str, agent_id: str) -> dict:
    validate_agent(root, agent_id)
    items = load_items(root)
    item = find_item(items, item_id)
    claimed_by = item.get("claim", {}).get("claimed_by")
    if claimed_by and claimed_by != agent_id:
        raise QueueError(f"Work item already claimed by {claimed_by}")
    timestamp = now_iso()
    item["claim"] = {"claimed_by": agent_id, "claimed_at": timestamp}
    item["status"] = "agent_working"
    item["updated_at"] = timestamp
    save_items(root, items)
    return item


def release_item(root: Path, item_id: str, status: str) -> dict:
    validate_status(status)
    items = load_items(root)
    item = find_item(items, item_id)
    timestamp = now_iso()
    item["claim"] = {"claimed_by": None, "claimed_at": None}
    item["status"] = status
    item["updated_at"] = timestamp
    save_items(root, items)
    return item


def update_status(root: Path, item_id: str, status: str) -> dict:
    validate_status(status)
    items = load_items(root)
    item = find_item(items, item_id)
    item["status"] = status
    item["updated_at"] = now_iso()
    save_items(root, items)
    return item


def attach_receipt(root: Path, item_id: str, receipt_path: str, status: str | None = None) -> dict:
    if status:
        validate_status(status)
    items = load_items(root)
    item = find_item(items, item_id)
    timestamp = now_iso()
    receipt = {"path": receipt_path, "created_at": timestamp}
    if status:
        receipt["status"] = status
        item["status"] = status
    item.setdefault("receipts", []).append(receipt)
    item["updated_at"] = timestamp
    save_items(root, items)
    return item


def item_is_available_for(item: dict, agent_id: str) -> bool:
    if item.get("status") not in AVAILABLE_STATUSES:
        return False
    if item.get("claim", {}).get("claimed_by"):
        return False
    owner = item.get("owner")
    return owner in {"", "unassigned", agent_id}


def next_item(root: Path, agent_id: str) -> dict | None:
    validate_agent(root, agent_id)
    candidates = [item for item in load_items(root) if item_is_available_for(item, agent_id)]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (-int(item.get("priority", 0)), item.get("created_at", ""), item.get("id", "")))[0]


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def print_item_table(items: list[dict]) -> None:
    for item in items:
        claimed_by = item.get("claim", {}).get("claimed_by") or "-"
        print(f"{item['id']}\t{item['status']}\t{item['priority']}\t{item['owner']}\t{claimed_by}\t{item['title']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Agentic OS work queue")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a local work item")
    create.add_argument("--title", required=True)
    create.add_argument("--requested-by", default="local")
    create.add_argument("--owner-type", default="agent")
    create.add_argument("--owner", default="unassigned")
    create.add_argument("--status", default="inbox")
    create.add_argument("--priority", type=int, default=0)
    create.add_argument("--source", default="local")
    create.add_argument("--tags", default="")
    create.add_argument("--context", default="")
    create.add_argument("--sources", default="")
    create.add_argument("--allowed-actions", default="")
    create.add_argument("--stop-conditions", default="")
    create.add_argument("--definition-of-done", default="")

    list_parser = subparsers.add_parser("list", help="List local work items")
    list_parser.add_argument("--status")
    list_parser.add_argument("--owner")
    list_parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")

    show = subparsers.add_parser("show", help="Show one work item")
    show.add_argument("item_id")

    claim = subparsers.add_parser("claim", help="Claim a work item for an agent")
    claim.add_argument("item_id")
    claim.add_argument("agent_id")

    release = subparsers.add_parser("release", help="Release a work item claim")
    release.add_argument("item_id")
    release.add_argument("--status", default="agent_todo")

    receipt = subparsers.add_parser("receipt", help="Attach a receipt path")
    receipt.add_argument("item_id")
    receipt.add_argument("receipt_path")
    receipt.add_argument("--status")

    status = subparsers.add_parser("status", help="Update item status")
    status.add_argument("item_id")
    status.add_argument("status")

    next_parser = subparsers.add_parser("next", help="Show the highest-priority available item for an agent")
    next_parser.add_argument("agent_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        if args.command == "create":
            print_json(create_item(root, args))
        elif args.command == "list":
            items = list_items(root, args.status, args.owner)
            print_json(items) if args.json else print_item_table(items)
        elif args.command == "show":
            print_json(find_item(load_items(root), args.item_id))
        elif args.command == "claim":
            print_json(claim_item(root, args.item_id, args.agent_id))
        elif args.command == "release":
            print_json(release_item(root, args.item_id, args.status))
        elif args.command == "receipt":
            print_json(attach_receipt(root, args.item_id, args.receipt_path, args.status))
        elif args.command == "status":
            print_json(update_status(root, args.item_id, args.status))
        elif args.command == "next":
            item = next_item(root, args.agent_id)
            print_json(item if item else {})
        else:
            parser.error(f"Unknown command: {args.command}")
    except (QueueError, json.JSONDecodeError, OSError) as exc:
        print(f"NEEDS ATTENTION: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
