from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import argparse
import importlib.util
import json
import datetime
import webbrowser
import os
import re
import shlex
import subprocess

app = FastAPI(title="Agentic OS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3010", "http://localhost:3010"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _aos_root() -> Path:
    configured = os.environ.get("AOS_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


BASE_DIR = _aos_root()
PACKETS_DIR = BASE_DIR / "packets"
LOGS_DIR = BASE_DIR / "logs"
RESULTS_DIR = BASE_DIR / "results"
CONNECTORS_DIR = BASE_DIR / "connectors"
CONNECTORS_FILE = CONNECTORS_DIR / "CONNECTORS.md"
DATA_DIR = BASE_DIR / "dashboard" / "data"
QUEUE_TOOL = BASE_DIR / "tools" / "aos-queue.py"

for d in [PACKETS_DIR, LOGS_DIR, RESULTS_DIR, CONNECTORS_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

TRACKER_FILE = DATA_DIR / "tracker.json"
TOKEN_USAGE_FILE = LOGS_DIR / "token_usage.jsonl"
CLAUDE_USAGE_READER_WSL = "/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live/dashboard/backend/claude_usage.py"

ENTITIES = [
    {
        "id": "claude-code",
        "name": "Claude Code",
        "role": "AI Coding Assistant",
        "status": "live_wsl",
        "statusLabel": "Live via AgenticOSClean",
        "command": "aos-claude",
        "commandHint": "Runs headlessly through AgenticOSClean via Hermes Run Panel",
        "commandType": "wsl",
        "capabilities": ["Code generation", "Debugging", "Refactoring", "File editing", "Shell execution"],
        "launchable": False,
        "description": "Claude Code is installed in AgenticOSClean and is launched headlessly through Hermes → Claude.",
    },
    {
        "id": "codex",
        "name": "Codex",
        "role": "AI Coding Assistant (OpenAI)",
        "status": "live_wsl",
        "statusLabel": "Live via AgenticOSClean",
        "command": "aos-codex",
        "commandHint": "Runs headlessly through AgenticOSClean via Hermes Run Panel or Direct Codex",
        "commandType": "wsl",
        "capabilities": ["Code completion", "Function synthesis", "Test generation", "Documentation"],
        "launchable": False,
        "description": "Codex is installed in AgenticOSClean and is launched headlessly through Hermes → Codex or Direct Codex.",
    },
    {
        "id": "antigravity",
        "name": "Antigravity",
        "role": "Strategy & Coordination",
        "status": "windows_operator",
        "statusLabel": "Windows dashboard builder/operator UI",
        "command": "",
        "commandHint": "Windows operator surface for dashboard and UI work",
        "commandType": "none",
        "capabilities": ["Strategic analysis", "Task coordination", "Workflow design", "Decision framing"],
        "launchable": False,
        "description": "Antigravity is the Windows dashboard builder and operator UI surface.",
    },
    {
        "id": "chatgpt",
        "name": "ChatGPT",
        "role": "General AI Assistant",
        "status": "browser_only",
        "statusLabel": "Browser/operator strategy",
        "command": "https://chatgpt.com",
        "commandHint": "Opens in default browser",
        "commandType": "url",
        "capabilities": ["General reasoning", "Writing", "Research", "Analysis", "Image generation"],
        "launchable": True,
        "description": "ChatGPT runs in the browser for strategy, prompt design, and operator decisions.",
    },
    {
        "id": "hermes",
        "name": "Hermes",
        "role": "Agent Coordinator",
        "status": "live_router",
        "statusLabel": "Live router via AgenticOSClean",
        "command": "aos-hermes",
        "commandHint": "Runs inside AgenticOSClean WSL distro — use the controls below",
        "commandType": "wsl",
        "capabilities": ["Agent orchestration", "Memory routing", "Task delegation", "Multi-agent coordination"],
        "launchable": True,
        "description": "Hermes is the live router in AgenticOSClean. Use the Run Panel to check status and route tasks to Codex or Claude.",
    },
    {
        "id": "local-vault",
        "name": "Local Vault / Obsidian",
        "role": "Knowledge Base",
        "status": "local_live",
        "statusLabel": "Agentic OS Live only",
        "command": r"C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live",
        "commandHint": "Opens the Agentic OS Live folder",
        "commandType": "path",
        "capabilities": ["Note storage", "Reference lookup", "Packet archive", "Results review"],
        "launchable": True,
        "description": "Agentic OS Live is the only live local workspace. Old vault/runtime folders are archive only.",
    },
]

ALLOWLISTED_LAUNCHERS = {
    "chatgpt": {"type": "browser", "url": "https://chatgpt.com"},
    "local-vault": {"type": "folder", "path": str(BASE_DIR)},
    "hermes": {"type": "wsl", "note": "Use /api/wsl/* endpoints"},
}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "workspace": str(BASE_DIR),
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


@app.get("/api/entities")
def get_entities():
    return {"entities": ENTITIES}


@app.get("/api/overview")
def get_overview():
    packets = list(PACKETS_DIR.glob("*"))
    logs = list(LOGS_DIR.glob("*"))
    results = list(RESULTS_DIR.glob("*"))
    tracker = json.loads(TRACKER_FILE.read_text()) if TRACKER_FILE.exists() else {}
    token_rollup = _token_usage_rollup()
    return {
        "totalPackets": len(packets),
        "totalLogs": len(logs),
        "totalResults": len(results),
        "activeAgents": 0,
        "estimatedValue": tracker.get("estimatedValue", 0),
        "tokenUsage": token_rollup,
        **token_rollup,
        "version": "0.1.0",
    }



@app.get("/api/packets")
def get_packets():
    entries = []
    for f in sorted(PACKETS_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
        if f.is_file():
            try:
                entries.append({
                    "name": f.name,
                    "content": f.read_text(encoding="utf-8", errors="replace"),
                    "modified": datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })
            except Exception:
                pass
    return {"packets": entries}


@app.get("/api/logs")
def get_logs():
    entries = []
    for f in sorted(LOGS_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
        if f.is_file():
            try:
                entries.append({
                    "name": f.name,
                    "content": f.read_text(encoding="utf-8", errors="replace"),
                    "modified": datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })
            except Exception:
                pass
    return {"logs": entries}


@app.get("/api/results")
def get_results():
    entries = []
    for f in sorted(RESULTS_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)[:20]:
        if f.is_file():
            try:
                entries.append({
                    "name": f.name,
                    "content": f.read_text(encoding="utf-8", errors="replace"),
                    "modified": datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })
            except Exception:
                pass
    return {"results": entries}



@app.get("/api/connectors")
def get_connectors():
    if not CONNECTORS_FILE.exists():
        return {
            "exists": False,
            "path": str(CONNECTORS_FILE),
            "updated": None,
            "content": "",
            "items": [],
        }

    stat = CONNECTORS_FILE.stat()
    content = CONNECTORS_FILE.read_text(encoding="utf-8", errors="replace")
    items = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and "—" in stripped:
            name, detail = stripped[2:].split("—", 1)
            items.append({"name": name.strip(), "detail": detail.strip()})
        elif stripped.startswith("- ") and ":" in stripped:
            name, detail = stripped[2:].split(":", 1)
            items.append({"name": name.strip(), "detail": detail.strip()})

    return {
        "exists": True,
        "path": str(CONNECTORS_FILE),
        "updated": stat.st_mtime,
        "content": content,
        "items": items,
    }


@app.get("/api/tracker")
def get_tracker():
    if TRACKER_FILE.exists():
        return json.loads(TRACKER_FILE.read_text())
    return {"hourlyRate": 150, "estimatedHoursSaved": 0, "estimatedValue": 0}


class TrackerUpdate(BaseModel):
    hourlyRate: float
    estimatedHoursSaved: float


@app.post("/api/tracker")
def update_tracker(data: TrackerUpdate):
    existing = json.loads(TRACKER_FILE.read_text()) if TRACKER_FILE.exists() else {}
    existing["hourlyRate"] = data.hourlyRate
    existing["estimatedHoursSaved"] = data.estimatedHoursSaved
    existing["estimatedValue"] = round(data.hourlyRate * data.estimatedHoursSaved, 2)
    existing["updatedAt"] = datetime.datetime.utcnow().isoformat() + "Z"
    TRACKER_FILE.write_text(json.dumps(existing, indent=2))
    return existing


class PacketCreate(BaseModel):
    target: str
    preset: str
    task: str


class QueueItemCreate(BaseModel):
    title: str
    owner: str = "unassigned"
    priority: str | int = "normal"
    tags: str = ""
    context: str = ""
    sources: str = ""
    definition_of_done: str = ""
    allowed_actions: str = "local_read,local_edit,local_test"
    stop_conditions: str = "external_send,secrets_exposure,destructive_action_outside_scope"


class QueueReceiptAttach(BaseModel):
    receipt_text: str
    status: str | None = None


class QueueStatusUpdate(BaseModel):
    status: str


@app.post("/api/packets")
def create_packet(packet: PacketCreate):
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"packet_{ts}.json"
    data = {
        "id": ts,
        "target": packet.target,
        "preset": packet.preset,
        "task": packet.task,
        "created": datetime.datetime.utcnow().isoformat() + "Z",
        "status": "pending",
    }
    (PACKETS_DIR / filename).write_text(json.dumps(data, indent=2))
    return {"success": True, "filename": filename, "packet": data}


@app.post("/api/launchers/{entity_id}/launch")
def launch_entity(entity_id: str):
    if entity_id not in ALLOWLISTED_LAUNCHERS:
        return {
            "success": False,
            "message": f"Not connected yet — launcher for '{entity_id}' requires a clean install path configured in v0.2+.",
        }
    launcher = ALLOWLISTED_LAUNCHERS[entity_id]
    if launcher["type"] == "browser":
        webbrowser.open(launcher["url"])
        return {"success": True, "message": f"Opened {launcher['url']} in browser"}
    if launcher["type"] == "folder":
        os.startfile(launcher["path"])
        return {"success": True, "message": f"Opened folder: {launcher['path']}"}
    if launcher["type"] == "wsl":
        return {"success": True, "message": "Use the Hermes Run panel to interact with WSL agents."}
    return {"success": False, "message": "Unknown launcher type"}


# ---------------------------------------------------------------------------
# WSL / AgenticOSClean runtime endpoints
# ---------------------------------------------------------------------------

WSL_ENV = 'export PATH="$HOME/.local/npm/bin:$HOME/.local/bin:$PATH"'
WSL_DISTRO = "AgenticOSClean"
WSL_USER = "liam"
COMPOSIO_PATH = "/home/liam/.composio:/home/liam/.local/bin:/home/liam/.composio:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/usr/lib/wsl/lib"
HERMES_COORDINATOR = BASE_DIR / "tools" / "aos-hermes-coordinator.sh"


def _path_for_wsl_command(path) -> str:
    raw = str(path)
    match = re.match(r"^([A-Za-z]):[\\/](.*)$", raw)
    if not match:
        return raw
    drive, rest = match.groups()
    return f"/mnt/{drive.lower()}/{rest.replace(chr(92), '/')}"


def _run_wsl(bash_cmd: str, timeout: int = 60) -> dict:
    """Run a bash command inside the AgenticOSClean WSL distro and return output."""
    full_cmd = f"{WSL_ENV}; {bash_cmd}"
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", WSL_DISTRO, "--user", WSL_USER, "--", "bash", "-lc", full_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        success = result.returncode == 0
        output = stdout if stdout else stderr
        return {
            "success": success,
            "output": output or "(no output)",
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": f"Command timed out after {timeout}s", "returncode": -1}
    except FileNotFoundError:
        return {"success": False, "output": "wsl.exe not found — WSL not available on this machine", "returncode": -1}
    except Exception as e:
        return {"success": False, "output": f"Error: {e}", "returncode": -1}


_CLOSEOUT_FIELDS = (
    "Files touched",
    "Validation",
    "Connector access",
    "Token usage",
    "Blockers",
    "Next action",
)

_HERMES_ANSWER_LIMIT = 1400
_ANSI_ESCAPE_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _field_from_output(output: str, label: str) -> str | None:
    # A closeout value is deliberately one line.  Consuming subsequent lines
    # risks relaying transcript, prompt, session, or sandbox details.
    match = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*([^\r\n]*)", output)
    if not match:
        return None
    value = match.group(1).strip(" -*\t")
    if re.search(
        r"(?i)(?:session\s*id|prompt\s*dump|command\s*transcript|raw\s+(?:codex|claude|hermes\s+)?transcript|sandbox\s+(?:metadata|mode|permissions))",
        value,
    ):
        return None
    return value[:700] or None


def _clean_hermes_stream(value: object) -> str:
    """Remove terminal control sequences while preserving native Hermes text."""
    return _ANSI_ESCAPE_RE.sub("", str(value or "")).strip()


def _hermes_useful_output(result: dict) -> tuple[str, str] | None:
    """Return full persisted content and the best user-facing Hermes answer."""
    stdout = _clean_hermes_stream(result.get("stdout"))
    stderr = _clean_hermes_stream(result.get("stderr"))
    fallback = _clean_hermes_stream(result.get("output"))
    if not stdout and not stderr and fallback not in {"", "(no output)"}:
        stdout = fallback

    sections = []
    if stdout:
        sections.append(("stdout", stdout))
    if stderr and stderr != stdout:
        sections.append(("stderr", stderr))
    if not sections:
        return None

    full_text = "\n\n".join(f"## Hermes {name}\n\n{text}" for name, text in sections)
    answer = stdout or stderr
    boilerplate = re.sub(r"[\s*`#._-]+", " ", answer).strip().upper()
    if boilerplate in {"PASS", "NEEDS ATTENTION"}:
        return None
    return full_text, answer


def _write_hermes_result(content: str) -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"hermes_{timestamp}.md"
    (RESULTS_DIR / filename).write_text(content.rstrip() + "\n", encoding="utf-8")
    return filename


def _bounded_hermes_answer(answer: str, limit: int = _HERMES_ANSWER_LIMIT) -> str:
    compact = re.sub(r"\n{3,}", "\n\n", answer).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _extract_token_usage(*outputs: str) -> tuple[dict, str]:
    """Extract only token values explicitly emitted by an agent CLI."""
    output = "\n".join(str(value) for value in outputs if value)
    if re.search(r"(?im)^\s*Token usage\s*:\s*no agent invocation\s*$", output):
        return (
            {"available": False, "no_agent_invocation": True},
            "Token usage: no agent invocation",
        )

    fields: dict[str, str] = {}
    patterns = {
        "input_tokens": r"(?im)^\s*(?:input|prompt)[ _-]*tokens?\s*[:=]\s*(\d(?:[\d,]*\d)?)",
        "output_tokens": r"(?im)^\s*(?:output|completion)[ _-]*tokens?\s*[:=]\s*(\d(?:[\d,]*\d)?)",
        "cached_input_tokens": r"(?im)^\s*cached[ _-]*(?:input[ _-]*)?tokens?\s*[:=]\s*(\d(?:[\d,]*\d)?)",
        "total_tokens": r"(?im)^\s*total[ _-]*tokens?\s*[:=]\s*(\d(?:[\d,]*\d)?)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            fields[key] = match.group(1)

    used = re.search(
        r"(?im)^\s*tokens?\s+used\s*(?::|=|\r?\n)\s*(\d(?:[\d,]*\d)?)",
        output,
    )
    if used and "total_tokens" not in fields:
        fields["total_tokens"] = used.group(1)

    labeled = _field_from_output(output, "Token usage")
    if labeled and "unavailable" not in labeled.lower() and "no agent invocation" not in labeled.lower():
        for key, label in (("input_tokens", "input"), ("output_tokens", "output"), ("cached_input_tokens", "cached"), ("total_tokens", "total")):
            match = re.search(rf"(?i)\b{label}(?:[ _-]*tokens?)?\s*[:=]?\s*(\d(?:[\d,]*\d)?)", labeled)
            if match and key not in fields:
                fields[key] = match.group(1)
        if not fields:
            bare = re.fullmatch(r"[\d,]+", labeled.strip())
            if bare:
                fields["total_tokens"] = bare.group(0)

    if not fields:
        return {"available": False}, "Token usage: unavailable from current CLI output"

    labels = {
        "input_tokens": "input",
        "output_tokens": "output",
        "cached_input_tokens": "cached input",
        "total_tokens": "total",
    }
    ordered_fields = {key: fields[key] for key in labels if key in fields}
    summary = ", ".join(f"{labels[key]} {value}" for key, value in ordered_fields.items())
    return {"available": True, **ordered_fields}, f"Token usage: {summary}"


def _parse_record_timestamp(value: object) -> datetime.datetime | None:
    try:
        parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
    except (TypeError, ValueError):
        return None


def _known_total(record: dict) -> int | None:
    usage = record.get("token_usage") or {}
    if usage.get("available") is not True or "total_tokens" not in usage:
        return None
    value = usage.get("total_tokens")
    if isinstance(value, bool):
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _read_token_usage_records() -> list[dict]:
    if not TOKEN_USAGE_FILE.exists():
        return []
    records = []
    try:
        for line in TOKEN_USAGE_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
                if isinstance(record, dict):
                    records.append(record)
            except (json.JSONDecodeError, TypeError):
                continue
    except OSError:
        return []
    return records


def _read_claude_local_usage() -> dict:
    """Read aggregate counters from Liam's Claude Code JSONL without transcript content."""
    command = f"python3 {shlex.quote(CLAUDE_USAGE_READER_WSL)}"
    result = _run_wsl(command, timeout=15)
    if not result.get("success"):
        return {
            "available": False,
            "accuracy_label": "Unavailable: Claude Code local usage reader could not run",
        }
    try:
        usage = json.loads(result.get("stdout") or result.get("output") or "")
    except (json.JSONDecodeError, TypeError):
        return {
            "available": False,
            "accuracy_label": "Unavailable: Claude Code local usage reader returned invalid data",
        }
    return usage if isinstance(usage, dict) else {
        "available": False,
        "accuracy_label": "Unavailable: Claude Code local usage reader returned invalid data",
    }


def _token_usage_rollup(records: list[dict] | None = None, now: datetime.datetime | None = None) -> dict:
    records = _read_token_usage_records() if records is None else records
    now = now or datetime.datetime.now().astimezone()
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    local_tz = now.tzinfo
    today = now.date()
    week_start = today - datetime.timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    totals = {"today": 0, "week": 0, "month": 0, "all_time": 0}
    unavailable_today = 0
    no_agent_today = 0
    dated_records = []

    for position, record in enumerate(records):
        timestamp = _parse_record_timestamp(record.get("timestamp"))
        local_date = timestamp.astimezone(local_tz).date() if timestamp else None
        dated_records.append((timestamp, position, record))
        no_agent = bool(record.get("no_agent_invocation") or (record.get("token_usage") or {}).get("no_agent_invocation"))
        if local_date == today:
            no_agent_today += int(no_agent)
            unavailable = record.get("unavailable") is True or (record.get("token_usage") or {}).get("available") is False
            unavailable_today += int(not no_agent and unavailable)
        total = _known_total(record)
        if total is None:
            continue
        totals["all_time"] += total
        if local_date is not None and month_start <= local_date <= today:
            totals["month"] += total
        if local_date is not None and week_start <= local_date <= today:
            totals["week"] += total
        if local_date == today:
            totals["today"] += total

    dated_records.sort(key=lambda item: (item[0] or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), item[1]), reverse=True)
    task_records = [item for item in dated_records if not (item[2].get("no_agent_invocation") or (item[2].get("token_usage") or {}).get("no_agent_invocation"))]
    latest = task_records[0][2] if task_records else {}
    recent_activity = []
    for _, _, record in dated_records[:10]:
        no_agent = bool(record.get("no_agent_invocation") or (record.get("token_usage") or {}).get("no_agent_invocation"))
        unavailable = record.get("unavailable") is True or (record.get("token_usage") or {}).get("available") is False
        recent_activity.append({
            "timestamp": record.get("timestamp"),
            "route": record.get("route"),
            "agent": record.get("agent"),
            "status": record.get("status") or ("no agent invocation" if no_agent else "unavailable" if unavailable else "completed"),
            "token_usage_text": record.get("token_usage_text") or "Token usage: unavailable",
            "task": record.get("task"),
        })

    return {
        "last_task_token_usage_text": latest.get("token_usage_text", "Token usage: no task recorded"),
        "last_task_route": latest.get("route") or latest.get("agent"),
        "last_task_timestamp": latest.get("timestamp"),
        "known_tokens_today": totals["today"],
        "known_tokens_this_week": totals["week"],
        "known_tokens_this_month": totals["month"],
        "known_tokens_all_time": totals["all_time"],
        "unavailable_count_today": unavailable_today,
        "no_agent_invocation_count_today": no_agent_today,
        "recent_activity": recent_activity,
        "claude_local_usage": _read_claude_local_usage(),
    }


def _latest_token_usage() -> dict:
    """Compatibility wrapper for callers expecting the former helper."""
    return _token_usage_rollup()


def _log_token_usage(
    route: str,
    agent: str,
    task: str,
    token_usage: dict,
    token_usage_text: str,
    route_metadata: dict | None = None,
) -> dict:
    record = {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "route": route,
        "agent": agent,
        "task": task,
        "source": "dashboard/backend",
        "token_usage_text": token_usage_text,
        "token_usage": token_usage,
        "unavailable": not token_usage.get("available", False),
        "no_agent_invocation": False,
        **(route_metadata or {}),
    }
    with TOKEN_USAGE_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _compact_agent_closeout(
    result: dict,
    route: str,
    agent: str,
    task: str,
    route_metadata: dict | None = None,
) -> dict:
    """Return only the operator closeout; never relay a raw agent transcript."""
    raw = str(result.get("output") or "")
    agent_reported_failure = bool(re.search(r"(?im)^\s*NEEDS ATTENTION\s*$", raw))
    passed = bool(result.get("success")) and not agent_reported_failure
    token_usage, token_usage_text = _extract_token_usage(
        raw, str(result.get("stdout") or ""), str(result.get("stderr") or "")
    )
    values = {
        "Files touched": _field_from_output(raw, "Files touched") or "None reported",
        "Validation": _field_from_output(raw, "Validation") or ("Agent command completed" if passed else "Agent command failed"),
        "Connector access": _field_from_output(raw, "Connector access") or "No connector action reported",
        "Token usage": token_usage_text.removeprefix("Token usage: "),
        "Blockers": _field_from_output(raw, "Blockers") or ("None" if passed else "See local agent logs"),
        "Next action": _field_from_output(raw, "Next action") or ("None" if passed else "Review the local agent failure"),
    }
    output = "\n".join(["PASS" if passed else "NEEDS ATTENTION"] + [f"{key}: {values[key]}" for key in _CLOSEOUT_FIELDS])
    metadata = route_metadata or {
        "requested_target": route,
        "selected_route": route,
        "delegation_reason": "direct API route",
        "codex_forbidden": "no",
    }
    _log_token_usage(route, agent, task, token_usage, token_usage_text, metadata)
    return {
        "success": passed,
        "output": output,
        "returncode": result.get("returncode", -1),
        "token_usage": token_usage,
        "token_usage_text": token_usage_text,
        **metadata,
    }


def _hermes_coordinator_closeout(result: dict, task: str, route_metadata: dict) -> dict:
    """Add native Hermes output to its closeout without changing other routes."""
    closeout = _compact_agent_closeout(result, "hermes", "hermes", task, route_metadata)
    useful = _hermes_useful_output(result)
    if useful is None:
        return closeout

    full_text, answer = useful
    filename = _write_hermes_result(full_text)
    lines = closeout["output"].splitlines()
    # The protected Telegram bridge relays only established closeout fields.
    # Mirror the useful payload into those fields while retaining dedicated
    # Answer/Result lines for the dashboard response.
    relay_answer = re.sub(r"\s+", " ", answer).strip()
    relay_answer = _bounded_hermes_answer(relay_answer, 700)
    lines = [
        f"Files touched: results/{filename}" if line.startswith("Files touched:")
        else f"Validation: Answer: {relay_answer}" if line.startswith("Validation:")
        else line
        for line in lines
    ]
    lines.insert(1, f"Result file: {filename}")
    lines.insert(1, f"Answer: {_bounded_hermes_answer(answer)}")
    closeout["output"] = "\n".join(lines)
    closeout["result_file"] = filename
    return closeout


@app.get("/api/composio/connections")
def composio_connections():
    """Read the current Composio connections without changing account state."""
    result = _run_wsl(
        f"export PATH={COMPOSIO_PATH}; composio connections list",
        timeout=30,
    )
    raw_output = result["output"]

    if result["success"]:
        try:
            return {
                "success": True,
                "format": "json",
                "connections": json.loads(raw_output),
            }
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "success": result["success"],
        "format": "raw",
        "raw": raw_output,
        "returncode": result["returncode"],
    }


@app.get("/api/wsl/status")
def wsl_status():
    """Check aos-hermes status inside AgenticOSClean."""
    result = _run_wsl("aos-hermes status")
    result["output"] = f"{result.get('output', '').rstrip()}\nToken usage: no agent invocation".lstrip()
    result["token_usage"] = {"available": False, "no_agent_invocation": True}
    result["token_usage_text"] = "Token usage: no agent invocation"
    return result


class TaskRun(BaseModel):
    task: str


# Commands deliberately use only read/info slugs already evidenced by the local
# Composio cache, workspace results, or CLI binary.  Toolkits without a locally
# evidenced zero-argument read slug are checked through the shared registry
# instead of guessing an action name or arguments.
COMPOSIO_SMOKE_CHECKS = (
    ("Gmail", "tool-run", "GMAIL_FETCH_EMAILS", {"max_results": 1, "ids_only": True, "include_payload": False}),
    ("LinkedIn", "tool-info", "LINKEDIN_GET_COMPANY_INFO", None),
    ("YouTube", "tool-info", "YOUTUBE_LIST_CHANNEL_VIDEOS", None),
    ("Google Drive", "registry-status", "googledrive", None),
    ("Google Calendar", "tool-info", "GOOGLECALENDAR_FIND_EVENT", None),
    ("Google Docs", "registry-status", "googledocs", None),
    ("Google Sheets", "registry-status", "googlesheets", None),
    ("GitHub", "tool-info", "GITHUB_GET_THE_AUTHENTICATED_USER", None),
)

_COMPOSIO_ACTION_TASK_RE = re.compile(
    r"^\s*(?:run\s+)?composio\s+action\s+([A-Z][A-Z0-9_]+)\s+(\{.*\})\s*[.!]?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_COMPOSIO_SMOKE_TASK_RE = re.compile(
    r"\bcomposio\b.*\b(?:spine|connector)\b.*\b(?:check|smoke|status|test)\b|"
    r"\b(?:check|smoke|test)\b.*\bcomposio\b.*\b(?:spine|connectors?)\b",
    re.IGNORECASE,
)

_CODEX_FORBIDDEN_RE = re.compile(
    r"\b(?:"
    r"(?:do\s+not|don['’]t|never)\s+(?:use|delegate\s+to|route\s+to|send\s+(?:this\s+)?to)\s+codex"
    r"|(?:do\s+not|don['’]t)\s+want\s+codex\s+to"
    r")\b",
    re.IGNORECASE,
)
_EXPLICIT_TARGET_RE = {
    target: re.compile(
        rf"\b(?:get|tell|use)\s+{target}\b|\b(?:get|tell)\s+{target}\s+to\b",
        re.IGNORECASE,
    )
    for target in ("codex", "claude", "hermes")
}
_QUEUE_CREATE_PREFIX = "Add this to the queue:"
_QUEUE_CREATE_RE = re.compile(rf"^{re.escape(_QUEUE_CREATE_PREFIX)}", re.IGNORECASE)
_QUEUE_LIST_PREFIX = "List queue:"
_QUEUE_LIST_RE = re.compile(rf"^{re.escape(_QUEUE_LIST_PREFIX)}", re.IGNORECASE)
_QUEUE_STATUSES = (
    "inbox",
    "agent_todo",
    "agent_working",
    "needs_input",
    "human_review",
    "done",
    "blocked",
    "cancelled",
)
_ACTIVE_QUEUE_STATUSES = tuple(status for status in _QUEUE_STATUSES if status not in {"done", "cancelled"})
_QUEUE_OWNER_RE = {
    owner: re.compile(rf"\b{re.escape(owner)}\b", re.IGNORECASE)
    for owner in ("codex", "claude", "revenue", "marketing", "delivery", "operations")
}


def _load_queue_tool():
    spec = importlib.util.spec_from_file_location("aos_queue", QUEUE_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("Queue tool could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _queue_create_text(task: str) -> str | None:
    match = _QUEUE_CREATE_RE.match(task)
    if not match:
        return None
    return task[match.end():].strip()


def _queue_status_filter(task: str) -> tuple[bool, str | None, dict | None]:
    stripped = task.strip()
    if stripped.lower() == "list queue":
        return True, None, None
    match = _QUEUE_LIST_RE.match(stripped)
    if not match:
        return False, None, None
    status = stripped[match.end():].strip().lower()
    if status not in _QUEUE_STATUSES:
        output = "\n".join((
            "NEEDS ATTENTION",
            f"Invalid queue status: {status or '(empty)'}",
            "Next action: Use one of inbox, agent_todo, agent_working, needs_input, human_review, done, blocked, cancelled.",
        ))
        return True, None, {
            "success": False,
            "output": output,
            "returncode": 2,
            "requested_target": "queue",
            "selected_route": "local_queue_list",
            "delegation_reason": "invalid exact queue-list status",
            "codex_forbidden": "no",
        }
    return True, status, None


def _queue_items_path() -> Path:
    return BASE_DIR / "queue" / "work_items.jsonl"


def _queue_templates_dir() -> Path:
    return BASE_DIR / "queue" / "templates"


def _read_queue_items() -> list[dict]:
    path = _queue_items_path()
    if not path.exists():
        return []
    items = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid queue JSONL at line {line_number}: {exc.msg}") from exc
        if isinstance(item, dict):
            items.append(item)
    return items


def _queue_find_item(item_id: str) -> dict:
    for item in _read_queue_items():
        if item.get("id") == item_id:
            return item
    raise KeyError(item_id)


def _queue_split_text(value: object) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    parts = []
    for line in text.splitlines():
        parts.extend(part.strip() for part in line.split(",") if part.strip())
    return parts


def _queue_priority_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    text = str(value or "normal").strip().lower()
    mapping = {"low": 1, "normal": 5, "high": 8, "urgent": 10}
    if text in mapping:
        return mapping[text]
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError("priority must be low, normal, high, urgent, or an integer") from exc


def _queue_create_dashboard_item(body: QueueItemCreate) -> dict:
    title = body.title.strip()
    if not title:
        raise ValueError("title must not be empty")
    owner = body.owner.strip().lower() or "unassigned"
    if owner not in {"unassigned", "hermes", "codex", "claude", "revenue", "marketing", "delivery", "operations"}:
        raise ValueError(f"Unknown owner: {owner}")
    queue_tool = _load_queue_tool()
    args = argparse.Namespace(
        title=title,
        requested_by="Liam",
        owner_type="agent",
        owner=owner,
        status="agent_todo",
        priority=_queue_priority_value(body.priority),
        source="dashboard",
        tags=",".join(_queue_split_text(body.tags)),
        context=body.context.strip(),
        sources=",".join(_queue_split_text(body.sources)),
        allowed_actions=",".join(_queue_split_text(body.allowed_actions)) or "local_read,local_edit,local_test",
        stop_conditions=",".join(_queue_split_text(body.stop_conditions)) or "external_send,secrets_exposure,destructive_action_outside_scope",
        definition_of_done=body.definition_of_done.strip(),
    )
    return queue_tool.create_item(BASE_DIR, args)


def _queue_validate_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized not in _QUEUE_STATUSES:
        raise ValueError("invalid status; use one of inbox, agent_todo, agent_working, needs_input, human_review, done, blocked, cancelled")
    return normalized


def _queue_receipt_path(item_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", item_id).strip("-") or "receipt"
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (Path("queue") / "receipts" / f"{safe_id}-{timestamp}.md").as_posix()


def _queue_write_receipt(item_id: str, receipt_text: str) -> str:
    text = receipt_text.strip()
    if not text:
        raise ValueError("receipt_text must not be empty")
    receipt_path = _queue_receipt_path(item_id)
    target = BASE_DIR / receipt_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text.rstrip() + "\n", encoding="utf-8")
    return receipt_path


def _queue_receipt_artifact(relative_path: str) -> tuple[str, str]:
    path_text = str(relative_path or "").strip()
    if not path_text:
        raise ValueError("receipt path is required")
    candidate = Path(path_text)
    if candidate.is_absolute():
        raise ValueError("receipt path must be root-relative")

    receipts_dir = (BASE_DIR / "queue" / "receipts").resolve()
    target = (BASE_DIR / candidate).resolve()
    try:
        target.relative_to(receipts_dir)
    except ValueError as exc:
        raise ValueError("receipt path must stay under queue/receipts") from exc
    if target.name == ".gitkeep" or not target.is_file():
        raise FileNotFoundError(path_text)
    root_relative = target.relative_to(BASE_DIR.resolve()).as_posix()
    return root_relative, target.read_text(encoding="utf-8", errors="replace")


def _queue_detail_item(item: dict) -> dict:
    public = _queue_public_item(item)
    public.update({
        "requested_by": item.get("requested_by", ""),
        "owner_type": item.get("owner_type", ""),
        "source": item.get("source", ""),
        "tags": item.get("tags") or [],
        "context": item.get("context", ""),
        "sources": item.get("sources") or [],
        "allowed_actions": item.get("allowed_actions") or [],
        "stop_conditions": item.get("stop_conditions") or [],
        "definition_of_done": item.get("definition_of_done", ""),
        "claim": item.get("claim") or {"claimed_by": None, "claimed_at": None},
        "receipts": item.get("receipts") or [],
    })
    return public


def _queue_item_sort_key(item: dict) -> tuple[int, str, str]:
    try:
        priority = int(item.get("priority", 0))
    except (TypeError, ValueError):
        priority = 0
    return (-priority, str(item.get("created_at", "")), str(item.get("id", "")))


def _queue_next_action(items: list[dict], counts: dict[str, int] | None = None) -> str:
    counts = counts or {status: sum(1 for item in items if item.get("status") == status) for status in _QUEUE_STATUSES}
    if counts.get("needs_input", 0) or counts.get("human_review", 0) or counts.get("blocked", 0):
        return "Review needs_input, human_review, or blocked items first."
    if counts.get("agent_working", 0):
        return "Let active agent_working items continue and review new inbox items."
    if counts.get("agent_todo", 0):
        return "Claim the next agent_todo item."
    if counts.get("inbox", 0):
        return "Triage inbox items into agent_todo or owner-specific work."
    return "Add a queue item or continue normal Hermes work."


def _queue_status_closeout() -> dict:
    try:
        items = _read_queue_items()
    except ValueError as exc:
        return {
            "success": False,
            "output": "\n".join(("NEEDS ATTENTION", f"Queue status unavailable: {exc}", "Next action: Repair queue/work_items.jsonl.")),
            "returncode": 2,
            "requested_target": "queue",
            "selected_route": "local_queue_status",
            "delegation_reason": "exact queue-status intent",
            "codex_forbidden": "no",
        }
    counts = {status: sum(1 for item in items if item.get("status") == status) for status in _QUEUE_STATUSES}
    needs_liam = counts["needs_input"] + counts["human_review"] + counts["blocked"]
    output = "\n".join((
        "PASS",
        "Queue status:",
        *[f"  - {status}: {counts[status]}" for status in _QUEUE_STATUSES],
        "Needs Liam:",
        f"  - {needs_liam}",
        "Next action:",
        f"  - {_queue_next_action(items, counts)}",
    ))
    return {
        "success": True,
        "output": output,
        "returncode": 0,
        "requested_target": "queue",
        "selected_route": "local_queue_status",
        "delegation_reason": "exact queue-status intent",
        "codex_forbidden": "no",
    }


def _queue_public_item(item: dict) -> dict:
    return {
        "id": item.get("id", ""),
        "title": item.get("title", ""),
        "status": item.get("status", ""),
        "owner": item.get("owner", "unassigned"),
        "priority": item.get("priority", 0),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


def _queue_active_items(items: list[dict]) -> list[dict]:
    return sorted(
        [item for item in items if item.get("status") in _ACTIVE_QUEUE_STATUSES],
        key=_queue_item_sort_key,
    )


@app.get("/api/queue/summary")
def queue_summary():
    """Read local queue state for the dashboard without mutating the queue."""
    try:
        items = _read_queue_items()
    except ValueError as exc:
        return {
            "success": False,
            "message": "Queue unavailable",
            "reason": str(exc),
            "counts": {status: 0 for status in _QUEUE_STATUSES},
            "needsLiam": 0,
            "activeItems": [],
            "nextItem": None,
        }

    counts = {status: sum(1 for item in items if item.get("status") == status) for status in _QUEUE_STATUSES}
    needs_liam = counts["needs_input"] + counts["human_review"] + counts["blocked"]
    active_items = _queue_active_items(items)
    return {
        "success": True,
        "counts": counts,
        "needsLiam": needs_liam,
        "activeCount": len(active_items),
        "activeItems": [_queue_public_item(item) for item in active_items[:10]],
        "nextItem": _queue_public_item(active_items[0]) if active_items else None,
        "nextAction": _queue_next_action(active_items, counts),
    }


@app.get("/api/queue/status")
def queue_status():
    """Read-only dashboard queue status."""
    return queue_summary()


@app.get("/api/queue/items")
def queue_items():
    """List local queue items without mutating or launching anything."""
    try:
        items = sorted(_read_queue_items(), key=_queue_item_sort_key)
    except ValueError as exc:
        return {"success": False, "message": "Queue unavailable", "reason": str(exc), "items": []}
    return {"success": True, "items": [_queue_detail_item(item) for item in items]}


@app.get("/api/queue/items/{item_id}")
def queue_item(item_id: str):
    """Return one local queue item."""
    try:
        return {"success": True, "item": _queue_detail_item(_queue_find_item(item_id))}
    except KeyError:
        raise HTTPException(status_code=404, detail="queue item not found")
    except ValueError as exc:
        return {"success": False, "message": "Queue unavailable", "reason": str(exc), "item": None}


@app.get("/api/queue/next")
def queue_next():
    """Return the next active local queue item without claiming it."""
    try:
        active_items = _queue_active_items(_read_queue_items())
    except ValueError as exc:
        return {"success": False, "message": "Queue unavailable", "reason": str(exc), "item": None}
    return {"success": True, "item": _queue_detail_item(active_items[0]) if active_items else None}


@app.post("/api/queue/items")
def create_queue_item(body: QueueItemCreate):
    """Create one local queue item; never invoke agents or connectors."""
    try:
        item = _queue_create_dashboard_item(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"success": True, "item": _queue_detail_item(item)}


@app.post("/api/queue/items/{item_id}/status")
def update_queue_item_status(item_id: str, body: QueueStatusUpdate):
    """Update one local queue item status; never invoke agents or connectors."""
    try:
        status = _queue_validate_status(body.status)
        _queue_find_item(item_id)
        item = _load_queue_tool().update_status(BASE_DIR, item_id, status)
    except KeyError:
        raise HTTPException(status_code=404, detail="queue item not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "success": True, "item_id": item_id, "status": item.get("status"), "item": _queue_detail_item(item)}


@app.post("/api/queue/items/{item_id}/receipt")
def attach_queue_item_receipt(item_id: str, body: QueueReceiptAttach):
    """Persist a pasted local receipt and attach its root-relative path."""
    try:
        status = _queue_validate_status(body.status) if body.status is not None else None
        _queue_find_item(item_id)
        receipt_path = _queue_write_receipt(item_id, body.receipt_text)
        item = _load_queue_tool().attach_receipt(BASE_DIR, item_id, receipt_path, status)
    except KeyError:
        raise HTTPException(status_code=404, detail="queue item not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "ok": True,
        "success": True,
        "item_id": item_id,
        "receipt_path": receipt_path,
        "status": item.get("status"),
        "item": _queue_detail_item(item),
    }


@app.get("/api/queue/receipt")
def queue_receipt(path: str):
    """Read one local receipt artifact without mutating queue state."""
    try:
        receipt_path, content = _queue_receipt_artifact(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="receipt not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"success": True, "path": receipt_path, "content": content}


def _queue_render_list(values: object) -> str:
    items = values if isinstance(values, list) else _queue_split_text(values)
    clean = [str(item).strip() for item in items if str(item).strip()]
    return "\n".join(f"- {item}" for item in clean) if clean else "- None provided"


DEPARTMENT_PROMPT_TARGETS = {"hermes", "revenue", "marketing", "delivery", "operations"}


def _queue_read_text(relative_path: str) -> str:
    return (BASE_DIR / relative_path).read_text(encoding="utf-8")


def _queue_department_card_path(owner: str) -> str | None:
    if owner in {"revenue", "marketing", "delivery", "operations"}:
        return f"agents/{owner}.card.md"
    return None


def _queue_render_hermes_department_prompt(item: dict, target: str) -> str:
    template = _queue_read_text("queue/templates/department_task.prompt.md")
    owner = str(item.get("owner") or "unassigned").strip().lower()
    card_path = _queue_department_card_path(target)
    card_content = (
        _queue_read_text(card_path).strip()
        if card_path
        else "No single department card applies. Operating Hermes should inspect queue/card/context as needed."
    )
    card_reference = f"- `{card_path}`" if card_path else "- `agents/*.card.md` when routing requires a department lane"
    if target == "hermes":
        routing_instruction = (
            "Operating Hermes should coordinate directly, inspect the queue item, registry, card/context references, "
            "and source refs as needed, then decide the next route without creating bureaucracy."
        )
    else:
        routing_instruction = (
            f"Operating Hermes should operate through the `{target}` department card as the scoped lane. "
            "This is a routing lane, not a separate runtime."
        )
    replacements = {
        "<AOS-ID>": item.get("id", ""),
        "<TITLE>": item.get("title", ""),
        "<OWNER_OR_AGENT>": owner,
        "<STATUS>": item.get("status") or "unavailable",
        "<CONTEXT>": item.get("context") or "No additional context provided.",
        "<SOURCE_REFERENCES>": _queue_render_list(item.get("sources") or []),
        "<ALLOWED_ACTIONS>": _queue_render_list(item.get("allowed_actions") or []),
        "<STOP_CONDITIONS>": _queue_render_list(item.get("stop_conditions") or []),
        "<DEFINITION_OF_DONE>": item.get("definition_of_done") or "Complete or route the scoped queue item and return the required closeout.",
        "<CARD_REFERENCE>": card_reference,
        "<ROUTING_INSTRUCTION>": routing_instruction,
        "<CARD_CONTENT>": card_content,
    }
    prompt = template
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, str(value))
    return prompt.rstrip() + "\n"


def _queue_render_prompt(item: dict, target: str) -> str:
    if target in DEPARTMENT_PROMPT_TARGETS:
        return _queue_render_hermes_department_prompt(item, target)
    if target not in {"codex", "claude"}:
        raise ValueError("invalid target")
    template_path = _queue_templates_dir() / f"{target}_task.prompt.md"
    template = template_path.read_text(encoding="utf-8")
    launch = (
        'wsl -d AgenticOSClean --user liam -- bash -lc \'export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$HOME/.composio:$PATH"; command -v codex; codex --version; cd "/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live"; codex --sandbox workspace-write --ask-for-approval never\''
        if target == "codex"
        else 'wsl -d AgenticOSClean --user liam -- bash -lc \'export PATH="$HOME/.local/bin:$HOME/.local/npm/bin:$HOME/.composio:$PATH"; cd "/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live"; aos-claude\''
    )
    replacements = {
        "<WORK_SCOPE>": item.get("title") or "Local queue item",
        "<AOS-ID>": item.get("id", ""),
        "<OWNER_OR_AGENT>": item.get("owner", "unassigned"),
        "<TITLE>": item.get("title", ""),
        "<CONTEXT>": item.get("context") or "No additional context provided.",
        "<SOURCE_REFERENCES>": _queue_render_list(item.get("sources") or []),
        "<ALLOWED_ACTIONS>": _queue_render_list(item.get("allowed_actions") or []),
        "<STOP_CONDITIONS>": _queue_render_list(item.get("stop_conditions") or []),
        "<DEFINITION_OF_DONE>": item.get("definition_of_done") or "Complete the scoped queue item and return the required closeout.",
        "<VALIDATION_COMMANDS_OR_CHECKS>": "Run relevant local validation for the scoped change. Do not call external systems.",
    }
    prompt = template
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, str(value))
    return "\n".join((
        prompt.rstrip(),
        "",
        "## Launch from PowerShell",
        "",
        'cd "C:\\Users\\Admin\\Documents\\A-Time to revenue\\Agentic OS Live"',
        "",
        launch,
        "",
        "## Manual Launch",
        "",
        "Paste this prompt into the workbench manually. Do not launch agents automatically.",
        "",
    ))


@app.get("/api/queue/items/{item_id}/prompt")
def queue_item_prompt(item_id: str, target: str):
    """Generate a manual workbench prompt from local templates."""
    normalized = target.strip().lower()
    if normalized not in {"codex", "claude"} | DEPARTMENT_PROMPT_TARGETS:
        raise HTTPException(status_code=400, detail="invalid target; use codex, claude, hermes, revenue, marketing, delivery, or operations")
    try:
        item = _queue_find_item(item_id)
        prompt = _queue_render_prompt(item, normalized)
    except KeyError:
        raise HTTPException(status_code=404, detail="queue item not found")
    except ValueError as exc:
        return {"success": False, "message": "Queue unavailable", "reason": str(exc), "prompt": ""}
    except OSError as exc:
        return {"success": False, "message": "Queue unavailable", "reason": f"Prompt template unavailable: {exc}", "prompt": ""}
    return {"success": True, "target": normalized, "item_id": item_id, "prompt": prompt}


def _queue_list_closeout(status: str | None = None) -> dict:
    try:
        items = _read_queue_items()
    except ValueError as exc:
        return {
            "success": False,
            "output": "\n".join(("NEEDS ATTENTION", f"Queue list unavailable: {exc}", "Next action: Repair queue/work_items.jsonl.")),
            "returncode": 2,
            "requested_target": "queue",
            "selected_route": "local_queue_list",
            "delegation_reason": "exact queue-list intent",
            "codex_forbidden": "no",
        }
    filtered = [
        item for item in items
        if (item.get("status") == status if status else item.get("status") in _ACTIVE_QUEUE_STATUSES)
    ]
    rows = [
        f"  - {item.get('id', '')} | {item.get('status', '')} | {item.get('owner', 'unassigned')} | {item.get('title', '')}"
        for item in sorted(filtered, key=_queue_item_sort_key)[:10]
    ] or ["  - None"]
    output = "\n".join((
        "PASS",
        "Queue items:",
        *rows,
        "Next action:",
        f"  - {_queue_next_action(filtered)}",
    ))
    return {
        "success": True,
        "output": output,
        "returncode": 0,
        "requested_target": "queue",
        "selected_route": "local_queue_list",
        "delegation_reason": "exact queue-list intent" if status is None else "exact queue-list status intent",
        "codex_forbidden": "no",
    }


def _try_queue_read_task(task: str) -> dict | None:
    if task.strip().lower() == "queue status":
        return _queue_status_closeout()
    is_queue_list, status, invalid = _queue_status_filter(task)
    if invalid is not None:
        return invalid
    if is_queue_list:
        return _queue_list_closeout(status)
    return None


def _infer_queue_owner(text: str) -> str:
    for owner, pattern in _QUEUE_OWNER_RE.items():
        if pattern.search(text):
            return owner
    return "unassigned"


def _create_queue_item(text: str) -> dict:
    queue_tool = _load_queue_tool()
    owner = _infer_queue_owner(text)
    args = argparse.Namespace(
        title=text,
        requested_by="hermes",
        owner_type="agent",
        owner=owner,
        status="inbox",
        priority=0,
        source="dashboard/backend/hermes",
        tags="hermes,queue",
        context="",
        sources="",
        allowed_actions="",
        stop_conditions="",
        definition_of_done="",
    )
    return queue_tool.create_item(BASE_DIR, args)


def _queue_create_closeout(item: dict) -> dict:
    output = "\n".join((
        "PASS",
        f"Work item ID: {item['id']}",
        f"Owner: {item['owner']}",
        f"Status: {item['status']}",
        "Next action: Review or claim the local queue item",
    ))
    return {
        "success": True,
        "output": output,
        "returncode": 0,
        "work_item_id": item["id"],
        "owner": item["owner"],
        "status": item["status"],
        "next_action": "Review or claim the local queue item",
        "requested_target": "queue",
        "selected_route": "local_queue",
        "delegation_reason": "exact queue-create prefix",
        "codex_forbidden": "no",
    }


def _select_hermes_entry_route(task: str) -> dict:
    """Select only explicit agents; all other decisions belong to Hermes."""
    codex_forbidden = bool(_CODEX_FORBIDDEN_RE.search(task))
    if _EXPLICIT_TARGET_RE["hermes"].search(task):
        requested_target = "hermes"
        selected_route = "hermes_coordinator"
        reason = "explicit Hermes request"
    elif _EXPLICIT_TARGET_RE["claude"].search(task):
        requested_target = "claude"
        selected_route = "direct_claude"
        reason = "explicit Claude request"
    elif _EXPLICIT_TARGET_RE["codex"].search(task) and not codex_forbidden:
        requested_target = "codex"
        selected_route = "direct_codex"
        reason = "explicit Codex request"
    else:
        requested_target = "unspecified"
        selected_route = "hermes_coordinator"
        reason = "Codex forbidden by operator" if codex_forbidden else "default coordinator route"
    return {
        "requested_target": requested_target,
        "selected_route": selected_route,
        "delegation_reason": reason,
        "codex_forbidden": "yes" if codex_forbidden else "no",
    }


def _run_composio_adapter(mode: str, subject: str | None = None, json_args: dict | None = None) -> dict:
    """Call the one shared Composio adapter; never create per-connector paths."""
    workspace = "/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live"
    command = (
        f"cd {shlex.quote(workspace)}; python3 connectors/composio_access_adapter.py "
        f"{shlex.quote(mode)}"
    )
    if subject is not None:
        command += f" {shlex.quote(subject)}"
    if json_args is not None:
        payload = json.dumps(json_args, separators=(",", ":"))
        command += f" {shlex.quote(payload)}"
    result = _run_wsl(command, timeout=120)
    try:
        parsed = json.loads(result["output"])
        return parsed if isinstance(parsed, dict) else {"ok": False, "error": "Adapter returned non-object JSON"}
    except (json.JSONDecodeError, TypeError):
        return {"ok": False, "error": result["output"]}


def _registry_toolkit_is_active(toolkit: str, registry: dict | None = None) -> bool:
    try:
        if registry is None:
            registry_file = CONNECTORS_DIR / "composio_tool_registry.json"
            registry = json.loads(registry_file.read_text(encoding="utf-8"))
        record = next(item for item in registry["toolkits"] if item.get("slug") == toolkit)
        accounts = record["connection_evidence"]["accounts"]
        return int(accounts.get("ACTIVE", 0)) > 0
    except (OSError, ValueError, KeyError, StopIteration, TypeError):
        return False


def _composio_closeout(results: list[tuple[str, bool, str]]) -> dict:
    passed = all(ok for _, ok, _ in results)
    summary = "; ".join(f"{name}={'PASS' if ok else 'FAIL'} ({detail})" for name, ok, detail in results)
    output = "\n".join((
        "PASS" if passed else "NEEDS ATTENTION",
        "Files touched: None",
        f"Validation: {'Read-only Composio spine check completed' if passed else 'One or more Composio spine checks failed'}",
        f"Connector access: {summary}",
        "Token usage: no agent invocation",
        f"Blockers: {'None' if passed else 'See failed connector checks above'}",
        "Next action: None" if passed else "Next action: Review the failed shared-adapter check",
    ))
    return {"success": passed, "output": output, "returncode": 0 if passed else 2}


def _try_composio_task(task: str) -> dict | None:
    """Recognize explicit generic actions and the read-only operator smoke task."""
    action = _COMPOSIO_ACTION_TASK_RE.fullmatch(task)
    if action:
        tool_slug = action.group(1).upper()
        try:
            json_args = json.loads(action.group(2))
        except json.JSONDecodeError as exc:
            return _composio_closeout([("Composio action", False, f"invalid JSON: {exc.msg}")])
        if not isinstance(json_args, dict):
            return _composio_closeout([("Composio action", False, "arguments must be a JSON object")])
        response = _run_composio_adapter("tool-run", tool_slug, json_args)
        detail = "shared adapter returned ok" if response.get("ok") else str(response.get("error", "adapter failed"))[:180]
        return _composio_closeout([(tool_slug, bool(response.get("ok")), detail)])

    if not _COMPOSIO_SMOKE_TASK_RE.search(task):
        return None

    results: list[tuple[str, bool, str]] = []
    registry_response: dict | None = None
    for name, mode, subject, args in COMPOSIO_SMOKE_CHECKS:
        if mode == "registry-status":
            if registry_response is None:
                registry_response = _run_composio_adapter("registry")
            ok = bool(registry_response.get("toolkits")) and _registry_toolkit_is_active(subject, registry_response)
            results.append((name, ok, "active local registry connection" if ok else "no active local registry connection"))
            continue
        response = _run_composio_adapter(mode, subject, args)
        detail = "shared adapter returned ok" if response.get("ok") else str(response.get("error", "adapter failed"))[:180]
        results.append((name, bool(response.get("ok")), detail))
    return _composio_closeout(results)


@app.post("/api/wsl/hermes")
def wsl_hermes(body: TaskRun):
    """Use Hermes by default; bypass it only for explicit agent requests."""
    if not body.task.strip():
        raise HTTPException(status_code=422, detail="task must not be empty")
    queue_text = _queue_create_text(body.task)
    if queue_text is not None:
        if not queue_text:
            raise HTTPException(status_code=422, detail="queue item text must not be empty")
        return _queue_create_closeout(_create_queue_item(queue_text))
    queue_read = _try_queue_read_task(body.task)
    if queue_read is not None:
        return queue_read
    metadata = _select_hermes_entry_route(body.task)
    safe_task = body.task.replace("'", "'\\''")
    selected_route = metadata["selected_route"]
    if selected_route == "direct_codex":
        command, route, agent = f"aos-codex '{safe_task}'", "codex", "codex"
    elif selected_route == "direct_claude":
        command, route, agent = f"aos-hermes claude '{safe_task}'", "claude", "claude"
    else:
        command = f"{shlex.quote(_path_for_wsl_command(HERMES_COORDINATOR))} '{safe_task}'"
        route, agent = "hermes", "hermes"
    result = _run_wsl(command, timeout=120)
    if selected_route == "hermes_coordinator":
        return _hermes_coordinator_closeout(result, body.task, metadata)
    return _compact_agent_closeout(result, route, agent, body.task, metadata)


@app.post("/api/wsl/claude")
def wsl_claude(body: TaskRun):
    """Route a task through aos-hermes to Claude inside AgenticOSClean."""
    if not body.task.strip():
        raise HTTPException(status_code=422, detail="task must not be empty")
    safe_task = body.task.replace("'", "'\\''")
    return _compact_agent_closeout(
        _run_wsl(f"aos-hermes claude '{safe_task}'", timeout=120),
        "claude", "claude", body.task,
        {
            "requested_target": "claude",
            "selected_route": "direct_claude",
            "delegation_reason": "direct Claude API route",
            "codex_forbidden": "no",
        },
    )


@app.post("/api/wsl/codex")
def wsl_codex(body: TaskRun):
    """Call aos-codex directly inside AgenticOSClean."""
    if not body.task.strip():
        raise HTTPException(status_code=422, detail="task must not be empty")
    safe_task = body.task.replace("'", "'\\''")
    return _compact_agent_closeout(
        _run_wsl(f"aos-codex '{safe_task}'", timeout=120),
        "codex", "codex", body.task,
        {
            "requested_target": "codex",
            "selected_route": "direct_codex",
            "delegation_reason": "direct Codex API route",
            "codex_forbidden": "no",
        },
    )


class ComposioAction(BaseModel):
    tool_slug: str
    json_args: dict


@app.post("/api/connectors/composio/action")
def composio_action(body: ComposioAction):
    """Execute one generic Composio tool through the shared workspace adapter."""
    tool = body.tool_slug.strip().upper()
    response = _run_composio_adapter("tool-run", tool, body.json_args)
    response.setdefault("tool_slug", tool)
    response.setdefault("args", body.json_args)
    return response

@app.get("/api/connectors/telegram/status")
def telegram_connector_status():
    import json
    import os
    import subprocess
    from pathlib import Path

    workspace = Path(r"C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live")
    bridge = workspace / "connectors" / "telegram_bridge" / "telegram_bridge.py"
    env_file = workspace / "connectors" / "telegram_bridge" / ".env"
    allowed = workspace / "connectors" / "telegram_bridge" / "allowed_chats.json"
    reports = workspace / "pilots" / "northshore_honda_sales_demo" / "sales_reports.jsonl"

    running = False
    try:
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*telegram_bridge.py*' -and $_.CommandLine -like '*Agentic OS Live*' } | Select-Object -First 1 -ExpandProperty ProcessId"
        ]
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        running = bool(out.stdout.strip())
    except Exception:
        running = False

    report_count = 0
    if reports.exists():
        report_count = len([line for line in reports.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()])

    operator_configured = bool(os.environ.get("TELEGRAM_OPERATOR_CHAT_IDS", "").strip())

    return {
        "status": "running" if running else "stopped",
        "running": running,
        "bridge_file": bridge.exists(),
        "env_file": env_file.exists(),
        "allowed_chats": allowed.exists(),
        "pilot_report_file": reports.exists(),
        "pilot_report_count": report_count,
        "operator_chat_configured": operator_configured or allowed.exists(),
        "pilot_id": "northshore_honda_sales_demo"
    }


# Agentic OS local connector status endpoint — zero token / read only
import json as _agentic_connector_json
from pathlib import Path as _AgenticConnectorPath

@app.get("/api/connectors/status")
def get_agentic_connector_status():
    root = _AgenticConnectorPath(__file__).resolve().parents[2]
    path = root / "connectors" / "connector_status.json"
    if not path.exists():
        return {
            "updated": None,
            "mode": "local_zero_token_status",
            "connectors": [],
            "error": "connector_status.json not found"
        }
    try:
        return _agentic_connector_json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "updated": None,
            "mode": "local_zero_token_status",
            "connectors": [],
            "error": str(exc)
        }

# Agentic OS connector action: Refresh Composio CLI Status
@app.post("/api/connectors/composio/refresh")
def refresh_composio_cli_status():
    import subprocess
    from datetime import datetime
    from pathlib import Path

    workspace = Path(__file__).resolve().parents[2]
    out_file = workspace / "connectors" / "composio_live_connections.txt"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    commands = [
        ("version", ["wsl.exe", "-d", "AgenticOSClean", "--user", "liam", "--", "/home/liam/.composio/composio", "version"]),
        ("whoami", ["wsl.exe", "-d", "AgenticOSClean", "--user", "liam", "--", "/home/liam/.composio/composio", "whoami"]),
        ("connections list", ["wsl.exe", "-d", "AgenticOSClean", "--user", "liam", "--", "/home/liam/.composio/composio", "connections", "list"]),
    ]

    sections = [
        "Agentic OS Composio CLI refresh",
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "Distro: AgenticOSClean",
        "CLI: /home/liam/.composio/composio",
        "",
    ]

    ok = True
    for label, cmd in commands:
        sections.append(f"=== {label} ===")
        try:
            result = subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if result.stdout:
                sections.append(result.stdout.strip())
            if result.stderr:
                sections.append(result.stderr.strip())
            sections.append(f"EXIT={result.returncode}")
            if result.returncode != 0:
                ok = False
        except Exception as exc:
            ok = False
            sections.append(f"ERROR={exc}")
        sections.append("")

    output = "\n".join(sections)
    out_file.write_text(output, encoding="utf-8")

    return {
        "success": ok,
        "output": output,
        "output_file": str(out_file),
    }
