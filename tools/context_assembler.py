#!/usr/bin/env python3
"""Mandatory, relevance-based context assembly for every TTROS model call.

The assembler emits an immutable object with visible per-block byte/token
counts.  It selects relevant Brain sources instead of dumping the vault and
never truncates a selected block silently.

Revisit: when a model surface, Brain retrieval source, or context block changes. · Last touched: 2026-08-04.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Iterable

import yaml

try:
    from brain_memory import VAULT_ROOT, file_sha256, read_session
    from business_brain_context import BrainContextError, ScopedBrainLoader
    from business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry
except ModuleNotFoundError:
    from tools.brain_memory import VAULT_ROOT, file_sha256, read_session
    from tools.business_brain_context import BrainContextError, ScopedBrainLoader
    from tools.business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry


ROOT = Path(os.environ.get("AOS_ROOT", Path(__file__).resolve().parents[1])).resolve()
ASSEMBLY_DIR = ROOT / "queue" / "context_assemblies"
PACK_DIR = ROOT / "context" / "packs"
# The transport marker is an installed-runtime ABI and remains V1.  The
# manifest schema and explicit assembler_version identify the v2 selection
# contract without requiring a second model-call path.
SCHEMA_VERSION = 2
MARKER = "TTROS_ASSEMBLED_CONTEXT_V1"
ASSEMBLER_VERSION = 2
SOFT_BUDGET_TOKENS = 60_000
TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
TERM_RE = re.compile(r"[a-z0-9][a-z0-9&.'’-]+", re.IGNORECASE)
ITEM_RE = re.compile(r"\bAOS-\d{4}-\d{4}\b", re.IGNORECASE)
SOURCE_SHA256_RE = re.compile(r"#sha256=[0-9a-f]{64}", re.IGNORECASE)
SOURCE_ROUTE_RE = re.compile(r"#route=([^#]+)")
POINTER_RE = re.compile(r"business_brain:[A-Za-z0-9_./-]+\.md")
RELATIONSHIP_RE = re.compile(
    r"\b(?:relationship|related|activity|touched|follow[- ]?up|owed|connected|connection|"
    r"recent|history|why|consequence|depends? on|associated)\b|\bAOS-\d{4}-\d{4}\b",
    re.IGNORECASE,
)
TECHNICAL_RE = re.compile(
    r"\b(?:unit tests?|pytest|javascript|typescript|python|backend|frontend|css|html|api route|"
    r"repository|codebase|refactor|bug|build|lint|schema|migration|function|class|module)\b",
    re.IGNORECASE,
)
BUSINESS_RE = re.compile(
    r"\b(?:prospects?|clients?|revenue|offers?|pricing|pipeline|follow[- ]?up|outreach|sales|"
    r"loretta|evan|talent harbour|highway 99|time to revenue|ttros business)\b",
    re.IGNORECASE,
)
OPERATOR_MESSAGE_RE = re.compile(
    r"(?s)(?:^|\n)Current operator message:\n(?P<message>.*?)(?=\n\nRequest metadata for create_task only:|\Z)"
)
EXCLUDED_VAULT_PARTS = {".git", ".obsidian", "_backups", "raw", "attachments"}


class ContextAssemblyError(RuntimeError):
    """A model call attempted to proceed without valid assembled context."""


@dataclasses.dataclass(frozen=True)
class ActualRead:
    """One content-bearing source actually opened after scope validation."""

    identity: str
    retrieval_route: str
    client_scope: str
    content_sha256: str

    def to_dict(self) -> dict[str, str]:
        return dataclasses.asdict(self)


def estimate_tokens(text: str) -> int:
    return len(TOKEN_RE.findall(str(text or "")))


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


@dataclasses.dataclass(frozen=True)
class ContextBlock:
    name: str
    content: str
    sources: tuple[str, ...]
    stable_prefix: bool = False
    selection: str = "required"
    actual_reads: tuple[ActualRead, ...] = ()
    byte_count: int = dataclasses.field(init=False)
    token_count: int = dataclasses.field(init=False)
    sha256: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "byte_count", len(self.content.encode("utf-8")))
        object.__setattr__(self, "token_count", estimate_tokens(self.content))
        object.__setattr__(self, "sha256", _sha(self.content))

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class AssembledContext:
    invocation_id: str
    surface: str
    session_id: str
    classification: str
    client_scope: str
    request: str
    blocks: tuple[ContextBlock, ...]
    created_at: str
    warnings: tuple[str, ...] = ()
    source_discovery_token_usage: dict[str, int] = dataclasses.field(
        default_factory=lambda: {"model_invocations": 0, "input_tokens": 0, "output_tokens": 0}
    )
    schema_version: int = SCHEMA_VERSION
    marker: str = MARKER

    @property
    def total_bytes(self) -> int:
        return sum(block.byte_count for block in self.blocks) + len(self.request.encode("utf-8"))

    @property
    def total_tokens(self) -> int:
        return sum(block.token_count for block in self.blocks) + estimate_tokens(self.request)

    @property
    def provenance(self) -> tuple[str, ...]:
        values: list[str] = []
        for block in self.blocks:
            for source in block.sources:
                if source not in values:
                    values.append(source)
        return tuple(values)

    @property
    def actual_reads(self) -> tuple[ActualRead, ...]:
        values: list[ActualRead] = []
        seen: set[tuple[str, str, str]] = set()
        for block in self.blocks:
            for read in block.actual_reads:
                key = (read.identity, read.retrieval_route, read.content_sha256)
                if key not in seen:
                    values.append(read)
                    seen.add(key)
        return tuple(values)

    def validate(self) -> "AssembledContext":
        if self.marker != MARKER or self.schema_version != SCHEMA_VERSION:
            raise ContextAssemblyError("unknown assembled-context object")
        if not self.invocation_id or not self.surface or not self.request.strip():
            raise ContextAssemblyError("assembled context lacks invocation identity or request")
        names = [block.name for block in self.blocks]
        required = {"identity/company", "current priorities", "executive_view", "action boundaries", "provenance"}
        if not required.issubset(names):
            raise ContextAssemblyError(f"assembled context lacks required blocks: {sorted(required - set(names))}")
        for block in self.blocks:
            if block.byte_count != len(block.content.encode("utf-8")) or block.token_count != estimate_tokens(block.content):
                raise ContextAssemblyError(f"assembled context count mismatch: {block.name}")
            if block.sha256 != _sha(block.content):
                raise ContextAssemblyError(f"assembled context digest mismatch: {block.name}")
            for read in block.actual_reads:
                if not read.identity or not read.retrieval_route or not read.client_scope or len(read.content_sha256) != 64:
                    raise ContextAssemblyError(f"assembled context actual-read provenance is incomplete: {block.name}")
        if self.source_discovery_token_usage != {"model_invocations": 0, "input_tokens": 0, "output_tokens": 0}:
            raise ContextAssemblyError("source discovery must spend zero model tokens")
        return self

    def manifest(self) -> dict[str, Any]:
        return {
            "marker": self.marker,
            "schema_version": self.schema_version,
            "assembler_version": ASSEMBLER_VERSION,
            "invocation_id": self.invocation_id,
            "surface": self.surface,
            "session_id": self.session_id,
            "classification": self.classification,
            "client_scope": self.client_scope,
            "created_at": self.created_at,
            "request": self.request,
            "request_bytes": len(self.request.encode("utf-8")),
            "request_tokens": estimate_tokens(self.request),
            "blocks": [block.to_dict() for block in self.blocks],
            "total_bytes": self.total_bytes,
            "total_tokens": self.total_tokens,
            "warnings": list(self.warnings),
            "provenance": list(self.provenance),
            "actual_reads": [read.to_dict() for read in self.actual_reads],
            "retrieval_hierarchy": ["explicit_pointer", "graphify_one_hop", "exact_search", "direct_canonical_fallback"],
            "whole_vault_default": False,
            "source_discovery_token_usage": self.source_discovery_token_usage,
        }

    def render(self, *, include_request: bool = True) -> str:
        self.validate()
        lines = [
            f"[{MARKER}]",
            f"Invocation: {self.invocation_id}",
            f"Surface: {self.surface}",
            f"Session: {self.session_id or 'N/A'}",
            f"Classification: {self.classification}",
            f"Assembler: v{ASSEMBLER_VERSION}; source discovery model tokens: 0",
            f"Context total: {self.total_tokens} estimated tokens / {self.total_bytes} bytes",
            "No selected block was truncated. Counts are visible below.",
        ]
        if self.warnings:
            lines.extend(("Warnings:", *(f"- {warning}" for warning in self.warnings)))
        for block in self.blocks:
            prefix = "stable-prefix" if block.stable_prefix else "dynamic"
            lines.extend((
                "",
                f"## {block.name} [{block.token_count} tokens / {block.byte_count} bytes · {prefix}]",
                f"Selection: {block.selection}",
                block.content,
            ))
        if include_request:
            lines.extend(("", "## Current request", self.request))
        return "\n".join(lines).rstrip() + "\n"


def require_assembled_context(value: Any) -> AssembledContext:
    if not isinstance(value, AssembledContext):
        raise TypeError("model-call boundary requires AssembledContext; raw prompt strings are forbidden")
    return value.validate()


def _read(
    relative: str,
    *,
    vault_root: Path = VAULT_ROOT,
    client_scope: str = "global",
    registry: ClientScopeRegistry | None = None,
    route: str = "pointer",
) -> tuple[str, str, ActualRead] | None:
    gate = registry or load_registry()
    pointer = f"business_brain:{relative}"
    try:
        resolved = gate.resolve_brain_pointer(client_scope, pointer, root=vault_root)
    except ClientScopeError:
        raise
    path = resolved.resolved_path
    try:
        path.relative_to(vault_root.resolve())
    except ValueError:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    digest = _sha(text)
    return text, f"{pointer}#sha256={digest}", ActualRead(pointer, route, client_scope, digest)


def _frontmatter_body(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    try:
        fields = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        fields = {}
    return fields if isinstance(fields, dict) else {}, text[end + 5 :]


def _block_from_note(
    name: str,
    relative: str,
    *,
    stable: bool,
    missing: str,
    vault_root: Path = VAULT_ROOT,
    client_scope: str = "global",
    registry: ClientScopeRegistry | None = None,
) -> ContextBlock:
    opened = _read(relative, vault_root=vault_root, client_scope=client_scope, registry=registry)
    if opened is None:
        return ContextBlock(name, f"N/A — {missing}", (f"business_brain:{relative}#missing",), stable, "required; unavailable surfaced")
    text, source, actual = opened
    _fields, body = _frontmatter_body(text)
    return ContextBlock(name, body.strip(), (source,), stable, "required canonical note", (actual,))


def classify_request(query: str, explicit: str | None = None) -> str:
    if explicit in {"technical_only", "knowledge_sensitive"}:
        return explicit
    technical = bool(TECHNICAL_RE.search(query))
    business = bool(BUSINESS_RE.search(query))
    return "technical_only" if technical and not business else "knowledge_sensitive"


def relevance_query(request: str) -> str:
    """Strip operator transport/boundary text before relevance scoring."""
    match = OPERATOR_MESSAGE_RE.search(str(request or ""))
    return match.group("message").strip() if match else str(request or "").strip()


def _query_terms(query: str) -> set[str]:
    stop = {
        "this", "that", "with", "from", "have", "what", "when", "where", "which", "about", "into",
        "please", "could", "would", "should", "proceed", "who", "are", "identify", "distinguish",
        "distinguishing", "verified", "fact", "interpretation", "hypothesis", "uncertainty", "stale",
    }
    return {term.casefold() for term in TERM_RE.findall(query) if len(term) > 2 and term.casefold() not in stop}


def _entity_name_terms(query: str) -> set[str]:
    result: set[str] = set()
    for phrase in re.findall(r"\b(?:[A-Z][a-z]+\s+){1,3}[A-Z][a-z]+\b", query):
        words = {word.casefold() for word in phrase.split() if word.casefold() not in {"what", "which", "where", "when", "use", "cite", "for"}}
        if len(words) >= 2:
            result.update(words)
    return result


def _direct_fallback(query: str) -> str | None:
    lowered = query.casefold()
    choices = (
        (("offer", "pricing"), "business_brain:memory/offers.md"),
        (("position", "claim"), "business_brain:memory/positioning.md"),
        (("sales", "revenue", "outreach"), "business_brain:memory/sales_and_revenue.md"),
        (("ideal client", "icp"), "business_brain:memory/ideal_clients.md"),
        (("company", "time to revenue", "ttros"), "business_brain:memory/company.md"),
    )
    return next((pointer for terms, pointer in choices if any(term in lowered for term in terms)), None)


def _known_entity_pointers(query: str, *, client_scope: str, registry: ClientScopeRegistry) -> list[str]:
    """Resolve obvious canonical entity names from scoped logical paths only."""
    terms = _query_terms(query)
    entity_terms = _entity_name_terms(query)
    result: list[str] = []
    for pointer in registry.permitted_brain_pointers(client_scope):
        if not pointer.startswith("business_brain:prospects/") or not pointer.endswith(".md"):
            continue
        stem_terms = {
            value for value in re.findall(r"[a-z0-9]+", Path(pointer).stem.casefold())
            if len(value) > 2 and not value.isdigit()
        }
        if len(stem_terms & terms) >= 2:
            result.append(pointer)
    return result


def _scoped_note_block(
    query: str,
    *,
    classification: str,
    client_scope: str,
    vault_root: Path = VAULT_ROOT,
    registry: ClientScopeRegistry | None = None,
    graph_service: Any | None = None,
    search_db_path: Path | None = None,
) -> ContextBlock:
    if classification == "technical_only":
        return ContextBlock(
            "scoped canonical Brain notes",
            "N/A — genuinely technical-only work; no business entity or commercial decision is implicated.",
            ("classification:technical_only",),
            False,
            "explicit N/A",
        )
    gate = registry or load_registry()
    gate.resolve_scope(client_scope)
    if graph_service is None and RELATIONSHIP_RE.search(query):
        try:
            from dashboard.backend.business_brain_graph import BusinessBrainGraphService
            graph_service = BusinessBrainGraphService(vault_root=vault_root, registry=gate)
        except Exception:
            graph_service = None
    loader = ScopedBrainLoader(
        registry=gate,
        vault_root=vault_root,
        graph_service=graph_service,
        search_db_path=search_db_path,
    )
    pointers = list(dict.fromkeys([*POINTER_RE.findall(query), *_known_entity_pointers(query, client_scope=client_scope, registry=gate)]))
    reads = []
    graph_state: dict[str, Any] | None = None
    if pointers:
        result = loader.retrieve(work={"client_scope": client_scope}, pointers=pointers, query=query)
        reads.extend(result.reads)
    relationship_dependent = bool(RELATIONSHIP_RE.search(query))
    try:
        result = loader.retrieve(
            work={"client_scope": client_scope},
            query=query,
            discovery_mode="relationship_dependent" if relationship_dependent else "explicit",
            direct_fallback=None if pointers else _direct_fallback(query),
            limit=5,
        )
        graph_state = result.graph_state
        existing = {read.provenance.path for read in reads}
        reads.extend(read for read in result.reads if read.provenance.path not in existing)
    except BrainContextError:
        if not reads:
            reads = []
    # The stable required blocks already carry these notes.  Avoid repeating
    # their bodies in the scoped block while retaining their own actual reads.
    fixed = {
        "business_brain:memory/company.md",
        "business_brain:operating_context/current_priorities.md",
        "business_brain:operating_context/executive_view.md",
        "business_brain:operating_context/open_loops.md",
    }
    reads = [read for read in reads if read.provenance.path not in fixed]
    if not reads:
        return ContextBlock(
            "scoped canonical Brain notes",
            "N/A — the scope-first pointer → one-hop Graphify → exact search → direct canonical fallback route found no additional canonical note. Required operating notes remain loaded separately.",
            ("retrieval:scope-first-hierarchy#no-additional-read",),
            False,
            "route hierarchy exhausted without a whole-vault scan",
        )
    sections = [f"Selected {len(reads)} canonical note(s); source discovery used zero model tokens."]
    sources: list[str] = []
    actual: list[ActualRead] = []
    for read in reads:
        _fields, body = _frontmatter_body(read.content)
        provenance = read.provenance
        sections.extend(("", f"### {provenance.path} · route={provenance.retrieval_route}", body.strip()))
        sources.append(f"{provenance.path}#sha256={provenance.content_sha256}#route={provenance.retrieval_route}")
        actual.append(ActualRead(provenance.path, provenance.retrieval_route, client_scope, provenance.content_sha256))
    if graph_state:
        sources.append("graphify:ttros-business-brain#" + json.dumps(graph_state, sort_keys=True, separators=(",", ":")))
    return ContextBlock(
        "scoped canonical Brain notes", "\n".join(sections), tuple(sources), False,
        "scope-first explicit/entity seeds with relationship-aware one-hop expansion and canonical reads",
        tuple(actual),
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _row_in_scope(row: dict[str, Any], client_scope: str) -> bool:
    declared = str(row.get("client_scope") or "global")
    return declared == client_scope


def _recent_outcomes_block(
    query: str,
    *,
    client_scope: str,
    root: Path = ROOT,
    registry: ClientScopeRegistry | None = None,
) -> ContextBlock:
    gate = registry or load_registry()
    gate.resolve_scope(client_scope)
    terms = _query_terms(query)
    entity_terms = _entity_name_terms(query)
    ids = {value.upper() for value in ITEM_RE.findall(query)}
    rows: list[tuple[int, dict[str, Any]]] = []
    for item in _read_jsonl(root / "queue" / "work_items.jsonl"):
        if not _row_in_scope(item, client_scope):
            continue
        haystack = " ".join((str(item.get("id") or ""), str(item.get("title") or ""), str(item.get("context") or ""))).casefold()
        if ids and not any(item_id.casefold() in haystack for item_id in ids):
            continue
        if not ids and entity_terms and len(entity_terms.intersection(set(TERM_RE.findall(haystack)))) < 2:
            continue
        score = 100 if str(item.get("id") or "").upper() in ids else 0
        score += sum(20 if term in str(item.get("title") or "").casefold() else 1 for term in terms if len(term) >= 4 and term in haystack)
        if score:
            rows.append((score, item))
    rows.sort(key=lambda row: (-row[0], str(row[1].get("updated_at") or row[1].get("created_at") or "")), reverse=False)
    selected = [item for _score, item in rows[:4]]
    summaries = []
    sources: list[str] = []
    actual: list[ActualRead] = []
    for item in selected:
        review = item.get("outreach_review") if isinstance(item.get("outreach_review"), dict) else {}
        summaries.append(json.dumps({
            "id": item.get("id"),
            "title": item.get("title"),
            "status": item.get("status"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "source": item.get("source"),
            "definition_of_done": item.get("definition_of_done"),
            "primary_signal": review.get("primary_signal"),
            "qualification": review.get("qualification"),
            "readiness": review.get("readiness"),
            "exact_action": review.get("exact_action"),
            "main_caution": review.get("main_caution"),
            "last_event": review.get("last_event"),
            "history_count": review.get("history_count"),
            "missing_record_is_not_clearance": (review.get("reconciliation") or {}).get("missing_record_is_not_clearance") if isinstance(review.get("reconciliation"), dict) else None,
            "receipt_paths": [r.get("path") for r in item.get("receipts") or [] if isinstance(r, dict)],
        }, ensure_ascii=False, sort_keys=True))
        identity = f"queue/work_items.jsonl#{item.get('id')}"
        digest = _sha(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        sources.append(identity)
        actual.append(ActualRead(identity, "episodic_activity", client_scope, digest))
        sources.extend(str(r.get("path")) for r in item.get("receipts") or [] if isinstance(r, dict) and r.get("path"))
    content = "\n".join(summaries) if summaries else "N/A — no matching queue outcome or receipt metadata."
    return ContextBlock(
        "recent receipts and outcomes", content, tuple(sources or ("queue/work_items.jsonl#no-match",)), False,
        f"selected {len(selected)} of {len(rows)} scoped matching items; receipt bodies and unrelated activity excluded",
        tuple(actual),
    )


def _session_recency_block(
    query: str,
    *,
    client_scope: str,
    vault_root: Path = VAULT_ROOT,
    registry: ClientScopeRegistry | None = None,
) -> ContextBlock:
    gate = registry or load_registry()
    gate.resolve_scope(client_scope)
    terms = _query_terms(query)
    entity_terms = _entity_name_terms(query)
    ids = {value.upper() for value in ITEM_RE.findall(query)}
    candidates: list[tuple[int, str, str, str]] = []
    sessions = vault_root / "sessions"
    if sessions.is_dir():
        for path in sorted(sessions.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            fields, body = _frontmatter_body(text)
            if str(fields.get("type") or "") != "session":
                continue
            declared_scope = str(fields.get("client_scope") or "global")
            if declared_scope != client_scope:
                continue
            relative = path.relative_to(vault_root).as_posix()
            for turn in re.split(r"(?=^### Turn ·)", body, flags=re.MULTILINE):
                haystack = turn.casefold()
                score = 100 * sum(1 for item_id in ids if item_id.casefold() in haystack)
                score += sum(12 if term in haystack else 0 for term in terms if len(term) >= 4)
                if score:
                    paragraphs = [value.strip() for value in re.split(r"\n\s*\n", turn) if value.strip()]
                    matched = [
                        value for value in paragraphs
                        if any(item_id.casefold() in value.casefold() for item_id in ids)
                        or any(term in value.casefold() for term in terms if len(term) >= 4)
                    ]
                    header = paragraphs[0] if paragraphs and paragraphs[0].startswith("### Turn ·") else ""
                    excerpt_parts = list(dict.fromkeys(([header] if header else []) + matched))
                    excerpt = "\n\n".join(excerpt_parts)
                    excerpt += f"\n\n[Selected {len(matched)} relevant paragraph(s) of {len(paragraphs)} from this historical turn.]"
                    candidates.append((score, relative, excerpt.strip(), _sha(text)))
    candidates.sort(key=lambda row: (-row[0], row[1], row[2][:40]))
    selected = candidates[:2]
    if not selected:
        return ContextBlock(
            "relevant session recency",
            "N/A — no scoped historical session turn matched this request.",
            (f"business_brain:sessions/#scope={client_scope}#no-match",),
            False,
            "episodic scan restricted to scoped session journals; zero matching turns",
        )
    sections = [f"Selected {len(selected)} relevant historical turn(s); session journals remain evidence, not fact authority."]
    sources: list[str] = []
    actual: list[ActualRead] = []
    for score, relative, turn, digest in selected:
        identity = f"business_brain:{relative}"
        sections.extend(("", f"### {identity} · episodic_relevance={score}", turn))
        sources.append(f"{identity}#sha256={digest}#route=episodic_recency")
        actual.append(ActualRead(identity, "episodic_recency", client_scope, digest))
    return ContextBlock(
        "relevant session recency",
        "\n".join(sections),
        tuple(sources),
        False,
        f"selected {len(selected)} of {len(candidates)} scoped relevant turns; no transcript-wide default",
        tuple(actual),
    )


ACTIVE_COMMITMENT_STATUSES = frozenset({"inbox", "agent_todo", "agent_working", "needs_input", "human_review", "blocked"})


def _current_commitments_block(
    query: str,
    *,
    client_scope: str,
    root: Path = ROOT,
    registry: ClientScopeRegistry | None = None,
) -> ContextBlock:
    gate = registry or load_registry()
    gate.resolve_scope(client_scope)
    terms = _query_terms(query)
    entity_terms = _entity_name_terms(query)
    ids = {value.upper() for value in ITEM_RE.findall(query)}
    ranked: list[tuple[int, dict[str, Any]]] = []
    for item in _read_jsonl(root / "queue" / "work_items.jsonl"):
        if not _row_in_scope(item, client_scope) or str(item.get("status") or "") not in ACTIVE_COMMITMENT_STATUSES:
            continue
        material = " ".join((str(item.get("id") or ""), str(item.get("title") or ""), str(item.get("context") or ""))).casefold()
        if ids and not any(item_id.casefold() in material for item_id in ids):
            continue
        if not ids and entity_terms and len(entity_terms.intersection(set(TERM_RE.findall(material)))) < 2:
            continue
        score = 100 if str(item.get("id") or "").upper() in ids else 0
        score += sum(8 if term in str(item.get("title") or "").casefold() else 1 for term in terms if term in material)
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda row: (-row[0], str(row[1].get("id") or "")))
    selected = [item for _score, item in ranked[:4]]
    if not selected:
        return ContextBlock(
            "relevant current commitments",
            "N/A — no active scoped queue commitment matched this request.",
            (f"queue/work_items.jsonl#scope={client_scope}#no-match",),
            False,
            "active-status and relevance predicates returned zero matches",
        )
    rows: list[str] = []
    sources: list[str] = []
    actual: list[ActualRead] = []
    for item in selected:
        compact = {
            "id": item.get("id"), "title": item.get("title"), "status": item.get("status"),
            "owner": item.get("owner"), "updated_at": item.get("updated_at"),
            "needs_me": item.get("needs_me"), "allowed_actions": item.get("allowed_actions"),
        }
        rows.append(json.dumps(compact, ensure_ascii=False, sort_keys=True))
        identity = f"queue/work_items.jsonl#{item.get('id')}"
        sources.append(identity)
        actual.append(ActualRead(identity, "current_commitment", client_scope, _sha(json.dumps(item, sort_keys=True, ensure_ascii=False))))
    return ContextBlock(
        "relevant current commitments", "\n".join(rows), tuple(sources), False,
        f"selected {len(selected)} of {len(ranked)} scoped active commitments; no new commitment inferred",
        tuple(actual),
    )


def _open_loops_block(
    query: str,
    *,
    client_scope: str,
    vault_root: Path = VAULT_ROOT,
    registry: ClientScopeRegistry | None = None,
) -> ContextBlock:
    opened = _read(
        "operating_context/open_loops.md", vault_root=vault_root,
        client_scope=client_scope, registry=registry, route="pointer",
    )
    if opened is None:
        return ContextBlock("relevant open loops", "N/A — open-loop note unavailable.", ("business_brain:operating_context/open_loops.md#missing",), False, "required; unavailable surfaced")
    text, source, actual = opened
    _fields, body = _frontmatter_body(text)
    terms = _query_terms(query)
    ids = {value.upper() for value in ITEM_RE.findall(query)}
    selected = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line.startswith(("- ", "* ")):
            continue
        if client_scope != "global" and not any(
            marker in line for marker in (f"[{client_scope}]", f"client_scope:{client_scope}")
        ):
            continue
        lowered = line.casefold()
        if any(item_id.casefold() in lowered for item_id in ids) or sum(1 for term in terms if len(term) >= 4 and term in lowered) >= 2:
            selected.append(line)
    content = "\n".join(selected[:6]) if selected else "N/A — no canonical open loop matched this request."
    return ContextBlock(
        "relevant open loops", content, (source,), False,
        f"selected {min(len(selected), 6)} relevant canonical loop(s); unrelated loops omitted from context, not from the source",
        (actual,),
    )


def _matching_workflows_block(query: str) -> ContextBlock:
    terms = _query_terms(query)
    candidates: list[tuple[int, str, str]] = []
    for pattern in ("*/SKILL.md", "*/workflow.md"):
        for path in ROOT.glob(pattern):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            relative = path.relative_to(ROOT).as_posix()
            lowered = (relative + "\n" + text).casefold()
            score = sum((5 if term in relative.casefold() else 1) * lowered.count(term) for term in terms)
            if score:
                candidates.append((score, relative, text))
    candidates.sort(key=lambda row: (-row[0], row[1]))
    selected = candidates[:4]
    omitted = [relative for _score, relative, _text in candidates[4:]]
    if not selected:
        return ContextBlock("matching skills/workflows", "N/A — no workflow matched.", ("skills:index#no-match",), False, "relevance search returned zero matches")
    sections = [
        f"Selected {len(selected)} of {len(candidates)} matches."
        + (f" Not loaded: {', '.join(omitted)}." if omitted else "")
    ]
    sources = []
    for score, relative, text in selected:
        sections.extend(("", f"### {relative} · relevance={score}", text.strip()))
        sources.append(f"{relative}#sha256={_sha(text)}")
    return ContextBlock("matching skills/workflows", "\n".join(sections), tuple(sources), False, "term/workflow relevance")


def _conversation_block(surface: str, session_key: str, *, client_scope: str = "global") -> ContextBlock:
    if client_scope != "global":
        return ContextBlock(
            "conversation summary",
            "N/A — client-scoped worker context never receives a global Hermes transcript.",
            (f"session:excluded-for-scope:{client_scope}",),
            False,
            "client isolation before conversation result construction",
        )
    if not session_key:
        return ContextBlock("conversation summary", "N/A — fresh task-scoped worker invocation.", ("session:none",), False, "fresh session")
    text, digest = read_session(surface, session_key)
    if not text:
        return ContextBlock("conversation summary", "N/A — no prior durable turns for this sticky session.", (f"session:{surface}:new",), False, "new sticky session")
    _fields, body = _frontmatter_body(text)
    relative = str(next((p for p in (VAULT_ROOT / "sessions").glob(f"*_{re.sub(r'[^a-z0-9_-]+', '-', surface.lower()).strip('-') or 'hermes'}_*.md") if file_sha256(p) == digest), ""))
    source = f"business_brain:{Path(relative).relative_to(VAULT_ROOT).as_posix()}#sha256={digest}" if relative else f"session:{surface}#sha256={digest}"
    actual = ActualRead(source.split("#sha256=", 1)[0], "sticky_session", client_scope, digest or _sha(text))
    return ContextBlock("conversation summary", body.strip(), (source,), False, "durable sticky session; no transcript forwarding to workers", (actual,))


def _action_boundaries() -> ContextBlock:
    content = "\n".join((
        "UNGATED: reading, reasoning, conversation, synthesis, ordinary durable learning, local drafts, and context assembly.",
        "GATED: email/LinkedIn send, CRM/Calendar/Drive mutation, publishing, money, credentials, destructive deletion, and formal legal/financial/client commitments.",
        "Gmail remains draft-only. Inbound evidence is not approval. Preserve client isolation, protected paths, and immutable queue records.",
        "Never commit or push the Agentic OS repository. Vault-local Hermes audit commits are allowed; never push the vault automatically.",
    ))
    return ContextBlock("action boundaries", content, ("context:TTROS_ARCHITECTURE_UNBOUND_HERMES_ONE_MEMORY_2026-08-04#§5", "rules/never.md"), True, "required safety boundary")


def _project_morning_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Keep the decision-facing finding facts; leave detector bookkeeping raw."""
    age = finding.get("calculated_age") if isinstance(finding.get("calculated_age"), dict) else {}
    activity = (
        finding.get("last_relevant_activity")
        if isinstance(finding.get("last_relevant_activity"), dict)
        else {}
    )
    discovery = finding.get("discovery") if isinstance(finding.get("discovery"), dict) else {}
    return {
        "finding_id": finding.get("finding_id"),
        "category": finding.get("category"),
        "rule": finding.get("rule"),
        "supporting_rules": finding.get("supporting_rules") or [],
        "entity_id": finding.get("entity_id"),
        "title": finding.get("title"),
        "entity_path": finding.get("entity_path"),
        "current_state": finding.get("current_state") or {},
        "age": age.get("display"),
        "last_activity_at": activity.get("at"),
        "last_activity_source": activity.get("reference"),
        "reason": finding.get("reason"),
        "owner_class": finding.get("owner_class"),
        "waits_on": finding.get("waits_on"),
        "next_permitted_action": finding.get("next_permitted_action"),
        "supporting_references": finding.get("supporting_references") or [],
        "retrieval_route": discovery.get("route"),
    }


def _render_morning_findings(payload: dict[str, Any], selected: list[dict[str, Any]]) -> str:
    """Render selected findings as compact, deterministic model-facing records."""
    selection = "broad executive attention" if payload.get("selection") == "broad executive attention" else "request relevance"
    lines = [
        f"Fresh deterministic snapshot {payload.get('observed_at') or 'unknown'}; "
        f"{len(selected)} of {payload.get('total_finding_count', len(selected))} findings; "
        f"selection={selection}."
    ]
    for finding in selected:
        value = _project_morning_finding(finding)
        state = json.dumps(value["current_state"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        predicates = ",".join(str(item) for item in value["supporting_rules"])
        references = "; ".join(str(item) for item in value["supporting_references"])
        lines.extend((
            "",
            f"- {value['finding_id']} | {value['category']}/{value['rule']} | predicates={predicates}",
            f"  Subject: {value['entity_id']} | {value['title']} | target={value['entity_path']}",
            f"  State: {state} | age={value['age'] or 'unknown'} | "
            f"last_activity={value['last_activity_at'] or 'unknown'} @ {value['last_activity_source'] or 'unknown'}",
            f"  Why: {value['reason']}",
            f"  Owner/waits: {value['owner_class']} | {value['waits_on']}",
            f"  Next: {value['next_permitted_action']}",
            f"  Sources (route={value['retrieval_route'] or 'unknown'}): {references}",
        ))
    return "\n".join(lines) + "\n"


def _deterministic_morning_brief(classification: str, *, client_scope: str = "global", query: str = "") -> ContextBlock:
    if classification == "technical_only":
        return ContextBlock(
            "deterministic morning findings",
            "N/A — genuinely technical-only work; executive attention detection was not required.",
            ("classification:technical_only",),
            False,
            "explicit N/A",
        )
    if client_scope != "global":
        return ContextBlock(
            "deterministic morning findings",
            "N/A — the global executive detector is excluded from client-scoped context.",
            (f"detector:excluded-for-scope:{client_scope}",),
            False,
            "client isolation before detector result construction",
        )
    try:
        try:
            from aos_executive_brief import FINDINGS_REL, refresh
        except ModuleNotFoundError:
            from tools.aos_executive_brief import FINDINGS_REL, refresh
        outcome = refresh(root=ROOT, brain_root=VAULT_ROOT, client_scope="global")
        finding_path = ROOT / FINDINGS_REL
        if outcome.exit_code:
            return ContextBlock(
                "deterministic morning findings",
                "DEGRADED — fresh deterministic detection failed; no partial generation was published. "
                f"Reason: {outcome.reason}. Prior artifact was not treated as current truth.",
                ("detector:aos_executive_brief#failed",),
                False,
                "fresh detection failed closed",
            )
        raw_content = finding_path.read_text(encoding="utf-8")
        payload = json.loads(raw_content)
        findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
        terms = _query_terms(query)
        ids = {value.upper() for value in ITEM_RE.findall(query)}
        broad_attention = bool(re.search(r"\b(?:morning|attention|focus|priorit|executive brief|needs me)\b", query, re.IGNORECASE))
        ranked: list[tuple[int, dict[str, Any]]] = []
        for finding in findings:
            material = json.dumps(finding, ensure_ascii=False, sort_keys=True, separators=(",", ":")).casefold()
            score = 100 * sum(1 for item_id in ids if item_id.casefold() in material)
            score += sum(8 if term in str(finding.get("title") or "").casefold() else 1 for term in terms if term in material)
            if score or broad_attention:
                ranked.append((score, finding))
        ranked.sort(key=lambda row: (-row[0], str(row[1].get("finding_id") or "")))
        limit = 12 if broad_attention else 6
        selected = [finding for _score, finding in ranked[:limit]]
        content = _render_morning_findings({
            "observed_at": payload.get("observed_at"),
            "total_finding_count": len(findings),
            "selection": "broad executive attention" if broad_attention else "request relevance",
        }, selected)
        return ContextBlock(
            "deterministic morning findings",
            content,
            (
                f"context/{FINDINGS_REL.name}#sha256={_sha(raw_content)}",
                "queue/work_items.jsonl",
                "queue/prospects.jsonl",
                "business_brain:inbox/contradictions.md",
                "business_brain:operating_context/open_loops.md",
            ),
            False,
            f"fresh zero-model-token detector result; selected {len(selected)} of {len(findings)} findings by request relevance",
        )
    except Exception as exc:
        return ContextBlock(
            "deterministic morning findings",
            f"DEGRADED — deterministic detector unavailable: {type(exc).__name__}. No generated list was used as authority.",
            ("detector:aos_executive_brief#unavailable",),
            False,
            "detector unavailable surfaced",
        )


def _provenance_block(blocks: Iterable[ContextBlock], *, compact: bool = False) -> ContextBlock:
    selected = tuple(blocks)
    rows = []
    for block in selected:
        if compact:
            routes = {read.identity: read.retrieval_route for read in block.actual_reads}
            for source in block.sources:
                model_source = SOURCE_SHA256_RE.sub("", source)
                embedded_route = SOURCE_ROUTE_RE.search(model_source)
                model_source = SOURCE_ROUTE_RE.sub("", model_source)
                route = routes.get(model_source) or (embedded_route.group(1) if embedded_route else "")
                route_suffix = f" · route={route}" if route else ""
                rows.append(f"- {block.name}: {model_source}{route_suffix}")
            continue
        rows.extend(f"- {block.name}: {source}" for source in block.sources)
        rows.extend(
            f"  - actual-read: {read.identity} · route={read.retrieval_route} · sha256={read.content_sha256} · scope={read.client_scope}"
            for read in block.actual_reads
        )
    selection = (
        "compact selected source identities and routes; full hashes, actual reads, and scopes remain in the assembly artifact"
        if compact else
        "all selected source identities, actual reads, routes, hashes, and scopes"
    )
    return ContextBlock(
        "provenance",
        "\n".join(rows),
        tuple(source for block in selected for source in block.sources),
        False,
        selection,
    )


def assemble(
    request: str,
    *,
    surface: str,
    session_id: str = "",
    session_key: str = "",
    client_scope: str = "global",
    profile: str = "",
    classification: str | None = None,
    invocation_id: str | None = None,
    write_artifact: bool = True,
    root: Path = ROOT,
    vault_root: Path = VAULT_ROOT,
    registry: ClientScopeRegistry | None = None,
    graph_service: Any | None = None,
    search_db_path: Path | None = None,
) -> AssembledContext:
    query = str(request or "").strip()
    if not query:
        raise ContextAssemblyError("cannot assemble context for an empty request")
    gate = registry or load_registry()
    try:
        gate.resolve_scope(client_scope)
    except ClientScopeError as exc:
        raise ContextAssemblyError(f"client isolation failed before context construction: {exc}") from exc
    relevance = relevance_query(query)
    conversation = _conversation_block(surface, session_key, client_scope=client_scope)
    # Resolve ordinary executive anaphora from the durable sticky session.
    # Without this, a phrase such as "the two prospects we discussed" can
    # remember the answer from the conversation block while failing to select
    # the canonical notes and activity that substantiate it.
    if (
        session_key
        and not conversation.content.startswith("N/A —")
        and re.search(r"\b(?:we discussed|those|them|same|both|these|the two prospects)\b", relevance, re.IGNORECASE)
    ):
        # The latest completed turn resolves the referent without letting old,
        # unrelated item IDs dominate queue-outcome ranking. The complete
        # durable conversation still remains visible in its own block.
        latest_turn = conversation.content.rsplit("\n### Turn ·", 1)[-1]
        relevance = relevance + "\n\nLatest durable turn for reference resolution:\n" + latest_turn
    kind = classify_request(relevance, classification)
    if kind == "technical_only":
        identity = ContextBlock("identity/company", "N/A — genuinely technical-only work.", ("classification:technical_only",), True, "explicit N/A")
        priorities = ContextBlock("current priorities", "N/A — genuinely technical-only work.", ("classification:technical_only",), True, "explicit N/A")
        executive = ContextBlock("executive_view", "N/A — genuinely technical-only work.", ("classification:technical_only",), True, "explicit N/A")
    else:
        try:
            identity = _block_from_note("identity/company", "memory/company.md", stable=True, missing="company identity unavailable", vault_root=vault_root, client_scope=client_scope, registry=gate)
            priorities = _block_from_note("current priorities", "operating_context/current_priorities.md", stable=True, missing="current priorities unavailable", vault_root=vault_root, client_scope=client_scope, registry=gate)
            executive = _block_from_note("executive_view", "operating_context/executive_view.md", stable=True, missing="executive synthesis has not been established", vault_root=vault_root, client_scope=client_scope, registry=gate)
        except ClientScopeError as exc:
            raise ContextAssemblyError(f"client isolation rejected a required canonical source: {exc}") from exc
    initial = [
        identity,
        priorities,
        executive,
        _deterministic_morning_brief(kind, client_scope=client_scope, query=relevance),
        _scoped_note_block(
            relevance, classification=kind, client_scope=client_scope,
            vault_root=vault_root, registry=gate, graph_service=graph_service,
            search_db_path=search_db_path,
        ),
        _recent_outcomes_block(relevance, client_scope=client_scope, root=root, registry=gate),
        _session_recency_block(relevance, client_scope=client_scope, vault_root=vault_root, registry=gate),
        _open_loops_block(relevance, client_scope=client_scope, vault_root=vault_root, registry=gate) if kind != "technical_only" else ContextBlock("relevant open loops", "N/A — genuinely technical-only work.", ("classification:technical_only",), False, "explicit N/A"),
        _current_commitments_block(relevance, client_scope=client_scope, root=root, registry=gate),
        _matching_workflows_block(relevance),
        conversation,
        _action_boundaries(),
    ]
    blocks = tuple([*initial, _provenance_block(initial, compact=str(profile or "").strip().casefold() == "david")])
    invocation = invocation_id or f"ctx-{uuid.uuid4().hex}"
    total = sum(block.token_count for block in blocks) + estimate_tokens(query)
    warnings = (f"soft context budget exceeded: {total}>{SOFT_BUDGET_TOKENS}; no block was silently removed",) if total > SOFT_BUDGET_TOKENS else ()
    assembled = AssembledContext(
        invocation_id=invocation,
        surface=str(surface or "unknown"),
        session_id=str(session_id or ""),
        classification=kind,
        client_scope=client_scope,
        request=query,
        blocks=blocks,
        created_at=_iso_now(),
        warnings=warnings,
    ).validate()
    if write_artifact:
        write_assembly_artifact(assembled)
    return assembled


def write_assembly_artifact(context: AssembledContext) -> Path:
    context.validate()
    ASSEMBLY_DIR.mkdir(parents=True, exist_ok=True)
    target = ASSEMBLY_DIR / f"{context.invocation_id}.json"
    payload = json.dumps(context.manifest(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(raw_tmp, target)
    finally:
        Path(raw_tmp).unlink(missing_ok=True)
    return target


def worker_context_pack(
    item: dict[str, Any],
    *,
    owner: str,
    execution_instructions: str = "",
    pack_dir: Path | None = None,
) -> tuple[AssembledContext, Path]:
    item_id = str(item.get("id") or "").strip()
    if not re.fullmatch(r"AOS-\d{4}-\d{4}", item_id):
        raise ContextAssemblyError("worker context pack requires a canonical work-item id")
    sources = item.get("sources") if isinstance(item.get("sources"), list) else []
    request = "\n".join((
        f"Work item {item_id}: {item.get('title') or ''}",
        str(item.get("context") or ""),
        "Source references: " + ", ".join(str(value) for value in sources),
        "Definition of done: " + str(item.get("definition_of_done") or ""),
        "",
        "Task-scoped execution instructions:",
        str(execution_instructions or "No additional execution instructions.").strip(),
    ))
    context = assemble(
        request,
        surface=f"worker:{owner}",
        session_id=item_id,
        session_key="",
        client_scope=str(item.get("client_scope") or "global"),
        classification=str(item.get("context_classification") or "") or None,
    )
    selected_pack_dir = pack_dir or PACK_DIR
    selected_pack_dir.mkdir(parents=True, exist_ok=True)
    target = selected_pack_dir / f"{item_id}_pack.md"
    content = "\n".join((
        f"# Context pack — {item_id}",
        "> Revisit: when the linked work item reaches a terminal state. · Last touched: 2026-08-04.",
        "",
        f"Worker: {owner}",
        "Fresh task-scoped session: yes",
        "Hermes transcript included wholesale: no",
        "",
        context.render(),
    ))
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(raw_tmp, target)
    finally:
        Path(raw_tmp).unlink(missing_ok=True)
    return context, target


def context_from_hook_payload(payload: dict[str, Any]) -> AssembledContext:
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    query = str(extra.get("user_message") or "").strip()
    session_id = str(payload.get("session_id") or "")
    platform = str(extra.get("platform") or "hermes")
    sender = str(extra.get("sender_id") or "")
    surface = f"hermes:{platform}"
    session_key = sender or session_id
    return assemble(query, surface=surface, session_id=session_id, session_key=session_key)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("assemble")
    build.add_argument("--surface", required=True)
    build.add_argument("--session-id", default="")
    build.add_argument("--session-key", default="")
    build.add_argument("--classification", choices=("technical_only", "knowledge_sensitive"))
    build.add_argument("--request-file")
    build.add_argument("request", nargs="*")
    args = parser.parse_args(argv)
    request = Path(args.request_file).read_text(encoding="utf-8") if args.request_file else " ".join(args.request)
    context = assemble(
        request, surface=args.surface, session_id=args.session_id,
        session_key=args.session_key, classification=args.classification,
    )
    print(json.dumps(context.manifest(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
