"""Fail-open Latitude telemetry helper for the Agentic OS dashboard backend."""

from __future__ import annotations

import datetime
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


SECRET_ENV_VARS = ("LATITUDE_API_KEY",)
PROJECT_ENV_VARS = ("LATITUDE_PROJECT_SLUG", "LATITUDE_PROJECT", "LATITUDE_PROJECT_ID")
REQUIRED_ENV_VARS = (*SECRET_ENV_VARS, "LATITUDE_PROJECT_SLUG_OR_ID", "LATITUDE_ENDPOINT")
OPTIONAL_ENV_VARS = ("LATITUDE_WORKSPACE_URL",)
STATE_FILE = Path(__file__).resolve().parents[1] / "data" / "latitude_state.json"


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _env_path() -> Path:
    return Path(__file__).with_name(".env")


def _read_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = _env_path().read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return values
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().upper()] = value.strip().strip("'\"")
    return values


def _env_values() -> dict[str, str]:
    values = _read_env_file()
    for key in (*SECRET_ENV_VARS, *PROJECT_ENV_VARS, "LATITUDE_ENDPOINT", *OPTIONAL_ENV_VARS):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def _state() -> dict[str, Any]:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(data: dict[str, Any]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        return


def config_status() -> dict[str, Any]:
    values = _env_values()
    present = []
    missing = []
    if values.get("LATITUDE_API_KEY"):
        present.append("LATITUDE_API_KEY")
    else:
        missing.append("LATITUDE_API_KEY")
    project_key = (
        "LATITUDE_PROJECT_SLUG"
        if values.get("LATITUDE_PROJECT_SLUG")
        else ("LATITUDE_PROJECT" if values.get("LATITUDE_PROJECT") else ("LATITUDE_PROJECT_ID" if values.get("LATITUDE_PROJECT_ID") else ""))
    )
    if project_key:
        present.append(project_key)
    else:
        missing.append("LATITUDE_PROJECT_SLUG_OR_ID")
    if values.get("LATITUDE_ENDPOINT"):
        present.append("LATITUDE_ENDPOINT")
    else:
        missing.append("LATITUDE_ENDPOINT")
    state = _state()
    configured = not missing
    degraded_reason = None if configured else "Latitude is not configured; missing " + ", ".join(missing) + "."
    connected: bool | str = bool(state.get("last_heartbeat_accepted")) if configured else "unknown"
    return {
        "configured": configured,
        "connected": connected,
        "degraded_reason": degraded_reason,
        "workspace_url_present": bool(values.get("LATITUDE_WORKSPACE_URL")),
        "workspace_url": values.get("LATITUDE_WORKSPACE_URL") or "",
        "required_env_vars_present": present,
        "required_env_vars_missing": missing,
        "last_heartbeat_ts": state.get("last_heartbeat_ts"),
    }


def _private_config() -> dict[str, str]:
    values = _env_values()
    return {
        "api_key": values.get("LATITUDE_API_KEY", ""),
        "project": values.get("LATITUDE_PROJECT_SLUG") or values.get("LATITUDE_PROJECT") or values.get("LATITUDE_PROJECT_ID", ""),
        "project_kind": "id" if values.get("LATITUDE_PROJECT_ID") and not (values.get("LATITUDE_PROJECT_SLUG") or values.get("LATITUDE_PROJECT")) else "slug",
        "endpoint": values.get("LATITUDE_ENDPOINT", ""),
    }


def event_payload(event_type: str, component: str, status: str = "ok", **attrs: Any) -> dict[str, Any]:
    safe_attrs = {
        key: value
        for key, value in attrs.items()
        if value is not None and key.lower() not in {"api_key", "token", "authorization", "secret", "project_id"}
    }
    return {
        "event_type": event_type,
        "component": component,
        "status": status,
        "timestamp": utc_now_iso(),
        "service": "agentic-os-dashboard-backend",
        "telemetry": "latitude",
        **safe_attrs,
    }


def send_event(event: dict[str, Any]) -> dict[str, Any]:
    status = config_status()
    if not status["configured"]:
        return {"sent": False, "degraded": True, **status}

    config = _private_config()
    body = json.dumps(event, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        config["endpoint"],
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        },
        method="POST",
    )
    if config["project_kind"] == "slug":
        request.add_header("X-Project-Slug", config["project"])
    else:
        request.add_header("X-Project-Id", config["project"])
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            accepted = 200 <= response.status < 300
            if accepted and event.get("event_type") == "backend.heartbeat":
                _write_state({
                    "last_heartbeat_ts": event.get("timestamp"),
                    "last_heartbeat_accepted": True,
                    "last_status_code": response.status,
                })
            return {
                "sent": accepted,
                "degraded": not accepted,
                "status_code": response.status,
                "last_heartbeat_ts": event.get("timestamp") if event.get("event_type") == "backend.heartbeat" and accepted else status.get("last_heartbeat_ts"),
            }
    except urllib.error.HTTPError as exc:
        return {"sent": False, "degraded": True, "degraded_reason": f"Latitude HTTP {exc.code}", **status}
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        return {"sent": False, "degraded": True, "degraded_reason": f"Latitude unreachable: {type(exc).__name__}", **status}


def trace(event_type: str, component: str, status: str = "ok", **attrs: Any) -> dict[str, Any]:
    return send_event(event_payload(event_type, component, status, **attrs))


def heartbeat() -> dict[str, Any]:
    event = event_payload("backend.heartbeat", "dashboard_backend", "ok", token_usage_basis="no_agent_invocation")
    result = send_event(event)
    current = config_status()
    if not current["configured"]:
        return {"success": False, "sent": False, "event_sending": "degraded", **current}
    return {
        "success": bool(result.get("sent")),
        "sent": bool(result.get("sent")),
        "event_sending": "sent" if result.get("sent") else "degraded",
        **config_status(),
        "degraded_reason": result.get("degraded_reason") or config_status().get("degraded_reason"),
    }
