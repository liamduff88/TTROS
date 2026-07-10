#!/usr/bin/env python3
"""Run one deterministic Agentic OS orchestration tick."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aos_paths import aos_root
from aos_orchestration import EVENTS_PATH, append_jsonl, attempt_telegram_send, save_items, tick


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic local queue orchestration runner")
    parser.add_argument("--root", default=str(aos_root()), help="Repository root")
    parser.add_argument("--skip-telegram-escalation", action="store_true", help="Log Needs Me notifications without attempting Telegram escalation")
    parser.add_argument("--attempt-telegram", metavar="ITEM_ID", help="Validation helper: attempt one telegram send for an item")
    parser.add_argument("--recipient", help="Recipient for --attempt-telegram")
    parser.add_argument("--message", default="Agentic OS validation send", help="Message for --attempt-telegram")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.attempt_telegram:
        from aos_orchestration import load_items

        items = load_items(root)
        item = next((row for row in items if row.get("id") == args.attempt_telegram), None)
        if not item:
            raise SystemExit(f"item not found: {args.attempt_telegram}")
        result = attempt_telegram_send(root, item, args.recipient or "", args.message, key="manual_validation")
        append_jsonl(root / EVENTS_PATH, result)
        save_items(root, items)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("result") in {"sent", "already_sent", "blocked", "send_failed"} else 1
    print(json.dumps(tick(root, allow_telegram_escalation=not args.skip_telegram_escalation), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
