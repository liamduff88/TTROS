"""Shared Brain workflow start/finish: open a bounded workstream from Liam's request, report it back.

Start: David's `start_workflow` brain tool calls `start()`. It opens a new workstream note
through the existing `checkpoint()` (expected_version 0) with a working-artifact brief, and
hands the next action to Claude, so the existing Claude handoff watcher runs it unattended.
The brief carries a named TTROS workflow's method (from `workflows/workflow_registry.json`)
or, when none matches, an ad-hoc bounded brief. Where Liam's request routes the work explicitly
(actors, handoffs, his question, the submit, COMPLETE), his route wins and Claude does only its
own part, checkpointing to the next actor he named. Where it is silent, the default bound holds:
one unattended Claude pass; no send, publish or external action; the result comes back as
`work_product` result.md.

Finish: `report()` runs on the same 2-minute timer as the Claude watcher. When a workstream
started here is handed back to Liam (`next_action` begins "Liam"), or Claude's pass for it
ended without a checkpoint, it sends Liam one short Telegram message through the existing
orchestration bridge send: the result's title, the done line and clickable Google Drive links to
the result artifact and its workstream folder. When Claude marks the result finished
(`next_action` "Liam: review the finished result"), it is first closed through the existing
`shared_brain_submit.submit()` (one deliverable record, unconfirmed, idempotency key fixed per
note version, so reruns cannot duplicate it) and the workstream gets one COMPLETE checkpoint
that names the record. A blocked or unfinished result ("Liam: answer the open questions") is
never submitted; it goes back to Liam as a working result. A result that needs Liam's input
starts with the line `TTROS WORKSTREAM <workstream_id> v<version>` and names who resumes.

Answer: when Liam replies on Telegram to that message, the backend passes the replied-to text
to `answer()`. The workstream and version come only from that marker, never from "the latest
pending question". The note is re-read; only if that version is still current and still waiting
for Liam is his answer checkpointed onto the same workstream (expected_version = that version),
with next_action handed to the resume actor: the surface that asked (Claude or ChatGPT), or the
one next_action names after "then". When next_action set what that actor does after the answer
("then ChatGPT should …"), that continuation is carried over verbatim; otherwise the actor gets the
generic finish-or-ask instruction. The existing Claude watcher or ChatGPT wake then continues.
The links come from Drive for Desktop's own local
index of the files it syncs (read-only copy; no API call). Only when no link can be produced is
the result inlined. No model calls. No new queue, store or daemon: the bounded log below records
starts and reports, as the watcher's log does.

Revisit: when the checkpoint note schema, the Claude watcher's assignment rule, the workflow
registry shape, the submit contract, the Telegram reply context or Drive for Desktop's index schema
changes. Last touched: 2026-10-06.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
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
DRIVE_INDEX_GLOB = "/mnt/c/Users/*/AppData/Local/Google/DriveFS/[0-9]*/metadata_sqlite_db"
DRIVE_ID_RE = re.compile(r"[A-Za-z0-9_-]{10,}\Z")
DRIVE_LINK_GRACE = dt.timedelta(minutes=10)
LIAM_RE = re.compile(r"\s*\**\s*liam\b", re.I)
FINISHED_RE = re.compile(r"\s*\**\s*liam\s*:\s*review the finished result", re.I)
# "Liam: COMPLETE. …" from any actor is terminal: nothing for Liam to answer.
COMPLETE_ACTION_RE = re.compile(r"\s*\**\s*(?i:liam)\s*\**\s*:\s*\**\s*COMPLETE\b")
RECORD_ID_RE = re.compile(r"shared-submit-[0-9a-f]{32}")
QUESTION_MARKER = "TTROS WORKSTREAM {ws} v{version}"
QUESTION_MARKER_RE = re.compile(r"TTROS WORKSTREAM ([a-z0-9][a-z0-9-]{2,63}) v([1-9][0-9]{0,8})\Z")
# "Liam: answer the open questions, then ChatGPT should …" names the resume actor explicitly.
THEN_ACTOR_RE = re.compile(r"\bthen\s+\**\s*(claude|chatgpt)\b", re.I)
# … and what that actor does after the answer: "then ChatGPT should record it, submit once, COMPLETE".
CONTINUATION_RE = re.compile(r"\bthen\s+\**\s*(?:claude|chatgpt)\b\**[\s:,-]*(?:should\s+)?(?P<rest>\w.*)", re.I | re.S)
ACTORS = {"claude": "Claude", "chatgpt": "ChatGPT"}
MAX_ANSWER_CHARS = 900
# Who records Liam's Telegram answer: Liam himself, through TTROS's Telegram reply path.
ANSWER_STAMP = {"authenticated_identity": "liam", "surface": "telegram",
                "actor_class": "authorised_client", "surface_source": "telegram-reply"}
# Who closes a finished workflow: TTROS's local workflow layer, acting for the David-started workflow.
FINISH_STAMP = {"authenticated_identity": "david", "surface": "david",
                "actor_class": "authorised_client", "surface_source": "local-workflow"}
COMPLETE_NEXT = "Liam: COMPLETE. Nothing is pending; review the finished result whenever you like."
HOST_PATH_RE = re.compile(r"(?:/(?:home|mnt|tmp|etc|usr|var)/\S*|[A-Za-z]:\\\S*)")
STOPWORDS = set("""a an and the to of for with on in into this that these my me our please can could
would you start run kick off begin shared brain workflow workstream bring back finished result
results it its then i want need idea""".split())

NEXT_ACTION = ("Claude should open the workflow brief in the work product and do the bounded pass it describes. "
               "If Liam's request there routes the work explicitly, do only Claude's part and checkpoint to the "
               "next actor it names; otherwise store the finished result as work_product result.md and set "
               "next_action to 'Liam: review the finished result'.")


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

## Liam's route comes first

If Liam's request above sets an explicit route (which actor does what, handoffs, a question to him, who submits, when it is COMPLETE), that route is authoritative and overrides the defaults below. Do only the part it assigns to Claude, then checkpoint `{workstream_id}` to the next actor it names: next_action begins with that actor ("ChatGPT should …", or "Liam: …" for his question) and carries Liam's later steps forward in his words, including what happens after his answer ("Liam: …, then ChatGPT should …"). Do not do another actor's part, ask Liam a question he routed to someone else, or mark the result finished for Liam's review unless his route says so. The defaults below apply only where his request is silent.

## Bounds

- One unattended Claude pass. Use the Shared Brain read tools for TTR context and cite the record references you rely on.
- Produce the finished result in full, not a plan for it.
- Where a step needs a local tool, live data you cannot read, a send, a publish, money, or any external action, do not do it: name what is needed in open_questions.
- Do not submit it yourself. When you mark the result finished, TTROS records it once as a durable Brain deliverable (unconfirmed) and sends Liam the link.

## Finish

Make exactly one checkpoint for `{workstream_id}` with work_product {{name: "{RESULT_NAME}", content: the finished result, at most 20,000 characters}}, a one-line summary in done, and next_action beginning "Liam: review the finished result". Use that only when the result is finished and needs nothing from Liam. If you cannot finish, are blocked, or need Liam's input, still checkpoint what you have and begin next_action with "Liam: answer the open questions"; that result stays a working artifact and is not submitted.
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


def _pending_claude_handoffs(root: Path | None, watcher_log: Path) -> list[dict[str, Any]]:
    """Notes the watcher would still run; it runs them one per tick, oldest first."""
    claimed = watcher._claimed(watcher._read_log(watcher_log))
    return [note for note in watcher.candidates(_now(), watcher.FRESH_HOURS, root) if note["id"] not in claimed]


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
    label = f"named workflow {workflow_id}" if workflow else "ad-hoc bounded workstream"
    summary = " ".join(request.split())
    goal = f"Shared Brain workflow ({label}): " + (summary if len(summary) <= 600 else summary[:597] + "...")
    # Other workstreams may be waiting for Claude; the same request already waiting is a duplicate start.
    duplicate = [note["workstream_id"] for note in _pending_claude_handoffs(root, watcher_log) if note["goal"] == goal]
    if duplicate:
        return {"success": False, "error": "this workflow is already waiting to run; do not start it again",
                "pending_workstreams": duplicate}
    ws, problem = _workstream_id(request, str(workstream_id or "").strip(), root)
    if problem:
        return {"success": False, "error": problem}
    fields = {
        "goal": goal,
        "done": "Started from Liam's request through David. Nothing done yet.",
        "decisions": (f"Workflow: {label}. Liam's explicit route in the request, if any, wins. Default where it "
                      f"is silent: one unattended Claude pass, result as work_product {RESULT_NAME}; a finished "
                      "result is submitted once as a durable Brain record, then back to Liam on Telegram. "
                      "No send, publish or external action without Liam."),
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


def _drive_indexes() -> list[Path]:
    configured = os.environ.get("TTROS_DRIVEFS_INDEX")
    pattern = configured if configured is not None else DRIVE_INDEX_GLOB
    return sorted(Path(match) for match in glob.glob(pattern)) if pattern else []


def _drive_ids(index: Path, parts: list[str]) -> list[str] | None:
    """Cloud IDs along `My Drive/<parts>` in one Drive for Desktop index, or None.

    Drive for Desktop holds the index open and writes through its WAL, so it is read from a
    private copy; the copy is opened read-only and deleted afterwards."""
    with tempfile.TemporaryDirectory() as temp:
        copy = Path(temp) / "index.db"
        shutil.copyfile(index, copy)
        wal = index.with_name(index.name + "-wal")
        if wal.is_file():
            shutil.copyfile(wal, copy.with_name(copy.name + "-wal"))
        connection = sqlite3.connect(copy)
        try:
            alive = "i.trashed = 0 AND i.is_tombstone = 0"
            rows = connection.execute(
                f"SELECT i.stable_id, i.id FROM items i WHERE i.local_title = 'My Drive' AND i.is_folder = 1 "
                f"AND {alive} AND NOT EXISTS (SELECT 1 FROM stable_parents p WHERE p.item_stable_id = i.stable_id)").fetchall()
            ids = []
            for part in parts:
                if len(rows) != 1:
                    return None
                rows = connection.execute(
                    f"SELECT i.stable_id, i.id FROM items i JOIN stable_parents p ON p.item_stable_id = i.stable_id "
                    f"WHERE p.parent_stable_id = ? AND i.local_title = ? AND {alive}", (rows[0][0], part)).fetchall()
                ids.append(rows[0][1] if len(rows) == 1 else "")
            if len(rows) != 1 or not all(DRIVE_ID_RE.fullmatch(value) and not value.startswith("local") for value in ids):
                return None  # ambiguous, missing, or not yet uploaded (Drive for Desktop's local-* ids)
            return ids
        finally:
            connection.close()


def drive_links(note: Mapping[str, Any], root: Path | None) -> dict[str, str] | None:
    """Clickable Drive links for the note's artifact: {"result", "folder"}; {} when the artifact
    is not on a Drive for Desktop mount with an index here; None when it is but is not indexed yet."""
    reference = str(note.get("work_product_reference") or "")
    path = checkpoint_store._artifact_path(reference, note["workstream_id"], root or checkpoint_store.VAULT_ROOT)
    if path is None or not path.is_file():
        return {}
    parts = list(path.parts)
    if "My Drive" not in parts[:-2]:
        return {}
    parts = parts[parts.index("My Drive") + 1:]
    indexes = _drive_indexes()
    if not indexes:
        return {}
    found = []
    for index in indexes:
        try:
            ids = _drive_ids(index, parts)
        except (OSError, sqlite3.Error):
            ids = None
        if ids:
            found.append(ids)
    if len(found) != 1:
        return None
    return {"result": f"https://drive.google.com/file/d/{found[0][-1]}/view",
            "folder": f"https://drive.google.com/drive/folders/{found[0][-2]}"}


def _title(note: Mapping[str, Any], root: Path | None) -> str:
    reference = str(note.get("work_product_reference") or "")
    if not reference.startswith("artifact:"):
        return ""
    artifact = checkpoint_store._open_artifact(reference, note["workstream_id"], root or checkpoint_store.VAULT_ROOT)
    for line in str(artifact.get("content") or "").splitlines():
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            return title if len(title) <= 200 else title[:197] + "..."
    return ""


def _excerpt(note: Mapping[str, Any], root: Path | None) -> str:
    reference = str(note.get("work_product_reference") or "")
    if not reference:
        return "No result was attached."
    if reference.startswith("artifact:"):
        artifact = checkpoint_store._open_artifact(reference, note["workstream_id"], root or checkpoint_store.VAULT_ROOT)
        if artifact.get("available"):
            return f"No Drive link was available, so here is the result:\n\n{artifact['content']}"
        return "The result file could not be opened; ask David to resume this workstream."
    return f"Result: {reference}"


def _submit_enabled() -> bool:
    return os.environ.get("TTROS_SHARED_BRAIN_SUBMIT", "").strip().lower() in {"1", "true", "yes"}


def _is_complete(note: Mapping[str, Any]) -> bool:
    return note.get("surface_source") == FINISH_STAMP["surface_source"] and str(note.get("done", "")).startswith("COMPLETE.")


def _finished_result(note: Mapping[str, Any], root: Path | None) -> str | None:
    """Claude's finished result text, or None when this note is not one (blocked, unfinished,
    needs Liam's input, not Claude's, or the result file is missing or over the limit)."""
    ws = note["workstream_id"]
    if note.get("surface") != "claude" or not FINISHED_RE.match(str(note.get("next_action", ""))):
        return None
    if note.get("work_product_reference") != f"artifact:{ws}/{RESULT_NAME}":
        return None
    artifact = checkpoint_store._open_artifact(note["work_product_reference"], ws, root or checkpoint_store.VAULT_ROOT)
    content = str(artifact.get("content") or "")
    if not artifact.get("available") or artifact.get("truncated") or not content.strip():
        return None
    return content


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 3] + "..."


def close_finished(note: Mapping[str, Any], content: str, root: Path | None,
                   submit: Callable[..., Mapping[str, Any]]) -> dict[str, Any]:
    """Submit Claude's finished result through the existing submit, once, and mark the note COMPLETE.

    The idempotency key is fixed per note version, so a rerun after a crash returns the same
    record (`duplicate`) instead of a second one; the COMPLETE note is not Claude's, so it is
    never submitted again."""
    ws, version = note["workstream_id"], note["version"]
    title = _title(note, root) or f"Shared Brain workflow result: {ws}"
    try:
        out = submit("deliverable", title, content, [ws], f"workflow-{ws}-v{version}", ws, attribution=FINISH_STAMP)
    except Exception as exc:  # index or Git errors must not stop the other workstreams' reports
        out = {"success": False, "error": type(exc).__name__}
    if not out.get("success"):
        return {"success": False, "error": str(out.get("error") or "submit failed")[:300]}
    record = f"Durable record {out['reference']} ({out.get('status', 'unconfirmed')}), submitted once by TTROS from Claude's finished result v{version}."
    done, decisions = f"COMPLETE. {note['done']}", f"{record} {note['decisions']}".strip()
    for _ in range(12):  # keep the note inside its 2,500-character cap; the full result stays in result.md
        fields = {"goal": note["goal"], "done": _clip(done, checkpoint_store.MAX_FIELD_CHARS),
                  "decisions": _clip(decisions, checkpoint_store.MAX_FIELD_CHARS),
                  "work_product_reference": note["work_product_reference"], "next_action": COMPLETE_NEXT,
                  "open_questions": note["open_questions"]}
        check = checkpoint_store.checkpoint(ws, fields, version, attribution=FINISH_STAMP, root=root, validate_only=True)
        if check.get("success") or "2500" not in str(check.get("error")):
            break
        if len(decisions) > len(record) + 100:
            decisions = decisions[:max(len(record), len(decisions) - 250)]
        else:
            done = done[:max(40, len(done) - 250)]
    written = checkpoint_store.checkpoint(ws, fields, version, attribution=FINISH_STAMP, root=root)
    if not written.get("success"):
        return {"success": False, "error": "submitted, but the COMPLETE checkpoint failed: " + str(written.get("error"))[:200],
                "submit": out}
    return {"success": True, "note": written["note"], "submit": out}


def resume_actor(note: Mapping[str, Any]) -> str | None:
    """Who continues once Liam answers: the actor next_action names after "then", else the
    surface that handed the question to Liam. None when neither is Claude or ChatGPT."""
    named = THEN_ACTOR_RE.search(str(note.get("next_action", "")))
    actor = (named.group(1) if named else str(note.get("surface", ""))).lower()
    return actor if actor in ACTORS else None


def awaiting_liam(note: Mapping[str, Any]) -> bool:
    """Handed to Liam for input; a finished or COMPLETE result is not waiting for an answer."""
    action = str(note.get("next_action", ""))
    return (bool(LIAM_RE.match(action)) and not FINISHED_RE.match(action)
            and not COMPLETE_ACTION_RE.match(action) and not _is_complete(note))


def question_marker(note: Mapping[str, Any]) -> str:
    """First line of a Telegram question Liam can answer by replying; empty when the reply
    could not be routed (not waiting for Liam, or no resume actor recorded)."""
    if not awaiting_liam(note) or resume_actor(note) is None:
        return ""
    return QUESTION_MARKER.format(ws=note["workstream_id"], version=note["version"])


def parse_marker(text: str) -> tuple[str, int] | None:
    """(workstream_id, version) from the first non-empty line of a replied-to message, or None."""
    for line in str(text or "").splitlines():
        if line.strip():
            match = QUESTION_MARKER_RE.fullmatch(line.strip())
            return (match.group(1), int(match.group(2))) if match else None
    return None


def answer(reply_text: str, answer_text: str, *, root: Path | None = None) -> dict[str, Any]:
    """Record Liam's Telegram reply to a workstream question on that same workstream.

    `{"handled": False}` when the replied-to message carries no TTROS question marker: the
    caller continues with the normal David conversation. Otherwise the result is handled, and
    `message` tells Liam what happened. The optimistic version check in `checkpoint()` makes a
    reply to a superseded version fail safely even if the note moves during this call."""
    marker = parse_marker(reply_text)
    if marker is None:
        return {"handled": False}
    ws, version = marker

    def rejected(reason: str, message: str) -> dict[str, Any]:
        return {"handled": True, "success": False, "reason": reason, "workstream_id": ws,
                "version": version, "message": message + " Nothing was recorded."}

    text = str(answer_text or "").strip()
    if not text:
        return rejected("empty_answer", f"Your reply to {ws} v{version} was empty.")
    if len(text) > MAX_ANSWER_CHARS:
        return rejected("answer_too_long", f"Your reply to {ws} v{version} is over {MAX_ANSWER_CHARS} characters; "
                        f"shorten it, or ask David to resume {ws}.")
    current = checkpoint_store.resume(ws, root=root)
    if not current.get("success"):
        return rejected("unknown_workstream", f"Workstream {ws} could not be read.")
    note = current["note"]
    stale = (f"That question ({ws} v{version}) is out of date: the workstream is now at v{note['version']}, "
             f"next: {_clip(note['next_action'], 200)}")
    if note["version"] != version:
        return rejected("stale", stale)
    if not awaiting_liam(note):
        return rejected("not_waiting", f"{ws} v{version} is not waiting for your answer.")
    actor = resume_actor(note)
    if actor is None:
        return rejected("no_resume_actor", f"{ws} v{version} does not record who continues after your answer; "
                        f"ask David to resume {ws}.")
    name, reference = ACTORS[actor], note["work_product_reference"]
    keep = f", keep the result as work_product {reference.split('/', 1)[1]}" if reference.startswith("artifact:") else ""
    answered = f"Liam's answer (Telegram reply to v{version}): {text}"
    asked = f" Asked: {note['open_questions']}" if note["open_questions"] else ""
    continuation = CONTINUATION_RE.search(note["next_action"])
    if continuation:  # what Liam's route set for after his answer stays the instruction, verbatim
        next_action = (f"{name} should continue {ws} with Liam's answer in open_questions{keep}, then do what "
                       f"was set for after his answer: {continuation.group('rest').strip()}")
    else:
        next_action = (f"{name} should continue {ws} with Liam's answer in open_questions{keep}, and set "
                       "next_action to 'Liam: review the finished result' when it is finished, or "
                       "'Liam: answer the open questions' if it is still blocked.")
    fields = {"goal": note["goal"], "done": note["done"], "decisions": note["decisions"],
              "work_product_reference": reference,
              "next_action": next_action,  # never clipped: an over-long one fails the write, nothing lost
              "open_questions": _clip(answered + asked, checkpoint_store.MAX_FIELD_CHARS)}
    if not checkpoint_store.checkpoint(ws, fields, version, attribution=ANSWER_STAMP, root=root,
                                       validate_only=True).get("success"):
        fields["open_questions"] = answered  # the question itself stays in the previous version
    written = checkpoint_store.checkpoint(ws, fields, version, attribution=ANSWER_STAMP, root=root)
    if not written.get("success"):
        error = str(written.get("error") or "checkpoint failed")
        if "stale" in error:
            return rejected("stale", f"That question ({ws} v{version}) was answered or moved on meanwhile.")
        if "2500" in error:
            return rejected("answer_too_long", f"Your reply does not fit in the {ws} note; shorten it.")
        return rejected("checkpoint_failed", f"Your answer to {ws} v{version} could not be saved ({error[:200]}).")
    new = written["note"]
    how = ("Claude picks it up within a few minutes." if actor == "claude"
           else "ChatGPT is woken by email; its hourly check is the fallback.")
    return {"handled": True, "success": True, "workstream_id": ws, "answered_version": version,
            "version": new["version"], "resume_actor": name,
            "message": f"Recorded your answer on {ws} (v{version} -> v{new['version']}). {how}"}


def compose(note: Mapping[str, Any], started: Mapping[str, Any], kind: str, root: Path | None,
            run: Mapping[str, Any] | None = None, links: Mapping[str, str] | None = None,
            submit_error: str = "") -> str:
    text = _compose_body(note, started, kind, root, run, links, submit_error)
    marker = question_marker(note) if kind == "returned" else ""
    if not marker:
        return text
    head = marker + "\n"
    tail = (f"\n\nReply to this message to answer; {ACTORS[resume_actor(note)]} continues "
            f"{note['workstream_id']} with your answer.")
    return head + text[:MAX_MESSAGE_CHARS - len(head) - len(tail)] + tail


def _compose_body(note: Mapping[str, Any], started: Mapping[str, Any], kind: str, root: Path | None,
                  run: Mapping[str, Any] | None = None, links: Mapping[str, str] | None = None,
                  submit_error: str = "") -> str:
    ws = note["workstream_id"]
    head = [f"Shared Brain workflow {ws}", f"Workflow: {started.get('workflow', 'ad-hoc')}"]
    if kind == "stalled":
        reason = (run or {}).get("aborted") or (run or {}).get("result") or "no checkpoint was written"
        head += [f"Claude's unattended pass did not finish ({str(reason)[:300]}).",
                 f"The note is unchanged at v{note['version']}; nothing was retried.",
                 f"Next: ask David to resume {ws}, or hand it to Claude again."]
        return "\n".join(head)
    complete = kind == "complete"
    done = note["done"].removeprefix("COMPLETE. ") if complete else note["done"]
    record = RECORD_ID_RE.search(note.get("decisions", "")) if complete else None
    if complete:
        saved = [f"Saved to the Brain as a durable record{' ' + record.group(0) if record else ''} (unconfirmed)."]
    else:
        saved = [f"Not saved to the Brain: the durable submit failed ({submit_error})."] if submit_error else []
    next_line = "Next: nothing pending; review the result whenever you like." if complete else f"Next: {note['next_action']}"
    if links:
        title = _title(note, root)
        lines = [f"Shared Brain workflow {'COMPLETE' if complete else 'finished'}: {ws}", *([title] if title else []),
                 f"Done: {done}"]
        if note.get("open_questions"):
            lines.append(f"Open questions: {note['open_questions']}")
        lines += [*saved, f"Result: {links['result']}", f"Folder: {links['folder']}", next_line]
        text = "\n".join(lines)
        return text if len(text) <= MAX_MESSAGE_CHARS else text[:MAX_MESSAGE_CHARS]
    if complete:
        head[0] = f"Shared Brain workflow COMPLETE: {ws}"
        head += [*saved, next_line, f"Done: {done}"]
    else:
        head += [f"Back with you at v{note['version']} (from {note.get('surface')}).", *saved,
                 next_line, f"Done: {done}"]
    if note.get("open_questions"):
        head.append(f"Open questions: {note['open_questions']}")
    text = "\n".join(head) + "\n\n" + _excerpt(note, root)
    if len(text) > MAX_MESSAGE_CHARS:
        tail = f"\n\n[truncated; ask David to resume {ws} for the full result]"
        text = text[:MAX_MESSAGE_CHARS - len(tail)] + tail
    return text


def report(*, root: Path | None = None, log: Path = LOG_PATH, watcher_log: Path = watcher.LOG_PATH,
           send: Callable[[str, str], Any] | None = None, recipient: str | None = None,
           submit: Callable[..., Mapping[str, Any]] | None = None,
           dry_run: bool = False) -> list[dict[str, Any]]:
    """Tell Liam once per note version when a started workstream comes back to him; close a
    finished result through the existing submit first."""
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
            kind = "complete" if _is_complete(note) else "returned"
        elif run is not None and not run.get("checkpointed"):
            kind = "stalled"
        else:
            continue
        key = f"{note['id']}:{kind}"
        if key in done or failures.get(key, 0) >= MAX_REPORT_ATTEMPTS:
            continue
        submit_error = ""
        content = _finished_result(note, root) if kind == "returned" and _submit_enabled() else None
        submit_key = f"{note['id']}:submit"
        if content is not None and failures.get(submit_key, 0) < MAX_REPORT_ATTEMPTS:
            if dry_run:
                actions.append({"key": submit_key, "kind": "complete", "dry_run": True, "would_submit": True})
                continue
            if submit is None:
                try:
                    import shared_brain_submit
                except ModuleNotFoundError:
                    from tools import shared_brain_submit
                submit = shared_brain_submit.submit
            closed = close_finished(note, content, root, submit)
            if not closed["success"]:
                actions.append(_log(log, "report_failed", key=submit_key, reason=closed["error"],
                                    reference=(closed.get("submit") or {}).get("reference", "")))
                continue  # retried next tick with the same key; after the bound, sent as a working result
            out = closed["submit"]
            actions.append(_log(log, "submitted", key=submit_key, workstream_id=ws, reference=out["reference"],
                                record_id=out["record_id"], commit=out.get("commit", ""),
                                sync_status=out.get("sync_status", ""), duplicate=bool(out.get("duplicate")),
                                complete_version=closed["note"]["version"], model_calls=0))
            note, kind = closed["note"], "complete"
            key = f"{note['id']}:{kind}"
        elif content is not None:
            submit_error = f"{MAX_REPORT_ATTEMPTS} attempts; see the workflow log"
        links = drive_links(note, root) if kind in {"returned", "complete"} else {}
        if links is None:
            updated = dt.datetime.fromisoformat(str(note.get("updated") or "1970-01-01T00:00:00Z").replace("Z", "+00:00"))
            if _now() - updated < DRIVE_LINK_GRACE:
                continue  # Drive for Desktop has not uploaded it yet; try again next tick
        text = compose(note, started, kind, root, run, links, submit_error)
        if dry_run:
            actions.append({"key": key, "kind": kind, "dry_run": True, "characters": len(text),
                            "drive_link": bool(links)})
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
                            reference=note.get("work_product_reference") or "",
                            drive_link=(links or {}).get("result", ""), model_calls=0))
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
