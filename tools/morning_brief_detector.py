#!/usr/bin/env python3
"""Zero-model-token attention detection for the TTROS morning brief.

Graphify discovers canonical targets. Queue, receipts, the prospect ledger,
and canonical Brain notes decide state. Generated findings are never read as
input on a later run.

Revisit: when queue/prospect status contracts or canonical entity typing changes. · Last touched: 2026-08-04.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

try:
    from business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry
except ModuleNotFoundError:
    from tools.business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry


ROOT = Path(os.environ.get("AOS_ROOT", Path(__file__).resolve().parents[1])).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
GRAPHIFY_ROOT = Path("/home/liam/graphify-brain")
GRAPHIFY_NAMESPACE = "ttros-business-brain"
ACTIVE_QUEUE_STATUSES = frozenset({"inbox", "agent_todo", "agent_working", "needs_input", "human_review", "blocked"})
LIAM_QUEUE_STATUSES = frozenset({"needs_input", "human_review"})
TERMINAL_QUEUE_STATUSES = frozenset({"done", "cancelled"})
TERMINAL_PROSPECT_STATUSES = frozenset({
    "replied_negative", "no_response", "won", "lost", "rejected", "do_not_contact",
})
FOLLOW_UP_PROSPECT_STATUSES = frozenset({"sent", "touch_2"})
DRAFT_INTEGRITY_DAYS = 3
PENDING_CONNECTION_DAYS = 7
TOKEN_USAGE = {"model_invocations": 0, "input_tokens": 0, "output_tokens": 0}
TOKEN_USAGE_TEXT = "Token usage: no agent invocation"
ITEM_RE = re.compile(r"\bAOS-\d{4}-\d{4}\b", re.IGNORECASE)
REVISIT_RE = re.compile(
    r"(?im)^\s*>?\s*Revisit:\s*(.+?)\s*·\s*Last touched:\s*(\d{4}-\d{2}-\d{2})\s*$"
)
FIXTURE_RE = re.compile(
    r"ask hermes from dashboard|phase [ab] validation|test client|\bproof\b|\bsmoke\b|"
    r"\bplaceholder\b|fast[- ]path demo|manual ingest test|block 3 fixture|route[-_ ]repair fixture|"
    r"self[- ]test|harmless approval-routing",
    re.IGNORECASE,
)
EXTERNAL_WORD_RE = re.compile(
    r"\b(?:send|sent|email|linkedin|invite|invitation|message|publish|crm|calendar|drive|withdraw)\b",
    re.IGNORECASE,
)


class MorningBriefError(RuntimeError):
    """Detection could not safely resolve its authoritative scope or inputs."""


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = dt.datetime.fromisoformat(text[:10])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _age(now: dt.datetime, activity: dt.datetime | None) -> dict[str, Any]:
    if activity is None:
        return {"seconds": None, "days": None, "display": "unknown"}
    seconds = max(0, int((now - activity).total_seconds()))
    return {"seconds": seconds, "days": seconds // 86_400, "display": f"{seconds // 86_400}d"}


def _clean(value: Any, limit: int = 180) -> str:
    return " ".join(str(value or "").replace("`", "'").split())[:limit].rstrip()


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _is_fixture(item: dict[str, Any]) -> bool:
    if str(item.get("source") or "") in {"capture/fixture", "phase_b_validation", "local_fixture", "fast_path_demo"}:
        return True
    metadata = [
        str(item.get("id") or ""),
        str(item.get("title") or ""),
        str(item.get("source") or ""),
        str(item.get("requested_by") or ""),
        *(str(value) for value in item.get("tags") or []),
    ]
    return bool(FIXTURE_RE.search("\n".join(metadata)))


def _read_jsonl(path: Path, *, identity: str, required: bool = True) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        if required:
            raise MorningBriefError(f"authoritative source unavailable: {identity}: {type(exc).__name__}") from exc
        return []
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MorningBriefError(f"authoritative source malformed: {identity} line {number}") from exc
        if not isinstance(value, dict):
            raise MorningBriefError(f"authoritative source contains a non-object: {identity} line {number}")
        rows.append(value)
    return rows


def _latest(rows: Iterable[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = str(row.get(key) or "").strip()
        if identity:
            result[identity] = row
    return result


def _frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    try:
        fields = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError as exc:
        raise MorningBriefError("canonical Brain note has malformed frontmatter") from exc
    return (fields if isinstance(fields, dict) else {}), text[end + 5 :]


def _title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return _clean(line[2:], 120)
    return _clean(fallback, 120)


def _safe_receipt_reference(root: Path, value: Any) -> str | None:
    raw = str(value or "").strip()
    rel = Path(raw)
    if not raw or rel.is_absolute() or rel.parts[:2] != ("queue", "receipts"):
        return None
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return raw if target.is_file() else None


def _last_queue_activity(root: Path, item: dict[str, Any]) -> tuple[dt.datetime | None, str]:
    candidates: list[tuple[dt.datetime, str]] = []
    item_id = str(item.get("id") or "")
    for receipt in item.get("receipts") or []:
        if not isinstance(receipt, dict):
            continue
        path = _safe_receipt_reference(root, receipt.get("path"))
        stamp = _parse_time(receipt.get("created_at"))
        if path and stamp:
            candidates.append((stamp, path))
    for effect in (item.get("orchestration_effects") or {}).values():
        if isinstance(effect, dict):
            stamp = _parse_time(effect.get("created_at"))
            if stamp:
                candidates.append((stamp, f"queue/work_items.jsonl#{item_id}:orchestration_effects"))
    if candidates:
        return max(candidates, key=lambda row: (row[0], row[1].startswith("queue/receipts/"), row[1]))
    stamp = _parse_time(item.get("updated_at") or item.get("created_at"))
    return stamp, f"queue/work_items.jsonl#{item_id}"


def _has_recorded_outcome(item: dict[str, Any], prospect: dict[str, Any] | None) -> bool:
    review = item.get("outreach_review") if isinstance(item.get("outreach_review"), dict) else {}
    last_event = review.get("last_event")
    reply_status = str((prospect or {}).get("reply_status") or "").strip().casefold()
    return bool(
        last_event
        or (prospect or {}).get("outcome")
        or reply_status not in {"", "none", "pending", "not_received"}
        or str(item.get("review") or "") in {"ACCEPT", "REVISE"}
    )


def _external_gate(item: dict[str, Any]) -> bool:
    return isinstance(item.get("outreach_review"), dict) or bool(
        EXTERNAL_WORD_RE.search(" ".join(str(value) for value in item.get("allowed_actions") or []))
    )


@dataclasses.dataclass(frozen=True)
class Finding:
    finding_id: str
    rule: str
    supporting_rules: tuple[str, ...]
    category: str
    owner_class: str
    title: str
    entity_id: str
    entity_path: str
    current_state: dict[str, Any]
    reason: str
    last_relevant_activity: dict[str, Any]
    calculated_age: dict[str, Any]
    supporting_references: tuple[str, ...]
    waits_on: str
    next_permitted_action: str
    external_action_boundary: str
    observation_timestamp: str
    discovery: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        value = dataclasses.asdict(self)
        value["supporting_rules"] = list(self.supporting_rules)
        value["supporting_references"] = list(self.supporting_references)
        return value


@dataclasses.dataclass(frozen=True)
class DetectionResult:
    observed_at: str
    client_scope: str
    findings: tuple[Finding, ...]
    discovery: dict[str, Any]
    source_state_sha256: str
    token_usage: dict[str, int] = dataclasses.field(default_factory=lambda: dict(TOKEN_USAGE))
    token_usage_text: str = TOKEN_USAGE_TEXT

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "observed_at": self.observed_at,
            "client_scope": self.client_scope,
            "finding_count": len(self.findings),
            "findings": [finding.to_dict() for finding in self.findings],
            "discovery": self.discovery,
            "source_state_sha256": self.source_state_sha256,
            "generated_artifact_is_authoritative": False,
            "generated_artifact_used_as_input": False,
            "token_usage": self.token_usage,
            "token_usage_text": self.token_usage_text,
        }


def _finding_id(rule: str, entity_path: str) -> str:
    digest = hashlib.sha256(f"{rule}\0{entity_path}".encode("utf-8")).hexdigest()[:20]
    return f"morning-{digest}"


def _make_finding(
    *,
    now: dt.datetime,
    rule: str,
    supporting_rules: Iterable[str] = (),
    category: str,
    owner_class: str,
    title: str,
    entity_id: str,
    entity_path: str,
    current_state: dict[str, Any],
    reason: str,
    activity: dt.datetime | None,
    activity_reference: str,
    references: Iterable[str],
    waits_on: str,
    next_action: str,
    external_boundary: str,
    discovery: dict[str, Any] | None = None,
) -> Finding:
    refs = tuple(sorted(dict.fromkeys(value for value in references if value)))
    return Finding(
        finding_id=_finding_id(rule, entity_path),
        rule=rule,
        supporting_rules=tuple(sorted(set(supporting_rules) | {rule})),
        category=category,
        owner_class=owner_class,
        title=_clean(title, 120),
        entity_id=_clean(entity_id, 120),
        entity_path=entity_path,
        current_state=current_state,
        reason=_clean(reason, 420),
        last_relevant_activity={"at": _iso(activity) if activity else None, "reference": activity_reference},
        calculated_age=_age(now, activity),
        supporting_references=refs,
        waits_on=_clean(waits_on, 240),
        next_permitted_action=_clean(next_action, 420),
        external_action_boundary=_clean(external_boundary, 300),
        observation_timestamp=_iso(now),
        discovery=discovery or {"route": "direct_authority", "reason": "entity path came from an authoritative source"},
    )


def _canonical_prospect_notes(brain_root: Path) -> dict[str, dict[str, Any]]:
    notes: dict[str, dict[str, Any]] = {}
    directory = brain_root / "prospects"
    if not directory.is_dir():
        return {}
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fields, body = _frontmatter(text)
        if str(fields.get("type") or "") != "prospect":
            continue
        pointer = f"business_brain:{path.relative_to(brain_root).as_posix()}"
        notes[pointer] = {
            "fields": fields,
            "title": _title(body, path.stem),
            "queue_ids": tuple(str(value).upper() for value in fields.get("queue_ids") or []),
        }
    return notes


def _fallback_relationships(
    notes: dict[str, dict[str, Any]],
    item_ids: Iterable[str],
    *,
    client_scope: str,
    registry: ClientScopeRegistry,
) -> dict[str, list[dict[str, Any]]]:
    wanted = set(item_ids)
    result: dict[str, list[dict[str, Any]]] = {item_id: [] for item_id in wanted}
    for pointer, note in notes.items():
        matched = wanted.intersection(note["queue_ids"])
        if not matched:
            continue
        canonical = registry.validate_graph_target(client_scope, GRAPHIFY_NAMESPACE, pointer)
        for item_id in matched:
            result[item_id].append({
                "path": canonical,
                "relationship_reasons": ["direct fallback: canonical queue_ids frontmatter declares the activity relationship"],
            })
    return result


def _discover_relationships(
    *,
    item_ids: Iterable[str],
    brain_root: Path,
    client_scope: str,
    registry: ClientScopeRegistry,
    notes: dict[str, dict[str, Any]],
    graph_query: Callable[[str, str], dict[str, Any]] | None,
    graphify_root: Path,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    ids = tuple(sorted(set(item_ids)))
    if not ids:
        return {}, {"route": "not_needed", "graph_state": "not_queried", "reasons": []}
    registry.resolve_scope(client_scope)
    reasons: list[str] = []
    query = graph_query
    if query is None:
        try:
            from dashboard.backend.business_brain_graph import BusinessBrainGraphService

            service = BusinessBrainGraphService(
                graphify_root=graphify_root,
                vault_root=brain_root,
                registry=registry,
            )
            query = lambda item_id, scope: service.query_targets(item_id, client_scope=scope)
        except Exception as exc:  # safe deterministic fallback; no note body has been returned
            reasons.append(f"Graphify unavailable: {type(exc).__name__}")
    if query is not None:
        discovered: dict[str, list[dict[str, Any]]] = {}
        graph_state = "fresh"
        try:
            for item_id in ids:
                value = query(item_id, client_scope)
                if value.get("graph_state") != "fresh":
                    graph_state = str(value.get("graph_state") or "unavailable")
                    fallback = value.get("fallback") or {}
                    reasons.append(str(fallback.get("reason") or "Graphify did not return a fresh projection"))
                    raise MorningBriefError("Graphify fallback requested")
                rows = []
                for target in value.get("targets") or []:
                    canonical = registry.validate_graph_target(
                        client_scope, GRAPHIFY_NAMESPACE, str(target.get("path") or "")
                    )
                    rows.append({
                        "path": canonical,
                        "relationship_reasons": list(target.get("relationship_reasons") or []),
                    })
                discovered[item_id] = sorted(rows, key=lambda row: row["path"])
            return discovered, {
                "route": "graphify_one_hop",
                "graph_state": graph_state,
                "reasons": ["canonical targets returned after client-scope validation"],
                "token_usage": dict(TOKEN_USAGE),
            }
        except ClientScopeError:
            raise
        except Exception as exc:
            if not reasons:
                reasons.append(f"Graphify query failed: {type(exc).__name__}")
    fallback = _fallback_relationships(notes, ids, client_scope=client_scope, registry=registry)
    return fallback, {
        "route": "canonical_frontmatter_fallback",
        "graph_state": "degraded",
        "reasons": reasons or ["Graphify unavailable"],
        "token_usage": dict(TOKEN_USAGE),
    }


def _open_bullets(text: str, heading: str = "Open") -> list[str]:
    body = text
    section = False
    bullets: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            section = line[3:].strip().casefold() == heading.casefold()
            continue
        if section and line.startswith(("- ", "* ")):
            value = line[2:].strip()
            if value and value.casefold() != "none.":
                bullets.append(value)
    return bullets


def _source_digest(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(str(path).encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<unavailable>")
    return digest.hexdigest()


def _merge(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    owner_order = {"liam_judgment": 0, "liam_review": 1, "external_action_gate": 2, "system_work": 3}
    rule_order = {
        "prospect_review_without_outcome": 0,
        "recorded_contradiction": 1,
        "decision_awaiting_confirmation": 2,
        "item_waiting_on_liam_judgment": 3,
        "prospect_overdue_follow_up": 4,
        "prospect_pending_connection": 5,
        "prospect_no_recent_activity": 6,
        "project_blocked": 7,
        "open_commitment_blocked": 8,
        "unresolved_follow_up": 9,
        "open_commitment": 10,
    }
    selected: dict[str, Finding] = {}
    for finding in findings:
        prior = selected.get(finding.entity_path)
        if prior is None:
            selected[finding.entity_path] = finding
            continue
        prior_key = (owner_order.get(prior.owner_class, 99), rule_order.get(prior.rule, 99), prior.rule)
        current_key = (owner_order.get(finding.owner_class, 99), rule_order.get(finding.rule, 99), finding.rule)
        primary, secondary = (finding, prior) if current_key < prior_key else (prior, finding)
        selected[finding.entity_path] = dataclasses.replace(
            primary,
            supporting_rules=tuple(sorted(set(primary.supporting_rules + secondary.supporting_rules))),
            supporting_references=tuple(sorted(set(primary.supporting_references + secondary.supporting_references))),
        )
    return tuple(sorted(
        selected.values(),
        key=lambda row: (
            owner_order.get(row.owner_class, 99),
            rule_order.get(row.rule, 99),
            row.entity_path.casefold(),
            row.finding_id,
        ),
    ))


def detect(
    *,
    root: Path = ROOT,
    brain_root: Path,
    now: dt.datetime | None = None,
    client_scope: str | None,
    registry: ClientScopeRegistry | None = None,
    graph_query: Callable[[str, str], dict[str, Any]] | None = None,
    graphify_root: Path = GRAPHIFY_ROOT,
) -> DetectionResult:
    """Return a deterministic snapshot of live attention predicates."""
    root = Path(root).resolve()
    brain_root = Path(brain_root).resolve()
    observed = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    gate = registry or load_registry()
    try:
        identity = gate.resolve_scope(client_scope)
    except PermissionError as exc:
        raise MorningBriefError(f"unresolved scope; detection failed closed: {exc}") from exc

    work_path = root / "queue/work_items.jsonl"
    prospect_path = root / "queue/prospects.jsonl"
    items = _latest(_read_jsonl(work_path, identity="queue/work_items.jsonl"), "id")
    prospects = _latest(_read_jsonl(prospect_path, identity="queue/prospects.jsonl"), "prospect_id")
    notes = _canonical_prospect_notes(brain_root)

    relationship_ids = [
        item_id for item_id, item in items.items()
        if str(item.get("status") or "") in ACTIVE_QUEUE_STATUSES
        and isinstance(item.get("outreach_review"), dict)
        and not _is_fixture(item)
    ]
    if (prospects or relationship_ids) and not notes:
        raise MorningBriefError("canonical Brain prospect directory is unavailable")
    relationships, discovery_summary = _discover_relationships(
        item_ids=relationship_ids,
        brain_root=brain_root,
        client_scope=identity.scope_id,
        registry=gate,
        notes=notes,
        graph_query=graph_query,
        graphify_root=Path(graphify_root),
    )

    findings: list[Finding] = []
    prospect_paths_by_item: dict[str, str] = {}
    prospect_rows_by_review = {
        str(row.get("review_item_id") or ""): row for row in prospects.values() if row.get("review_item_id")
    }
    for item_id in relationship_ids:
        item = items[item_id]
        targets = relationships.get(item_id) or []
        if not targets:
            continue
        if len(targets) != 1:
            raise MorningBriefError(f"relationship discovery is ambiguous for {item_id}")
        target = targets[0]
        pointer = str(target["path"])
        note = notes.get(pointer)
        if note is None or item_id not in note["queue_ids"]:
            raise MorningBriefError(f"discovered target is not the canonical prospect declared for {item_id}")
        prospect_paths_by_item[item_id] = pointer
        row = prospect_rows_by_review.get(item_id)
        if str(item.get("status") or "") not in LIAM_QUEUE_STATUSES or _has_recorded_outcome(item, row):
            continue
        activity, activity_ref = _last_queue_activity(root, item)
        channel = str((item.get("outreach_review") or {}).get("channel") or "").casefold()
        name = str(((item.get("outreach_review") or {}).get("prospect") or {}).get("person_name") or note["title"])
        next_action = (
            "Confirm role and prior-contact/opt-out state, then either approve the external invitation or close with a recorded outcome."
            if channel == "linkedin"
            else "Inspect the existing draft, confirm CASL, role, and prior-contact/opt-out state, then either approve the external send or close with a recorded outcome."
        )
        refs = [f"queue/work_items.jsonl#{item_id}", pointer, f"queue/prospects.jsonl#{(row or {}).get('prospect_id', 'no-match')}"]
        refs.extend(
            path for value in item.get("receipts") or []
            if isinstance(value, dict) and (path := _safe_receipt_reference(root, value.get("path")))
        )
        findings.append(_make_finding(
            now=observed,
            rule="prospect_review_without_outcome",
            supporting_rules=("open_commitment", "decision_awaiting_confirmation", "no_recent_activity", "unresolved_follow_up"),
            category="prospect",
            owner_class="liam_judgment",
            title=name,
            entity_id=str(note["fields"].get("id") or item_id),
            entity_path=pointer,
            current_state={
                "queue_status": item.get("status"),
                "canonical_status": note["fields"].get("status"),
                "prospect_ledger_status": (row or {}).get("status"),
                "recorded_outcome": False,
                "system_work": "work_already_done",
                "external_action_gate": "required",
                "decision_waiting_on_liam": True,
            },
            reason="Prospect remains in human review with no recorded outcome since the latest relevant activity.",
            activity=activity,
            activity_reference=activity_ref,
            references=refs,
            waits_on="Liam's internal review and decision.",
            next_action=next_action,
            external_boundary="Not performed by the morning brief; any invitation or email send requires Liam's explicit per-action confirmation.",
            discovery={
                "route": discovery_summary["route"],
                "graph_state": discovery_summary["graph_state"],
                "relationship_reasons": target.get("relationship_reasons") or [],
            },
        ))

    # Prospect-ledger integrity/follow-up predicates come from the existing
    # prospecting skills and validator, not from a new lifecycle vocabulary.
    for prospect_id, row in prospects.items():
        status = str(row.get("status") or "")
        if status in TERMINAL_PROSPECT_STATUSES:
            continue
        review_id = str(row.get("review_item_id") or "")
        if review_id in prospect_paths_by_item:
            continue
        linked_review = items.get(review_id) if review_id else None
        if linked_review and str(linked_review.get("status") or "") in TERMINAL_QUEUE_STATUSES:
            # Queue status is authoritative for work state. A retained drafted
            # prospect/history row must not resurrect a closed review finding.
            continue
        raw_pointer = str(row.get("entity_page_path") or "")
        try:
            pointer = gate.validate_brain_pointer(identity.scope_id, raw_pointer)
        except ClientScopeError:
            continue
        activity = _parse_time(
            ((row.get("latest_event") or {}).get("recorded_at") if isinstance(row.get("latest_event"), dict) else None)
            or row.get("last_contact_date")
            or row.get("status_date")
        )
        age = _age(observed, activity)
        name = str(row.get("person_name") or row.get("name") or prospect_id)
        base = dict(
            now=observed,
            category="prospect",
            title=name,
            entity_id=prospect_id,
            entity_path=pointer,
            current_state={
                "prospect_ledger_status": status,
                "system_work": "outstanding",
                "external_action_gate": "not_granted",
                "decision_waiting_on_liam": False,
            },
            activity=activity,
            activity_reference=f"queue/prospects.jsonl#{prospect_id}",
            references=(f"queue/prospects.jsonl#{prospect_id}", pointer),
            external_boundary="No outreach is performed by the morning brief; any later send remains explicitly approval-gated.",
        )
        due = _parse_time(row.get("next_touch_due"))
        if status in FOLLOW_UP_PROSPECT_STATUSES and due and due.date() <= observed.date():
            findings.append(_make_finding(
                **base,
                rule="prospect_overdue_follow_up",
                supporting_rules=("unresolved_follow_up",),
                owner_class="system_work",
                reason=f"Prospect has a recorded next_touch_due of {due.date().isoformat()}, which is due or overdue at observation time.",
                waits_on="The existing Revenue follow-up sweep to prepare the permitted draft or record a stop event.",
                next_action="Run the existing follow-up sweep; prepare the next draft only if no stop event is recorded, then route any external action to Liam.",
            ))
        if (
            status == "sent"
            and str(row.get("outreach_channel") or "").casefold() == "linkedin"
            and age["days"] is not None
            and age["days"] >= PENDING_CONNECTION_DAYS
            and not row.get("future_activity_cancelled")
        ):
            findings.append(_make_finding(
                **base,
                rule="prospect_pending_connection",
                supporting_rules=("unresolved_follow_up",),
                owner_class="liam_review",
                reason=f"LinkedIn connection remains pending for {age['days']} days; the existing workflow flags pending requests at 7 days.",
                waits_on="Liam's review of whether the pending request should be withdrawn.",
                next_action="Review the pending request and, only with explicit approval, withdraw it or record the supported outcome.",
            ))
        if status == "drafted" and age["days"] is not None and age["days"] > DRAFT_INTEGRITY_DAYS:
            findings.append(_make_finding(
                **base,
                rule="prospect_no_recent_activity",
                supporting_rules=("stale_prospect",),
                owner_class="system_work",
                reason=f"Prospect remains drafted for {age['days']} days with no sent or rejected transition; the existing >3-day integrity window is exceeded.",
                waits_on="The existing Revenue workflow to prepare review or record rejection; infrastructure is not the blocker.",
                next_action="Use the existing prospecting workflow to prepare and route review, or record the supported rejected/do-not-contact outcome.",
            ))

    # Every remaining active queue record is an open commitment. Special
    # prospect findings above replace, rather than duplicate, their queue rows.
    for item_id, item in sorted(items.items()):
        status = str(item.get("status") or "")
        if status not in ACTIVE_QUEUE_STATUSES or _is_fixture(item) or item_id in prospect_paths_by_item:
            continue
        activity, activity_ref = _last_queue_activity(root, item)
        refs = [f"queue/work_items.jsonl#{item_id}"]
        refs.extend(
            path for value in item.get("receipts") or []
            if isinstance(value, dict) and (path := _safe_receipt_reference(root, value.get("path")))
        )
        material = bool(refs[1:]) or any(
            "workflows/queue_artifacts/" in str(value)
            for field in ("sources", "source_refs")
            for value in (item.get(field) or [])
        )
        external = _external_gate(item)
        if status in LIAM_QUEUE_STATUSES:
            rule = "decision_awaiting_confirmation"
            owner = "liam_judgment"
            waits = "Liam's internal review, information, or explicit decision."
            next_action = "Review the linked evidence and use an existing queue transition to accept/close it, return it for revision, or cancel it with the outcome preserved."
        elif status == "blocked" and item.get("needs_me"):
            rule = "item_waiting_on_liam_judgment"
            owner = "liam_judgment"
            waits = "Liam's recorded judgment: " + "; ".join(_clean(value, 100) for value in item.get("needs_me") or [])
            next_action = "Supply the requested internal judgment through the existing queue path; do not perform an external action from the brief."
        elif status == "blocked":
            rule = "open_commitment_blocked"
            owner = "system_work"
            waits = "The recorded system blocker to be diagnosed or resolved by the owning lane."
            next_action = "The existing owner diagnoses the blocker and records a supported status/outcome transition."
        else:
            rule = "open_commitment"
            owner = "system_work"
            waits = f"The existing owner ({item.get('owner') or 'unassigned'}) to complete the queued work."
            next_action = "Continue through the existing queue runner and receipt path; no new queue item is needed."
        findings.append(_make_finding(
            now=observed,
            rule=rule,
            supporting_rules=("open_commitment",),
            category="queue",
            owner_class=owner,
            title=str(item.get("title") or item_id),
            entity_id=item_id,
            entity_path=f"queue/work_items.jsonl#{item_id}",
            current_state={
                "queue_status": status,
                "system_work": "work_already_done" if material else "outstanding",
                "external_action_gate": "required" if external else "not_applicable",
                "decision_waiting_on_liam": owner == "liam_judgment",
            },
            reason=(
                f"Queue item is in {status}; prepared evidence exists and the remaining state is review/decision."
                if material and status in LIAM_QUEUE_STATUSES
                else f"Queue item remains in the active {status} state."
            ),
            activity=activity,
            activity_reference=activity_ref,
            references=refs,
            waits_on=waits,
            next_action=next_action,
            external_boundary=(
                "No external action is performed by the morning brief; any send, publish, or external-system mutation remains explicitly approval-gated."
                if external else "No external action is required or performed by the morning brief."
            ),
        ))

    # Canonical open loops augment an entity finding when linked; standalone
    # loops remain query-derived and self-clear when moved/removed.
    open_loops_path = brain_root / "operating_context/open_loops.md"
    if open_loops_path.is_file():
        loop_text = open_loops_path.read_text(encoding="utf-8")
        _loop_fields, _loop_body = _frontmatter(loop_text)
        for bullet in _open_bullets(_loop_body, heading="Revenue review") + _open_bullets(_loop_body, heading="Open"):
            ids = sorted(set(value.upper() for value in ITEM_RE.findall(bullet)))
            if ids:
                # The live queue predicate, never this prose list, decides if
                # the loop is still open.
                for item_id in ids:
                    item = items.get(item_id)
                    if not item or str(item.get("status") or "") not in ACTIVE_QUEUE_STATUSES:
                        continue
                    pointer = prospect_paths_by_item.get(item_id, f"queue/work_items.jsonl#{item_id}")
                    for index, finding in enumerate(findings):
                        if finding.entity_path == pointer:
                            findings[index] = dataclasses.replace(
                                finding,
                                supporting_rules=tuple(sorted(set(finding.supporting_rules + ("unresolved_follow_up",)))),
                                supporting_references=tuple(sorted(set(finding.supporting_references + ("business_brain:operating_context/open_loops.md",)))),
                            )
                continue
            key = hashlib.sha256(bullet.encode("utf-8")).hexdigest()[:16]
            touched = _parse_time((_frontmatter(loop_text)[0].get("hermes_last_write") or {}).get("at"))
            findings.append(_make_finding(
                now=observed,
                rule="unresolved_follow_up",
                category="open_loop",
                owner_class="liam_judgment" if "liam" in bullet.casefold() else "system_work",
                title=_clean(bullet.split(".", 1)[0], 120),
                entity_id=f"open-loop-{key}",
                entity_path=f"business_brain:operating_context/open_loops.md#open-{key}",
                current_state={"canonical_loop_state": "open", "system_work": "outstanding", "external_action_gate": "not_granted", "decision_waiting_on_liam": "liam" in bullet.casefold()},
                reason="Follow-up remains recorded in the canonical Open Loops note and has no linked terminal queue state.",
                activity=touched,
                activity_reference="business_brain:operating_context/open_loops.md",
                references=("business_brain:operating_context/open_loops.md",),
                waits_on="Liam's judgment." if "liam" in bullet.casefold() else "The existing system owner to resolve and record the loop.",
                next_action="Resolve the underlying work through its existing path, then update the canonical loop record; never manually edit a generated brief.",
                external_boundary="No external action is performed by the morning brief.",
            ))

    contradiction_path = brain_root / "inbox/contradictions.md"
    if contradiction_path.is_file():
        text = contradiction_path.read_text(encoding="utf-8")
        fields, body = _frontmatter(text)
        touched = _parse_time((fields.get("hermes_last_write") or {}).get("at"))
        for bullet in _open_bullets(body):
            key = hashlib.sha256(bullet.encode("utf-8")).hexdigest()[:16]
            title = _clean(bullet.split(":", 1)[0], 120)
            findings.append(_make_finding(
                now=observed,
                rule="recorded_contradiction",
                category="contradiction",
                owner_class="liam_judgment",
                title=title,
                entity_id=f"contradiction-{key}",
                entity_path=f"business_brain:inbox/contradictions.md#open-{key}",
                current_state={"contradiction_state": "open", "system_work": "work_already_done", "external_action_gate": "not_applicable", "decision_waiting_on_liam": True},
                reason="Contradiction is recorded under the canonical note's Open heading and has not been moved to Resolved.",
                activity=touched,
                activity_reference="business_brain:inbox/contradictions.md",
                references=("business_brain:inbox/contradictions.md",),
                waits_on="Liam's confirmation of the authoritative interpretation or classification.",
                next_action="Confirm the authoritative state; Hermes may then update the relevant canonical note and move this contradiction to Resolved through the atomic Brain transaction path.",
                external_boundary="No external action is required or performed by the morning brief.",
            ))

    # A typed project is stalled only when its own canonical frontmatter says
    # blocked. Aggregate narrative project lists do not acquire invented state.
    project_candidates = []
    for pointer in gate.permitted_brain_pointers(identity.scope_id):
        if not pointer.startswith("business_brain:"):
            continue
        path = brain_root / pointer.removeprefix("business_brain:")
        if path.suffix == ".md" and path.is_file() and path.parent != brain_root / "prospects":
            project_candidates.append(path)
    for path in sorted(set(project_candidates)):
        text = path.read_text(encoding="utf-8")
        fields, body = _frontmatter(text)
        if str(fields.get("type") or "") != "project" or str(fields.get("status") or "") != "blocked":
            continue
        pointer = f"business_brain:{path.relative_to(brain_root).as_posix()}"
        try:
            pointer = gate.validate_brain_pointer(identity.scope_id, pointer)
        except ClientScopeError:
            continue
        touched_match = REVISIT_RE.search(text)
        touched = _parse_time(touched_match.group(2)) if touched_match else _parse_time(fields.get("date"))
        findings.append(_make_finding(
            now=observed,
            rule="project_blocked",
            category="project",
            owner_class="system_work",
            title=_title(body, path.stem),
            entity_id=str(fields.get("id") or path.stem),
            entity_path=pointer,
            current_state={"canonical_project_status": "blocked", "system_work": "outstanding", "external_action_gate": "not_granted", "decision_waiting_on_liam": False},
            reason="Typed canonical project is explicitly recorded with status blocked.",
            activity=touched,
            activity_reference=pointer,
            references=(pointer,),
            waits_on="The project's recorded blocker to be resolved by its existing owner.",
            next_action="Resolve or reclassify the blocker in the canonical project record; do not clear the generated brief manually.",
            external_boundary="No external action is performed by the morning brief.",
        ))

    merged = _merge(findings)
    source_paths = [work_path, prospect_path, open_loops_path, contradiction_path]
    source_paths.extend(brain_root / pointer.removeprefix("business_brain:").split("#", 1)[0] for pointer in notes)
    source_paths.extend(
        brain_root / pointer.removeprefix("business_brain:")
        for pointer in gate.permitted_brain_pointers(identity.scope_id)
        if pointer.startswith("business_brain:")
    )
    return DetectionResult(
        observed_at=_iso(observed),
        client_scope=identity.scope_id,
        findings=merged,
        discovery=discovery_summary,
        source_state_sha256=_source_digest(source_paths),
    )


def render_markdown(result: DetectionResult) -> list[str]:
    if not result.findings:
        return ["none"]
    lines: list[str] = []
    for finding in result.findings:
        state = json.dumps(finding.current_state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        references = ", ".join(f"`{value}`" for value in finding.supporting_references)
        activity_at = finding.last_relevant_activity.get("at") or "unknown"
        lines.extend((
            f"### {finding.title}",
            f"- Finding: `{finding.finding_id}` · rule: `{finding.rule}` · owner: `{finding.owner_class}`",
            f"- Entity: `{finding.entity_id}` · path: `{finding.entity_path}`",
            f"- Current state: `{state}`",
            f"- Reason: {finding.reason}",
            f"- Last relevant activity: {activity_at} · age: {finding.calculated_age['display']} · source: `{finding.last_relevant_activity['reference']}`",
            f"- Evidence: {references}",
            f"- Waiting on: {finding.waits_on}",
            f"- Permitted next step: {finding.next_permitted_action}",
            f"- External action: {finding.external_action_boundary}",
            f"- Observed: {finding.observation_timestamp}",
            "",
        ))
    return lines[:-1]
