#!/usr/bin/env python3
"""Hermes native pre-tool guard for Agentic OS protected boundaries.

The script implements the existing hook contracts at Hermes' real
``pre_tool_call`` lifecycle.  It receives one JSON payload on stdin and may
block the call before execution.  Exact external-action authorization remains
owned by ``connectors/composio_access_adapter.py``.

Revisit: on a new connector, protected path, or Hermes hook payload change. · Last touched: 2026-07-31.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any


PROTECTED_PATH_PATTERNS = (
    r"(?:^|/)workspaces/north_shore_sales_coach(?:/|$)",
    r"(?:^|/)connectors/telegram_bridge(?:/|$)",
    r"(?:^|/)dashboard/(?:backend|frontend)(?:/|$)",
    r"(?:^|/)queue/(?:command_routes|model_routes|lane_profiles)\.json$",
    r"(?:^|/)(?:old[_ -]?(?:ubuntu|hermes|vault|runtime)|legacy_harvest|zpc)(?:/|$)",
)
SECRET_PATH_RE = re.compile(
    r"(?:^|/)(?:\.env(?:\.[^/]*)?|auth(?:entication)?(?:\.[^/]*)?|credentials?(?:\.[^/]*)?|secrets?(?:\.[^/]*)?|tokens?(?:\.[^/]*)?)(?:$|/)",
    re.IGNORECASE,
)
SECRET_VALUE_RES = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}", re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret)\s*[:=]\s*['\"]?[A-Za-z0-9._~+/-]{12,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
)
WRITE_TOOL_RE = re.compile(r"(?:write|patch|edit|delete|remove|move|rename|create_file|apply_patch)", re.IGNORECASE)
TERMINAL_MUTATION_RE = re.compile(
    r"(?:^|[;&|]\s*|\s)(?:rm|mv|cp|install|truncate|chmod|chown|ln|mkdir|touch)\s|"
    r"(?:sed|perl)\s+[^\n]*(?:-i|--in-place)|(?:^|\s)(?:tee|dd)\s|>\s*[^&]",
    re.IGNORECASE,
)
EXTERNAL_ACTION_RE = re.compile(
    r"\b(?:GMAIL|LINKEDIN|GITHUB|GOOGLECALENDAR|GOOGLEDRIVE|GOOGLEDOCS|GOOGLESHEETS|INSTAGRAM|FACEBOOK|WHATSAPP|APOLLO|AGENT_MAIL)_[A-Z0-9_]*(?:SEND|CREATE|UPDATE|DELETE|MODIFY|ADD|FORWARD|POST|PUBLISH|UPLOAD)[A-Z0-9_]*\b"
)
DIRECT_SEND_RE = re.compile(r"\bhermes\s+send\b|\b(?:send|post|publish)\s+(?:email|message|dm|linkedin)\b", re.IGNORECASE)
SAFE_ADAPTER_CALL_RE = re.compile(
    r"^\s*(?:(?:\S*python(?:3(?:\.\d+)?)?)\s+)?"
    r"(?:\S*/)?connectors/(?:composio_access_adapter|gmail_draft_adapter)\.py(?:\s|$)",
    re.IGNORECASE,
)


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _strings(child)


def _block(message: str) -> dict[str, str]:
    return {"action": "block", "message": message}


def evaluate(payload: dict[str, Any]) -> dict[str, str]:
    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    values = list(_strings(tool_input))
    combined = "\n".join(values)
    normalized = combined.replace("\\", "/")

    normalized_values = [value.replace("\\", "/") for value in values]
    if any(SECRET_PATH_RE.search(value) for value in normalized_values):
        return _block("secret-exposure hook blocked access to credential-shaped runtime state")
    if any(pattern.search(combined) for pattern in SECRET_VALUE_RES):
        return _block("secret-exposure hook blocked credential-shaped content before tool execution")

    is_terminal = tool_name.lower() in {"terminal", "exec", "shell", "bash"} or "terminal" in tool_name.lower()
    mutating = bool(WRITE_TOOL_RE.search(tool_name)) or (is_terminal and bool(TERMINAL_MUTATION_RE.search(combined)))
    if mutating and any(
        re.search(pattern, value, re.IGNORECASE)
        for pattern in PROTECTED_PATH_PATTERNS
        for value in normalized_values
    ):
        return _block("protected-path hook blocked a write to an Agentic OS protected category")

    direct_external = bool(EXTERNAL_ACTION_RE.search(combined) or EXTERNAL_ACTION_RE.search(tool_name.upper()) or DIRECT_SEND_RE.search(combined))
    command = str(tool_input.get("command") or tool_input.get("cmd") or "").replace("\\", "/")
    safe_adapter = bool(
        is_terminal
        and SAFE_ADAPTER_CALL_RE.search(command)
        and not any(separator in command for separator in (";", "&&", "||", "\n"))
    )
    if direct_external and not safe_adapter:
        return _block("pre-external-action/pre-publish hook blocked a direct connector mutation; use the governed adapter and exact queue-item approval")

    client_scopes = set(re.findall(r"\bclient:[a-z0-9][a-z0-9_-]*\b", combined, re.IGNORECASE))
    if len({value.casefold() for value in client_scopes}) > 1:
        return _block("client-isolation hook blocked a tool call spanning multiple client scopes")
    return {}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        print(json.dumps(_block("runtime guard received an invalid Hermes hook payload")))
        return 0
    print(json.dumps(evaluate(payload if isinstance(payload, dict) else {})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
