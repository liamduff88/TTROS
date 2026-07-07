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
import sys
import tempfile

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from aos_paths import AosPathError, aos_root, resolve_root_relative

app = FastAPI(title="Agentic OS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3010", "http://localhost:3010"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = aos_root()
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


class QueueReviewClose(BaseModel):
    review_note: str = ""


_QUEUE_ARTIFACT_ALLOWED_PREFIXES = (
    "queue/receipts/",
    "results/",
    "workflows/",
    "packets/",
    "logs/",
)
_QUEUE_ARTIFACT_EXTENSIONS = {".md", ".txt", ".json", ".jsonl"}
_QUEUE_ARTIFACT_SECRET_RE = re.compile(r"(^|[/.])(\.env|env\.|.*secret.*|.*token.*|.*credential.*|.*password.*)", re.IGNORECASE)
_QUEUE_ARTIFACT_PATH_RE = re.compile(
    r"(?P<path>(?:queue/receipts|results|workflows|packets|logs)/[^\s`'\"<>]+?\.(?:md|txt|json|jsonl))",
    re.IGNORECASE,
)
_QUEUE_ARTIFACT_MAX_BYTES = 250_000


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
QUEUE_WORKER_TIMEOUT_SECONDS = 300
QUEUE_HERMES_REVIEW_TIMEOUT_SECONDS = 120
QUEUE_STUCK_TIMEOUT_SECONDS = QUEUE_WORKER_TIMEOUT_SECONDS + QUEUE_HERMES_REVIEW_TIMEOUT_SECONDS + 180


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
        return {
            "success": False,
            "output": f"Command timed out after {timeout}s",
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "returncode": -1,
            "timed_out": True,
            "timeout_seconds": timeout,
        }
    except FileNotFoundError:
        return {"success": False, "output": "wsl.exe not found — WSL not available on this machine", "returncode": -1}
    except Exception as e:
        return {"success": False, "output": f"Error: {e}", "returncode": -1}


def _write_agent_prompt_file(prompt: str, prefix: str = "aos_prompt_") -> tuple[Path, str]:
    """Persist one prompt outside the shell command line and return WSL path."""
    prompt_dir = BASE_DIR / "queue" / "run_prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix=prefix,
        suffix=".md",
        dir=prompt_dir,
        delete=False,
    )
    with handle:
        handle.write(prompt)
    prompt_path = Path(handle.name)
    return prompt_path, _path_for_wsl_command(prompt_path)


def _run_wsl_prompt_command(command_template: str, prompt: str, timeout: int) -> dict:
    prompt_path, prompt_wsl_path = _write_agent_prompt_file(prompt)
    try:
        command = command_template.format(prompt_file=shlex.quote(prompt_wsl_path))
        return _run_wsl(command, timeout=timeout)
    finally:
        try:
            prompt_path.unlink()
        except FileNotFoundError:
            pass


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


def _token_usage_detail(token_usage_text: str) -> str:
    detail = str(token_usage_text or "").removeprefix("Token usage:").strip()
    return detail or "unavailable from current CLI output"


def _compact_closeout_lines(status: str, values: dict[str, str]) -> list[str]:
    lines = [status]
    for key in _CLOSEOUT_FIELDS:
        if key == "Token usage":
            lines.extend(("Token usage:", f"- {values[key]}"))
        else:
            lines.append(f"{key}: {values[key]}")
    return lines


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


def _record_no_agent_invocation(record: dict) -> bool:
    return bool(record.get("no_agent_invocation") or (record.get("token_usage") or {}).get("no_agent_invocation"))


def _record_unavailable(record: dict) -> bool:
    return record.get("unavailable") is True or (record.get("token_usage") or {}).get("available") is False


def _record_matches_token_route(record: dict, route: str) -> bool:
    route = route.lower()
    candidates = (
        record.get("route"),
        record.get("agent"),
        record.get("selected_route"),
        record.get("requested_target"),
    )
    for value in candidates:
        text = str(value or "").lower()
        if text == route or text.endswith(f"_{route}") or text.endswith(f"-{route}"):
            return True
    return False


def _token_route_summary(record: dict) -> dict:
    no_agent = _record_no_agent_invocation(record)
    unavailable = _record_unavailable(record)
    return {
        "timestamp": record.get("timestamp"),
        "route": record.get("route"),
        "agent": record.get("agent"),
        "status": "no agent invocation" if no_agent else "unavailable" if unavailable else "completed",
        "token_usage_text": record.get("token_usage_text") or "Token usage: unavailable from current CLI output",
        "token_usage": record.get("token_usage") or {"available": False},
    }


def _token_usage_by_route(dated_records: list[tuple[datetime.datetime | None, int, dict]]) -> dict:
    by_route = {}
    for route in ("hermes", "codex", "claude"):
        matches = [item for item in dated_records if _record_matches_token_route(item[2], route)]
        latest_known = next((record for _, _, record in matches if (record.get("token_usage") or {}).get("available") is True), None)
        latest = latest_known or (matches[0][2] if matches else None)
        by_route[route] = _token_route_summary(latest) if latest else {
            "status": "no agent invocation",
            "token_usage_text": "Token usage: no agent invocation",
            "token_usage": {"available": False, "no_agent_invocation": True},
        }
    return by_route


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
    known_total_records = {"today": 0, "week": 0, "month": 0, "all_time": 0}
    unavailable_today = 0
    no_agent_today = 0
    dated_records = []

    for position, record in enumerate(records):
        timestamp = _parse_record_timestamp(record.get("timestamp"))
        local_date = timestamp.astimezone(local_tz).date() if timestamp else None
        dated_records.append((timestamp, position, record))
        no_agent = _record_no_agent_invocation(record)
        if local_date == today:
            no_agent_today += int(no_agent)
            unavailable = _record_unavailable(record)
            unavailable_today += int(not no_agent and unavailable)
        total = _known_total(record)
        if total is None:
            continue
        totals["all_time"] += total
        known_total_records["all_time"] += 1
        if local_date is not None and month_start <= local_date <= today:
            totals["month"] += total
            known_total_records["month"] += 1
        if local_date is not None and week_start <= local_date <= today:
            totals["week"] += total
            known_total_records["week"] += 1
        if local_date == today:
            totals["today"] += total
            known_total_records["today"] += 1

    dated_records.sort(key=lambda item: (item[0] or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), item[1]), reverse=True)
    task_records = [item for item in dated_records if not (item[2].get("no_agent_invocation") or (item[2].get("token_usage") or {}).get("no_agent_invocation"))]
    latest = task_records[0][2] if task_records else {}
    recent_activity = []
    for _, _, record in dated_records[:10]:
        no_agent = _record_no_agent_invocation(record)
        unavailable = _record_unavailable(record)
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
        "known_token_record_counts": known_total_records,
        "has_known_tokens_today": known_total_records["today"] > 0,
        "has_known_tokens_this_week": known_total_records["week"] > 0,
        "has_known_tokens_this_month": known_total_records["month"] > 0,
        "unavailable_count_today": unavailable_today,
        "no_agent_invocation_count_today": no_agent_today,
        "recent_activity": recent_activity,
        "by_route": _token_usage_by_route(dated_records),
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
    TOKEN_USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
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
    timed_out = bool(result.get("timed_out"))
    timeout_seconds = result.get("timeout_seconds")
    token_usage, token_usage_text = _extract_token_usage(
        raw, str(result.get("stdout") or ""), str(result.get("stderr") or "")
    )
    values = {
        "Files touched": _field_from_output(raw, "Files touched") or "None reported",
        "Validation": _field_from_output(raw, "Validation") or (
            f"Agent command timed out after {timeout_seconds}s" if timed_out else ("Agent command completed" if passed else "Agent command failed")
        ),
        "Connector access": _field_from_output(raw, "Connector access") or "No connector action reported",
        "Token usage": _token_usage_detail(token_usage_text),
        "Blockers": _field_from_output(raw, "Blockers") or (
            f"Timeout after {timeout_seconds}s during local agent run" if timed_out else ("None" if passed else "See local agent logs")
        ),
        "Next action": _field_from_output(raw, "Next action") or ("None" if passed else "Review the local agent failure"),
    }
    output = "\n".join(_compact_closeout_lines("PASS" if passed else "NEEDS ATTENTION", values))
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
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
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
_QUEUE_STATUS_INTENTS = {"queue status", "show queue status", "show queue summary"}
_QUEUE_FILTERED_READ_INTENTS = {
    "what is currently blocked?": ("blocked", "Blocked queue items"),
    "show queue items needing review": ("human_review", "Queue items needing review"),
}
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


def _queue_model_routes_path() -> Path:
    return BASE_DIR / "queue" / "model_routes.json"


def _queue_route_fallback(lane: str = "unassigned") -> dict:
    return {
        "lane": lane or "unassigned",
        "profile_requested": "default",
        "provider": "configured externally",
        "model": "configured externally",
        "escalation_profile": "orchestrator_escalated",
        "escalation_rule": "Use Operating Hermes triage when the queue owner is missing or unknown.",
        "policy": "Fallback to the single Operating Hermes runtime for triage and safe routing.",
    }


def _load_queue_model_routes() -> dict:
    path = _queue_model_routes_path()
    if not path.exists():
        return {"version": "0", "fallback": _queue_route_fallback(), "routes": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("queue/model_routes.json must contain a JSON object")
    routes = data.get("routes")
    if not isinstance(routes, dict):
        raise ValueError("queue/model_routes.json must contain a routes object")
    fallback = data.get("fallback")
    if not isinstance(fallback, dict):
        fallback = _queue_route_fallback()
    return {"version": str(data.get("version", "0")), "fallback": fallback, "routes": routes}


_ROUTE_PLACEHOLDERS = {
    "",
    "null",
    "none",
    "unavailable",
    "configured externally",
    "inherit_default",
    "default",
    "—",
    "-",
    "tbd",
}
_ROUTE_PLACEHOLDER_RE = re.compile(
    r"(?:^<[^>]+>$|exact[_ -]?(?:provider|model)|placeholder|fake|unit[_ -]?(?:provider|model))",
    re.IGNORECASE,
)
_KNOWN_HERMES_PROVIDERS = {
    "anthropic",
    "deepseek",
    "gemini",
    "github-copilot",
    "google",
    "kilocode",
    "kimi",
    "mistral",
    "moonshot",
    "nous",
    "openai",
    "openai-codex",
    "opencode-go",
    "opencode-zen",
    "openrouter",
    "qwen-oauth",
    "xai",
    "zai",
}


def _queue_route_value(value: object, fallback: str = "configured externally") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _queue_route_value_is_explicit(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower() not in _ROUTE_PLACEHOLDERS and not _ROUTE_PLACEHOLDER_RE.search(text)


def _queue_provider_value_is_safe(value: object) -> bool:
    provider = str(value or "").strip().lower()
    return _queue_route_value_is_explicit(provider) and provider in _KNOWN_HERMES_PROVIDERS


def _queue_resolve_route_metadata(owner: object) -> dict:
    requested_lane = str(owner or "unassigned").strip().lower() or "unassigned"
    config = _load_queue_model_routes()
    route = config["routes"].get(requested_lane)
    if not isinstance(route, dict):
        route = {**_queue_route_fallback(requested_lane), **config.get("fallback", {})}
        route["lane"] = requested_lane
    profile_requested = _queue_route_value(
        route.get("profile_requested", route.get("profile")),
        "default",
    )
    provider_requested = _queue_route_value(route.get("provider"))
    model_requested = _queue_route_value(route.get("model"))
    explicit_route = (
        _queue_provider_value_is_safe(provider_requested)
        and _queue_route_value_is_explicit(model_requested)
    )
    profile_used = "explicit_model_provider_route" if explicit_route else "default"
    profile_fallback_reason = "" if explicit_route else "explicit provider/model route missing or placeholder"
    provider_used = provider_requested if explicit_route else "default"
    model_used = model_requested if explicit_route else "default"
    model_confirmed = "configured in queue/model_routes.json" if explicit_route else "unavailable from current CLI output"
    provider_confirmed = "configured in queue/model_routes.json" if explicit_route else "unavailable from current CLI output"
    metadata = {
        "route_config_version": config.get("version", "0"),
        "lane": str(route.get("lane") or requested_lane),
        "profile_requested": profile_requested,
        "profile_used": profile_used,
        "profile": profile_used,
        "profile_fallback_reason": profile_fallback_reason,
        "provider_requested": provider_requested,
        "provider_used": provider_used,
        "provider_confirmed": provider_confirmed,
        "model_requested": model_requested,
        "model_used": model_used,
        "model_confirmed": model_confirmed,
        "explicit_model_provider_route": explicit_route,
        "escalation_profile": str(route.get("escalation_profile") or ""),
        "escalation_rule": str(route.get("escalation_rule") or "No escalation rule configured."),
        "route_policy": str(route.get("policy") or ""),
    }
    return metadata


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


def _queue_write_review_receipt(item_id: str, review_note: str) -> str:
    note = str(review_note or "").strip()
    if len(note) > 500:
        raise ValueError("review_note must be 500 characters or fewer")
    timestamp = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lines = [
        "PASS",
        "",
        "Review closeout:",
        "- Reviewed by: Liam",
        f"- Reviewed at: {timestamp}",
        "- Status: done",
    ]
    if note:
        lines.extend(["", "Review note:", note])
    return _queue_write_receipt(item_id, "\n".join(lines))


def _queue_run_receipt_path(item_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", item_id).strip("-") or "receipt"
    return (Path("queue") / "receipts" / f"{safe_id}.md").as_posix()


def _queue_write_run_receipt(item_id: str, receipt_text: str) -> str:
    text = receipt_text.strip()
    if not text:
        raise ValueError("receipt_text must not be empty")
    receipt_path = _queue_run_receipt_path(item_id)
    target = BASE_DIR / receipt_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text.rstrip() + "\n", encoding="utf-8")
    return receipt_path


def _queue_artifact_block_reason(path_text: str) -> str | None:
    normalized = path_text.replace("\\", "/").lstrip("./")
    if _QUEUE_ARTIFACT_SECRET_RE.search(normalized):
        return "path is blocked because it looks like a secret or environment file"
    if Path(normalized).suffix.lower() not in _QUEUE_ARTIFACT_EXTENSIONS:
        return "only .md, .txt, .json, and .jsonl artifacts are readable"
    if not any(normalized.startswith(prefix) for prefix in _QUEUE_ARTIFACT_ALLOWED_PREFIXES):
        return "artifact path must stay under queue/receipts, results, workflows, packets, or logs"
    return None


def _queue_read_artifact(relative_path: str, *, receipt_only: bool = False) -> dict:
    path_text = str(relative_path or "").strip()
    if not path_text:
        raise ValueError("artifact path is required")
    if Path(path_text).is_absolute():
        raise ValueError("artifact path must be root-relative")

    blocked = _queue_artifact_block_reason(path_text)
    if blocked:
        raise ValueError(blocked)

    try:
        target = resolve_root_relative(path_text, root=BASE_DIR)
    except AosPathError as exc:
        raise ValueError(str(exc)) from exc

    try:
        root_relative = target.relative_to(BASE_DIR.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("artifact path must stay inside the workspace") from exc
    blocked = _queue_artifact_block_reason(root_relative)
    if blocked:
        raise ValueError(blocked)

    if receipt_only:
        try:
            target.relative_to(resolve_root_relative("queue/receipts", root=BASE_DIR))
        except ValueError as exc:
            raise ValueError("receipt path must stay under queue/receipts") from exc

    if target.name == ".gitkeep" or not target.is_file():
        raise FileNotFoundError(path_text)
    stat = target.stat()
    if stat.st_size > _QUEUE_ARTIFACT_MAX_BYTES:
        raise ValueError("artifact is too large to display in the dashboard")
    return {
        "path": root_relative,
        "name": target.name,
        "extension": target.suffix.lower(),
        "size_bytes": stat.st_size,
        "modified": datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


def _queue_receipt_artifact(relative_path: str) -> tuple[str, str]:
    artifact = _queue_read_artifact(relative_path, receipt_only=True)
    return artifact["path"], artifact["content"]


def _queue_token_usage_lines(content: str) -> list[str]:
    lines = content.splitlines()
    token_lines: list[str] = []
    capture = False
    for line in lines:
        stripped = line.strip()
        if "token usage" in stripped.lower():
            capture = True
            token_lines.append(stripped)
            continue
        if capture:
            if not stripped:
                if token_lines:
                    break
                continue
            if stripped.startswith("-") or stripped.lower().startswith(("attempt", "total", "input", "output", "cached", "unavailable")):
                token_lines.append(stripped)
                continue
            break
    return token_lines[:8]


def _queue_artifact_candidates_from_text(text: str) -> list[str]:
    candidates = []
    for match in _QUEUE_ARTIFACT_PATH_RE.finditer(str(text or "")):
        path = match.group("path").rstrip(").,;:]")
        if not _queue_artifact_block_reason(path):
            candidates.append(path)
    return candidates


def _queue_unique_artifact_paths(paths: list[str]) -> list[str]:
    unique = []
    seen = set()
    for path in paths:
        cleaned = str(path or "").strip().strip("`'\"")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        unique.append(cleaned)
    return unique


def _queue_verified_artifacts_from_worker_result(item: dict, worker_result: dict) -> list[dict]:
    paths = [_queue_default_artifact_path(item)]
    paths.extend(_queue_artifact_candidates_from_text(str(worker_result.get("output") or "")))
    verified = []
    for path in _queue_unique_artifact_paths(paths):
        ref = {"path": path}
        reason = _queue_artifact_block_reason(path)
        if reason:
            ref.update({"available": False, "reason": reason})
        else:
            try:
                artifact = _queue_read_artifact(path)
                ref.update({
                    "available": True,
                    "size_bytes": artifact["size_bytes"],
                    "modified": artifact["modified"],
                    "content_excerpt": _bounded_hermes_answer(artifact["content"], 900),
                })
            except FileNotFoundError:
                ref.update({"available": False, "reason": "artifact not found at workspace root-relative path"})
            except ValueError as exc:
                ref.update({"available": False, "reason": str(exc)})
            except OSError as exc:
                ref.update({"available": False, "reason": f"artifact could not be read: {exc}"})
        verified.append(ref)
    return verified


def _queue_render_verified_artifacts(artifacts: list[dict], *, include_excerpt: bool) -> str:
    if not artifacts:
        return "- None detected"
    lines = []
    for artifact in artifacts:
        path = artifact.get("path", "")
        if artifact.get("available"):
            lines.append(f"- AVAILABLE: {path} ({artifact.get('size_bytes', 0)} bytes)")
            if include_excerpt:
                lines.append("  Content excerpt:")
                lines.extend(f"  {line}" for line in str(artifact.get("content_excerpt") or "").splitlines()[:20])
        else:
            lines.append(f"- MISSING/BLOCKED: {path} ({artifact.get('reason', 'unavailable')})")
    return "\n".join(lines)


def _queue_artifact_refs(item: dict, receipt_content: str = "") -> list[dict]:
    raw_paths: list[str] = []
    for field in ("sources", "source_refs", "results", "artifacts"):
        value = item.get(field)
        values = value if isinstance(value, list) else _queue_split_text(value)
        raw_paths.extend(str(entry).strip() for entry in values if str(entry).strip())
    for receipt in item.get("receipts") or []:
        if isinstance(receipt, str):
            raw_paths.append(receipt)
        elif isinstance(receipt, dict):
            raw_paths.append(str(receipt.get("path") or "").strip())
    raw_paths.extend(_queue_artifact_candidates_from_text(receipt_content))

    refs = []
    seen = set()
    for path in raw_paths:
        path = path.strip().strip("`'\"")
        if not path or path in seen:
            continue
        seen.add(path)
        reason = _queue_artifact_block_reason(path)
        ref = {"path": path}
        if reason:
            ref.update({"available": False, "reason": reason})
        else:
            try:
                artifact = _queue_read_artifact(path)
                ref.update({
                    "available": True,
                    "name": artifact["name"],
                    "extension": artifact["extension"],
                    "size_bytes": artifact["size_bytes"],
                    "modified": artifact["modified"],
                })
            except FileNotFoundError:
                ref.update({"available": False, "reason": "file is listed but missing"})
            except ValueError as exc:
                ref.update({"available": False, "reason": str(exc)})
            except OSError as exc:
                ref.update({"available": False, "reason": f"file is listed but could not be read: {exc}"})
        refs.append(ref)
    return refs


def _queue_latest_receipt(item: dict) -> dict | None:
    receipts = item.get("receipts") or []
    if not receipts:
        return None
    latest = receipts[-1]
    if isinstance(latest, str):
        latest = {"path": latest}
    if not isinstance(latest, dict):
        return None

    path = str(latest.get("path") or "").strip()
    summary = ""
    content = ""
    metadata = {}
    if path:
        try:
            artifact = _queue_read_artifact(path, receipt_only=True)
            content = artifact["content"]
            metadata = {key: artifact[key] for key in ("name", "extension", "size_bytes", "modified")}
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            summary = "\n".join(lines[:8])
        except (FileNotFoundError, ValueError, OSError):
            summary = "Receipt file is listed but could not be read from queue/receipts."

    return {
        "path": path,
        "status": latest.get("status") or item.get("status", ""),
        "created_at": latest.get("created_at"),
        "available": bool(content),
        "content": content,
        "token_usage_lines": _queue_token_usage_lines(content) if content else [],
        **metadata,
        "summary": _bounded_hermes_answer(summary or "Receipt summary unavailable.", 900),
    }


def _queue_detail_item(item: dict) -> dict:
    public = _queue_public_item(item)
    latest_receipt = _queue_latest_receipt(item)
    public.update({
        "requested_by": item.get("requested_by", ""),
        "owner_type": item.get("owner_type", ""),
        "source": item.get("source", ""),
        "tags": item.get("tags") or [],
        "context": item.get("context", ""),
        "sources": item.get("sources") or [],
        "source_refs": item.get("source_refs") or [],
        "allowed_actions": item.get("allowed_actions") or [],
        "stop_conditions": item.get("stop_conditions") or [],
        "definition_of_done": item.get("definition_of_done", ""),
        "next_action": item.get("next_action", ""),
        "claim": item.get("claim") or {"claimed_by": None, "claimed_at": None},
        "receipts": item.get("receipts") or [],
        "latest_receipt": latest_receipt,
        "run_artifacts": _queue_artifact_refs(item, latest_receipt.get("content", "") if latest_receipt else ""),
        "stuck_recovery": _queue_stuck_recovery(item),
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
            "token_usage": {"available": False, "no_agent_invocation": True},
            "token_usage_text": "Token usage: no agent invocation",
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
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
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


@app.post("/api/queue/items/{item_id}/review-close")
def close_queue_item_review(item_id: str, body: QueueReviewClose):
    """Close one human_review queue item as done with an optional local review note."""
    try:
        existing = _queue_find_item(item_id)
        if existing.get("status") != "human_review":
            raise ValueError("only human_review items can be closed from review")
        receipt_path = _queue_write_review_receipt(item_id, body.review_note)
        item = _load_queue_tool().attach_receipt(BASE_DIR, item_id, receipt_path, "done")
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


@app.get("/api/queue/artifact")
def queue_artifact(path: str):
    """Read one safe local queue artifact without mutating queue state."""
    try:
        artifact = _queue_read_artifact(path)
    except FileNotFoundError:
        return {"success": False, "available": False, "path": str(path or ""), "reason": "artifact not found"}
    except ValueError as exc:
        return {"success": False, "available": False, "path": str(path or ""), "reason": str(exc)}
    return {
        "success": True,
        "available": True,
        **artifact,
        "token_usage_lines": _queue_token_usage_lines(artifact["content"]),
    }


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


def _queue_required_receipt_shape() -> str:
    return "\n".join((
        "PASS/NEEDS ATTENTION",
        "",
        "Work item:",
        "- <AOS-ID>",
        "",
        "Files touched:",
        "- ...",
        "",
        "Validation:",
        "- ...",
        "",
        "Artifacts:",
        "- ...",
        "",
        "Blockers:",
        "- ...",
        "",
        "Next action:",
        "- ...",
        "",
        "Token usage:",
        "- available / unavailable from current CLI output",
    ))


def _queue_slug(value: object, limit: int = 64) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return (slug or "queue_artifact")[:limit].strip("_") or "queue_artifact"


def _queue_default_artifact_path(item: dict) -> str:
    return (
        Path("workflows")
        / "queue_artifacts"
        / f"{_queue_slug(item.get('id'))}_{_queue_slug(item.get('title'), 48)}.md"
    ).as_posix()


def _queue_actual_department_run_prompt(
    item: dict,
    owner: str,
    attempt: int,
    revision_instructions: str | None = None,
) -> str:
    lines = [
        "Run this Agentic OS department queue item locally and return only the required receipt.",
        "",
        "Work item essentials:",
        f"- ID: {item.get('id', '')}",
        f"- Title: {item.get('title', '')}",
        f"- Owner: {owner}",
        f"- Current attempt: {attempt}/2",
        "",
        "Context:",
        str(item.get("context") or "No additional context provided.").strip(),
        "",
        "Sources:",
        _queue_render_list(item.get("sources") or []),
        "",
        "Allowed actions:",
        _queue_render_list(item.get("allowed_actions") or []),
        "",
        "Stop conditions:",
        _queue_render_list(item.get("stop_conditions") or []),
        "",
        "Definition of done:",
        str(item.get("definition_of_done") or "Complete or route the scoped queue item and return the required closeout.").strip(),
        "",
        "Required local artifact path:",
        _queue_default_artifact_path(item),
        "If this task produces business output, write the durable output to that path and list it under Artifacts.",
        "",
        "Required artifact/receipt shape:",
        _queue_required_receipt_shape(),
    ]
    if revision_instructions:
        lines.extend((
            "",
            "Hermes revision instructions:",
            revision_instructions.strip(),
            "Revise only what is needed to satisfy the queue item, stop conditions, and definition of done.",
        ))
    return "\n".join(lines).rstrip() + "\n"


def _queue_actual_run_prompt(
    item: dict,
    owner: str,
    revision_instructions: str | None = None,
    attempt: int = 1,
) -> str:
    if owner in DEPARTMENT_PROMPT_TARGETS:
        return _queue_actual_department_run_prompt(item, owner, attempt, revision_instructions)
    prompt = _queue_render_prompt(item, owner)
    for marker in ("## Launch from PowerShell", "## Manual Launch", "## Manual launch"):
        if marker in prompt:
            prompt = prompt.split(marker, 1)[0].rstrip()
    prompt = "\n\n".join((
        prompt.rstrip(),
        f"Current attempt: {attempt}/2",
        "Required artifact/receipt shape:",
        _queue_required_receipt_shape(),
        f"Required local artifact path: {_queue_default_artifact_path(item)}",
        "If this task produces business output, write the durable output to that path and list it under Artifacts.",
    ))
    if revision_instructions:
        prompt = "\n\n".join((
            prompt.rstrip(),
            "## Hermes Revision Instructions",
            revision_instructions.strip(),
            "Revise only what is needed to satisfy the queue item, stop conditions, and definition of done.",
        ))
    return prompt.rstrip() + "\n"


def _queue_worker_owner(item: dict) -> str:
    owner = str(item.get("owner") or "unassigned").strip().lower()
    if owner in {"codex", "claude", "hermes", "revenue", "marketing", "delivery", "operations"}:
        return owner
    return "unassigned"


def _queue_token_task_label(item: dict, owner: str) -> str:
    return f"{item.get('id', '')} | {owner} | {str(item.get('title') or '')[:160]}"


def _hermes_coordinator_command_template(route_metadata: dict | None = None) -> str:
    command = f"{shlex.quote(_path_for_wsl_command(HERMES_COORDINATOR))}"
    if route_metadata and route_metadata.get("explicit_model_provider_route"):
        command += f" --provider {shlex.quote(str(route_metadata['provider_requested']))}"
        command += f" --model {shlex.quote(str(route_metadata['model_requested']))}"
    return f"{command} --prompt-file {{prompt_file}}"


def _queue_run_worker(owner: str, prompt: str, item: dict) -> dict:
    route_metadata = _queue_resolve_route_metadata(owner)
    metadata = {
        "requested_target": owner,
        "selected_route": "queue_worker",
        "delegation_reason": "assigned queue worker",
        "codex_forbidden": "no",
        "timeout_seconds": QUEUE_WORKER_TIMEOUT_SECONDS,
        "queue_item_id": item.get("id", ""),
        "queue_item_title": item.get("title", ""),
        "queue_lane": route_metadata["lane"],
        **route_metadata,
    }
    if owner == "codex":
        result = _run_wsl_prompt_command('aos-codex "$(<{prompt_file})"', prompt, QUEUE_WORKER_TIMEOUT_SECONDS)
        return _compact_agent_closeout(result, "codex", "codex", _queue_token_task_label(item, owner), metadata)
    if owner == "claude":
        result = _run_wsl_prompt_command('aos-hermes claude "$(<{prompt_file})"', prompt, QUEUE_WORKER_TIMEOUT_SECONDS)
        return _compact_agent_closeout(result, "claude", "claude", _queue_token_task_label(item, owner), metadata)
    command_template = _hermes_coordinator_command_template(route_metadata)
    result = _run_wsl_prompt_command(command_template, prompt, QUEUE_WORKER_TIMEOUT_SECONDS)
    agent = owner if owner in DEPARTMENT_PROMPT_TARGETS else "hermes"
    return _compact_agent_closeout(result, agent, agent, _queue_token_task_label(item, owner), metadata)


def _queue_hermes_review_prompt(item: dict, owner: str, attempt: int, worker_result: dict) -> str:
    verified_artifacts = _queue_verified_artifacts_from_worker_result(item, worker_result)
    return "\n".join((
        "Review this Agentic OS queue worker result.",
        "",
        "Return exactly one review decision:",
        "PASS",
        "or",
        "REVISE: <specific revision instructions>",
        "",
        "Check:",
        "- Did it satisfy the queue item title/context?",
        "- Did it respect stop conditions?",
        "- Did it produce the required output/definition of done?",
        "- Is it good enough to return to Liam?",
        "",
        "Local artifact verification from repo root:",
        "- Treat AVAILABLE artifacts below as verified by the dashboard-safe workspace path reader.",
        "- Do not claim an artifact is missing when it is marked AVAILABLE here.",
        _queue_render_verified_artifacts(verified_artifacts, include_excerpt=True),
        "",
        "Queue item:",
        f"- ID: {item.get('id', '')}",
        f"- Title: {item.get('title', '')}",
        f"- Assigned worker: {owner}",
        f"- Context: {item.get('context') or 'None'}",
        f"- Definition of done: {item.get('definition_of_done') or 'Complete the scoped queue item and return the required closeout.'}",
        "Stop conditions:",
        _queue_render_list(item.get("stop_conditions") or []),
        "",
        f"Worker attempt {attempt} result:",
        _bounded_hermes_answer(str(worker_result.get("output") or worker_result.get("stdout") or ""), 2500),
    ))


def _queue_run_hermes_review(item: dict, owner: str, attempt: int, worker_result: dict) -> dict:
    prompt = _queue_hermes_review_prompt(item, owner, attempt, worker_result)
    route_metadata = _queue_resolve_route_metadata("hermes")
    command_template = _hermes_coordinator_command_template(route_metadata)
    result = _run_wsl_prompt_command(command_template, prompt, QUEUE_HERMES_REVIEW_TIMEOUT_SECONDS)
    token_usage, token_usage_text = _extract_token_usage(
        str(result.get("output") or ""), str(result.get("stdout") or ""), str(result.get("stderr") or "")
    )
    return {
        "success": bool(result.get("success")),
        "output": result.get("output") or result.get("stdout") or result.get("stderr") or "",
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "returncode": result.get("returncode", -1),
        "timed_out": bool(result.get("timed_out")),
        "timeout_seconds": result.get("timeout_seconds"),
        "token_usage": token_usage,
        "token_usage_text": token_usage_text,
    }


def _queue_parse_review(review_result: dict) -> tuple[str, str]:
    output = str(review_result.get("output") or review_result.get("stdout") or "")
    pass_match = re.search(r"(?im)^\s*PASS\s*$", output)
    revise_match = re.search(r"(?im)^\s*REVISE\s*:?\s*(.*)$", output)
    if pass_match and (not revise_match or pass_match.start() < revise_match.start()):
        return "PASS", "PASS"
    if revise_match:
        instructions = revise_match.group(1).strip()
        if not instructions:
            after = output[revise_match.end():].strip()
            instructions = after.splitlines()[0].strip() if after else "Revise to satisfy the queue item and definition of done."
        return "REVISE", instructions[:1000]
    if review_result.get("success") and output.strip().upper().startswith("PASS"):
        return "PASS", "PASS"
    return "REVISE", "Hermes review did not return PASS. Review the worker result and provide a corrected closeout."


def _queue_result_summary(result: dict, limit: int = 900) -> str:
    text = str(result.get("output") or result.get("stdout") or result.get("stderr") or "").strip()
    if not text:
        text = "(no worker output)"
    return _bounded_hermes_answer(text, limit)


def _queue_result_field(result: dict, label: str, default: str = "None reported") -> str:
    raw = str(result.get("output") or "")
    return _field_from_output(raw, label) or default


def _queue_item_timestamp(item: dict) -> datetime.datetime | None:
    for key in ("claim", "updated_at", "created_at"):
        value = item.get(key)
        if key == "claim" and isinstance(value, dict):
            value = value.get("claimed_at")
        parsed = _parse_record_timestamp(value)
        if parsed:
            return parsed
    return None


def _queue_stuck_recovery(item: dict, now: datetime.datetime | None = None) -> dict:
    if item.get("status") != "agent_working":
        return {"stuck": False}
    started = _queue_item_timestamp(item)
    if not started:
        return {
            "stuck": True,
            "age_seconds": None,
            "timeout_seconds": QUEUE_STUCK_TIMEOUT_SECONDS,
            "reason": "agent_working item has no readable claim/update timestamp",
        }
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    age = max(0, int((now - started.astimezone(datetime.timezone.utc)).total_seconds()))
    return {
        "stuck": age >= QUEUE_STUCK_TIMEOUT_SECONDS,
        "age_seconds": age,
        "timeout_seconds": QUEUE_STUCK_TIMEOUT_SECONDS,
        "reason": f"agent_working for {age}s; recovery threshold is {QUEUE_STUCK_TIMEOUT_SECONDS}s",
    }


def _queue_recovery_receipt_text(item: dict, owner: str, reason: str) -> str:
    route_metadata = _queue_resolve_route_metadata(owner)
    return "\n".join((
        "NEEDS ATTENTION",
        "",
        f"Work item ID: {item.get('id', '')}",
        f"Assigned worker: {owner}",
        f"Lane: {route_metadata['lane']}",
        f"Profile requested: {route_metadata['profile_requested']}",
        f"Profile used: {route_metadata['profile_used']}",
        f"Profile fallback reason: {route_metadata.get('profile_fallback_reason') or 'None'}",
        f"Model requested: {route_metadata['model_requested']}",
        f"Model used: {route_metadata['model_used']}",
        f"Provider requested: {route_metadata['provider_requested']}",
        f"Provider used: {route_metadata['provider_used']}",
        f"Model confirmed: {route_metadata['model_confirmed']}",
        f"Provider confirmed: {route_metadata['provider_confirmed']}",
        f"Escalation rule: {route_metadata['escalation_rule']}",
        "Attempts used: 0",
        "Hermes review result: not run; recovered locally from stuck agent_working state",
        "",
        "Files touched:",
        "- queue/work_items.jsonl",
        "",
        "Validation:",
        "- Local stuck-item recovery wrote this durable receipt and moved the item to blocked.",
        "",
        "Artifacts:",
        f"- Required output path: {_queue_default_artifact_path(item)} (not produced during recovery)",
        "",
        "Blockers:",
        f"- {reason}",
        "",
        "Next action:",
        "- Review the blocker, then rerun the assigned worker when ready.",
        "",
        "Token usage:",
        "- no agent invocation during local stuck-item recovery",
    ))


def _queue_run_receipt_text(
    status_label: str,
    item: dict,
    owner: str,
    attempts: list[dict],
    final_review: dict,
    final_status: str,
    reason: str,
) -> str:
    last_worker = attempts[-1]["worker_result"] if attempts else {}
    route_metadata = _queue_resolve_route_metadata(owner)
    revised_once = any(attempt.get("review", {}).get("decision") == "REVISE" for attempt in attempts[:1])
    escalation_policy_applied = (
        "escalation-eligible retry after one REVISE; real provider/model switching not applied"
        if revised_once and len(attempts) > 1
        else "not applied"
    )
    token_lines = []
    for attempt in attempts:
        worker_token = attempt["worker_result"].get("token_usage_text") or "Token usage: unavailable from current CLI output"
        review_token = attempt["review_result"].get("token_usage_text") or "Token usage: unavailable from current CLI output"
        token_lines.append(f"- Attempt {attempt['attempt']} worker: {_token_usage_detail(worker_token)}")
        token_lines.append(f"- Attempt {attempt['attempt']} Hermes review: {_token_usage_detail(review_token)}")
    if not token_lines:
        token_lines.append("- unavailable/no agent invocation")
    verified_artifacts = _queue_verified_artifacts_from_worker_result(item, last_worker)

    lines = [
        status_label,
        "",
        f"Work item ID: {item.get('id', '')}",
        f"Assigned worker: {owner}",
        f"Lane: {route_metadata['lane']}",
        f"Profile requested: {route_metadata['profile_requested']}",
        f"Profile used: {route_metadata['profile_used']}",
        f"Profile fallback reason: {route_metadata.get('profile_fallback_reason') or 'None'}",
        f"Model requested: {route_metadata['model_requested']}",
        f"Model used: {route_metadata['model_used']}",
        f"Provider requested: {route_metadata['provider_requested']}",
        f"Provider used: {route_metadata['provider_used']}",
        f"Model confirmed: {route_metadata['model_confirmed']}",
        f"Provider confirmed: {route_metadata['provider_confirmed']}",
        f"Escalation rule: {route_metadata['escalation_rule']}",
        f"Escalation policy applied: {escalation_policy_applied}",
        f"Attempts used: {len(attempts)}",
        f"Hermes review result: {final_review.get('decision', 'REVISE')}",
        "",
        "Worker result summary:",
        _queue_result_summary(last_worker),
        "",
        "Files touched:",
        f"- {_queue_result_field(last_worker, 'Files touched')}",
        "",
        "Validation:",
        f"- {_queue_result_field(last_worker, 'Validation')}",
        "",
        "Artifacts:",
        _queue_render_verified_artifacts(verified_artifacts, include_excerpt=False),
        "",
        "Blockers:",
        f"- {reason or _queue_result_field(last_worker, 'Blockers')}",
        "",
        "Next action:",
        "- Liam review in dashboard." if final_status == "human_review" else "- Liam input needed before another worker run.",
        "",
        "Token usage:",
        *token_lines,
    ]
    return "\n".join(lines)


@app.post("/api/queue/items/{item_id}/run")
def run_queue_item(item_id: str):
    """Run one selected queue item through its assigned worker, then Hermes review."""
    try:
        item = _queue_find_item(item_id)
        owner = _queue_worker_owner(item)
        recovery = _queue_stuck_recovery(item)
        if item.get("status") == "agent_working":
            if not recovery.get("stuck"):
                raise HTTPException(status_code=409, detail="queue item is already agent_working; refresh before rerun")
            receipt_text = _queue_recovery_receipt_text(item, owner, recovery.get("reason") or "agent_working item exceeded local timeout")
            receipt_path = _queue_write_run_receipt(item_id, receipt_text)
            updated = _load_queue_tool().attach_receipt(BASE_DIR, item_id, receipt_path, "blocked")
            updated = _load_queue_tool().release_item(BASE_DIR, item_id, "blocked")
            return {
                "ok": True,
                "success": False,
                "recovered_stuck": True,
                "item_id": item_id,
                "assigned_worker": owner,
                "attempts_used": 0,
                "status": updated.get("status"),
                "started_status": "agent_working",
                "receipt_path": receipt_path,
                "hermes_review": {"decision": "RECOVERED", "output": recovery.get("reason", "")},
                "worker_result": {"success": False, "output": recovery.get("reason", "")},
                "attempts": [],
                "item": _queue_detail_item(updated),
            }

        claim_owner = owner if owner != "unassigned" else "hermes"
        started = _load_queue_tool().claim_item(BASE_DIR, item_id, claim_owner)
        attempts = []
        revision_instructions = None
        final_review = {"decision": "REVISE", "instructions": "No review completed."}
        final_status = "needs_input"
        reason = "Hermes did not pass the worker result."

        for attempt_number in (1, 2):
            run_item = _queue_find_item(item_id)
            prompt = _queue_actual_run_prompt(run_item, owner if owner != "unassigned" else "hermes", revision_instructions, attempt_number)
            worker_result = _queue_run_worker(owner, prompt, run_item)
            review_result = _queue_run_hermes_review(run_item, owner, attempt_number, worker_result)
            if worker_result.get("timed_out"):
                final_status = "blocked"
                decision = "REVISE"
                review_text = f"Worker timed out after {worker_result.get('timeout_seconds')}s."
                review_result["output"] = f"REVISE: {review_text}\n\nHermes review output:\n{review_result.get('output', '')}"
            else:
                decision, review_text = _queue_parse_review(review_result)
                if review_result.get("timed_out"):
                    final_status = "blocked"
                    review_text = f"Hermes review timed out after {review_result.get('timeout_seconds')}s."
                    review_result["output"] = f"REVISE: {review_text}"
            if final_status != "blocked":
                decision, review_text = _queue_parse_review(review_result)
            final_review = {
                "decision": decision,
                "instructions": review_text if decision == "REVISE" else "",
                "output": review_result.get("output", ""),
            }
            attempts.append({
                "attempt": attempt_number,
                "worker": owner,
                "worker_result": worker_result,
                "review_result": review_result,
                "review": final_review,
            })
            if decision == "PASS":
                final_status = "human_review"
                reason = "None"
                break
            if final_status == "blocked":
                reason = review_text
                break
            revision_instructions = review_text

        if final_status != "human_review":
            reason = final_review.get("instructions") or "Hermes requested revision after 2 attempts."

        receipt_text = _queue_run_receipt_text(
            "PASS" if final_status == "human_review" else "NEEDS ATTENTION",
            item,
            owner,
            attempts,
            final_review,
            final_status,
            reason,
        )
        receipt_path = _queue_write_run_receipt(item_id, receipt_text)
        updated = _load_queue_tool().attach_receipt(BASE_DIR, item_id, receipt_path, final_status)
        updated = _load_queue_tool().release_item(BASE_DIR, item_id, final_status)
    except KeyError:
        raise HTTPException(status_code=404, detail="queue item not found")
    except HTTPException:
        raise
    except (ValueError, OSError) as exc:
        try:
            failed_item = _queue_find_item(item_id)
            failed_owner = _queue_worker_owner(failed_item)
            receipt_path = _queue_write_run_receipt(
                item_id,
                _queue_recovery_receipt_text(failed_item, failed_owner, f"Queue run failed before completion: {exc}"),
            )
            _load_queue_tool().attach_receipt(BASE_DIR, item_id, receipt_path, "blocked")
            _load_queue_tool().release_item(BASE_DIR, item_id, "blocked")
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "ok": True,
        "success": final_status == "human_review",
        "item_id": item_id,
        "assigned_worker": owner,
        "attempts_used": len(attempts),
        "status": updated.get("status"),
        "started_status": started.get("status"),
        "receipt_path": receipt_path,
        "hermes_review": final_review,
        "worker_result": attempts[-1]["worker_result"] if attempts else {},
        "attempts": attempts,
        "item": _queue_detail_item(updated),
    }


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


def _queue_compact_item_row(item: dict) -> str:
    fields = [
        str(item.get("id", "")),
        str(item.get("title", "")),
        str(item.get("owner", "unassigned")),
        str(item.get("status", "")),
    ]
    next_action = item.get("next_action") or item.get("nextAction")
    if next_action:
        fields.append(f"Next action: {next_action}")
    return "  - " + " | ".join(fields)


def _queue_filtered_read_closeout(status: str, heading: str) -> dict:
    try:
        items = _read_queue_items()
    except ValueError as exc:
        return {
            "success": False,
            "output": "\n".join(("NEEDS ATTENTION", f"Queue read unavailable: {exc}", "Next action: Repair queue/work_items.jsonl.")),
            "returncode": 2,
            "requested_target": "queue",
            "selected_route": "local_queue_read",
            "delegation_reason": "exact queue-read intent",
            "codex_forbidden": "no",
            "token_usage": {"available": False, "no_agent_invocation": True},
            "token_usage_text": "Token usage: no agent invocation",
        }
    filtered = [item for item in items if item.get("status") == status]
    rows = [_queue_compact_item_row(item) for item in sorted(filtered, key=_queue_item_sort_key)[:10]] or ["  - None"]
    output = "\n".join((
        "PASS",
        heading + ":",
        f"  - {status}: {len(filtered)}",
        "Items:",
        *rows,
        "Next action:",
        f"  - {_queue_next_action(filtered)}",
    ))
    return {
        "success": True,
        "output": output,
        "returncode": 0,
        "requested_target": "queue",
        "selected_route": "local_queue_read",
        "delegation_reason": "exact queue-read intent",
        "codex_forbidden": "no",
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


def _try_queue_read_task(task: str) -> dict | None:
    normalized = task.strip().lower()
    if normalized in _QUEUE_STATUS_INTENTS:
        return _queue_status_closeout()
    filtered_intent = _QUEUE_FILTERED_READ_INTENTS.get(normalized)
    if filtered_intent is not None:
        return _queue_filtered_read_closeout(*filtered_intent)
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
    selected_route = metadata["selected_route"]
    if selected_route == "direct_codex":
        result = _run_wsl_prompt_command('aos-codex "$(<{prompt_file})"', body.task, 120)
        route, agent = "codex", "codex"
    elif selected_route == "direct_claude":
        result = _run_wsl_prompt_command('aos-hermes claude "$(<{prompt_file})"', body.task, 120)
        route, agent = "claude", "claude"
    else:
        metadata = {**metadata, **_queue_resolve_route_metadata("hermes")}
        command_template = _hermes_coordinator_command_template(metadata)
        result = _run_wsl_prompt_command(command_template, body.task, 120)
        route, agent = "hermes", "hermes"
    if selected_route == "hermes_coordinator":
        return _hermes_coordinator_closeout(result, body.task, metadata)
    return _compact_agent_closeout(result, route, agent, body.task, metadata)


@app.post("/api/wsl/claude")
def wsl_claude(body: TaskRun):
    """Route a task through aos-hermes to Claude inside AgenticOSClean."""
    if not body.task.strip():
        raise HTTPException(status_code=422, detail="task must not be empty")
    return _compact_agent_closeout(
        _run_wsl_prompt_command('aos-hermes claude "$(<{prompt_file})"', body.task, 120),
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
    return _compact_agent_closeout(
        _run_wsl_prompt_command('aos-codex "$(<{prompt_file})"', body.task, 120),
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
