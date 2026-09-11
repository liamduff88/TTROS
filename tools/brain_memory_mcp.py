#!/usr/bin/env python3
"""Scoped Hermes tools for ordinary One Brain learning and corrections.

Formal commitments and destructive/sensitive records are intentionally outside
this tool. Those remain explicit Liam-confirmation paths.

Revisit: when Hermes cognition boundaries or canonical note placement changes. · Last touched: 2026-08-04.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

try:
    from brain_memory import (
        BrainMemoryError,
        HISTORICAL_CALLS_DIR,
        VAULT_ROOT,
        read_vault_note,
        resolve_ordinary_knowledge_pointer,
        update_note_section,
    )
except ModuleNotFoundError:
    from tools.brain_memory import (
        BrainMemoryError,
        HISTORICAL_CALLS_DIR,
        VAULT_ROOT,
        read_vault_note,
        resolve_ordinary_knowledge_pointer,
        update_note_section,
    )

try:
    import aos_indexer
except ModuleNotFoundError:
    from tools import aos_indexer


mcp = MCPServer("brain")

# The Step 6 depth tools below (search_calls/open_call/open_note/search_history)
# are read-only Business Brain retrieval added on top of this server's original
# two tools. Every Hermes profile's config.yaml points its "brain" MCP server at
# this same shared script, so an unconditional @mcp.tool() here is visible to
# every one of them -- including operator-lean, a separate, fail-closed,
# safety-bounded surface whose exact tool contract (operator_lean_oneshot.py::
# EXPECTED_TOOLS) does not include them. Registration is gated behind this
# explicit opt-in so only a profile whose config.yaml sets
# mcp_servers.brain.env.AOS_BRAIN_DEPTH_TOOLS gains the depth tools; every other
# client keeps the original two-tool surface unchanged.
DEPTH_TOOLS_ENABLED = os.environ.get("AOS_BRAIN_DEPTH_TOOLS", "").strip().lower() in {"1", "true", "yes"}

KnowledgeState = Literal["verified_fact", "interpretation", "hypothesis", "uncertainty", "operator_correction"]
COMMITMENT_RE = re.compile(
    r"\b(?:price|pricing|contract|legally|legal conclusion|financial conclusion|"
    r"we commit|client commitment|send|publish|delete|supersede|authority)\b",
    re.IGNORECASE,
)
CALL_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}")
MAX_NOTE_CHARS = 60_000
MAX_SEARCH_RESULTS = 20
# Kept well under Hermes's own 50,000-char MCP tool-result spill threshold
# (tools/budget_config.py::DEFAULT_MCP_RESULT_SIZE_CHARS), including JSON-wrapper
# and escaping overhead, so a passage never itself triggers a spill.
PASSAGE_MAX_CHARS = 12_000
PASSAGE_CONTEXT_LINES = 2
_QUERY_TERM_RE = re.compile(r"[a-z0-9']+")


def _truncate(text: str, limit: int = MAX_NOTE_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _bounded_passage(text: str, query: str) -> str | None:
    """Return a small excerpt of `text` built from the lines that best match
    `query`'s terms (plus a couple of lines of surrounding context), or None
    if no line matches any term. Bounded by PASSAGE_MAX_CHARS regardless of
    the source note's size -- the point is on-demand reading of the actual
    words, not a full-document dump."""
    terms = list(dict.fromkeys(t for t in _QUERY_TERM_RE.findall(query.lower()) if len(t) > 2))
    if not terms:
        return None
    lines = text.splitlines()
    lower_lines = [line.lower() for line in lines]
    # Down-weight terms by how common they are in THIS note (a plain
    # inverse-document-frequency-style weight, computed fresh per call) --
    # a query word repeated in a speaker label or filler phrase throughout
    # the transcript (e.g. a participant's own name) must not drown out a
    # rare word that actually pinpoints the answer. A term absent from the
    # note contributes nothing (and never raises).
    term_totals = {term: sum(line.count(term) for line in lower_lines) for term in terms}
    weights = {term: (1.0 / count) if count else 0.0 for term, count in term_totals.items()}
    scored = [
        (sum(line.count(term) * weights[term] for term in terms), idx)
        for idx, line in enumerate(lower_lines)
    ]
    scored = [(score, idx) for score, idx in scored if score > 0]
    if not scored:
        return None
    scored.sort(key=lambda pair: (-pair[0], pair[1]))

    included: set[int] = set()
    total = 0
    for _score, idx in scored:
        lo = max(0, idx - PASSAGE_CONTEXT_LINES)
        hi = min(len(lines), idx + PASSAGE_CONTEXT_LINES + 1)
        block_new = [j for j in range(lo, hi) if j not in included]
        if not block_new:
            continue
        block_chars = sum(len(lines[j]) + 1 for j in block_new)
        if included and total + block_chars > PASSAGE_MAX_CHARS:
            continue
        included.update(block_new)
        total += block_chars
        if total >= PASSAGE_MAX_CHARS:
            break

    ordered = sorted(included)
    parts: list[str] = []
    run: list[int] = []
    for j in ordered:
        if run and j != run[-1] + 1:
            parts.append("\n".join(lines[k] for k in run))
            run = []
        run.append(j)
    if run:
        parts.append("\n".join(lines[k] for k in run))
    return "\n\n[...]\n\n".join(parts)


def _vault_search(query: str, *, limit: int) -> list[dict[str, Any]]:
    result = aos_indexer.search(query, source="business_brain", limit=limit, client_scope="global")
    return [row for group in result.get("groups", {}).values() for row in group]


@mcp.tool()
def remember_brain_knowledge(
    pointer: str,
    section_id: str,
    statement: str,
    knowledge_state: KnowledgeState,
    source: str,
    session_id: str,
) -> dict[str, Any]:
    """Persist an ordinary fact, interpretation, hypothesis, uncertainty, or explicit operator correction directly in its canonical Brain note.

    This is ungated cognition. Do not use it for pricing, contracts, formal
    legal/financial conclusions, client commitments, authority changes,
    destructive deletion/supersession, or any external action.
    """
    body = str(statement or "").strip()
    try:
        relative = resolve_ordinary_knowledge_pointer(pointer)
    except BrainMemoryError:
        return {"success": False, "error": "pointer is outside ordinary Hermes knowledge placement"}
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", str(section_id or "")):
        return {"success": False, "error": "section_id must be a safe lowercase slug"}
    if not body or len(body.encode("utf-8")) > 8_000:
        return {"success": False, "error": "statement must contain 1-8,000 UTF-8 bytes"}
    if COMMITMENT_RE.search(body):
        return {"success": False, "error": "formal commitment or consequential-action language requires Liam's explicit confirmation path"}
    if not str(source or "").strip() or not str(session_id or "").strip():
        return {"success": False, "error": "source and session_id provenance are required"}
    title = knowledge_state.replace("_", " ").title()
    result = update_note_section(
        relative,
        section_id=str(section_id),
        title=title,
        content=f"Knowledge state: `{knowledge_state}`\n\n{body}",
        source=str(source),
        session_id=str(session_id),
    )
    return {
        "success": True,
        "done": True,
        "pointer": f"business_brain:{relative}",
        "knowledge_state": knowledge_state,
        "classification": "eligible_ordinary_organisational_knowledge",
        "review_required": False,
        "promotion_boundary": "formal commitments and consequential classes remain outside this ungated writer",
        "commit": result.commit,
        "changed_paths": list(result.changed_paths),
        "external_action": False,
        "note": "Durable Brain update complete; do not repeat it.",
    }


def search_calls(query: str, limit: int = 5) -> dict[str, Any]:
    """Search historical call/meeting transcripts (sources/historical_calls/)
    by keyword or participant name, via the existing repo-wide FTS index.
    Read-only. These records are historical evidence, never canonical TTROS
    truth. Use open_call with a returned call_id to read a full transcript.
    """
    q = str(query or "").strip()
    if not q:
        return {"success": False, "error": "query must be non-empty"}
    n = max(1, min(int(limit), MAX_SEARCH_RESULTS))
    try:
        rows = _vault_search(q, limit=50)
    except Exception as exc:
        return {"success": False, "error": f"search failed: {exc}"}
    prefix = f"business_brain:{HISTORICAL_CALLS_DIR}/"
    matches = [row for row in rows if str(row.get("path", "")).startswith(prefix)][:n]
    return {
        "success": True,
        "query": q,
        "matches": [
            {
                "call_id": Path(m["path"]).stem,
                "pointer": m["path"],
                "title": m.get("title"),
                "modified": m.get("modified"),
                "snippet": m.get("snippet"),
            }
            for m in matches
        ],
        "canonical_truth": False,
        "note": "No speaker's statement in these records is canonical TTROS truth.",
    }


def open_call(call_id: str) -> dict[str, Any]:
    """Open one full historical call/meeting transcript by id (its filename
    stem, e.g. 'mike-knapp-july-21' -- get ids from search_calls). Read-only,
    direct vault read. Historical evidence, never canonical TTROS truth.
    """
    slug = str(call_id or "").strip()
    slug = slug.removeprefix("business_brain:").removeprefix(f"{HISTORICAL_CALLS_DIR}/")
    if slug.endswith(".md"):
        slug = slug[:-3]
    if not CALL_ID_RE.fullmatch(slug):
        return {"success": False, "error": "call_id must be a safe lowercase slug"}
    try:
        relative, text = read_vault_note(f"{HISTORICAL_CALLS_DIR}/{slug}.md")
    except BrainMemoryError as exc:
        return {"success": False, "error": str(exc)}
    body, truncated = _truncate(text)
    return {
        "success": True,
        "pointer": f"business_brain:{relative}",
        "content": body,
        "truncated": truncated,
        "canonical_truth": False,
    }


def open_note(pointer: str, query: str = "") -> dict[str, Any]:
    """Open any canonical Business Brain note by its vault-relative path
    (e.g. 'operating_context/open_loops.md'), including notes outside the
    working canonical map, and including a raw intake source record under
    'sources/intake/records/' -- accepts the pointer exactly as its source
    card renders it (extension optional; with or without a 'business_brain:'
    prefix). Intake records can be large: pass `query` (a few keywords) to
    get back a small bounded passage containing those words instead of the
    full note -- use this whenever a card's summary doesn't carry the exact
    words you need. Read-only, direct vault read -- no gated transaction, no
    write.
    """
    raw = str(pointer or "").strip().removeprefix("business_brain:")
    if raw and "." not in Path(raw).name:
        raw = f"{raw}.md"
    try:
        relative, text = read_vault_note(raw)
    except BrainMemoryError as exc:
        return {"success": False, "error": str(exc)}
    q = str(query or "").strip()
    if q:
        passage = _bounded_passage(text, q)
        if passage is None:
            return {
                "success": True,
                "pointer": f"business_brain:{relative}",
                "content": "",
                "truncated": False,
                "query": q,
                "matched": False,
                "note": "no passage in this note matched the query terms",
            }
        return {
            "success": True,
            "pointer": f"business_brain:{relative}",
            "content": passage,
            "truncated": len(passage) < len(text),
            "query": q,
            "matched": True,
        }
    body, truncated = _truncate(text)
    return {
        "success": True,
        "pointer": f"business_brain:{relative}",
        "content": body,
        "truncated": truncated,
    }


def search_history(query: str, limit: int = 8) -> dict[str, Any]:
    """Full-text search across the whole Business Brain vault (not just
    historical calls), via the existing repo-wide FTS index. Use open_note
    with a returned pointer to read a full match. Read-only.
    """
    q = str(query or "").strip()
    if not q:
        return {"success": False, "error": "query must be non-empty"}
    n = max(1, min(int(limit), MAX_SEARCH_RESULTS))
    try:
        rows = _vault_search(q, limit=n)
    except Exception as exc:
        return {"success": False, "error": f"search failed: {exc}"}
    return {
        "success": True,
        "query": q,
        "matches": [
            {"pointer": m["path"], "title": m.get("title"), "modified": m.get("modified"), "snippet": m.get("snippet")}
            for m in rows[:n]
        ],
    }


@mcp.tool()
def brain_memory_status() -> dict[str, Any]:
    """Return the non-secret One Brain authority and required note availability."""
    required = (
        "memory/company.md",
        "operating_context/current_priorities.md",
        "operating_context/executive_view.md",
        "operating_context/open_loops.md",
        "inbox/contradictions.md",
    )
    return {
        "authority": str(VAULT_ROOT),
        "native_profile_memory_authority": False,
        "required_notes": {relative: (VAULT_ROOT / relative).is_file() for relative in required},
        "automatic_push": False,
    }


if DEPTH_TOOLS_ENABLED:
    mcp.tool()(search_calls)
    mcp.tool()(open_call)
    mcp.tool()(open_note)
    mcp.tool()(search_history)


if __name__ == "__main__":
    mcp.run(transport="stdio")
