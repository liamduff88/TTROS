#!/usr/bin/env python3
"""Validate the append-only TTROS prospect ledger and outreach snapshots.

Revisit: when the prospect schema, status vocabulary, or transition cadence changes. · Last touched: 2026-07-23.
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
PILOT_RECORD_TYPE = "outreach_pilot_v1"
PILOT_IMMUTABLE_FIELDS = {
    "record_type", "pilot_version", "prospect_id", "name", "person_name",
    "company", "company_name", "company_domain", "related_entities", "role",
    "lane", "icp_variant", "source_handoff", "source_hash", "handoff_version",
    "signal_date", "signal_source_url", "score", "tier", "readiness",
    "qualification", "primary_signal", "main_caution", "review_item_id",
}
PILOT_CONTACT_EVENTS = {
    "email_1_sent", "email_2_sent", "invitation_sent", "linkedin_message_sent",
}
PILOT_STOP_EVENTS = {
    "reply_received", "not_interested", "opt_out", "do_not_contact",
    "invalid_contact", "wrong_person", "wrong_company", "declined_connection",
    "prior_contact_discovered", "duplicate_detected", "active_sequence_found",
    "closed_or_disqualified", "cancelled",
}


def _validate_pilot_row(
    row: dict,
    prior: dict | None,
    line_number: int,
    errors: list[str],
    event_ids: set[str],
) -> None:
    prospect_id = row["prospect_id"]
    event_id = row["event_id"]
    if event_id in event_ids:
        errors.append(f"line {line_number}: duplicate pilot event_id {event_id}")
    event_ids.add(event_id)
    event = str((row.get("latest_event") or {}).get("type") or "")
    if prior:
        changed = sorted(field for field in PILOT_IMMUTABLE_FIELDS if prior[field] != row[field])
        if changed:
            errors.append(f"line {line_number}: immutable fields changed for {prospect_id}: {', '.join(changed)}")
        prior_history = prior.get("outreach_history") or []
        history = row.get("outreach_history") or []
        if len(history) != len(prior_history) + 1 or history[:-1] != prior_history:
            errors.append(f"line {line_number}: outreach history is not an append-only extension for {prospect_id}")
        if row["status_date"] < prior["status_date"]:
            errors.append(f"line {line_number}: status_date moved backwards for {prospect_id}")
        if prior.get("opt_out") and not row.get("opt_out"):
            errors.append(f"line {line_number}: opt_out was not preserved for {prospect_id}")
        if prior.get("do_not_contact") and not row.get("do_not_contact"):
            errors.append(f"line {line_number}: do_not_contact was not preserved for {prospect_id}")
        if prior.get("future_activity_cancelled") and event not in PILOT_STOP_EVENTS:
            errors.append(f"line {line_number}: non-stop event appended after future activity was cancelled for {prospect_id}")
    elif event != "handoff_imported" or len(row.get("outreach_history") or []) != 1:
        errors.append(f"line {line_number}: first pilot snapshot must be handoff_imported")

    reminder = row.get("next_reminder")
    if reminder is not None:
        if reminder.get("due_date") != row.get("next_touch_due"):
            errors.append(f"line {line_number}: next reminder and next_touch_due disagree")
        if reminder.get("condition") != "only if no stop event is recorded":
            errors.append(f"line {line_number}: next reminder is not conditional")
    if row.get("future_activity_cancelled"):
        if row.get("next_touch_due") is not None or row.get("next_reminder") is not None:
            errors.append(f"line {line_number}: stopped prospect retains future activity")
        if event not in PILOT_STOP_EVENTS:
            errors.append(f"line {line_number}: future activity cancelled without a stop event")
    if event in PILOT_CONTACT_EVENTS and row.get("last_contact_date") != row.get("status_date"):
        errors.append(f"line {line_number}: contact event must set last_contact_date")
    if event == "reply_received" and row.get("reply_status") != "received":
        errors.append(f"line {line_number}: reply_received must set reply_status=received")
    if event == "opt_out" and not (row.get("opt_out") and row.get("do_not_contact")):
        errors.append(f"line {line_number}: opt_out must preserve opt_out and do_not_contact")

    crm = row.get("crm_dry_run") or {}
    if crm.get("mode") != "dry_run" or crm.get("mutation_performed") is not False:
        errors.append(f"line {line_number}: CRM record is not a non-mutating dry run")
    record = crm.get("record") or {}
    if record.get("agentic_os_prospect_id") != prospect_id:
        errors.append(f"line {line_number}: CRM prospect identity mismatch")
    if bool(record.get("opt_out")) != bool(row.get("opt_out")) or bool(record.get("do_not_contact")) != bool(row.get("do_not_contact")):
        errors.append(f"line {line_number}: CRM opt-out authority mismatch")


def validate_ledger(ledger: Path = DEFAULT_LEDGER, schema_path: Path = DEFAULT_SCHEMA) -> dict:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker())
    rows: list[dict] = []
    errors: list[str] = []
    previous: dict[str, dict] = {}
    signal_owners: dict[str, str] = {}
    event_ids: set[str] = set()

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
        if row.get("record_type") == PILOT_RECORD_TYPE:
            _validate_pilot_row(row, prior, line_number, errors, event_ids)
            previous[prospect_id] = row
            expected_tier = "A" if row["score"] >= 80 else "B" if row["score"] >= 65 else "C_monitor" if row["score"] >= 50 else "D_reject"
            if row["tier"] != expected_tier:
                errors.append(f"line {line_number}: score {row['score']} requires tier {expected_tier}")
            owner = signal_owners.setdefault(row["signal_source_url"], prospect_id)
            if owner != prospect_id:
                errors.append(f"line {line_number}: signal URL is already owned by {owner}")
            continue
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
