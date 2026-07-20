#!/usr/bin/env python3
"""Run deterministic queue transitions and tagged asynchronous dispatch work.

Revisit: when queue claim or backend agent-timeout contracts change. · Last touched: 2026-07-18.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from aos_paths import aos_root
from aos_orchestration import (
    EVENTS_PATH,
    _invoke_telegram_sender,
    append_jsonl,
    default_bridge_send,
    load_items,
    prepare_telegram_send,
    record_telegram_send_result,
    save_items,
    tick,
)
from aos_queue_storage import queue_write_lock

ASYNC_DISPATCH_TAG = "async_dispatch"
BACKEND_URL = os.environ.get("AOS_BACKEND_URL", "http://127.0.0.1:8010").rstrip("/")
DEFAULT_STARTUP_TIMEOUT_SECONDS = 60
DEFAULT_EXECUTION_TIMEOUT_SECONDS = 7800
DEFAULT_REVIEW_TIMEOUT_SECONDS = 120
DEFAULT_FINALIZATION_TIMEOUT_SECONDS = 120
DEFAULT_GRACEFUL_TERMINATION_SECONDS = 10


def _timeout_from_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, "") or default))
    except ValueError:
        return default


def next_async_item(root: Path) -> dict | None:
    tagged = [
        item for item in load_items(root)
        if item.get("owner_type") != "workflow"
        and ASYNC_DISPATCH_TAG in {str(tag) for tag in item.get("tags") or []}
    ]
    now = datetime.datetime.now(datetime.timezone.utc)
    lease_seconds = _timeout_from_env("AOS_AGENT_LEASE_SECONDS", 90)

    def heartbeat_age(item: dict) -> float | None:
        value = item.get("worker_heartbeat_at") or (item.get("claim") or {}).get("claimed_at") or item.get("updated_at")
        try:
            parsed = datetime.datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        return max(0.0, (now - parsed.astimezone(datetime.timezone.utc)).total_seconds())

    def worker_runtime_live(item: dict) -> bool:
        runtime = item.get("worker_runtime")
        if not isinstance(runtime, dict):
            return False
        try:
            pid = int(runtime.get("pid"))
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
            fields = stat.rsplit(") ", 1)[1].split()
            actual_start_id = fields[19]
        except (OSError, TypeError, ValueError, IndexError):
            return False
        expected_start_id = str(runtime.get("process_start_id") or "")
        return bool(expected_start_id and actual_start_id == expected_start_id)

    abandoned = [
        item for item in tagged
        if item.get("status") == "agent_working"
        and (heartbeat_age(item) is None or heartbeat_age(item) >= lease_seconds)
        and not worker_runtime_live(item)
    ]
    ready = [item for item in tagged if item.get("status") == "agent_todo"]
    candidates = abandoned or ready
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (-int(item.get("priority", 0)), item.get("created_at", ""), item.get("id", "")))[0]


def dispatch_via_backend(item_id: str) -> dict:
    startup_timeout = _timeout_from_env("AOS_AGENT_STARTUP_TIMEOUT_SECONDS", DEFAULT_STARTUP_TIMEOUT_SECONDS)
    agent_timeout = _timeout_from_env("AOS_AGENT_TIMEOUT_SECONDS", DEFAULT_EXECUTION_TIMEOUT_SECONDS)
    review_timeout = _timeout_from_env("AOS_AGENT_REVIEW_TIMEOUT_SECONDS", DEFAULT_REVIEW_TIMEOUT_SECONDS)
    finalization_timeout = _timeout_from_env("AOS_AGENT_FINALIZATION_TIMEOUT_SECONDS", DEFAULT_FINALIZATION_TIMEOUT_SECONDS)
    graceful_timeout = _timeout_from_env("AOS_AGENT_GRACEFUL_TERMINATION_SECONDS", DEFAULT_GRACEFUL_TERMINATION_SECONDS)
    parent_timeout = startup_timeout + agent_timeout + graceful_timeout
    request_timeout = (parent_timeout + review_timeout) * 2 + finalization_timeout
    request = urllib.request.Request(
        f"{BACKEND_URL}/api/queue/items/{item_id}/run",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except TimeoutError:
        return {
            "success": False,
            "item_id": item_id,
            "state": "runner_backend_request_timeout",
            "reason": "backend request exceeded the complete two-attempt boundary",
            "command_stage": "runner_to_backend",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "timeout_seconds": request_timeout,
            "diagnostic_log": "logs/runtime/runner.log",
        }
    except urllib.error.HTTPError as exc:
        return {
            "success": False,
            "item_id": item_id,
            "state": "runner_backend_http_failure",
            "reason": f"HTTP {exc.code}",
            "command_stage": "runner_to_backend",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "diagnostic_log": "logs/runtime/backend.log",
        }
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {
            "success": False,
            "item_id": item_id,
            "state": "runner_unavailable",
            "reason": type(exc).__name__,
            "command_stage": "runner_to_backend",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "diagnostic_log": "logs/runtime/runner.log",
        }
    return payload if isinstance(payload, dict) else {
        "success": False,
        "item_id": item_id,
        "state": "invalid_runner_response",
    }


def dispatch_via_executor(root: Path, item_id: str) -> dict:
    """Start one isolated queue executor that survives dashboard restarts."""
    env = os.environ.copy()
    env["AOS_ROOT"] = str(root)
    backend_python = root / "dashboard" / "backend" / ".venv" / "bin" / "python"
    executable = str(backend_python) if backend_python.is_file() and os.access(backend_python, os.X_OK) else sys.executable
    log_path = root / "logs" / "runtime" / f"queue-executor-{item_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("ab") as log_handle:
            process = subprocess.Popen(
                [executable, str(Path(__file__).resolve()), "--root", str(root), "--execute-item", item_id],
                cwd=str(root),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
    except OSError as exc:
        return {
            "success": False,
            "item_id": item_id,
            "state": "executor_start_failed",
            "reason": type(exc).__name__,
        }
    return {
        "success": True,
        "item_id": item_id,
        "state": "executor_started",
        "executor_pid": process.pid,
        "executor_log": str(log_path.relative_to(root)),
    }


def execute_item(root: Path, item_id: str) -> dict:
    """Execute inside the detached supervisor, not the restartable backend."""
    module_path = root / "dashboard" / "backend" / "main.py"
    backend_dir = str(module_path.parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    spec = importlib.util.spec_from_file_location("aos_queue_executor_backend", module_path)
    if spec is None or spec.loader is None:
        return {"success": False, "item_id": item_id, "state": "backend_import_failed"}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run_queue_item(item_id)


def dispatch_next(root: Path, dispatch: Callable[[str], dict] | None = None) -> dict | None:
    item = next_async_item(root)
    if item is None:
        return None
    item_id = str(item.get("id") or "")
    return dispatch(item_id) if dispatch is not None else dispatch_via_executor(root, item_id)


def dispatch_item(root: Path, item_id: str, dispatch: Callable[[str], dict] | None = None) -> dict:
    item = next((row for row in load_items(root) if str(row.get("id") or "") == item_id), None)
    if item is None:
        return {"success": False, "item_id": item_id, "state": "not_found"}
    if ASYNC_DISPATCH_TAG not in {str(tag) for tag in item.get("tags") or []}:
        return {"success": False, "item_id": item_id, "state": "not_async_dispatch"}
    if item.get("status") not in {"agent_todo", "agent_working"}:
        return {"success": True, "item_id": item_id, "state": str(item.get("status") or "finished"), "already_finished": True}
    return dispatch(item_id) if dispatch is not None else dispatch_via_executor(root, item_id)


def run_manual_attempt(root: Path, item_id: str, recipient: str, message: str) -> dict:
    """Lock-owned manual notification mutation; never saves a stale snapshot.

    Same shape as aos_orchestration.tick: prepare under the queue write lock,
    release it for the network delivery, then re-acquire it only to record the
    outcome — a stalled bridge send must never hold the 5s-bounded lock.
    """
    with queue_write_lock(root):
        items = load_items(root)
        item = next((row for row in items if row.get("id") == item_id), None)
        if not item:
            raise SystemExit(f"item not found: {item_id}")
        prepared = prepare_telegram_send(root, item, recipient, message, key="manual_validation")
        if not prepared.get("ready"):
            result = prepared["record"]
            append_jsonl(root / EVENTS_PATH, result)
            save_items(root, items)
            return result
    delivery_result = None
    send_error = None
    try:
        delivery_result = _invoke_telegram_sender(
            default_bridge_send, prepared["recipient"], prepared["message"], prepared["document_paths"]
        )
    except Exception as exc:
        send_error = exc
    with queue_write_lock(root):
        items = load_items(root)
        target = next((row for row in items if row.get("id") == item_id), None) or prepared["item"]
        result = record_telegram_send_result(root, target, prepared, delivery_result, send_error=send_error)
        append_jsonl(root / EVENTS_PATH, result)
        save_items(root, items)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic local queue orchestration runner")
    parser.add_argument("--root", default=str(aos_root()), help="Repository root")
    parser.add_argument("--skip-telegram-escalation", action="store_true", help="Log Needs Me notifications without attempting Telegram escalation")
    parser.add_argument("--attempt-telegram", metavar="ITEM_ID", help="Validation helper: attempt one telegram send for an item")
    parser.add_argument("--dispatch-item", metavar="ITEM_ID", help="Dispatch one tagged async item without running the recurring orchestration tick")
    parser.add_argument("--execute-item", metavar="ITEM_ID", help=argparse.SUPPRESS)
    parser.add_argument("--recipient", help="Recipient for --attempt-telegram")
    parser.add_argument("--message", default="Agentic OS validation send", help="Message for --attempt-telegram")
    parser.add_argument("--watch", action="store_true", help="Run the existing tick model continuously")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between watch-mode ticks")
    parser.add_argument("--max-ticks", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.attempt_telegram:
        result = run_manual_attempt(root, args.attempt_telegram, args.recipient or "", args.message)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("result") in {"sent", "already_sent", "blocked", "send_failed"} else 1
    if args.execute_item:
        result = execute_item(root, args.execute_item)
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        return 0 if result.get("success") or result.get("status") in {"blocked", "human_review", "done", "needs_input"} else 1
    if args.dispatch_item:
        result = dispatch_item(root, args.dispatch_item)
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        return 0 if result.get("success") or result.get("state") in {"blocked", "human_review", "done", "needs_input"} else 1
    count = 0
    while True:
        result = tick(root, allow_telegram_escalation=not args.skip_telegram_escalation)
        result["dispatch"] = dispatch_next(root)
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        count += 1
        if not args.watch or (args.max_ticks is not None and count >= args.max_ticks):
            break
        time.sleep(max(0.05, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
