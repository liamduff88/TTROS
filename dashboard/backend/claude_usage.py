#!/usr/bin/env python3
"""Read aggregate Claude Code token counters without exposing transcript content."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo


TOKEN_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)


def _empty_counts() -> dict[str, int]:
    return {field: 0 for field in TOKEN_FIELDS} | {"total_tokens": 0}


def _add_counts(target: dict[str, int], usage: dict) -> None:
    for field in TOKEN_FIELDS:
        value = usage.get(field, 0)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            target[field] += value
            target["total_tokens"] += value


def read_claude_usage(claude_dir: Path, now: dt.datetime, timezone: str) -> dict:
    projects_dir = claude_dir / "projects"
    accuracy = "Exact local Claude Code transcript counters; includes cached input; not a billing estimate"
    if not projects_dir.is_dir():
        return {
            "available": False,
            "source": str(projects_dir),
            "accuracy_label": "Unavailable: Claude Code project JSONL directory not found",
        }

    zone = ZoneInfo(timezone)
    now = now.astimezone(zone)
    today = now.date()
    week_start = today - dt.timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    periods = {name: _empty_counts() for name in ("today", "week", "month")}
    messages: dict[tuple[str, str], dict] = {}
    latest_user_by_session: dict[str, dt.datetime] = {}
    files_read = 0

    for path in projects_dir.glob("*/*.jsonl"):
        files_read += 1
        try:
            lines = path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with lines:
            for line in lines:
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                session_id = record.get("sessionId")
                timestamp_text = record.get("timestamp")
                if not isinstance(session_id, str) or not isinstance(timestamp_text, str):
                    continue
                try:
                    timestamp = dt.datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if record.get("type") == "user":
                    previous = latest_user_by_session.get(session_id)
                    if previous is None or timestamp > previous:
                        latest_user_by_session[session_id] = timestamp
                    continue
                message = record.get("message")
                usage = message.get("usage") if isinstance(message, dict) else None
                if record.get("type") != "assistant" or not isinstance(usage, dict):
                    continue
                message_id = message.get("id")
                fallback_id = record.get("uuid")
                identity = message_id if isinstance(message_id, str) else fallback_id
                if not isinstance(identity, str):
                    continue
                key = (session_id, identity)
                existing = messages.get(key)
                if existing is None or timestamp > existing["timestamp"]:
                    messages[key] = {"session_id": session_id, "timestamp": timestamp, "usage": usage}

    if not messages:
        return {
            "available": False,
            "source": str(projects_dir / "*/*.jsonl"),
            "files_read": files_read,
            "accuracy_label": "Unavailable: no Claude Code usage counters found in local project JSONL",
        }

    latest_session_id = max(messages.values(), key=lambda item: item["timestamp"])["session_id"]
    latest_session = _empty_counts()
    latest_task = _empty_counts()
    latest_task_start = latest_user_by_session.get(latest_session_id)
    latest_timestamp = max(item["timestamp"] for item in messages.values())

    for item in messages.values():
        local_date = item["timestamp"].astimezone(zone).date()
        if local_date == today:
            _add_counts(periods["today"], item["usage"])
        if week_start <= local_date <= today:
            _add_counts(periods["week"], item["usage"])
        if month_start <= local_date <= today:
            _add_counts(periods["month"], item["usage"])
        if item["session_id"] == latest_session_id:
            _add_counts(latest_session, item["usage"])
            if latest_task_start is not None and item["timestamp"] >= latest_task_start:
                _add_counts(latest_task, item["usage"])

    return {
        "available": True,
        "source": str(projects_dir / "*/*.jsonl"),
        "accuracy_label": accuracy,
        "timezone": timezone,
        "files_read": files_read,
        "unique_usage_messages": len(messages),
        "today": periods["today"],
        "week": periods["week"],
        "month": periods["month"],
        "latest_session": latest_session,
        "latest_task_delta": latest_task if latest_task_start is not None else None,
        "latest_task_delta_label": (
            "Exact counters after the latest user record in the latest session"
            if latest_task_start is not None
            else "Unavailable: latest user record not found"
        ),
        "latest_usage_timestamp": latest_timestamp.isoformat().replace("+00:00", "Z"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--claude-dir", type=Path, default=Path.home() / ".claude")
    parser.add_argument("--timezone", default="America/Vancouver")
    args = parser.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    print(json.dumps(read_claude_usage(args.claude_dir, now, args.timezone), separators=(",", ":")))


if __name__ == "__main__":
    main()
