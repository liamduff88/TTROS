#!/usr/bin/env python3
"""Hermes lifecycle hook for mandatory One Brain context and session journals.

`pre_llm_call` returns the assembled context. `post_llm_call` records completed
executive turns in the vault with an atomic audited transaction.

Revisit: when Hermes native plugin payloads or sticky-session identity changes. · Last touched: 2026-08-05.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


ROOT = Path("/home/liam/agentic-os-live")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.brain_memory import append_session_turn
from tools.context_assembler import MARKER, assemble
from tools.step6_cost_control import Scope, preflight


STICKY_RE = re.compile(r"(?m)^TTROS sticky session key:\s*([a-f0-9]{12,64})\s*$")
AOS_PROFILES = {"operator-lean", "aos-orchestrator", "aos-revenue", "aos-marketing", "aos-delivery", "aos-ops"}
BRAIN_CONTEXT_PROFILES = {*AOS_PROFILES, "david"}


def _profile() -> str:
    home = Path(os.environ.get("HERMES_HOME", ""))
    return home.name if home.parent.name == "profiles" else ""


def _sticky_key(message: str, session_id: str) -> str:
    match = STICKY_RE.search(str(message or ""))
    return match.group(1) if match else session_id


def evaluate(payload: dict) -> dict:
    if (
        os.environ.get("TTROS_NATIVE_CONTEXT_PLUGIN_REGISTERED") == "1"
        and not payload.get("native_plugin")
    ):
        return {}
    event = str(payload.get("hook_event_name") or "")
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    session_id = str(payload.get("session_id") or "")
    platform = str(extra.get("platform") or "hermes")
    surface = f"hermes:{platform}"
    message = str(extra.get("user_message") or "")
    profile = _profile()
    if profile not in BRAIN_CONTEXT_PROFILES:
        return {}
    sticky = _sticky_key(message, session_id)

    if event == "pre_llm_call":
        if profile in AOS_PROFILES and os.environ.get("AOS_STEP6_WRAPPED") != "1":
            raise RuntimeError("Step 6 protected model runner requires the canonical accounting/fuse wrapper")
        if profile in AOS_PROFILES:
            scope_type = os.environ.get("AOS_STEP6_SCOPE_TYPE", "")
            scope_id = os.environ.get("AOS_STEP6_SCOPE_ID", "")
            preflight(Scope(scope_type, scope_id), root=ROOT)
        context = assemble(
            message,
            surface=surface,
            session_id=session_id,
            session_key=sticky,
            invocation_id=f"hermes-{session_id or 'session'}-{str(extra.get('turn_id') or 'turn')}",
        )
        return {"context": context.render(include_request=False)}

    if event == "post_llm_call":
        response = str(extra.get("assistant_response") or "")
        read_only_consultation = os.environ.get("AOS_OPERATOR_CONSULTATION") == "1"
        if response and not read_only_consultation and (profile == "operator-lean" or STICKY_RE.search(message)):
            append_session_turn(
                surface=surface,
                session_key=sticky,
                session_id=session_id or "hermes-turn",
                user_message=message,
                assistant_response=response,
                token_usage="unavailable from current Hermes post_llm_call payload",
                source=f"session {session_id or 'unknown'}",
            )
        return {}
    return {}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be an object")
        result = evaluate(payload)
    except Exception as exc:
        # The scoped Hermes runtime has a matching fail-closed marker check;
        # returning no marker prevents a model call instead of degrading.
        print(json.dumps({"error": f"context assembly failed: {type(exc).__name__}"}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
