"""Manual-only Sheets sync command service."""

from __future__ import annotations

import json as json_lib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import apps_script_webapp_provider, sheets_adapter, sheets_sync_adapter


class SheetsManualSyncError(RuntimeError):
    """Manual Sheets sync failed closed before or during provider execution."""


@dataclass(frozen=True)
class SheetsManualSyncResult:
    provider: str
    tabs: tuple[str, ...]
    row_count: int
    post_count: int


class UrlLibHttpClient:
    """Small production HTTP client kept outside the provider for fakeable tests."""

    def post(
        self,
        url: str,
        *,
        json: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: float,
    ) -> Any:
        body = bytes(json_lib.dumps(json, separators=(",", ":"), ensure_ascii=False), "utf-8")
        request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise SheetsManualSyncError("Apps Script Web App POST failed") from exc
        if not payload.strip():
            return None
        try:
            return json_lib.loads(payload)
        except json_lib.JSONDecodeError:
            return {"raw_response_present": True}


def _filtered_requests(
    requests: Sequence[sheets_adapter.SheetWriteRequest],
    tab_names: Sequence[str] | None,
) -> tuple[sheets_adapter.SheetWriteRequest, ...]:
    if tab_names is None:
        return tuple(requests)
    allowed = tuple(tab_names)
    return tuple(request for request in requests if request.tab_name in allowed)


def run_manual_sheets_sync(
    *,
    root: str | Path,
    config: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    http_client: apps_script_webapp_provider.AppsScriptHttpClient | None = None,
    tab_names: Sequence[str] | None = None,
) -> SheetsManualSyncResult:
    """Build local payloads and push them through the selected provider."""
    selected_http = http_client if http_client is not None else UrlLibHttpClient()
    provider = apps_script_webapp_provider.AppsScriptWebAppProvider(
        config,
        environ=environ,
        http_client=selected_http,
    )
    try:
        loaded = provider.status()
        if loaded.provider != apps_script_webapp_provider.PROVIDER_APPS_SCRIPT_WEBAPP:
            raise SheetsManualSyncError("NORTH_SHORE_SHEETS_PROVIDER must be apps_script_webapp")
        requests = _filtered_requests(
            sheets_adapter.SheetsAdapter().build_write_requests(
                sheets_sync_adapter.load_local_payloads(root)
            ),
            tab_names,
        )
        provider.append_objects(requests)
    except (apps_script_webapp_provider.AppsScriptWebAppProviderError, sheets_adapter.SheetsValidationError) as exc:
        raise SheetsManualSyncError(str(exc)) from exc
    return SheetsManualSyncResult(
        provider=apps_script_webapp_provider.PROVIDER_APPS_SCRIPT_WEBAPP,
        tabs=tuple(request.tab_name for request in requests),
        row_count=sum(len(request.rows) for request in requests),
        post_count=len(requests),
    )
