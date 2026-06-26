"""Direct Google Sheets API provider scaffold.

This module is intentionally local-only and fail-closed. It adapts the existing
provider-neutral sheets_adapter request objects to the shape a future direct
Google Sheets/Drive API implementation will need, but it does not import Google
SDKs at module import time and it does not perform live reads or writes.
"""

from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import sheets_adapter, sheets_sync_adapter


PROVIDER_NONE = "none"
PROVIDER_GOOGLE = "google_sheets_api"
PROVIDER_APPS_SCRIPT_WEBAPP = "apps_script_webapp"
PROVIDER_HERMES = "hermes_native"
PROVIDER_COMPOSIO = "composio"
PROVIDER_AGENTIC_OS_BACKEND = "agentic_os_backend"
ALLOWED_PROVIDERS = (
    PROVIDER_NONE,
    PROVIDER_GOOGLE,
    PROVIDER_APPS_SCRIPT_WEBAPP,
    PROVIDER_HERMES,
    PROVIDER_COMPOSIO,
    PROVIDER_AGENTIC_OS_BACKEND,
)
FORBIDDEN_DIRECT_PROVIDERS = (
    PROVIDER_HERMES,
    PROVIDER_COMPOSIO,
    PROVIDER_AGENTIC_OS_BACKEND,
)
GOOGLE_LIBRARY_SPECS = (
    "googleapiclient.discovery",
    "google.oauth2.service_account",
)
SERVICE_ACCOUNT_REQUIRED_FIELDS = (
    "type",
    "project_id",
    "private_key_id",
    "private_key",
    "client_email",
    "token_uri",
)


class GoogleSheetsProviderError(RuntimeError):
    """Direct Google Sheets provider is not ready or execution is disabled."""


@dataclass(frozen=True)
class GoogleSheetsConfig:
    """Sanitized direct-provider configuration.

    Credential values are tracked only as booleans so validation and dry-run
    output cannot leak secrets.
    """

    provider: str = PROVIDER_NONE
    sheet_id_present: bool = False
    credentials_json_present: bool = False
    credentials_path_present: bool = False
    credentials_path_exists: bool = False
    reads_enabled: bool = False
    writes_enabled: bool = False
    execution_enabled: bool = False
    reads_explicit: bool = False
    writes_explicit: bool = False
    execution_explicit: bool = False


@dataclass(frozen=True)
class GoogleSheetsValidation:
    """Fail-closed validation result for the direct Google provider."""

    provider: str
    dry_run_only: bool
    can_read_metadata: bool
    can_write: bool
    messages: tuple[str, ...]
    execution_enabled: bool = False
    reads_enabled: bool = False
    writes_enabled: bool = False
    credentials_available: bool = False
    google_libraries_available: bool = False
    client_ready: bool = False
    reason: str = "not_validated"
    error_code: str = "not_validated"
    route_locked: bool = False
    selected_provider: str = PROVIDER_NONE
    forbidden_providers_detected: tuple[str, ...] = ()
    credential_source: str = "missing"


@dataclass(frozen=True)
class GoogleCredentialStatus:
    """Sanitized credential readiness status."""

    available: bool
    source: str
    reason: str
    error_code: str


@dataclass(frozen=True)
class GoogleRouteLockStatus:
    """Sanitized route-lock result for direct Google Sheets preflight."""

    route_locked: bool
    selected_provider: str
    forbidden_providers_detected: tuple[str, ...]
    credential_source: str
    reason: str
    error_code: str


@dataclass(frozen=True)
class GoogleClientReadiness:
    """Sanitized readiness status for a future direct Google API client."""

    execution_enabled: bool
    reads_enabled: bool
    writes_enabled: bool
    credentials_available: bool
    google_libraries_available: bool
    client_ready: bool
    reason: str
    error_code: str


@dataclass(frozen=True)
class GoogleAppendPayload:
    """Provider-specific append shape derived from validated generic request data."""

    spreadsheet_id_env: str
    tab_name: str
    value_input_option: str
    values: tuple[tuple[Any, ...], ...]


@dataclass(frozen=True)
class GoogleMetadataRequest:
    """Provider-specific metadata request placeholder."""

    spreadsheet_id_env: str
    include_grid_data: bool = False


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _has_explicit_value(data: Mapping[str, Any], env: Mapping[str, str], config_key: str, env_key: str) -> bool:
    return config_key in data or env_key in env


def _library_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _credential_shape_valid(data: Any) -> bool:
    if not isinstance(data, Mapping):
        return False
    return all(isinstance(data.get(field), str) and bool(data[field].strip()) for field in SERVICE_ACCOUNT_REQUIRED_FIELDS)


def _parse_credentials_json(raw_value: str) -> GoogleCredentialStatus:
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return GoogleCredentialStatus(False, "package_local_json", "Google credentials JSON is invalid", "credentials_json_invalid")
    if not _credential_shape_valid(decoded):
        return GoogleCredentialStatus(False, "package_local_json", "Google credentials JSON shape is invalid", "credentials_shape_invalid")
    return GoogleCredentialStatus(True, "package_local_json", "Google credentials JSON shape is valid", "credentials_available")


def _package_local_credentials_path(path_value: str) -> Path | None:
    raw_path = Path(path_value).expanduser()
    candidate = raw_path if raw_path.is_absolute() else sheets_sync_adapter.PACKAGE_ROOT / raw_path
    root = sheets_sync_adapter.PACKAGE_ROOT.resolve()
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def _read_credentials_path(path_value: str) -> GoogleCredentialStatus:
    path = _package_local_credentials_path(path_value)
    if path is None:
        return GoogleCredentialStatus(
            False,
            "missing",
            "NORTH_SHORE_GOOGLE_CREDENTIALS_PATH must be inside the North Shore package-local runtime path",
            "credentials_path_outside_package",
        )
    if not path.is_file():
        return GoogleCredentialStatus(False, "package_local_path", "NORTH_SHORE_GOOGLE_CREDENTIALS_PATH does not point to a package-local file", "credentials_path_missing")
    try:
        raw_value = path.read_text(encoding="utf-8")
    except OSError:
        return GoogleCredentialStatus(False, "package_local_path", "NORTH_SHORE_GOOGLE_CREDENTIALS_PATH is unreadable", "credentials_path_unreadable")
    parsed = _parse_credentials_json(raw_value)
    if not parsed.available:
        return GoogleCredentialStatus(False, "package_local_path", "Google credentials file shape is invalid", parsed.error_code)
    return GoogleCredentialStatus(True, "package_local_path", "Google credentials file shape is valid", "credentials_available")


def credential_status(
    config: Mapping[str, Any] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> GoogleCredentialStatus:
    """Validate credential presence and JSON shape without returning secrets."""
    data = dict(config or {})
    env = environ if environ is not None else os.environ
    credentials_json = _text(env.get("NORTH_SHORE_GOOGLE_CREDENTIALS_JSON"))
    credentials_path = _text(env.get("NORTH_SHORE_GOOGLE_CREDENTIALS_PATH")) or _text(data.get("credentials_path"))

    if credentials_json:
        return _parse_credentials_json(credentials_json)
    if credentials_path:
        return _read_credentials_path(credentials_path)
    return GoogleCredentialStatus(
        False,
        "missing",
        "Google credentials are missing; set NORTH_SHORE_GOOGLE_CREDENTIALS_JSON or NORTH_SHORE_GOOGLE_CREDENTIALS_PATH",
        "credentials_missing",
    )


def route_lock_status(loaded: GoogleSheetsConfig, credentials: GoogleCredentialStatus) -> GoogleRouteLockStatus:
    """Return the route lock before any live auth, connector, or Google preflight."""
    selected_provider = loaded.provider or PROVIDER_NONE
    forbidden = tuple(provider for provider in FORBIDDEN_DIRECT_PROVIDERS if selected_provider == provider)
    if forbidden:
        return GoogleRouteLockStatus(
            False,
            selected_provider,
            forbidden,
            credentials.source,
            "Selected provider is forbidden for direct Google Sheets preflight",
            "forbidden_provider",
        )
    if selected_provider != PROVIDER_GOOGLE:
        return GoogleRouteLockStatus(
            False,
            selected_provider,
            (),
            credentials.source,
            "NORTH_SHORE_SHEETS_PROVIDER must be google_sheets_api",
            "provider_not_google_sheets_api",
        )
    if not loaded.sheet_id_present:
        return GoogleRouteLockStatus(
            False,
            selected_provider,
            (),
            credentials.source,
            "NORTH_SHORE_GOOGLE_SHEET_ID is missing",
            "sheet_id_missing",
        )
    if not credentials.available:
        return GoogleRouteLockStatus(
            False,
            selected_provider,
            (),
            credentials.source,
            credentials.reason,
            credentials.error_code,
        )
    return GoogleRouteLockStatus(
        True,
        selected_provider,
        (),
        credentials.source,
        "Direct Google Sheets route is locked to package-local credentials",
        "route_locked",
    )


def validate_client_readiness(
    loaded: GoogleSheetsConfig,
    *,
    credentials: GoogleCredentialStatus,
    google_libraries_available: bool,
    client_builder: Callable[[], Any] | None = None,
) -> GoogleClientReadiness:
    """Validate future client readiness without using a real Google builder."""
    if not loaded.execution_enabled or not loaded.execution_explicit:
        return GoogleClientReadiness(
            loaded.execution_enabled,
            loaded.reads_enabled,
            loaded.writes_enabled,
            credentials.available,
            google_libraries_available,
            False,
            "Direct Google Sheets API execution is disabled",
            "execution_disabled",
        )
    if not credentials.available:
        return GoogleClientReadiness(
            loaded.execution_enabled,
            loaded.reads_enabled,
            loaded.writes_enabled,
            False,
            google_libraries_available,
            False,
            credentials.reason,
            credentials.error_code,
        )
    if not google_libraries_available:
        return GoogleClientReadiness(
            loaded.execution_enabled,
            loaded.reads_enabled,
            loaded.writes_enabled,
            True,
            False,
            False,
            "Google API libraries are not installed",
            "google_libraries_missing",
        )
    if client_builder is None:
        return GoogleClientReadiness(
            loaded.execution_enabled,
            loaded.reads_enabled,
            loaded.writes_enabled,
            True,
            True,
            False,
            "Google client builder is not configured for this scaffold pass",
            "client_builder_missing",
        )
    try:
        client = client_builder()
    except Exception:
        return GoogleClientReadiness(
            loaded.execution_enabled,
            loaded.reads_enabled,
            loaded.writes_enabled,
            True,
            True,
            False,
            "Google client builder failed",
            "client_builder_failed",
        )
    if client is None:
        return GoogleClientReadiness(
            loaded.execution_enabled,
            loaded.reads_enabled,
            loaded.writes_enabled,
            True,
            True,
            False,
            "Google client builder returned no client",
            "client_builder_empty",
        )
    return GoogleClientReadiness(
        loaded.execution_enabled,
        loaded.reads_enabled,
        loaded.writes_enabled,
        True,
        True,
        True,
        "Google client scaffold is ready",
        "ready",
    )


def load_config(
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> GoogleSheetsConfig:
    """Load direct-provider config from placeholders without exposing values."""
    data = dict(config or {})
    env = environ if environ is not None else os.environ

    provider = _text(env.get("NORTH_SHORE_SHEETS_PROVIDER")) or _text(data.get("provider")) or PROVIDER_NONE
    sheet_id = _text(env.get("NORTH_SHORE_GOOGLE_SHEET_ID")) or _text(data.get("sheet_id"))
    credentials_json = _text(env.get("NORTH_SHORE_GOOGLE_CREDENTIALS_JSON"))
    credentials_path = _text(env.get("NORTH_SHORE_GOOGLE_CREDENTIALS_PATH"))
    credentials_path = credentials_path or _text(data.get("credentials_path"))
    package_local_path = _package_local_credentials_path(credentials_path) if credentials_path else None

    return GoogleSheetsConfig(
        provider=provider,
        sheet_id_present=bool(sheet_id),
        credentials_json_present=bool(credentials_json),
        credentials_path_present=bool(credentials_path),
        credentials_path_exists=bool(package_local_path and package_local_path.is_file()),
        reads_enabled=_truthy(data.get("reads_enabled")) or _truthy(env.get("NORTH_SHORE_GOOGLE_READS_ENABLED")),
        writes_enabled=_truthy(data.get("writes_enabled")) or _truthy(env.get("NORTH_SHORE_GOOGLE_WRITES_ENABLED")),
        execution_enabled=_truthy(data.get("execution_enabled")) or _truthy(env.get("NORTH_SHORE_GOOGLE_EXECUTION_ENABLED")),
        reads_explicit=_has_explicit_value(data, env, "reads_enabled", "NORTH_SHORE_GOOGLE_READS_ENABLED"),
        writes_explicit=_has_explicit_value(data, env, "writes_enabled", "NORTH_SHORE_GOOGLE_WRITES_ENABLED"),
        execution_explicit=_has_explicit_value(data, env, "execution_enabled", "NORTH_SHORE_GOOGLE_EXECUTION_ENABLED"),
    )


def validate_config(
    config: Mapping[str, Any] | GoogleSheetsConfig | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    library_checker: Any = _library_available,
    client_builder: Callable[[], Any] | None = None,
) -> GoogleSheetsValidation:
    """Validate direct-provider readiness without creating a Google client."""
    loaded = config if isinstance(config, GoogleSheetsConfig) else load_config(config, environ)
    messages: list[str] = []
    credentials = credential_status(config if not isinstance(config, GoogleSheetsConfig) else None, environ=environ)
    route_lock = route_lock_status(loaded, credentials)

    if loaded.provider not in ALLOWED_PROVIDERS:
        messages.append("Invalid Sheets provider; expected google_sheets_api for direct Google preflight")
    if not route_lock.route_locked:
        messages.append(route_lock.reason)
        return GoogleSheetsValidation(
            loaded.provider,
            True,
            False,
            False,
            tuple(messages),
            loaded.execution_enabled,
            loaded.reads_enabled,
            loaded.writes_enabled,
            credentials.available,
            False,
            False,
            route_lock.reason,
            route_lock.error_code,
            route_lock.route_locked,
            route_lock.selected_provider,
            route_lock.forbidden_providers_detected,
            route_lock.credential_source,
        )

    if not loaded.execution_enabled:
        messages.append("Direct Google Sheets API execution is disabled")
    if not loaded.execution_explicit:
        messages.append("NORTH_SHORE_GOOGLE_EXECUTION_ENABLED must be explicitly set for execution")
    if not loaded.sheet_id_present:
        messages.append("NORTH_SHORE_GOOGLE_SHEET_ID is missing")
    if not credentials.available:
        messages.append(credentials.reason)

    missing_libraries = tuple(name for name in GOOGLE_LIBRARY_SPECS if not library_checker(name))
    libraries_available = not missing_libraries
    if missing_libraries:
        messages.append("Google API libraries are not installed")

    readiness = validate_client_readiness(
        loaded,
        credentials=credentials,
        google_libraries_available=libraries_available,
        client_builder=client_builder,
    )
    if readiness.error_code not in {
        "ready",
        "execution_disabled",
        "credentials_missing",
        "credentials_path_missing",
        "credentials_path_unreadable",
        "credentials_json_invalid",
        "credentials_shape_invalid",
        "google_libraries_missing",
    }:
        messages.append(readiness.reason)

    common_ready = (
        loaded.provider == PROVIDER_GOOGLE
        and loaded.execution_enabled
        and loaded.sheet_id_present
        and readiness.client_ready
    )
    can_read_metadata = common_ready and loaded.reads_enabled
    can_write = common_ready and loaded.writes_enabled
    if not loaded.reads_explicit:
        messages.append("NORTH_SHORE_GOOGLE_READS_ENABLED must be explicitly set for reads")
        can_read_metadata = False
    elif common_ready and not loaded.reads_enabled:
        messages.append("Google Sheets reads are disabled")
    if not loaded.writes_explicit:
        messages.append("NORTH_SHORE_GOOGLE_WRITES_ENABLED must be explicitly set for writes")
        can_write = False
    elif common_ready and not loaded.writes_enabled:
        messages.append("Google Sheets writes are disabled")

    return GoogleSheetsValidation(
        loaded.provider,
        dry_run_only=not (can_read_metadata or can_write),
        can_read_metadata=can_read_metadata,
        can_write=can_write,
        messages=tuple(messages),
        execution_enabled=loaded.execution_enabled,
        reads_enabled=loaded.reads_enabled,
        writes_enabled=loaded.writes_enabled,
        credentials_available=credentials.available,
        google_libraries_available=libraries_available,
        client_ready=readiness.client_ready,
        reason=readiness.reason,
        error_code=readiness.error_code,
        route_locked=route_lock.route_locked,
        selected_provider=route_lock.selected_provider,
        forbidden_providers_detected=route_lock.forbidden_providers_detected,
        credential_source=route_lock.credential_source,
    )


def build_append_payloads(
    requests: Sequence[sheets_adapter.SheetWriteRequest],
) -> tuple[GoogleAppendPayload, ...]:
    """Build direct-API append payload placeholders from adapter request data."""
    return tuple(
        GoogleAppendPayload(
            spreadsheet_id_env="NORTH_SHORE_GOOGLE_SHEET_ID",
            tab_name=request.tab_name,
            value_input_option="RAW",
            values=request.rows,
        )
        for request in requests
    )


def build_local_append_payloads() -> tuple[GoogleAppendPayload, ...]:
    """Validate local rows through the generic adapter, then shape API payloads."""
    requests = sheets_adapter.build_write_requests(sheets_sync_adapter.load_local_payloads())
    return build_append_payloads(requests)


def dry_run_summary(
    requests: Sequence[sheets_adapter.SheetWriteRequest],
    validation: GoogleSheetsValidation | None = None,
) -> str:
    """Summarize direct-provider readiness without identifiers or row contents."""
    validation = validation or validate_config()
    payloads = build_append_payloads(requests)
    lines = ["Direct Google Sheets provider dry-run (no external calls)"]
    lines.append(f"Provider: {validation.provider}")
    lines.append(f"Route locked: {validation.route_locked}")
    lines.append(f"Selected provider: {validation.selected_provider}")
    lines.append(
        "Forbidden providers detected: "
        + (", ".join(validation.forbidden_providers_detected) if validation.forbidden_providers_detected else "none")
    )
    lines.append(f"Credential source: {validation.credential_source}")
    lines.extend(f"{payload.tab_name}: {len(payload.values)} row(s) | payload valid" for payload in payloads)
    lines.append(f"Read metadata: {'READY' if validation.can_read_metadata else 'BLOCKED'}")
    lines.append(f"Append rows: {'READY' if validation.can_write else 'BLOCKED'}")
    lines.append(f"Execution enabled: {validation.execution_enabled}")
    lines.append(f"Reads enabled: {validation.reads_enabled}")
    lines.append(f"Writes enabled: {validation.writes_enabled}")
    lines.append(f"Credentials available: {validation.credentials_available}")
    lines.append(f"Google libraries available: {validation.google_libraries_available}")
    lines.append(f"Client ready: {validation.client_ready}")
    lines.append(f"Reason: {validation.reason}")
    lines.append(f"Error code: {validation.error_code}")
    lines.append("Execution: BLOCKED")
    if validation.messages:
        lines.append("Messages: " + "; ".join(validation.messages))
    return "\n".join(lines)


class DirectGoogleSheetsProvider(sheets_adapter.SheetsConnector):
    """Direct API provider placeholder behind the neutral adapter boundary."""

    def __init__(self, config: Mapping[str, Any] | None = None, *, client_builder: Callable[[], Any] | None = None):
        self.config = dict(config or {})
        self.client_builder = client_builder

    def validate_config(self) -> GoogleSheetsValidation:
        return validate_config(self.config, client_builder=self.client_builder)

    def build_payloads(
        self,
        requests: Sequence[sheets_adapter.SheetWriteRequest],
    ) -> tuple[GoogleAppendPayload, ...]:
        return build_append_payloads(requests)

    def read(self, request: sheets_adapter.SheetReadRequest) -> Sequence[Sequence[Any]]:
        del request
        raise GoogleSheetsProviderError(
            "Direct Google Sheets value reads are not implemented; no Google call was made"
        )

    def read_sheet_metadata(self) -> Mapping[str, Any]:
        validation = self.validate_config()
        if not validation.can_read_metadata:
            raise GoogleSheetsProviderError("; ".join(validation.messages) or "Google Sheets metadata reads are disabled")
        raise GoogleSheetsProviderError(
            "Direct Google Sheets metadata reads are not implemented; no Google call was made"
        )

    def write(self, requests: Sequence[sheets_adapter.SheetWriteRequest]) -> None:
        self.append_rows(requests)

    def append_rows(self, requests: Sequence[sheets_adapter.SheetWriteRequest]) -> None:
        validation = self.validate_config()
        if not validation.can_write:
            raise GoogleSheetsProviderError("; ".join(validation.messages) or "Google Sheets writes are disabled")
        del requests
        raise GoogleSheetsProviderError(
            "Direct Google Sheets append rows is not implemented; no Google call was made"
        )


def config_template() -> dict[str, Any]:
    """Return non-secret configuration placeholders for examples and tests."""
    return {
        "provider_env": "NORTH_SHORE_SHEETS_PROVIDER",
        "provider": PROVIDER_NONE,
        "allowed_providers": list(ALLOWED_PROVIDERS),
        "forbidden_direct_google_preflight_providers": list(FORBIDDEN_DIRECT_PROVIDERS),
        "sheet_id_env": "NORTH_SHORE_GOOGLE_SHEET_ID",
        "credentials_json_env": "NORTH_SHORE_GOOGLE_CREDENTIALS_JSON",
        "credentials_path_env": "NORTH_SHORE_GOOGLE_CREDENTIALS_PATH",
        "reads_enabled": False,
        "writes_enabled": False,
        "execution_enabled": False,
    }


def main() -> int:
    requests = sheets_adapter.build_write_requests(sheets_sync_adapter.load_local_payloads())
    print(dry_run_summary(requests))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
