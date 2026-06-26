#!/usr/bin/env python3
"""Read-only structural validation for the North Shore profile distribution."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml


DISTRIBUTION_ROOT = Path(__file__).resolve().parents[1]
APPROVED_OPERATIONS = {
    "route_north_shore_message",
    "route_north_shore_command",
    "generate_north_shore_report",
    "validate_north_shore_config",
}
EXPECTED_ENV = {
    "NORTH_SHORE_PACKAGE_ROOT": True,
    "NORTH_SHORE_TELEGRAM_BOT_TOKEN": False,
    "NORTH_SHORE_LLM_API_KEY": False,
    "NORTH_SHORE_SHEETS_SPREADSHEET_ID": False,
    "NORTH_SHORE_GOOGLE_CREDENTIALS_JSON": False,
}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path.name} must contain a YAML mapping"
    return data


def validate_env_requires(requirements: Any) -> None:
    """Validate approved env requirements despite installer YAML normalization."""
    assert isinstance(requirements, list), "env_requires must be a list"
    actual_names: set[str] = set()
    for requirement in requirements:
        assert isinstance(requirement, dict), "each env requirement must be a mapping"
        name = requirement.get("name")
        assert isinstance(name, str) and name, "each env requirement must have a name"
        actual_names.add(name)

        description = requirement.get("description")
        assert isinstance(description, str) and description.strip(), (
            f"{name} must have a non-empty description"
        )

        # Hermes profile installation may omit ``required: true`` while preserving
        # the semantic default. Optional envs must remain explicitly optional.
        required = requirement.get("required", True)
        assert isinstance(required, bool), f"{name}.required must be a boolean when set"
        assert required is EXPECTED_ENV.get(name), (
            f"{name}.required does not match the approved environment"
        )

        if not required and "default" in requirement:
            assert requirement.get("default") == "", f"{name}.default must be empty when set"

    assert actual_names == set(EXPECTED_ENV), "env_requires does not match the approved environment"


def validate_distribution() -> None:
    path = DISTRIBUTION_ROOT / "distribution.yaml"
    assert path.is_file(), "distribution.yaml is missing"
    data = load_yaml(path)
    expected = {
        "name": "north-shore-sales-coach",
        "version": "0.1.0",
        "hermes_requires": ">=0.17.0",
        "author": "Time to Revenue",
        "license": "Private",
    }
    for key, value in expected.items():
        assert str(data.get(key)) == value, f"distribution.yaml: invalid {key}"

    validate_env_requires(data.get("env_requires"))


def validate_config() -> None:
    data = load_yaml(DISTRIBUTION_ROOT / "config.yaml")
    assert data.get("model") == "", "model must be empty"
    assert data.get("providers") == {}, "providers must be empty"
    assert data.get("fallback_providers") == {}, "fallback providers must be empty"
    assert data.get("toolsets") == [], "toolsets must be empty"
    assert data.get("platform_toolsets") == {}, "platform toolsets must be empty"
    assert data.get("mcp_servers") == {}, "MCP servers must be empty"
    assert data.get("plugins") == [], "plugins must be empty"
    assert data.get("streaming") is False, "streaming must be off"

    for section in ("memory", "curator", "cron", "stt"):
        assert data.get(section, {}).get("enabled") is False, f"{section} must be disabled"
    assert data.get("skills", {}).get("external_dirs") == [], "external skill dirs must be empty"
    assert data.get("kanban", {}).get("gateway_dispatch_enabled") is False, (
        "kanban gateway dispatch must be disabled"
    )
    telegram = data.get("telegram", {})
    assert telegram.get("enabled") is False, "Telegram must be disabled"
    assert telegram.get("polling_enabled") is False, "Telegram polling must be disabled"
    assert telegram.get("live_polling_enabled") is False, "live polling must be disabled"

    north_shore = data.get("north_shore_sales_coach", {})
    expected_top = {
        "deterministic_first": True,
        "general_hermes_routing": False,
        "agentic_os_bridge": False,
        "private_operator_route": False,
    }
    for key, value in expected_top.items():
        assert north_shore.get(key) is value, f"north_shore_sales_coach.{key} is invalid"
    assert north_shore.get("telegram", {}).get("enabled") is False
    assert north_shore.get("telegram", {}).get("live_polling_enabled") is False
    assert north_shore.get("llm", {}).get("enabled") is False
    sheets = north_shore.get("sheets", {})
    assert sheets.get("provider") == "none"
    for key in ("reads_enabled", "writes_enabled", "execution_enabled"):
        assert sheets.get(key) is False, f"north_shore_sales_coach.sheets.{key} must be false"


def validate_mcp() -> None:
    data = json.loads((DISTRIBUTION_ROOT / "mcp.json").read_text(encoding="utf-8"))
    assert data == {"mcpServers": {}}, "mcp.json must declare no servers"


def validate_manifest() -> None:
    data = load_yaml(DISTRIBUTION_ROOT / "north_shore_wrapper_manifest.yaml")
    operations = data.get("operations")
    assert isinstance(operations, dict), "manifest operations must be a mapping"
    assert set(operations) == APPROVED_OPERATIONS, "manifest operations are not exactly approved"
    for name, operation in operations.items():
        assert isinstance(operation, dict), f"{name} must be a mapping"
        assert operation.get("token_free") is True, f"{name} must be token-free"
        assert operation.get("network") is False, f"{name} must block network access"
        assert operation.get("starts_service") is False, f"{name} must not start a service"


def validate_package_root() -> None:
    configured = os.environ.get("NORTH_SHORE_PACKAGE_ROOT")
    if not configured:
        return
    root = Path(configured).expanduser()
    assert root.is_dir(), "NORTH_SHORE_PACKAGE_ROOT does not exist or is not a directory"
    required_files = (
        "README.md",
        "bot_manifest.json",
        "src/__init__.py",
        "src/north_shore_bot_runner.py",
        "src/message_router.py",
        "src/command_router.py",
        "src/report_generator.py",
        "src/llm_adapter.py",
        "src/sheets_adapter.py",
        "config/commands.json",
        "config/roles.json",
    )
    missing = [relative for relative in required_files if not (root / relative).is_file()]
    assert not missing, "package root is missing actual package files: " + ", ".join(missing)


def main() -> int:
    validate_distribution()
    validate_config()
    validate_mcp()
    validate_manifest()
    validate_package_root()
    print("PASS: North Shore Hermes profile distribution is structurally ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
