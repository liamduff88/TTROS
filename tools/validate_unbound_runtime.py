#!/usr/bin/env python3
"""Read-only drift audit for the scoped Unbound Hermes integration.

This intentionally inspects only the six AOS profiles and three accepted
runtime entry points. It never reads the Hermes global/default profile.

Revisit: on a Hermes package upgrade or One Brain integration change. · Last touched: 2026-08-05.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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
DEFAULT_RUNTIME_PATHS = {
    "turn_context": Path("/home/liam/.hermes/hermes-agent/agent/turn_context.py"),
    "router": Path("/home/liam/agentic-os/hermes/hermes.py"),
    "aos_claude": Path("/home/liam/.local/bin/aos-claude"),
}
DEFAULT_PROFILE_ROOT = Path("/home/liam/.hermes/profiles")
ASSEMBLER = "/home/liam/agentic-os-live/hooks/context_assembler_hook.py"
BRAIN_MCP = "/home/liam/agentic-os-live/tools/brain_memory_mcp.py"
PLUGIN_NAME = "ttros-context-assembler"
PLUGIN_SOURCE = Path("/home/liam/agentic-os-live/hooks/hermes_context_assembler_plugin")


def _read(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise OSError(f"owned runtime file is unavailable or indirect: {path}")
    return path.read_text(encoding="utf-8", errors="strict")


def audit_runtime(
    *,
    runtime_paths: dict[str, Path] | None = None,
    profile_root: Path = DEFAULT_PROFILE_ROOT,
) -> dict[str, Any]:
    paths = runtime_paths or DEFAULT_RUNTIME_PATHS
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    try:
        turn = _read(Path(paths["turn_context"]))
        check("native_marker_required", "TTROS model call blocked: mandatory assembled context is absent" in turn, "native turn boundary fails closed")
        check("assembled_context_not_spilled", '"TTROS_ASSEMBLED_CONTEXT_V1" not in _piece' in turn, "validated assembled context survives the native hook boundary")
        check("seven_profiles_scoped", all(f'"{profile}"' in turn for profile in SCOPED_PROFILES), "all seven declared native profiles are covered by the fail-closed boundary")

        router = _read(Path(paths["router"]))
        check("router_assembles", "from context_assembler import assemble" in router and "assembled.render()" in router, "workbench delegation renders typed context")
        check("router_permission_dedup", 'startswith("PERMISSION MODE — SCOPED LOCAL TASK APPROVED")' in router, "assembled tasks are not double wrapped")

        claude = _read(Path(paths["aos_claude"]))
        check("claude_canonical_root", 'CANONICAL_AOS_ROOT="/home/liam/agentic-os-live"' in claude, "wrapper is pinned to the canonical live root")
        check("claude_backend_boundary", "http://127.0.0.1:8010/api/wsl/claude" in claude, "direct calls converge on the authoritative assembler endpoint")

        plugin = _read(PLUGIN_SOURCE / "__init__.py")
        manifest = _read(PLUGIN_SOURCE / "plugin.yaml")
        check(
            "native_plugin_contract",
            'ctx.register_hook("pre_llm_call"' in plugin and 'ctx.register_hook("post_llm_call"' in plugin,
            "repository plugin registers both native lifecycle hooks",
        )
        check("native_plugin_manifest", f"name: {PLUGIN_NAME}" in manifest, "repository plugin manifest is discoverable")
    except (KeyError, OSError, UnicodeError) as exc:
        check("runtime_files_readable", False, str(exc))

    for profile in SCOPED_PROFILES:
        path = Path(profile_root) / profile / "config.yaml"
        try:
            text = _read(path)
            if profile in PERSONAL_PROFILES:
                check(f"{profile}:native_memory_enabled", "memory_enabled: true" in text and "user_profile_enabled: true" in text, "native personal conversation continuity remains enabled")
                check(f"{profile}:single_assembler_path", text.count(ASSEMBLER) == 0, "David uses the native plugin without duplicate shell hooks")
            else:
                check(f"{profile}:native_memory_disabled", "memory_enabled: false" in text and "user_profile_enabled: false" in text, "AOS private memory authorities are disabled")
                check(f"{profile}:assembler_hooks", text.count(ASSEMBLER) == 2, "pre/post assembler fallback hooks are exact")
            check(f"{profile}:brain_mcp", BRAIN_MCP in text, "canonical Brain writer MCP is present")
            plugin_path = Path(profile_root) / profile / "plugins" / PLUGIN_NAME
            check(
                f"{profile}:native_plugin_link",
                plugin_path.is_symlink() and plugin_path.resolve() == PLUGIN_SOURCE.resolve(),
                "profile plugin resolves to the repository-controlled source",
            )
            check(f"{profile}:native_plugin_enabled", PLUGIN_NAME in text, "profile explicitly enables the native plugin")
        except (OSError, UnicodeError) as exc:
            check(f"{profile}:config", False, str(exc))

    passed = all(row["passed"] for row in checks)
    return {
        "status": "PASS" if passed else "NEEDS ATTENTION",
        "mode": "read_only_status",
        "profiles_checked": list(SCOPED_PROFILES),
        "global_default_profile_inspected": False,
        "checks": checks,
        "token_usage_text": "Token usage: no agent invocation",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Status-only audit of the scoped Unbound Hermes runtime")
    parser.add_argument("--status", action="store_true", help="run the read-only status audit (default)")
    parser.add_argument("--dry-run", action="store_true", help="alias for the same read-only status audit")
    args = parser.parse_args(argv)
    result = audit_runtime()
    result["requested_mode"] = "dry-run" if args.dry_run else "status"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
