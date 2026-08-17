#!/usr/bin/env python3
"""Deterministic historical-source intake for the TTROS Business Brain.

Revisit: when Brain source, search, Graphify, or scope contracts change. · Last touched: 2026-08-17.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "tools"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from dashboard.backend.business_brain_graph import BusinessBrainGraphService
from tools import aos_indexer, brain_memory
from tools.business_brain import BUSINESS_BRAIN_ROOT
from tools.business_brain_scope import ClientScopeRegistry

TOKEN_USAGE_TEXT = "Token usage: no agent invocation"
INDEX_RELATIVE = "sources/intake/INDEX.md"
RECORDS_RELATIVE = "sources/intake/records"
MAIN_INDEX_RELATIVE = "index/MEMORY_INDEX.md"
INTAKE_LINK = "[[sources/intake/INDEX|Historical source intake]]"
BYTES_BEGIN = "<!-- TTROS:SOURCE-BYTES:BEGIN -->"
BYTES_END = "<!-- TTROS:SOURCE-BYTES:END -->"
SUPPORTED_SUFFIXES = {".txt": "text/plain", ".md": "text/markdown", ".eml": "message/rfc822"}
SUPPORTED_MIME = frozenset(SUPPORTED_SUFFIXES.values())
DATE_RE = re.compile(r"(?<!\d)(20\d{2})[-_](0[1-9]|1[0-2])[-_](0[1-9]|[12]\d|3[01])(?!\d)")


class SourceIntakeError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceItem:
    path: Path
    raw: bytes
    sha256: str
    content_type: str
    title: str
    source_date: str | None

    @property
    def relative(self) -> str:
        return f"{RECORDS_RELATIVE}/{self.sha256}.md"

    @property
    def pointer(self) -> str:
        return f"business_brain:{self.relative}"


@dataclass(frozen=True)
class IntakeResult:
    status: str
    scanned: int
    imported: int
    duplicates: int
    model_invocations: int
    retrieval_ready: bool
    imported_pointers: tuple[str, ...]
    duplicate_pointers: tuple[str, ...]
    search_status: str
    graphify_status: str
    brain_commit: str | None
    semantic_requested: bool
    token_usage_text: str = TOKEN_USAGE_TEXT

    def compact(self) -> str:
        file_label = "file" if self.scanned == 1 else "files"
        duplicate_label = "duplicate" if self.duplicates == 1 else "duplicates"
        readiness = "retrieval ready" if self.retrieval_ready else "retrieval unavailable"
        return (
            f"{self.scanned} {file_label} scanned | {self.imported} imported | "
            f"{self.duplicates} {duplicate_label} | {self.model_invocations} model calls | {readiness}"
        )


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _one_line(value: str, fallback: str) -> str:
    cleaned = " ".join(str(value or "").replace("\x00", " ").split()).strip("# ")
    return (cleaned or fallback).replace("[[", "[ [").replace("]]", "] ]")[:160]


def _metadata(path: Path, raw: bytes, content_type: str) -> tuple[str, str | None]:
    fallback = path.stem.replace("_", " ").replace("-", " ").title() or path.name
    if content_type == "message/rfc822":
        try:
            message = BytesParser(policy=policy.default).parsebytes(raw)
            title = _one_line(str(message.get("subject") or ""), fallback)
            source_date = parsedate_to_datetime(str(message.get("date"))).date().isoformat() if message.get("date") else None
            return title, source_date
        except (TypeError, ValueError, OverflowError):
            return fallback, None
    text = raw.decode("utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    heading = next((line.lstrip("#").strip() for line in lines if line.startswith("#")), "")
    match = DATE_RE.search(path.name)
    return _one_line(heading or (lines[0] if lines else ""), fallback), "-".join(match.groups()) if match else None


def _content_type(path: Path, raw: bytes, override: str | None) -> str:
    if override:
        value = override.split(";", 1)[0].strip().lower()
        if value not in SUPPORTED_MIME:
            raise SourceIntakeError(f"unsupported content type: {override}")
        return value
    if path.suffix.lower() in SUPPORTED_SUFFIXES:
        return SUPPORTED_SUFFIXES[path.suffix.lower()]
    if not path.suffix:
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            text = ""
        if text and "\x00" not in text:
            return "text/plain"
    raise SourceIntakeError(
        f"unsupported input: {path} (supported: .txt, .md, text/plain, message/rfc822/.eml)"
    )


def inventory(input_path: Path, *, content_type: str | None = None) -> list[SourceItem]:
    source = Path(input_path).expanduser().resolve()
    if not source.exists():
        raise SourceIntakeError(f"input does not exist: {source}")
    if source.is_symlink():
        raise SourceIntakeError("symlink inputs are not supported")
    paths = [source] if source.is_file() else sorted(path for path in source.rglob("*") if path.is_file()) if source.is_dir() else []
    if not paths:
        raise SourceIntakeError(f"input is not a file or contains no files: {source}")
    if content_type and len(paths) != 1:
        raise SourceIntakeError("--content-type applies only to one file")
    items = []
    for path in paths:
        if path.is_symlink() or aos_indexer.is_excluded(path):
            raise SourceIntakeError(f"protected, excluded, or symlink input: {path}")
        raw = path.read_bytes()
        detected = _content_type(path, raw, content_type)
        title, source_date = _metadata(path, raw, detected)
        items.append(SourceItem(path, raw, hashlib.sha256(raw).hexdigest(), detected, title, source_date))
    return items


def _searchable(item: SourceItem) -> str:
    lines = []
    for line in item.raw.decode("utf-8", errors="replace").splitlines():
        if not aos_indexer.SENSITIVE_LINE_RE.search(line):
            lines.append(
                line.replace("[[", "[ [")
                .replace("]]", "] ]")
                .replace("<!-- TTROS:HERMES:", "< !-- TTROS:HERMES:")
            )
    return "\n".join(lines).strip() or "[No safely indexable UTF-8 text; exact bytes remain preserved below.]"


def render_record(item: SourceItem, imported_at: str) -> str:
    y = lambda value: json.dumps(str(value), ensure_ascii=False)
    frontmatter = [
        "---", f"id: source-intake-{item.sha256}", "type: source", "status: historical-evidence",
        f"title: {y(item.title)}", f"original_filename: {y(item.path.name)}", f"source_path: {y(item.path)}",
        f"imported_at: {y(imported_at)}", f"source_sha256: {item.sha256}", f"source_bytes: {len(item.raw)}",
        f"content_type: {y(item.content_type)}", "knowledge_state: raw-source-not-canonical-truth", "model_invocations: 0",
    ]
    if item.source_date:
        frontmatter.append(f"source_date: {y(item.source_date)}")
    body = [
        "---", f"# {item.title}", "",
        "> Expires: never; byte-faithful historical source. Revisit only if the source contract changes.",
        "> Raw communications are evidence, not canonical organisational truth.", "", "## Source metadata", "",
        f"- Original filename: `{item.path.name}`", f"- SHA-256: `{item.sha256}`",
        f"- Content type: `{item.content_type}`", f"- Imported: `{imported_at}`",
    ]
    if item.source_date:
        body.append(f"- Obvious source date: `{item.source_date}`")
    body.extend([
        "", "## Searchable source text", "", _searchable(item), "", "## Exact source bytes", "",
        "Base64 decodes to the exact original bytes named by `source_sha256`.", "", BYTES_BEGIN,
        base64.b64encode(item.raw).decode("ascii"), BYTES_END, "",
    ])
    return "\n".join(frontmatter + body)


def extract_exact_bytes(text: str) -> bytes:
    try:
        return base64.b64decode(text.split(BYTES_BEGIN, 1)[1].split(BYTES_END, 1)[0].strip(), validate=True)
    except (IndexError, ValueError) as exc:
        raise SourceIntakeError("source record has no valid exact-byte payload") from exc


def _frontmatter(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    with path.open("r", encoding="utf-8", errors="strict") as handle:
        if handle.readline().rstrip() != "---":
            raise SourceIntakeError(f"source record lacks frontmatter: {path}")
        for line in handle:
            if line.rstrip() == "---":
                return fields
            key, separator, value = line.partition(":")
            if separator:
                fields[key.strip()] = value.strip().strip('"')
    raise SourceIntakeError(f"source record has unterminated frontmatter: {path}")


def render_index(brain_root: Path, new_items: list[SourceItem]) -> str:
    entries: dict[str, dict[str, str]] = {}
    records = brain_root / RECORDS_RELATIVE
    if records.is_dir():
        for path in sorted(records.glob("*.md")):
            fields = _frontmatter(path)
            digest = fields.get("source_sha256", "")
            if re.fullmatch(r"[0-9a-f]{64}", digest):
                entries[digest] = fields
    for item in new_items:
        entries[item.sha256] = {
            "title": item.title, "original_filename": item.path.name,
            "source_sha256": item.sha256, "source_date": item.source_date or "",
        }
    lines = [
        "---", "id: source-intake-index", "type: index", "status: active", "---",
        "# Historical source intake", "",
        "> Revisit: when the deterministic source-intake contract changes. · Last touched: 2026-08-17.",
        "> These records preserve evidence. They do not promote raw communications into canonical truth.", "", "## Sources", "",
    ]
    for digest, fields in sorted(entries.items()):
        label = (fields.get("title") or fields.get("original_filename") or digest).replace("[", "(").replace("]", ")").replace("|", "-")
        date = f" · {fields['source_date']}" if fields.get("source_date") else ""
        filename = fields.get("original_filename", "unknown").replace("`", "'")
        lines.append(f"- [[{RECORDS_RELATIVE}/{digest}|{label}]] — `{filename}`{date} · `sha256:{digest}`")
    return "\n".join(lines) + "\n"


def _configure_indexer(repo_root: Path, brain_root: Path, search_db: Path) -> dict[str, Path]:
    names = ("LIVE_ROOT", "BUSINESS_BRAIN_ROOT", "DB_PATH", "INGEST_CONFIG_PATH", "INGEST_RECEIPT_PATH")
    previous = {name: getattr(aos_indexer, name) for name in names}
    aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT, aos_indexer.DB_PATH = repo_root, brain_root, search_db
    aos_indexer.INGEST_CONFIG_PATH = repo_root / "queue/ingest_watch.json"
    aos_indexer.INGEST_RECEIPT_PATH = repo_root / "queue/receipts/ingestion.jsonl"
    return previous


def run_intake(
    input_path: Path, *, repo_root: Path = ROOT, brain_root: Path = BUSINESS_BRAIN_ROOT,
    registry_path: Path | None = None, schema_path: Path | None = None, search_db: Path | None = None,
    graphify_root: Path = Path("/home/liam/graphify-brain"), client_scope: str = "global",
    content_type: str | None = None, mode: str = "capture", commit: bool = True,
    now: Callable[[], str] = _utc_now,
) -> IntakeResult:
    if client_scope != "global":
        raise SourceIntakeError("routine intake is global-only; client material requires its existing isolated workflow")
    if mode not in {"capture", "semantic"}:
        raise SourceIntakeError("mode must be capture or semantic")
    repo_root, brain_root = Path(repo_root).resolve(), Path(brain_root).resolve()
    registry_path = Path(registry_path or repo_root / "context/client_scope_registry.json")
    schema_path = Path(schema_path or repo_root / "context/client_scope_registry.schema.json")
    search_db = Path(search_db or repo_root / "search/os_index.db")
    gate = ClientScopeRegistry(registry_path=registry_path, schema_path=schema_path)
    gate.resolve_scope(client_scope)
    items = inventory(input_path, content_type=content_type)

    unique: dict[str, SourceItem] = {}
    duplicates: list[str] = []
    for item in items:
        if item.sha256 in unique:
            duplicates.append(unique[item.sha256].pointer)
        else:
            unique[item.sha256] = item
    new_items = []
    for item in unique.values():
        gate.validate_brain_pointer(client_scope, item.pointer)
        target = brain_root / item.relative
        if target.exists():
            preserved = extract_exact_bytes(target.read_text(encoding="utf-8", errors="strict"))
            if preserved != item.raw or hashlib.sha256(preserved).hexdigest() != item.sha256:
                raise SourceIntakeError(f"existing source record failed exact-byte verification: {item.pointer}")
            duplicates.append(item.pointer)
        else:
            new_items.append(item)
    if not new_items:
        return IntakeResult("success", len(items), 0, len(duplicates), 0, True, (), tuple(duplicates),
                            "unchanged", "unchanged", None, mode == "semantic")

    main_index = brain_root / MAIN_INDEX_RELATIVE
    if not main_index.is_file():
        raise SourceIntakeError(f"Business Brain navigation index is unavailable: {main_index}")
    stamp = now()
    existing_main = main_index.read_text(encoding="utf-8", errors="strict")
    documents = {item.relative: render_record(item, stamp) for item in new_items}
    documents[INDEX_RELATIVE] = render_index(brain_root, new_items)
    documents[MAIN_INDEX_RELATIVE] = existing_main if INTAKE_LINK in existing_main else existing_main.rstrip() + f"\n\n## Historical source intake\n\n{INTAKE_LINK}\n"
    expected = {relative: brain_memory.file_sha256(brain_root / relative) for relative in documents}
    previous_indexer = _configure_indexer(repo_root, brain_root, search_db)
    previous_brain_root, brain_memory.VAULT_ROOT = brain_memory.VAULT_ROOT, brain_root
    refresh: dict[str, str] = {}
    refresh_started = False

    def verify_and_refresh(_changed: tuple[str, ...]) -> None:
        nonlocal refresh_started
        for item in new_items:
            preserved = extract_exact_bytes((brain_root / item.relative).read_text(encoding="utf-8", errors="strict"))
            if preserved != item.raw or hashlib.sha256(preserved).hexdigest() != item.sha256:
                raise SourceIntakeError(f"exact-byte verification failed: {item.pointer}")
            gate.resolve_brain_pointer(client_scope, item.pointer, root=brain_root)
        refresh_started = True
        graph = BusinessBrainGraphService(graphify_root=graphify_root, vault_root=brain_root, registry=gate).build()
        search = aos_indexer.scan(search_db, roots=[brain_root], registry=gate)
        if graph.get("status") != "success" or search.get("status") != "success" or not search.get("published"):
            raise SourceIntakeError("existing retrieval refresh failed")
        connection = aos_indexer.connect(search_db, readonly=True)
        try:
            indexed = {row[0] for row in connection.execute(
                "SELECT path FROM documents WHERE client_scope=? AND path IN (%s)" % ",".join("?" for _ in new_items),
                (client_scope, *(item.pointer for item in new_items)),
            )}
        finally:
            connection.close()
        missing = {item.pointer for item in new_items} - indexed
        if missing:
            raise SourceIntakeError(f"sources absent from exact search: {', '.join(sorted(missing))}")
        refresh.update(search="ready", graphify=str(graph.get("operation") or "build"))

    try:
        written = brain_memory.write_transaction(
            documents, source=f"source-intake:{Path(input_path).resolve()}",
            session_id=f"source-intake-{stamp.replace(':', '').replace('-', '')}-{new_items[0].sha256[:12]}",
            expected_hashes=expected, commit=commit, post_write_validator=verify_and_refresh,
        )
    except Exception:
        if refresh_started:
            try:
                BusinessBrainGraphService(graphify_root=graphify_root, vault_root=brain_root, registry=gate).build()
                aos_indexer.scan(search_db, roots=[brain_root], registry=gate)
            except Exception:
                pass
        raise
    finally:
        brain_memory.VAULT_ROOT = previous_brain_root
        for name, value in previous_indexer.items():
            setattr(aos_indexer, name, value)

    return IntakeResult(
        "success", len(items), len(new_items), len(duplicates), 0, True,
        tuple(item.pointer for item in new_items), tuple(duplicates), refresh["search"], refresh["graphify"],
        written.commit, mode == "semantic",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture historical text sources into the existing TTROS Business Brain")
    parser.add_argument("input", type=Path)
    parser.add_argument("--mode", choices=("capture", "semantic"), default="capture")
    parser.add_argument("--client-scope", default="global")
    parser.add_argument("--content-type", help="MIME type for one extensionless file")
    parser.add_argument("--brain-root", type=Path, default=BUSINESS_BRAIN_ROOT)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--search-db", type=Path)
    parser.add_argument("--graphify-root", type=Path, default=Path("/home/liam/graphify-brain"))
    parser.add_argument("--no-commit", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_intake(
            args.input, repo_root=args.repo_root, brain_root=args.brain_root,
            registry_path=args.registry, schema_path=args.schema, search_db=args.search_db,
            graphify_root=args.graphify_root, client_scope=args.client_scope,
            content_type=args.content_type, mode=args.mode, commit=not args.no_commit,
        )
    except SourceIntakeError as exc:
        print(f"source intake failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"source intake failed safely: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(result), indent=2, sort_keys=True) if args.json else result.compact())
    if result.semantic_requested:
        print("Semantic mode requested: retrieve only relevant imported sources, then apply existing promotion/review rules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
