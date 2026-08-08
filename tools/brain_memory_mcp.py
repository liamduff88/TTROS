#!/usr/bin/env python3
"""Scoped Hermes tools for ordinary One Brain learning and corrections.

Formal commitments and destructive/sensitive records are intentionally outside
this tool. Those remain explicit Liam-confirmation paths.

Revisit: when Hermes cognition boundaries or canonical note placement changes. · Last touched: 2026-08-04.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

try:
    from brain_memory import BrainMemoryError, VAULT_ROOT, resolve_ordinary_knowledge_pointer, update_note_section
except ModuleNotFoundError:
    from tools.brain_memory import BrainMemoryError, VAULT_ROOT, resolve_ordinary_knowledge_pointer, update_note_section


mcp = FastMCP("brain")
KnowledgeState = Literal["verified_fact", "interpretation", "hypothesis", "uncertainty", "operator_correction"]
COMMITMENT_RE = re.compile(
    r"\b(?:price|pricing|contract|legally|legal conclusion|financial conclusion|"
    r"we commit|client commitment|send|publish|delete|supersede|authority)\b",
    re.IGNORECASE,
)


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


if __name__ == "__main__":
    mcp.run(transport="stdio")
