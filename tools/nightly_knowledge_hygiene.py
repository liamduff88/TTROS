#!/usr/bin/env python3
"""Idempotent nightly reconciliation for the canonical TTROS Business Brain.

This is the script-only job used by the existing Hermes scheduler.  It folds
only explicitly structured session candidates, reconciles deterministic
staleness/contradiction state, refreshes the disposable Graphify/search
publications, and commits only coherent vault-local knowledge transactions.
It never invokes a model, changes Agentic OS code, pushes, or acts externally.

Revisit: when session-candidate, Brain transaction, Graphify, or search
publication contracts change. · Last touched: 2026-08-04.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Iterable

import yaml

try:
    import aos_indexer
    import brain_memory
    from business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry
    from morning_brief_detector import detect
    from validate_business_brain import analyze_vault
except ModuleNotFoundError:
    from tools import aos_indexer, brain_memory
    from tools.business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry
    from tools.morning_brief_detector import detect
    from tools.validate_business_brain import analyze_vault

from dashboard.backend.business_brain_graph import BusinessBrainGraphError, BusinessBrainGraphService


ROOT = Path(os.environ.get("AOS_ROOT", Path(__file__).resolve().parents[1])).resolve()
TOKEN_USAGE = {"model_invocations": 0, "input_tokens": 0, "output_tokens": 0}
TOKEN_USAGE_TEXT = "Token usage: no agent invocation"
SESSION_STATES = frozenset({"verified_fact", "operator_correction", "interpretation", "hypothesis", "uncertainty", "unresolved_follow_up", "contradiction", "formal_commitment"})
EXECUTIVE_STATES = frozenset({"interpretation", "hypothesis", "uncertainty"})
STALE_RULES = frozenset({"prospect_overdue_follow_up", "prospect_pending_connection", "prospect_no_recent_activity", "project_blocked"})
MANAGED_RE = re.compile(r"<!-- TTROS:HERMES:([^:>]+):BEGIN -->[\s\S]*?<!-- TTROS:HERMES:\1:END -->")
SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
REVENUE_GATE_PROOF = Path("proofs/unbound-hermes-one-brain-2026-08-04/REVENUE_GATE.md")
REVENUE_GATE_LOOP_PREFIX = "Revenue Gate must prove restart recall, automatic canonical/activity retrieval"


class NightlyHygieneError(RuntimeError):
    """The complete nightly transaction could not be published safely."""


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_text(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise NightlyHygieneError("session or canonical note lacks YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise NightlyHygieneError("session or canonical note has unterminated frontmatter")
    try:
        fields = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError as exc:
        raise NightlyHygieneError("session or canonical note has malformed frontmatter") from exc
    if not isinstance(fields, dict):
        raise NightlyHygieneError("frontmatter must be a mapping")
    return fields, text[end + 5 :]


def _title(body: str, fallback: str) -> str:
    return next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), fallback)


def _section_block(section_id: str, title: str, content: str, *, source: str, session_id: str) -> str:
    return "\n".join((
        brain_memory.MANAGED_BEGIN.format(section=section_id),
        f"## {title.strip()}",
        "",
        f"> Provenance: `author: hermes` · `source: {source}` · `session: {session_id}`",
        "",
        content.strip(),
        brain_memory.MANAGED_END.format(section=section_id),
    ))


def _upsert_section(existing: str, *, section_id: str, title: str, content: str, source: str, session_id: str) -> tuple[str, bool]:
    desired = _section_block(section_id, title, content, source=source, session_id=session_id)
    begin = brain_memory.MANAGED_BEGIN.format(section=section_id)
    end = brain_memory.MANAGED_END.format(section=section_id)
    if begin in existing or end in existing:
        pattern = re.compile(re.escape(begin) + r"[\s\S]*?" + re.escape(end))
        matches = pattern.findall(existing)
        if len(matches) != 1:
            raise NightlyHygieneError(f"managed section is duplicated or incomplete: {section_id}")
        if matches[0] == desired:
            return existing, False
    updated = brain_memory.managed_section(
        existing,
        section_id=section_id,
        title=title,
        content=content,
        source=source,
        session_id=session_id,
    )
    return updated, updated != existing


def _candidate_section_id(candidate_id: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "-", candidate_id.casefold()).strip("-")
    if not normalized:
        normalized = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16]
    value = f"nightly-{normalized}"[:80]
    if not SAFE_ID_RE.fullmatch(value):
        raise NightlyHygieneError("knowledge candidate id cannot form a stable section id")
    return value


@dataclasses.dataclass(frozen=True)
class KnowledgeCandidate:
    candidate_id: str
    state: str
    statement: str
    source_pointer: str
    source_session_id: str
    target: str | None
    evidence: str
    verified: bool
    operator_confirmed: bool


@dataclasses.dataclass
class NightlyPlan:
    documents: dict[str, str]
    expected_hashes: dict[str, str | None]
    changes: list[dict[str, Any]]
    deferred_commitments: list[dict[str, str]]
    session_candidate_count: int
    staleness_finding_count: int
    contradiction_resolution_count: int
    source_state_sha256: str

    def public(self) -> dict[str, Any]:
        return {
            "changed_paths": sorted(self.documents),
            "changes": self.changes,
            "expected_hashes": self.expected_hashes,
            "candidate_hashes": {path: _sha_text(text) for path, text in sorted(self.documents.items())},
            "deferred_formal_commitments": self.deferred_commitments,
            "session_candidate_count": self.session_candidate_count,
            "staleness_finding_count": self.staleness_finding_count,
            "contradiction_resolution_count": self.contradiction_resolution_count,
            "source_state_sha256": self.source_state_sha256,
        }


def _session_candidates(brain_root: Path, *, client_scope: str, gate: ClientScopeRegistry) -> list[KnowledgeCandidate]:
    gate.resolve_scope(client_scope)
    result: list[KnowledgeCandidate] = []
    identities: dict[str, str] = {}
    sessions = brain_root / "sessions"
    if not sessions.is_dir():
        return []
    for path in sorted(sessions.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        fields, _body = _frontmatter(text)
        if str(fields.get("type") or "") != "session" or str(fields.get("client_scope") or "global") != client_scope:
            continue
        raw_candidates = fields.get("knowledge_candidates") or []
        if not isinstance(raw_candidates, list):
            raise NightlyHygieneError(f"knowledge_candidates must be a list: {path.name}")
        source_pointer = f"business_brain:{path.relative_to(brain_root).as_posix()}"
        for raw in raw_candidates:
            if not isinstance(raw, dict):
                raise NightlyHygieneError(f"knowledge candidate must be a mapping: {path.name}")
            candidate_id = str(raw.get("id") or "").strip()
            state = str(raw.get("state") or "").strip()
            statement = " ".join(str(raw.get("statement") or "").split())
            target = str(raw.get("target") or "").strip() or None
            evidence = str(raw.get("evidence") or source_pointer).strip()
            if not candidate_id or state not in SESSION_STATES or not statement or not evidence:
                raise NightlyHygieneError(f"incomplete or unsupported knowledge candidate: {path.name}")
            fingerprint = _json(raw)
            if candidate_id in identities and identities[candidate_id] != fingerprint:
                raise NightlyHygieneError(f"knowledge candidate id has contradictory definitions: {candidate_id}")
            identities[candidate_id] = fingerprint
            if target:
                try:
                    target = gate.validate_brain_pointer(client_scope, target)
                except ClientScopeError as exc:
                    raise NightlyHygieneError(f"knowledge candidate target failed client isolation: {candidate_id}") from exc
            result.append(KnowledgeCandidate(
                candidate_id=candidate_id,
                state=state,
                statement=statement,
                source_pointer=source_pointer,
                source_session_id=str(fields.get("id") or path.stem),
                target=target,
                evidence=evidence,
                verified=raw.get("verified") is True,
                operator_confirmed=raw.get("operator_confirmed") is True,
            ))
    return sorted(result, key=lambda row: (row.candidate_id, row.source_pointer))


def _canonical_operator_corrections(brain_root: Path, *, client_scope: str, gate: ClientScopeRegistry) -> dict[str, tuple[str, str]]:
    gate.resolve_scope(client_scope)
    corrections: dict[str, tuple[str, str]] = {}
    for pointer in gate.permitted_brain_pointers(client_scope):
        if not pointer.startswith("business_brain:prospects/") or not pointer.endswith(".md"):
            continue
        path = brain_root / pointer.removeprefix("business_brain:")
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        _fields, body = _frontmatter(text)
        if "Knowledge state: `operator_correction`" not in body:
            continue
        title = _title(body, path.stem).split(" — ", 1)[0].strip()
        if title:
            corrections[title.casefold()] = (pointer, title)
    return corrections


def _reconcile_contradictions(text: str, corrections: dict[str, tuple[str, str]]) -> tuple[str, list[dict[str, str]]]:
    fields, body = _frontmatter(text)
    del fields
    lines = body.splitlines()
    section = ""
    kept: list[str] = []
    resolved: list[tuple[str, str, str]] = []
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip().casefold()
        if section == "open" and stripped.startswith(("- ", "* ")) and stripped[2:].strip().casefold() not in {"none", "none."}:
            bullet = stripped[2:].strip()
            match = re.match(r"(.+?)\s+classification\s*:", bullet, flags=re.IGNORECASE)
            key = match.group(1).strip().casefold() if match else ""
            correction = corrections.get(key)
            if correction and "until liam confirms" in bullet.casefold():
                resolved.append((bullet, correction[0], correction[1]))
                continue
        kept.append(raw)
    if not resolved:
        return text, []
    body = "\n".join(kept)
    # Normalise the now-empty Open section without touching any other section.
    body = re.sub(r"(## Open\s*\n)(?=\s*## )", r"\1\n- None.\n\n", body, count=1)
    resolution_lines = [
        f"- {bullet} Resolution: Liam's canonical operator correction in `{pointer}#operator-correction` confirms the authoritative classification."
        for bullet, pointer, _title_value in resolved
    ]
    if re.search(r"(?m)^## Resolved\s*$", body):
        body = re.sub(
            r"(?ms)(^## Resolved\s*\n)(?:\s*- None\.\s*)?",
            lambda match: match.group(1) + "\n" + "\n".join(resolution_lines) + "\n",
            body,
            count=1,
        )
    else:
        body = body.rstrip() + "\n\n## Resolved\n\n" + "\n".join(resolution_lines) + "\n"
    prefix_end = text.find("\n---\n", 4) + 5
    updated = text[:prefix_end] + body.lstrip("\n").rstrip() + "\n"
    records = [{"kind": "contradiction_reconciled", "statement": bullet, "canonical_evidence": pointer} for bullet, pointer, _title_value in resolved]
    return updated, records


def _reconcile_closed_release_gate(text: str, *, root: Path) -> tuple[str, list[dict[str, str]]]:
    """Resolve the historical Step-4 gate loop only from its explicit PASS proof."""
    proof_path = root / REVENUE_GATE_PROOF
    if not proof_path.is_file():
        return text, []
    proof = proof_path.read_text(encoding="utf-8")
    if "Verdict: **PASS** for Steps 0–3 and the Revenue Gate." not in proof:
        return text, []
    _fields, body = _frontmatter(text)
    lines = body.splitlines()
    section = ""
    kept: list[str] = []
    resolved = False
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip().casefold()
        if section == "one brain release" and stripped.startswith(("- ", "* ")):
            if stripped[2:].strip().startswith(REVENUE_GATE_LOOP_PREFIX):
                resolved = True
                continue
        kept.append(raw)
    if not resolved:
        return text, []
    body = "\n".join(kept)
    body = re.sub(r"(## One Brain release\s*\n)(?=\s*(?:## |<!--|\Z))", r"\1\n- None.\n\n", body, count=1)
    prefix_end = text.find("\n---\n", 4) + 5
    updated = text[:prefix_end] + body.lstrip("\n").rstrip() + "\n"
    evidence = REVENUE_GATE_PROOF.as_posix()
    updated, _changed = _upsert_section(
        updated,
        section_id="nightly-closed-release-gates",
        title="Resolved architecture release gates",
        content=f"- Revenue Gate closed by explicit PASS verdict in `{evidence}`; Steps 0–3 and its pre-Step-4 completion predicate are satisfied.",
        source=evidence,
        session_id="nightly-knowledge-hygiene",
    )
    return updated, [{
        "kind": "open_loop_reconciled",
        "statement": "Revenue Gate completion before Step 4",
        "canonical_evidence": evidence,
    }]


def _load_document(brain_root: Path, relative: str, documents: dict[str, str]) -> str:
    if relative in documents:
        return documents[relative]
    path = brain_root / relative
    if not path.is_file():
        raise NightlyHygieneError(f"canonical target does not exist: {relative}")
    return path.read_text(encoding="utf-8")


def build_plan(
    *,
    root: Path,
    brain_root: Path,
    client_scope: str = "global",
    registry: ClientScopeRegistry | None = None,
    graphify_root: Path = Path("/home/liam/graphify-brain"),
) -> NightlyPlan:
    root, brain_root = Path(root).resolve(), Path(brain_root).resolve()
    gate = registry or load_registry()
    gate.resolve_scope(client_scope)
    candidates = _session_candidates(brain_root, client_scope=client_scope, gate=gate)
    documents: dict[str, str] = {}
    changes: list[dict[str, Any]] = []
    deferred: list[dict[str, str]] = []
    transaction_id = "nightly-knowledge-hygiene"

    for candidate in candidates:
        if candidate.state == "formal_commitment":
            deferred.append({"id": candidate.candidate_id, "statement": candidate.statement, "reason": "formal commitment requires Liam's explicit confirmation"})
            continue
        if candidate.state == "verified_fact" and not candidate.verified:
            continue
        if candidate.state == "operator_correction" and not candidate.operator_confirmed:
            continue
        if candidate.state in {"verified_fact", "operator_correction"}:
            if not candidate.target:
                raise NightlyHygieneError(f"durable fact/correction requires a canonical target: {candidate.candidate_id}")
            relative = candidate.target.removeprefix("business_brain:")
        elif candidate.state in EXECUTIVE_STATES:
            relative = "operating_context/executive_view.md"
            gate.validate_brain_pointer(client_scope, f"business_brain:{relative}")
        elif candidate.state == "unresolved_follow_up":
            relative = "operating_context/open_loops.md"
            gate.validate_brain_pointer(client_scope, f"business_brain:{relative}")
        else:
            relative = "inbox/contradictions.md"
            gate.validate_brain_pointer(client_scope, f"business_brain:{relative}")
        existing = _load_document(brain_root, relative, documents)
        content = "\n".join((
            f"Knowledge state: `{candidate.state}`",
            "",
            candidate.statement,
            "",
            f"Evidence: `{candidate.evidence}` · session journal: `{candidate.source_pointer}`",
        ))
        updated, changed = _upsert_section(
            existing,
            section_id=_candidate_section_id(candidate.candidate_id),
            title=f"Folded learning — {candidate.candidate_id}",
            content=content,
            source=candidate.source_pointer,
            session_id=candidate.source_session_id,
        )
        if changed:
            documents[relative] = updated
            changes.append({"kind": "session_learning_fold", "candidate_id": candidate.candidate_id, "state": candidate.state, "target": f"business_brain:{relative}", "source": candidate.source_pointer})

    service = BusinessBrainGraphService(graphify_root=graphify_root, vault_root=brain_root, registry=gate)
    findings = detect(
        root=root,
        brain_root=brain_root,
        client_scope=client_scope,
        registry=gate,
        graphify_root=graphify_root,
        graph_query=lambda item_id, scope: service.query_targets(item_id, client_scope=scope, registry=gate),
    )
    stale = [finding for finding in findings.findings if finding.rule in STALE_RULES]
    open_relative = "operating_context/open_loops.md"
    open_existing = _load_document(brain_root, open_relative, documents)
    marker = brain_memory.MANAGED_BEGIN.format(section="nightly-staleness-findings")
    if stale or marker in open_existing:
        rows = [
            f"- `{finding.finding_id}` · `{finding.rule}` · {finding.title} · `{finding.entity_path}` · evidence: "
            + ", ".join(f"`{ref}`" for ref in finding.supporting_references)
            for finding in stale
        ] or ["- None."]
        open_updated, changed = _upsert_section(
            open_existing,
            section_id="nightly-staleness-findings",
            title="Nightly deterministic staleness findings",
            content="\n".join(rows),
            source="deterministic morning-brief predicates",
            session_id=transaction_id,
        )
        if changed:
            documents[open_relative] = open_updated
            changes.append({"kind": "staleness_reconciliation", "target": f"business_brain:{open_relative}", "finding_ids": [finding.finding_id for finding in stale]})

    if client_scope == "global":
        open_existing = _load_document(brain_root, open_relative, documents)
        open_updated, closed_release_gates = _reconcile_closed_release_gate(open_existing, root=root)
        if closed_release_gates:
            documents[open_relative] = open_updated
            changes.extend(closed_release_gates)

    contradiction_relative = "inbox/contradictions.md"
    contradiction_existing = _load_document(brain_root, contradiction_relative, documents)
    corrections = _canonical_operator_corrections(brain_root, client_scope=client_scope, gate=gate)
    contradiction_updated, reconciled = _reconcile_contradictions(contradiction_existing, corrections)
    if reconciled:
        documents[contradiction_relative] = contradiction_updated
        changes.extend(reconciled)

    # Remove paths whose semantic candidate equals the current file.  This is
    # the no-op boundary that prevents timestamp-only commits on rerun.
    for relative in list(documents):
        if documents[relative].encode("utf-8") == (brain_root / relative).read_bytes():
            documents.pop(relative)
    expected = {relative: brain_memory.file_sha256(brain_root / relative) for relative in documents}
    source_digest = hashlib.sha256()
    for path in sorted({root / "queue/work_items.jsonl", root / "queue/prospects.jsonl", root / REVENUE_GATE_PROOF, *(brain_root / "sessions").glob("*.md"), brain_root / open_relative, brain_root / contradiction_relative}):
        source_digest.update(str(path).encode("utf-8"))
        source_digest.update(path.read_bytes() if path.is_file() else b"<missing>")
    return NightlyPlan(
        documents=documents,
        expected_hashes=expected,
        changes=changes,
        deferred_commitments=deferred,
        session_candidate_count=len(candidates),
        staleness_finding_count=len(stale),
        contradiction_resolution_count=len(reconciled),
        source_state_sha256=source_digest.hexdigest(),
    )


def _search_is_fresh(db_path: Path, *, brain_root: Path, client_scope: str, gate: ClientScopeRegistry) -> bool:
    if not db_path.is_file():
        return False
    expected: dict[str, tuple[int, float]] = {}
    for pointer in gate.permitted_brain_pointers(client_scope):
        if not pointer.endswith(".md"):
            continue
        if gate.scope_for_search_identity("business_brain", pointer) != client_scope:
            continue
        path = brain_root / pointer.removeprefix("business_brain:")
        if path.is_file():
            if aos_indexer.is_excluded(path):
                continue
            raw = path.read_bytes()[: aos_indexer.MAX_TEXT_BYTES].decode("utf-8", errors="replace")
            if aos_indexer.SECRET_CONTENT_RE.search(raw):
                continue
            stat = path.stat()
            expected[pointer] = (stat.st_size, stat.st_mtime)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = conn.execute("SELECT path,size_bytes,mtime FROM documents WHERE source='business_brain' AND client_scope=?", (client_scope,)).fetchall()
        conn.close()
    except (OSError, sqlite3.Error):
        return False
    actual = {str(path): (int(size), float(mtime)) for path, size, mtime in rows}
    return actual == expected


class _PublicationSnapshot:
    def __init__(self, graph_published: Path, search_db: Path):
        self.graph_published = graph_published
        self.search_db = search_db
        self.temp = tempfile.TemporaryDirectory(prefix="ttros-nightly-publication-")
        self.root = Path(self.temp.name)
        self.graph_existed = graph_published.is_dir()
        self.search_existed = search_db.is_file()
        if self.graph_existed:
            shutil.copytree(graph_published, self.root / "graph")
        if self.search_existed:
            shutil.copy2(search_db, self.root / "search.db")

    def restore(self) -> None:
        if self.graph_existed:
            replacement = self.graph_published.parent / f".nightly-restore-{os.getpid()}"
            shutil.rmtree(replacement, ignore_errors=True)
            shutil.copytree(self.root / "graph", replacement)
            displaced = self.graph_published.parent / f".nightly-failed-{os.getpid()}"
            if self.graph_published.exists():
                os.replace(self.graph_published, displaced)
            os.replace(replacement, self.graph_published)
            shutil.rmtree(displaced, ignore_errors=True)
        elif self.graph_published.exists():
            shutil.rmtree(self.graph_published)
        if self.search_existed:
            self.search_db.parent.mkdir(parents=True, exist_ok=True)
            fd, raw = tempfile.mkstemp(prefix=f".{self.search_db.name}.restore-", dir=self.search_db.parent)
            with os.fdopen(fd, "wb") as handle:
                handle.write((self.root / "search.db").read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(raw, self.search_db)
        elif self.search_db.exists():
            self.search_db.unlink()

    def close(self) -> None:
        self.temp.cleanup()


def run(
    *,
    root: Path = ROOT,
    brain_root: Path = brain_memory.VAULT_ROOT,
    graphify_root: Path = Path("/home/liam/graphify-brain"),
    search_db_path: Path | None = None,
    client_scope: str = "global",
    registry: ClientScopeRegistry | None = None,
    dry_run: bool = False,
    commit: bool = True,
    failure_injection: str | None = None,
) -> dict[str, Any]:
    root, brain_root, graphify_root = Path(root).resolve(), Path(brain_root).resolve(), Path(graphify_root).resolve()
    db_path = Path(search_db_path or (root / "search/os_index.db")).resolve()
    gate = registry or load_registry()
    service = BusinessBrainGraphService(graphify_root=graphify_root, vault_root=brain_root, registry=gate)
    plan = build_plan(root=root, brain_root=brain_root, client_scope=client_scope, registry=gate, graphify_root=graphify_root)
    graph_before = service._artifact_hashes(service.published) if service._published_is_usable() else {}
    search_before = _sha_bytes(db_path.read_bytes()) if db_path.is_file() else None
    graph_fresh = service.status().get("state") == "fresh"
    search_fresh = _search_is_fresh(db_path, brain_root=brain_root, client_scope=client_scope, gate=gate)
    base = {
        "schema_version": 1,
        "operation": "nightly_knowledge_hygiene",
        "dry_run": dry_run,
        "client_scope": client_scope,
        "plan": plan.public(),
        "planned_graph_action": "rebuild" if plan.documents or not graph_fresh else "none_fresh",
        "planned_search_action": "reindex" if plan.documents or not search_fresh else "none_fresh",
        "token_usage": dict(TOKEN_USAGE),
        "token_usage_text": TOKEN_USAGE_TEXT,
        "external_actions": 0,
        "agentic_os_code_writes": 0,
    }
    if dry_run:
        return {**base, "status": "dry_run", "mutated": False, "commit": None, "graph_before": graph_before, "search_before": search_before}
    if not plan.documents and graph_fresh and search_fresh:
        return {**base, "status": "unchanged", "mutated": False, "commit": None, "graph_before": graph_before, "graph_after": graph_before, "search_before": search_before, "search_after": search_before}

    old_globals = (brain_memory.VAULT_ROOT, aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT, aos_indexer.INGEST_CONFIG_PATH)
    brain_memory.VAULT_ROOT = brain_root
    aos_indexer.LIVE_ROOT = root
    aos_indexer.BUSINESS_BRAIN_ROOT = brain_root
    aos_indexer.INGEST_CONFIG_PATH = root / "queue/ingest_watch.json"
    snapshot = _PublicationSnapshot(service.published, db_path)
    derived: dict[str, Any] = {}

    def refresh_and_validate(_changed_paths: tuple[str, ...] = ()) -> None:
        selected_service = service
        if failure_injection == "graphify":
            selected_service = BusinessBrainGraphService(
                graphify_root=graphify_root,
                vault_root=brain_root,
                registry=gate,
                graphify_python=graphify_root / "missing-graphify-python",
            )
        derived["graph"] = selected_service.build()
        search = aos_indexer.scan(
            db_path,
            roots=[root, brain_root],
            registry=gate,
            failure_injection="before_publish" if failure_injection == "reindex" else None,
        )
        derived["search"] = search
        if search.get("status") != "success" or not search.get("published"):
            raise NightlyHygieneError("search reindex failed; previous publication must be restored")
        validation = analyze_vault(brain_root)
        derived["validation"] = {"status": validation["status"], "checks": validation["checks"], "canonical_note_count": len(validation["canonical_paths"])}
        if validation["status"] != "PASS" or failure_injection == "validation":
            raise NightlyHygieneError("Brain Markdown/link validation failed")

    try:
        if plan.documents:
            expected = dict(plan.expected_hashes)
            if failure_injection == "expected_hash":
                expected[next(iter(sorted(expected)))] = "0" * 64
            result = brain_memory.write_transaction(
                plan.documents,
                source="nightly knowledge hygiene",
                session_id=f"nightly-knowledge-hygiene-{dt.datetime.now(dt.timezone.utc).date().isoformat()}",
                expected_hashes=expected,
                commit=commit,
                post_write_validator=refresh_and_validate,
                failure_injection=("after_first_replace" if failure_injection == "write" else "provenance" if failure_injection == "provenance" else None),
            )
            commit_hash = result.commit
        else:
            refresh_and_validate(())
            commit_hash = None
        graph_after = service._artifact_hashes(service.published)
        search_after = _sha_bytes(db_path.read_bytes()) if db_path.is_file() else None
        return {
            **base,
            "status": "changed" if plan.documents else "refreshed",
            "mutated": True,
            "changed_paths": sorted(plan.documents),
            "commit": commit_hash,
            "graph": derived.get("graph"),
            "search": derived.get("search"),
            "validation": derived.get("validation"),
            "graph_before": graph_before,
            "graph_after": graph_after,
            "search_before": search_before,
            "search_after": search_after,
        }
    except Exception:
        snapshot.restore()
        raise
    finally:
        snapshot.close()
        brain_memory.VAULT_ROOT, aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT, aos_indexer.INGEST_CONFIG_PATH = old_globals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run failure-safe TTROS nightly knowledge hygiene")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--brain-root", type=Path, default=brain_memory.VAULT_ROOT)
    parser.add_argument("--graphify-root", type=Path, default=Path("/home/liam/graphify-brain"))
    parser.add_argument("--search-db", type=Path)
    parser.add_argument("--client-scope", default="global")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-commit", action="store_true")
    parser.add_argument("--inject-failure", choices=("expected_hash", "write", "graphify", "reindex", "validation", "provenance"))
    args = parser.parse_args(argv)
    try:
        payload = run(
            root=args.root,
            brain_root=args.brain_root,
            graphify_root=args.graphify_root,
            search_db_path=args.search_db,
            client_scope=args.client_scope,
            dry_run=args.dry_run,
            commit=not args.no_commit,
            failure_injection=args.inject_failure,
        )
        exit_code = 0
    except Exception as exc:
        payload = {
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "token_usage": dict(TOKEN_USAGE),
            "token_usage_text": TOKEN_USAGE_TEXT,
            "external_actions": 0,
        }
        exit_code = 1
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
