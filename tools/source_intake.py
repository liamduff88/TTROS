#!/usr/bin/env python3
"""Deterministic historical-source intake for the TTROS Business Brain.

Revisit: when Brain source, search, Graphify, or scope contracts change. · Last touched: 2026-09-13.
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
SEMANTIC_TOKEN_USAGE_TEXT = "Token usage: unavailable from current CLI output"
INDEX_RELATIVE = "sources/intake/INDEX.md"
RECORDS_RELATIVE = "sources/intake/records"
CARDS_RELATIVE = "sources/intake/cards"
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
            # rstrip only: the vault's write_transaction runs `git diff --cached --check`,
            # which fails a commit on trailing whitespace. This is a rendering-only
            # normalization of the derived searchable copy -- exact original bytes are
            # preserved unchanged in the BYTES_BEGIN/BYTES_END block below, untouched by
            # this function. Trailing whitespace carries no semantic content.
            lines.append(
                line.replace("[[", "[ [")
                .replace("]]", "] ]")
                .replace("<!-- TTROS:HERMES:", "< !-- TTROS:HERMES:")
                .rstrip()
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


def _intake_cards_present(brain_root: Path, extra: frozenset[str] = frozenset()) -> set[str]:
    """Digests that already have a generated source card on disk, plus any `extra`
    digest whose card this same call is about to write (not yet on disk when this
    runs -- see `_run_semantic_intake`)."""
    cards_dir = brain_root / CARDS_RELATIVE
    present = {path.name.removesuffix(".card.md") for path in cards_dir.glob("*.card.md")} if cards_dir.is_dir() else set()
    return present | set(extra)


def _assert_index_links_source_and_card(index_text: str, digest: str) -> None:
    """The exact two-link shape a healthy `sources/intake/INDEX.md` entry has:
    the preserved original record and, once one exists, its generated card. This
    is the mechanical check for F-SOURCEINTAKE-CARDLINK-1 -- an existing card
    with no index link back to it is a needs-attention state, not a success."""
    if f"{RECORDS_RELATIVE}/{digest}|" not in index_text:
        raise SourceIntakeError(f"source-intake index is missing the original-record link for {digest}")
    if f"{CARDS_RELATIVE}/{digest}.card|card" not in index_text:
        raise SourceIntakeError(f"source-intake index is missing the generated-card link for {digest}")


def verify_intake_index_integrity(brain_root: Path) -> dict:
    """Read-only health check over the whole `sources/intake/` tree: every
    preserved original record and every generated card must have a working
    link in `sources/intake/INDEX.md`. Never mutates anything; safe to call at
    any time, including from the dashboard, as an operator-visible signal."""
    records_dir = brain_root / RECORDS_RELATIVE
    cards_dir = brain_root / CARDS_RELATIVE
    index_path = brain_root / INDEX_RELATIVE
    index_text = index_path.read_text(encoding="utf-8", errors="strict") if index_path.is_file() else ""
    record_digests = {path.stem for path in records_dir.glob("*.md")} if records_dir.is_dir() else set()
    card_digests = {path.name.removesuffix(".card.md") for path in cards_dir.glob("*.card.md")} if cards_dir.is_dir() else set()
    missing_record_links = sorted(digest for digest in record_digests if f"{RECORDS_RELATIVE}/{digest}|" not in index_text)
    missing_card_links = sorted(digest for digest in card_digests if f"{CARDS_RELATIVE}/{digest}.card|card" not in index_text)
    ok = index_path.is_file() and not missing_record_links and not missing_card_links
    return {
        "ok": ok if record_digests or card_digests else index_path.is_file(),
        "index_present": index_path.is_file(),
        "record_count": len(record_digests),
        "card_count": len(card_digests),
        "missing_record_links": missing_record_links,
        "missing_card_links": missing_card_links,
    }


def render_index(brain_root: Path, new_items: list[SourceItem], cards_present: set[str] | None = None) -> str:
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
    present = cards_present if cards_present is not None else _intake_cards_present(brain_root)
    lines = [
        "---", "id: source-intake-index", "type: index", "status: active", "---",
        "# Historical source intake", "",
        "> Revisit: when the deterministic source-intake contract changes. · Last touched: 2026-09-13.",
        "> These records preserve evidence. They do not promote raw communications into canonical truth.", "", "## Sources", "",
    ]
    for digest, fields in sorted(entries.items()):
        label = (fields.get("title") or fields.get("original_filename") or digest).replace("[", "(").replace("]", ")").replace("|", "-")
        date = f" · {fields['source_date']}" if fields.get("source_date") else ""
        filename = fields.get("original_filename", "unknown").replace("`", "'")
        # STEP MEMORYINTAKE-1, 2026-09-13: an entry whose source already has a
        # generated card must link the card too -- the Fred repair fixed one
        # entry by hand; this is what keeps every future one correct.
        card_suffix = f" · [[{CARDS_RELATIVE}/{digest}.card|card]]" if digest in present else ""
        lines.append(f"- [[{RECORDS_RELATIVE}/{digest}|{label}]] — `{filename}`{date} · `sha256:{digest}`{card_suffix}")
    return "\n".join(lines) + "\n"


def _configure_indexer(repo_root: Path, brain_root: Path, search_db: Path) -> dict[str, Path]:
    names = ("LIVE_ROOT", "BUSINESS_BRAIN_ROOT", "DB_PATH", "INGEST_CONFIG_PATH", "INGEST_RECEIPT_PATH")
    previous = {name: getattr(aos_indexer, name) for name in names}
    aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT, aos_indexer.DB_PATH = repo_root, brain_root, search_db
    aos_indexer.INGEST_CONFIG_PATH = repo_root / "queue/ingest_watch.json"
    aos_indexer.INGEST_RECEIPT_PATH = repo_root / "queue/receipts/ingestion.jsonl"
    return previous


def _run_semantic_intake(
    input_path: Path, *, repo_root: Path, brain_root: Path, search_db: Path, graphify_root: Path,
    client_scope: str, gate: "ClientScopeRegistry", commit: bool, now: Callable[[], str],
    semantic_budget: "object | None",
) -> IntakeResult:
    """Backfill/production path for mode="semantic": one already-preserved
    `type: historical_source` OR `type: source` (production capture) record in,
    a compact source card (Business Brain, gated write_transaction + graph/FTS
    refresh) and a structured claim receipt (system evidence,
    queue/receipts/source_intake/, outside the vault, never indexed) out. Never
    re-preserves the original.
    STEP I1, 2026-09-09; see scripts/i1_source_intake_semantic_extraction_transcript.md.
    Production-shape support added STEP I2, 2026-09-09; see
    scripts/i2_source_intake_production_path_transcript.md.
    """
    from tools import source_intake_semantic as sis

    source_path = Path(input_path).expanduser().resolve()
    if source_path.is_symlink():
        raise SourceIntakeError("symlink inputs are not supported")
    if not source_path.is_file():
        raise SourceIntakeError(f"semantic mode requires one existing historical_source record file: {source_path}")
    if aos_indexer.is_excluded(source_path):
        raise SourceIntakeError(f"protected, excluded, or symlink input: {source_path}")
    try:
        relative = source_path.relative_to(brain_root)
    except ValueError as exc:
        raise SourceIntakeError("semantic mode requires a source already preserved inside the Business Brain vault") from exc
    relative_posix = relative.as_posix()
    if relative.name in {"INDEX.md", "MANIFEST.md"}:
        raise SourceIntakeError(f"semantic mode refuses navigation/manifest files as a source: {relative_posix}")

    record_text = source_path.read_text(encoding="utf-8")
    # extract_verbatim_source() itself enforces type: historical_source or
    # type: source and raises SemanticExtractionError (a SourceIntakeError) for
    # anything else -- no separate type check needed here.
    header_fields, body = sis.extract_verbatim_source(record_text)

    source_id = sis.slug_for(source_path)
    source_sha256 = header_fields.get("source_sha256", "")
    # Production-shape captures (type: source) get their own card/receipt tree
    # and never touch the historical-only sources/historical_calls/INDEX.md
    # below -- that index is a curated table over the 15 pre-existing
    # historical_source imports, not a general card registry. Legacy
    # historical_source records keep the exact pre-existing behavior,
    # unchanged (STEP I2, 2026-09-10). Production-shape sources get their own
    # index update instead -- sources/intake/INDEX.md, the one capture mode
    # itself writes -- so the record's existing entry there also links its new
    # card (STEP MEMORYINTAKE-1, 2026-09-13; see the Fred hand-repair this
    # generalizes).
    is_production_shape = header_fields.get("type") == "source"
    if is_production_shape:
        card_relative = f"sources/intake/cards/{source_id}.card.md"
        index_relative = None
    else:
        card_relative = f"sources/historical_calls/cards/{source_id}.card.md"
        index_relative = "sources/historical_calls/INDEX.md"
    # Structured claim records are system evidence, never Business Brain content:
    # locked outside the vault, in the repo's own queue/receipts tree (never a
    # brain_pointer, never search-indexed -- .claims.yaml is not in
    # aos_indexer.INDEXABLE_EXTENSIONS).
    if is_production_shape:
        receipt_relative = f"queue/receipts/source_intake/claims/{source_id}.claims.yaml"
    else:
        receipt_relative = f"queue/receipts/source_intake/claims/historical/{source_id}.claims.yaml"
    receipt_path = repo_root / receipt_relative

    if (brain_root / card_relative).exists():
        return IntakeResult(
            "success", 1, 0, 1, 0, True, (), (f"business_brain:{card_relative}",),
            "unchanged", "unchanged", None, True,
        )

    stamp = now()
    prompt = sis.render_prompt(body)
    budget = semantic_budget if semantic_budget is not None else sis.ModelCallBudget(maximum=30)
    payload = sis.call_hermes_semantic(prompt, budget=budget, source_id=source_id)
    kept, dropped = sis.validate_claims(payload.get("claims"), body)
    card = payload.get("card") if isinstance(payload.get("card"), dict) else {}

    receipt_text = sis.render_claim_receipt(
        source_id=source_id, source_path=relative_posix, source_sha256=source_sha256,
        generated_at=stamp, model=sis.DEFAULT_MODEL, kept=kept, dropped=dropped,
    )
    card_text = sis.render_source_card(
        source_id=source_id, source_path=relative_posix, source_sha256=source_sha256,
        source_date=header_fields.get("source_date_text", "unavailable"), ingested_at=stamp,
        kind=header_fields.get("source_document_kind", ""), participants=header_fields.get("participants_text", ""),
        card=card, receipt_relative=receipt_relative,
    )

    if is_production_shape:
        documents = {card_relative: card_text}
        # Only sources capture mode itself preserved under sources/intake/records/
        # have an entry in sources/intake/INDEX.md to correct; a production-shape
        # source outside that tree (not produced by this module's own capture
        # path) has no such entry to link, and none is invented here.
        if relative_posix.startswith(f"{RECORDS_RELATIVE}/"):
            cards_present = _intake_cards_present(brain_root, extra=frozenset({source_id}))
            index_text = render_index(brain_root, [], cards_present=cards_present)
            _assert_index_links_source_and_card(index_text, source_id)
            documents[INDEX_RELATIVE] = index_text
    else:
        index_path = brain_root / index_relative
        if not index_path.is_file():
            raise SourceIntakeError(f"historical_calls navigation index is unavailable: {index_path}")
        cards_dir = brain_root / "sources/historical_calls/cards"
        existing_cards = {
            path.name[: -len(".card.md")]: path.read_text(encoding="utf-8")
            for path in (sorted(cards_dir.glob("*.card.md")) if cards_dir.is_dir() else [])
        }
        existing_cards[source_id] = card_text
        new_index_text = sis.evolve_historical_calls_index(index_path.read_text(encoding="utf-8"), existing_cards)
        documents = {card_relative: card_text, index_relative: new_index_text}

    gate.validate_brain_pointer(client_scope, f"business_brain:{card_relative}")

    # The receipt is not vault content -- written directly (atomically), never
    # through the gated vault write_transaction, and written before the vault
    # commit so a card's existence always implies its receipt already landed.
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_tmp = receipt_path.with_name(receipt_path.name + ".tmp")
    receipt_tmp.write_text(receipt_text, encoding="utf-8")
    receipt_tmp.replace(receipt_path)

    expected = {relative: brain_memory.file_sha256(brain_root / relative) for relative in documents}
    previous_indexer = _configure_indexer(repo_root, brain_root, search_db)
    previous_brain_root, brain_memory.VAULT_ROOT = brain_memory.VAULT_ROOT, brain_root
    refresh: dict[str, str] = {}
    refresh_started = False
    card_pointer = f"business_brain:{card_relative}"

    def verify_and_refresh(_changed: tuple[str, ...]) -> None:
        nonlocal refresh_started
        refresh_started = True
        graph = BusinessBrainGraphService(graphify_root=graphify_root, vault_root=brain_root, registry=gate).build()
        search = aos_indexer.scan(search_db, roots=[brain_root], registry=gate)
        if graph.get("status") != "success" or search.get("status") != "success" or not search.get("published"):
            raise SourceIntakeError("existing retrieval refresh failed")
        connection = aos_indexer.connect(search_db, readonly=True)
        try:
            indexed = {row[0] for row in connection.execute(
                "SELECT path FROM documents WHERE client_scope=? AND path=?", (client_scope, card_pointer),
            )}
        finally:
            connection.close()
        if card_pointer not in indexed:
            raise SourceIntakeError(f"card absent from exact search: {card_pointer}")
        refresh.update(search="ready", graphify=str(graph.get("operation") or "build"))

    try:
        written = brain_memory.write_transaction(
            documents, source=f"source-intake-semantic:{relative_posix}",
            session_id=f"source-intake-semantic-{stamp.replace(':', '').replace('-', '')}-{source_id[:24]}",
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
        "success", 1, 2, 0, 1, True,
        (card_pointer, receipt_relative), (), refresh["search"], refresh["graphify"],
        written.commit, True, SEMANTIC_TOKEN_USAGE_TEXT,
    )


def run_intake(
    input_path: Path, *, repo_root: Path = ROOT, brain_root: Path = BUSINESS_BRAIN_ROOT,
    registry_path: Path | None = None, schema_path: Path | None = None, search_db: Path | None = None,
    graphify_root: Path = Path("/home/liam/graphify-brain"), client_scope: str = "global",
    content_type: str | None = None, mode: str = "capture", commit: bool = True,
    now: Callable[[], str] = _utc_now, semantic_budget: "object | None" = None,
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
    if mode == "semantic":
        return _run_semantic_intake(
            input_path, repo_root=repo_root, brain_root=brain_root, search_db=search_db,
            graphify_root=graphify_root, client_scope=client_scope, gate=gate, commit=commit,
            now=now, semantic_budget=semantic_budget,
        )
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
