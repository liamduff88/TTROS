"""Optional Composio preflight for the provider-neutral Sheets boundary.

Composio is one possible future provider alongside a Hermes-native connector or
the direct Google Sheets API. This module has no provider SDK dependency and
cannot execute writes. Core request construction lives in ``sheets_adapter``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import sheets_adapter, sheets_sync_adapter


# Compatibility aliases keep existing callers on the generic implementation.
WriterValidationError = sheets_adapter.SheetsValidationError
LiveExecutionDisabledError = sheets_adapter.SheetsExecutionDisabledError
SheetsWriteRequest = sheets_adapter.SheetWriteRequest
build_write_requests = sheets_adapter.build_write_requests
dry_run_summary = sheets_adapter.dry_run_summary
target_tabs_match_specs = sheets_adapter.target_tabs_match_specs


@dataclass(frozen=True)
class ActionContract:
    """Minimum provider fields required by a future approved executor."""

    operation: str
    required_field_groups: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class ComposioProbe:
    toolkit_available: bool
    append_action_available: bool
    update_action_available: bool
    append_contract_matches: bool
    update_contract_matches: bool
    detail: str


APPEND_CONTRACT = ActionContract(
    "append",
    (("spreadsheet_id", "spreadsheetid"), ("range", "sheet_name", "sheetname"), ("values", "rows", "data")),
)
UPDATE_CONTRACT = ActionContract(
    "update",
    (("spreadsheet_id", "spreadsheetid"), ("range", "sheet_name", "sheetname"), ("values", "rows", "data")),
)
COMPOSIO_TOOLKIT = "googlesheets"


def _json_value(raw: str) -> Any:
    """Decode CLI JSON without ever including raw provider output in an error."""
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise WriterValidationError("Composio returned unreadable discovery metadata") from exc


def _objects(value: Any):
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def _action_slugs(value: Any, operation: str) -> tuple[str, ...]:
    found = set()
    for item in _objects(value):
        for key in ("slug", "name", "tool_slug"):
            candidate = item.get(key)
            if not isinstance(candidate, str):
                continue
            normalized = candidate.upper()
            if "GOOGLE" in normalized and "SHEET" in normalized and operation.upper() in normalized:
                found.add(candidate)
    return tuple(sorted(found))


def _schema_field_names(value: Any) -> set[str]:
    names: set[str] = set()
    for item in _objects(value):
        properties = item.get("properties")
        if isinstance(properties, Mapping):
            names.update(str(key).lower() for key in properties)
    return names


def _contract_matches(schema: Any, contract: ActionContract) -> bool:
    fields = _schema_field_names(schema)
    return all(any(alias in fields for alias in aliases) for aliases in contract.required_field_groups)


def probe_composio(
    cli_path: str | Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> ComposioProbe:
    """Discover append/update actions and inspect schemas; never execute an action."""
    configured_path = cli_path or os.environ.get("NORTH_SHORE_COMPOSIO_CLI_PATH")
    if not configured_path:
        return ComposioProbe(False, False, False, False, False, "Composio CLI not configured")
    cli = Path(configured_path).expanduser()
    if not cli.is_file():
        return ComposioProbe(False, False, False, False, False, "Configured Composio CLI unavailable")

    def run(arguments: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return runner([str(cli), *arguments], capture_output=True, text=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None

    search = run([
        "search", "append rows to a Google Sheet", "update values in a Google Sheet",
        "--toolkits", COMPOSIO_TOOLKIT, "--limit", "20",
    ])
    if search is None or search.returncode != 0:
        return ComposioProbe(True, False, False, False, False, "Composio discovery unavailable")
    try:
        discovery = _json_value(search.stdout)
    except WriterValidationError:
        return ComposioProbe(True, False, False, False, False, "Composio discovery metadata unreadable")
    append_slugs = _action_slugs(discovery, "append")
    update_slugs = _action_slugs(discovery, "update")

    def inspect(slugs: tuple[str, ...], contract: ActionContract) -> bool:
        for slug in slugs:
            result = run(["execute", slug, "--get-schema"])
            if result is not None and result.returncode == 0:
                try:
                    if _contract_matches(_json_value(result.stdout), contract):
                        return True
                except WriterValidationError:
                    pass
        return False

    append_matches = inspect(append_slugs, APPEND_CONTRACT)
    update_matches = inspect(update_slugs, UPDATE_CONTRACT)
    complete = bool(append_slugs and update_slugs and append_matches and update_matches)
    return ComposioProbe(
        True, bool(append_slugs), bool(update_slugs), append_matches, update_matches,
        "append/update actions and contracts verified" if complete else "action contract verification incomplete",
    )


def preflight_summary(
    requests: Sequence[SheetsWriteRequest], *, sheet_id_present: bool,
    composio: ComposioProbe | None = None,
) -> str:
    """Render readiness without row contents, identifiers, credentials, or CLI output."""
    actual_tabs = tuple(request.tab_name for request in requests)
    lines = ["North Shore Sheets preflight (read-only; no write actions)"]
    lines.append(f"Google Sheet ID config: {'present' if sheet_id_present else 'missing'}")
    tabs_valid = sheets_adapter.target_tabs_match_specs(actual_tabs)
    lines.append(f"Target tabs: {'valid' if tabs_valid else 'invalid'} ({len(actual_tabs)} expected)")
    for request in requests:
        lines.append(f"Payload {request.tab_name}: ready ({len(request.rows)} row(s))")
    lines.append("Append contract: spreadsheet + tab/range + ordered row values")
    lines.append("Update contract: spreadsheet + tab/range + ordered row values")
    if composio is None:
        lines.append("Composio availability: not checked")
        lines.append("Composio action contracts: not checked")
    else:
        lines.append(f"Composio toolkit: {'available' if composio.toolkit_available else 'unavailable'}")
        lines.append(
            "Composio actions: "
            f"append={'available' if composio.append_action_available else 'unavailable'}, "
            f"update={'available' if composio.update_action_available else 'unavailable'}"
        )
        contracts_ok = composio.append_contract_matches and composio.update_contract_matches
        lines.append(f"Composio action contracts: {'verified' if contracts_ok else 'unverified'}")
    lines.append("Execute mode: BLOCKED pending explicit approval and separate implementation")
    return "\n".join(lines)


def execute_write_requests(requests: Sequence[SheetsWriteRequest]) -> None:
    """Delegate to the provider-neutral fail-closed execution boundary."""
    sheets_adapter.execute_write_requests(requests)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Optional Composio preflight for generic Sheets requests")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="run generic local validation only")
    mode.add_argument("--preflight", action="store_true", help="run local read-only readiness checks")
    mode.add_argument(
        "--check-composio", action="store_true",
        help="also search Composio actions and inspect schemas (no action execution)",
    )
    mode.add_argument("--execute", action="store_true", help="request live execution (currently disabled)")
    args = parser.parse_args(argv)

    payloads = sheets_sync_adapter.load_local_payloads()
    requests = build_write_requests(payloads)
    if args.execute:
        execute_write_requests(requests)
    if args.preflight or args.check_composio:
        composio = probe_composio() if args.check_composio else None
        print(preflight_summary(
            requests,
            sheet_id_present=bool(os.environ.get("NORTH_SHORE_GOOGLE_SHEET_ID", "").strip()),
            composio=composio,
        ))
    else:
        print(dry_run_summary(requests))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
