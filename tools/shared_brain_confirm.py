#!/usr/bin/env python3
"""Confirm one existing Shared Brain submit record: status unconfirmed -> confirmed.

The only operation is that one status change, written through `write_transaction()` so it is
committed, pushed and verified like every durable Brain write. No other field, record type,
correction, delete or identity change is possible here.

Usage: python3 tools/shared_brain_confirm.py shared-submit-<32 hex>

Revisit: when the Shared Brain review tier or confirmation contract changes. Last touched: 2026-10-04.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from typing import Any

try:
    from . import brain_memory
    from .shared_brain_checkpoint import _host_path
except ImportError:
    import brain_memory
    from shared_brain_checkpoint import _host_path

RECORD_ID_RE = re.compile(r"shared-submit-[0-9a-f]{32}\Z")
INTAKE_DIR = "inbox/distilled_packets"
SUBMIT_SOURCES = {"shared-brain-submit", "shared-brain-confirm"}
# The David -> Orchestration worker runs this as a local command, not over David's stdio server.
CLI_STAMP = {"authenticated_identity": "david", "surface": "david",
             "actor_class": "authorised_client", "surface_source": "local-cli"}
_log = logging.getLogger("shared_brain")


def _record_id(value: str) -> str | None:
    text = str(value or "").strip()
    for prefix in (f"business_brain:{INTAKE_DIR}/", f"{INTAKE_DIR}/"):
        if text.startswith(prefix) and text.endswith(".md"):
            text = text[len(prefix):-3]
    return text if RECORD_ID_RE.fullmatch(text) else None


def _fingerprint(fields: dict, rest: str) -> str | None:
    title = fields.get("title")
    heading = f"# {title}\n\n"
    if not isinstance(title, str) or not rest.startswith(heading) or not rest.endswith("\n"):
        return None
    payload = {"type": fields.get("type"), "title": title, "body": rest[len(heading):-1],
               "source_refs": fields.get("source_refs"), "workstream_id": fields.get("workstream_id")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _sync_status(commit: str) -> str:
    merged = brain_memory._git("merge-base", "--is-ancestor", commit, "origin/main", check=False)
    return "synced" if not merged.returncode else "pending"


def confirm(record: str, *, attribution: dict[str, str] | None = None, _retry: bool = True) -> dict[str, Any]:
    record_id = _record_id(record)
    if record_id is None:
        return {"success": False, "error": "record must be a Shared Brain submit record ID (shared-submit-<32 hex>)"}
    relative = f"{INTAKE_DIR}/{record_id}.md"
    reference = f"business_brain:{relative}"
    target = brain_memory.VAULT_ROOT / relative
    if not target.is_file():
        return {"success": False, "error": "no Shared Brain submit record has this ID"}
    committed = brain_memory._git("show", f"HEAD:{relative}", check=False)
    if committed.returncode:
        return {"success": False, "error": "record is not committed in the Brain; nothing was changed"}
    raw = target.read_bytes()
    if raw != committed.stdout.encode("utf-8"):
        return {"success": False, "error": "record has uncommitted changes; restore it before confirming"}
    text = raw.decode("utf-8")
    try:
        fields, rest = brain_memory.parse_frontmatter(text)
    except brain_memory.BrainMemoryError:
        return {"success": False, "error": "record frontmatter is invalid; nothing was changed"}
    provenance = fields.get(brain_memory.PROVENANCE_KEY) or {}
    if (fields.get("id") != record_id or not isinstance(provenance, dict)
            or provenance.get("source") not in SUBMIT_SOURCES or not fields.get("attribution")):
        return {"success": False, "error": "record is not a Shared Brain submit record"}
    if _fingerprint(fields, rest) != fields.get("payload_fingerprint"):
        return {"success": False, "error": "record content does not match its submitted fingerprint"}
    status = fields.get("status")
    if status == "confirmed":
        commit = brain_memory._git("log", "-1", "--format=%H", "--", relative).stdout.strip()
        return {"success": True, "record_id": record_id, "reference": reference,
                "status": "confirmed", "previous_status": "confirmed", "already_confirmed": True,
                "commit": commit, "sync_status": _sync_status(commit)}
    if status != "unconfirmed":
        return {"success": False, "error": "only an unconfirmed record can be confirmed"}

    head, separator, tail = text.partition("\n---\n")
    head, replaced = re.subn(r"^status: unconfirmed$", "status: confirmed", head, flags=re.MULTILINE)
    if replaced != 1:
        return {"success": False, "error": "record status line is not in the submitted form"}
    stamp = dict(attribution or CLI_STAMP)
    try:
        result = brain_memory.write_transaction(
            {relative: head + separator + tail}, source="shared-brain-confirm",
            session_id=f"{record_id}-confirm",
            expected_hashes={relative: brain_memory.sha256_bytes(raw)},
            # Submit records live in the Brain-ignored intake directory by design.
            attribution=stamp, force_add=True,
        )
    except brain_memory.ConcurrentEditError:
        if _retry:
            return confirm(record_id, attribution=attribution, _retry=False)
        return {"success": False, "error": "record changed during confirmation; nothing was changed"}
    except brain_memory.BrainMemoryError as exc:
        _log.warning("shared_brain confirm write failed record=%s: %s", record_id, exc)
        message = str(exc)
        if _host_path(message) or "/" in message or "\\" in message:
            message = "Brain write failed; nothing was changed"
        return {"success": False, "error": message}
    return {"success": True, "record_id": record_id, "reference": reference,
            "status": "confirmed", "previous_status": "unconfirmed", "already_confirmed": False,
            "commit": result.commit, "sync_status": result.sync_status,
            "index_status": result.index_status, "confirmed_by": stamp}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(json.dumps({"success": False, "error": "usage: shared_brain_confirm.py shared-submit-<32 hex>"}))
        return 2
    result = confirm(args[0])
    print(json.dumps(result, sort_keys=True))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
