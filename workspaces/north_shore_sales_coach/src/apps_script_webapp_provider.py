"""Google Apps Script Web App bridge for North Shore Sheets writes.

This provider is optional and fail-closed. It prepares approved append payloads
for a Sheet-bound Apps Script Web App and only posts through an injected HTTP
client after all local execution gates are explicitly open.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence
from uuid import uuid4

from . import sheets_adapter


PROVIDER_APPS_SCRIPT_WEBAPP = "apps_script_webapp"
STATUS_ACTION = "status"
APPEND_RAW_LOG_ACTION = "append_raw_log"
APPEND_OBJECTS_ACTION = "append_objects"
ALLOWED_ACTIONS = (STATUS_ACTION, APPEND_RAW_LOG_ACTION, APPEND_OBJECTS_ACTION)
ALLOWED_TABS = (
    "Raw_Logs",
    "Users",
    "Salespeople",
    "Daily_Team_Summary",
    "Daily_Salesperson_Scorecard",
    "Followups",
    "Missing_Data",
    "Coaching_Flags",
    "Report_Archive",
    "QA_Checks",
)


class AppsScriptWebAppProviderError(RuntimeError):
    """Apps Script bridge is unavailable, misconfigured, or denied locally."""


class AppsScriptHttpClient(Protocol):
    """Minimal fakeable HTTP client boundary."""

    def post(
        self,
        url: str,
        *,
        json: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Any:
        """Send a POST request. Production wiring must provide this explicitly."""


@dataclass(frozen=True)
class AppsScriptWebAppConfig:
    provider: str = "none"
    webapp_url_present: bool = False
    webapp_url_https: bool = False
    secret_present: bool = False
    secret_required: bool = True
    execution_enabled: bool = False
    reads_enabled: bool = False
    writes_enabled: bool = False


@dataclass(frozen=True)
class AppsScriptPostPayload:
    url: str
    headers: Mapping[str, str]
    body: Mapping[str, Any]
    timeout: float = 10.0


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_https_url(value: str) -> bool:
    return value.lower().startswith("https://") and len(value) > len("https://")


def load_config(
    config: Mapping[str, Any] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> AppsScriptWebAppConfig:
    """Load non-secret readiness state from config and environment."""
    data = dict(config or {})
    env = environ if environ is not None else os.environ
    provider = _text(env.get("NORTH_SHORE_SHEETS_PROVIDER")) or _text(data.get("provider")) or "none"
    webapp_url = _text(env.get("NORTH_SHORE_SHEETS_WEBAPP_URL")) or _text(data.get("webapp_url"))
    secret = _text(env.get("NORTH_SHORE_SHEETS_WEBAPP_SECRET")) or _text(data.get("webapp_secret"))
    return AppsScriptWebAppConfig(
        provider=provider,
        webapp_url_present=bool(webapp_url),
        webapp_url_https=_is_https_url(webapp_url),
        secret_present=bool(secret),
        secret_required=data.get("webapp_secret_required") is not False,
        execution_enabled=_truthy(data.get("execution_enabled"))
        or _truthy(env.get("NORTH_SHORE_SHEETS_EXECUTION_ENABLED")),
        reads_enabled=_truthy(data.get("reads_enabled"))
        or _truthy(env.get("NORTH_SHORE_SHEETS_READS_ENABLED")),
        writes_enabled=_truthy(data.get("writes_enabled"))
        or _truthy(env.get("NORTH_SHORE_SHEETS_WRITES_ENABLED")),
    )


def validate_action_tab(action: str, target_tab: str) -> None:
    """Reject anything outside the North Shore bridge allowlist."""
    if action not in ALLOWED_ACTIONS:
        raise AppsScriptWebAppProviderError("Apps Script action is not allowed")
    if action == STATUS_ACTION:
        return
    if target_tab not in ALLOWED_TABS:
        raise AppsScriptWebAppProviderError("Apps Script target tab is not allowed")


def _request_rows(request: sheets_adapter.SheetWriteRequest) -> tuple[tuple[Any, ...], ...]:
    return tuple(tuple(row) for row in request.rows)


def _request_objects(request: sheets_adapter.SheetWriteRequest) -> tuple[dict[str, Any], ...]:
    return tuple(dict(zip(request.headers, row, strict=True)) for row in request.rows)


def _headers(secret: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-North-Shore-Sheets-Secret"] = secret
    return headers


def _with_optional_secret(body: dict[str, Any], secret: str) -> dict[str, Any]:
    if secret:
        body["_shared_secret"] = secret
    return body


def build_status_payload(
    *,
    webapp_url: str,
    secret: str = "",
    request_id: str | None = None,
    timestamp: str | None = None,
    timeout: float = 10.0,
) -> AppsScriptPostPayload:
    """Create the status-check Web App POST shape without network I/O."""
    webapp_url = _text(webapp_url)
    secret = _text(secret)
    if not webapp_url:
        raise AppsScriptWebAppProviderError("NORTH_SHORE_SHEETS_WEBAPP_URL is missing")
    if not _is_https_url(webapp_url):
        raise AppsScriptWebAppProviderError("NORTH_SHORE_SHEETS_WEBAPP_URL must be HTTPS")
    body = _with_optional_secret(
        {
            "action": STATUS_ACTION,
            "request_id": request_id or str(uuid4()),
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        },
        secret,
    )
    return AppsScriptPostPayload(url=webapp_url, headers=_headers(secret), body=body, timeout=timeout)


def build_append_objects_payload(
    request: sheets_adapter.SheetWriteRequest,
    *,
    webapp_url: str,
    secret: str = "",
    action: str = APPEND_OBJECTS_ACTION,
    request_id: str | None = None,
    timestamp: str | None = None,
    timeout: float = 10.0,
) -> AppsScriptPostPayload:
    """Create the Web App POST shape without performing network I/O."""
    webapp_url = _text(webapp_url)
    secret = _text(secret)
    if not webapp_url:
        raise AppsScriptWebAppProviderError("NORTH_SHORE_SHEETS_WEBAPP_URL is missing")
    if not _is_https_url(webapp_url):
        raise AppsScriptWebAppProviderError("NORTH_SHORE_SHEETS_WEBAPP_URL must be HTTPS")
    validate_action_tab(action, request.tab_name)
    body = _with_optional_secret(
        {
            "action": action,
            "target_tab": request.tab_name,
            "objects": _request_objects(request),
            "rows": _request_rows(request),
            "request_id": request_id or str(uuid4()),
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        },
        secret,
    )
    return AppsScriptPostPayload(url=webapp_url, headers=_headers(secret), body=body, timeout=timeout)


def build_raw_log_payload(
    request: sheets_adapter.SheetWriteRequest,
    *,
    webapp_url: str,
    secret: str = "",
    request_id: str | None = None,
    timestamp: str | None = None,
    timeout: float = 10.0,
) -> AppsScriptPostPayload:
    """Create the Raw_Logs append payload expected by the demo Web App."""
    if request.tab_name != "Raw_Logs":
        raise AppsScriptWebAppProviderError("append_raw_log requires Raw_Logs")
    return build_append_objects_payload(
        request,
        webapp_url=webapp_url,
        secret=secret,
        action=APPEND_RAW_LOG_ACTION,
        request_id=request_id,
        timestamp=timestamp,
        timeout=timeout,
    )


def build_post_payload(*args: Any, **kwargs: Any) -> AppsScriptPostPayload:
    """Backward-compatible alias for object-row append payload construction."""
    return build_append_objects_payload(*args, **kwargs)


class AppsScriptWebAppProvider(sheets_adapter.SheetsConnector):
    """Optional Apps Script bridge behind explicit local gates."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        environ: Mapping[str, str] | None = None,
        http_client: AppsScriptHttpClient | None = None,
        timeout: float = 10.0,
    ):
        self.config = dict(config or {})
        self.environ = environ
        self.http_client = http_client
        self.timeout = timeout

    def _env(self) -> Mapping[str, str]:
        return self.environ if self.environ is not None else os.environ

    def status(self) -> AppsScriptWebAppConfig:
        return load_config(self.config, environ=self._env())

    def _value(self, config_key: str, env_key: str) -> str:
        return _text(self._env().get(env_key)) or _text(self.config.get(config_key))

    def _assert_base_ready(self) -> None:
        loaded = self.status()
        if loaded.provider != PROVIDER_APPS_SCRIPT_WEBAPP:
            raise AppsScriptWebAppProviderError("NORTH_SHORE_SHEETS_PROVIDER must be apps_script_webapp")
        if not loaded.execution_enabled:
            raise AppsScriptWebAppProviderError("Apps Script Web App execution is disabled")
        if not loaded.webapp_url_present:
            raise AppsScriptWebAppProviderError("NORTH_SHORE_SHEETS_WEBAPP_URL is missing")
        if not loaded.webapp_url_https:
            raise AppsScriptWebAppProviderError("NORTH_SHORE_SHEETS_WEBAPP_URL must be HTTPS")
        if loaded.secret_required and not loaded.secret_present:
            raise AppsScriptWebAppProviderError("NORTH_SHORE_SHEETS_WEBAPP_SECRET is missing")
        if self.http_client is None:
            raise AppsScriptWebAppProviderError("Apps Script Web App HTTP client is not configured")

    def _assert_write_ready(self) -> None:
        loaded = self.status()
        self._assert_base_ready()
        if not loaded.writes_enabled:
            raise AppsScriptWebAppProviderError("Apps Script Web App writes are disabled")

    def read(self, request: sheets_adapter.SheetReadRequest) -> Sequence[Sequence[Any]]:
        del request
        raise AppsScriptWebAppProviderError(
            "Apps Script Web App reads are status-only in this scaffold"
        )

    def write(self, requests: Sequence[sheets_adapter.SheetWriteRequest]) -> None:
        self.append_objects(requests)

    def _post_payload(self, payload: AppsScriptPostPayload) -> Any:
        assert self.http_client is not None
        return self.http_client.post(
            payload.url,
            json=payload.body,
            headers=payload.headers,
            timeout=payload.timeout,
        )

    def status_check(self) -> Any:
        """Call the Web App status action. This does not require reads_enabled."""
        self._assert_base_ready()
        webapp_url = self._value("webapp_url", "NORTH_SHORE_SHEETS_WEBAPP_URL")
        secret = self._value("webapp_secret", "NORTH_SHORE_SHEETS_WEBAPP_SECRET")
        return self._post_payload(
            build_status_payload(webapp_url=webapp_url, secret=secret, timeout=self.timeout)
        )

    def append_raw_log(self, requests: Sequence[sheets_adapter.SheetWriteRequest]) -> None:
        self._assert_write_ready()
        webapp_url = self._value("webapp_url", "NORTH_SHORE_SHEETS_WEBAPP_URL")
        secret = self._value("webapp_secret", "NORTH_SHORE_SHEETS_WEBAPP_SECRET")
        for request in requests:
            self._post_payload(
                build_raw_log_payload(
                    request,
                    webapp_url=webapp_url,
                    secret=secret,
                    timeout=self.timeout,
                )
            )

    def append_objects(self, requests: Sequence[sheets_adapter.SheetWriteRequest]) -> None:
        self._assert_write_ready()
        webapp_url = self._value("webapp_url", "NORTH_SHORE_SHEETS_WEBAPP_URL")
        secret = self._value("webapp_secret", "NORTH_SHORE_SHEETS_WEBAPP_SECRET")
        for request in requests:
            payload = build_append_objects_payload(
                request,
                webapp_url=webapp_url,
                secret=secret,
                timeout=self.timeout,
            )
            self._post_payload(payload)

    def append_rows(self, requests: Sequence[sheets_adapter.SheetWriteRequest]) -> None:
        """Compatibility method; the Apps Script bridge receives object rows."""
        self.append_objects(requests)


def config_template() -> dict[str, Any]:
    """Return placeholder-only Apps Script bridge config."""
    return {
        "provider": PROVIDER_APPS_SCRIPT_WEBAPP,
        "webapp_url_env": "NORTH_SHORE_SHEETS_WEBAPP_URL",
        "webapp_secret_env": "NORTH_SHORE_SHEETS_WEBAPP_SECRET",
        "webapp_secret_required": True,
        "execution_enabled": False,
        "reads_enabled": False,
        "writes_enabled": False,
        "allowed_actions": list(ALLOWED_ACTIONS),
        "allowed_tabs": list(ALLOWED_TABS),
    }
