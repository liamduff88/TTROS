"""Scoped Business Brain Git closure and recovery sweep.

Revisit: when the Shared Brain Git durability contract changes. Last touched: 2026-10-03.
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "logs/runtime/brain_git_closure.json"
TIMEOUT = 20


def enabled() -> bool:
    value = os.environ.get("TTROS_BRAIN_AUTOPUSH", "").strip()
    if not value:
        try:
            for line in (Path.home() / ".config/ttros-shared-brain.env").read_text().splitlines():
                key, sep, raw = line.partition("=")
                if sep and key.strip() == "TTROS_BRAIN_AUTOPUSH":
                    value = raw.strip().strip('"').strip("'")
        except OSError:
            pass
    return value.lower() in {"1", "true", "yes"}


def git(brain: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(brain), *args], capture_output=True,
                          text=True, timeout=TIMEOUT, check=False,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})


def _state_path() -> Path:
    return Path(os.environ.get("TTROS_BRAIN_CLOSURE_STATE", str(STATE)))


def state() -> dict:
    try:
        value = json.loads(_state_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def record(**changes: object) -> None:
    target = _state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    value = {**state(), **changes}
    fd, name = tempfile.mkstemp(prefix=".brain-closure-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)


def pending_count(brain: Path) -> int:
    result = git(brain, "rev-list", "--count", "origin/main..HEAD")
    return int(result.stdout.strip()) if result.returncode == 0 else -1


def push_commit(brain: Path, sha: str) -> str:
    """Call under the Brain transaction lock. Never roll back a valid commit."""
    if not enabled():
        return "local_only"
    try:
        pushed = git(brain, "push", "origin", "HEAD:refs/heads/main")
        if pushed.returncode:
            return "pending"
        remote = git(brain, "ls-remote", "origin", "refs/heads/main")
        if remote.returncode or not remote.stdout.startswith(sha + "\t"):
            return "pending"
        git(brain, "fetch", "origin", "main")
        return "synced"
    except (OSError, subprocess.TimeoutExpired):
        return "pending"


@contextmanager
def brain_lock(brain: Path):
    with (brain / ".git/hermes-memory.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _alert(message: str) -> None:
    # Existing operator-only Telegram send path; no connector files are inspected.
    from tools.aos_orchestration import default_bridge_send
    recipients = json.loads((ROOT / "queue/notifications.json").read_text())["allowlist"]["telegram"]
    for recipient in recipients:
        default_bridge_send(str(recipient), message)


def sweep(brain: Path, *, alert=_alert) -> dict:
    """Push existing durable commits only; stop on remote divergence."""
    with brain_lock(brain):
        previous = state().get("last_sweep")
        try:
            fetched = git(brain, "fetch", "origin", "main")
            if fetched.returncode:
                outcome = "pending_remote_unreachable"
            else:
                remote_ahead = git(brain, "rev-list", "--count", "HEAD..origin/main")
                if remote_ahead.returncode or int(remote_ahead.stdout.strip()) > 0:
                    outcome = "stopped_remote_diverged"
                else:
                    pending = pending_count(brain)
                    outcome = "synced" if pending == 0 else push_commit(brain, git(brain, "rev-parse", "HEAD").stdout.strip())
                    if outcome == "local_only":
                        outcome = "pending_disabled"
        except (OSError, subprocess.TimeoutExpired, ValueError):
            outcome = "pending_remote_unreachable"
        record(last_sweep=outcome)
    # One alert when the sweep stops, not one per five-minute tick while it stays stopped.
    if outcome == "stopped_remote_diverged" and previous != outcome:
        try:
            alert("TTROS Shared Brain Git sweep stopped: remote diverged. No push was attempted.")
        except Exception:
            record(last_alert="failed")
        else:
            record(last_alert="sent")
    return {"result": outcome, "pending_count": pending_count(brain)}


def status(brain: Path) -> dict:
    value = state()
    return {"pending_count": pending_count(brain),
            "last_sweep": value.get("last_sweep", "never"),
            "last_write": value.get("last_write")}


def main() -> int:
    from tools.brain_memory import VAULT_ROOT
    result = sweep(VAULT_ROOT)
    print(json.dumps(result, sort_keys=True))
    return 2 if result["result"] == "stopped_remote_diverged" else 0


if __name__ == "__main__":
    raise SystemExit(main())
