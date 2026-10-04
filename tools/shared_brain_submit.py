"""Add-only, unconfirmed Shared Brain submissions from authenticated transports.

Revisit: when the Brain review tier or submit contract changes. Last touched: 2026-10-03.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

try:
    from . import brain_memory, shared_brain_read
    from .shared_brain_checkpoint import WORKSTREAM_RE, _host_path
except ImportError:
    import brain_memory
    import shared_brain_read
    from shared_brain_checkpoint import WORKSTREAM_RE, _host_path

TYPES = {"decision", "fact", "deliverable", "milestone"}
KEY_RE = re.compile(r"[A-Za-z0-9_-]{8,100}\Z")
DRIVE_RE = re.compile(r"[A-Za-z]:[\\/]")
MAX_TITLE = 200
MAX_BODY = 20_000
MAX_REFS = 20
MAX_REF = 300
RECORD_ID_RE = re.compile(r"record:[a-z0-9][a-z0-9_-]{2,127}\Z")
# Lines `git diff --check` reads as leftover merge conflicts; the commit gate would refuse them.
CONFLICT_MARKER_RE = re.compile(r"^(?:<{7}|={7}|>{7}|\|{7})(?:[ \t]|$)", re.MULTILINE)
_log = logging.getLogger("shared_brain")


def _normalise(text: str) -> str:
    """Remove the whitespace the Brain commit gate (`git diff --check`) refuses.

    Clients routinely send a trailing newline, Markdown hard breaks or CRLF line ends.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [re.sub(r"^[ \t]+", lambda m: m.group(0).expandtabs(4), line).rstrip() for line in lines]
    return "\n".join(lines).strip("\n")


def _indexed_record_id(reference: str) -> bool:
    if not RECORD_ID_RE.fullmatch(reference):
        return False
    conn = shared_brain_read.aos_indexer.connect(shared_brain_read.aos_indexer.runtime_db_path(), readonly=True)
    try:
        paths = [row[0] for row in conn.execute(
            "SELECT path FROM documents WHERE source = 'business_brain' AND client_scope = 'global'")]
    finally:
        conn.close()
    wanted = reference.removeprefix("record:")
    for path in paths:
        target = shared_brain_read._indexed_target(path)
        if target is None:
            continue
        try:
            frontmatter, _ = brain_memory.parse_frontmatter(target.read_text(encoding="utf-8"))
        except (OSError, brain_memory.BrainMemoryError):
            continue
        if frontmatter.get("id") == wanted:
            return True
    return False


def _validate(type: str, title: str, body: str, source_refs: list[str],
              workstream_id: str | None, idempotency_key: str) -> str | None:
    if type not in TYPES:
        return "type must be decision, fact, deliverable, or milestone"
    if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE:
        return "title must contain 1-200 characters"
    if _host_path(title) or any(ord(char) < 32 for char in title):
        return "title cannot contain host paths or control characters"
    if not isinstance(body, str) or not body.strip() or len(body) > MAX_BODY:
        return "body must contain 1-20000 characters"
    if CONFLICT_MARKER_RE.search(body):
        return "body cannot contain Git conflict-marker lines"
    if not isinstance(source_refs, list) or len(source_refs) > MAX_REFS:
        return "source_refs may contain at most 20 references"
    if workstream_id is not None and not WORKSTREAM_RE.fullmatch(str(workstream_id)):
        return "invalid workstream ID"
    if not isinstance(idempotency_key, str) or not KEY_RE.fullmatch(idempotency_key):
        return "idempotency_key must be 8-100 letters, digits, underscores or hyphens"
    for ref in source_refs:
        if not isinstance(ref, str) or not ref or len(ref) > MAX_REF:
            return "each source reference must contain 1-300 characters"
        if ref.startswith("/") or ref.startswith("file://") or DRIVE_RE.match(ref) or ".." in ref or "\\" in ref:
            return "source references cannot be filesystem paths"
        if _host_path(ref) or any(char.isspace() for char in ref):
            return "source references cannot contain host addresses, paths or whitespace"
        if ref.startswith("https://"):
            continue
        if WORKSTREAM_RE.fullmatch(ref):
            continue
        if shared_brain_read._indexed_target(ref) is not None:
            continue
        if _indexed_record_id(ref):
            continue
        return "source reference must be an indexed Brain record, workstream ID or HTTPS URL"
    return None


def submit(type: str, title: str, body: str, source_refs: list[str],
           idempotency_key: str, workstream_id: str | None = None, *,
           attribution: dict[str, str]) -> dict[str, Any]:
    if isinstance(title, str):
        title = title.strip()
    if isinstance(body, str):
        body = _normalise(body)
    error = _validate(type, title, body, source_refs, workstream_id, idempotency_key)
    if error:
        return {"success": False, "error": error}
    stamp = {key: str(attribution[key]) for key in
             ("authenticated_identity", "surface", "actor_class", "surface_source")}
    key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]
    record_id = f"shared-submit-{key_hash}"
    relative = f"inbox/distilled_packets/{record_id}.md"
    reference = f"business_brain:{relative}"
    fields = {"type": type, "title": title, "body": body,
              "source_refs": source_refs, "workstream_id": workstream_id}
    fingerprint = hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    target = brain_memory.VAULT_ROOT / relative
    if target.exists():
        existing, _ = brain_memory.parse_frontmatter(target.read_text(encoding="utf-8"))
        if existing.get("payload_fingerprint") != fingerprint:
            return {"success": False, "error": "idempotency key already belongs to another record"}
        commit = brain_memory._git("log", "-1", "--format=%H", "--", relative).stdout.strip()
        return {"success": True, "record_id": record_id, "reference": reference,
                "commit": commit, "sync_status": "synced" if not brain_memory._git("merge-base", "--is-ancestor", commit, "origin/main", check=False).returncode else "pending",
                "duplicate": True, "status": "unconfirmed", "attribution": existing.get("attribution")}
    document = "\n".join((
        "---", f"id: {record_id}", f"type: {type}", "status: unconfirmed",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        f"payload_fingerprint: {fingerprint}",
        f"source_refs: {json.dumps(source_refs, ensure_ascii=False)}",
        f"workstream_id: {json.dumps(workstream_id)}",
        f"attribution: {json.dumps(stamp, ensure_ascii=False, sort_keys=True)}",
        "---", f"# {title}", "", body, "",
    ))
    try:
        result = brain_memory.write_transaction(
            {relative: document}, source="shared-brain-submit", session_id=record_id,
            # The Brain ignores inbox/distilled_packets/*; a submit record is committed there by design.
            require_absent=True, attribution=stamp, force_add=True,
        )
    except brain_memory.BrainMemoryError as exc:
        if target.exists():
            return submit(type, title, body, source_refs, idempotency_key, workstream_id,
                          attribution=attribution)
        _log.warning("shared_brain submit write failed record=%s: %s", record_id, exc)
        # Git stderr can name the host vault path; never return it to a client.
        message = str(exc)
        if _host_path(message) or "/" in message or "\\" in message:
            message = "Brain write failed; nothing was stored"
        return {"success": False, "error": message}
    return {"success": True, "record_id": record_id, "reference": reference,
            "commit": result.commit, "sync_status": result.sync_status,
            "index_status": result.index_status,
            "duplicate": False, "status": "unconfirmed", "attribution": stamp}
