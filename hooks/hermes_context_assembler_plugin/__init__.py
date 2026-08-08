"""Hermes-native registration for the repository Context Assembler.

Revisit: when Hermes changes PluginContext or pre/post LLM hook kwargs. · Last touched: 2026-08-05.
"""

from __future__ import annotations

import os
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("AOS_ROOT", "/home/liam/agentic-os-live")).resolve()
HOOK = ROOT / "hooks" / "context_assembler_hook.py"


def _payload(event: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    return {
        "hook_event_name": event,
        "native_plugin": True,
        "session_id": str(kwargs.get("session_id") or ""),
        "extra": {
            "assistant_response": str(kwargs.get("assistant_response") or ""),
            "platform": str(kwargs.get("platform") or "hermes"),
            "turn_id": str(kwargs.get("turn_id") or ""),
            "user_message": str(kwargs.get("user_message") or ""),
        },
    }


def _invoke(event: str, kwargs: dict[str, Any]) -> dict:
    result = subprocess.run(
        [str(HOOK)],
        input=json.dumps(_payload(event, kwargs), ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
        cwd=ROOT,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("TTROS Context Assembler hook returned invalid JSON") from exc
    if result.returncode != 0 or not isinstance(payload, dict) or payload.get("error"):
        raise RuntimeError("TTROS Context Assembler hook failed")
    return payload


def _pre_llm_call(**kwargs: Any) -> dict:
    return _invoke("pre_llm_call", kwargs)


def _post_llm_call(**kwargs: Any) -> dict:
    return _invoke("post_llm_call", kwargs)


def register(ctx: Any) -> None:
    """Register through Hermes' supported general-plugin lifecycle contract."""
    ctx.register_hook("pre_llm_call", _pre_llm_call)
    ctx.register_hook("post_llm_call", _post_llm_call)
    # Existing shell-hook declarations stay as a fallback for a process where
    # this plugin did not load. Hermes registers Python callbacks first, so a
    # successfully loaded plugin can suppress duplicate subprocess assembly.
    os.environ["TTROS_NATIVE_CONTEXT_PLUGIN_REGISTERED"] = "1"
