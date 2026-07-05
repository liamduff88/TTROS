"""Explicit package-local Liam admin recovery helper.

This script only updates the North Shore package's local state file by matching
the display name. It does not scan the filesystem or print Telegram IDs.
"""

from __future__ import annotations

from pathlib import Path

from src.admin_recovery import promote_by_name

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "data" / "local_state.json"
PROMOTE_NAME = "Liam Duff"


def main() -> int:
    try:
        matched = promote_by_name(STATE_PATH, PROMOTE_NAME, "admin")
    except ValueError as exc:
        print(str(exc))
        return 2
    if matched == 0:
        print(f"No local user matched {PROMOTE_NAME!r}.")
        return 1
    print(f"Updated {matched} local user record(s) for {PROMOTE_NAME!r} to admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
