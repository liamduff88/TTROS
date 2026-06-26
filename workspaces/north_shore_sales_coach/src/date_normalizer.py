"""Deterministic follow-up date extraction for the local sales package."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE = ZoneInfo("America/Vancouver")
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

FOLLOWUP_DATE_PATTERN = re.compile(
    r"\b(?:"
    r"\d{4}-\d{2}-\d{2}"
    r"|today|tomorrow|next\s+week"
    r"|(?:(?:this|next)\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r")(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?))?\b",
    re.IGNORECASE,
)
FOLLOWUP_CONTEXT_PATTERN = re.compile(
    r"\b(follow[ -]?up|next step|appointment|call back|contact|come back|return)\b",
    re.IGNORECASE,
)


def normalize_followup_date(text: str, anchor: Any = None) -> str | None:
    """Return the first supported follow-up phrase as an ISO calendar date."""
    match = FOLLOWUP_DATE_PATTERN.search(text)
    if match is None:
        return None
    phrase = re.sub(r"\s+at\s+\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)$", "", match.group(0), flags=re.I)
    phrase = " ".join(phrase.lower().split())
    anchor_date = _anchor_date(anchor)

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", phrase):
        try:
            return date.fromisoformat(phrase).isoformat()
        except ValueError:
            return None
    if phrase == "today":
        return anchor_date.isoformat()
    if phrase == "tomorrow":
        return (anchor_date + timedelta(days=1)).isoformat()
    if phrase == "next week":
        days_until_next_monday = 7 - anchor_date.weekday()
        return (anchor_date + timedelta(days=days_until_next_monday)).isoformat()

    parts = phrase.split()
    modifier, weekday_name = (parts[0], parts[1]) if len(parts) == 2 else (None, parts[0])
    target = WEEKDAYS[weekday_name]
    if modifier == "next":
        next_monday = anchor_date + timedelta(days=7 - anchor_date.weekday())
        return (next_monday + timedelta(days=target)).isoformat()
    days_ahead = (target - anchor_date.weekday()) % 7 or 7
    return (anchor_date + timedelta(days=days_ahead)).isoformat()


def extract_followup_phrase(text: str) -> str | None:
    """Return the supported source phrase, including a simple time when present."""
    match = FOLLOWUP_DATE_PATTERN.search(text)
    return match.group(0) if match else None


def extract_contextual_followup_phrase(text: str) -> str | None:
    """Return the supported date phrase nearest a follow-up action phrase."""
    dates = list(FOLLOWUP_DATE_PATTERN.finditer(text))
    contexts = list(FOLLOWUP_CONTEXT_PATTERN.finditer(text))
    if not dates or not contexts:
        return None

    def distance(date_match: re.Match[str]) -> int:
        return min(
            max(context.start() - date_match.end(), date_match.start() - context.end(), 0)
            for context in contexts
        )

    return min(dates, key=distance).group(0)


def _anchor_date(anchor: Any) -> date:
    if anchor is None:
        return datetime.now(BUSINESS_TIMEZONE).date()
    if isinstance(anchor, datetime):
        if anchor.tzinfo is None:
            return anchor.date()
        return anchor.astimezone(BUSINESS_TIMEZONE).date()
    if isinstance(anchor, date):
        return anchor
    if isinstance(anchor, str):
        value = anchor.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            try:
                return date.fromisoformat(anchor.strip())
            except ValueError:
                return datetime.now(BUSINESS_TIMEZONE).date()
        if parsed.tzinfo is None:
            return parsed.date()
        return parsed.astimezone(BUSINESS_TIMEZONE).date()
    return datetime.now(BUSINESS_TIMEZONE).date()
