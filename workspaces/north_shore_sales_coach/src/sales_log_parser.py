"""Zero-token construction of Honda-shaped draft sales logs."""

from __future__ import annotations

import uuid
import re
from datetime import datetime, timezone
from typing import Any

from .date_normalizer import extract_contextual_followup_phrase, extract_followup_phrase, normalize_followup_date

PARSED_FIELDS = (
    "customer_type",
    "customer_name_or_ref",
    "vehicle_interest",
    "lead_source",
    "interaction_type",
    "appointment_count",
    "walk_in_count",
    "people_spoken_to",
    "test_drive",
    "worksheet_or_offer_presented",
    "asked_for_business",
    "outcome",
    "next_step",
    "followup_date",
    "notes",
)

CORE_FIELDS = ("interaction_type", "vehicle_interest", "outcome", "next_step")
VEHICLES = ("CR-V", "Civic", "Accord", "HR-V", "Pilot", "Passport", "Odyssey", "Ridgeline", "Prologue")
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "couple": 2,
}


def parse_sales_log(
    text: str,
    telegram_user_id: str,
    *,
    salesperson_id: str | None = None,
    source: str = "telegram_dm",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a local record using conservative, deterministic extraction only."""
    raw_text = text.strip()
    if not raw_text:
        raise ValueError("Sales log text cannot be empty")
    if source not in {"telegram_dm", "local", "import"}:
        raise ValueError("Unsupported sales log source")
    timestamp = now or datetime.now(timezone.utc)
    parsed = {field: None for field in PARSED_FIELDS}
    lowered = raw_text.lower()

    for vehicle in VEHICLES:
        flexible = re.escape(vehicle).replace(r"\-", r"[ -]?")
        if re.search(rf"\b{flexible}\b", raw_text, re.IGNORECASE):
            parsed["vehicle_interest"] = vehicle
            break

    if re.search(r"\btest[ -]?(drive|drove|driven|driving)\b", lowered):
        parsed["test_drive"] = True
        parsed["interaction_type"] = "test_drive"
    if re.search(r"\bwalk[ -]?ins?\b", lowered):
        parsed["walk_in_count"] = _count_before_term(lowered, r"walk[ -]?ins?") or 1
        parsed["interaction_type"] = parsed["interaction_type"] or "walk_in"
    if re.search(r"\b(worksheet|numbers|offer|presented)\b", lowered):
        parsed["worksheet_or_offer_presented"] = True
    if re.search(r"\b(asked for (the )?business|asked (them|the customer) to buy|asked to buy|tried to close|closed the deal)\b", lowered):
        parsed["asked_for_business"] = True

    people_match = re.search(
        r"\b(?:spoke|talked)\s+(?:to|with)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|a couple)\s+people\b",
        lowered,
    ) or re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|a couple)\s+people\b", lowered)
    if people_match:
        parsed["people_spoken_to"] = _number_value(people_match.group(1))

    followup = extract_contextual_followup_phrase(raw_text)
    if followup:
        parsed["followup_date"] = normalize_followup_date(followup, timestamp)
        parsed["next_step"] = f"follow-up {followup}"

    missing_fields = [field for field in CORE_FIELDS if parsed[field] is None]
    extracted_count = sum(value is not None for value in parsed.values())
    status = "draft" if extracted_count == 0 else ("complete" if not missing_fields else "needs_followup")
    confidence = 0.0 if extracted_count == 0 else min(0.9, 0.25 + (0.1 * extracted_count))
    return {
        "log_id": str(uuid.uuid4()),
        "submitted_at": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "telegram_user_id": str(telegram_user_id),
        "salesperson_id": str(salesperson_id or telegram_user_id),
        "source": source,
        "raw_text": raw_text,
        "parsed": parsed,
        "missing_fields": missing_fields,
        "coaching_flags": [],
        "confidence": confidence,
        "status": status,
        "llm_used": False,
        "llm_tokens_estimate": None,
    }


def apply_missing_field_answer(record: dict[str, Any], field: str, answer: str) -> dict[str, Any]:
    """Apply one deterministic DM answer to an existing local log."""
    value = answer.strip()
    if not value:
        raise ValueError("Missing-field answer cannot be empty")
    if field not in CORE_FIELDS:
        raise ValueError("Unsupported pending sales field")
    updated = {**record, "parsed": dict(record.get("parsed") or {})}
    parsed = updated["parsed"]
    submitted_at = record.get("submitted_at")
    extracted = parse_sales_log(
        value,
        str(record.get("telegram_user_id", "local")),
        source="local",
        now=_submitted_datetime(submitted_at),
    )["parsed"]

    if field == "vehicle_interest":
        parsed[field] = extracted.get(field) or value
    elif field == "interaction_type":
        parsed[field] = extracted.get(field) or value
    else:
        parsed[field] = value

    followup_phrase = extract_contextual_followup_phrase(value)
    if followup_phrase is None and field == "next_step":
        followup_phrase = extract_followup_phrase(value)
    followup_date = normalize_followup_date(followup_phrase, submitted_at) if followup_phrase else None
    followup_context = re.search(r"\b(follow[ -]?up|come back|return|call back|contact|appointment)\b", value, re.I)
    if followup_date and (followup_context or field == "next_step"):
        parsed["followup_date"] = followup_date
        parsed["next_step"] = value
    elif field == "next_step" and extracted.get("followup_date"):
        parsed["followup_date"] = extracted["followup_date"]

    missing = [name for name in CORE_FIELDS if not parsed.get(name)]
    updated["missing_fields"] = missing
    updated["status"] = "complete" if not missing else "needs_followup"
    updated["llm_used"] = False
    return updated


def _number_value(value: str) -> int:
    normalized = value.lower().removeprefix("a ")
    return int(normalized) if normalized.isdigit() else NUMBER_WORDS[normalized]


def _count_before_term(text: str, term: str) -> int | None:
    match = re.search(
        rf"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|a couple)\s+{term}\b",
        text,
    )
    return _number_value(match.group(1)) if match else None


def _submitted_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
