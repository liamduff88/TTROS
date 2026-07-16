#!/usr/bin/env python3
"""Validate the append-only TTROS prospect ledger and entity-page pointers.

Revisit: when the prospect schema, status vocabulary, or transition cadence changes. · Last touched: 2026-07-16.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import jsonschema

try:
    from business_brain import resolve_business_brain_pointer
except ModuleNotFoundError:
    from tools.business_brain import resolve_business_brain_pointer


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "queue" / "prospects.jsonl"
DEFAULT_SCHEMA = ROOT / "queue" / "prospects_schema.json"

ALLOWED_TRANSITIONS = {
    "identified": {"drafted", "rejected", "do_not_contact"},
    "drafted": {"sent", "rejected", "do_not_contact"},
    "sent": {"touch_2", "replied_positive", "replied_negative", "do_not_contact", "withdrawn"},
    "touch_2": {"touch_3", "replied_positive", "replied_negative", "do_not_contact"},
    "touch_3": {"replied_positive", "replied_negative", "no_response", "do_not_contact"},
    "replied_positive": {"call_booked", "nurture", "lost", "do_not_contact"},
    "call_booked": {"fit_call_done", "lost", "nurture", "do_not_contact"},
    "fit_call_done": {"offer_sent", "lost", "nurture", "do_not_contact"},
    "offer_sent": {"won", "lost", "nurture", "do_not_contact"},
    "nurture": {"replied_positive", "call_booked", "lost", "do_not_contact"},
    "withdrawn": {"sent", "rejected", "do_not_contact"},
}
TERMINAL = {"replied_negative", "no_response", "won", "lost", "rejected", "do_not_contact"}
EXPECTED_TOUCH_COUNT = {"identified": 0, "drafted": 0, "sent": 1, "touch_2": 2, "touch_3": 3}
IMMUTABLE_FIELDS = {
    "prospect_id", "name", "company", "lane", "icp_variant", "signal_class",
    "signal_date", "signal_source_url", "source_query", "score", "tier",
    "readiness", "wedge", "angle_type", "first_touch_style", "outreach_basis",
    "entity_page_path",
}


def validate_ledger(ledger: Path = DEFAULT_LEDGER, schema_path: Path = DEFAULT_SCHEMA) -> dict:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker())
    rows: list[dict] = []
    errors: list[str] = []
    previous: dict[str, dict] = {}
    signal_owners: dict[str, str] = {}

    for line_number, raw in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc.msg}")
            continue
        rows.append(row)
        for error in sorted(validator.iter_errors(row), key=lambda item: list(item.path)):
            field = ".".join(str(part) for part in error.path) or "record"
            errors.append(f"line {line_number} {field}: {error.message}")
        if any(validator.iter_errors(row)):
            continue

        prospect_id = row["prospect_id"]
        prior = previous.get(prospect_id)
        if prior:
            changed = sorted(field for field in IMMUTABLE_FIELDS if prior[field] != row[field])
            if changed:
                errors.append(f"line {line_number}: immutable fields changed for {prospect_id}: {', '.join(changed)}")
            allowed = ALLOWED_TRANSITIONS.get(prior["status"], set())
            side_state = row["status"] == "do_not_contact"
            if not side_state and (prior["status"] in TERMINAL or row["status"] not in allowed):
                errors.append(f"line {line_number}: invalid transition {prior['status']} -> {row['status']} for {prospect_id}")
            if row["status_date"] < prior["status_date"]:
                errors.append(f"line {line_number}: status_date moved backwards for {prospect_id}")
        previous[prospect_id] = row

        expected = EXPECTED_TOUCH_COUNT.get(row["status"])
        if expected is not None and row["touch_count"] != expected:
            errors.append(f"line {line_number}: {row['status']} requires touch_count={expected}")
        if row["status"] in {"identified", "drafted", "touch_3"} and row["next_touch_due"] is not None:
            errors.append(f"line {line_number}: {row['status']} requires next_touch_due=null")
        if row["do_not_contact"] != (row["status"] == "do_not_contact"):
            errors.append(f"line {line_number}: do_not_contact flag/status mismatch")
        if row["status_date"] < row["signal_date"]:
            errors.append(f"line {line_number}: status_date precedes signal_date")
        age_days = (dt.date.fromisoformat(row["status_date"]) - dt.date.fromisoformat(row["signal_date"])).days
        if row["tier"] == "A" and age_days > 90:
            errors.append(f"line {line_number}: tier A signal is older than 90 days")
        if row["tier"] in {"A", "B"} and age_days > 365:
            errors.append(f"line {line_number}: drafted signal is older than 12 months")
        expected_tier = "A" if row["score"] >= 80 else "B" if row["score"] >= 65 else "C_monitor" if row["score"] >= 50 else "D_reject"
        if row["tier"] != expected_tier:
            errors.append(f"line {line_number}: score {row['score']} requires tier {expected_tier}")
        if row["status"] in {"sent", "touch_2"} and row["next_touch_due"] is None:
            errors.append(f"line {line_number}: {row['status']} requires next_touch_due")
        if row["status"] == "sent" and row["next_touch_due"]:
            due = dt.date.fromisoformat(row["next_touch_due"])
            status_date = dt.date.fromisoformat(row["status_date"])
            if due != status_date + dt.timedelta(days=4):
                errors.append(f"line {line_number}: sent requires next_touch_due=status_date+4")
        if row["status"] == "touch_2" and row["next_touch_due"]:
            due = dt.date.fromisoformat(row["next_touch_due"])
            status_date = dt.date.fromisoformat(row["status_date"])
            if due != status_date + dt.timedelta(days=5):
                errors.append(f"line {line_number}: touch_2 requires next_touch_due=status_date+5")

        owner = signal_owners.setdefault(row["signal_source_url"], prospect_id)
        if owner != prospect_id:
            errors.append(f"line {line_number}: signal URL is already owned by {owner}")
        try:
            resolve_business_brain_pointer(row["entity_page_path"])
        except Exception as exc:
            errors.append(f"line {line_number}: entity_page_path is not canonical/readable: {exc}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "ledger": str(ledger),
        "row_count": len(rows),
        "prospect_count": len(previous),
        "errors": errors,
        "token_usage_text": "Token usage: no agent invocation",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = validate_ledger(args.ledger, args.schema)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
