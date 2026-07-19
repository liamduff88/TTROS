"""Mandatory Agentic OS policy for every Codex process launch.

Revisit: when the canonical Agentic OS root, Linux user, Codex installation,
or fresh-session CLI contract changes. · Last touched: 2026-07-19.
"""

from __future__ import annotations

import os
import pwd
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


class CodexPolicyError(RuntimeError):
    """The mandatory Agentic OS Codex runtime contract is not effective."""


SANDBOX_MODE = "danger-full-access"
APPROVAL_POLICY = "never"
CONTEXT_CEILING_PCT = 50
MAX_FRESH_PROMPT_BYTES = 64 * 1024


def _positive_environment_integer(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise CodexPolicyError(f"{name} must be a positive integer") from exc
    if value < 1:
        raise CodexPolicyError(f"{name} must be a positive integer")
    return value


CONTEXT_HANDOFF_THRESHOLD_TOKENS = _positive_environment_integer(
    "AOS_CODEX_CONTEXT_HANDOFF_TOKENS", 75_000,
)
MAX_CONTEXT_HANDOFFS = _positive_environment_integer("AOS_CODEX_MAX_CONTEXT_HANDOFFS", 4)
PERMISSION_HEADER = """PERMISSION MODE — SCOPED LOCAL TASK APPROVED

Do not ask for permission during this scoped local task. Assume approval for local reads, local edits, local file creation, dependency installation, validation commands, local dev-server startup, browser preview, and screenshot capture inside the stated scope.

Do not ask before editing files inside the stated folder. Make the changes, validate, and return the compact closeout.

Stop only for real external/destructive actions."""
FRESH_SESSION_POLICY = f"""## Fresh-session and retained-context contract

- This invocation is a new, independently scoped ephemeral Codex session. Do not resume, inherit, or search for any previous Codex transcript or session.
- Work only from this prompt and the repository/artifact paths it names. Do not replay orchestration history.
- Keep logs, screenshots, browser evidence, and verbose test output in local artifacts; retain only compact summaries and paths in prompts and closeouts.
- Before context reaches {CONTEXT_CEILING_PCT}%, write a compact receipt/handoff artifact and end the session. Any continuation must start as another fresh session from that artifact, never by transcript resume.
- If a clean session cannot be created, fail explicitly without doing task work."""

@dataclass(frozen=True)
class CodexRuntimeTarget:
    """Filesystem/process identity only; permission policy cannot be overridden."""

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
    except KeyError as exc:  # pragma: no cover - a broken host account database
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
        "session_mode": "fresh_ephemeral",
        "resume_allowed": False,
        "context_ceiling_pct": CONTEXT_CEILING_PCT,
        "context_handoff_threshold_tokens": CONTEXT_HANDOFF_THRESHOLD_TOKENS,
    }


def validate_runtime(
    requested_root: Path | str,
    target: CodexRuntimeTarget = CODEX_TARGET,
) -> dict:
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
    """Return the immutable headless CLI contract; callers add no policy args."""
    return [
        str(target.executable),
        "--sandbox", SANDBOX_MODE,
        "--ask-for-approval", APPROVAL_POLICY,
        "-C", str(target.root),
        "exec", "--ephemeral", "--skip-git-repo-check", "--json", "--color", "never", "-",
    ]


def prepare_fresh_prompt(prompt: str) -> str:
    """Apply the mandatory permission/session header and enforce a bounded work order."""
    task = str(prompt or "").strip()
    if not task:
        raise CodexPolicyError("Codex clean-session prompt is empty")
    if task.startswith(PERMISSION_HEADER):
        task = task[len(PERMISSION_HEADER):].lstrip()
    sections = [PERMISSION_HEADER, FRESH_SESSION_POLICY, task]
    prepared = "\n\n".join(sections).rstrip() + "\n"
    size = len(prepared.encode("utf-8"))
    if size > MAX_FRESH_PROMPT_BYTES:
        raise CodexPolicyError(
            f"Codex clean-session prompt is {size} bytes; maximum is {MAX_FRESH_PROMPT_BYTES}. "
            "Store large context as an artifact and pass a compact summary plus paths."
        )
    return prepared


def require_clean_session_id(output: str) -> str:
    """Require one real ``thread.started`` identity; never invent a fallback ID."""
    identities: list[str] = []
    started_events = 0
    for raw in str(output or "").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "thread.started":
            continue
        started_events += 1
        value = event.get("thread_id") or event.get("session_id") or event.get("id")
        if isinstance(value, str) and value.strip():
            identities.append(value.strip())
    if started_events != 1 or len(identities) != 1:
        if started_events == 0:
            detail = "missing"
        elif not identities:
            detail = "invalid (thread.started has no real identity)"
        else:
            detail = f"ambiguous ({started_events} thread.started events)"
        raise CodexPolicyError(
            f"Codex clean-session creation failed: thread.started identity is {detail}; "
            "refusing previous-session inheritance or synthetic fallback"
        )
    return identities[0]


def cumulative_usage_snapshot(output: str) -> dict:
    """Return the last cumulative JSONL usage snapshot without summing events.

    Codex ``turn.completed`` usage is cumulative. Repeated snapshots replace the
    preceding snapshot; an incomplete final event never falls back to an older
    complete event because that would silently under-report the closing usage.
    """
    event_count = 0
    last_usage: object = None
    for raw in str(output or "").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "turn.completed":
            continue
        event_count += 1
        last_usage = event.get("usage")
    if event_count == 0:
        return {"available": False, "event_count": 0, "reason": "missing terminal turn.completed usage"}
    if not isinstance(last_usage, dict):
        return {"available": False, "event_count": event_count, "reason": "terminal turn.completed usage is malformed"}

    values = {
        "input_tokens": last_usage.get("input_tokens"),
        "cached_input_tokens": last_usage.get("cached_input_tokens"),
        "output_tokens": last_usage.get("output_tokens"),
        "reasoning_output_tokens": last_usage.get("reasoning_output_tokens"),
    }
    required = ("input_tokens", "output_tokens")
    if any(not isinstance(values[key], int) or isinstance(values[key], bool) or values[key] < 0 for key in required):
        return {"available": False, "event_count": event_count, "reason": "terminal turn.completed usage lacks non-negative input/output"}
    for key in ("cached_input_tokens", "reasoning_output_tokens"):
        value = values[key]
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            return {"available": False, "event_count": event_count, "reason": f"terminal {key} is malformed"}
    cached = values["cached_input_tokens"]
    reasoning = values["reasoning_output_tokens"]
    if cached is not None and cached > values["input_tokens"]:
        return {"available": False, "event_count": event_count, "reason": "cached input exceeds provider-total input"}
    if reasoning is not None and reasoning > values["output_tokens"]:
        return {"available": False, "event_count": event_count, "reason": "reasoning output exceeds provider output"}
    return {
        "available": True,
        "event_count": event_count,
        **values,
        "cumulative_tokens": values["input_tokens"] + values["output_tokens"],
    }


def build_environment(target: CodexRuntimeTarget = CODEX_TARGET) -> dict[str, str]:
    """Retain the authenticated process environment while pinning Liam's Codex home."""
    try:
        account = pwd.getpwnam(target.linux_user)
    except KeyError as exc:
        raise CodexPolicyError(f"Linux user does not exist: {target.linux_user}") from exc
    env = os.environ.copy()
    env["HOME"] = account.pw_dir
    env["USER"] = target.linux_user
    env["LOGNAME"] = target.linux_user
    env["CODEX_HOME"] = str(target.codex_home)
    env["PATH"] = os.pathsep.join((
        str(target.executable.parent),
        str(Path(account.pw_dir) / ".local" / "bin"),
        env.get("PATH", ""),
    ))
    return env


def readiness(target: CodexRuntimeTarget = CODEX_TARGET, *, timeout: float = 5) -> dict:
    """Inspect the actual production command, identity, executable, and authentication."""
    metadata = invocation_metadata(target)
    command = build_exec_command(target)
    try:
        validate_runtime(target.root, target)
    except CodexPolicyError as exc:
        return {"available": False, "state": "policy_defect", "policy_error": str(exc), **metadata, "command": command}
    env = build_environment(target)
    try:
        version = subprocess.run(
            [str(target.executable), "--version"],
            cwd=str(target.root), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "state": type(exc).__name__, **metadata, "command": command}
    result = {
        "available": version.returncode == 0,
        "state": "ready" if version.returncode == 0 else "version_probe_failed",
        "version": ((version.stdout or "") + (version.stderr or "")).strip().splitlines()[-1]
        if (version.stdout or version.stderr) else "unavailable",
        **metadata,
        "command": command,
    }
    if not result["available"]:
        return result
    try:
        auth = subprocess.run(
            [str(target.executable), "login", "status"],
            cwd=str(target.root), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        result.update(available=False, authenticated=False, state="authentication_probe_failed")
        return result
    result["authenticated"] = auth.returncode == 0 and "logged in" in ((auth.stdout or "") + (auth.stderr or "")).lower()
    if not result["authenticated"]:
        result.update(available=False, state="authentication_unavailable")
    return result
