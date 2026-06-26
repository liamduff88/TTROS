"""Deterministic, local-only Google Sheets row payload construction.

This module deliberately contains no Sheets client or network integration.  Its
ordered dictionaries are the hand-off boundary for a separately approved writer.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .report_generator import generate_daily_report

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SYNC_TABS = (
    "Users",
    "Salespeople",
    "Raw_Logs",
    "Daily_Team_Summary",
    "Daily_Salesperson_Scorecard",
    "Followups",
    "Missing_Data",
    "Coaching_Flags",
    "Report_Archive",
    "QA_Checks",
)


def load_headers(path: str | Path | None = None) -> dict[str, list[str]]:
    source = Path(path) if path is not None else PACKAGE_ROOT / "google_sheets" / "tab_headers.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    return {tab: list(data[tab]) for tab in SYNC_TABS}


def _compact_json(value: Any) -> str:
    return json.dumps(value if value is not None else [], ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _cell(value: Any) -> Any:
    return "" if value is None else value


def _ordered_row(tab: str, values: Mapping[str, Any], headers: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    columns = headers[tab]
    missing = set(columns) - set(values)
    extra = set(values) - set(columns)
    if missing or extra:
        raise ValueError(f"{tab} row shape mismatch: missing={sorted(missing)}, extra={sorted(extra)}")
    return {column: _cell(values[column]) for column in columns}


def build_users_rows(
    roles: Mapping[str, Any], state: Mapping[str, Any], headers: Mapping[str, Sequence[str]] | None = None
) -> list[dict[str, Any]]:
    """Merge users and apply the display-name precedence declared in the spec."""
    headers = headers or load_headers()
    role_users = roles.get("users", {}) if isinstance(roles.get("users", {}), Mapping) else {}
    state_users = state.get("users", {}) if isinstance(state.get("users", {}), Mapping) else {}
    rows = []
    for user_id in sorted({str(key) for key in role_users} | {str(key) for key in state_users}):
        role = role_users.get(user_id, {})
        profile = state_users.get(user_id, {})
        role = role if isinstance(role, Mapping) else {}
        profile = profile if isinstance(profile, Mapping) else {}
        full_name = " ".join(
            value.strip()
            for value in (profile.get("first_name"), profile.get("last_name"))
            if isinstance(value, str) and value.strip()
        )
        username = profile.get("username")
        candidates = (role.get("display_name"), profile.get("display_name"), full_name)
        display_name = next((value.strip() for value in candidates if isinstance(value, str) and value.strip()), None)
        if display_name is None and isinstance(username, str) and username.strip():
            display_name = "@" + username.strip().lstrip("@")
        effective_role = role.get("role") or profile.get("role")
        effective_active = role.get("active") if "active" in role else profile.get("active")
        effective_salesperson_id = role.get("salesperson_id") or profile.get("salesperson_id")
        rows.append(
            _ordered_row(
                "Users",
                {
                    "telegram_user_id": user_id,
                    "display_name": display_name or "Unregistered salesperson",
                    "role": effective_role,
                    "active": effective_active,
                    "salesperson_id": effective_salesperson_id,
                },
                headers,
            )
        )
    return rows


def build_salespeople_rows(state: Mapping[str, Any], headers: Mapping[str, Sequence[str]] | None = None) -> list[dict[str, Any]]:
    headers = headers or load_headers()
    source = state.get("salespeople", {})
    records = source.values() if isinstance(source, Mapping) else source if isinstance(source, list) else []
    rows = []
    for record in sorted((item for item in records if isinstance(item, Mapping)), key=lambda item: str(item.get("salesperson_id", ""))):
        rows.append(_ordered_row("Salespeople", {column: record.get(column) for column in headers["Salespeople"]}, headers))
    return rows


def build_raw_logs_rows(records: Iterable[Mapping[str, Any]], headers: Mapping[str, Sequence[str]] | None = None) -> list[dict[str, Any]]:
    headers = headers or load_headers()
    rows = []
    for record in sorted(records, key=lambda item: (str(item.get("submitted_at", "")), str(item.get("log_id", "")))):
        parsed = record.get("parsed", {})
        parsed = parsed if isinstance(parsed, Mapping) else {}
        values = {column: record.get(column) for column in headers["Raw_Logs"]}
        for column in (
            "customer_type", "customer_name_or_ref", "vehicle_interest", "lead_source", "interaction_type",
            "appointment_count", "walk_in_count", "people_spoken_to", "test_drive",
            "worksheet_or_offer_presented", "asked_for_business", "outcome", "next_step", "followup_date", "notes",
        ):
            values[column] = parsed.get(column)
        values["missing_fields_json"] = _compact_json(record.get("missing_fields"))
        values["coaching_flags_json"] = _compact_json(record.get("coaching_flags"))
        rows.append(_ordered_row("Raw_Logs", values, headers))
    return rows


def build_daily_team_summary_rows(reports: Iterable[Mapping[str, Any]], headers: Mapping[str, Sequence[str]] | None = None) -> list[dict[str, Any]]:
    headers = headers or load_headers()
    rows = []
    for report in sorted(reports, key=lambda item: (str(item.get("report_date", "")), str(item.get("generated_at", "")))):
        metrics = report.get("metrics", {})
        metrics = metrics if isinstance(metrics, Mapping) else {}
        values = {"report_date": report.get("report_date"), "generated_at": report.get("generated_at")}
        values.update({column: metrics.get(column) for column in headers["Daily_Team_Summary"][2:]})
        rows.append(_ordered_row("Daily_Team_Summary", values, headers))
    return rows


def build_scorecard_rows(reports: Iterable[Mapping[str, Any]], headers: Mapping[str, Sequence[str]] | None = None) -> list[dict[str, Any]]:
    headers = headers or load_headers()
    rows = []
    for report in sorted(reports, key=lambda item: (str(item.get("report_date", "")), str(item.get("generated_at", "")))):
        for item in sorted(report.get("team", []), key=lambda row: str(row.get("salesperson_id", ""))):
            values = {
                "report_date": report.get("report_date"), "generated_at": report.get("generated_at"),
                "salesperson_id": item.get("salesperson_id"), "display_name": item.get("name"),
                **{column: item.get(column) for column in headers["Daily_Salesperson_Scorecard"][4:]},
            }
            rows.append(_ordered_row("Daily_Salesperson_Scorecard", values, headers))
    return rows


def build_followup_rows(reports: Iterable[Mapping[str, Any]], headers: Mapping[str, Sequence[str]] | None = None) -> list[dict[str, Any]]:
    headers = headers or load_headers()
    rows = []
    for report in sorted(reports, key=lambda item: (str(item.get("report_date", "")), str(item.get("generated_at", "")))):
        followups = report.get("followups", {})
        for status in ("overdue", "due", "upcoming"):
            for item in sorted(
                followups.get(status, []),
                key=lambda row: (str(row.get("date", "")), str(row.get("salesperson_id", "")), str(row.get("log_id", ""))),
            ):
                rows.append(_ordered_row("Followups", {
                    "report_date": report.get("report_date"), "followup_status": status,
                    "salesperson_id": item.get("salesperson_id"), "display_name": item.get("name"),
                    "followup_date": item.get("date"),
                    # Only a separately emitted field is eligible. Never inspect free text.
                    "followup_time": item.get("followup_time"),
                    "next_step": item.get("next_step"), "log_id": item.get("log_id"),
                }, headers))
    return rows


def build_missing_data_rows(
    reports: Iterable[Mapping[str, Any]], active_roster_ids: Iterable[str] = (), headers: Mapping[str, Sequence[str]] | None = None
) -> list[dict[str, Any]]:
    headers = headers or load_headers()
    active = {str(value) for value in active_roster_ids}
    rows = []
    details = {
        "roster_no_update": "Active roster member has no complete update for report_date.",
        "incomplete_log": "Submitted log is incomplete; see missing_fields_json.",
        "unregistered_submitter": "Submitter is not in the active roster.",
    }
    for report in sorted(reports, key=lambda item: (str(item.get("report_date", "")), str(item.get("generated_at", "")))):
        missing = report.get("missing", {})
        branches = (
            ("roster_no_update", missing.get("not_updated", [])),
            ("incomplete_log", missing.get("incomplete_logs", [])),
            ("unregistered_submitter", missing.get("unregistered_submitters", [])),
        )
        for missing_type, items in branches:
            for item in sorted(items, key=lambda row: (str(row.get("salesperson_id", "")), str(row.get("log_id", "")))):
                person = str(item.get("salesperson_id", ""))
                if missing_type == "roster_no_update":
                    log_id, fields, roster_status = "", "[]", "roster_missing_update"
                elif missing_type == "incomplete_log":
                    log_id, fields = item.get("log_id"), _compact_json(item.get("fields"))
                    roster_status = "active_roster" if person in active else "unregistered"
                else:
                    log_id, fields, roster_status = "", "[]", "unregistered"
                rows.append(_ordered_row("Missing_Data", {
                    "report_date": report.get("report_date"), "missing_type": missing_type,
                    "salesperson_id": person, "display_name": item.get("name"), "log_id": log_id,
                    "missing_fields_json": fields, "roster_status": roster_status, "detail": details[missing_type],
                }, headers))
    return rows


def build_coaching_flag_rows(reports: Iterable[Mapping[str, Any]], headers: Mapping[str, Sequence[str]] | None = None) -> list[dict[str, Any]]:
    headers = headers or load_headers()
    rows = []
    for report in sorted(reports, key=lambda item: (str(item.get("report_date", "")), str(item.get("generated_at", "")))):
        for item in sorted(report.get("coaching_flags", []), key=lambda row: (str(row.get("salesperson_id", "")), str(row.get("code", "")))):
            rows.append(_ordered_row("Coaching_Flags", {
                "report_date": report.get("report_date"), "salesperson_id": item.get("salesperson_id"),
                "display_name": item.get("name"), "flag_code": item.get("code"),
                "detail": item.get("detail"), "log_id": item.get("log_id"),
            }, headers))
    return rows


def build_report_archive_rows(records: Iterable[Mapping[str, Any]], headers: Mapping[str, Sequence[str]] | None = None) -> list[dict[str, Any]]:
    headers = headers or load_headers()
    rows = []
    for record in sorted(records, key=lambda item: (str(item.get("generated_at", "")), str(item.get("report_id", "")))):
        metrics = record.get("summary_metrics", {})
        metrics = metrics if isinstance(metrics, Mapping) else {}
        values = {column: record.get(column) for column in ("report_id", "generated_at", "report_type", "date")}
        values.update({column: metrics.get(column) for column in headers["Report_Archive"][4:14]})
        values["coaching_flags_count"] = metrics.get("coaching_flags")
        values["flags_json"] = _compact_json(record.get("flags"))
        values["llm_used"] = record.get("llm_used")
        rows.append(_ordered_row("Report_Archive", values, headers))
    return rows


def build_qa_check_rows(
    payloads: Mapping[str, Sequence[Mapping[str, Any]]],
    checked_at: str,
    headers: Mapping[str, Sequence[str]] | None = None,
) -> list[dict[str, Any]]:
    headers = headers or load_headers()
    row_count = sum(len(rows) for tab, rows in payloads.items() if tab != "QA_Checks")
    missing_tabs = [tab for tab in SYNC_TABS if tab not in payloads and tab != "QA_Checks"]
    status = "pass" if not missing_tabs else "fail"
    detail = "All deterministic sync payload tabs built." if status == "pass" else "Missing tabs: " + ", ".join(missing_tabs)
    return [
        _ordered_row(
            "QA_Checks",
            {
                "checked_at": checked_at,
                "check_name": "deterministic_payload_shape",
                "status": status,
                "row_count": row_count,
                "detail": detail,
            },
            headers,
        )
    ]


def build_sync_payloads(
    *, roles: Mapping[str, Any], state: Mapping[str, Any], sales_logs: Iterable[Mapping[str, Any]],
    daily_reports: Iterable[Mapping[str, Any]], report_archive: Iterable[Mapping[str, Any]],
    headers: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return all supported tab payloads in stable tab, row, and column order."""
    headers = headers or load_headers()
    reports, logs, archive = list(daily_reports), list(sales_logs), list(report_archive)
    salespeople = build_salespeople_rows(state, headers)
    active_ids = [row["salesperson_id"] for row in salespeople if row["active"] is True]
    payloads = {
        "Users": build_users_rows(roles, state, headers),
        "Salespeople": salespeople,
        "Raw_Logs": build_raw_logs_rows(logs, headers),
        "Daily_Team_Summary": build_daily_team_summary_rows(reports, headers),
        "Daily_Salesperson_Scorecard": build_scorecard_rows(reports, headers),
        "Followups": build_followup_rows(reports, headers),
        "Missing_Data": build_missing_data_rows(reports, active_ids, headers),
        "Coaching_Flags": build_coaching_flag_rows(reports, headers),
        "Report_Archive": build_report_archive_rows(archive, headers),
    }
    checked_at = ""
    for collection in (reports, archive, logs):
        checked_at = max(
            [checked_at]
            + [
                str(item.get("generated_at") or item.get("submitted_at") or "")
                for item in collection
                if isinstance(item, Mapping)
            ]
        )
    payloads["QA_Checks"] = build_qa_check_rows(payloads, checked_at, headers)
    return payloads


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_local_payloads(root: str | Path = PACKAGE_ROOT) -> dict[str, list[dict[str, Any]]]:
    """Read only package-local files and deterministically construct dry-run rows."""
    root = Path(root)
    roles = _read_json(root / "config" / "roles.json")
    state = _read_json(root / "data" / "local_state.json")
    logs = _read_jsonl(root / "data" / "sales_logs.jsonl")
    archive = _read_jsonl(root / "data" / "report_archive.jsonl")
    roster = {
        str(item.get("salesperson_id")): str(item.get("display_name"))
        for item in state.get("salespeople", {}).values()
        if isinstance(item, Mapping) and item.get("active") is True and item.get("salesperson_id")
    }
    role_users = roles.get("users", {})
    for user_id, user in role_users.items():
        if isinstance(user, Mapping) and user.get("active") is True and user.get("role") == "salesperson":
            roster.setdefault(str(user.get("salesperson_id") or user_id), str(user.get("display_name") or "Unregistered salesperson"))
    names = dict(roster)
    names.update({row["telegram_user_id"]: row["display_name"] for row in build_users_rows(roles, state)})
    archive_times = {str(item.get("date")): item.get("generated_at") for item in archive if item.get("date") and item.get("generated_at")}
    reports = []
    for day in sorted({str(item.get("submitted_at", ""))[:10] for item in logs if str(item.get("submitted_at", ""))[:10]}):
        try:
            report_day = date.fromisoformat(day)
        except ValueError:
            continue
        timestamp = archive_times.get(day) or max(
            (str(item.get("submitted_at")) for item in logs if str(item.get("submitted_at", "")).startswith(day)),
            default=f"{day}T00:00:00Z",
        )
        generated_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00")).astimezone(timezone.utc)
        reports.append(generate_daily_report(logs, report_day, roster, generated_at=generated_at, names=names))
    return build_sync_payloads(roles=roles, state=state, sales_logs=logs, daily_reports=reports, report_archive=archive)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build local-only Sheets payloads")
    parser.add_argument("--dry-run", action="store_true", help="print tab row counts without identifiers or row data")
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.error("only --dry-run is supported")
    payloads = load_local_payloads()
    print("Sheets sync dry-run (local only; no external calls)")
    for tab in SYNC_TABS:
        print(f"{tab}: {len(payloads[tab])} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
