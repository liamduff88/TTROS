"""Shared Agentic OS policy for supervised Codex process launches.

Revisit: when the Codex CLI invocation contract changes. · Last touched: 2026-07-18.
"""

from __future__ import annotations

import os
import pwd
import subprocess
from dataclasses import dataclass
from pathlib import Path


SANDBOX_MODE = "danger-full-access"
APPROVAL_POLICY = "never"
AUTO_COMPACT_TOKEN_LIMIT = 75_000


class CodexPolicyError(RuntimeError):
    """The shared Codex runtime contract is not effective."""


@dataclass(frozen=True)
class CodexRuntimeTarget:
    root: Path
    executable: Path
    linux_user: str
    codex_home: Path


CODEX_TARGET = CodexRuntimeTarget(
    root=Path("/home/liam/agentic-os-live"),
    executable=Path("/home/liam/.local/npm/bin/codex"),
    linux_user="liam",
    codex_home=Path("/home/liam/.codex"),
)


def effective_linux_user() -> str:
    try:
        return pwd.getpwuid(os.geteuid()).pw_name
    except KeyError as exc:  # pragma: no cover
        raise CodexPolicyError(f"effective uid {os.geteuid()} has no Linux user") from exc


def invocation_metadata(target: CodexRuntimeTarget = CODEX_TARGET) -> dict:
    return {
        "executable": str(target.executable),
        "cwd": str(target.root),
        "linux_user": effective_linux_user(),
        "effective_uid": os.geteuid(),
        "sandbox": SANDBOX_MODE,
        "sandbox_mode": SANDBOX_MODE,
        "approval_policy": APPROVAL_POLICY,
        "ask_for_approval": APPROVAL_POLICY,
    }


def validate_runtime(requested_root: Path | str, target: CodexRuntimeTarget = CODEX_TARGET) -> dict:
    requested = Path(requested_root).resolve()
    expected = target.root.resolve()
    user = effective_linux_user()
    defects = []
    if requested != expected:
        defects.append(f"cwd must be {expected}, got {requested}")
    if user != target.linux_user:
        defects.append(f"Linux user must be {target.linux_user}, got {user}")
    if not target.executable.is_absolute() or not target.executable.is_file() or not os.access(target.executable, os.X_OK):
        defects.append(f"Codex executable is missing or not executable: {target.executable}")
    if str(expected).startswith("/mnt/"):
        defects.append(f"Windows-mounted Agentic OS roots are forbidden: {expected}")
    if defects:
        raise CodexPolicyError("Agentic OS Codex policy defect: " + "; ".join(defects))
    return invocation_metadata(target)


def build_exec_command(target: CodexRuntimeTarget = CODEX_TARGET) -> list[str]:
    return [
        str(target.executable),
        "--sandbox", SANDBOX_MODE,
        "--ask-for-approval", APPROVAL_POLICY,
        "-C", str(target.root),
        "--config", f"model_auto_compact_token_limit={AUTO_COMPACT_TOKEN_LIMIT}",
        "exec", "--skip-git-repo-check", "--json", "--color", "never", "-",
    ]


def build_environment(target: CodexRuntimeTarget = CODEX_TARGET) -> dict[str, str]:
    try:
        account = pwd.getpwnam(target.linux_user)
    except KeyError as exc:
        raise CodexPolicyError(f"Linux user does not exist: {target.linux_user}") from exc
    environment = os.environ.copy()
    environment["HOME"] = account.pw_dir
    environment["USER"] = target.linux_user
    environment["LOGNAME"] = target.linux_user
    environment["CODEX_HOME"] = str(target.codex_home)
    environment["PATH"] = os.pathsep.join((
        str(target.executable.parent),
        str(Path(account.pw_dir) / ".local" / "bin"),
        environment.get("PATH", ""),
    ))
    return environment


def readiness(target: CodexRuntimeTarget = CODEX_TARGET, *, timeout: float = 5) -> dict:
    metadata = invocation_metadata(target)
    command = build_exec_command(target)
    try:
        validate_runtime(target.root, target)
    except CodexPolicyError as exc:
        return {"available": False, "state": "policy_defect", "policy_error": str(exc), **metadata, "command": command}
    try:
        version = subprocess.run(
            [str(target.executable), "--version"], cwd=str(target.root),
            env=build_environment(target), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "state": type(exc).__name__, **metadata, "command": command}
    return {
        "available": version.returncode == 0,
        "state": "ready" if version.returncode == 0 else "version_probe_failed",
        "version": ((version.stdout or "") + (version.stderr or "")).strip() or "unavailable",
        **metadata,
        "command": command,
    }
