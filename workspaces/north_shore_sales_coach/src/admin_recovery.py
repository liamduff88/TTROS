"""Local-only role recovery for package state.

This module intentionally prints no Telegram IDs, tokens, URLs, or customer data.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .local_store import LocalStateStore, ROLE_RANK

ROOT = Path(__file__).resolve().parents[1]


def _display_name(profile: dict[str, Any]) -> str:
    explicit = profile.get("display_name")
    if isinstance(explicit, str) and explicit.strip():
        return " ".join(explicit.split())
    full_name = " ".join(
        value.strip()
        for value in (profile.get("first_name"), profile.get("last_name"))
        if isinstance(value, str) and value.strip()
    )
    if full_name:
        return full_name
    username = profile.get("username")
    if isinstance(username, str) and username.strip():
        return "@" + username.strip().lstrip("@")
    return ""


def promote_by_name(path: str | Path, promote_name: str, role: str) -> int:
    if role not in ROLE_RANK:
        raise ValueError("Role must be admin, manager, or salesperson.")
    target = " ".join(promote_name.split()).casefold()
    if not target:
        raise ValueError("A display name is required.")

    store = LocalStateStore(path)
    state = store.read()
    users = state.get("users", {})
    if not isinstance(users, dict):
        return 0

    matched = 0
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for profile in users.values():
        if not isinstance(profile, dict):
            continue
        if _display_name(profile).casefold() != target:
            continue
        current_role = profile.get("role")
        if isinstance(current_role, str) and ROLE_RANK.get(current_role, 0) > ROLE_RANK[role]:
            matched += 1
            continue
        profile["role"] = role
        profile["active"] = True
        profile["updated_at"] = timestamp
        if role != "salesperson":
            profile.pop("salesperson_id", None)
        matched += 1

    if matched:
        store._write(state)
    return matched


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover a local North Shore user role by display name.")
    parser.add_argument("--promote-name", required=True, help="Display name to match exactly.")
    parser.add_argument("--role", required=True, choices=sorted(ROLE_RANK), help="Role to set.")
    parser.add_argument("--state-path", default=str(ROOT / "data" / "local_state.json"), help=argparse.SUPPRESS)
    args = parser.parse_args()

    try:
        matched = promote_by_name(args.state_path, args.promote_name, args.role)
    except ValueError as exc:
        print(str(exc))
        return 2
    if matched == 0:
        print(f"No local user matched {args.promote_name!r}.")
        return 1
    print(f"Updated {matched} local user record(s) for {args.promote_name!r} to {args.role}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
