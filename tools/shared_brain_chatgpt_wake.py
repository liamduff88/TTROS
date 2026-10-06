"""ChatGPT wake signal: one AgentMail email per workstream version newly handed to ChatGPT.

ChatGPT has no direct Brain connection; it works the Drive handoff (plan sections 8 and 17) and
checks it hourly. This step shortens that wait. Each tick on the existing
`aos-claude-handoff.service` reads the workstream notes through `shared_brain_checkpoint.resume()`.
For every current note whose `next_action` explicitly assigns the work to ChatGPT, it sends one
email through the existing governed AgentMail path (the same adapter command and allowlist as the
backend's internal digest) to the allowlisted internal recipient.

The email is a wake signal only, never task state: it carries the workstream_id, the version and
"resume". ChatGPT must re-read the Drive projection and act only if that version is still current
and still assigned to it. The hourly ChatGPT check stays the fallback.

At most once per version: the bounded log records the claim before the send, so a crash, timeout
or failed send is never repeated for that version (the hourly fallback covers it). A newer version
is a new note ID and may wake again. The note is re-read immediately before sending; a superseded
version is skipped. "Current" means written within FRESH_HOURS, as for the Claude watcher, so old
notes that still name ChatGPT stay inert. A note ChatGPT itself wrote never wakes ChatGPT.
No model calls. No new queue, store, timer or daemon.

Revisit: when the checkpoint note schema, the AgentMail adapter command, the notification
allowlist or the ChatGPT-side email trigger changes. Last touched: 2026-10-06.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

try:
    import shared_brain_checkpoint as checkpoint_store
    import shared_brain_claude_watcher as watcher
except ModuleNotFoundError:
    from tools import shared_brain_checkpoint as checkpoint_store
    from tools import shared_brain_claude_watcher as watcher

REPO = Path(__file__).resolve().parents[1]
LOG_PATH = REPO / "logs" / "shared_brain_chatgpt_wake.log"
MAX_LOG_LINES = 300
FRESH_HOURS = 12.0
MAX_WAKES_PER_TICK = 5
SEND_TIMEOUT_SECONDS = 120
ACTION = "AGENT_MAIL_SEND_EMAIL"
WAKE_RECIPIENT = "automation@timetorevenue.com"
DEFAULT_INBOX = "olmec1@agentmail.to"
SUBJECT_PREFIX = "TTROS ChatGPT handoff:"
BODY_MARKER = "TTROS-SHARED-BRAIN-WAKE v1"
PROJECTION = "TTROS Memory Exchange/06_WORKSTREAMS_READ"
# "ChatGPT should …", "ChatGPT: …"; not "ChatGPT or Claude …", not "David or ChatGPT …".
ASSIGNED_RE = re.compile(r"\s*\**\s*chatgpt(?=[\s:,.*]|$)(?!\s*(?:or|and)\s)(?!\s*[/&])", re.I)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _log(path: Path, event: str, **fields: Any) -> dict[str, Any]:
    entry = {"at": _now().isoformat(timespec="seconds").replace("+00:00", "Z"), "event": event, **fields}
    lines = [json.dumps(item, ensure_ascii=False) for item in watcher._read_log(path)]
    lines.append(json.dumps(entry, ensure_ascii=False))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text("\n".join(lines[-MAX_LOG_LINES:]) + "\n", encoding="utf-8")
    os.replace(temp, path)
    print(json.dumps(entry, ensure_ascii=False))
    return entry


def assigned_to_chatgpt(note: Mapping[str, Any]) -> bool:
    return bool(ASSIGNED_RE.match(str(note.get("next_action", ""))))


def _eligible(note: Mapping[str, Any], now: dt.datetime, hours: float) -> bool:
    return assigned_to_chatgpt(note) and note.get("surface") != "chatgpt" and watcher._fresh(dict(note), now, hours)


def candidates(now: dt.datetime, hours: float, root: Path | None = None) -> list[dict[str, Any]]:
    """Current notes assigned to ChatGPT, oldest first, so a backlog wakes in order."""
    notes = []
    for row in checkpoint_store.resume(root=root).get("workstreams", []):
        result = checkpoint_store.resume(row["workstream_id"], root=root)
        if result.get("success") and _eligible(result["note"], now, hours):
            notes.append(result["note"])
    return sorted(notes, key=lambda note: str(note.get("updated", "")))


def compose(note: Mapping[str, Any]) -> tuple[str, str]:
    """Subject and plain-text body: deterministic routing fields only, no note content."""
    ws, version = note["workstream_id"], note["version"]
    subject = f"{SUBJECT_PREFIX} {ws} v{version}"
    body = "\n".join([
        BODY_MARKER,
        f"workstream_id: {ws}",
        f"version: {version}",
        "action: resume",
        f"projection: {PROJECTION}/{ws}.md",
        "",
        "Wake signal only; this email is not the task and carries no task state.",
        f"Re-read the projection above. Act only if its version is {version} and its next_action still "
        "assigns the work to ChatGPT; otherwise do nothing. Then follow the usual Drive handoff.",
    ])
    return subject, body


def _agentmail_inbox(root: Path) -> str:
    try:
        config = json.loads((root / "queue" / "notifications.json").read_text(encoding="utf-8")).get("agentmail") or {}
    except (OSError, ValueError, AttributeError):
        config = {}
    if str(config.get("action") or ACTION).strip().upper() != ACTION:
        return ""
    return str(config.get("inbox_id") or DEFAULT_INBOX).strip()


def authorized(recipient: str, root: Path = REPO) -> bool:
    """The standing internal-mail exception from the existing notification allowlist, nothing wider."""
    try:
        import aos_orchestration
    except ModuleNotFoundError:
        from tools import aos_orchestration
    verdict = aos_orchestration.action_authorization(root, None, action=ACTION, target=recipient)
    return verdict.get("authorized") is True and verdict.get("basis") == "internal_mail_allowlist"


def agentmail_send(recipient: str, subject: str, text: str, *, root: Path = REPO) -> dict[str, Any]:
    """Send through the existing governed AgentMail adapter, exactly as the backend's internal digest
    does (`dashboard/backend/main.py::_run_agentmail_composio_send`)."""
    inbox = _agentmail_inbox(root)
    if not inbox:
        return {"ok": False, "error": "agentmail_contract_not_configured"}
    recipient = recipient.strip().lower()
    payload = {"inbox_id": inbox, "to": [recipient], "subject": subject, "text": text, "html": "",
               "cc": [], "bcc": [], "labels": [], "reply_to": []}
    quoted = shlex.quote(str(root))
    # The adapter's authorization imports `tools.aos_orchestration`; run as a script, only
    # `connectors/` is on its path, so the repo root must be added or every execute crashes.
    command = (f'export PATH="$HOME/.local/npm/bin:$HOME/.local/bin:$HOME/.composio:$PATH"; '
               f"export AOS_ROOT={quoted}; export PYTHONPATH={quoted}; cd {quoted}; "
               "python3 connectors/composio_access_adapter.py "
               f"run agent_mail {ACTION} --data {shlex.quote(json.dumps(payload, separators=(',', ':')))} "
               # The adapter authorizes the send against `--target`; without it the internal
               # allowlist sees an empty destination and refuses every wake.
               f"--target {shlex.quote(recipient)} --execute --operator-command")
    try:
        done = subprocess.run(["bash", "-lc", command], cwd=str(root), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=SEND_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    try:
        response = json.loads(done.stdout.strip() or done.stderr.strip())
    except ValueError:
        # Exception class only (e.g. ModuleNotFoundError), never the message or payload.
        crash = re.search(r"^(\w+(?:Error|Exception))\b", done.stderr.strip().splitlines()[-1] if done.stderr.strip() else "")
        return {"ok": False, "error": "adapter_returned_no_json" + (f": {crash.group(1)}" if crash else "")}
    return response if isinstance(response, dict) else {"ok": False, "error": "adapter_returned_non_object"}


def _acknowledged(response: Mapping[str, Any]) -> bool:
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    return response.get("ok") is True and data.get("successful") is not False


def _message_id(response: Any) -> str:
    if isinstance(response, dict):
        for key in ("message_id", "id"):
            if isinstance(response.get(key), (str, int)) and str(response[key]).strip():
                return str(response[key])[:200]
        for key in ("data", "result", "response"):
            found = _message_id(response.get(key))
            if found:
                return found
    return ""


def run(*, root: Path | None = None, log: Path = LOG_PATH, recipient: str | None = None,
        send: Callable[[str, str, str], Mapping[str, Any]] | None = None,
        is_authorized: Callable[[str], bool] | None = None,
        hours: float = FRESH_HOURS, dry_run: bool = False) -> list[dict[str, Any]]:
    """One tick: wake ChatGPT once for each newly assigned current note version."""
    recipient = (recipient or os.environ.get("TTROS_CHATGPT_WAKE_RECIPIENT") or WAKE_RECIPIENT).strip().lower()
    claimed = {entry["note_id"] for entry in watcher._read_log(log)
               if entry.get("event") == "wake_claimed" and "note_id" in entry}
    pending = [note for note in candidates(_now(), hours, root) if note["id"] not in claimed]
    if dry_run:
        return [{"note_id": note["id"], "dry_run": True, "would_wake": True} for note in pending]
    if not pending:
        return []
    if not (is_authorized or authorized)(recipient):
        entries = watcher._read_log(log)
        if not entries or entries[-1].get("event") != "wake_blocked":  # once per change, not every tick
            _log(log, "wake_blocked", reason="recipient_not_in_internal_mail_allowlist")
        return []
    send = send or agentmail_send
    actions = []
    for note in pending[:MAX_WAKES_PER_TICK]:
        # Re-read immediately before sending; a superseded version never wakes ChatGPT.
        fresh = checkpoint_store.resume(note["workstream_id"], root=root)
        if (not fresh.get("success") or fresh["note"]["version"] != note["version"]
                or not _eligible(fresh["note"], _now(), hours)):
            actions.append(_log(log, "changed_before_wake", note_id=note["id"]))
            continue
        subject, body = compose(fresh["note"])
        # Claim before the send: a failed or timed-out send is never repeated for this version.
        _log(log, "wake_claimed", note_id=note["id"], workstream_id=note["workstream_id"], version=note["version"])
        try:
            response = send(recipient, subject, body)
        except Exception as exc:  # the adapter's own error types; logged, never retried
            response = {"ok": False, "error": type(exc).__name__}
        if _acknowledged(response):
            actions.append(_log(log, "wake_sent", note_id=note["id"], subject=subject,
                                provider_message_id=_message_id(response) or "unavailable", model_calls=0))
        else:
            actions.append(_log(log, "wake_failed", note_id=note["id"],
                                reason=str(response.get("error") or "not_acknowledged")[:300], model_calls=0))
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="list the wakes that would be sent; send and log nothing")
    args = parser.parse_args(argv)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.with_name(LOG_PATH.name + ".lock").open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"event": "wake_tick", "skipped": "another tick is running"}))
            return 0
        actions = run(dry_run=args.dry_run)
    print(json.dumps({"event": "wake_tick", "actions": len(actions), "dry_run": args.dry_run, "model_calls": 0,
                      **({"would_wake": [action["note_id"] for action in actions]} if args.dry_run else {})}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
