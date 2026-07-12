#!/usr/bin/env python3
"""Run the deterministic Agentic OS orchestration runner."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from aos_paths import aos_root
from aos_orchestration import EVENTS_PATH, append_jsonl, attempt_telegram_send, save_items, tick
from aos_queue_storage import queue_write_lock


def run_manual_attempt(root: Path, item_id: str, recipient: str, message: str) -> dict:
    """Lock-owned manual notification mutation; never saves a stale snapshot."""
    from aos_orchestration import load_items

    with queue_write_lock(root):
        items = load_items(root)
        item = next((row for row in items if row.get("id") == item_id), None)
        if not item:
            raise SystemExit(f"item not found: {item_id}")
        result = attempt_telegram_send(root, item, recipient, message, key="manual_validation")
        append_jsonl(root / EVENTS_PATH, result)
        save_items(root, items)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic local queue orchestration runner")
    parser.add_argument("--root", default=str(aos_root()), help="Repository root")
    parser.add_argument("--skip-telegram-escalation", action="store_true", help="Log Needs Me notifications without attempting Telegram escalation")
    parser.add_argument("--attempt-telegram", metavar="ITEM_ID", help="Validation helper: attempt one telegram send for an item")
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
    count = 0
    while True:
        print(json.dumps(tick(root, allow_telegram_escalation=not args.skip_telegram_escalation), indent=2, sort_keys=True), flush=True)
        count += 1
        if not args.watch or (args.max_ticks is not None and count >= args.max_ticks):
            break
        time.sleep(max(0.05, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
