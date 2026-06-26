"""Deterministic reporting over package-local sales JSONL records."""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from .date_normalizer import normalize_followup_date

METRIC_FIELDS = (
    "people_spoken_to",
    "appointment_count",
    "test_drives",
    "worksheets_offers",
    "asks_for_business",
)
USEFUL_FIELDS = ("people_spoken_to", "test_drive", "worksheet_or_offer_presented", "asked_for_business")


def generate_daily_report(
    records: Iterable[dict[str, Any]],
    report_date: date,
    roster: Mapping[str, str] | None = None,
    *,
    generated_at: datetime | None = None,
    names: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a stable summary. Time is injected only for archive/test reproducibility."""
    all_records = list(records)
    selected = [record for record in all_records if _record_date(record) == report_date]
    people = sorted({_person_id(record) for record in selected})
    metrics = Counter(
        {
            "total_updates": len(selected),
            "active_salespeople": len(people),
            "people_spoken_to": 0,
            "appointments": 0,
            "test_drives": 0,
            "worksheets_offers": 0,
            "asks_for_business": 0,
            "outcomes": 0,
        }
    )
    scorecards: dict[str, Counter[str]] = defaultdict(Counter)
    for record in selected:
        parsed = _parsed(record)
        person = _person_id(record)
        row = scorecards[person]
        row["updates"] += 1
        for target, source in (("people_spoken_to", "people_spoken_to"), ("appointments", "appointment_count")):
            value = _nonnegative_int(parsed.get(source))
            metrics[target] += value
            row[target] += value
        for target, source in (
            ("test_drives", "test_drive"),
            ("worksheets_offers", "worksheet_or_offer_presented"),
            ("asks_for_business", "asked_for_business"),
        ):
            value = int(parsed.get(source) is True)
            metrics[target] += value
            row[target] += value
        outcome = int(bool(parsed.get("outcome")))
        metrics["outcomes"] += outcome
        row["outcomes"] += outcome

    resolved_names = names or roster or {}
    followups = classify_followups(all_records, report_date, resolved_names)
    missing = find_missing(selected, roster, resolved_names)
    flags = coaching_flags(selected, resolved_names)
    metrics["followups_due"] = len(followups["overdue"]) + len(followups["due"])
    metrics["missing_incomplete_updates"] = len(missing["incomplete_logs"]) + len(missing["not_updated"])
    metrics["coaching_flags"] = len(flags)
    team = [
        {"salesperson_id": person, "name": _name_for_person(person, selected, resolved_names), **{key: scorecards[person][key] for key in ("updates", "people_spoken_to", "appointments", "test_drives", "worksheets_offers", "asks_for_business", "outcomes")}}
        for person in people
    ]
    timestamp = generated_at or datetime.now(timezone.utc)
    return {
        "report_date": report_date.isoformat(),
        "generated_at": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "metrics": dict(metrics),
        "team": team,
        "followups": followups,
        "missing": missing,
        "coaching_flags": flags,
        # Compatibility with the original report shape.
        "records": len(selected),
        "totals": dict(metrics),
    }


def archive_record(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "report_id": str(uuid.uuid4()),
        "generated_at": report["generated_at"],
        "report_type": "daily",
        "date": report["report_date"],
        "summary_metrics": dict(report["metrics"]),
        "flags": list(report["coaching_flags"]),
        "llm_used": False,
    }


def classify_followups(
    records: Iterable[dict[str, Any]],
    as_of: date,
    names: Mapping[str, str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {"overdue": [], "due": [], "upcoming": []}
    for record in records:
        parsed = _parsed(record)
        raw_date = parsed.get("followup_date")
        followup_date = parse_followup_date(raw_date, as_of)
        next_step = parsed.get("next_step")
        if followup_date is None:
            continue
        bucket = "overdue" if followup_date < as_of else "due" if followup_date == as_of else "upcoming"
        result[bucket].append(
            {
                "salesperson_id": _person_id(record),
                "name": _record_name(record, names or {}),
                "date": followup_date.isoformat(),
                "next_step": next_step or "Follow up",
                "log_id": str(record.get("log_id", "")),
            }
        )
    for items in result.values():
        items.sort(key=lambda item: (item["date"], item["salesperson_id"], item["log_id"]))
    return result


def parse_followup_date(value: Any, as_of: date) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().lower()
    normalized = normalize_followup_date(text, as_of)
    if normalized:
        return date.fromisoformat(normalized)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y", "%B %d", "%b %d"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            return parsed.replace(year=as_of.year) if "%Y" not in fmt and "%y" not in fmt else parsed
        except ValueError:
            pass
    return None


def find_missing(
    records: Iterable[dict[str, Any]],
    roster: Mapping[str, str] | None = None,
    names: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    selected = list(records)
    complete_updates: set[str] = set()
    incomplete = []
    for record in selected:
        parsed = _parsed(record)
        fields = sorted(set(record.get("missing_fields") or []) | {field for field in USEFUL_FIELDS if parsed.get(field) is None})
        if fields:
            incomplete.append({"salesperson_id": _person_id(record), "name": _record_name(record, names or roster or {}), "log_id": str(record.get("log_id", "")), "fields": fields})
        elif record.get("status") not in {"draft", "needs_followup"}:
            complete_updates.add(_person_id(record))
    roster_ids = set(roster or {})
    unregistered_ids = sorted({_person_id(record) for record in selected} - roster_ids) if roster is not None else []
    return {
        "not_updated": [{"salesperson_id": person, "name": (roster or {}).get(person) or "Unregistered salesperson"} for person in sorted(roster_ids - complete_updates)],
        "incomplete_logs": incomplete,
        "unregistered_submitters": [
            {
                "salesperson_id": person,
                "name": _name_for_person(person, selected, names or {}),
            }
            for person in unregistered_ids
        ],
        "roster_available": roster is not None,
        "note": None if roster is not None else "Roster data unavailable; cannot determine who has not updated.",
    }


def coaching_flags(
    records: Iterable[dict[str, Any]],
    names: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    by_person: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_person[_person_id(record)].append(record)
    flags: list[dict[str, str]] = []
    for person in sorted(by_person):
        person_records = by_person[person]
        traffic = sum(_nonnegative_int(_parsed(record).get("people_spoken_to")) for record in person_records)
        drives = sum(_parsed(record).get("test_drive") is True for record in person_records)
        offers = sum(_parsed(record).get("worksheet_or_offer_presented") is True for record in person_records)
        asks = sum(_parsed(record).get("asked_for_business") is True for record in person_records)
        incomplete = sum(bool(record.get("missing_fields")) or record.get("status") in {"draft", "needs_followup"} for record in person_records)
        def add(code: str, detail: str) -> None:
            flags.append({"salesperson_id": person, "name": _record_name(person_records[0], names or {}), "code": code, "detail": detail})
        if traffic >= 5 and drives == 0:
            add("high_traffic_low_test_drives", f"{traffic} people spoken to and no test drives.")
        if drives and asks == 0:
            add("test_drive_without_ask", f"{drives} test drive(s) and no ask for business.")
        if any(_parsed(r).get("worksheet_or_offer_presented") is True and not _parsed(r).get("followup_date") for r in person_records):
            add("offer_without_followup_date", "Offer/worksheet recorded without a follow-up date.")
        if any(not _parsed(r).get("next_step") for r in person_records):
            add("missing_next_step", "At least one update has no next step.")
        if incomplete >= 2:
            add("repeated_incomplete_update", f"{incomplete} updates are incomplete.")
        if traffic >= 5 and drives >= 2 and offers >= 1 and asks >= 1:
            add("strong_performance", "Strong activity and conversion behavior worth recognition.")
    return flags


def format_daily(report: Mapping[str, Any]) -> str:
    m = report["metrics"]
    missing = report["missing"]
    followups = report["followups"]
    overdue = len(followups["overdue"])
    due = len(followups["due"])
    missing_names = ", ".join(item["name"] for item in missing["not_updated"]) or "None identified"
    active_status = (
        f"{m['active_salespeople']} active update(s); missing/incomplete {m['missing_incomplete_updates']}."
    )
    if missing["note"]:
        active_status += f" {missing['note']}"
    attention = (
        "No coaching attention items from today's updates."
        if m["coaching_flags"] == 0
        else f"{m['coaching_flags']} coaching attention item(s) to review."
    )
    next_action = "Next action: Check overdue follow-ups first." if overdue else "Next action: Confirm any missing updates before close."
    return "\n".join(
        (
            f"Manager briefing — {report['report_date']}",
            (
                f"Key numbers: {m['total_updates']} update(s), {m['people_spoken_to']} people, "
                f"{m['appointments']} appointment(s), {m['test_drives']} test drive(s), "
                f"{m['worksheets_offers']} offer(s), {m['asks_for_business']} ask(s), {m['outcomes']} outcome(s)."
            ),
            f"Update status: {active_status} Missing updates: {missing_names}.",
            f"Follow-up priority: {overdue} overdue, {due} due today.",
            f"Coaching note: {attention}",
            next_action,
        )
    )


def format_team(report: Mapping[str, Any]) -> str:
    rows = report["team"]
    if not rows:
        return f"Team scorecard — {report['report_date']}\nNo sales updates recorded."
    incomplete_by_name = Counter(item["name"] for item in report["missing"]["incomplete_logs"])
    missing_names = {item["name"] for item in report["missing"]["not_updated"]}
    lines = [
        f"Team scorecard — {report['report_date']}",
        "Name | Activity | Progression | Update status",
    ]
    for row in rows:
        progression = (
            f"{row['test_drives']} drive(s), {row['worksheets_offers']} offer(s), "
            f"{row['asks_for_business']} ask(s), {row['outcomes']} outcome(s)"
        )
        status = "Complete"
        if incomplete_by_name[row["name"]]:
            status = f"Incomplete ({incomplete_by_name[row['name']]})"
        elif row["name"] in missing_names:
            status = "Missing update"
        win = " | progress: outcome logged" if row["outcomes"] else ""
        lines.append(
            f"{row['name']} | {row['updates']} update(s), {row['people_spoken_to']} people, "
            f"{row['appointments']} appt(s) | {progression} | {status}{win}"
        )
    not_updated = [item["name"] for item in report["missing"]["not_updated"] if item["name"] not in {row["name"] for row in rows}]
    if not_updated:
        lines.append("No update yet: " + ", ".join(not_updated))
    return "\n".join(lines)


def format_followups(report: Mapping[str, Any]) -> str:
    lines = [f"Follow-ups — {report['report_date']}"]
    for bucket in ("overdue", "due", "upcoming"):
        items = report["followups"][bucket]
        lines.append(f"{bucket.title()} ({len(items)}):")
        lines.extend(f"- {item['date']} · {item['name']} · {item['next_step']}" for item in items)
        if not items:
            lines.append("- None")
    return "\n".join(lines)


def format_missing(report: Mapping[str, Any]) -> str:
    missing = report["missing"]
    lines = [f"Missing updates — {report['report_date']}"]
    if missing["note"]:
        lines.append(missing["note"])
    lines.append("Not updated: " + (", ".join(item["name"] for item in missing["not_updated"]) or "None identified"))
    lines.append(f"Incomplete logs ({len(missing['incomplete_logs'])}):")
    lines.extend(f"- {item['name']}: {', '.join(item['fields'])}" for item in missing["incomplete_logs"])
    if not missing["incomplete_logs"]:
        lines.append("- None")
    unregistered = missing.get("unregistered_submitters", [])
    lines.append("Unregistered submitters: " + (", ".join(item["name"] for item in unregistered) or "None"))
    return "\n".join(lines)


def format_coaching(report: Mapping[str, Any]) -> str:
    flags = report["coaching_flags"]
    lines = [f"Coaching support — {report['report_date']}"]
    for flag in flags:
        lines.append(f"- {flag['name']}: {_coaching_prompt(flag)}")
    if not flags:
        lines.append("No coaching opportunities surfaced from today's updates.")
    return "\n".join(lines)


def _coaching_prompt(flag: Mapping[str, str]) -> str:
    code = flag.get("code")
    detail = flag.get("detail", "").rstrip(".")
    prompts = {
        "high_traffic_low_test_drives": "Ask what kept conversations from moving to test drives; check whether vehicle fit or timing was the blocker.",
        "test_drive_without_ask": "Check whether an ask for business happened after the drive and what objection needs support.",
        "offer_without_followup_date": "Confirm the follow-up date and next commitment for the offer.",
        "missing_next_step": "Ask for the next step so the customer is not left without an owner.",
        "repeated_incomplete_update": "Help tighten update quality; ask which fields are hard to capture during the shift.",
        "strong_performance": "Recognize the solid progression and ask what worked so it can be repeated.",
    }
    prompt = prompts.get(code)
    if prompt:
        return prompt
    return f"Review this update and ask what support is needed. Note: {detail}." if detail else "Review this update and ask what support is needed."


def _parsed(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("parsed")
    return value if isinstance(value, Mapping) else {}


def _person_id(record: Mapping[str, Any]) -> str:
    return str(record.get("salesperson_id") or record.get("telegram_user_id") or "unknown")


def _record_name(record: Mapping[str, Any], names: Mapping[str, str]) -> str:
    for identity in (record.get("salesperson_id"), record.get("telegram_user_id")):
        name = names.get(str(identity)) if identity is not None else None
        if isinstance(name, str) and name.strip():
            return name.strip()
    return "Unregistered salesperson"


def _name_for_person(person: str, records: Iterable[Mapping[str, Any]], names: Mapping[str, str]) -> str:
    direct = names.get(person)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    matching = next((record for record in records if _person_id(record) == person), None)
    return _record_name(matching, names) if matching is not None else "Unregistered salesperson"


def _record_date(record: Mapping[str, Any]) -> date | None:
    value = str(record.get("submitted_at", ""))[:10]
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _nonnegative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
