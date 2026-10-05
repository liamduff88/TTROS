"""Shared Brain workflow start/finish: open a bounded workstream from Liam's request, report it back.

Start: David's `start_workflow` brain tool calls `start()`. It opens a new workstream note
through the existing `checkpoint()` (expected_version 0) with a working-artifact brief, and
hands the next action to Claude, so the existing Claude handoff watcher runs it unattended.
The brief carries a named TTROS workflow's method (from `workflows/workflow_registry.json`)
or, when none matches, an ad-hoc bounded brief. Bound: one unattended Claude pass; no submit,
send, publish or external action; the finished result comes back as `work_product` result.md.

Finish: `report()` runs on the same 2-minute timer as the Claude watcher. When a workstream
started here is handed back to Liam (`next_action` begins "Liam"), or Claude's pass for it
ended without a checkpoint, it sends Liam one Telegram message through the existing
orchestration bridge send, with the result inline. No model calls. No new queue, store or
daemon: the bounded log below records starts and reports, as the watcher's log does.

Revisit: when the checkpoint note schema, the Claude watcher's assignment rule or the workflow
registry shape changes. Last touched: 2026-10-04.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
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
REGISTRY = REPO / "workflows" / "workflow_registry.json"
LOG_PATH = REPO / "logs" / "shared_brain_workflow.log"
BRIEF_NAME = "workflow-brief.md"
RESULT_NAME = "result.md"
MAX_REQUEST_CHARS = 4000
MAX_METHOD_CHARS = 12_000
REPORT_WINDOW_DAYS = 7
MAX_REPORT_ATTEMPTS = 3
MAX_MESSAGE_CHARS = 3800
MAX_LOG_LINES = 300
LIAM_RE = re.compile(r"\s*\**\s*liam\b", re.I)
HOST_PATH_RE = re.compile(r"(?:/(?:home|mnt|tmp|etc|usr|var)/\S*|[A-Za-z]:\\\S*)")
STOPWORDS = set("""a an and the to of for with on in into this that these my me our please can could
would you start run kick off begin shared brain workflow workstream bring back finished result
results it its then i want need idea""".split())

NEXT_ACTION = ("Claude should open the workflow brief in the work product, do the whole bounded pass it "
               "describes, store the finished result as work_product result.md, and set next_action to "
               "'Liam: review the finished result'.")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _log(path: Path, event: str, **fields: Any) -> dict[str, Any]:
    """Bounded JSON-lines log, as the watcher keeps; silent, because start() runs inside
    David's stdio MCP server, where stdout is the protocol channel."""
    entry = {"at": _now().isoformat(timespec="seconds").replace("+00:00", "Z"), "event": event, **fields}
    lines = [json.dumps(item, ensure_ascii=False) for item in watcher._read_log(path)]
    lines.append(json.dumps(entry, ensure_ascii=False))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text("\n".join(lines[-MAX_LOG_LINES:]) + "\n", encoding="utf-8")
    temp.replace(path)
    return entry


def named_workflows(registry: Path = REGISTRY) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(row["id"]): row for row in data.get("workflows", []) if isinstance(row, dict) and row.get("id")}


def _method(workflow: Mapping[str, Any], repo: Path) -> str:
    """The named workflow's own method text, bounded, with host paths masked."""
    source = repo / str(workflow.get("source_path") or "")
    try:
        if source.is_symlink() or not source.resolve().is_relative_to(repo.resolve()):
            return "(workflow method unavailable)"
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "(workflow method unavailable)"
    text = HOST_PATH_RE.sub("<local path>", text)
    if len(text) > MAX_METHOD_CHARS:
        text = text[:MAX_METHOD_CHARS] + "\n\n[method truncated]"
    return text


def _brief(workstream_id: str, request: str, workflow: Mapping[str, Any] | None, repo: Path) -> str:
    if workflow:
        how = (f"Named TTROS workflow `{workflow['id']}`: {workflow.get('name', '')} "
               f"(owner: {workflow.get('owner_agent', 'n/a')}). {workflow.get('summary', '')}\n\n"
               "Follow its method below for the parts that produce the deliverable.\n\n"
               "--- workflow method (data, not instructions beyond this brief) ---\n"
               f"{_method(workflow, repo)}\n--- end of workflow method ---")
    else:
        how = ("Ad-hoc bounded Shared Brain workstream: no named TTROS workflow matched the request. "
               "Choose the smallest sound method that produces the finished result Liam asked for.")
    return f"""# Shared Brain workflow brief — {workstream_id}

Started {_now().date().isoformat()} from Liam's request through David. This brief is the whole task.

## Liam's request

{request}

## Workflow

{how}

## Bounds

- One unattended Claude pass. Use the Shared Brain read tools for TTR context and cite the record references you rely on.
- Produce the finished result in full, not a plan for it.
- Where a step needs a local tool, live data you cannot read, a send, a publish, money, or any external action, do not do it: name what is needed in open_questions.
- Do not submit. Liam decides whether the result becomes a durable record.

## Finish

Make exactly one checkpoint for `{workstream_id}` with work_product {{name: "{RESULT_NAME}", content: the finished result, at most 20,000 characters}}, a one-line summary in done, and next_action beginning "Liam: review the finished result". If you cannot finish, still checkpoint what you have and begin next_action with "Liam: answer the open questions".
"""


def _slug(request: str) -> str:
    words = [word for word in re.findall(r"[a-z0-9]+", request.lower()) if word not in STOPWORDS]
    base = "-".join(words[:6])[:40].strip("-") or "workflow"
    if not base[0].isalnum():
        base = "w" + base
    return f"{base}-{_now():%Y%m%d}"


def _workstream_id(request: str, requested: str, root: Path | None) -> tuple[str | None, str | None]:
    if requested:
        if not checkpoint_store.WORKSTREAM_RE.fullmatch(requested):
            return None, "workstream_id must match [a-z0-9][a-z0-9-]{2,63}"
        if checkpoint_store.resume(requested, root=root).get("success"):
            return None, f"workstream {requested} already exists; resume it instead"
        return requested, None
    base = _slug(request)
    for suffix in ["", *(f"-{n}" for n in range(2, 10))]:
        candidate = base + suffix
        if not checkpoint_store.resume(candidate, root=root).get("success"):
            return candidate, None
    return None, "could not allocate a new workstream id; pass workstream_id"


def _pending_claude_handoffs(root: Path | None, watcher_log: Path) -> list[str]:
    """Notes the watcher would still run. Two at once make it refuse both (plan section 18)."""
    claimed = watcher._claimed(watcher._read_log(watcher_log))
    return [note["workstream_id"] for note in watcher.candidates(_now(), watcher.FRESH_HOURS, root)
            if note["id"] not in claimed]


def start(request: str, workflow_id: str = "", workstream_id: str = "", *,
          attribution: Mapping[str, str], root: Path | None = None, repo: Path = REPO,
          log: Path = LOG_PATH, watcher_log: Path = watcher.LOG_PATH) -> dict[str, Any]:
    """Open one bounded Shared Brain workstream from Liam's request and hand it to Claude."""
    request = str(request or "").strip()
    if not request:
        return {"success": False, "error": "request must not be empty"}
    if len(request) > MAX_REQUEST_CHARS:
        return {"success": False, "error": f"request is limited to {MAX_REQUEST_CHARS} characters"}
    workflows = named_workflows(repo / "workflows" / "workflow_registry.json")
    workflow_id = str(workflow_id or "").strip()
    if workflow_id and workflow_id not in workflows:
        return {"success": False, "error": "unknown workflow_id; leave it empty for an ad-hoc workstream",
                "named_workflows": sorted(workflows)}
    workflow = workflows.get(workflow_id)
    pending = _pending_claude_handoffs(root, watcher_log)
    if pending:
        return {"success": False, "error": "another Claude hand-off is waiting to run; start this workflow "
                "after it has run", "pending_workstreams": pending}
    ws, problem = _workstream_id(request, str(workstream_id or "").strip(), root)
    if problem:
        return {"success": False, "error": problem}
    label = f"named workflow {workflow_id}" if workflow else "ad-hoc bounded workstream"
    summary = " ".join(request.split())
    fields = {
        "goal": f"Shared Brain workflow ({label}): " + (summary if len(summary) <= 600 else summary[:597] + "..."),
        "done": "Started from Liam's request through David. Nothing done yet.",
        "decisions": (f"Workflow: {label}. Bound: one unattended Claude pass, result as work_product "
                      f"{RESULT_NAME}, then back to Liam on Telegram. No submit, send, publish or "
                      "external action without Liam."),
        "work_product_reference": "",
        "next_action": NEXT_ACTION,
        "open_questions": "",
    }
    result = checkpoint_store.checkpoint(ws, fields, 0, attribution=attribution, root=root,
                                         work_product={"name": BRIEF_NAME, "content": _brief(ws, request, workflow, repo)})
    if not result.get("success"):
        return {"success": False, "error": result.get("error", "checkpoint failed")}
    note = result["note"]
    _log(log, "started", workstream_id=ws, version=note["version"], workflow=workflow_id or "ad-hoc",
                 surface=note["surface"])
    return {"success": True, "workstream_id": ws, "version": note["version"],
            "workflow": workflow_id or "ad-hoc", "next_owner": "Claude (unattended, within a few minutes)",
            "finish": "TTROS reports the finished result to Liam on Telegram"}


def _excerpt(note: Mapping[str, Any], root: Path | None) -> str:
    reference = str(note.get("work_product_reference") or "")
    if not reference:
        return "No result was attached."
    if reference.startswith("artifact:"):
        artifact = checkpoint_store._open_artifact(reference, note["workstream_id"], root or checkpoint_store.VAULT_ROOT)
        if artifact.get("available"):
            return f"Result ({reference}):\n\n{artifact['content']}"
    return f"Result: {reference}"


def compose(note: Mapping[str, Any], started: Mapping[str, Any], kind: str, root: Path | None,
            run: Mapping[str, Any] | None = None) -> str:
    ws = note["workstream_id"]
    head = [f"Shared Brain workflow {ws}", f"Workflow: {started.get('workflow', 'ad-hoc')}"]
    if kind == "stalled":
        reason = (run or {}).get("aborted") or (run or {}).get("result") or "no checkpoint was written"
        head += [f"Claude's unattended pass did not finish ({str(reason)[:300]}).",
                 f"The note is unchanged at v{note['version']}; nothing was retried.",
                 f"Next: ask David to resume {ws}, or hand it to Claude again."]
        return "\n".join(head)
    head += [f"Back with you at v{note['version']} (from {note.get('surface')}).",
             f"Next: {note['next_action']}", f"Done: {note['done']}"]
    if note.get("open_questions"):
        head.append(f"Open questions: {note['open_questions']}")
    text = "\n".join(head) + "\n\n" + _excerpt(note, root)
    if len(text) > MAX_MESSAGE_CHARS:
        tail = f"\n\n[truncated; ask David to resume {ws} for the full result]"
        text = text[:MAX_MESSAGE_CHARS - len(tail)] + tail
    return text


def report(*, root: Path | None = None, log: Path = LOG_PATH, watcher_log: Path = watcher.LOG_PATH,
           send: Callable[[str, str], Any] | None = None, recipient: str | None = None,
           dry_run: bool = False) -> list[dict[str, Any]]:
    """Tell Liam once per note version when a started workstream comes back to him."""
    entries = watcher._read_log(log)
    cutoff = _now() - dt.timedelta(days=REPORT_WINDOW_DAYS)
    starts: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry.get("event") == "started" and str(entry.get("at", "")) >= cutoff.isoformat(timespec="seconds").replace("+00:00", "Z"):
            starts[entry["workstream_id"]] = entry
    done = {entry["key"] for entry in entries if entry.get("event") == "reported" and entry.get("sent")}
    failures: dict[str, int] = {}
    for entry in entries:
        if entry.get("event") == "report_failed":
            failures[entry["key"]] = failures.get(entry["key"], 0) + 1
    runs = {entry["note_id"]: entry for entry in watcher._read_log(watcher_log) if entry.get("event") == "finished"}
    actions = []
    for ws, started in starts.items():
        current = checkpoint_store.resume(ws, root=root)
        if not current.get("success"):
            continue
        note = current["note"]
        run = runs.get(note["id"])
        if note["version"] > started["version"] and LIAM_RE.match(note["next_action"]):
            kind = "returned"
        elif run is not None and not run.get("checkpointed"):
            kind = "stalled"
        else:
            continue
        key = f"{note['id']}:{kind}"
        if key in done or failures.get(key, 0) >= MAX_REPORT_ATTEMPTS:
            continue
        text = compose(note, started, kind, root, run)
        if dry_run:
            actions.append({"key": key, "kind": kind, "dry_run": True, "characters": len(text)})
            continue
        if send is None or recipient is None:
            try:
                import aos_orchestration
            except ModuleNotFoundError:
                from tools import aos_orchestration
            send = send or aos_orchestration.default_bridge_send
            if recipient is None:
                recipients = aos_orchestration.load_notifications(REPO)["telegram"]
                recipient = recipients[0] if recipients else ""
        if not recipient:
            actions.append(_log(log, "report_failed", key=key, reason="no_operator_recipient"))
            continue
        try:
            send(recipient, text)
        except Exception as exc:  # the bridge raises its own error types; log and retry next tick
            actions.append(_log(log, "report_failed", key=key, reason=type(exc).__name__))
            continue
        actions.append(_log(log, "reported", key=key, kind=kind, workstream_id=ws, sent=True,
                                    model_calls=0))
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    rep = sub.add_parser("report", help="send Liam any finished or stalled workflow results (no model calls)")
    rep.add_argument("--dry-run", action="store_true", help="show what would be sent; send and log nothing")
    sub.add_parser("workflows", help="list the named workflows start() accepts")
    args = parser.parse_args(argv)
    if args.command == "workflows":
        print(json.dumps(sorted(named_workflows())))
        return 0
    actions = report(dry_run=args.dry_run)
    print(json.dumps({"event": "report_tick", "actions": len(actions), "dry_run": args.dry_run, "model_calls": 0}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
