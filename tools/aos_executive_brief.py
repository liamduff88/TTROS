#!/usr/bin/env python3
"""Build the bounded, read-only Agentic OS executive brief.

Revisit: when queue, prospect, capture, or Business Brain evidence contracts change. · Last touched: 2026-08-04.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

try:
    from morning_brief_detector import DetectionResult, detect as detect_attention, render_markdown
except ModuleNotFoundError:
    from tools.morning_brief_detector import DetectionResult, detect as detect_attention, render_markdown


ROOT = Path(os.environ.get("AOS_ROOT", Path(__file__).resolve().parents[1])).resolve()
BRIEF_REL = Path("context/EXECUTIVE_BRIEF.md")
HEADER_REL = Path("context/EXECUTIVE_HEADER.txt")
FINDINGS_REL = Path("context/MORNING_BRIEF_FINDINGS.json")
ACTIVE_STATUSES = frozenset({"inbox", "agent_todo", "agent_working", "needs_input", "human_review", "blocked"})
DECISION_STATUSES = ("human_review", "needs_input")
TERMINAL_PROSPECT_STATUSES = frozenset({"won", "lost", "rejected", "do_not_contact", "withdrawn"})
CANONICAL_POINTERS = (
    "business_brain:operating_context/current_priorities.md",
    "business_brain:operating_context/active_projects.md",
    "business_brain:memory/company.md",
    "business_brain:memory/offers.md",
    "business_brain:memory/sales_and_revenue.md",
    "business_brain:memory/agentic_os.md",
)
CANONICAL_NOTE_ROOTS = (Path("memory"), Path("operating_context"))
LOCAL_NOTE_DIRS = (Path("capture/approved"), Path("context/operator_notes"))
SECTION_NAMES = ("State", "Attention", "Open", "Changed", "Conflicts", "Decisions")
BRIEF_TOKEN_LIMIT = 4_000
HEADER_TOKEN_LIMIT = 250
BRIEF_BYTE_LIMIT = 7_800
RECENT_DAYS = 30
TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
ISO_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
FACT_LINE_RE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:executive\s+)?fact\s*:\s*([^=:\n]{2,100})\s*(?:=|:)\s*([^\n]{1,80})\s*$"
)
DECLARATIVE_FACT_RE = re.compile(
    r"(?im)^\s*([A-Z][A-Za-z0-9 .&+/_-]{2,80}?)\s+(?:is|are|remains?)\s+"
    r"(live|active|benched|paused|inactive|cancelled|canceled|done|gated|manual|approval[- ]gated|disabled|automatic|enabled)\b"
)
HEADING_FACT_RE = re.compile(
    r"(?im)^#{2,6}\s+(.{2,100}?)\s+(?:—|--|:)\s*"
    r"(live|active|benched|paused|inactive|cancelled|canceled|done|gated|manual|approval[- ]gated|disabled|automatic|enabled)\s*$"
)
TODO_RE = re.compile(r"(?im)^\s*(?:[-*]\s*\[ \]|TODO:\s*|[-*]\s+TODO:\s*)(.+?)\s*$")
PROHIBITED_PARTS = frozenset({"_backups", "raw", "attachments", "secrets", "tokens", "credentials"})
NOTE_META_RE = re.compile(
    r"(?im)^\s*>?\s*Revisit:\s*(.+?)\s*·\s*Last touched:\s*(\d{4}-\d{2}-\d{2})\s*$"
)
BRIEF_FIXTURE_RE = re.compile(
    r"ask hermes from dashboard|phase [ab] validation|test client|\bproof\b|\bsmoke\b|"
    r"\bplaceholder\b|fast[- ]path demo|manual ingest test|block 3 fixture|route[-_ ]repair fixture",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Issue:
    path: str
    reason: str


@dataclass
class Evidence:
    sources: set[str] = field(default_factory=set)
    issues: list[Issue] = field(default_factory=list)
    queue_items: list[dict[str, Any]] = field(default_factory=list)
    runs: list[dict[str, Any]] = field(default_factory=list)
    prospects: list[dict[str, Any]] = field(default_factory=list)
    canonical_text: dict[str, str] = field(default_factory=dict)
    canonical_facts: list[tuple[str, str, str]] = field(default_factory=list)
    recent_facts: list[tuple[str, str, str]] = field(default_factory=list)
    canonical_todos: list[tuple[str, str]] = field(default_factory=list)
    local_todos: list[tuple[str, str]] = field(default_factory=list)
    canonical_note_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    canonical_notes_read: list[str] = field(default_factory=list)
    canonical_notes_skipped: list[Issue] = field(default_factory=list)
    source_times: dict[str, datetime] = field(default_factory=dict)


@dataclass(frozen=True)
class OpenEntry:
    sort_at: datetime
    display_date: str
    status: str
    identity: str
    title: str
    source: str
    material: bool = False
    fixture: bool = False

    def line(self) -> str:
        return (
            f"- {self.display_date} · {self.status} · {self.identity} — "
            f"{_clean(self.title, 120)} — source: `{self.source}`"
        )


@dataclass(frozen=True)
class RefreshOutcome:
    exit_code: int
    header: str
    brief: str
    reason: str = ""
    duration_seconds: float = 0.0


def token_count(text: str) -> int:
    """Return a deterministic, dependency-free conservative token estimate."""
    lexical = len(TOKEN_RE.findall(text))
    # IDs and Markdown punctuation split much more heavily than prose in the
    # runtime tokenizer. Two UTF-8 bytes per token keeps the no-dependency CLI
    # safely below the model cap without making tokenizer availability a runtime
    # requirement.
    byte_floor = math.ceil(len(text.encode("utf-8")) / 2)
    return max(lexical, byte_floor)


def _clean(value: Any, limit: int = 160) -> str:
    text = " ".join(str(value or "").replace("`", "'").split())
    return text[:limit].rstrip()


def _parse_time(value: Any, fallback: datetime | None = None) -> datetime:
    text = str(value or "").strip()
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            pass
        if ISO_PREFIX_RE.match(text):
            try:
                return datetime.fromisoformat(text[:10]).replace(tzinfo=UTC)
            except ValueError:
                pass
    return fallback or datetime.max.replace(tzinfo=UTC)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _add_issue(evidence: Evidence, path: str, reason: str) -> None:
    issue = Issue(_clean(path, 180), _clean(reason, 180))
    if issue not in evidence.issues:
        evidence.issues.append(issue)


def _set_source_time(evidence: Evidence, source: str, value: Any) -> None:
    parsed = _parse_time(value, datetime.min.replace(tzinfo=UTC))
    if parsed.year > 1:
        evidence.source_times[source] = max(parsed, evidence.source_times.get(source, parsed))


def _read_jsonl(path: Path, citation: str, evidence: Evidence) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        _add_issue(evidence, citation, f"unavailable: {exc.strerror or type(exc).__name__}")
        return []
    rows: list[dict[str, Any]] = []
    malformed = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            malformed += 1
    if malformed:
        _add_issue(evidence, citation, f"ignored {malformed} malformed JSONL line(s)")
    if lines and not rows:
        return []
    evidence.sources.add(citation)
    return rows


def _latest_by(rows: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    for row in rows:
        identity = str(row.get(key) or "").strip()
        if identity:
            latest[identity] = row
        else:
            anonymous.append(row)
    return [*latest.values(), *anonymous]


def _safe_receipt_path(root: Path, relative: str) -> Path | None:
    rel = Path(relative)
    if rel.is_absolute() or rel.suffix.lower() != ".json" or not rel.parts:
        return None
    lowered = {part.casefold() for part in rel.parts}
    if rel.parts[:2] != ("queue", "receipts") or lowered & PROHIBITED_PARTS:
        return None
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def _fact_pairs(value: Any) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    if isinstance(value, dict):
        pairs.extend((str(key), str(item)) for key, item in value.items())
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                subject = item.get("subject") or item.get("name")
                state = item.get("value") or item.get("state") or item.get("status")
                if subject and state:
                    pairs.append((str(subject), str(state)))
    return pairs


def _facts_from_text(text: str, *, canonical: bool = False) -> list[tuple[str, str]]:
    facts = [(match.group(1), match.group(2)) for match in FACT_LINE_RE.finditer(text)]
    facts.extend((match.group(1), match.group(2)) for match in DECLARATIVE_FACT_RE.finditer(text))
    if canonical:
        facts.extend((match.group(1), match.group(2)) for match in HEADING_FACT_RE.finditer(text))
        in_benched = False
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("## "):
                in_benched = line[3:].strip().casefold() == "benched"
                continue
            if in_benched and line.startswith("-"):
                subject = re.split(r"\s+(?:—|--)\s+", line[1:].strip(), maxsplit=1)[0]
                if subject:
                    facts.append((subject, "benched"))
    return facts


def _todos_from_text(text: str) -> list[str]:
    todos = [_clean(match.group(1), 160) for match in TODO_RE.finditer(text)]
    in_todo = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.casefold() in {"todo:", "## todo", "### todo"}:
            in_todo = True
            continue
        if in_todo and line.startswith("#"):
            in_todo = False
        elif in_todo and line.startswith(("- ", "* ")):
            todos.append(_clean(line[2:], 160))
        elif in_todo and line:
            in_todo = False
    return list(dict.fromkeys(todo for todo in todos if todo))


def _read_receipts(root: Path, items: list[dict[str, Any]], evidence: Evidence) -> None:
    seen: set[str] = set()
    malformed: list[str] = []
    for item in items:
        item_id = str(item.get("id") or "")
        for receipt in item.get("receipts") or []:
            relative = str(receipt.get("path") if isinstance(receipt, dict) else receipt or "")
            if not relative or relative in seen:
                continue
            seen.add(relative)
            path = _safe_receipt_path(root, relative)
            if path is None:
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                malformed.append(relative)
                continue
            if not isinstance(value, dict):
                malformed.append(relative)
                continue
            evidence.sources.add(relative)
            try:
                _set_source_time(evidence, relative, datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
            except OSError:
                pass
            for field_name in ("executive_facts", "facts", "state_facts"):
                for subject, state in _fact_pairs(value.get(field_name)):
                    evidence.recent_facts.append((subject, state, relative))
            summary = value.get("executive_summary")
            if isinstance(summary, str):
                for subject, state in _facts_from_text(summary):
                    evidence.recent_facts.append((subject, state, relative))
        proposal = item.get("capture_proposal")
        if isinstance(proposal, dict):
            for subject, state in _fact_pairs(proposal.get("executive_facts")):
                evidence.recent_facts.append((subject, state, f"queue/work_items.jsonl#{item_id}"))
    if malformed:
        sample = ", ".join(malformed[:3])
        suffix = f" and {len(malformed) - 3} more" if len(malformed) > 3 else ""
        _add_issue(evidence, "queue/receipts/", f"ignored {len(malformed)} malformed/unavailable referenced JSON receipt(s): {sample}{suffix}")


def _brain_resolver(pointer: str, brain_root: Path):
    try:
        from business_brain import resolve_business_brain_pointer
    except ImportError:
        from tools.business_brain import resolve_business_brain_pointer
    return resolve_business_brain_pointer(pointer, root=brain_root)


def _note_metadata(text: str) -> dict[str, Any]:
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return {"status": "UNKNOWN", "reason": "malformed or missing YAML front matter"}
    if not re.search(r"(?m)^#\s+\S", text):
        return {"status": "UNKNOWN", "reason": "missing Markdown title"}
    match = NOTE_META_RE.search(text)
    if not match:
        return {"status": "UNKNOWN", "reason": "missing parseable Revisit and Last touched metadata"}
    touched = _parse_time(match.group(2), datetime.max.replace(tzinfo=UTC))
    if touched.year == 9999:
        return {"status": "UNKNOWN", "reason": "invalid Last touched stamp"}
    return {
        "status": "READ",
        "reason": "",
        "revisit": _clean(match.group(1), 180),
        "last_touched": touched,
    }


def _read_brain(brain_root: Path, evidence: Evidence) -> None:
    index_pointer = "business_brain:index/MEMORY_INDEX.md"
    try:
        index_path = _brain_resolver(index_pointer, brain_root).resolved_path
        index_path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        _add_issue(evidence, index_pointer, f"unavailable: {_clean(exc, 120)}")
    else:
        evidence.sources.add(index_pointer)

    resolved_brain = brain_root.resolve()
    for relative_root in CANONICAL_NOTE_ROOTS:
        directory = (brain_root / relative_root).resolve()
        try:
            directory.relative_to(resolved_brain)
        except ValueError:
            evidence.canonical_notes_skipped.append(Issue(f"business_brain:{relative_root.as_posix()}", "root escaped canonical Brain"))
            continue
        if not directory.is_dir():
            evidence.canonical_notes_skipped.append(Issue(f"business_brain:{relative_root.as_posix()}", "canonical note root is unavailable"))
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(brain_root).as_posix()
            pointer = f"business_brain:{relative}"
            lowered = {part.casefold() for part in path.relative_to(directory).parts}
            if path.is_symlink():
                evidence.canonical_notes_skipped.append(Issue(pointer, "symbolic-link note skipped"))
                continue
            if lowered & PROHIBITED_PARTS:
                evidence.canonical_notes_skipped.append(Issue(pointer, "protected path component"))
                continue
            if path.suffix.casefold() != ".md":
                evidence.canonical_notes_skipped.append(Issue(pointer, "not a Markdown note"))
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                reason = f"UNKNOWN: unreadable ({type(exc).__name__})"
                evidence.canonical_notes_skipped.append(Issue(pointer, reason))
                evidence.canonical_note_meta[pointer] = {"status": "UNKNOWN", "reason": reason}
                continue
            evidence.sources.add(pointer)
            evidence.canonical_notes_read.append(pointer)
            evidence.canonical_text[pointer] = text
            evidence.canonical_note_meta[pointer] = _note_metadata(text)
            for subject, state in _facts_from_text(text, canonical=True):
                evidence.canonical_facts.append((subject, state, pointer))
            evidence.canonical_todos.extend((todo, pointer) for todo in _todos_from_text(text))


def _read_local_notes(root: Path, evidence: Evidence) -> None:
    for relative_dir in LOCAL_NOTE_DIRS:
        directory = root / relative_dir
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".md", ".json"}:
                continue
            lowered = {part.casefold() for part in path.relative_to(root).parts}
            if lowered & PROHIBITED_PARTS:
                continue
            citation = path.relative_to(root).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                _add_issue(evidence, citation, f"unavailable: {exc.strerror or type(exc).__name__}")
                continue
            evidence.sources.add(citation)
            try:
                _set_source_time(evidence, citation, datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
            except OSError:
                pass
            if path.suffix.lower() == ".json":
                try:
                    value = json.loads(text)
                except json.JSONDecodeError:
                    _add_issue(evidence, citation, "ignored malformed approved note")
                    continue
                if isinstance(value, dict):
                    for field_name in ("executive_facts", "facts", "state_facts"):
                        for subject, state in _fact_pairs(value.get(field_name)):
                            evidence.recent_facts.append((subject, state, citation))
                    todos = value.get("commitments")
                    if isinstance(todos, list):
                        evidence.local_todos.extend((_clean(item, 160), citation) for item in todos if str(item).strip())
            else:
                evidence.recent_facts.extend((subject, state, citation) for subject, state in _facts_from_text(text))
                evidence.local_todos.extend((todo, citation) for todo in _todos_from_text(text))


def collect_evidence(root: Path, brain_root: Path, now: datetime) -> Evidence:
    evidence = Evidence()
    work_rows = _read_jsonl(root / "queue/work_items.jsonl", "queue/work_items.jsonl", evidence)
    evidence.queue_items = _latest_by(work_rows, "id")
    evidence.runs = _read_jsonl(root / "queue/run_ledger.jsonl", "queue/run_ledger.jsonl", evidence)
    prospect_rows = _read_jsonl(root / "queue/prospects.jsonl", "queue/prospects.jsonl", evidence)
    evidence.prospects = _latest_by(prospect_rows, "prospect_id")
    cutoff = now - timedelta(days=RECENT_DAYS)
    recent_items = []
    for item in evidence.queue_items:
        updated = _parse_time(item.get("updated_at") or item.get("created_at"))
        if updated.year < 9999 and updated >= cutoff:
            recent_items.append(item)
    for item in recent_items:
        source = str(item.get("source") or "")
        citation = f"queue/work_items.jsonl#{item.get('id', '')}"
        _set_source_time(evidence, citation, item.get("updated_at") or item.get("created_at"))
        if source.startswith("capture/"):
            continue
        for field_name in ("executive_facts", "facts", "state_facts"):
            for subject, state in _fact_pairs(item.get(field_name)):
                evidence.recent_facts.append((subject, state, citation))
        for field_name in ("title", "context"):
            value = item.get(field_name)
            if isinstance(value, str):
                evidence.recent_facts.extend((subject, state, citation) for subject, state in _facts_from_text(value))
    _read_receipts(root, recent_items, evidence)
    _read_brain(brain_root, evidence)
    _read_local_notes(root, evidence)
    return evidence


def _semantic_state(value: str) -> str | None:
    normalized = re.sub(r"[_\s]+", "-", value.strip().casefold())
    if normalized in {"active", "live", "enabled"}:
        return "active"
    if normalized in {"benched", "paused", "inactive", "cancelled", "canceled", "done", "disabled"}:
        return "inactive"
    if normalized in {"gated", "manual", "approval-gated"}:
        return "guarded"
    if normalized == "automatic":
        return "automatic"
    return None


def _subject_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _run_time(row: dict[str, Any]) -> datetime:
    return _parse_time(row.get("done") or row.get("created") or row.get("timestamp"), datetime.min.replace(tzinfo=UTC))


def _revisit_reasons(
    meta: dict[str, Any],
    evidence: Evidence,
    now: datetime,
    *,
    material_change: bool,
) -> list[str]:
    if meta.get("status") != "READ":
        return []
    revisit = str(meta.get("revisit") or "")
    lowered = revisit.casefold()
    touched = meta["last_touched"]
    reasons: list[str] = []
    duration = re.search(r"\b(\d+)\s*[- ]?week", lowered)
    if duration and now >= touched + timedelta(weeks=int(duration.group(1))):
        reasons.append(f"{duration.group(1)}-week interval elapsed")
    if "first three daily runs" in lowered:
        daily = sum(
            _run_time(row) > touched and str(row.get("skill") or "") == "prospecting_daily_run"
            for row in evidence.runs
        )
        if daily >= 3:
            reasons.append(f"first three daily runs completed ({daily} recorded after stamp)")
    if "cycle review" in lowered:
        reviewed = any(
            _run_time(row) > touched
            and str(row.get("skill") or "") in {"prospecting_week_review", "weekly_review"}
            for row in evidence.runs
        )
        if reviewed:
            reasons.append("a cycle-review run is recorded after the stamp")
    if material_change and "change" in lowered:
        reasons.append("the described state changed materially after the stamp")
    return list(dict.fromkeys(reasons))


def _conflict_lines(evidence: Evidence, now: datetime) -> list[str]:
    canonical: dict[str, list[tuple[str, str, str]]] = {}
    for subject, state, source in evidence.canonical_facts:
        semantic = _semantic_state(state)
        key = _subject_key(subject)
        if semantic and key:
            canonical.setdefault(key, []).append((_clean(subject, 90), semantic, source))
    lines: list[str] = []
    seen: set[tuple[str, str]] = set()
    material_changes: dict[str, list[tuple[str, datetime]]] = {}
    for subject, state, source in evidence.recent_facts:
        semantic = _semantic_state(state)
        key = _subject_key(subject)
        if not semantic or key not in canonical:
            continue
        for canonical_subject, canonical_state, canonical_source in canonical[key]:
            pair = frozenset({semantic, canonical_state})
            if semantic == canonical_state or pair not in {
                frozenset({"active", "inactive"}),
                frozenset({"automatic", "guarded"}),
            }:
                continue
            identity = (key, source)
            if identity in seen:
                continue
            seen.add(identity)
            lines.append(
                f"- {_clean(subject, 80)}: recent evidence says {semantic}; canonical note says "
                f"{canonical_state} — sources: `{source}` + `{canonical_source}`"
            )
            source_time = evidence.source_times.get(source)
            if source_time is not None:
                material_changes.setdefault(canonical_source, []).append((source, source_time))
    for pointer in sorted(evidence.canonical_note_meta):
        meta = evidence.canonical_note_meta[pointer]
        if meta.get("status") != "READ":
            continue
        changes = material_changes.get(pointer, [])
        touched = meta["last_touched"]
        newer = sorted((source, stamp) for source, stamp in changes if stamp > touched)
        if newer:
            source, stamp = newer[0]
            lines.append(
                f"- STALE — `{pointer}` Last touched {touched.date().isoformat()} predates material "
                f"evidence {_iso(stamp)} — source: `{source}`"
            )
        for reason in _revisit_reasons(meta, evidence, now, material_change=bool(changes)):
            lines.append(f"- REVISIT MET — `{pointer}` — {reason}")
    return sorted(lines, key=str.casefold)


def _unknown_lines(evidence: Evidence) -> list[str]:
    return [
        f"- `{pointer}` — {_clean(meta.get('reason'), 140)}"
        for pointer, meta in sorted(evidence.canonical_note_meta.items())
        if meta.get("status") == "UNKNOWN"
    ]


def _conflicts_section_lines(conflicts: list[str], unknown: list[str]) -> list[str]:
    return [
        "### Conflicts",
        *(conflicts or ["none"]),
        "",
        "### Unknown",
        *(unknown or ["none"]),
    ]


def _item_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _item_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _item_strings(child)


def _item_has_material(item: dict[str, Any]) -> bool:
    for receipt in item.get("receipts") or []:
        path = str(receipt.get("path") if isinstance(receipt, dict) else receipt or "")
        if path.startswith("queue/receipts/"):
            return True
    return any("workflows/queue_artifacts/" in value for value in _item_strings(item))


def _item_is_fixture(item: dict[str, Any]) -> bool:
    source = str(item.get("source") or "")
    if source in {"capture/fixture", "phase_b_validation", "local_fixture", "fast_path_demo"}:
        return True
    return bool(BRIEF_FIXTURE_RE.search("\n".join(_item_strings(item))))


def _open_entries(evidence: Evidence) -> list[OpenEntry]:
    entries: list[OpenEntry] = []
    for item in evidence.queue_items:
        status = str(item.get("status") or "")
        if status not in ACTIVE_STATUSES:
            continue
        item_id = str(item.get("id") or "unknown")
        updated = _parse_time(
            item.get("updated_at") or item.get("created_at"),
            datetime.min.replace(tzinfo=UTC),
        )
        display = updated.date().isoformat() if updated.year > 1 else "undated"
        entries.append(OpenEntry(
            updated,
            display,
            status,
            item_id,
            str(item.get("title") or "untitled commitment"),
            f"queue/work_items.jsonl#{item_id}",
            _item_has_material(item),
            _item_is_fixture(item),
        ))
    return entries


def _open_lines(evidence: Evidence, now: datetime) -> tuple[list[str], int]:
    entries = _open_entries(evidence)
    cutoff = now - timedelta(days=14)
    fixtures = [entry for entry in entries if entry.fixture]
    excluded = [entry for entry in entries if not entry.fixture and not entry.material and entry.sort_at < cutoff]
    eligible = [entry for entry in entries if entry not in excluded and entry not in fixtures]
    recent = sorted(
        eligible,
        key=lambda entry: (entry.sort_at, entry.identity.casefold()),
        reverse=True,
    )[:10]
    selected_ids = {entry.identity for entry in recent}
    stale_material = sorted(
        (
            entry for entry in entries
            if entry.material and not entry.fixture and entry.sort_at < cutoff and entry.identity not in selected_ids
        ),
        key=lambda entry: (entry.sort_at, entry.identity.casefold()),
    )[:5]
    lines = [entry.line() for entry in [*recent, *stale_material]]
    if excluded:
        lines.append(
            f"- {len(excluded)} stale item(s) without artifact or receipt excluded — see dashboard"
        )
    if fixtures:
        lines.append(f"- {len(fixtures)} build fixture(s) excluded — see archive/dashboard")
    return lines, len(excluded)


def _decision_lines(items: list[dict[str, Any]], now: datetime) -> tuple[list[str], int]:
    awaiting = [item for item in items if str(item.get("status") or "") in DECISION_STATUSES]
    selected = sorted(
        awaiting,
        key=lambda item: (
            0 if _item_has_material(item) else 1,
            _parse_time(item.get("created_at"), datetime.max.replace(tzinfo=UTC)),
            str(item.get("id") or ""),
        ),
    )[:10]
    lines = []
    for item in selected:
        created = _parse_time(item.get("created_at"), now)
        age = max(0, int((now - created).total_seconds() // 86_400))
        item_id = str(item.get("id") or "unknown")
        title = _clean(item.get("title") or "untitled", 100)
        status = str(item.get("status") or "unknown")
        lines.append(
            f"- {item_id} — {title} — status: {status} · age: {age}d — "
            f"source: `queue/work_items.jsonl#{item_id}`"
        )
    remaining = len(awaiting) - len(selected)
    if remaining:
        lines.append(f"- {remaining} further items awaiting review — see dashboard")
    return lines, len(awaiting)


def _previous_generated(previous: str) -> datetime | None:
    match = re.search(r"(?m)^> Generated:\s*([^\s]+)\s*·\s*Sources:", previous)
    return _parse_time(match.group(1)) if match else None


def _previous_queue_snapshot(previous: str) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    section = ""
    for line in previous.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if section == "Open":
            match = re.match(r"^-\s+[^\s]+ ?\s*·\s*([a-z_]+)\s*·\s*(AOS-\d{4}-\d{4})\b", line)
            if match:
                snapshot[match.group(2)] = match.group(1)
        elif section == "Decisions" and line.startswith("-"):
            decision_match = re.match(
                r"^-\s+(AOS-\d{4}-\d{4})\s+—.*?status:\s*(human_review|needs_input)\b",
                line,
            )
            if decision_match:
                snapshot[decision_match.group(1)] = decision_match.group(2)
    return snapshot


def _changed_lines(previous: str, items: list[dict[str, Any]]) -> list[str]:
    if not previous:
        return []
    prior = _previous_queue_snapshot(previous)
    prior_generated = _previous_generated(previous)
    current = {
        str(item.get("id")): str(item.get("status"))
        for item in items
        if str(item.get("status")) in ACTIVE_STATUSES and item.get("id")
    }
    by_id = {str(item.get("id")): item for item in items if item.get("id")}
    lines: list[str] = []
    for item_id in sorted(prior):
        if item_id not in current:
            now_status = str((by_id.get(item_id) or {}).get("status") or "absent")
            lines.append(
                f"- {item_id}: {prior[item_id]} → {now_status} — source: `queue/work_items.jsonl#{item_id}`"
            )
        elif current[item_id] != prior[item_id]:
            lines.append(
                f"- {item_id}: {prior[item_id]} → {current[item_id]} — source: `queue/work_items.jsonl#{item_id}`"
            )
    if prior_generated is not None:
        for item_id, status in sorted(current.items()):
            if item_id in prior:
                continue
            created = _parse_time((by_id.get(item_id) or {}).get("created_at"))
            if created > prior_generated and created.year < 9999:
                lines.append(f"- {item_id}: newly open as {status} — source: `queue/work_items.jsonl#{item_id}`")
    if len(lines) > 5:
        omitted = len(lines) - 5
        lines = [*lines[:5], f"- {omitted} additional changes compacted — source: `queue/work_items.jsonl`"]
    return lines


def _state_lines(evidence: Evidence, decision_total: int) -> list[str]:
    queue_counts = Counter(str(item.get("status") or "unknown") for item in evidence.queue_items)
    active_count = sum(queue_counts[status] for status in ACTIVE_STATUSES)
    lines = [
        f"- Queue: {active_count} open; {decision_total} awaiting Liam — source: `queue/work_items.jsonl`"
    ] if "queue/work_items.jsonl" in evidence.sources else []
    capture_pending = sum(
        1 for item in evidence.queue_items
        if str(item.get("status") or "") in ACTIVE_STATUSES
        and str(item.get("source") or "").startswith("capture/gmail")
        and isinstance(item.get("capture_proposal"), dict)
    )
    if capture_pending:
        lines.append(
            f"- Gmail capture: {capture_pending} pending metadata-only proposal(s) — source: `queue/work_items.jsonl`"
        )
    if "queue/prospects.jsonl" in evidence.sources:
        statuses = Counter(str(row.get("status") or "unknown") for row in evidence.prospects)
        summary = ", ".join(f"{key}={statuses[key]}" for key in sorted(statuses)) or "none"
        lines.append(f"- Prospects: {len(evidence.prospects)} current ({summary}) — source: `queue/prospects.jsonl`")
    if "queue/run_ledger.jsonl" in evidence.sources:
        latest = max(
            (_parse_time(row.get("done") or row.get("created"), datetime.min.replace(tzinfo=UTC)) for row in evidence.runs),
            default=datetime.min.replace(tzinfo=UTC),
        )
        latest_text = latest.date().isoformat() if latest.year > 1 else "none"
        lines.append(f"- Runs: {len(evidence.runs)} recorded; latest {latest_text} — source: `queue/run_ledger.jsonl`")
    if evidence.canonical_notes_read:
        pointers = "; ".join(
            f"`{pointer.removeprefix('business_brain:')}`"
            for pointer in sorted(evidence.canonical_notes_read)
        )
        lines.append(f"- Canonical notes READ under `business_brain:` ({len(evidence.canonical_notes_read)}): {pointers}")
    if evidence.canonical_notes_skipped:
        skipped = "; ".join(
            f"`{issue.path.removeprefix('business_brain:')}` ({issue.reason})"
            for issue in sorted(evidence.canonical_notes_skipped, key=lambda item: item.path)
        )
        lines.append(f"- Canonical notes SKIPPED under `business_brain:` ({len(evidence.canonical_notes_skipped)}): {skipped}")
    for issue in sorted(evidence.issues, key=lambda item: (item.path, item.reason)):
        lines.append(f"- Evidence omission: {issue.reason} — source: `{issue.path}`")
    return lines


def _section(name: str, lines: list[str]) -> str:
    return f"## {name}\n" + ("\n".join(lines) if lines else "none")


def _assemble(generated: datetime, source_count: int, sections: dict[str, list[str]]) -> str:
    body = "\n\n".join(_section(name, sections[name]) for name in SECTION_NAMES)
    return f"> Generated: {_iso(generated)} · Sources: {source_count}\n\n{body}\n"


def build_brief(
    evidence: Evidence,
    previous: str,
    now: datetime,
    detection: DetectionResult | None = None,
) -> tuple[str, str]:
    decisions, decision_total = _decision_lines(evidence.queue_items, now)
    conflicts = _conflict_lines(evidence, now)
    unknown = _unknown_lines(evidence)
    state = _state_lines(evidence, decision_total)
    # A prior generated brief is never an authority for the next run. Change
    # history belongs to queue/receipt records, so this projection is empty
    # until an authoritative transition stream is selected.
    changed: list[str] = []
    open_lines, _excluded = _open_lines(evidence, now)
    attention = render_markdown(detection) if detection is not None else []
    sections = {
        "State": state,
        "Attention": attention,
        "Open": open_lines,
        "Changed": changed,
        "Conflicts": _conflicts_section_lines(conflicts, unknown),
        "Decisions": decisions,
    }
    brief = _assemble(now, len(evidence.sources), sections)
    oldest = min(
        (
            _parse_time(item.get("created_at"))
            for item in evidence.queue_items
            if str(item.get("status") or "") in ACTIVE_STATUSES
        ),
        default=None,
    )
    oldest_days = max(0, int((now - oldest).total_seconds() // 86_400)) if oldest else 0
    age_hours = max(0, int((now - _previous_generated(brief)).total_seconds() // 3_600))
    finding_total = len(detection.findings) if detection is not None else 0
    detected_conflicts = sum(
        finding.category == "contradiction"
        for finding in (detection.findings if detection is not None else ())
    )
    liam_total = sum(
        finding.owner_class in {"liam_judgment", "liam_review", "external_action_gate"}
        for finding in (detection.findings if detection is not None else ())
    )
    header = (
        f"{finding_total} deterministic findings · {liam_total} awaiting Liam · "
        f"{len(conflicts) + detected_conflicts} conflicts · {len(unknown)} unknown · "
        f"oldest open commitment {oldest_days}d · brief {age_hours}h old"
    )
    if token_count(header) >= HEADER_TOKEN_LIMIT or "\n" in header:
        raise RuntimeError("executive header exceeds its cap")
    return brief, header


def _good_previous(text: str) -> bool:
    if not text.startswith("> Generated:"):
        return False
    positions = [text.find(f"## {name}") for name in SECTION_NAMES]
    return all(position >= 0 for position in positions) and positions == sorted(positions)


def _write_temp(path: Path, text: str) -> Path:
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def _atomic_write_artifacts(artifacts: list[tuple[Path, str]]) -> None:
    temporary = [(path, _write_temp(path, content)) for path, content in artifacts]
    previous = {
        path: path.read_text(encoding="utf-8") if path.exists() else None
        for path, _content in artifacts
    }
    replaced: list[Path] = []
    try:
        for path, temp in temporary:
            os.replace(temp, path)
            replaced.append(path)
    except Exception:
        for _path, temp in temporary:
            temp.unlink(missing_ok=True)
        for path in reversed(replaced):
            old = previous[path]
            if old is None:
                path.unlink(missing_ok=True)
            else:
                restore = _write_temp(path, old)
                os.replace(restore, path)
        raise


def _atomic_write_pair(brief_path: Path, brief: str, header_path: Path, header: str) -> None:
    _atomic_write_artifacts([(brief_path, brief), (header_path, header + "\n")])


def _atomic_write(path: Path, text: str) -> None:
    temp = _write_temp(path, text)
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _stale_header(previous: str, now: datetime) -> str:
    generated = _previous_generated(previous) or now
    decisions_section = previous.partition("## Decisions\n")[2]
    decisions = set(re.findall(r"AOS-\d{4}-\d{4}", decisions_section))
    further = re.search(r"(?m)^-\s+(\d+) further items awaiting review", decisions_section)
    decision_total = len(decisions) + (int(further.group(1)) if further else 0)
    conflicts_text = previous.partition("## Conflicts\n")[2].partition("\n\n## Decisions")[0]
    if "### Conflicts\n" in conflicts_text and "### Unknown\n" in conflicts_text:
        conflict_rows = conflicts_text.partition("### Conflicts\n")[2].partition("\n\n### Unknown")[0]
        unknown_rows = conflicts_text.partition("### Unknown\n")[2]
        conflicts = sum(1 for line in conflict_rows.splitlines() if line.startswith("- "))
        unknown = sum(1 for line in unknown_rows.splitlines() if line.startswith("- "))
    else:
        legacy_rows = [line for line in conflicts_text.splitlines() if line.startswith("- ")]
        conflicts = sum(1 for line in legacy_rows if not line.startswith("- UNKNOWN —"))
        unknown = sum(1 for line in legacy_rows if line.startswith("- UNKNOWN —"))
    open_text = previous.partition("## Open\n")[2].partition("\n\n## Changed")[0]
    dates = [_parse_time(match.group(1)) for match in re.finditer(r"(?m)^-\s+(\d{4}-\d{2}-\d{2})\s+·", open_text)]
    oldest = min(dates, default=None)
    oldest_days = max(0, int((now - oldest).total_seconds() // 86_400)) if oldest else 0
    age_hours = max(0, int((now - generated).total_seconds() // 3_600))
    return (
        f"{decision_total} awaiting you · {conflicts} conflicts · {unknown} unknown · oldest open commitment "
        f"{oldest_days}d · brief {age_hours}h old · STALE"
    )


def _unavailable_brief(now: datetime) -> str:
    return _assemble(now, 0, {name: [] for name in SECTION_NAMES})


def refresh(
    *,
    root: Path = ROOT,
    brain_root: Path | None = None,
    now: datetime | None = None,
    client_scope: str | None = "global",
    registry: Any = None,
    graph_query: Any = None,
    graphify_root: Path | None = None,
) -> RefreshOutcome:
    started = time.monotonic()
    root = Path(root).resolve()
    now = (now or datetime.now(UTC)).astimezone(UTC)
    brain_root = Path(brain_root) if brain_root is not None else None
    brief_path = root / BRIEF_REL
    header_path = root / HEADER_REL
    findings_path = root / FINDINGS_REL
    try:
        previous = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
    except OSError:
        previous = ""
    good_previous = previous if _good_previous(previous) else ""
    try:
        if not brief_path.parent.is_dir():
            raise RuntimeError(f"artifact directory unavailable: {brief_path.parent}")
        if brain_root is None:
            try:
                from business_brain import BUSINESS_BRAIN_ROOT
            except ImportError:
                from tools.business_brain import BUSINESS_BRAIN_ROOT
            brain_root = BUSINESS_BRAIN_ROOT
        evidence = collect_evidence(root, Path(brain_root), now)
        if not evidence.sources:
            raise RuntimeError("no readable executive evidence sources")
        detection = detect_attention(
            root=root,
            brain_root=Path(brain_root),
            now=now,
            client_scope=client_scope,
            registry=registry,
            graph_query=graph_query,
            graphify_root=graphify_root or Path("/home/liam/graphify-brain"),
        )
        brief, header = build_brief(evidence, "", now, detection)
        findings_json = json.dumps(detection.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        _atomic_write_artifacts([
            (brief_path, brief),
            (header_path, header + "\n"),
            (findings_path, findings_json),
        ])
        return RefreshOutcome(0, header, brief, duration_seconds=time.monotonic() - started)
    except Exception as exc:
        reason = _clean(exc, 300) or type(exc).__name__
        if good_previous:
            # Failure publishes nothing: the entire prior usable artifact set
            # remains byte-exact rather than becoming a mixed-generation pair.
            try:
                header = header_path.read_text(encoding="utf-8").strip()
            except OSError:
                header = "brief stale; prior usable Markdown retained"
            return RefreshOutcome(1, header, good_previous, reason, time.monotonic() - started)
        brief = _unavailable_brief(now)
        header = "brief unavailable"
        try:
            _atomic_write_pair(brief_path, brief, header_path, header)
        except Exception as unavailable_exc:
            reason = f"{reason}; unavailable artifact write failed: {_clean(unavailable_exc, 180)}"
        return RefreshOutcome(1, header, brief, reason, time.monotonic() - started)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--brain-root", type=Path)
    parser.add_argument("--now", help="fixed ISO8601 generation time for deterministic validation")
    parser.add_argument("--client-scope", default="global")
    parser.add_argument("--format", choices=("quiet", "markdown", "json"), default="quiet")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        now = _parse_time(args.now) if args.now else None
        if args.now and (now is None or now.year == 9999):
            raise ValueError("--now must be ISO8601")
    except ValueError as exc:
        print(f"executive brief refresh failed: {exc}", file=sys.stderr)
        return 2
    outcome = refresh(root=args.root, brain_root=args.brain_root, now=now, client_scope=args.client_scope)
    if outcome.exit_code:
        print(f"executive brief refresh failed: {outcome.reason}", file=sys.stderr)
    elif args.format == "markdown":
        print(outcome.brief, end="")
    elif args.format == "json":
        print((Path(args.root).resolve() / FINDINGS_REL).read_text(encoding="utf-8"), end="")
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
