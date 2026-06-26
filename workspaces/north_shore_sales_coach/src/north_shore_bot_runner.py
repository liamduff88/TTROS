"""Direct stdlib Telegram Bot API polling for the North Shore sub-bot only."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .command_router import CommandRouter
from .local_store import LocalJsonlStore, LocalStateStore
from .message_router import MessageRouter
from .natural_language_router import NaturalLanguageRouter
from .role_store import RoleStore

ROOT = Path(__file__).resolve().parents[1]


class TelegramBotApi:
    """Minimal direct Bot API client. The token is never logged."""

    def __init__(self, token: str):
        self._base_url = f"https://api.telegram.org/bot{token}/"

    def call(self, method: str, payload: dict[str, Any]) -> Any:
        body = urllib.parse.urlencode(
            {key: json.dumps(value) if isinstance(value, (list, dict)) else value for key, value in payload.items()}
        ).encode("utf-8")
        request = urllib.request.Request(self._base_url + method, data=body, method="POST")
        with urllib.request.urlopen(request, timeout=35) as response:
            result = json.load(response)
        if result.get("ok") is not True:
            raise RuntimeError("Telegram Bot API returned an unsuccessful response")
        return result.get("result")

    def get_updates(self, offset: int | None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": 25, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        result = self.call("getUpdates", payload)
        return result if isinstance(result, list) else []

    def send_text(self, chat_id: str | int, text: str) -> None:
        self.call("sendMessage", {"chat_id": chat_id, "text": text})


def build_message_router() -> MessageRouter:
    roles_path = ROOT / "config" / "roles.json"
    if not roles_path.exists():
        roles_path = ROOT / "config" / "roles.example.json"
    return MessageRouter(
        role_store=RoleStore(roles_path),
        command_router=CommandRouter.from_file(ROOT / "config" / "commands.json"),
        natural_language_router=NaturalLanguageRouter(llm_enabled=False),
        state_store=LocalStateStore(ROOT / "data" / "local_state.json"),
        events_store=LocalJsonlStore(ROOT / "data" / "events.jsonl"),
        sales_store=LocalJsonlStore(ROOT / "data" / "sales_logs.jsonl"),
        report_archive_store=LocalJsonlStore(ROOT / "data" / "report_archive.jsonl"),
        dashboard_url=os.getenv("NORTH_SHORE_DASHBOARD_URL"),
    )


def run_polling(api: TelegramBotApi, router: MessageRouter) -> None:
    offset: int | None = None
    while True:
        try:
            updates = api.get_updates(offset)
            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                reply = router.handle_update(update)
                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id") if isinstance(message, dict) else None
                if reply and chat_id is not None:
                    api.send_text(chat_id, reply)
        except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError, json.JSONDecodeError):
            print("North Shore Telegram polling error; retrying safely.", file=sys.stderr)
            time.sleep(3)


def main() -> int:
    token = os.getenv("NORTH_SHORE_TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("NORTH_SHORE_TELEGRAM_BOT_TOKEN is required; bot not started.", file=sys.stderr)
        return 2
    run_polling(TelegramBotApi(token), build_message_router())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
