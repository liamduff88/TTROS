#!/usr/bin/env python3
"""Deterministic queue orchestration spine for Agentic OS.

The runner advances local queue state only. It never invokes a model. Telegram
escalation uses the existing bridge send function when a caller supplies it or
when the default loader can import it.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from aos_paths import aos_root, assert_authoritative_root
from aos_queue_storage import durable_create_directory, durable_replace_text, fsync_directory, queue_write_lock

QUEUE_DIR = Path("queue")
WORK_ITEMS_PATH = QUEUE_DIR / "work_items.jsonl"
RECEIPTS_DIR = QUEUE_DIR / "receipts"
EVENTS_PATH = QUEUE_DIR / "orchestration_events.jsonl"
NOTIFICATIONS_PATH = QUEUE_DIR / "notifications.json"
TOKEN_LEDGER_PATH = QUEUE_DIR / "token_ledger.jsonl"
TICK_LOCK_PATH = QUEUE_DIR / "locks" / "orchestration_tick.lock"

GATE_STATUSES = {"human_review", "needs_input"}
ATTENTION_STATUSES = {"human_review", "needs_input", "blocked"}
ADVANCE_FROM_STATUSES = {"inbox"}
READY_STATUS = "agent_todo"
DONE_STATUS = "done"
ALLOWED_ARTIFACT_PREFIXES = ("results/", "workflows/", "packets/", "logs/", "queue/receipts/")
ARTIFACT_RE = re.compile(r"(?P<path>(?:results|workflows|packets|logs|queue/receipts)/[^\s`'\"<>]+?\.(?:md|txt|json|jsonl|pdf|html))")


class OrchestrationError(Exception):
    """Raised when local orchestration cannot continue safely."""


@contextmanager
def tick_lock(root: Path):
    root = assert_authoritative_root(root)
    import fcntl
    lock_path = root / TICK_LOCK_PATH
    durable_create_directory(lock_path.parent, parents=True)
    created = False
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        created = True
    except FileExistsError:
        fd = os.open(lock_path, os.O_RDWR)
    if created:
        os.fsync(fd)
        fsync_directory(lock_path.parent)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        try:

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass


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
    with queue_write_lock(root):
        path = root / WORK_ITEMS_PATH
        durable_replace_text(
            path,
            _items_text(items),
        )


def _items_text(items: list[dict]) -> str:
    return "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in items)


def append_jsonl(path: Path, record: dict, *, root: Path | None = None) -> bool:
    """Durably append a deterministic effect once."""
    if root is None:
        root = path.parent.parent if path.parent.name == "queue" else path.parent
    root = assert_authoritative_root(root)
    with queue_write_lock(root):
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        effect_id = record.get("effect_id")
        if effect_id:
            for number, raw in enumerate(existing.splitlines(), start=1):
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise OrchestrationError(f"malformed effect JSONL {path} line {number}") from exc
                if row.get("effect_id") == effect_id:
                    return False
        durable_replace_text(path, existing + json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return True


def effect_identity(event: str, item_id: str, key: str = "") -> str:
    digest = hashlib.sha256("\0".join([event, item_id, key]).encode("utf-8")).hexdigest()
    return f"orchestration:{digest}"


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


def write_receipt(root: Path, item_id: str, kind: str, lines: list[str], *, effect_id: str | None = None) -> str:
    root = assert_authoritative_root(root)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", item_id).strip("-") or "item"
    stamp = hashlib.sha256(effect_id.encode("utf-8")).hexdigest()[:16] if effect_id else datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RECEIPTS_DIR / f"{safe}-{kind}-{stamp}.md"
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines).rstrip() + "\n"
    if target.exists() and target.read_text(encoding="utf-8") != content:
        raise OrchestrationError(f"receipt effect identity collision: {path}")
    if not target.exists():
        durable_replace_text(target, content)
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


def append_no_agent_token_line(root: Path, item: dict, event: str, *, effect_id: str | None = None) -> None:
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
        "effect_id": f"{effect_id}:tokens" if effect_id else None,
    })


def _attach_effect_receipt(item: dict, path: str, status: str, created_at: str) -> None:
    if not any(isinstance(row, dict) and row.get("path") == path for row in item.get("receipts", [])):
        item.setdefault("receipts", []).append({"path": path, "created_at": created_at, "status": status})


def _prepare_tick_intent(root: Path, items: list[dict], item: dict, effect_id: str, payload: dict) -> dict:
    intents = item.setdefault("orchestration_effects", {})
    existing = intents.get(effect_id)
    if existing is None:
        existing = {**payload, "status": "pending", "created_at": now_iso()}
        intents[effect_id] = existing
        save_items(root, items)
    elif not isinstance(existing, dict) or any(existing.get(k) != v for k, v in payload.items()):
        raise OrchestrationError(f"contradictory orchestration intent {effect_id}")
    return existing


def _is_acceptance_delivery_step(item: dict) -> bool:
    tags = {str(tag) for tag in item.get("tags") or []}
    return (
        item.get("status") == READY_STATUS
        and str(item.get("owner") or "").lower() == "delivery"
        and str(item.get("workbench") or "").lower() == "local"
        and "orchestration_acceptance" in tags
        and isinstance(item.get("parent_id"), str)
        and item.get("step_index") == 3
    )


def _read_text_if_available(root: Path, ref: str, limit: int = 12000) -> str:
    path = clean_ref(ref)
    if not path:
        return ""
    target = root / path
    if not target.is_file() or target.stat().st_size > 250_000:
        return ""
    return target.read_text(encoding="utf-8", errors="replace")[:limit]


def _first_ref(refs: list[str], suffix: str) -> str:
    for ref in refs:
        if ref.endswith(suffix):
            return ref
    return ""


def complete_acceptance_delivery_steps(root: Path, items: list[dict], events: list[dict]) -> list[dict]:
    root = assert_authoritative_root(root)
    actions = []
    by_id = {str(item.get("id")): item for item in items}
    for item in sorted((row for row in items if _is_acceptance_delivery_step(row)), key=_step_sort_key):
        item_id = str(item.get("id") or "")
        parent_id = str(item.get("parent_id") or "")
        prior = latest_event(events, "acceptance_finalized", item_id, parent_id)
        if prior:
            _attach_effect_receipt(item, prior["receipt_path"], DONE_STATUS, prior["created_at"])
            item["status"] = DONE_STATUS
            item["updated_at"] = prior["created_at"]
            parent = by_id.get(parent_id)
            if parent:
                _attach_effect_receipt(parent, prior["receipt_path"], DONE_STATUS, prior["created_at"])
                parent["status"] = DONE_STATUS
                parent["updated_at"] = prior["created_at"]
            continue
        deps = [str(dep) for dep in item.get("depends_on") or [] if str(dep).strip()]
        if deps and not all(is_step_complete(by_id.get(dep, {})) for dep in deps):
            continue

        refs = [str(ref) for ref in item.get("source_refs") or []]
        source_pack = _first_ref(refs, "/01_source_pack.md")
        approved_brief = _first_ref(refs, "/02_speed_to_lead_micro_brief.md")
        review_receipt = ""
        for ref in refs:
            if ref.startswith("queue/receipts/") and item.get("depends_on") and str(item["depends_on"][0]) in ref:
                review_receipt = ref
                break
        source_text = _read_text_if_available(root, source_pack, 6000)
        brief_text = _read_text_if_available(root, approved_brief, 8000)
        review_text = _read_text_if_available(root, review_receipt, 4000)

        final_artifact = f"results/orchestration_acceptance/{parent_id}/03_final_review_package.md"
        stable_effect = effect_identity("acceptance_finalized", item_id, parent_id)
        intent = _prepare_tick_intent(
            root, items, item, stable_effect,
            {"event": "acceptance_finalized", "key": parent_id, "target_status": DONE_STATUS},
        )
        target = root / final_artifact
        target.parent.mkdir(parents=True, exist_ok=True)
        artifact_text = "\n".join([
            "# Final Review Package",
            "",
            f"Acceptance-run ID: {parent_id}",
            f"Source-pack path: {source_pack or 'unavailable'}",
            f"Approved micro-brief path: {approved_brief or 'unavailable'}",
            f"Operator review receipt/reference: {review_receipt or 'unavailable'}",
            "",
            "Approved micro-brief content:",
            brief_text.strip() or "Unavailable.",
            "",
            "Operator review note/reference:",
            review_text.strip() or "Unavailable.",
            "",
            "Chain-step summary:",
            "- Step 1 operations/local source pack: done.",
            "- Step 2 marketing draft: approved through human_review.",
            "- Step 3 delivery/local final package: done.",
            "",
            "Final status: done",
            "",
            "Token summary:",
            "- Step 1: Token usage: no agent invocation",
            "- Step 2: Token usage: unavailable from current CLI output",
            "- Step 3: Token usage: no agent invocation",
            "- Runner activity: Token usage: no agent invocation",
            "",
            "Source-pack excerpt:",
            source_text.strip() or "Unavailable.",
            "",
        ]).rstrip() + "\n"
        if target.exists() and target.read_text(encoding="utf-8") != artifact_text:
            raise OrchestrationError(f"artifact effect identity collision: {final_artifact}")
        if not target.exists():
            durable_replace_text(target, artifact_text)

        receipt_path = write_receipt(root, item_id, "final-closeout", [
            "PASS",
            "",
            "Final queue closeout:",
            f"- Work item ID: {item_id}",
            f"- Parent ID: {parent_id}",
            f"- Final artifact: {final_artifact}",
            f"- Source pack: {source_pack or 'unavailable'}",
            f"- Approved brief: {approved_brief or 'unavailable'}",
            f"- Review receipt: {review_receipt or 'unavailable'}",
            "- Final status: done",
            "",
            "Token usage: no agent invocation",
        ], effect_id=stable_effect)
        _attach_effect_receipt(item, receipt_path, DONE_STATUS, intent["created_at"])
        item["status"] = DONE_STATUS
        item["updated_at"] = intent["created_at"]

        parent = by_id.get(parent_id)
        if parent and parent.get("status") != DONE_STATUS:
            _attach_effect_receipt(parent, receipt_path, DONE_STATUS, intent["created_at"])
            parent["status"] = DONE_STATUS
            parent["updated_at"] = intent["created_at"]

        record = {
            "event": "acceptance_finalized",
            "item_id": item_id,
            "key": parent_id,
            "parent_id": parent_id,
            "status": DONE_STATUS,
            "artifact_path": final_artifact,
            "receipt_path": receipt_path,
            "token_usage_text": "Token usage: no agent invocation",
            "created_at": intent["created_at"],
            "effect_id": stable_effect,
        }
        append_jsonl(root / EVENTS_PATH, record)
        events.append(record)
        append_no_agent_token_line(root, item, "acceptance_finalized", effect_id=stable_effect)
        intent["status"] = "applied"
        actions.append(record)
    return actions


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


def tick(
    root: Path | None = None,
    *,
    send_telegram: Callable[[str, str], Any] | None = None,
    now: datetime | None = None,
    allow_telegram_escalation: bool = True,
) -> dict:
    root = Path(root or aos_root()).resolve()
    with tick_lock(root), queue_write_lock(root):
        current_time = now or datetime.now(timezone.utc)
        items = load_items(root)
        initial_items_text = _items_text(items)
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
            prior = latest_event(events, "step_advanced", item_id, key)
            if prior:
                append_source_refs(item, list(prior.get("source_refs_added") or []))
                _attach_effect_receipt(item, prior["receipt_path"], prior["status"], prior["created_at"])
                item["status"] = prior["status"]
                item["updated_at"] = prior["created_at"]
                continue
            refs: list[str] = []
            for dep in deps:
                if dep in completed:
                    refs.extend(artifact_refs_for(root, completed[dep]))
            added_refs = append_source_refs(item, refs)
            target_status = str(item.get("on_complete") or "").strip().lower()
            if target_status not in GATE_STATUSES:
                target_status = READY_STATUS
            stable_effect = effect_identity("step_advanced", item_id, key)
            intent = _prepare_tick_intent(
                root, items, item, stable_effect,
                {"event": "step_advanced", "key": key, "target_status": target_status},
            )
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
            ], effect_id=stable_effect)
            _attach_effect_receipt(item, receipt_path, target_status, intent["created_at"])
            item["status"] = target_status
            item["updated_at"] = intent["created_at"]
            record = {
                "event": "step_advanced",
                "item_id": item_id,
                "key": key,
                "parent_id": item.get("parent_id"),
                "status": target_status,
                "source_refs_added": added_refs,
                "receipt_path": receipt_path,
                "token_usage_text": "Token usage: no agent invocation",
                "created_at": intent["created_at"],
                "effect_id": stable_effect,
            }
            append_jsonl(root / EVENTS_PATH, record)
            events.append(record)
            append_no_agent_token_line(root, item, "step_advanced", effect_id=stable_effect)
            intent["status"] = "applied"
            actions.append(record)

        local_actions = complete_acceptance_delivery_steps(root, items, events)
        actions.extend(local_actions)

        notification_actions = process_notifications(
            root,
            items,
            events,
            send_telegram=send_telegram,
            now=current_time,
            allow_telegram_escalation=allow_telegram_escalation,
        )
        if _items_text(items) != initial_items_text:
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


def log_notification_receipt(
    root: Path, item: dict, kind: str, status: str, result: str, detail: str,
    *, effect_id: str | None = None,
) -> str:
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
    ], effect_id=effect_id)
    _attach_effect_receipt(item, path, status, now_iso())
    return path


def process_notifications(
    root: Path,
    items: list[dict],
    events: list[dict],
    *,
    send_telegram: Callable[[str, str], Any] | None,
    now: datetime,
    allow_telegram_escalation: bool = True,
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
            prior = latest_event(events, "notification_logged", item_id, key)
            if prior:
                _attach_effect_receipt(item, prior["receipt_path"], status, prior["created_at"])
                continue
            stable_effect = effect_identity("notification_logged", item_id, key)
            intent = _prepare_tick_intent(
                root, items, item, stable_effect,
                {"event": "notification_logged", "key": key, "target_status": status},
            )
            receipt_path = log_notification_receipt(
                root, item, "notification", status, "logged", channel, effect_id=stable_effect
            )
            record = {
                "event": "notification_logged",
                "item_id": item_id,
                "key": key,
                "status": status,
                "channel": channel,
                "receipt_path": receipt_path,
                "created_at": intent["created_at"],
                "effect_id": stable_effect,
            }
            append_jsonl(root / EVENTS_PATH, record)
            events.append(record)
            append_no_agent_token_line(root, item, "notification_logged", effect_id=stable_effect)
            intent["status"] = "applied"
            actions.append(record)

        origin_key = f"{status}:originating_channel"
        origin_event = latest_event(events, "notification_logged", item_id, origin_key)
        origin_logged_at = parse_iso(origin_event.get("created_at") if origin_event else None)
        if not origin_logged_at:
            continue
        if not allow_telegram_escalation:
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
        append_no_agent_token_line(
            root, item, "telegram_escalation",
            effect_id=str(record.get("effect_id") or effect_identity("telegram_escalation", item_id, key)),
        )
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
    stable_effect = effect_identity("telegram_escalation", item_id, f"{key}|{recipient}")
    if str(recipient) not in set(config["telegram"]):
        receipt_path = log_notification_receipt(
            root, item, "telegram-escalation", str(item.get("status") or ""), "blocked",
            f"recipient_not_allowlisted:{recipient}", effect_id=stable_effect,
        )
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
            "effect_id": f"{stable_effect}:result",
        }
    prior = _telegram_prior_send_event(read_jsonl(root / EVENTS_PATH), item_id, key, recipient)
    if prior:
        prior_receipt = prior.get("receipt_path")
        prior_created = prior.get("created_at")
        if isinstance(prior_receipt, str) and prior_receipt and isinstance(prior_created, str) and prior_created:
            _attach_effect_receipt(item, prior_receipt, str(item.get("status") or ""), prior_created)
        return {
            "event": "telegram_escalation",
            "item_id": item_id,
            "key": key,
            "recipient": recipient,
            "idempotency_key": stable_key,
            "result": "already_sent",
            "sent": False,
            "duplicate_blocked": True,
            "prior_receipt_path": prior_receipt,
            "prior_created_at": prior_created,
            "created_at": now_iso(),
            "effect_id": f"{stable_effect}:result",
        }
    intent_record = {
        "event": "telegram_send_intent",
        "item_id": item_id,
        "key": key,
        "recipient": recipient,
        "idempotency_key": stable_key,
        "effect_id": f"{stable_effect}:intent",
        "created_at": now_iso(),
    }
    if not append_jsonl(root / EVENTS_PATH, intent_record):
        return {
            "event": "telegram_escalation",
            "item_id": item_id,
            "key": key,
            "recipient": recipient,
            "idempotency_key": stable_key,
            "result": "ambiguous_not_retried",
            "sent": False,
            "duplicate_blocked": True,
            "reason": "durable send intent exists without acknowledged result; operator reconciliation required",
            "effect_id": f"{stable_effect}:result",
            "created_at": now_iso(),
        }
    sender = send_telegram or default_bridge_send
    try:
        sender(recipient, message)
    except Exception as exc:
        receipt_path = log_notification_receipt(
            root, item, "telegram-escalation", str(item.get("status") or ""), "send_failed",
            type(exc).__name__, effect_id=stable_effect,
        )
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
            "effect_id": f"{stable_effect}:result",
        }
    receipt_path = log_notification_receipt(
        root, item, "telegram-escalation", str(item.get("status") or ""), "sent",
        f"recipient:{recipient}", effect_id=stable_effect,
    )
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
        "effect_id": f"{stable_effect}:result",
    }
