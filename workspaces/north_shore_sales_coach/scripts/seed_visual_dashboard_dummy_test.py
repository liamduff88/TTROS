#!/usr/bin/env python3
"""Seed local dummy rows for the live visual dashboard sync path."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from copy import deepcopy
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Sequence

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from src.date_normalizer import BUSINESS_TIMEZONE, normalize_followup_date  # noqa: E402
from src.local_store import LocalJsonlStore, LocalStateStore  # noqa: E402

DUMMY_DISPLAY_NAME = "Dashboard Test Rep"
DUMMY_SALESPERSON_ID = "dashboard_test_rep"
DUMMY_CUSTOMER_REF = "DASHBOARD_TEST_CUSTOMER"
DUMMY_SOURCE = "local_visual_dashboard_dummy_test"
DUMMY_NOTE = "Dummy visual dashboard sync test only. Not real customer data."
DUMMY_ROSTER_NOTE = "Dummy visual dashboard test only."


def today_local() -> str:
    return datetime.now(BUSINESS_TIMEZONE).date().isoformat()


def submitted_at_for_today() -> str:
    today = datetime.now(BUSINESS_TIMEZONE).date()
    local_midday = datetime.combine(today, time(hour=12), tzinfo=BUSINESS_TIMEZONE)
    return local_midday.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def dummy_salesperson(existing: dict[str, Any] | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    existing = existing or {}
    return {
        "salesperson_id": DUMMY_SALESPERSON_ID,
        "display_name": DUMMY_DISPLAY_NAME,
        "active": True,
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "source": DUMMY_SOURCE,
        "notes": DUMMY_ROSTER_NOTE,
    }


def dummy_log(*, force: bool = False) -> dict[str, Any]:
    submitted_at = submitted_at_for_today()
    suffix = "-" + datetime.now(timezone.utc).strftime("%H%M%S") if force else ""
    return {
        "log_id": f"dashboard-test-{today_local()}{suffix}-{uuid.uuid4().hex[:8]}",
        "submitted_at": submitted_at,
        "telegram_user_id": "local_dummy_dashboard_test",
        "salesperson_id": DUMMY_SALESPERSON_ID,
        "display_name": DUMMY_DISPLAY_NAME,
        "source": DUMMY_SOURCE,
        "raw_text": DUMMY_NOTE,
        "customer_ref": DUMMY_CUSTOMER_REF,
        "parsed": {
            "customer_type": None,
            "customer_name_or_ref": DUMMY_CUSTOMER_REF,
            "vehicle_interest": "CR-V",
            "lead_source": "walk-in",
            "interaction_type": "walk_in",
            "appointment_count": 1,
            "walk_in_count": 1,
            "people_spoken_to": 3,
            "test_drive": True,
            "worksheet_or_offer_presented": True,
            "asked_for_business": True,
            "outcome": "follow_up",
            "next_step": "follow up tomorrow",
            "followup_date": normalize_followup_date("tomorrow", submitted_at),
            "notes": DUMMY_NOTE,
        },
        "missing_fields": [],
        "coaching_flags": [],
        "confidence": 1.0,
        "status": "complete",
        "llm_used": False,
        "llm_tokens_estimate": None,
    }


def is_dummy_log(record: dict[str, Any]) -> bool:
    parsed = record.get("parsed")
    parsed = parsed if isinstance(parsed, dict) else {}
    return record.get("source") == DUMMY_SOURCE or record.get("customer_ref") == DUMMY_CUSTOMER_REF or parsed.get("customer_name_or_ref") == DUMMY_CUSTOMER_REF


def identical_dummy_log_for_today(record: dict[str, Any], day: str) -> bool:
    return (
        str(record.get("submitted_at", "")).startswith(day)
        and record.get("source") == DUMMY_SOURCE
        and is_dummy_log(record)
        and record.get("salesperson_id") == DUMMY_SALESPERSON_ID
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return list(LocalJsonlStore(path).records()) if path.exists() else []


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)


def plan_execute(root: Path, *, cleanup: bool = False, force: bool = False) -> dict[str, Any]:
    state_store = LocalStateStore(root / "data" / "local_state.json")
    sales_path = root / "data" / "sales_logs.jsonl"
    state_before = state_store.read()
    logs_before = read_jsonl(sales_path)
    state_after = deepcopy(state_before)
    logs_after = list(logs_before)

    if cleanup:
        salespeople = state_after.get("salespeople")
        rep_removed = False
        if isinstance(salespeople, dict) and DUMMY_SALESPERSON_ID in salespeople:
            del salespeople[DUMMY_SALESPERSON_ID]
            rep_removed = True
        kept_logs = [record for record in logs_after if not is_dummy_log(record)]
        return {
            "state_after": state_after,
            "logs_after": kept_logs,
            "salesperson_action": "removed" if rep_removed else "not present",
            "log_action": f"removed {len(logs_after) - len(kept_logs)}",
            "mutated": rep_removed or len(kept_logs) != len(logs_after),
        }

    salespeople = state_after.setdefault("salespeople", {})
    if not isinstance(salespeople, dict):
        raise ValueError("local_state salespeople must be an object")
    existing = salespeople.get(DUMMY_SALESPERSON_ID)
    salesperson_action = "updated" if isinstance(existing, dict) else "created"
    salespeople[DUMMY_SALESPERSON_ID] = dummy_salesperson(existing if isinstance(existing, dict) else None)

    day = today_local()
    already_present = any(identical_dummy_log_for_today(record, day) for record in logs_after)
    if already_present and not force:
        log_action = "already present"
    else:
        logs_after.append(dummy_log(force=force))
        log_action = "created" if not force else "created with --force"

    return {
        "state_after": state_after,
        "logs_after": logs_after,
        "salesperson_action": salesperson_action,
        "log_action": log_action,
        "mutated": True,
    }


def apply_plan(root: Path, plan: dict[str, Any]) -> None:
    LocalStateStore(root / "data" / "local_state.json")._write(plan["state_after"])
    write_jsonl(root / "data" / "sales_logs.jsonl", plan["logs_after"])


def print_summary(plan: dict[str, Any], *, dry_run: bool, cleanup: bool) -> None:
    prefix = "DRY RUN: " if dry_run else ""
    if cleanup:
        print(f"{prefix}dummy salesperson {plan['salesperson_action']}")
        print(f"{prefix}dummy Raw_Logs-compatible logs {plan['log_action']}")
    else:
        print(f"{prefix}dummy salesperson {plan['salesperson_action']}")
        print(f"{prefix}dummy Raw_Logs-compatible log {plan['log_action']}")
    print("next manual step: run /sync_sheets once from North Shore admin group")
    print("expected result: Dashboard Test Rep appears in the visual Dashboard Team Scorecard after sync and browser refresh")
    print("note: do not rebuild the dashboard unless Salespeople and Raw_Logs receive the dummy rows and the visual Dashboard still stays blank")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed a local dummy dashboard sync test row")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    mode.add_argument("--execute", action="store_true", help="write local dummy salesperson/log rows")
    parser.add_argument("--cleanup", action="store_true", help="remove only local dummy dashboard test rows")
    parser.add_argument("--force", action="store_true", help="append a fresh dummy log even if today's dummy log exists")
    parser.add_argument("--root", type=Path, default=PACKAGE_ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    plan = plan_execute(args.root, cleanup=args.cleanup, force=args.force)
    if args.execute:
        apply_plan(args.root, plan)
    print_summary(plan, dry_run=args.dry_run, cleanup=args.cleanup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
