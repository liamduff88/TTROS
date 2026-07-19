"""Deterministic local SQLite FTS index for Agentic OS."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import uuid
from pathlib import Path

try:
    from aos_paths import aos_root, assert_authoritative_root, resolve_root_relative
    from aos_queue_storage import durable_append_text, durable_replace_text, fsync_directory, queue_write_lock
    from business_brain import BUSINESS_BRAIN_ROOT, business_brain_pointer_for_path
    from business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry
except ModuleNotFoundError:  # package import in unittest/IDE contexts
    from tools.aos_paths import aos_root, assert_authoritative_root, resolve_root_relative
    from tools.aos_queue_storage import durable_append_text, durable_replace_text, fsync_directory, queue_write_lock
    from tools.business_brain import BUSINESS_BRAIN_ROOT, business_brain_pointer_for_path
    from tools.business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry


TOKEN_USAGE_TEXT = "Token usage: no agent invocation"
LIVE_ROOT = aos_root()
DB_PATH = LIVE_ROOT / "search" / "os_index.db"
INGEST_CONFIG_PATH = LIVE_ROOT / "queue" / "ingest_watch.json"
INGEST_RECEIPT_PATH = LIVE_ROOT / "queue" / "receipts" / "ingestion.jsonl"
CLIENT_SCOPE_REGISTRY_PATH = LIVE_ROOT / "context" / "client_scope_registry.json"
TEXT_EXTENSIONS = {".md", ".txt", ".json", ".jsonl"}
FILENAME_ONLY_EXTENSIONS = {".pdf", ".docx", ".xlsx"}
INDEXABLE_EXTENSIONS = TEXT_EXTENSIONS | FILENAME_ONLY_EXTENSIONS
MAX_TEXT_BYTES = 750_000

PROTECTED_SEGMENTS = {
    ".git",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "cache",
    "north_shore_sales_coach",
    "_backups",
}
PROTECTED_PATH_PARTS = (
    "connectors/telegram_bridge",
    "workspaces/north_shore_sales_coach",
    "queue/command_routes.json",
    "queue/model_routes.json",
    "queue/lane_profiles.json",
    "capture/runtime",
    "queue/draft_runtime",
    "inbox/source_notes",
)
LEGACY_RE = re.compile(r"(old[_\s-]*(ubuntu|hermes|vault|runtime)|legacy|legacy_harvest|old[_\s-]*zpc|\bzpc\b)", re.I)
SECRET_PATH_RE = re.compile(r"(^|[/.])(\.env($|\.)|.*secret.*|.*token.*|.*credential.*|.*password.*)", re.I)
SENSITIVE_LINE_RE = re.compile(
    r"(api[_-]?key|secret|token|credential|password|authorization|bearer|private[_-]?key|north[_\s-]*shore)",
    re.I,
)
SECRET_CONTENT_RE = re.compile(r"(api[_-]?key|authorization|bearer|password|private[_-]?key|credential)", re.I)
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_path_text(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def source_for_path(path: Path) -> tuple[str, Path]:
    resolved = path.resolve()
    try:
        resolved.relative_to(LIVE_ROOT.resolve())
        return "agentic_os_live", LIVE_ROOT
    except ValueError:
        pass
    try:
        resolved.relative_to(BUSINESS_BRAIN_ROOT.resolve())
        return "business_brain", BUSINESS_BRAIN_ROOT
    except ValueError:
        return "external", resolved.parent


def is_excluded(path: Path | str, *, root: Path | None = None) -> bool:
    path_obj = Path(path)
    text = normalize_path_text(path_obj)
    lowered = text.lower()
    parts = [part.lower() for part in path_obj.parts]
    if any(part in PROTECTED_SEGMENTS for part in parts):
        return True
    if any(part.startswith(".venv") for part in parts):
        return True
    if "north_shore" in lowered or "north shore" in lowered:
        return True
    if SECRET_PATH_RE.search(lowered):
        return True
    if LEGACY_RE.search(lowered):
        return True
    check_text = lowered
    if root is not None:
        try:
            check_text = path_obj.resolve().relative_to(root.resolve()).as_posix().lower()
        except ValueError:
            check_text = lowered
    return any(part in check_text for part in PROTECTED_PATH_PARTS)


def ensure_default_config() -> dict:
    if INGEST_CONFIG_PATH.exists():
        return json.loads(INGEST_CONFIG_PATH.read_text(encoding="utf-8"))
    assert_authoritative_root(LIVE_ROOT)
    config = {
        "inboxes": ["queue/inbox"],
        "watch_roots": ["queue/inbox", "results", "workflows", "queue/receipts"],
        "business_brain_read_index_only": True,
        "token_usage_text": TOKEN_USAGE_TEXT,
    }
    INGEST_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    INGEST_CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (LIVE_ROOT / "queue" / "inbox").mkdir(parents=True, exist_ok=True)
    return config


def runtime_db_path(db_path: Path | None = None) -> Path:
    return db_path or DB_PATH


def connect(db_path: Path | None = None, *, readonly: bool = False) -> sqlite3.Connection:
    db_path = runtime_db_path(db_path)
    if readonly:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    assert_authoritative_root(db_path.parent)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            kind TEXT NOT NULL,
            source TEXT NOT NULL,
            source_root TEXT NOT NULL,
            mtime REAL NOT NULL,
            tags TEXT NOT NULL,
            snippet TEXT NOT NULL,
            body TEXT NOT NULL,
            indexed_at TEXT NOT NULL,
            size_bytes INTEGER NOT NULL
        )
        """
    )
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
    if "client_scope" not in columns:
        conn.execute("ALTER TABLE documents ADD COLUMN client_scope TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
        USING fts5(path, title, kind, source, tags, snippet, body, content='documents', content_rowid='id')
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_kind ON documents(kind)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_client_scope ON documents(client_scope)")
    conn.commit()
    return conn


def reset_index(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM documents_fts")
    conn.execute("DELETE FROM documents")
    conn.commit()


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().lower()] = value.strip().strip("'\"")
    return data, text[match.end() :]


def sanitize_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if SENSITIVE_LINE_RE.search(line):
            continue
        lines.append(line)
    return "\n".join(lines)


def title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()[:180] or fallback
        if stripped:
            return stripped[:180]
    return fallback


def tags_from_frontmatter(frontmatter: dict[str, str]) -> list[str]:
    raw = frontmatter.get("tags") or frontmatter.get("tag") or ""
    raw = raw.strip("[]")
    return [tag.strip(" '\"") for tag in raw.split(",") if tag.strip(" '\"")]


def kind_for_path(path: Path, source: str) -> str:
    rel = relative_to_root(path, LIVE_ROOT).lower() if source == "agentic_os_live" else path.name.lower()
    if source == "business_brain":
        return "memory"
    if rel.startswith("queue/receipts/"):
        return "receipt"
    if rel.startswith("queue/") and path.suffix.lower() == ".jsonl":
        return "queue_item"
    if rel.startswith("workflows/") or rel.startswith("skills/"):
        return "workflow"
    if rel.startswith("memory_index/") or rel.startswith("context/") or rel.startswith("decisions/"):
        return "memory"
    if rel.startswith("results/") or rel.startswith("logs/") or rel.startswith("packets/") or "artifact" in rel:
        return "artifact"
    return "file"


def document_from_path(path: Path, *, registry: ClientScopeRegistry | None = None) -> dict | None:
    if not path.is_file() or is_excluded(path):
        return None
    suffix = path.suffix.lower()
    if suffix not in INDEXABLE_EXTENSIONS:
        return None
    source, root = source_for_path(path)
    if source == "external":
        return None
    if is_excluded(path, root=root):
        return None
    pointer = business_brain_pointer_for_path(path, root=BUSINESS_BRAIN_ROOT) if source == "business_brain" else f"{source}:{relative_to_root(path, root)}"
    gate = registry or load_registry(CLIENT_SCOPE_REGISTRY_PATH)
    client_scope = gate.scope_for_search_identity(source, pointer)
    if client_scope is None:
        return None
    stat = path.stat()
    rel = relative_to_root(path, root)
    body = ""
    tags: list[str] = []
    if suffix in TEXT_EXTENSIONS:
        raw = path.read_bytes()[:MAX_TEXT_BYTES].decode("utf-8", errors="replace")
        if SECRET_CONTENT_RE.search(raw):
            return None
        frontmatter, content = parse_frontmatter(raw)
        tags = tags_from_frontmatter(frontmatter)
        body = sanitize_text(content)
        title = frontmatter.get("title") or frontmatter.get("name") or title_from_text(body, path.stem.replace("_", " ").title())
    else:
        title = path.stem.replace("_", " ").title()
        body = ""
    snippet = " ".join(body.split())[:600] if body else f"{path.suffix.lower()[1:].upper()} file indexed by filename only."
    return {
        "path": pointer,
        "title": title,
        "kind": kind_for_path(path, source),
        "source": source,
        "source_root": str(root),
        "client_scope": client_scope,
        "mtime": stat.st_mtime,
        "tags": ",".join(tags),
        "snippet": snippet,
        "body": body,
        "indexed_at": utc_now(),
        "size_bytes": stat.st_size,
    }


def upsert_document(conn: sqlite3.Connection, doc: dict) -> bool:
    existing = conn.execute("SELECT id FROM documents WHERE path = ?", (doc["path"],)).fetchone()
    values = (
        doc["path"],
        doc["title"],
        doc["kind"],
        doc["source"],
        doc["source_root"],
        doc["client_scope"],
        doc["mtime"],
        doc["tags"],
        doc["snippet"],
        doc["body"],
        doc["indexed_at"],
        doc["size_bytes"],
    )
    if existing:
        rowid = existing["id"]
        conn.execute(
            """
            UPDATE documents
            SET path=?, title=?, kind=?, source=?, source_root=?, client_scope=?, mtime=?, tags=?, snippet=?, body=?, indexed_at=?, size_bytes=?
            WHERE id=?
            """,
            (*values, rowid),
        )
        conn.execute("DELETE FROM documents_fts WHERE rowid=?", (rowid,))
    else:
        cur = conn.execute(
            """
            INSERT INTO documents(path, title, kind, source, source_root, client_scope, mtime, tags, snippet, body, indexed_at, size_bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        rowid = cur.lastrowid
    conn.execute(
        """
        INSERT INTO documents_fts(rowid, path, title, kind, source, tags, snippet, body)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (rowid, doc["path"], doc["title"], doc["kind"], doc["source"], doc["tags"], doc["snippet"], doc["body"]),
    )
    return True


def iter_indexable(root: Path):
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [
            name
            for name in dirnames
            if not is_excluded(current / name, root=root)
        ]
        for name in filenames:
            path = current / name
            if is_excluded(path, root=root):
                continue
            if path.suffix.lower() in INDEXABLE_EXTENSIONS:
                yield path


def _previous_index_snapshot(db_path: Path, target: Path) -> bool:
    if not db_path.exists():
        return False
    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()
        source.close()
    return True


def scan(
    db_path: Path | None = None,
    *,
    roots: list[Path] | None = None,
    registry: ClientScopeRegistry | None = None,
    failure_injection: str | None = None,
    capture_runtime_root: Path | None = None,
) -> dict:
    db_path = runtime_db_path(db_path)
    ensure_default_config()
    gate = registry or load_registry(CLIENT_SCOPE_REGISTRY_PATH)
    default_roots = roots is None
    roots = roots or [LIVE_ROOT, BUSINESS_BRAIN_ROOT]
    indexed = 0
    skipped = 0
    failures = []
    start = time.perf_counter()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    candidate = db_path.parent / f".{db_path.name}.{uuid.uuid4().hex}.candidate"
    previous = db_path.parent / f".{db_path.name}.{uuid.uuid4().hex}.previous"
    published = False
    retained_previous = db_path.exists()
    try:
        conn = connect(candidate)
        reset_index(conn)
        for root in roots:
            if not root.exists():
                continue
            for path in iter_indexable(root):
                try:
                    doc = document_from_path(path, registry=gate)
                    if not doc:
                        skipped += 1
                        continue
                    upsert_document(conn, doc)
                    indexed += 1
                except Exception as exc:  # complete candidate, but never publish a partial index
                    failures.append({"path": str(path), "error": str(exc)})
        projection_root = Path(capture_runtime_root) if capture_runtime_root is not None else (LIVE_ROOT / "capture" / "runtime" if default_roots else None)
        if projection_root is not None and projection_root.exists():
            try:
                try:
                    from aos_capture import capture_document, load_capture_metadata
                except ModuleNotFoundError:
                    from tools.aos_capture import capture_document, load_capture_metadata
                for projection in load_capture_metadata(projection_root):
                    try:
                        upsert_document(conn, capture_document(projection, registry=gate))
                        indexed += 1
                    except ClientScopeError:
                        skipped += 1
            except Exception as exc:
                failures.append({"path": str(projection_root), "error": str(exc)})
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.close()
        if failures:
            raise RuntimeError("candidate index contains source failures")
        if failure_injection == "before_publish":
            raise RuntimeError("injected search publication failure")
        with queue_write_lock(LIVE_ROOT):
            had_previous = _previous_index_snapshot(db_path, previous)
            try:
                os.replace(candidate, db_path)
                Path(str(db_path) + "-wal").unlink(missing_ok=True)
                Path(str(db_path) + "-shm").unlink(missing_ok=True)
                fsync_directory(db_path.parent)
                if failure_injection == "after_publish":
                    raise RuntimeError("injected search validation failure")
                validation = connect(db_path, readonly=True)
                validation.execute("SELECT client_scope, COUNT(*) FROM documents GROUP BY client_scope").fetchall()
                validation.close()
                published = True
            except Exception:
                if had_previous and previous.exists():
                    os.replace(previous, db_path)
                    Path(str(db_path) + "-wal").unlink(missing_ok=True)
                    Path(str(db_path) + "-shm").unlink(missing_ok=True)
                    fsync_directory(db_path.parent)
                raise
        retained_previous = not published and retained_previous
        status_value = "success"
    except Exception as exc:
        if not failures:
            failures.append({"path": str(db_path), "error": str(exc)})
        status_value = "failed"
    finally:
        for path in (candidate, previous, Path(str(candidate) + "-wal"), Path(str(candidate) + "-shm")):
            path.unlink(missing_ok=True)
    return {
        "status": status_value,
        "indexed": indexed,
        "skipped": skipped,
        "failures": failures[:25],
        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        "indexed_at": utc_now(),
        "db_path": str(db_path),
        "published": published,
        "retained_previous": retained_previous,
        "token_usage_text": TOKEN_USAGE_TEXT,
    }


def index_one(path_text: str, db_path: Path | None = None, *, registry: ClientScopeRegistry | None = None) -> dict:
    db_path = runtime_db_path(db_path)
    ensure_default_config()
    path = Path(path_text)
    if not path.is_absolute():
        path = resolve_root_relative(path_text, root=LIVE_ROOT)
    doc = document_from_path(path, registry=registry)
    if not doc:
        return {"status": "skipped", "path": str(path), "token_usage_text": TOKEN_USAGE_TEXT}
    conn = connect(db_path)
    upsert_document(conn, doc)
    conn.commit()
    return {"status": "success", "path": doc["path"], "kind": doc["kind"], "token_usage_text": TOKEN_USAGE_TEXT}


def quote_fts_query(query: str) -> str:
    terms = re.findall(r"[\w.-]+", query)
    return " OR ".join(f'"{term}"' for term in terms[:12])


def quote_exact_fts_query(query: str) -> str:
    terms = re.findall(r"[\w.-]+", query)
    return f'"{" ".join(terms[:24])}"' if terms else '""'


def public_row(row: sqlite3.Row) -> dict:
    value = dict(row)
    value["modified"] = dt.datetime.fromtimestamp(float(value["mtime"]), dt.timezone.utc).isoformat().replace("+00:00", "Z")
    value["tags"] = [tag for tag in str(value.get("tags") or "").split(",") if tag]
    value.pop("body", None)
    value.pop("mtime", None)
    return value


def search(
    query: str,
    *,
    kind: str = "",
    tag: str = "",
    source: str = "",
    limit: int = 25,
    db_path: Path | None = None,
    client_scope: str | None = None,
    registry: ClientScopeRegistry | None = None,
    exact: bool = False,
    path_only: bool = False,
) -> dict:
    db_path = runtime_db_path(db_path)
    start = time.perf_counter()
    gate = registry or load_registry(CLIENT_SCOPE_REGISTRY_PATH)
    scope = gate.validate_search_source(client_scope, source)
    if not db_path.exists():
        return {"query": query, "count": 0, "groups": {key: [] for key in ("files", "receipts", "queue_items", "prompts_skills_workflows", "memory", "artifacts")}, "latency_ms": 0.0, "token_usage_text": TOKEN_USAGE_TEXT}
    conn = connect(db_path, readonly=True)
    limit = max(1, min(int(limit or 25), 100))
    params: list[object] = []
    where = []
    join = ""
    select = "d.path, d.kind, d.source, d.client_scope" if path_only else "d.*"
    where.append("d.client_scope = ?")
    params.append(scope.scope_id)
    if query.strip():
        fts = quote_exact_fts_query(query) if exact else quote_fts_query(query)
        if not fts:
            fts = '""'
        join = "JOIN documents_fts f ON d.id = f.rowid"
        where.append("documents_fts MATCH ?")
        params.append(fts)
        select = ("d.path, d.kind, d.source, d.client_scope" if path_only else "d.*") + ", bm25(documents_fts) AS rank"
        order = "rank, d.mtime DESC"
    else:
        order = "d.mtime DESC"
    if kind:
        where.append("d.kind = ?")
        params.append(kind)
    if source:
        where.append("d.source = ?")
        params.append(source)
    if tag:
        where.append("(',' || d.tags || ',') LIKE ?")
        params.append(f"%,{tag},%")
    sql = f"SELECT {select} FROM documents d {join}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order} LIMIT ?"
    params.append(limit)
    selected = conn.execute(sql, params).fetchall()
    rows = [dict(row) if path_only else public_row(row) for row in selected]
    conn.close()
    groups: dict[str, list[dict]] = {
        "files": [],
        "receipts": [],
        "queue_items": [],
        "prompts_skills_workflows": [],
        "memory": [],
        "artifacts": [],
    }
    for row in rows:
        if is_excluded(row["path"]):
            continue
        bucket = {
            "receipt": "receipts",
            "queue_item": "queue_items",
            "workflow": "prompts_skills_workflows",
            "memory": "memory",
            "artifact": "artifacts",
        }.get(row["kind"], "files")
        groups[bucket].append(row)
    return {
        "query": query,
        "count": sum(len(items) for items in groups.values()),
        "groups": groups,
        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        "token_usage_text": TOKEN_USAGE_TEXT,
    }


def status(db_path: Path | None = None) -> dict:
    db_path = runtime_db_path(db_path)
    if not db_path.exists():
        return {
            "exists": False,
            "files_indexed": 0,
            "last_scan_time": None,
            "last_ingestion_receipt": None,
            "failures_count": 0,
            "db_path": str(db_path),
            "token_usage_text": TOKEN_USAGE_TEXT,
        }
    conn = connect(db_path, readonly=True)
    row = conn.execute("SELECT COUNT(*) AS count, MAX(indexed_at) AS last_scan_time FROM documents").fetchone()
    latest_receipt = None
    failures_count = 0
    if INGEST_RECEIPT_PATH.exists():
        for line in INGEST_RECEIPT_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            latest_receipt = record
            if record.get("status") not in {"success", "skipped"}:
                failures_count += 1
    return {
        "exists": True,
        "files_indexed": int(row["count"] or 0),
        "last_scan_time": row["last_scan_time"],
        "last_ingestion_receipt": latest_receipt,
        "failures_count": failures_count,
        "db_path": str(db_path),
        "token_usage_text": TOKEN_USAGE_TEXT,
    }


def load_watch_roots() -> list[Path]:
    config = ensure_default_config()
    roots = []
    for value in config.get("watch_roots") or config.get("inboxes") or ["queue/inbox"]:
        try:
            roots.append(resolve_root_relative(value, root=LIVE_ROOT))
        except Exception:
            continue
    return roots


def write_ingestion_receipt(record: dict) -> None:
    assert_authoritative_root(LIVE_ROOT)
    durable_append_text(LIVE_ROOT, INGEST_RECEIPT_PATH, json.dumps(record, sort_keys=True) + "\n")


def ingested_source_paths() -> set[str]:
    if not INGEST_RECEIPT_PATH.exists():
        return set()
    paths = set()
    for line in INGEST_RECEIPT_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        source_path = str(record.get("source_path") or "")
        if source_path:
            paths.add(source_path)
    return paths


def is_inbox_path(path: Path) -> bool:
    config = ensure_default_config()
    for value in config.get("inboxes") or ["queue/inbox"]:
        try:
            inbox = resolve_root_relative(value, root=LIVE_ROOT)
            path.resolve().relative_to(inbox.resolve())
            return True
        except Exception:
            continue
    return False


def ingest_tick(db_path: Path | None = None) -> dict:
    db_path = runtime_db_path(db_path)
    ensure_default_config()
    processed = []
    indexed = 0
    already_receipted = ingested_source_paths()
    candidates = []
    for root in load_watch_roots():
        if not root.exists() or BUSINESS_BRAIN_ROOT.resolve() in root.resolve().parents:
            continue
        for path in iter_indexable(root):
            if path.suffix.lower() not in INDEXABLE_EXTENSIONS:
                continue
            if path.resolve() == INGEST_RECEIPT_PATH.resolve():
                continue
            candidates.append(path)
    for path in candidates:
        result = index_one(str(path), db_path=db_path)
        indexed += 1
        if not is_inbox_path(path) or str(path) in already_receipted:
            continue
        source, source_root = source_for_path(path)
        record = {
            "timestamp": utc_now(),
            "source_path": str(path),
            "indexed_path": result.get("path", str(path)),
            "status": result.get("status", "success"),
            "kind": result.get("kind", kind_for_path(path, source)),
            "source": source,
            "source_root": str(source_root),
            "token_usage_text": TOKEN_USAGE_TEXT,
        }
        write_ingestion_receipt(record)
        processed.append(record)
    return {
        "status": "success",
        "processed": processed,
        "count": len(processed),
        "indexed": indexed,
        "token_usage_text": TOKEN_USAGE_TEXT,
    }


def artifacts(*, kind: str = "", tag: str = "", source: str = "", limit: int = 50, db_path: Path | None = None, client_scope: str | None = None, registry: ClientScopeRegistry | None = None) -> dict:
    result = search("", kind=kind, tag=tag, source=source, limit=limit, db_path=db_path, client_scope=client_scope, registry=registry)
    items = []
    for group_name in ("artifacts", "receipts", "queue_items", "prompts_skills_workflows", "memory", "files"):
        items.extend(result["groups"][group_name])
    items.sort(key=lambda item: item.get("modified") or "", reverse=True)
    return {"items": items[:limit], "latency_ms": result["latency_ms"], "token_usage_text": TOKEN_USAGE_TEXT}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agentic OS local deterministic search index")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan")
    one = sub.add_parser("index")
    one.add_argument("path")
    watch = sub.add_parser("watch")
    watch.add_argument("--once", action="store_true")
    query = sub.add_parser("search")
    query.add_argument("q")
    query.add_argument("--limit", type=int, default=10)
    query.add_argument("--client-scope", required=True)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    if args.command == "scan":
        payload = scan()
    elif args.command == "index":
        payload = index_one(args.path)
    elif args.command == "watch":
        payload = ingest_tick()
    elif args.command == "search":
        payload = search(args.q, limit=args.limit, client_scope=args.client_scope)
    elif args.command == "status":
        payload = status()
    else:
        parser.error("unknown command")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
