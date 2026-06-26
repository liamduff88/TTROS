"""Append-only local JSONL persistence."""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

RUNTIME_DATA_FILES = {
    "sales_logs": Path("data/sales_logs.jsonl"),
    "events": Path("data/events.jsonl"),
    "report_archive": Path("data/report_archive.jsonl"),
    "local_state": Path("data/local_state.json"),
}


class LocalJsonlStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    def records(self) -> Iterable[dict[str, Any]]:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"Invalid JSONL at line {line_number}") from exc

    def update_first(self, predicate: Callable[[dict[str, Any]], bool], replacement: dict[str, Any]) -> bool:
        """Atomically replace one JSONL object while preserving record order."""
        records = list(self.records())
        for index, record in enumerate(records):
            if predicate(record):
                records[index] = replacement
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.path.with_suffix(self.path.suffix + ".tmp")
                with temporary.open("w", encoding="utf-8") as handle:
                    for item in records:
                        handle.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
                temporary.replace(self.path)
                return True
        return False


class LocalStateStore:
    """Small JSON state file for package-local bot registration state."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"groups": {}}
        with self.path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("Local state must be a JSON object")
        return data

    def set_group(self, group_type: str, chat_id: str | int) -> None:
        if group_type not in {"admin_group", "broadcast_group"}:
            raise ValueError("Unsupported group type")
        state = self.read()
        groups = state.setdefault("groups", {})
        groups[f"{group_type}_chat_id"] = str(chat_id)
        self._write(state)

    def update_user_profile(self, telegram_user_id: str | int, profile: dict[str, Any]) -> None:
        """Merge non-secret Telegram identity fields into portable local state."""
        user_id = str(telegram_user_id)
        state = self.read()
        users = state.setdefault("users", {})
        current = users.setdefault(user_id, {"telegram_user_id": user_id})
        current["telegram_user_id"] = user_id
        for field in ("first_name", "last_name", "username"):
            value = profile.get(field)
            if isinstance(value, str) and value.strip():
                current[field] = value.strip()
        self._write(state)

    def user_profiles(self) -> dict[str, dict[str, Any]]:
        users = self.read().get("users", {})
        if not isinstance(users, dict):
            return {}
        return {str(user_id): dict(profile) for user_id, profile in users.items() if isinstance(profile, dict)}

    def user_display_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        for user_id, profile in self.user_profiles().items():
            explicit = profile.get("display_name")
            full_name = " ".join(
                value.strip()
                for value in (profile.get("first_name"), profile.get("last_name"))
                if isinstance(value, str) and value.strip()
            )
            username = profile.get("username")
            if isinstance(explicit, str) and explicit.strip():
                names[user_id] = explicit.strip()
            elif full_name:
                names[user_id] = full_name
            elif isinstance(username, str) and username.strip():
                names[user_id] = "@" + username.strip().lstrip("@")
        return names

    def role_for(self, telegram_user_id: str | int) -> str | None:
        user = self.user_profiles().get(str(telegram_user_id))
        if not user or user.get("active") is not True:
            return None
        role = user.get("role")
        return role if role in {"admin", "manager", "salesperson"} else None

    def user_status(self, telegram_user_id: str | int) -> dict[str, Any] | None:
        user_id = str(telegram_user_id)
        user = self.user_profiles().get(user_id)
        if not user:
            return None
        role = self.role_for(user_id)
        if role is None:
            return None
        display_name = user.get("display_name") or self.user_display_names().get(user_id)
        return {
            "telegram_user_id": user_id,
            "role": role,
            "display_name": display_name or "Registered user",
            "salesperson_id": user.get("salesperson_id"),
        }

    def register_salesperson(
        self,
        display_name: str,
        *,
        telegram_user_id: str | int | None = None,
    ) -> dict[str, Any]:
        """Create or reactivate a portable package-local roster record."""
        name = " ".join(display_name.split())
        if not name:
            raise ValueError("Display name is required")
        state = self.read()
        salesperson_id = self._unique_salesperson_id(name, state.get("salespeople", {}), telegram_user_id)
        salespeople = state.setdefault("salespeople", {})
        existing = salespeople.get(salesperson_id, {})
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        record: dict[str, Any] = {
            "salesperson_id": salesperson_id,
            "display_name": name,
            "active": True,
            "created_at": existing.get("created_at") or timestamp,
            "updated_at": timestamp,
        }
        linked_id = telegram_user_id if telegram_user_id is not None else existing.get("telegram_user_id")
        if linked_id is not None:
            record["telegram_user_id"] = str(linked_id)
        salespeople[salesperson_id] = record
        self._write(state)
        return dict(record)

    def create_invite(
        self,
        *,
        role: str,
        display_name: str,
        created_by: str | int,
        expires_days: int = 14,
    ) -> dict[str, Any]:
        if role not in {"manager", "salesperson"}:
            raise ValueError("Invites can only be created for managers or salespeople.")
        name = " ".join(display_name.split())
        if not name:
            raise ValueError("Please include a display name.")
        state = self.read()
        invites = state.setdefault("invites", {})
        code = self._new_invite_code(invites)
        now = datetime.now(timezone.utc)
        record = {
            "code": code,
            "role": role,
            "display_name": name,
            "status": "pending",
            "created_by": str(created_by),
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(days=expires_days)).isoformat().replace("+00:00", "Z"),
        }
        invites[code] = record
        self._write(state)
        return dict(record)

    def pending_invites(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        result = []
        for record in self.read().get("invites", {}).values():
            if not isinstance(record, dict) or record.get("status") != "pending":
                continue
            expires_at = self._parse_timestamp(record.get("expires_at"))
            if expires_at is not None and expires_at <= now:
                continue
            result.append(dict(record))
        return sorted(result, key=lambda item: (str(item.get("expires_at", "")), str(item.get("display_name", ""))))

    def revoke_invite(self, code: str) -> dict[str, Any] | None:
        normalized = self._normalize_invite_code(code)
        state = self.read()
        invites = state.get("invites", {})
        if not isinstance(invites, dict):
            return None
        record = invites.get(normalized)
        if not isinstance(record, dict) or record.get("status") != "pending":
            return None
        record["status"] = "revoked"
        record["revoked_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._write(state)
        return dict(record)

    def redeem_invite(self, code: str, telegram_user_id: str | int) -> tuple[str, dict[str, Any] | None]:
        normalized = self._normalize_invite_code(code)
        state = self.read()
        invites = state.setdefault("invites", {})
        record = invites.get(normalized)
        if not isinstance(record, dict):
            return "not_found", None
        if record.get("status") != "pending":
            status = str(record.get("status") or "used")
            return "already_redeemed" if status == "redeemed" else status, dict(record)
        expires_at = self._parse_timestamp(record.get("expires_at"))
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            record["status"] = "expired"
            self._write(state)
            return "expired", dict(record)

        user_id = str(telegram_user_id)
        role = record.get("role")
        name = str(record.get("display_name") or "").strip()
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        users = state.setdefault("users", {})
        user = users.setdefault(user_id, {"telegram_user_id": user_id})
        user.update(
            {
                "telegram_user_id": user_id,
                "display_name": name,
                "role": role,
                "active": True,
                "updated_at": timestamp,
            }
        )
        if role == "salesperson":
            salesperson_id = self._unique_salesperson_id(name, state.get("salespeople", {}), user_id)
            user["salesperson_id"] = salesperson_id
            salespeople = state.setdefault("salespeople", {})
            existing = salespeople.get(salesperson_id, {})
            salespeople[salesperson_id] = {
                "salesperson_id": salesperson_id,
                "display_name": name,
                "active": True,
                "telegram_user_id": user_id,
                "created_at": existing.get("created_at") or timestamp,
                "updated_at": timestamp,
            }
        else:
            user.pop("salesperson_id", None)
        record["status"] = "redeemed"
        record["redeemed_by"] = user_id
        record["redeemed_at"] = timestamp
        self._write(state)
        return "redeemed", dict(user)

    def salespeople(self, *, active_only: bool = False) -> list[dict[str, Any]]:
        records = self.read().get("salespeople", {})
        if not isinstance(records, dict):
            return []
        result = [dict(record) for record in records.values() if isinstance(record, dict)]
        if active_only:
            result = [record for record in result if record.get("active") is True]
        return sorted(result, key=lambda record: (str(record.get("display_name", "")).casefold(), str(record.get("salesperson_id", ""))))

    def salesperson_roster(self) -> dict[str, str]:
        return {
            str(record["salesperson_id"]): str(record["display_name"])
            for record in self.salespeople(active_only=True)
            if record.get("salesperson_id") and record.get("display_name")
        }

    def deactivate_salesperson(self, identifier: str) -> dict[str, Any] | None:
        value = identifier.strip()
        if not value:
            raise ValueError("Display name or salesperson ID is required")
        state = self.read()
        salespeople = state.get("salespeople", {})
        if not isinstance(salespeople, dict):
            return None
        salesperson_id = next(
            (
                key
                for key, record in salespeople.items()
                if key == value
                or (isinstance(record, dict) and str(record.get("display_name", "")).casefold() == value.casefold())
            ),
            None,
        )
        if salesperson_id is None or not isinstance(salespeople[salesperson_id], dict):
            return None
        record = salespeople[salesperson_id]
        record["active"] = False
        record["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._write(state)
        return dict(record)

    @staticmethod
    def _salesperson_id(display_name: str) -> str:
        normalized = unicodedata.normalize("NFKD", display_name).encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
        if not slug:
            raise ValueError("Display name must contain letters or numbers")
        return slug

    def _unique_salesperson_id(
        self,
        display_name: str,
        salespeople: Any,
        telegram_user_id: str | int | None = None,
    ) -> str:
        base = self._salesperson_id(display_name)
        if not isinstance(salespeople, dict):
            return base
        linked_user_id = str(telegram_user_id) if telegram_user_id is not None else None
        existing = salespeople.get(base)
        if not isinstance(existing, dict) or linked_user_id is None or str(existing.get("telegram_user_id")) == linked_user_id:
            return base
        suffix = 2
        while f"{base}-{suffix}" in salespeople:
            candidate = salespeople[f"{base}-{suffix}"]
            if linked_user_id is not None and isinstance(candidate, dict) and str(candidate.get("telegram_user_id")) == linked_user_id:
                return f"{base}-{suffix}"
            suffix += 1
        return f"{base}-{suffix}"

    @staticmethod
    def _new_invite_code(invites: dict[str, Any]) -> str:
        while True:
            raw = uuid.uuid4().hex.upper()
            code = f"NS-{raw[:4]}-{int(raw[4:8], 16) % 10000:04d}"
            if code not in invites:
                return code

    @staticmethod
    def _normalize_invite_code(code: str) -> str:
        return code.strip().upper()

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None

    def pending_sales_log(self, telegram_user_id: str | int) -> dict[str, str] | None:
        pending = self.read().get("pending_sales_logs", {}).get(str(telegram_user_id))
        if not isinstance(pending, dict):
            return None
        log_id = pending.get("log_id")
        field = pending.get("field")
        if not isinstance(log_id, str) or not isinstance(field, str):
            return None
        return {"log_id": log_id, "field": field}

    def set_pending_sales_log(self, telegram_user_id: str | int, log_id: str, field: str) -> None:
        state = self.read()
        state.setdefault("pending_sales_logs", {})[str(telegram_user_id)] = {
            "log_id": str(log_id),
            "field": field,
        }
        self._write(state)

    def clear_pending_sales_log(self, telegram_user_id: str | int) -> None:
        state = self.read()
        pending = state.get("pending_sales_logs")
        if not isinstance(pending, dict) or str(telegram_user_id) not in pending:
            return
        del pending[str(telegram_user_id)]
        if not pending:
            state.pop("pending_sales_logs", None)
        self._write(state)

    def _write(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)
