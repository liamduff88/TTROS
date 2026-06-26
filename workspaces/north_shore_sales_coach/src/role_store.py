"""Local role map: the Phase 1 identity permission boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RoleStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._users: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        with self.path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        users = data.get("users", {})
        if not isinstance(users, dict):
            raise ValueError("Role map 'users' must be an object")
        self._users = users

    def role_for(self, user_id: str | int) -> str | None:
        user = self._users.get(str(user_id))
        if not user or user.get("active") is not True:
            return None
        role = user.get("role")
        return role if role in {"admin", "manager", "salesperson"} else None

    def is_authorized(self, user_id: str | int) -> bool:
        return self.role_for(user_id) is not None

    def salesperson_roster(self) -> dict[str, str]:
        """Return active salesperson IDs and local display names, when configured."""
        return {
            str(user.get("salesperson_id") or user_id): str(user.get("display_name") or "Unregistered salesperson")
            for user_id, user in self._users.items()
            if user.get("active") is True and user.get("role") == "salesperson"
        }

    def salesperson_identities(self) -> dict[str, dict[str, Any]]:
        return {
            str(user.get("salesperson_id") or user_id): {**user, "telegram_user_id": str(user_id)}
            for user_id, user in self._users.items()
            if user.get("active") is True and user.get("role") == "salesperson"
        }
