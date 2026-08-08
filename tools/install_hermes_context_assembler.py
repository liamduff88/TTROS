#!/usr/bin/env python3
"""Install or audit the repository-owned Hermes Context Assembler plugin.

The installer links one immutable repository plugin source into each scoped
profile and asks Hermes itself to enable it. It never reads profile secrets or
the global/default profile.

Revisit: on a Hermes plugin discovery/configuration change. · Last touched: 2026-08-05.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "ttros-context-assembler"
PLUGIN_SOURCE = ROOT / "hooks" / "hermes_context_assembler_plugin"
PROFILE_ROOT = Path("/home/liam/.hermes/profiles")
AOS_PROFILES = (
    "operator-lean",
    "aos-orchestrator",
    "aos-revenue",
    "aos-marketing",
    "aos-delivery",
    "aos-ops",
)
PERSONAL_PROFILES = ("david",)
SCOPED_PROFILES = (*AOS_PROFILES, *PERSONAL_PROFILES)
BRAIN_MCP_NAME = "brain"
BRAIN_MCP_PYTHON = "/home/liam/.hermes/hermes-agent/venv/bin/python"
BRAIN_MCP_SCRIPT = str(ROOT / "tools" / "brain_memory_mcp.py")
Runner = Callable[..., subprocess.CompletedProcess[str]]


def _plugin_row(payload: object) -> dict[str, Any] | None:
    rows = payload if isinstance(payload, list) else []
    for row in rows:
        if isinstance(row, dict) and row.get("name") == PLUGIN_NAME:
            return row
    return None


def _hermes_status(profile: str, hermes: str, runner: Runner) -> tuple[bool, str]:
    result = runner(
        [hermes, "-p", profile, "plugins", "list", "--user", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, "Hermes plugin listing failed"
    try:
        row = _plugin_row(json.loads(result.stdout))
    except json.JSONDecodeError:
        return False, "Hermes plugin listing was not valid JSON"
    if row is None:
        return False, "plugin was not discovered"
    enabled = row.get("enabled") is True or str(row.get("status") or "").lower() == "enabled"
    if not enabled:
        return False, str(row.get("error") or "plugin is not enabled")
    if "hooks" in row and int(row.get("hooks") or 0) < 2:
        return False, "plugin did not register both lifecycle hooks"
    return True, "Hermes reports the repository plugin discovered and enabled"


def _profile_contract(profile: str, profile_home: Path) -> list[dict[str, Any]]:
    try:
        text = (profile_home / "config.yaml").read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        return [{"name": f"{profile}:configuration", "passed": False, "detail": str(exc)}]
    if profile in PERSONAL_PROFILES:
        return [
            {
                "name": f"{profile}:native_personal_memory_preserved",
                "passed": "memory_enabled: true" in text and "user_profile_enabled: true" in text,
                "detail": "native personal memory and user-profile continuity remain enabled",
            },
            {
                "name": f"{profile}:single_native_assembler_path",
                "passed": "context_assembler_hook.py" not in text,
                "detail": "native plugin is the only David assembler registration; no duplicate shell hook",
            },
            {
                "name": f"{profile}:brain_mcp",
                "passed": BRAIN_MCP_SCRIPT in text,
                "detail": "authoritative Brain write MCP is configured separately from native personal memory",
            },
        ]
    return []


def audit(
    *,
    profile_root: Path = PROFILE_ROOT,
    hermes: str = "hermes",
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    source_valid = (
        (PLUGIN_SOURCE / "plugin.yaml").is_file()
        and (PLUGIN_SOURCE / "__init__.py").is_file()
    )
    checks.append({"name": "repository_plugin_source", "passed": source_valid})
    for profile in SCOPED_PROFILES:
        destination = profile_root / profile / "plugins" / PLUGIN_NAME
        linked = destination.is_symlink() and destination.resolve() == PLUGIN_SOURCE.resolve()
        checks.append({
            "name": f"{profile}:repository_link",
            "passed": linked,
            "detail": "repository source linked" if linked else "repository plugin link missing or drifted",
        })
        enabled, detail = _hermes_status(profile, hermes, runner) if linked else (False, "link unavailable")
        checks.append({"name": f"{profile}:native_registration", "passed": enabled, "detail": detail})
        checks.extend(_profile_contract(profile, profile_root / profile))
    passed = all(row["passed"] for row in checks)
    return {
        "status": "PASS" if passed else "NEEDS ATTENTION",
        "mode": "read_only_status",
        "profiles_checked": list(SCOPED_PROFILES),
        "global_default_profile_inspected": False,
        "checks": checks,
        "token_usage_text": "Token usage: no agent invocation",
    }


def install(
    *,
    profile_root: Path = PROFILE_ROOT,
    hermes: str = "hermes",
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    if not (PLUGIN_SOURCE / "plugin.yaml").is_file() or not (PLUGIN_SOURCE / "__init__.py").is_file():
        raise RuntimeError(f"repository plugin source is incomplete: {PLUGIN_SOURCE}")
    for profile in SCOPED_PROFILES:
        profile_home = profile_root / profile
        if not profile_home.is_dir():
            raise RuntimeError(f"scoped Hermes profile is unavailable: {profile}")
        plugins = profile_home / "plugins"
        plugins.mkdir(parents=True, exist_ok=True)
        destination = plugins / PLUGIN_NAME
        if destination.is_symlink():
            if destination.resolve() != PLUGIN_SOURCE.resolve():
                replacement = destination.with_name(f".{PLUGIN_NAME}.replacement-{os.getpid()}")
                replacement.symlink_to(PLUGIN_SOURCE, target_is_directory=True)
                os.replace(replacement, destination)
        elif destination.exists():
            raise RuntimeError(f"refusing to replace non-symlink plugin path: {destination}")
        else:
            destination.symlink_to(PLUGIN_SOURCE, target_is_directory=True)
        result = runner(
            [hermes, "-p", profile, "plugins", "enable", PLUGIN_NAME, "--no-allow-tool-override"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Hermes could not enable {PLUGIN_NAME} for {profile}")
        if profile in PERSONAL_PROFILES:
            config = profile_home / "config.yaml"
            try:
                config_text = config.read_text(encoding="utf-8", errors="strict")
            except (OSError, UnicodeError) as exc:
                raise RuntimeError(f"could not read scoped profile configuration: {profile}") from exc
            if "memory_enabled: true" not in config_text or "user_profile_enabled: true" not in config_text:
                raise RuntimeError("refusing to register David unless native personal memory remains enabled")
            if BRAIN_MCP_SCRIPT not in config_text:
                result = runner(
                    [
                        hermes, "-p", profile, "mcp", "add", BRAIN_MCP_NAME,
                        "--command", BRAIN_MCP_PYTHON, "--args", BRAIN_MCP_SCRIPT,
                    ],
                    capture_output=True,
                    text=True,
                    input="y\n",
                    check=False,
                )
                if result.returncode != 0 or "Cancelled." in (result.stdout or ""):
                    raise RuntimeError(f"Hermes could not configure the authoritative Brain MCP for {profile}")
    return audit(profile_root=profile_root, hermes=hermes, runner=runner)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--install", action="store_true", help="link and enable the plugin for all scoped profiles")
    mode.add_argument("--check", action="store_true", help="run the read-only installation audit (default)")
    parser.add_argument("--profile-root", type=Path, default=PROFILE_ROOT)
    parser.add_argument("--hermes", default="hermes")
    args = parser.parse_args(argv)
    try:
        result = install(profile_root=args.profile_root, hermes=args.hermes) if args.install else audit(
            profile_root=args.profile_root, hermes=args.hermes
        )
    except RuntimeError as exc:
        result = {
            "status": "NEEDS ATTENTION",
            "error": str(exc),
            "global_default_profile_inspected": False,
            "token_usage_text": "Token usage: no agent invocation",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
