#!/usr/bin/env python3
"""Deterministic queue orchestration spine for Agentic OS.

The runner advances local queue state only. It never invokes a model. Telegram
escalation uses the existing bridge send function when a caller supplies it or
when the default loader can import it.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from aos_paths import aos_root

QUEUE_DIR = Path("queue")
WORK_ITEMS_PATH = QUEUE_DIR / "work_items.jsonl"
RECEIPTS_DIR = QUEUE_DIR / "receipts"
EVENTS_PATH = QUEUE_DIR / "orchestration_events.jsonl"
NOTIFICATIONS_PATH = QUEUE_DIR / "notifications.json"
TOKEN_LEDGER_PATH = QUEUE_DIR / "token_ledger.jsonl"

GATE_STATUSES = {"human_review", "needs_input"}
ATTENTION_STATUSES = {"human_review", "needs_input", "blocked"}
ADVANCE_FROM_STATUSES = {"inbox"}
READY_STATUS = "agent_todo"
DONE_STATUS = "done"
ALLOWED_ARTIFACT_PREFIXES = ("results/", "workflows/", "packets/", "logs/", "queue/receipts/")
ARTIFACT_RE = re.compile(r"(?P<path>(?:results|workflows|packets|logs|queue/receipts)/[^\s`'\"<>]+?\.(?:md|txt|json|jsonl|pdf|html))")


class OrchestrationError(Exception):
    """Raised when local orchestration cannot continue safely."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_items(root: Path) -> list[dict]:
    path = root / WORK_ITEMS_PATH
    if not path.exists():
        return []
    items = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OrchestrationError(f"Invalid queue JSONL at line {line_number}: {exc.msg}") from exc
        if isinstance(item, dict):
            items.append(item)
    return items


def save_items(root: Path, items: list[dict]) -> None:
    path = root / WORK_ITEMS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in items), encoding="utf-8")


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def event_exists(events: list[dict], event_type: str, item_id: str, key: str = "") -> bool:
    return any(
        row.get("event") == event_type
        and row.get("item_id") == item_id
        and str(row.get("key") or "") == key
        for row in events
    )


def latest_event(events: list[dict], event_type: str, item_id: str, key: str = "") -> dict | None:
    matches = [
        row for row in events
        if row.get("event") == event_type
        and row.get("item_id") == item_id
        and str(row.get("key") or "") == key
    ]
    return matches[-1] if matches else None


def telegram_idempotency_key(item_id: str, event: str, key: str, recipient: str) -> str:
    parts = [str(item_id or ""), str(event or ""), str(key or ""), str(recipient or "")]
    return "|".join(part.strip() for part in parts)


def _telegram_prior_send_event(events: list[dict], item_id: str, key: str, recipient: str) -> dict | None:
    stable_key = telegram_idempotency_key(item_id, "telegram_escalation", key, recipient)
    for row in reversed(events):
        if row.get("event") != "telegram_escalation":
            continue
        if str(row.get("item_id") or "") != item_id:
            continue
        if str(row.get("key") or "") != key:
            continue
        if str(row.get("recipient") or "") != str(recipient):
            continue
        if row.get("result") != "sent":
            continue
        if row.get("idempotency_key") and row.get("idempotency_key") != stable_key:
            continue
        return row
    return None


def write_receipt(root: Path, item_id: str, kind: str, lines: list[str]) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", item_id).strip("-") or "item"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RECEIPTS_DIR / f"{safe}-{kind}-{stamp}.md"
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path.as_posix()


def attach_receipt(item: dict, receipt_path: str, status: str | None = None) -> None:
    receipt = {"path": receipt_path, "created_at": now_iso()}
    if status:
        receipt["status"] = status
        item["status"] = status
    item.setdefault("receipts", []).append(receipt)
    item["updated_at"] = now_iso()


def latest_receipt_status(item: dict) -> str:
    receipts = item.get("receipts") or []
    if not receipts:
        return ""
    latest = receipts[-1]
    return str(latest.get("status") if isinstance(latest, dict) else "").strip()


def is_step_complete(item: dict) -> bool:
    return item.get("status") == DONE_STATUS and latest_receipt_status(item) == DONE_STATUS


def clean_ref(path: str) -> str | None:
    text = str(path or "").strip().strip(".,);]")
    if not text.startswith(ALLOWED_ARTIFACT_PREFIXES):
        return None
    if ".." in Path(text).parts:
        return None
    return text


def artifact_refs_for(root: Path, item: dict) -> list[str]:
    refs: list[str] = []
    for receipt in item.get("receipts") or []:
        if not isinstance(receipt, dict):
            continue
        path = clean_ref(str(receipt.get("path") or ""))
        if path:
            refs.append(path)
            target = root / path
            if target.exists() and target.is_file():
                content = target.read_text(encoding="utf-8", errors="replace")
                for match in ARTIFACT_RE.finditer(content):
                    candidate = clean_ref(match.group("path"))
                    if candidate:
                        refs.append(candidate)
    unique = []
    for ref in refs:
        if ref not in unique:
            unique.append(ref)
    return unique


def append_source_refs(item: dict, refs: list[str]) -> list[str]:
    existing = [str(ref) for ref in item.get("source_refs") or []]
    added = []
    for ref in refs:
        if ref not in existing:
            existing.append(ref)
            added.append(ref)
    item["source_refs"] = existing
    return added


def no_agent_token_usage() -> dict:
    return {
        "orchestrator": {"input": 0, "output": 0},
        "subagents": [],
        "workbenches": [],
        "totals": {"input": 0, "output": 0},
        "est_cost_usd": 0.0,
        "unavailable": ["no agent invocation"],
    }


def append_no_agent_token_line(root: Path, item: dict, event: str) -> None:
    lane = str(item.get("owner") or "unassigned").strip().lower() or "unassigned"
    if lane == "ops":
        lane = "operations"
    if lane not in {"revenue", "marketing", "delivery", "operations", "hermes", "codex", "claude", "unassigned"}:
        lane = "unassigned"
    append_jsonl(root / TOKEN_LEDGER_PATH, {
        "item_id": item.get("id"),
        "lane": lane,
        "profile": "default",
        "timestamp": now_iso(),
        "escalated": False,
        "model_requested": "none",
        "model_confirmed": "no agent invocation",
        "budget_class": "light",
        "token_usage": no_agent_token_usage(),
        "event": event,
    })


def _step_sort_key(item: dict) -> tuple[int, str]:
    index = item.get("step_index")
    return (index if isinstance(index, int) else 999999, str(item.get("id") or ""))


def next_steps(items: list[dict], completed: dict[str, dict]) -> list[dict]:
    ready = []
    completed_ids = set(completed)
    for item in items:
        if not item.get("parent_id") or item.get("status") not in ADVANCE_FROM_STATUSES:
            continue
        deps = [str(dep) for dep in item.get("depends_on") or [] if str(dep).strip()]
        if not deps:
            siblings = [
                other for other in items
                if other.get("parent_id") == item.get("parent_id")
                and isinstance(other.get("step_index"), int)
                and isinstance(item.get("step_index"), int)
                and other.get("step_index") < item.get("step_index")
            ]
            deps = [str(other.get("id")) for other in siblings[-1:]]
        if deps and all(dep in completed_ids for dep in deps):
            ready.append(item)
    return sorted(ready, key=_step_sort_key)


def tick(root: Path | None = None, *, send_telegram: Callable[[str, str], Any] | None = None, now: datetime | None = None) -> dict:
    root = Path(root or aos_root()).resolve()
    current_time = now or datetime.now(timezone.utc)
    items = load_items(root)
    by_id = {str(item.get("id")): item for item in items}
    completed = {item_id: item for item_id, item in by_id.items() if is_step_complete(item)}
    events = read_jsonl(root / EVENTS_PATH)
    actions: list[dict] = []

    for item in next_steps(items, completed):
        item_id = str(item.get("id"))
        deps = [str(dep) for dep in item.get("depends_on") or [] if str(dep).strip()]
        if not deps:
            previous = [
                other for other in items
                if other.get("parent_id") == item.get("parent_id")
                and isinstance(other.get("step_index"), int)
                and isinstance(item.get("step_index"), int)
                and other.get("step_index") < item.get("step_index")
            ]
            deps = [str(other.get("id")) for other in previous[-1:]]
        key = ",".join(deps)
        if event_exists(events, "step_advanced", item_id, key):
            continue
        refs: list[str] = []
        for dep in deps:
            if dep in completed:
                refs.extend(artifact_refs_for(root, completed[dep]))
        added_refs = append_source_refs(item, refs)
        target_status = str(item.get("on_complete") or "").strip().lower()
        if target_status not in GATE_STATUSES:
            target_status = READY_STATUS
        item["status"] = target_status
        item["updated_at"] = now_iso()
        receipt_path = write_receipt(root, item_id, "runner", [
            "PASS",
            "",
            "Runner action:",
            f"- Event: step_advanced",
            f"- Work item ID: {item_id}",
            f"- Parent ID: {item.get('parent_id')}",
            f"- Step index: {item.get('step_index')}",
            f"- Depends on: {', '.join(deps) if deps else 'none'}",
            f"- Routed owner: {item.get('owner') or 'unassigned'}",
            f"- Workbench: {item.get('workbench') or 'lane'}",
            f"- Status: {target_status}",
            f"- Source refs added: {', '.join(added_refs) if added_refs else 'none'}",
            "- Token usage: no agent invocation",
        ])
        item.setdefault("receipts", []).append({"path": receipt_path, "created_at": now_iso(), "status": target_status})
        record = {
            "event": "step_advanced",
            "item_id": item_id,
            "key": key,
            "parent_id": item.get("parent_id"),
            "status": target_status,
            "source_refs_added": added_refs,
            "receipt_path": receipt_path,
            "token_usage_text": "Token usage: no agent invocation",
            "created_at": now_iso(),
        }
        append_jsonl(root / EVENTS_PATH, record)
        events.append(record)
        append_no_agent_token_line(root, item, "step_advanced")
        actions.append(record)

    notification_actions = process_notifications(root, items, events, send_telegram=send_telegram, now=current_time)
    save_items(root, items)
    return {
        "success": True,
        "advanced": actions,
        "notifications": notification_actions,
        "token_usage_text": "Token usage: no agent invocation",
    }


def load_notifications(root: Path) -> dict:
    path = root / NOTIFICATIONS_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    escalation = data.get("escalation") if isinstance(data.get("escalation"), dict) else {}
    allowlist = data.get("allowlist") if isinstance(data.get("allowlist"), dict) else {}
    return {
        "unanswered_minutes": int(escalation.get("unanswered_minutes") or 10),
        "telegram": [str(value) for value in allowlist.get("telegram") or []],
        "agentmail_internal": [str(value) for value in allowlist.get("agentmail_internal") or []],
    }


def log_notification_receipt(root: Path, item: dict, kind: str, status: str, result: str, detail: str) -> str:
    path = write_receipt(root, str(item.get("id")), kind, [
        "PASS" if result in {"logged", "sent", "blocked"} else "NEEDS ATTENTION",
        "",
        "Notification action:",
        f"- Event: {kind}",
        f"- Work item ID: {item.get('id')}",
        f"- Status: {status}",
        f"- Result: {result}",
        f"- Detail: {detail}",
        "- Token usage: no agent invocation",
    ])
    item.setdefault("receipts", []).append({"path": path, "created_at": now_iso(), "status": status})
    return path


def process_notifications(
    root: Path,
    items: list[dict],
    events: list[dict],
    *,
    send_telegram: Callable[[str, str], Any] | None,
    now: datetime,
) -> list[dict]:
    config = load_notifications(root)
    actions = []
    for item in items:
        item_id = str(item.get("id") or "")
        status = str(item.get("status") or "")
        if status not in ATTENTION_STATUSES:
            continue
        for channel in ("originating_channel", "needs_me_rail"):
            key = f"{status}:{channel}"
            if event_exists(events, "notification_logged", item_id, key):
                continue
            receipt_path = log_notification_receipt(root, item, "notification", status, "logged", channel)
            record = {
                "event": "notification_logged",
                "item_id": item_id,
                "key": key,
                "status": status,
                "channel": channel,
                "receipt_path": receipt_path,
                "created_at": now_iso(),
            }
            append_jsonl(root / EVENTS_PATH, record)
            events.append(record)
            append_no_agent_token_line(root, item, "notification_logged")
            actions.append(record)

        origin_key = f"{status}:originating_channel"
        origin_event = latest_event(events, "notification_logged", item_id, origin_key)
        origin_logged_at = parse_iso(origin_event.get("created_at") if origin_event else None)
        if not origin_logged_at:
            continue
        age = now - origin_logged_at.astimezone(timezone.utc)
        if age < timedelta(minutes=config["unanswered_minutes"]):
            continue
        recipient = config["telegram"][0] if config["telegram"] else ""
        key = f"{status}:telegram_operator"
        if _telegram_prior_send_event(events, item_id, key, recipient):
            continue
        message = f"Agentic OS needs attention: {item_id} {status} - {item.get('title')}"
        record = attempt_telegram_send(root, item, recipient, message, send_telegram=send_telegram, key=key)
        append_jsonl(root / EVENTS_PATH, record)
        events.append(record)
        append_no_agent_token_line(root, item, "telegram_escalation")
        actions.append(record)
    return actions


def default_bridge_send(chat_id: str, text: str) -> None:
    import importlib.util

    root = aos_root()
    bridge_path = root / "connectors" / "telegram_bridge" / "telegram_bridge.py"
    spec = importlib.util.spec_from_file_location("aos_telegram_bridge", bridge_path)
    if spec is None or spec.loader is None:
        raise OrchestrationError("telegram bridge send path unavailable")
    bridge = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(bridge)
    except RuntimeError as exc:
        if ".env file not found" not in str(exc):
            raise
        source = bridge_path.read_text(encoding="utf-8")
        source = re.sub(r"^WORKSPACE = .*$", f"WORKSPACE = Path({str(root)!r})", source, count=1, flags=re.MULTILINE)
        exec(compile(source, str(bridge_path), "exec"), bridge.__dict__)
    send_result = {"ok": True, "error": None}
    bridge_api = bridge.api

    def tracking_api(method, data=None, timeout=60):
        try:
            return bridge_api(method, data, timeout)
        except Exception as exc:
            send_result["ok"] = False
            send_result["error"] = type(exc).__name__
            raise

    bridge.api = tracking_api
    bridge.send(chat_id, text, preserve_format=True)
    if not send_result["ok"]:
        raise OrchestrationError(str(send_result["error"] or "send_failed"))


def attempt_telegram_send(
    root: Path,
    item: dict,
    recipient: str,
    message: str,
    *,
    send_telegram: Callable[[str, str], Any] | None = None,
    key: str = "",
) -> dict:
    config = load_notifications(root)
    item_id = str(item.get("id") or "")
    recipient = str(recipient)
    stable_key = telegram_idempotency_key(item_id, "telegram_escalation", key, recipient)
    if str(recipient) not in set(config["telegram"]):
        receipt_path = log_notification_receipt(root, item, "telegram-escalation", str(item.get("status") or ""), "blocked", f"recipient_not_allowlisted:{recipient}")
        return {
            "event": "telegram_escalation",
            "item_id": item_id,
            "key": key,
            "recipient": recipient,
            "idempotency_key": stable_key,
            "result": "blocked",
            "sent": False,
            "reason": "recipient_not_allowlisted",
            "receipt_path": receipt_path,
            "created_at": now_iso(),
        }
    prior = _telegram_prior_send_event(read_jsonl(root / EVENTS_PATH), item_id, key, recipient)
    if prior:
        return {
            "event": "telegram_escalation",
            "item_id": item_id,
            "key": key,
            "recipient": recipient,
            "idempotency_key": stable_key,
            "result": "already_sent",
            "sent": False,
            "duplicate_blocked": True,
            "prior_receipt_path": prior.get("receipt_path"),
            "prior_created_at": prior.get("created_at"),
            "created_at": now_iso(),
        }
    sender = send_telegram or default_bridge_send
    try:
        sender(recipient, message)
    except Exception as exc:
        receipt_path = log_notification_receipt(root, item, "telegram-escalation", str(item.get("status") or ""), "send_failed", type(exc).__name__)
        return {
            "event": "telegram_escalation",
            "item_id": item_id,
            "key": key,
            "recipient": recipient,
            "idempotency_key": stable_key,
            "result": "send_failed",
            "sent": False,
            "error": type(exc).__name__,
            "receipt_path": receipt_path,
            "created_at": now_iso(),
        }
    receipt_path = log_notification_receipt(root, item, "telegram-escalation", str(item.get("status") or ""), "sent", f"recipient:{recipient}")
    return {
        "event": "telegram_escalation",
        "item_id": item_id,
        "key": key,
        "recipient": recipient,
        "idempotency_key": stable_key,
        "result": "sent",
        "sent": True,
        "duplicate_blocked": False,
        "bridge_function": "connectors.telegram_bridge.telegram_bridge.send",
        "receipt_path": receipt_path,
        "created_at": now_iso(),
    }
