#!/usr/bin/env python3
"""Import V3.1 outreach handoffs into the canonical prospect and review paths.

Revisit: when the outreach handoff version, event vocabulary, or Gmail draft
contract changes. · Last touched: 2026-07-23.

This module deliberately reuses ``queue/prospects.jsonl`` for append-only
prospect/history snapshots and ``queue/work_items.jsonl`` for the one operator
review card per prospect.  It does not implement a queue, scheduler, CRM, or
connector framework of its own.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from connectors.gmail_draft_adapter import GmailDraftAdapter, gmail_draft_url, revenue_gmail_user_id
from tools.aos_queue_storage import durable_replace_text, queue_write_lock


ROOT = MODULE_ROOT
PROSPECTS_PATH = Path("queue/prospects.jsonl")
WORK_ITEMS_PATH = Path("queue/work_items.jsonl")
RECEIPTS_DIR = Path("queue/receipts")
HANDOFF_VERSION = "3.1"
WORKFLOW = "ttr_icp_a_prospecting"
PILOT_RECORD_TYPE = "outreach_pilot_v1"
PILOT_VERSION = "1"

PROSPECT_ID_RE = re.compile(r"^TTR-[AB]-[a-z0-9]+(?:-[a-z0-9]+)*$")
DOMAIN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
INTERNAL_REVIEW_LINES = {
    "Manual CASL and role-relevance review required before sending.",
}
EMAIL_SIGNATURE_LINES = (
    "All the best,",
    "",
    "Liam Duff",
    "Time to Revenue",
    "liam@timetorevenue.com",
    "timetorevenue.com",
)
EMAIL_NOT_INTERESTED_FOOTER = (
    'We all hate spam — this is a personal reach-out from me, not an automated email. '
    'If you are not interested in using AI or workflow improvements in your business, '
    'just reply "NOT INTERESTED" and I won\'t reach out again.'
)
LEGACY_OPT_OUT_LINES = {
    "If you would prefer no further contact from me, reply and I will not follow up.",
}

SUPPORTED_EVENTS = frozenset({
    "invitation_sent",
    "connection_accepted",
    "linkedin_message_sent",
    "email_1_sent",
    "email_2_sent",
    "reply_received",
    "not_interested",
    "opt_out",
    "do_not_contact",
    "invalid_contact",
    "wrong_person",
    "wrong_company",
    "declined_connection",
    "prior_contact_discovered",
    "duplicate_detected",
    "active_sequence_found",
    "closed_or_disqualified",
    "cancelled",
})
STOP_EVENTS = frozenset({
    "reply_received",
    "not_interested",
    "opt_out",
    "do_not_contact",
    "invalid_contact",
    "wrong_person",
    "wrong_company",
    "declined_connection",
    "prior_contact_discovered",
    "duplicate_detected",
    "active_sequence_found",
    "closed_or_disqualified",
    "cancelled",
})
REQUIRED_STOP_CONDITIONS = STOP_EVENTS
REQUIRED_REQUESTED_ACTIONS = frozenset({
    "import or update the prospect using stable identifiers",
    "reconcile person, company, domain, related entities and canonical outreach history",
    "create the eligible Gmail draft or selected manual action card",
    "store later-stage copy as inactive",
    "after Liam records the actual event, calculate only the next conditional review",
    "cancel future steps on any stop condition",
})
REQUIRED_PROHIBITED_ACTIONS = frozenset({
    "send email",
    "send LinkedIn message",
    "send connection request",
    "submit contact form",
    "auto-approve outreach",
    "mark a draft or stored message as sent",
    "advance without a recorded prior event",
})


class HandoffValidationError(ValueError):
    """The handoff cannot create active state."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


class OutreachEventError(ValueError):
    """An operator event is invalid for the prospect's recorded state."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{number}: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"invalid JSONL object at {path}:{number}")
        rows.append(value)
    return rows


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)


def _yaml_blocks(text: str) -> list[dict[str, Any]]:
    # Imported lazily so the dashboard event endpoint does not depend on a
    # YAML package merely to append a recorded event.
    import yaml

    blocks = re.findall(r"```yaml\s*\n(.*?)\n```", text, flags=re.DOTALL | re.IGNORECASE)
    values: list[dict[str, Any]] = []
    for number, block in enumerate(blocks, start=1):
        try:
            value = yaml.safe_load(block)
        except yaml.YAMLError as exc:
            raise HandoffValidationError([f"YAML block {number}: {exc}"]) from exc
        if not isinstance(value, dict):
            raise HandoffValidationError([f"YAML block {number}: expected a mapping"])
        values.append(value)
    return values


def parse_handoff(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    blocks = _yaml_blocks(text)
    if len(blocks) < 2:
        raise HandoffValidationError(["handoff requires one header block and at least one prospect block"])
    header, prospects = blocks[0], blocks[1:]
    return header, prospects, _sha(text)


def _date(value: Any, field: str, errors: list[str]) -> str:
    text = str(value or "").strip()
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        errors.append(f"{field}: expected ISO date")
        return text


def _nonempty(value: Any, field: str, errors: list[str]) -> str:
    text = str(value or "").strip()
    if not text:
        errors.append(f"{field}: required")
    return text


def _https_url(value: Any, field: str, errors: list[str], *, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        errors.append(f"{field}: required")
    elif text and not text.startswith("https://"):
        errors.append(f"{field}: expected HTTPS URL")
    return text


def _list_of_text(value: Any, field: str, errors: list[str], *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or any(not str(item).strip() for item in value):
        errors.append(f"{field}: expected a list of non-empty strings")
        return []
    result = [str(item).strip() for item in value]
    if not allow_empty and not result:
        errors.append(f"{field}: at least one value is required")
    return result


def validate_handoff(header: dict[str, Any], prospects: list[dict[str, Any]]) -> None:
    errors: list[str] = []
    if str(header.get("handoff_version") or "") != HANDOFF_VERSION:
        errors.append(f"handoff_version: only {HANDOFF_VERSION} is supported")
    if str(header.get("workflow") or "") != WORKFLOW:
        errors.append(f"workflow: expected {WORKFLOW}")
    _date(header.get("run_date"), "run_date", errors)
    if str(header.get("icp") or "").strip() not in {"A", "B"}:
        errors.append("ICP: expected A or B")
    _nonempty(header.get("scope"), "scope", errors)
    count = header.get("prospect_count")
    if not isinstance(count, int) or isinstance(count, bool) or count != len(prospects):
        errors.append(f"prospect_count: declared {count!r}, parsed {len(prospects)}")

    seen: set[str] = set()
    for index, prospect in enumerate(prospects, start=1):
        prefix = f"prospect {index}"
        prospect_id = _nonempty(prospect.get("prospect_id"), f"{prefix}.prospect_id", errors)
        if prospect_id and not PROSPECT_ID_RE.fullmatch(prospect_id):
            errors.append(f"{prefix}.prospect_id: unstable or invalid V3.1 identifier")
        if prospect_id in seen:
            errors.append(f"{prefix}.prospect_id: duplicate in handoff")
        seen.add(prospect_id)
        _nonempty(prospect.get("person_name"), f"{prefix}.person_name", errors)
        _nonempty(prospect.get("company_name"), f"{prefix}.company_name", errors)
        domain = _nonempty(prospect.get("company_domain"), f"{prefix}.company_domain", errors).lower()
        if domain and not DOMAIN_RE.fullmatch(domain):
            errors.append(f"{prefix}.company_domain: invalid domain")
        _list_of_text(prospect.get("related_entities"), f"{prefix}.related_entities", errors)

        for field in (
            "commercial_readiness", "route_readiness", "automation_readiness",
            "primary_channel", "executable_route_class", "next_prepared_action",
            "route_change_condition", "sequence_status", "previous_action_required",
            "next_event_condition",
        ):
            _nonempty(prospect.get(field), f"{prefix}.{field}", errors)
        score = prospect.get("commercial_fit_score")
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
            errors.append(f"{prefix}.commercial_fit_score: expected integer 0..100")
        if prospect.get("manual_review_required") is not True:
            errors.append(f"{prefix}.manual_review_required: must be true")
        if prospect.get("manual_action_required") is not True:
            errors.append(f"{prefix}.manual_action_required: must be true")

        gmail_eligible = prospect.get("gmail_draft_eligible")
        if not isinstance(gmail_eligible, bool):
            errors.append(f"{prefix}.gmail_draft_eligible: expected boolean")
        if gmail_eligible:
            for field in ("email_to", "email_subject", "email_body", "email_source_url", "email_verification_status", "email_compliance_status"):
                _nonempty(prospect.get(field), f"{prefix}.{field}", errors)
            if prospect.get("email_manual_review_required") is not True:
                errors.append(f"{prefix}.email_manual_review_required: must be true")
            if str(prospect.get("primary_channel") or "") != "email":
                errors.append(f"{prefix}.primary_channel: Gmail-eligible route must be email-first")
        else:
            _nonempty(prospect.get("gmail_draft_block_reason"), f"{prefix}.gmail_draft_block_reason", errors)

        linkedin_ready = prospect.get("linkedin_action_ready")
        if not isinstance(linkedin_ready, bool):
            errors.append(f"{prefix}.linkedin_action_ready: expected boolean")
        if linkedin_ready:
            _https_url(prospect.get("linkedin_profile_url"), f"{prefix}.linkedin_profile_url", errors)
            for field in ("connection_note", "first_linkedin_message", "linkedin_follow_up", "linkedin_soft_close"):
                _nonempty(prospect.get(field), f"{prefix}.{field}", errors)

        delay = prospect.get("follow_up_delay_business_days")
        if not isinstance(delay, int) or isinstance(delay, bool) or delay < 1:
            errors.append(f"{prefix}.follow_up_delay_business_days: expected positive integer")
        stops = set(_list_of_text(prospect.get("stop_conditions"), f"{prefix}.stop_conditions", errors, allow_empty=False))
        missing_stops = sorted(REQUIRED_STOP_CONDITIONS - stops)
        if missing_stops:
            errors.append(f"{prefix}.stop_conditions: missing {', '.join(missing_stops)}")
        requested = set(_list_of_text(prospect.get("agentic_os_requested_actions"), f"{prefix}.agentic_os_requested_actions", errors, allow_empty=False))
        prohibited = set(_list_of_text(prospect.get("prohibited_actions"), f"{prefix}.prohibited_actions", errors, allow_empty=False))
        missing_requested = sorted(REQUIRED_REQUESTED_ACTIONS - requested)
        missing_prohibited = sorted(REQUIRED_PROHIBITED_ACTIONS - prohibited)
        if missing_requested:
            errors.append(f"{prefix}.agentic_os_requested_actions: missing {', '.join(missing_requested)}")
        if missing_prohibited:
            errors.append(f"{prefix}.prohibited_actions: missing {', '.join(missing_prohibited)}")

    if errors:
        raise HandoffValidationError(errors)


def strip_internal_review_instructions(body: str) -> str:
    lines = str(body or "").splitlines()
    filtered = [line for line in lines if line.strip() not in INTERNAL_REVIEW_LINES]
    # YAML's folded paragraphs can leave more than two blank lines after a
    # removed instruction; keep the prospect-facing draft tidy and stable.
    return re.sub(r"\n{3,}", "\n\n", "\n".join(filtered)).strip()


def append_required_email_footer(body: str) -> str:
    """Return prospect-facing email copy with Liam's signature and stop text."""
    clean = strip_internal_review_instructions(body)
    lines = [line.rstrip() for line in clean.splitlines()]
    blocked_tail_lines = set(EMAIL_SIGNATURE_LINES) | {EMAIL_NOT_INTERESTED_FOOTER} | LEGACY_OPT_OUT_LINES
    while lines and (not lines[-1].strip() or lines[-1].strip() in blocked_tail_lines):
        lines.pop()
    main = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    footer = "\n".join((*EMAIL_SIGNATURE_LINES, "", EMAIL_NOT_INTERESTED_FOOTER))
    return f"{main}\n\n{footer}" if main else footer


def add_business_days(value: str | dt.date, days: int) -> str:
    current = dt.date.fromisoformat(value) if isinstance(value, str) else value
    if days < 0:
        raise ValueError("business-day delay cannot be negative")
    remaining = days
    while remaining:
        current += dt.timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current.isoformat()


def _normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _aliases(prospect: dict[str, Any]) -> set[str]:
    values = [
        prospect.get("prospect_id"), prospect.get("person_name"), prospect.get("name"),
        prospect.get("company_name"), prospect.get("company"), prospect.get("company_domain"),
        prospect.get("domain"), *(prospect.get("related_entities") or []),
    ]
    return {item for item in (_normalized(value) for value in values) if item}


def reconcile_prospect(prospect: dict[str, Any], ledger: list[dict[str, Any]], items: list[dict[str, Any]]) -> dict[str, Any]:
    aliases = _aliases(prospect)
    matches: list[dict[str, Any]] = []
    for row in ledger:
        if aliases.intersection(_aliases(row)):
            matches.append(row)
    item_matches = [
        item for item in items
        if aliases.intersection(_aliases((item.get("outreach_review") or {}).get("prospect") or {}))
    ]
    latest = matches[-1] if matches else None
    stop_evidence = []
    active_evidence = []
    for row in matches:
        event = str((row.get("latest_event") or {}).get("type") or "")
        stage = str(row.get("outreach_stage") or "")
        if event in STOP_EVENTS or row.get("do_not_contact") is True:
            stop_evidence.append(event or "do_not_contact")
        if stage and stage not in {"draft_ready", "invitation_ready", "stopped", "completed"}:
            active_evidence.append(stage)
    return {
        "status": "conflict" if stop_evidence or active_evidence else "clear_for_prepared_action",
        "matched_ledger_snapshots": len(matches),
        "matched_review_items": len(item_matches),
        "latest_prospect_id": (latest or {}).get("prospect_id"),
        "stop_evidence": sorted(set(stop_evidence)),
        "active_sequence_evidence": sorted(set(active_evidence)),
        "sources_checked": [
            "queue/prospects.jsonl",
            "queue/work_items.jsonl structured outreach records",
            "canonical Business Brain prospect index (pre-import focused search)",
            "safe captured runtime metadata (pre-import focused search; Gmail SENT excluded)",
        ],
        "focused_review_question": (
            "Agentic OS found no matching canonical outreach-history event. Before acting, confirm you do not know of prior contact, an opt-out, or another active sequence for this person/company."
            if not matches and not item_matches else ""
        ),
        "missing_record_is_not_clearance": not matches and not item_matches,
    }


def _next_queue_id(items: list[dict[str, Any]], year: str) -> str:
    maximum = 0
    prefix = f"AOS-{year}-"
    for item in items:
        value = str(item.get("id") or "")
        if not value.startswith(prefix):
            continue
        try:
            maximum = max(maximum, int(value.rsplit("-", 1)[1]))
        except ValueError:
            pass
    return f"{prefix}{maximum + 1:04d}"


def _source_reference(root: Path, source: Path) -> str:
    try:
        return source.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(source.resolve())


def _initial_card(prospect: dict[str, Any], source_ref: str, source_hash: str, queue_id: str, now: str) -> dict[str, Any]:
    channel = "email" if prospect["gmail_draft_eligible"] else "linkedin"
    stage = "draft_preparing" if channel == "email" else "invitation_ready"
    title = (
        f"{prospect['person_name']} — Email draft ready for review"
        if channel == "email"
        else f"{prospect['person_name']} — LinkedIn invitation ready"
    )
    route_copy = {
        "email_1": {
            "subject": str(prospect.get("email_subject") or ""),
            "body": append_required_email_footer(str(prospect.get("email_body") or "")),
            "active": channel == "email",
        },
        "email_2": {
            "subject": str(prospect.get("email_follow_up_subject") or ""),
            "body": append_required_email_footer(str(prospect.get("email_follow_up_body") or "")),
            "active": False,
        },
        "linkedin_invitation": {"body": str(prospect.get("connection_note") or ""), "active": channel == "linkedin"},
        "linkedin_first_message": {"body": str(prospect.get("first_linkedin_message") or ""), "active": False},
        "linkedin_follow_up": {"body": str(prospect.get("linkedin_follow_up") or ""), "active": False},
        "linkedin_soft_close": {"body": str(prospect.get("linkedin_soft_close") or ""), "active": False},
    }
    exact_action = (
        "Review the Gmail draft, confirm CASL/role relevance and no known prior contact, then send it manually or record the actual outcome here."
        if channel == "email"
        else "Open the public LinkedIn profile, confirm the role and no known prior contact, send this connection invitation manually, then record invitation_sent here."
    )
    outreach = {
        "version": PILOT_VERSION,
        "idempotency_key": _sha(f"{source_hash}\0{prospect['prospect_id']}\0initial"),
        "prospect": {
            "prospect_id": prospect["prospect_id"],
            "person_name": prospect["person_name"],
            "company_name": prospect["company_name"],
            "company_domain": prospect["company_domain"],
            "email": str(prospect.get("email_to") or ""),
            "phone": str(prospect.get("phone_number") or ""),
            "linkedin_url": str(prospect.get("linkedin_profile_url") or prospect.get("linkedin_url") or ""),
            "related_entities": list(prospect.get("related_entities") or []),
        },
        "channel": channel,
        "stage": stage,
        "due_date": None,
        "source_handoff": source_ref,
        "source_hash": source_hash,
        "score": prospect["commercial_fit_score"],
        "readiness": prospect["automation_readiness"],
        "qualification": prospect["qualification_band"],
        "primary_signal": prospect["primary_signal"],
        "main_caution": prospect["main_caution"],
        "manual_review_metadata": ["Manual CASL and role-relevance review required before sending."] if channel == "email" else ["Manual LinkedIn-limit and role review required."],
        "exact_action": exact_action,
        "profile_url": str(prospect.get("linkedin_profile_url") or ""),
        "gmail_draft_reference": None,
        "gmail_draft_url": None,
        "copy": route_copy,
        "follow_up_delay_business_days": prospect["follow_up_delay_business_days"],
        "stop_conditions": list(prospect["stop_conditions"]),
        "reconciliation": {},
        "allowed_events": [],
        "history_count": 0,
        "last_event": None,
        "future_activity_cancelled": False,
        "updated_at": now,
    }
    return {
        "id": queue_id,
        "title": title,
        "status": "inbox" if channel == "email" else "human_review",
        "priority": 90 if prospect["commercial_fit_score"] >= 80 else 74,
        "requested_by": "V3.1 outreach handoff",
        "owner_type": "agent",
        "owner": "revenue",
        "source": "prospecting_daily_run",
        "tags": ["lane:revenue", "prospecting_daily_run", "outreach_handoff_v3_1"],
        "context": f"Prepared {channel} review for {prospect['person_name']} at {prospect['company_name']}; no outreach action has been performed.",
        "sources": [source_ref],
        "source_refs": [source_ref],
        "allowed_actions": ["record_actual_outreach_event", "review_prepared_copy"],
        "stop_conditions": list(prospect["stop_conditions"]),
        "definition_of_done": "Liam records an actual outreach event or stop outcome; stored copy alone never advances state.",
        "parent_id": None,
        "step_index": None,
        "depends_on": [],
        "on_complete": None,
        "workbench": "revenue",
        "review": "none",
        "claim": {"claimed_by": None, "claimed_at": None},
        "receipts": [],
        "needs_me": ["manual outreach action or outcome required"],
        "outreach_review": outreach,
        "created_at": now,
        "updated_at": now,
    }


def _allowed_events(review: dict[str, Any]) -> list[str]:
    if review.get("future_activity_cancelled"):
        return []
    stage = str(review.get("stage") or "")
    primary: list[str] = []
    if stage == "draft_ready":
        primary = ["email_1_sent"]
    elif stage == "email_follow_up_waiting":
        primary = ["email_2_sent"]
    elif stage == "invitation_ready":
        primary = ["invitation_sent"]
    elif stage == "waiting_for_connection":
        primary = ["connection_accepted"]
    elif stage in {"linkedin_first_message_ready", "linkedin_follow_up_waiting", "linkedin_soft_close_waiting"}:
        primary = ["linkedin_message_sent"]
    return primary + sorted(STOP_EVENTS)


def _receipt_path(source_hash: str, prospect_id: str) -> Path:
    return RECEIPTS_DIR / f"outreach-handoff-{source_hash[:12]}-{_sha(prospect_id)[:12]}.md"


def _render_receipt(item: dict[str, Any], *, status: str, validation: str, blocker: str = "None") -> str:
    review = item["outreach_review"]
    prospect = review["prospect"]
    return "\n".join((
        f"# {item['title']}",
        "> Expires: retained as point-in-time outreach handoff evidence. · Created: 2026-07-23.",
        "",
        status,
        "",
        "## Summary for operator",
        f"{prospect['person_name']} at {prospect['company_name']} has one prepared {review['channel']} review card. No outreach action is recorded.",
        "",
        "## Validation",
        validation,
        "",
        "## Blockers",
        blocker,
        "",
        "## External action evidence",
        "Gmail draft creation, when applicable, uses only GMAIL_CREATE_EMAIL_DRAFT. No email send, LinkedIn action, call, or contact-form submission occurred.",
        "",
        "## token_usage",
        "```json",
        json.dumps({"available": False, "unavailable": ["deterministic local import; harness usage unavailable"]}, sort_keys=True),
        "```",
        "",
    ))


def _quarantine_receipt(root: Path, source: Path, source_hash: str, errors: list[str], now: str) -> Path:
    path = root / RECEIPTS_DIR / f"outreach-handoff-{source_hash[:16]}-quarantined.md"
    content = "\n".join((
        "# V3.1 outreach handoff quarantine",
        f"> Expires: retained as point-in-time validation evidence. · Created: {now[:10]}.",
        "",
        "NEEDS ATTENTION",
        "",
        f"Source: {_source_reference(root, source)}",
        "",
        "No prospect, draft, review card, reminder, history event, or CRM dry-run record was activated.",
        "",
        "## Validation errors",
        *(f"- {error}" for error in errors),
        "",
        "## token_usage",
        "```json",
        json.dumps({"available": False, "unavailable": ["deterministic local validation; harness usage unavailable"]}, sort_keys=True),
        "```",
        "",
    ))
    path.parent.mkdir(parents=True, exist_ok=True)
    durable_replace_text(path, content)
    return path


def _status_for_event(event: str, prior: str) -> str:
    if event in {"not_interested", "opt_out", "do_not_contact"}:
        return "do_not_contact"
    if event == "reply_received":
        return "replied_positive"
    if event == "declined_connection":
        return "withdrawn"
    if event in STOP_EVENTS:
        return "rejected"
    if event in {"email_2_sent"}:
        return "touch_2"
    if event in {"email_1_sent", "invitation_sent", "connection_accepted", "linkedin_message_sent"}:
        return "sent"
    return prior


def _crm_dry_run(prospect: dict[str, Any], snapshot: dict[str, Any], source_ref: str) -> dict[str, Any]:
    values = {
        "agentic_os_prospect_id": prospect["prospect_id"],
        "future_gohighlevel_contact_id": None,
        "person": prospect["person_name"],
        "company": prospect["company_name"],
        "email": str(prospect.get("email_to") or ""),
        "phone": str(prospect.get("phone_number") or ""),
        "linkedin_url": str(prospect.get("linkedin_profile_url") or ""),
        "source": source_ref,
        "icp": prospect["icp"],
        "score": prospect["commercial_fit_score"],
        "qualification": prospect["qualification_band"],
        "outreach_stage": snapshot["outreach_stage"],
        "last_contact_date": snapshot.get("last_contact_date"),
        "next_action": snapshot.get("next_action"),
        "reply_status": snapshot.get("reply_status"),
        "outcome": snapshot.get("outcome"),
        "opt_out": snapshot.get("opt_out", False),
        "do_not_contact": snapshot.get("do_not_contact", False),
        "owner": "Liam Duff",
        "notes": snapshot.get("outcome_notes", ""),
        "tags": ["agentic-os", "outreach-handoff-v3.1", f"icp-{str(prospect['icp']).lower()}"],
        "related_company_opportunity": list(prospect.get("related_entities") or []),
        "outreach_history": list(snapshot.get("outreach_history") or []),
    }
    key = _sha(f"gohighlevel-dry-run-v1\0{prospect['prospect_id']}")
    return {
        "mode": "dry_run",
        "provider": "gohighlevel",
        "upsert_key": key,
        "duplicate_prevention": "Agentic OS prospect ID, then normalized person+company+domain; never create when conflict is unresolved.",
        "field_authority": {
            "agentic_os": ["outreach_stage", "last_contact_date", "next_action", "reply_status", "outcome", "outreach_history", "notes", "tags"],
            "gohighlevel": ["future_gohighlevel_contact_id"],
            "preserve_true": ["opt_out", "do_not_contact"],
            "manual_conflict": ["person", "company", "email", "phone", "linkedin_url", "related_company_opportunity"],
        },
        "conflicts": [],
        "record": values,
        "mutation_performed": False,
    }


def _snapshot(prospect: dict[str, Any], item: dict[str, Any], header: dict[str, Any], reconciliation: dict[str, Any], now: str) -> dict[str, Any]:
    review = item["outreach_review"]
    signal_raw = str(prospect.get("signal_date") or "")
    signal_match = re.match(r"^(\d{4}-\d{2})(?:$|\D)", signal_raw)
    signal_date = f"{signal_match.group(1)}-01" if signal_match and len(signal_match.group(1)) == 7 else signal_raw[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", signal_date):
        signal_date = header["run_date"]
    status = "drafted"
    snapshot = {
        "record_type": PILOT_RECORD_TYPE,
        "pilot_version": PILOT_VERSION,
        "prospect_id": prospect["prospect_id"],
        "name": prospect["person_name"],
        "person_name": prospect["person_name"],
        "company": prospect["company_name"],
        "company_name": prospect["company_name"],
        "company_domain": prospect["company_domain"],
        "related_entities": list(prospect.get("related_entities") or []),
        "role": prospect["role"],
        "lane": "recruiting_hr_training" if "recruit" in prospect["company_name"].casefold() or "talent" in prospect["company_name"].casefold() else "commercial_services",
        "icp_variant": prospect["icp"],
        "source_handoff": review["source_handoff"],
        "source_hash": review["source_hash"],
        "handoff_version": header["handoff_version"],
        "signal_date": signal_date,
        "signal_source_url": prospect["signal_source_url"],
        "score": prospect["commercial_fit_score"],
        "tier": "A" if prospect["commercial_fit_score"] >= 80 else "B" if prospect["commercial_fit_score"] >= 65 else "C_monitor" if prospect["commercial_fit_score"] >= 50 else "D_reject",
        "readiness": prospect["automation_readiness"],
        "qualification": prospect["qualification_band"],
        "primary_signal": prospect["primary_signal"],
        "main_caution": prospect["main_caution"],
        "status": status,
        "status_date": header["run_date"],
        "touch_count": 0,
        "next_touch_due": None,
        "outreach_channel": review["channel"],
        "outreach_stage": review["stage"],
        "next_action": review["exact_action"],
        "next_reminder": None,
        "last_contact_date": None,
        "reply_status": "none",
        "outcome": None,
        "opt_out": False,
        "do_not_contact": False,
        "event_id": f"import:{review['idempotency_key']}",
        "latest_event": {"type": "handoff_imported", "occurred_on": header["run_date"], "recorded_at": now},
        "outreach_history": [{"event": "handoff_imported", "occurred_on": header["run_date"], "recorded_at": now}],
        "future_activity_cancelled": False,
        "sequence_copy": copy.deepcopy(review["copy"]),
        "reconciliation": reconciliation,
        "review_item_id": item["id"],
        "gmail_draft_reference": review.get("gmail_draft_reference"),
        "gmail_draft_url": review.get("gmail_draft_url"),
        "outcome_notes": "No external action recorded. Missing canonical history is not treated as proof of no prior contact.",
        "crm_dry_run": {},
    }
    snapshot["crm_dry_run"] = _crm_dry_run(prospect, snapshot, review["source_handoff"])
    return snapshot


def _prospect_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    crm = ((snapshot.get("crm_dry_run") or {}).get("record") or {})
    return {
        "prospect_id": snapshot["prospect_id"],
        "person_name": snapshot["person_name"],
        "company_name": snapshot["company_name"],
        "email_to": crm.get("email", ""),
        "phone_number": crm.get("phone", ""),
        "linkedin_profile_url": crm.get("linkedin_url", ""),
        "icp": snapshot["icp_variant"],
        "commercial_fit_score": snapshot["score"],
        "qualification_band": snapshot["qualification"],
        "related_entities": snapshot.get("related_entities") or [],
    }


def import_handoff(
    source: Path,
    *,
    root: Path = ROOT,
    adapter: GmailDraftAdapter | Any | None = None,
    clock: Callable[[], str] = utc_now,
) -> dict[str, Any]:
    root = Path(root)
    source = Path(source)
    now = clock()
    raw_hash = _sha(source.read_text(encoding="utf-8")) if source.is_file() else _sha(str(source))
    try:
        header, prospects, source_hash = parse_handoff(source)
        validate_handoff(header, prospects)
    except HandoffValidationError as exc:
        receipt = _quarantine_receipt(root, source, raw_hash, exc.errors, now)
        return {
            "status": "quarantined",
            "source": _source_reference(root, source),
            "receipt": receipt.relative_to(root).as_posix(),
            "errors": exc.errors,
            "imported": 0,
            "token_usage": {"available": False},
        }

    source_ref = _source_reference(root, source)
    queue_path = root / WORK_ITEMS_PATH
    ledger_path = root / PROSPECTS_PATH
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)

    created_items: list[dict[str, Any]] = []
    duplicate_ids: list[str] = []
    blocked_ids: list[str] = []
    with queue_write_lock(root):
        items = _read_jsonl(queue_path)
        ledger = _read_jsonl(ledger_path)
        by_key = {
            str((item.get("outreach_review") or {}).get("idempotency_key") or ""): item
            for item in items
        }
        for prospect in prospects:
            key = _sha(f"{source_hash}\0{prospect['prospect_id']}\0initial")
            if key in by_key:
                duplicate_ids.append(prospect["prospect_id"])
                continue
            queue_id = _next_queue_id(items, now[:4])
            item = _initial_card(prospect, source_ref, source_hash, queue_id, now)
            reconciliation = reconcile_prospect(prospect, ledger, items)
            item["outreach_review"]["reconciliation"] = reconciliation
            if reconciliation["status"] == "conflict":
                item["status"] = "needs_input"
                item["needs_me"] = ["focused canonical-history conflict review required"]
                item["outreach_review"]["stage"] = "reconciliation_blocked"
                item["outreach_review"]["exact_action"] = "Resolve the recorded canonical outreach-history conflict; do not contact this prospect."
                blocked_ids.append(prospect["prospect_id"])
            item["outreach_review"]["allowed_events"] = _allowed_events(item["outreach_review"])
            items.append(item)
            by_key[key] = item
            created_items.append(item)
        durable_replace_text(queue_path, _jsonl_text(items))

    draft_adapter = adapter or GmailDraftAdapter(root=root)
    prospect_by_id = {prospect["prospect_id"]: prospect for prospect in prospects}
    draft_results: dict[str, dict[str, Any]] = {}
    for item in created_items:
        review = item["outreach_review"]
        prospect = prospect_by_id[review["prospect"]["prospect_id"]]
        if item["status"] == "needs_input" or review["channel"] != "email":
            continue
        body = review["copy"]["email_1"]["body"]
        receipt = draft_adapter.create_draft(
            work_item_id=item["id"],
            message_identity=prospect["prospect_id"],
            recipient=prospect["email_to"],
            subject=review["copy"]["email_1"]["subject"],
            body=body,
        )
        draft_results[prospect["prospect_id"]] = receipt
        if receipt.get("status") in {"draft-created", "duplicate-replay"} and receipt.get("safe_draft_reference"):
            review["gmail_draft_reference"] = receipt["safe_draft_reference"]
            state = draft_adapter.store.read_state(receipt["idempotency_key"])
            provider_id = str((state or {}).get("provider_draft_id") or "")
            review["gmail_draft_url"] = gmail_draft_url(provider_id)
            review["gmail_draft_mailbox"] = revenue_gmail_user_id()
            review["stage"] = "draft_ready"
            item["status"] = "human_review"
        else:
            review["stage"] = "draft_failed"
            review["exact_action"] = "Review the safe Gmail draft failure and repair the draft connection; do not send or switch channels automatically."
            item["status"] = "blocked"
            item["needs_me"] = ["Gmail draft creation failed"]
            blocked_ids.append(prospect["prospect_id"])
        review["allowed_events"] = _allowed_events(review)
        review["updated_at"] = clock()
        item["updated_at"] = review["updated_at"]

    appended = 0
    receipt_paths: list[str] = []
    with queue_write_lock(root):
        items = _read_jsonl(queue_path)
        item_by_id = {item["id"]: item for item in items}
        for updated in created_items:
            item_by_id[updated["id"]] = updated
        ordered_items = [item_by_id[item["id"]] for item in items]
        durable_replace_text(queue_path, _jsonl_text(ordered_items))

        ledger = _read_jsonl(ledger_path)
        event_ids = {str(row.get("event_id") or "") for row in ledger}
        for item in created_items:
            prospect = prospect_by_id[item["outreach_review"]["prospect"]["prospect_id"]]
            reconciliation = item["outreach_review"]["reconciliation"]
            snapshot = _snapshot(prospect, item, header, reconciliation, clock())
            if snapshot["event_id"] not in event_ids:
                ledger.append(snapshot)
                event_ids.add(snapshot["event_id"])
                appended += 1
            receipt_rel = _receipt_path(source_hash, prospect["prospect_id"])
            receipt_abs = root / receipt_rel
            receipt_abs.parent.mkdir(parents=True, exist_ok=True)
            validation = "V3.1 header, prospect identity, routes, readiness, sequence conditions, stop conditions, requested actions, and prohibited actions validated."
            blocker = "Canonical conflict; action suppressed." if item["status"] == "needs_input" else "None"
            durable_replace_text(receipt_abs, _render_receipt(item, status="PASS" if blocker == "None" else "NEEDS ATTENTION", validation=validation, blocker=blocker))
            rel_text = receipt_rel.as_posix()
            if not any(entry.get("path") == rel_text for entry in item.get("receipts") or []):
                item.setdefault("receipts", []).append({"path": rel_text, "created_at": clock(), "status": item["status"]})
            receipt_paths.append(rel_text)
        durable_replace_text(ledger_path, _jsonl_text(ledger))
        durable_replace_text(queue_path, _jsonl_text(ordered_items))

    return {
        "status": "PASS" if not blocked_ids else "NEEDS ATTENTION",
        "source": source_ref,
        "handoff_version": header["handoff_version"],
        "prospect_count": len(prospects),
        "imported": appended,
        "created_review_cards": len(created_items),
        "duplicate_replay_prospects": duplicate_ids,
        "blocked_prospects": sorted(set(blocked_ids)),
        "draft_results": draft_results,
        "receipts": receipt_paths,
        "crm_dry_run_records": appended,
        "external_actions": {"gmail_drafts_created": sum(1 for value in draft_results.values() if value.get("status") == "draft-created"), "emails_sent": 0, "linkedin_actions": 0, "contact_forms": 0},
        "token_usage": {"available": False},
    }


def _latest_snapshot(rows: list[dict[str, Any]], prospect_id: str) -> dict[str, Any]:
    candidates = [row for row in rows if row.get("record_type") == PILOT_RECORD_TYPE and row.get("prospect_id") == prospect_id]
    if not candidates:
        raise OutreachEventError(f"prospect has no {PILOT_RECORD_TYPE} snapshot: {prospect_id}")
    return candidates[-1]


def _apply_event(review: dict[str, Any], prior: dict[str, Any], event: str, occurred_on: str, note: str, recorded_at: str) -> dict[str, Any]:
    stage = str(review.get("stage") or "")
    due = review.get("due_date")
    if event not in STOP_EVENTS:
        allowed = set(_allowed_events(review)) - STOP_EVENTS
        if event not in allowed:
            raise OutreachEventError(f"{event} is not valid while stage is {stage}")
        if stage in {"email_follow_up_waiting", "linkedin_follow_up_waiting", "linkedin_soft_close_waiting"} and due and occurred_on < due:
            raise OutreachEventError(f"{event} cannot be recorded before due date {due}")

    next_stage = stage
    next_due = None
    exact_action = review.get("exact_action")
    copy_state = copy.deepcopy(review.get("copy") or {})
    if event in STOP_EVENTS:
        next_stage = "stopped"
        exact_action = f"No further outreach. Recorded stop event: {event}."
        for value in copy_state.values():
            value["active"] = False
        review["future_activity_cancelled"] = True
    elif event == "email_1_sent":
        next_stage = "email_follow_up_waiting"
        next_due = add_business_days(occurred_on, int(review["follow_up_delay_business_days"]))
        copy_state["email_1"]["active"] = False
        copy_state["email_2"]["active"] = False
        exact_action = f"Wait until {next_due}. If no stop event occurs, send Email 2 manually and record email_2_sent."
    elif event == "email_2_sent":
        next_stage = "completed"
        copy_state["email_2"]["active"] = False
        exact_action = "Sequence complete. Record any later reply or stop outcome; no further reminder is scheduled."
    elif event == "invitation_sent":
        next_stage = "waiting_for_connection"
        copy_state["linkedin_invitation"]["active"] = False
        exact_action = "Wait for the real connection outcome. Record connection_accepted or a stop outcome; do not send a message yet."
    elif event == "connection_accepted":
        next_stage = "linkedin_first_message_ready"
        next_due = occurred_on
        copy_state["linkedin_first_message"]["active"] = True
        exact_action = "Send the prepared first LinkedIn message manually, then record linkedin_message_sent."
    elif event == "linkedin_message_sent":
        if stage == "linkedin_first_message_ready":
            next_stage = "linkedin_follow_up_waiting"
            copy_state["linkedin_first_message"]["active"] = False
            next_due = add_business_days(occurred_on, int(review["follow_up_delay_business_days"]))
            exact_action = f"Wait until {next_due}. If no stop event occurs, send the prepared LinkedIn follow-up manually and record linkedin_message_sent."
        elif stage == "linkedin_follow_up_waiting":
            next_stage = "linkedin_soft_close_waiting"
            copy_state["linkedin_follow_up"]["active"] = False
            next_due = add_business_days(occurred_on, int(review["follow_up_delay_business_days"]))
            exact_action = f"Wait until {next_due}. If no stop event occurs, send the prepared soft close manually and record linkedin_message_sent."
        else:
            next_stage = "completed"
            copy_state["linkedin_soft_close"]["active"] = False
            exact_action = "Sequence complete. Record any later reply or stop outcome; no further reminder is scheduled."

    updated = copy.deepcopy(review)
    updated.update({
        "stage": next_stage,
        "due_date": next_due,
        "exact_action": exact_action,
        "copy": copy_state,
        "last_event": {"type": event, "occurred_on": occurred_on, "recorded_at": recorded_at, "note": note},
        "history_count": int(review.get("history_count") or 0) + 1,
        "updated_at": recorded_at,
    })
    updated["allowed_events"] = _allowed_events(updated)
    return updated


def record_event(
    item_id: str,
    event: str,
    *,
    occurred_on: str | None = None,
    note: str = "",
    event_id: str | None = None,
    root: Path = ROOT,
    clock: Callable[[], str] = utc_now,
) -> dict[str, Any]:
    event = str(event or "").strip()
    if event not in SUPPORTED_EVENTS:
        raise OutreachEventError(f"unsupported outreach event: {event}")
    if len(str(note or "")) > 500:
        raise OutreachEventError("event note must be 500 characters or fewer")
    date_value = occurred_on or clock()[:10]
    try:
        dt.date.fromisoformat(date_value)
    except ValueError as exc:
        raise OutreachEventError("occurred_on must be an ISO date") from exc

    root = Path(root)
    with queue_write_lock(root):
        items = _read_jsonl(root / WORK_ITEMS_PATH)
        try:
            item = next(row for row in items if row.get("id") == item_id)
        except StopIteration as exc:
            raise OutreachEventError(f"review item not found: {item_id}") from exc
        if not isinstance(item.get("outreach_review"), dict):
            raise OutreachEventError(f"queue item is not an outreach review card: {item_id}")
        review = item["outreach_review"]
        prospect_id = str((review.get("prospect") or {}).get("prospect_id") or "")
        ledger = _read_jsonl(root / PROSPECTS_PATH)
        prior = _latest_snapshot(ledger, prospect_id)
        identity = str(event_id or _sha(f"outreach-event-v1\0{prospect_id}\0{event}\0{date_value}"))
        existing = next((row for row in ledger if row.get("event_id") == identity), None)
        if existing:
            return {"status": "duplicate_replay", "event_id": identity, "prospect_id": prospect_id, "item": item, "snapshot": existing}

        recorded_at = clock()
        updated_review = _apply_event(review, prior, event, date_value, str(note or "").strip(), recorded_at)
        item["outreach_review"] = updated_review
        item["updated_at"] = recorded_at
        if event in STOP_EVENTS:
            item["status"] = "cancelled"
            item["needs_me"] = []
        else:
            item["status"] = "human_review"
            item["needs_me"] = ["manual outreach action or outcome required"]

        snapshot = copy.deepcopy(prior)
        history = list(prior.get("outreach_history") or [])
        history.append({"event": event, "occurred_on": date_value, "recorded_at": recorded_at, "note": str(note or "").strip()})
        snapshot.update({
            "status": _status_for_event(event, str(prior.get("status") or "drafted")),
            "status_date": date_value,
            "touch_count": int(prior.get("touch_count") or 0) + (1 if event in {"email_1_sent", "email_2_sent", "linkedin_message_sent"} else 0),
            "next_touch_due": updated_review.get("due_date"),
            "outreach_stage": updated_review["stage"],
            "next_action": updated_review["exact_action"],
            "next_reminder": ({"due_date": updated_review["due_date"], "condition": "only if no stop event is recorded"} if updated_review.get("due_date") else None),
            "last_contact_date": date_value if event in {"email_1_sent", "email_2_sent", "invitation_sent", "linkedin_message_sent"} else prior.get("last_contact_date"),
            "reply_status": "received" if event == "reply_received" else "not_interested" if event == "not_interested" else prior.get("reply_status", "none"),
            "outcome": event if event in STOP_EVENTS else None,
            "opt_out": event == "opt_out" or bool(prior.get("opt_out")),
            "do_not_contact": event in {"not_interested", "opt_out", "do_not_contact"} or bool(prior.get("do_not_contact")),
            "event_id": identity,
            "latest_event": {"type": event, "occurred_on": date_value, "recorded_at": recorded_at, "note": str(note or "").strip()},
            "outreach_history": history,
            "future_activity_cancelled": event in STOP_EVENTS,
            "sequence_copy": copy.deepcopy(updated_review["copy"]),
            "outcome_notes": str(note or "").strip() or f"Actual operator event recorded: {event}.",
        })
        snapshot["crm_dry_run"] = _crm_dry_run(_prospect_from_snapshot(snapshot), snapshot, snapshot["source_handoff"])
        ledger.append(snapshot)
        durable_replace_text(root / PROSPECTS_PATH, _jsonl_text(ledger))
        durable_replace_text(root / WORK_ITEMS_PATH, _jsonl_text(items))

    return {"status": "recorded", "event_id": identity, "prospect_id": prospect_id, "item": item, "snapshot": snapshot}


def main() -> int:
    parser = argparse.ArgumentParser(description="V3.1 Agentic OS outreach handoff importer and event recorder")
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import")
    importer.add_argument("source", type=Path)
    event = commands.add_parser("event")
    event.add_argument("item_id")
    event.add_argument("event", choices=sorted(SUPPORTED_EVENTS))
    event.add_argument("--occurred-on")
    event.add_argument("--note", default="")
    event.add_argument("--event-id")
    args = parser.parse_args()
    if args.command == "import":
        result = import_handoff(args.source, root=args.root)
    else:
        result = record_event(args.item_id, args.event, occurred_on=args.occurred_on, note=args.note, event_id=args.event_id, root=args.root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") not in {"quarantined", "NEEDS ATTENTION"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
