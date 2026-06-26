#!/usr/bin/env python3
"""Archive and clear package-local demo runtime data before Ryan onboarding."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = (
    Path("data/sales_logs.jsonl"),
    Path("data/report_archive.jsonl"),
    Path("data/events.jsonl"),
    Path("data/local_state.json"),
)
CLEAR_JSONL_FILES = (
    Path("data/sales_logs.jsonl"),
    Path("data/report_archive.jsonl"),
    Path("data/events.jsonl"),
)
DEMO_MARKERS = (
    "Dashboard Test Rep",
    "dashboard_test_rep",
    "Demo Rep",
    "demo-rep",
    "DASHBOARD_TEST_CUSTOMER",
    "local_visual_dashboard_dummy_test",
    "local_dummy_dashboard_test",
)
PRESERVED_SECTIONS = (
    "groups",
    "users",
    "invites",
    "onboarding",
    "config",
    "settings",
    "sheets",
)


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def package_path(root: Path, relative: Path) -> Path:
    return root / relative


def supplemental_runtime_files(root: Path) -> list[Path]:
    data_dir = root / "data"
    if not data_dir.exists():
        return []
    matches: set[Path] = set()
    for pattern in ("*invite*", "*roster*", "*state*"):
        matches.update(path for path in data_dir.glob(pattern) if path.is_file())
    return sorted(path.relative_to(root) for path in matches)


def files_to_archive(root: Path) -> list[Path]:
    ordered: list[Path] = []
    for relative in (*RUNTIME_FILES, *supplemental_runtime_files(root)):
        if relative not in ordered and package_path(root, relative).exists():
            ordered.append(relative)
    return ordered


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path.name}:{line_number}") from exc
            if isinstance(value, dict):
                records.append(value)
    return records


def contains_demo_marker(value: Any) -> bool:
    if isinstance(value, str):
        return any(marker in value for marker in DEMO_MARKERS)
    if isinstance(value, dict):
        return any(contains_demo_marker(key) or contains_demo_marker(item) for key, item in value.items())
    if isinstance(value, list):
        return any(contains_demo_marker(item) for item in value)
    return False


def is_demo_salesperson(key: str, record: Any) -> bool:
    if key in {"dashboard_test_rep", "demo-rep", "demo_rep"}:
        return True
    if not isinstance(record, dict):
        return contains_demo_marker(key)
    fields = (
        key,
        record.get("salesperson_id"),
        record.get("display_name"),
        record.get("source"),
        record.get("notes"),
    )
    return any(contains_demo_marker(field) for field in fields)


def clean_demo_references(value: Any) -> tuple[Any, int]:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        removed = 0
        for key, item in value.items():
            if contains_demo_marker(key) or contains_demo_marker(item):
                removed += 1
                continue
            child, child_removed = clean_demo_references(item)
            cleaned[key] = child
            removed += child_removed
        return cleaned, removed
    if isinstance(value, list):
        cleaned_items: list[Any] = []
        removed = 0
        for item in value:
            if contains_demo_marker(item):
                removed += 1
                continue
            child, child_removed = clean_demo_references(item)
            cleaned_items.append(child)
            removed += child_removed
        return cleaned_items, removed
    return value, 0


def clean_local_state(state: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    cleaned = deepcopy(state)
    preserved = [name for name in PRESERVED_SECTIONS if name in cleaned]
    cleaned_sections: list[str] = []

    salespeople = cleaned.get("salespeople")
    if isinstance(salespeople, dict):
        removed = [key for key, record in salespeople.items() if is_demo_salesperson(str(key), record)]
        for key in removed:
            del salespeople[key]
        if removed:
            cleaned_sections.append(f"salespeople removed {len(removed)} demo roster entr{'y' if len(removed) == 1 else 'ies'}")

    users = cleaned.get("users")
    if isinstance(users, dict):
        removed_users = [key for key, record in users.items() if contains_demo_marker(key) or contains_demo_marker(record)]
        for key in removed_users:
            del users[key]
        if removed_users:
            cleaned_sections.append(f"users removed {len(removed_users)} demo mapping{'s' if len(removed_users) != 1 else ''}")

    pending = cleaned.pop("pending_sales_logs", None)
    if isinstance(pending, dict) and pending:
        cleaned_sections.append(f"pending_sales_logs removed {len(pending)} stale flow{'s' if len(pending) != 1 else ''}")

    for section in ("reports", "report_cache", "sync_cache", "sync_counters", "dashboard_cache", "daily_report_cache"):
        value = cleaned.get(section)
        if isinstance(value, (dict, list)):
            next_value, removed = clean_demo_references(value)
            if removed:
                cleaned[section] = next_value
                cleaned_sections.append(f"{section} removed {removed} demo reference{'s' if removed != 1 else ''}")

    if "salespeople" in cleaned and "salespeople" not in preserved:
        preserved.append("salespeople")
    return cleaned, preserved, cleaned_sections


def make_plan(root: Path, *, visual_dashboard_only: bool = False) -> dict[str, Any]:
    backup = Path("data") / "backups" / f"pre_ryan_reset_{timestamp()}"
    archive = files_to_archive(root)
    state_path = root / "data" / "local_state.json"
    state_before: dict[str, Any] | None = None
    state_after: dict[str, Any] | None = None
    preserved: list[str] = []
    cleaned: list[str] = []
    sales_logs_after: list[dict[str, Any]] | None = None

    if state_path.exists():
        state_before = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state_before, dict):
            raise ValueError("local_state.json must contain a JSON object")
        state_after, preserved, cleaned = clean_local_state(state_before)

    clear_files = list(CLEAR_JSONL_FILES)
    if visual_dashboard_only:
        sales_path = root / "data" / "sales_logs.jsonl"
        sales_logs = read_jsonl(sales_path)
        sales_logs_after = [record for record in sales_logs if not contains_demo_marker(record)]
        clear_files = []
        removed = len(sales_logs) - len(sales_logs_after)
        if removed:
            cleaned.append(f"sales_logs removed {removed} visual dashboard dummy row{'s' if removed != 1 else ''}")

    return {
        "backup": backup,
        "archive": archive,
        "clear_files": clear_files,
        "state_after": state_after,
        "sales_logs_after": sales_logs_after,
        "preserved": preserved,
        "cleaned": cleaned,
        "visual_dashboard_only": visual_dashboard_only,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)


def execute_plan(root: Path, plan: dict[str, Any]) -> None:
    backup_dir = root / plan["backup"]
    backup_dir.mkdir(parents=True, exist_ok=False)
    for relative in plan["archive"]:
        source = root / relative
        destination = backup_dir / relative.name
        shutil.copy2(source, destination)

    if plan["visual_dashboard_only"]:
        if plan["sales_logs_after"] is not None:
            write_jsonl(root / "data" / "sales_logs.jsonl", plan["sales_logs_after"])
    else:
        for relative in plan["clear_files"]:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")

    if plan["state_after"] is not None:
        write_json(root / "data" / "local_state.json", plan["state_after"])


def print_summary(plan: dict[str, Any], *, execute: bool) -> None:
    prefix = "created" if execute else "would create"
    print(f"backup folder {prefix}: {plan['backup']}")
    print("files archived: " + (", ".join(str(path) for path in plan["archive"]) or "none"))
    if plan["visual_dashboard_only"]:
        print("files cleared: none; targeted visual dashboard dummy rows only")
    else:
        print("files cleared: " + ", ".join(str(path) for path in plan["clear_files"]))
    print("local_state sections preserved: " + (", ".join(plan["preserved"]) or "none"))
    print("local_state sections cleaned: " + (", ".join(plan["cleaned"]) or "none"))
    print("next manual step: clear Google Sheet data rows from row 2 down on data tabs")
    print("final verification: run /today, /team, /missing, and only run /sync_sheets after Sheet rows are clean")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive and clear North Shore demo runtime data before Ryan onboarding")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="show what would change without writing files")
    mode.add_argument("--execute", action="store_true", help="write backup and reset local demo runtime data")
    parser.add_argument(
        "--visual-dashboard-only",
        action="store_true",
        help="remove only dummy visual dashboard test data created by seed_visual_dashboard_dummy_test.py",
    )
    parser.add_argument("--root", type=Path, default=PACKAGE_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    plan = make_plan(root, visual_dashboard_only=args.visual_dashboard_only)
    if args.execute:
        execute_plan(root, plan)
    print_summary(plan, execute=args.execute)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
