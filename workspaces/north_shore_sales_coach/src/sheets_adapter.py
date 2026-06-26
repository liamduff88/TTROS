"""Provider-neutral, fail-closed Google Sheets integration boundary.

The deterministic ``sheets_sync_adapter`` produces ordered row mappings. This
module validates those mappings and converts them into provider-neutral request
objects. It imports no provider SDK and performs no external operation.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from . import sheets_sync_adapter


class SheetsValidationError(ValueError):
    """A sync payload does not match the package-local Sheets specification."""


class SheetsExecutionDisabledError(RuntimeError):
    """Provider execution is unavailable until separately approved and enabled."""


@dataclass(frozen=True)
class SheetWriteRequest:
    """Provider-neutral contract for a future append or update operation."""

    tab_name: str
    headers: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    operation: str = "append_rows"


@dataclass(frozen=True)
class SheetReadRequest:
    """Provider-neutral contract for a future bounded values read."""

    tab_name: str
    cell_range: str | None = None
    operation: str = "read_values"


@runtime_checkable
class SheetsConnector(Protocol):
    """Provider-neutral connector contract implemented only by selected adapters."""

    def read(self, request: SheetReadRequest) -> Sequence[Sequence[Any]]:
        """Return bounded values for an explicitly constructed read request."""

    def write(self, requests: Sequence[SheetWriteRequest]) -> None:
        """Apply validated write requests using deployment-owned authorization."""


class DisabledSheetsConnector:
    """Default connector: satisfies the boundary while failing closed."""

    def read(self, request: SheetReadRequest) -> Sequence[Sequence[Any]]:
        del request
        raise SheetsExecutionDisabledError("Sheets execution is disabled")

    def write(self, requests: Sequence[SheetWriteRequest]) -> None:
        del requests
        raise SheetsExecutionDisabledError("Sheets execution is disabled")


def target_tabs_match_specs(
    tab_names: Sequence[str],
    headers_path: str | Path = sheets_sync_adapter.PACKAGE_ROOT / "google_sheets" / "tab_headers.json",
    schema_path: str | Path = sheets_sync_adapter.PACKAGE_ROOT / "google_sheets" / "sheet_schema.json",
) -> bool:
    """Confirm every sync target exists in both package-local Sheets specs."""
    headers = json.loads(Path(headers_path).read_text(encoding="utf-8"))
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    header_tabs = set(headers) if isinstance(headers, Mapping) else set()
    schema_tabs = {
        item.get("name") for item in schema.get("tabs", [])
        if isinstance(item, Mapping) and isinstance(item.get("name"), str)
    } if isinstance(schema, Mapping) else set()
    expected = tuple(sheets_sync_adapter.SYNC_TABS)
    return tuple(tab_names) == expected and set(expected).issubset(header_tabs & schema_tabs)


def build_write_requests(
    payloads: Mapping[str, Sequence[Mapping[str, Any]]],
    headers: Mapping[str, Sequence[str]] | None = None,
) -> tuple[SheetWriteRequest, ...]:
    """Validate deterministic payloads and preserve tab, column, and row order."""
    expected_headers = headers or sheets_sync_adapter.load_headers()
    actual_tabs = list(payloads)
    expected_tabs = list(sheets_sync_adapter.SYNC_TABS)
    if actual_tabs != expected_tabs:
        raise SheetsValidationError(
            f"tab order mismatch: expected {expected_tabs}, got {actual_tabs}"
        )

    write_requests = []
    for tab_name in sheets_sync_adapter.SYNC_TABS:
        if tab_name not in expected_headers:
            raise SheetsValidationError(f"missing header specification for {tab_name}")
        ordered_headers = tuple(expected_headers[tab_name])
        value_rows = []
        for row_number, row in enumerate(payloads[tab_name], start=1):
            if not isinstance(row, Mapping):
                raise SheetsValidationError(f"{tab_name} row {row_number} is not a mapping")
            if list(row) != list(ordered_headers):
                raise SheetsValidationError(
                    f"{tab_name} row {row_number} column order mismatch"
                )
            value_rows.append(tuple(row[column] for column in ordered_headers))
        write_requests.append(SheetWriteRequest(tab_name, ordered_headers, tuple(value_rows)))
    return tuple(write_requests)


def dry_run_summary(requests: Sequence[SheetWriteRequest]) -> str:
    """Summarize provider-neutral validation without identifiers or row data."""
    lines = ["Sheets adapter dry-run (provider-neutral; no external calls)"]
    lines.extend(f"{request.tab_name}: {len(request.rows)} row(s) | valid" for request in requests)
    lines.append("Validation: PASS")
    lines.append("Execution: BLOCKED")
    return "\n".join(lines)


def execute_write_requests(requests: Sequence[SheetWriteRequest]) -> None:
    """Fail closed; a future selected provider must implement this separately."""
    del requests
    raise SheetsExecutionDisabledError(
        "Sheets execution is disabled; no provider call was made"
    )


class SheetsAdapter:
    """Provider-neutral request factory with disabled execution by default."""

    def __init__(self, config: Mapping[str, Any] | None = None):
        self.config = dict(config or {})

    @property
    def provider(self) -> str | None:
        value = self.config.get("provider")
        return value.strip() if isinstance(value, str) and value.strip() else None

    @property
    def enabled(self) -> bool:
        return self.config.get("enabled") is True and self.provider is not None

    def build_write_requests(
        self, payloads: Mapping[str, Sequence[Mapping[str, Any]]]
    ) -> tuple[SheetWriteRequest, ...]:
        return build_write_requests(payloads)

    def build_local_write_requests(self) -> tuple[SheetWriteRequest, ...]:
        return self.build_write_requests(sheets_sync_adapter.load_local_payloads())

    def execute(self, requests: Sequence[SheetWriteRequest]) -> None:
        del requests
        raise SheetsExecutionDisabledError(
            "Sheets execution is disabled; provider selection does not enable writes"
        )

    def append(self, record: Mapping[str, Any]) -> None:
        """Retain the Phase 1 single-record boundary while remaining fail-closed."""
        del record
        raise SheetsExecutionDisabledError("Sheets execution is disabled")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate provider-neutral Sheets requests")
    parser.add_argument("--dry-run", action="store_true", help="validate local payloads only")
    parser.add_argument("--execute", action="store_true", help="request execution (currently disabled)")
    args = parser.parse_args(argv)
    if not args.dry_run and not args.execute:
        parser.error("one of --dry-run or --execute is required")
    requests = SheetsAdapter().build_local_write_requests()
    if args.execute:
        execute_write_requests(requests)
    print(dry_run_summary(requests))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
