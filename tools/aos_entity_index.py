#!/usr/bin/env python3
"""Derived, rebuildable entity index for the Memory entity browser.

Revisit: when Business Brain frontmatter or the Memory Ingest manifest gains entity keys. · Last touched: 2026-10-02.

The Business Brain files stay authoritative. This module only reads files the
existing search index already exposes to the global scope, extracts entities
from metadata that is *declared* in those files (participants, card entities,
prospect titles, optional entity_key frontmatter, Memory Exchange receipts),
and stores the result in extra tables inside the existing search database
(search/os_index.db). Nothing here calls a model, an embedding API, or any
network service, and the tables can be dropped and rebuilt at any time.

Identity rule: two names are never merged unless metadata declares it. "Dr
Kenneth Moodley", "Kenneth (surname absent from metadata)" and "Ken Stanick"
stay three entities; the UI shows the overlap as explicit disambiguation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import sys
import threading
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import aos_indexer  # noqa: E402
from business_brain import BUSINESS_BRAIN_PREFIX, BUSINESS_BRAIN_ROOT  # noqa: E402

TOKEN_USAGE_TEXT = "Token usage: no agent invocation"
INDEX_VERSION = "entity-index-v2"
MEMORY_EXCHANGE_RECEIPTS = aos_indexer.LIVE_ROOT / "queue" / "receipts" / "memory_exchange_import.jsonl"
CANONICAL_AREAS = ("memory/", "operating_context/", "decisions/", "prospects/")
INDEX_NAMES = {"README.md", "INDEX.md", "MEMORY_INDEX.md", "index.md"}
HONORIFICS = {"dr", "mr", "mrs", "ms", "prof"}
NAME_RE = re.compile(
    r"^(?:(?P<hon>Dr|Mr|Mrs|Ms|Prof)\.?\s+)?"
    r"(?P<name>[A-Z][A-Za-z'’-]+(?:\s+[A-Z][A-Za-z'’-]+){0,3})"
    r"(?:\s*\((?P<qual>[^)]*)\))?$"
)
TEMPORAL_RE = re.compile(r"\*\*Temporal posture:\*\*\s*([A-Za-z_-]+)", re.I)
ISO_DATE_RE = re.compile(r"(20\d\d)-(\d\d)-(\d\d)")
MONTH_DAY_RE = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})$", re.I)
MONTHS = {name: index for index, name in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

KNOWLEDGE_LABELS = {
    "verified_fact": "Verified / current knowledge",
    "canonical": "Canonical knowledge",
    "explicit_decision": "Decision",
    "commitment": "Commitment",
    "open_loop": "Open loop",
    "current_priority": "Current priority",
    "liam_intention": "Intention",
    "historical_evidence": "Historical evidence",
    "client_project_context": "Project / client context",
    "prospect_entity_context": "Prospect context",
    "interpretation": "Interpretation",
    "hypothesis": "Hypothesis",
    "uncertainty": "Uncertainty",
    "source_card": "Source card · evidence summary",
    "inbox": "Inbox · unreviewed",
    "index": "Index",
}
SOURCE_LABELS = {
    "call_transcript": "Call transcript",
    "context_packet": "Context packet",
    "concept_summary": "Concept summary",
    "email": "Email",
    "meeting_record": "Meeting record",
}

_BUILD_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS entity_index_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS brain_documents (
    path TEXT PRIMARY KEY, title TEXT NOT NULL, role TEXT NOT NULL, knowledge_type TEXT NOT NULL,
    type_label TEXT NOT NULL, date_sort TEXT NOT NULL, date_text TEXT NOT NULL, date_basis TEXT NOT NULL,
    canonical INTEGER NOT NULL, package_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, entity_type TEXT NOT NULL,
    qualifier TEXT NOT NULL, knowledge_count INTEGER NOT NULL, source_count INTEGER NOT NULL,
    latest_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entity_aliases (entity_id TEXT NOT NULL, alias TEXT NOT NULL, alias_norm TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_entity_aliases_norm ON entity_aliases(alias_norm);
CREATE TABLE IF NOT EXISTS entity_links (
    entity_id TEXT NOT NULL, path TEXT NOT NULL, basis TEXT NOT NULL, PRIMARY KEY (entity_id, path)
);
CREATE INDEX IF NOT EXISTS idx_entity_links_path ON entity_links(path);
"""


def norm(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def slug(value: str) -> str:
    return norm(value).replace(" ", "-")


def parse_person(segment: str) -> dict | None:
    """Parse one participants segment into a person, or None if it is prose."""
    match = NAME_RE.match(segment.strip())
    if not match:
        return None
    name = match.group("name").strip()
    if name.split()[0].lower() in HONORIFICS:
        return None
    honorific = match.group("hon")
    aliases = {name}
    if honorific:
        aliases.add(f"{honorific} {name}")
    qualifier = (match.group("qual") or "").strip()
    if len(name.split()) == 1 and not qualifier:
        qualifier = "surname not recorded"
    return {"id": f"person:{slug(name)}", "name": name, "type": "person", "qualifier": qualifier, "aliases": aliases}


def _resolve_date(relative: str, title: str, fm: dict) -> tuple[str, str, str]:
    """Return (sortable ISO date, display text, basis) or empty strings."""
    for key in ("date", "source_date", "source_date_text"):
        value = str(fm.get(key) or "").strip()
        iso = ISO_DATE_RE.search(value)
        if iso:
            return iso.group(0), iso.group(0), key
    for text, basis in ((Path(relative).name, "filename"), (title, "title")):
        iso = ISO_DATE_RE.search(text)
        if iso:
            return iso.group(0), iso.group(0), basis
    imported = str(fm.get("imported_at") or fm.get("ingested_at") or "")
    for key in ("source_date", "source_date_text"):
        match = MONTH_DAY_RE.match(str(fm.get(key) or "").strip())
        year_match = re.match(r"(20\d\d)-(\d\d)-(\d\d)", imported)
        if match and year_match:
            month, day = MONTHS[match.group(1).lower()[:3]], int(match.group(2))
            year = int(year_match.group(1))
            try:
                candidate = dt.date(year, month, day)
                if candidate > dt.date.fromisoformat(year_match.group(0)):
                    candidate = dt.date(year - 1, month, day)
            except ValueError:
                continue
            return candidate.isoformat(), str(fm.get(key)).strip(), "source date + import year"
    year_match = re.match(r"20\d\d-\d\d-\d\d", imported)
    if year_match:
        return year_match.group(0), f"imported {year_match.group(0)}", "imported_at"
    return "", "", ""


def classify(relative: str, fm: dict, body: str) -> tuple[str, str, str, bool]:
    """Return (role, knowledge_type, display label, canonical) from declared metadata only."""
    kind = str(fm.get("type") or "").lower()
    name = Path(relative).name
    if name in INDEX_NAMES or kind in {"index", "navigation"}:
        return "index", "index", KNOWLEDGE_LABELS["index"], False
    if kind in {"historical_source", "source"}:
        source_kind = str(fm.get("source_document_kind") or "").lower()
        return "source", source_kind or "source_record", SOURCE_LABELS.get(source_kind, "Source record"), False
    if kind == "source_card":
        return "knowledge", "source_card", KNOWLEDGE_LABELS["source_card"], False
    declared = str(fm.get("knowledge_type") or "").strip().lower()
    if declared in KNOWLEDGE_LABELS:
        return "knowledge", declared, KNOWLEDGE_LABELS[declared], declared not in {"historical_evidence", "interpretation", "hypothesis", "uncertainty"}
    posture = TEMPORAL_RE.search(body[:2000])
    if posture:
        value = posture.group(1).lower()
        ktype = "historical_evidence" if value == "historical" else "verified_fact" if value == "current" else value
        return "knowledge", ktype, KNOWLEDGE_LABELS.get(ktype, value.replace("_", " ").title()), ktype == "verified_fact"
    if relative.startswith("inbox/"):
        return "knowledge", "inbox", KNOWLEDGE_LABELS["inbox"], False
    status = str(fm.get("status") or "").lower()
    if "hypothesis" in status:
        return "knowledge", "hypothesis", KNOWLEDGE_LABELS["hypothesis"], False
    for prefix, ktype in (
        ("decisions/", "explicit_decision"),
        ("prospects/", "prospect_entity_context"),
        ("operating_context/open_loops", "open_loop"),
        ("operating_context/current_priorities", "current_priority"),
        ("operating_context/active_projects", "client_project_context"),
        ("memory/clients", "client_project_context"),
    ):
        if relative.startswith(prefix):
            return "knowledge", ktype, KNOWLEDGE_LABELS[ktype], True
    return "knowledge", "canonical", KNOWLEDGE_LABELS["canonical"], relative.startswith(CANONICAL_AREAS)


def _frontmatter_list(raw: str, field: str) -> list[str]:
    fm, _ = aos_indexer.parse_frontmatter(raw)
    inline = str(fm.get(field) or "").strip().strip("[]")
    values = [item.strip(" '\"") for item in inline.split(",") if item.strip(" '\"")]
    match = aos_indexer.FRONTMATTER_RE.match(raw)
    if match and not values:
        collecting = False
        for line in match.group(1).splitlines():
            if not line.startswith((" ", "\t")):
                collecting = line.strip().lower() == f"{field}:"
                continue
            item = re.fullmatch(r"\s+-\s+(.+?)\s*", line)
            if collecting and item:
                values.append(item.group(1).strip("'\""))
    return values


def _title(body: str, fm: dict, fallback: str) -> str:
    return str(fm.get("title") or "").strip() or aos_indexer.title_from_text(body, fallback)


def _title_mentions(title: str, alias: str) -> bool:
    """Whole-word alias in a title; a bare first name must not be followed by a surname."""
    pattern = re.escape(alias) + (r"(?![\w'’-])(?!\s+[A-Z][a-z])" if len(alias.split()) == 1 else r"(?![\w'’-])")
    return re.search(r"(?<![\w'’-])" + pattern, title) is not None


def _receipt_packages() -> dict[str, str]:
    packages: dict[str, str] = {}
    try:
        lines = MEMORY_EXCHANGE_RECEIPTS.read_text(encoding="utf-8").splitlines()
    except OSError:
        return packages
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("outcome") not in {"imported", "committed", "refresh_pending"}:
            continue
        for output in record.get("outputs") or []:
            if isinstance(output, dict) and str(output.get("pointer") or "").startswith(BUSINESS_BRAIN_PREFIX):
                packages[output["pointer"]] = str(record.get("package_id") or "")
    return packages


def fingerprint(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT count(*), coalesce(sum(mtime), 0), coalesce(max(indexed_at), '') FROM documents "
        "WHERE source = 'business_brain' AND client_scope = 'global'"
    ).fetchone()
    try:
        stat = MEMORY_EXCHANGE_RECEIPTS.stat()
        receipts = f"{stat.st_size}:{stat.st_mtime}"
    except OSError:
        receipts = "none"
    return f"{INDEX_VERSION}|{row[0]}|{row[1]:.3f}|{row[2]}|{receipts}"


def _extract(pointers: list[str], vault: Path) -> tuple[dict, dict, dict]:
    docs: dict[str, dict] = {}
    entities: dict[str, dict] = {}
    links: dict[tuple[str, str], str] = {}
    packages = _receipt_packages()

    def entity(entity_id: str, name: str, kind: str, qualifier: str = "", aliases=()) -> None:
        record = entities.setdefault(entity_id, {"name": name, "type": kind, "qualifier": qualifier, "aliases": set()})
        record["aliases"].update({name, *aliases})
        if qualifier and not record["qualifier"]:
            record["qualifier"] = qualifier

    def link(entity_id: str, pointer: str, basis: str) -> None:
        links.setdefault((entity_id, pointer), basis)

    raw_by_pointer: dict[str, tuple[dict, str, str]] = {}
    for pointer in pointers:
        relative = pointer[len(BUSINESS_BRAIN_PREFIX):]
        path = vault / relative
        if path.suffix.lower() != ".md":
            continue
        try:
            raw = path.read_bytes()[: aos_indexer.MAX_TEXT_BYTES].decode("utf-8", errors="replace")
        except OSError:
            continue
        fm, body = aos_indexer.parse_frontmatter(raw)
        title = _title(body, fm, path.stem.replace("_", " ").replace("-", " ").title())
        role, ktype, label, canonical = classify(relative, fm, body)
        date_sort, date_text, date_basis = _resolve_date(relative, title, fm)
        docs[pointer] = {
            "title": title, "role": role, "knowledge_type": ktype, "type_label": label,
            "date_sort": date_sort, "date_text": date_text, "date_basis": date_basis,
            "canonical": canonical, "package_id": packages.get(pointer, ""),
        }
        raw_by_pointer[pointer] = (fm, body, raw)

    # 1. Declared metadata: participants, card entities, entity keys, prospect titles.
    has_people: set[str] = set()
    for pointer, (fm, body, raw) in raw_by_pointer.items():
        if docs[pointer]["role"] == "index":
            continue
        keys = [key for key in _frontmatter_list(raw, "entity_key") + _frontmatter_list(raw, "entity_keys") if norm(key)]
        declared_given = {norm(key.split(":", 1)[1]).split()[0] for key in keys if key.startswith("person:") and norm(key.split(":", 1)[1])}
        participants = str(fm.get("participants") or fm.get("participants_text") or "")
        segments = [segment for segment in participants.split(";") if segment.strip()]
        parsed = [parse_person(segment) for segment in segments]
        for person in filter(None, parsed):
            if len(person["name"].split()) == 1 and person["qualifier"] and norm(person["name"]) in declared_given:
                continue  # surname-less participant resolved by this record's own declared person entity_key
            entity(person["id"], person["name"], "person", person["qualifier"], person["aliases"])
            link(person["id"], pointer, "participants metadata")
        if segments and all(parsed):
            has_people.add(pointer)  # complete participant metadata: no title-mention fallback
        for topic in str(fm.get("entities") or "").split(","):
            topic = topic.strip(" '\"")
            if topic and norm(topic):
                entity(f"topic:{slug(topic)}", topic, "topic")
                link(f"topic:{slug(topic)}", pointer, "card entities metadata")
        for key in keys:
            kind = key.split(":", 1)[0] if ":" in key else "entity"
            name = key.split(":", 1)[-1].replace("-", " ").replace("_", " ").strip().title()
            entity(key if ":" in key else f"entity:{slug(key)}", name, kind)
            link(key if ":" in key else f"entity:{slug(key)}", pointer, "entity_key metadata")
            has_people.add(pointer)
        if str(fm.get("type") or "").lower() == "prospect":
            title = docs[pointer]["title"]
            parts = [part.strip() for part in re.split(r"\s+[—–-]\s+", title) if part.strip()]
            entity_id = f"prospect:{slug(fm.get('id') or Path(pointer).stem)}"
            entity(entity_id, title, "prospect", "", parts)
            link(entity_id, pointer, "prospect note")

    # 2. A card inherits the entities of the source it declares (source_path).
    for pointer, (fm, _body, _raw) in raw_by_pointer.items():
        source_path = str(fm.get("source_path") or "").strip()
        source_pointer = f"{BUSINESS_BRAIN_PREFIX}{source_path}"
        if docs[pointer]["knowledge_type"] == "source_card" and source_pointer in docs:
            if docs[source_pointer]["date_basis"] not in {"", "imported_at"} and docs[pointer]["date_basis"] in {"", "imported_at"}:
                for key in ("date_sort", "date_text", "date_basis"):
                    docs[pointer][key] = docs[source_pointer][key]
            for (entity_id, linked), _basis in list(links.items()):
                if linked == source_pointer and entity_id.startswith("person:"):
                    link(entity_id, pointer, "card of linked source")
            if source_pointer in has_people:
                has_people.add(pointer)

    people = {entity_id: record for entity_id, record in entities.items() if record["type"] == "person"}
    # 3. Title mentions for records without person metadata (exact alias, no surname guessing).
    for pointer, doc in docs.items():
        if doc["role"] == "index" or pointer in has_people:
            continue
        for entity_id, record in people.items():
            if any(_title_mentions(doc["title"], alias) for alias in record["aliases"]):
                link(entity_id, pointer, "title mention")

    # 4. Full-name mentions inside canonical knowledge (multi-word aliases only).
    for pointer, (_fm, body, _raw) in raw_by_pointer.items():
        doc = docs[pointer]
        relative = pointer[len(BUSINESS_BRAIN_PREFIX):]
        if doc["role"] != "knowledge" or not relative.startswith(CANONICAL_AREAS):
            continue
        for entity_id, record in people.items():
            if (entity_id, pointer) in links:
                continue
            if any(len(alias.split()) > 1 and re.search(r"(?<![\w'’-])" + re.escape(alias) + r"(?![\w'’-])", body) for alias in record["aliases"]):
                link(entity_id, pointer, "named in text")

    # 5. Records from the same Memory Exchange package as a person-linked record.
    by_package: dict[str, list[str]] = {}
    for pointer, doc in docs.items():
        if doc["package_id"]:
            by_package.setdefault(doc["package_id"], []).append(pointer)
    for siblings in by_package.values():
        linked_people = {entity_id for (entity_id, linked) in links if linked in siblings and entity_id.startswith("person:")}
        for entity_id in linked_people:
            for pointer in siblings:
                link(entity_id, pointer, "same Memory Ingest package")
    return docs, entities, links


def rebuild(db_path: Path | None = None, *, vault: Path | None = None) -> dict:
    start = time.perf_counter()
    conn = aos_indexer.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        pointers = [row[0] for row in conn.execute(
            "SELECT path FROM documents WHERE source = 'business_brain' AND client_scope = 'global' ORDER BY path"
        )]
        docs, entities, links = _extract(pointers, Path(vault or BUSINESS_BRAIN_ROOT))
        stamp = fingerprint(conn)
        conn.execute("BEGIN")
        for table in ("brain_documents", "entities", "entity_aliases", "entity_links", "entity_index_meta"):
            conn.execute(f"DELETE FROM {table}")
        conn.executemany(
            "INSERT INTO brain_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(p, d["title"], d["role"], d["knowledge_type"], d["type_label"], d["date_sort"], d["date_text"], d["date_basis"], int(d["canonical"]), d["package_id"]) for p, d in docs.items()],
        )
        for entity_id, record in entities.items():
            linked = [docs[p] for (e, p) in links if e == entity_id and p in docs]
            if not linked:
                continue
            conn.execute(
                "INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entity_id, record["name"], record["type"], record["qualifier"],
                 sum(1 for d in linked if d["role"] == "knowledge"), sum(1 for d in linked if d["role"] == "source"),
                 # latest *event* date only; an import date is not activity
                 max((d["date_sort"] for d in linked if d["date_basis"] not in {"", "imported_at"}), default="")),
            )
            conn.executemany("INSERT INTO entity_aliases VALUES (?, ?, ?)", [(entity_id, alias, norm(alias)) for alias in sorted(record["aliases"])])
        conn.executemany("INSERT INTO entity_links VALUES (?, ?, ?)", [(e, p, b) for (e, p), b in links.items()])
        conn.executemany("INSERT INTO entity_index_meta VALUES (?, ?)", [("fingerprint", stamp), ("built_at", aos_indexer.utc_now())])
        conn.commit()
    finally:
        conn.close()
    return {"status": "rebuilt", "documents": len(docs), "entities": len(entities), "links": len(links),
            "latency_ms": round((time.perf_counter() - start) * 1000, 2), "token_usage_text": TOKEN_USAGE_TEXT}


def ensure_current(db_path: Path | None = None) -> dict:
    """Rebuild only when the search index or ingest receipts changed since the last build."""
    path = aos_indexer.runtime_db_path(db_path)
    with _BUILD_LOCK:
        conn = aos_indexer.connect(path)
        try:
            conn.executescript(SCHEMA)
            stored = conn.execute("SELECT value FROM entity_index_meta WHERE key = 'fingerprint'").fetchone()
            current = fingerprint(conn)
        finally:
            conn.close()
        if stored and stored[0] == current:
            return {"status": "current", "token_usage_text": TOKEN_USAGE_TEXT}
        return rebuild(path)


def _connect_ro(db_path: Path | None) -> sqlite3.Connection:
    return aos_indexer.connect(aos_indexer.runtime_db_path(db_path), readonly=True)


def _entity_row(row: sqlite3.Row) -> dict:
    return {
        "entity_id": row["entity_id"], "display_name": row["display_name"], "entity_type": row["entity_type"],
        "qualifier": row["qualifier"], "knowledge_count": row["knowledge_count"], "source_count": row["source_count"],
        "latest_date": row["latest_date"],
    }


def search_entities(query: str, *, db_path: Path | None = None, limit: int = 12) -> dict:
    """Exact alias matches first, then every entity whose alias tokens all prefix-match the query."""
    terms = norm(query).split()
    if not terms:
        return {"query": query, "resolution": "none", "entities": []}
    conn = _connect_ro(db_path)
    try:
        rows = conn.execute(
            "SELECT e.*, a.alias, a.alias_norm FROM entity_aliases a JOIN entities e ON e.entity_id = a.entity_id"
        ).fetchall()
    finally:
        conn.close()
    joined = " ".join(terms)
    scored: dict[str, tuple[int, dict]] = {}
    for row in rows:
        tokens = row["alias_norm"].split()
        if row["alias_norm"] == joined:
            score = 0
        elif all(any(token.startswith(term) for token in tokens) for term in terms):
            score = 1
        else:
            continue
        current = scored.get(row["entity_id"])
        if current is None or score < current[0]:
            scored[row["entity_id"]] = (score, {**_entity_row(row), "matched_alias": row["alias"], "match": "exact" if score == 0 else "partial"})
    type_rank = {"person": 0, "prospect": 1, "company": 1, "project": 2, "topic": 3}
    ordered = sorted(scored.values(), key=lambda item: (item[0], type_rank.get(item[1]["entity_type"], 4), -(item[1]["knowledge_count"] + item[1]["source_count"]), item[1]["display_name"]))
    matches = [item[1] for item in ordered[:limit]]
    resolution = "none" if not matches else "single" if len(scored) == 1 else "ambiguous"
    return {"query": query, "resolution": resolution, "entities": matches}


def _doc_row(row: sqlite3.Row) -> dict:
    return {
        "path": row["path"], "title": row["title"], "role": row["role"], "knowledge_type": row["knowledge_type"],
        "type_label": row["type_label"], "date": row["date_sort"], "date_text": row["date_text"],
        "date_basis": row["date_basis"], "canonical": bool(row["canonical"]), "package_id": row["package_id"],
    }


def entity_view(entity_id: str, *, db_path: Path | None = None) -> dict | None:
    conn = _connect_ro(db_path)
    try:
        row = conn.execute("SELECT * FROM entities WHERE entity_id = ?", (entity_id,)).fetchone()
        if row is None:
            return None
        aliases = [r["alias"] for r in conn.execute("SELECT alias FROM entity_aliases WHERE entity_id = ? ORDER BY alias", (entity_id,))]
        linked = conn.execute(
            "SELECT d.*, l.basis FROM entity_links l JOIN brain_documents d ON d.path = l.path WHERE l.entity_id = ? "
            "ORDER BY d.date_sort DESC, d.title", (entity_id,)
        ).fetchall()
        paths = [r["path"] for r in linked]
        related = []
        if paths:
            marks = ",".join("?" for _ in paths)
            related = conn.execute(
                f"SELECT e.*, count(*) AS shared FROM entity_links l JOIN entities e ON e.entity_id = l.entity_id "
                f"WHERE l.path IN ({marks}) AND l.entity_id != ? GROUP BY e.entity_id ORDER BY shared DESC, e.display_name LIMIT 24",
                (*paths, entity_id),
            ).fetchall()
        similar = []
        if row["entity_type"] == "person":
            first = norm(row["display_name"]).split()[0]
            for other in conn.execute("SELECT * FROM entities WHERE entity_type = 'person' AND entity_id != ?", (entity_id,)):
                if first in norm(other["display_name"]).split():
                    similar.append(_entity_row(other))
    finally:
        conn.close()
    items = [{**_doc_row(r), "basis": r["basis"]} for r in linked]
    return {
        "entity": {**_entity_row(row), "aliases": aliases},
        "knowledge": [item for item in items if item["role"] == "knowledge"],
        "sources": [item for item in items if item["role"] == "source"],
        # An import date says when TTROS received a record, not when it happened,
        # so it never sits in the chronology beside event dates.
        "timeline": [item for item in items if item["date"] and item["date_basis"] != "imported_at"],
        "import_dated": [item for item in items if item["date_basis"] == "imported_at"],
        "undated_count": sum(1 for item in items if not item["date"]),
        "related": [{**_entity_row(r), "shared": r["shared"]} for r in related],
        "similar_not_merged": similar,
        "token_usage_text": TOKEN_USAGE_TEXT,
    }


def document_meta(paths: list[str], *, db_path: Path | None = None) -> dict[str, dict]:
    if not paths:
        return {}
    conn = _connect_ro(db_path)
    try:
        marks = ",".join("?" for _ in paths)
        rows = conn.execute(f"SELECT * FROM brain_documents WHERE path IN ({marks})", paths).fetchall()
        entity_rows = conn.execute(
            f"SELECT l.path, e.entity_id, e.display_name, e.entity_type, l.basis FROM entity_links l "
            f"JOIN entities e ON e.entity_id = l.entity_id WHERE l.path IN ({marks}) ORDER BY e.entity_type, e.display_name", paths
        ).fetchall()
    finally:
        conn.close()
    meta = {row["path"]: {**_doc_row(row), "entities": []} for row in rows}
    for row in entity_rows:
        if row["path"] in meta:
            meta[row["path"]]["entities"].append({"entity_id": row["entity_id"], "display_name": row["display_name"], "entity_type": row["entity_type"], "basis": row["basis"]})
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("rebuild")
    find = sub.add_parser("search")
    find.add_argument("query")
    show = sub.add_parser("show")
    show.add_argument("entity_id")
    args = parser.parse_args(argv)
    if args.command == "rebuild":
        result = rebuild()
    elif args.command == "search":
        ensure_current()
        result = search_entities(args.query)
    else:
        ensure_current()
        result = entity_view(args.entity_id) or {"error": "entity not found"}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
