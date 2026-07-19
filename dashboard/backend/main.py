"""Agentic OS dashboard backend.

Revisit: when operator routing, local-agent CLI contracts, or runtime health changes. · Last touched: 2026-07-19.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
try:
    from fastapi.responses import JSONResponse, Response
except ImportError:  # Static-validation stubs intentionally expose JSONResponse only.
    from fastapi.responses import JSONResponse

    class Response:  # pragma: no cover - used only by dependency-light import tests
        def __init__(self, content=b"", media_type=None, headers=None):
            self.body = content
            self.media_type = media_type
            self.headers = headers or {}
from pydantic import BaseModel
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import datetime
import webbrowser
import os
import re
import selectors
import signal
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from aos_paths import AuthorityError, AosPathError, aos_root, assert_authoritative_root, resolve_root_relative
from aos_codex_policy import (
    CODEX_TARGET,
    CONTEXT_HANDOFF_THRESHOLD_TOKENS,
    MAX_CONTEXT_HANDOFFS,
    CodexPolicyError,
    PERMISSION_HEADER,
    build_environment as build_codex_environment,
    build_exec_command as build_codex_exec_command,
    cumulative_usage_snapshot,
    invocation_metadata as codex_invocation_metadata,
    prepare_fresh_prompt as prepare_codex_fresh_prompt,
    readiness as codex_policy_readiness,
    require_clean_session_id,
    validate_runtime as validate_codex_runtime,
)
import aos_orchestration
from aos_queue_storage import durable_append_text, durable_replace_text, queue_write_lock
import aos_indexer
import business_brain
import business_brain_context
import business_brain_inbox
import business_brain_scope
import latitude_telemetry
from graphify_service import GRAPH_CSP, GraphifyError, GraphifyService, RepoIdentity, validate_github_url

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

TRACKER_FILE = DATA_DIR / "tracker.json"
TOKEN_USAGE_FILE = LOGS_DIR / "token_usage.jsonl"
QUEUE_DIR = BASE_DIR / "queue"
BACKUP_RECEIPTS_FILE = QUEUE_DIR / "receipts" / "backups.jsonl"
NOTIFICATIONS_FILE = QUEUE_DIR / "notifications.json"
TOKEN_LEDGER_FILE = QUEUE_DIR / "token_ledger.jsonl"
ROOT_TOKEN_LEDGER_FILE = BASE_DIR / "token_ledger.jsonl"
_IMPORTED_BASE_DIR = BASE_DIR


def _authoritative_append_target(path: Path) -> tuple[Path, Path]:
    """Resolve module constants against a runtime-configured/test root."""
    path = Path(path)
    if BASE_DIR != _IMPORTED_BASE_DIR:
        try:
            path = BASE_DIR / path.relative_to(_IMPORTED_BASE_DIR)
        except ValueError:
            pass
    try:
        path.relative_to(BASE_DIR)
        return BASE_DIR, path
    except ValueError:
        # A deliberately injected disposable ledger owns its own lock root.
        return path.parent, path
SKILL_TRUST_FILE = QUEUE_DIR / "skill_trust.jsonl"
WORKFLOWS_DIR = BASE_DIR / "workflows"
WORKFLOW_REGISTRY_FILE = WORKFLOWS_DIR / "workflow_registry.json"
SKILLS_DIR = BASE_DIR / "skills"
GRAPHIFY_BRAIN_DIR = Path("/home/liam/graphify-brain")
GRAPHIFY_CLONE_DIR = GRAPHIFY_BRAIN_DIR / "intake" / "cloned-repos"
GRAPHIFY_OUT_DIR = GRAPHIFY_BRAIN_DIR / "repo_graphs"
GRAPHIFY_RECEIPTS_DIR = GRAPHIFY_BRAIN_DIR / "receipts"
GRAPHIFY_SERVICE = GraphifyService(brain_root=GRAPHIFY_BRAIN_DIR, repo_root=BASE_DIR)
PROMPT_LIBRARY_DIRS = [QUEUE_DIR / "templates", WORKFLOWS_DIR / "prompt_templates"]
CLAUDE_USAGE_READER_WSL = str(BASE_DIR / "dashboard" / "backend" / "claude_usage.py")


def _require_authority() -> Path:
    return assert_authoritative_root(BASE_DIR)

@app.middleware("http")
async def linux_authority_boundary(request: Request, call_next):
    """Reject every HTTP mutation before an endpoint can create side effects."""
    if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        try:
            _require_authority()
        except AuthorityError as exc:
            return JSONResponse(status_code=503, content={"success": False, "detail": str(exc)})
    return await call_next(request)

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
        "command": "codex",
        "commandHint": "Runs through the supervised authoritative-root Codex route; readiness is reported by operator status",
        "commandType": "wsl",
        "capabilities": ["Code completion", "Function synthesis", "Test generation", "Documentation"],
        "launchable": False,
        "description": "Codex is installed in AgenticOSClean and launched through the supervised local route.",
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
        "command": str(BASE_DIR),
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
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
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


def _read_backup_receipts(path: Path | None = None) -> list[dict]:
    receipt_file = path or BACKUP_RECEIPTS_FILE
    if not receipt_file.exists():
        return []
    receipts = []
    for raw in receipt_file.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            receipts.append(record)
    return receipts


def _backup_status(now: datetime.datetime | None = None, receipts: list[dict] | None = None) -> dict:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    records = _read_backup_receipts() if receipts is None else receipts
    if not records:
        return {
            "state": "no_receipts",
            "latest": None,
            "latest_receipt_path": _safe_relative(BACKUP_RECEIPTS_FILE),
            "latest_log_path": None,
            "stale_after_hours": 48,
            "needs_attention": False,
            "token_usage_text": "Token usage: no agent invocation",
        }
    latest = records[-1]
    latest_ts = _parse_record_timestamp(latest.get("ts"))
    latest_status = str(latest.get("status") or "").lower()
    if latest_status == "fail":
        state = "failed"
    elif latest_status == "success" and latest_ts and (now - latest_ts.astimezone(datetime.timezone.utc)).total_seconds() <= 48 * 3600:
        state = "fresh_success"
    else:
        state = "stale"
    log_path = latest.get("log_path")
    safe_log_path = None
    if log_path:
        try:
            safe_log_path = _safe_relative(Path(log_path))
        except Exception:
            safe_log_path = str(log_path)
    return {
        "state": state,
        "latest": {
            "ts": latest.get("ts"),
            "status": latest.get("status"),
            "target": latest.get("target"),
            "target_drive": latest.get("target_drive"),
            "target_label": latest.get("target_label"),
            "snapshot_path": latest.get("snapshot_path"),
            "sources": latest.get("sources") or [],
            "files_copied": latest.get("files_copied") if latest.get("files_copied") is not None else latest.get("files_total"),
            "bytes_copied": latest.get("bytes_copied") if latest.get("bytes_copied") is not None else latest.get("bytes"),
            "duration_s": latest.get("duration_s"),
            "dry_run": bool(latest.get("dry_run")),
            "errors": latest.get("errors") or [],
            "warnings": latest.get("warnings") or [],
            "token_usage_text": latest.get("token_usage_text") or "Token usage: no agent invocation",
        },
        "latest_receipt_path": _safe_relative(BACKUP_RECEIPTS_FILE),
        "latest_log_path": safe_log_path,
        "stale_after_hours": 48,
        "needs_attention": state in {"failed", "stale"},
        "token_usage_text": "Token usage: no agent invocation",
    }


@app.get("/api/backups/status")
def backups_status():
    status = _backup_status()
    latitude_telemetry.trace("backup.status", "backup", status.get("state", "unknown"), needs_attention=status.get("needs_attention"))
    return status


@app.get("/api/search")
def api_search(q: str = "", type: str = "", tag: str = "", source: str = "", limit: int = 25, client_scope: str = ""):
    try:
        return aos_indexer.search(q, kind=type, tag=tag, source=source, limit=limit, client_scope=client_scope)
    except business_brain_scope.ClientScopeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/search/status")
def api_search_status():
    status = aos_indexer.status()
    latitude_telemetry.trace("search.status", "search_index", "ok", indexed=status.get("indexed"), path=status.get("path"))
    return status


@app.post("/api/search/reindex")
def api_search_reindex():
    result = aos_indexer.scan()
    latitude_telemetry.trace("search.reindex", "search_index", "ok", count=result.get("count"))
    return result


@app.post("/api/ingest/tick")
def api_ingest_tick():
    result = aos_indexer.ingest_tick()
    latitude_telemetry.trace("search.ingest_tick", "search_index", "ok", changed=result.get("changed"))
    return result


@app.get("/api/artifacts")
def api_artifacts(type: str = "", tag: str = "", source: str = "", limit: int = 50, client_scope: str = ""):
    try:
        result = aos_indexer.artifacts(kind=type, tag=tag, source=source, limit=limit, client_scope=client_scope)
    except business_brain_scope.ClientScopeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    queue_items = {str(row.get("id") or ""): row for row in _read_queue_items()}
    enriched = []
    for row in result.get("items") or []:
        indexed_path = str(row.get("path") or "")
        local_path = indexed_path.split(":", 1)[1] if ":" in indexed_path else indexed_path
        match = re.search(r"AOS-\d{4}-\d{4}", local_path)
        item_id = match.group(0) if match else ""
        item = queue_items.get(item_id, {})
        receipt = _queue_latest_receipt(item) if item else None
        canonical = _queue_canonical_token_usage(item_id) if item_id else None
        parts = Path(local_path).parts
        workflow = parts[1] if len(parts) > 2 and parts[0] == "workflows" else "orchestration_acceptance" if "orchestration_acceptance" in parts else "unfiled"
        enriched.append({
            **row,
            "local_path": local_path,
            "item_id": item_id or "unattributed",
            "linked": bool(item),
            "workflow": workflow,
            "lane": _queue_item_lane(item) if item else "unassigned",
            "owner": item.get("owner") if item else "unassigned",
            "status": item.get("status") if item else "unfiled",
            "receipt": (receipt or {}).get("path") if receipt else "",
            "token_line": (canonical or {}).get("lines", ["Token usage: unavailable"])[0],
        })
    return {**result, "items": enriched, "new_unfiled": [row for row in enriched if not row["linked"]][:12], "existing_index": True, "protected_content_excluded": True}



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
    durable_replace_text(TRACKER_FILE, json.dumps(existing, indent=2) + "\n")
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
    source: str = "dashboard"
    context: str = ""
    sources: str = ""
    source_refs: str = ""
    definition_of_done: str = ""
    allowed_actions: str = "local_read,local_edit,local_test"
    stop_conditions: str = "external_send,secrets_exposure,destructive_action_outside_scope"
    parent_id: str | None = None
    step_index: int | None = None
    depends_on: str = ""
    on_complete: str | None = None
    workbench: str | None = None
    review: str = "none"


class CockpitCommandCreate(BaseModel):
    command: str


class CockpitCaptureCreate(BaseModel):
    text: str
    capture_id: str | None = None


class QueueReceiptAttach(BaseModel):
    receipt_text: str
    status: str | None = None


class QueueStatusUpdate(BaseModel):
    status: str


class QueueReviewClose(BaseModel):
    status: str = "done"
    review_note: str = ""
    action: str = ""


class QueueReviewNote(BaseModel):
    review_note: str = ""


class QueueArtifactFolderOpen(BaseModel):
    path: str


class ExternalSendDryRun(BaseModel):
    item_id: str | None = None
    recipient: str
    action: str
    payload: str
    confirmation: str


class AgentMailDigestRequest(BaseModel):
    digest_date: str | None = None
    recipient: str | None = None
    send: bool = False
    dry_run: bool = True


class DashboardTaskCreate(BaseModel):
    title: str
    owner: str = "hermes"
    priority: str | int = "normal"
    tags: str = "dashboard"
    context: str = ""
    sources: str = ""
    definition_of_done: str = ""
    allowed_actions: str = "local_read,local_edit,local_test"
    stop_conditions: str = "external_send,secrets_exposure,destructive_action_outside_scope"


class GraphifyFetchRequest(BaseModel):
    url: str


class GraphifyRepositoryRequest(BaseModel):
    owner: str
    repository: str


class GraphifyActionRequest(GraphifyRepositoryRequest):
    action: str
    inputs: dict = {}


class GraphifyQueueRequest(GraphifyRepositoryRequest):
    requested_work: str


class DashboardSkillSave(BaseModel):
    path: str
    name: str = ""
    description: str = ""
    body: str = ""


class DashboardWorkflowSave(BaseModel):
    workflow_id: str
    content: str
    expected_revision: str


class DashboardOpenPath(BaseModel):
    path: str
    kind: str = "file"


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
    r"(?P<path>(?:queue/receipts|results|workflows|packets|logs)/[^\s`'\"<>]+?\.(?:jsonl|json|md|txt))",
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
    durable_replace_text(PACKETS_DIR / filename, json.dumps(data, indent=2) + "\n")
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
# Linux / AgenticOSClean-compatible runtime endpoints
# ---------------------------------------------------------------------------

WSL_ENV = 'export PATH="$HOME/.local/npm/bin:$HOME/.local/bin:$HOME/.composio:$PATH"'
WSL_DISTRO = "AgenticOSClean"
WSL_USER = os.environ.get("USER", "linux")
COMPOSIO_PATH = "/home/liam/.composio:/home/liam/.local/bin:/home/liam/.composio:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/usr/lib/wsl/lib"
HERMES_COORDINATOR = BASE_DIR / "tools" / "aos-hermes-coordinator.sh"
HERMES_DASHBOARD_LAUNCHER = BASE_DIR / "tools" / "aos-hermes-dashboard.sh"
HERMES_DASHBOARD_HOST = "127.0.0.1"
HERMES_DASHBOARD_PORT = 8081
HERMES_DASHBOARD_URL = f"http://{HERMES_DASHBOARD_HOST}:{HERMES_DASHBOARD_PORT}"


def _timeout_seconds_from_env(name: str, default: int, minimum: int) -> int:
    """Read a timeout override while retaining a safe lower bound."""
    try:
        configured = int(os.environ.get(name, ""))
    except ValueError:
        configured = default
    return max(configured or default, minimum)


INLINE_COMMAND_TIMEOUT_SECONDS = _timeout_seconds_from_env(
    "AOS_INLINE_COMMAND_TIMEOUT_SECONDS", default=120, minimum=1,
)
_LEGACY_AGENT_TIMEOUT_SECONDS = _timeout_seconds_from_env(
    "AOS_QUEUE_WORKER_TIMEOUT_SECONDS", default=7800, minimum=1,
)
AGENT_TIMEOUT_SECONDS = _timeout_seconds_from_env(
    "AOS_AGENT_TIMEOUT_SECONDS", default=_LEGACY_AGENT_TIMEOUT_SECONDS, minimum=1,
)
AGENT_STARTUP_TIMEOUT_SECONDS = _timeout_seconds_from_env(
    "AOS_AGENT_STARTUP_TIMEOUT_SECONDS", default=60, minimum=1,
)
# Backward-compatible name for existing queue worker/result payloads.
QUEUE_WORKER_TIMEOUT_SECONDS = AGENT_TIMEOUT_SECONDS
QUEUE_HERMES_REVIEW_TIMEOUT_SECONDS = _timeout_seconds_from_env(
    "AOS_AGENT_REVIEW_TIMEOUT_SECONDS", default=120, minimum=1,
)
MODEL_TURNS_THRESHOLD_DEFAULT = 75
MODEL_TURNS_THRESHOLD = _timeout_seconds_from_env(
    "AOS_MODEL_TURNS_THRESHOLD", default=MODEL_TURNS_THRESHOLD_DEFAULT, minimum=1,
)
UNAVAILABLE_CLI_VALUE = "unavailable from current CLI output"
USAGE_COUNTER_FIELDS = (
    "initial_prompt_bytes", "model_turns", "retained_context_bytes", "compaction_count",
    "total_input", "cached_input", "non_cached_input", "output", "reasoning",
    "input_plus_output", "fresh_input", "largest_tool_result_bytes",
    "context_pct_at_close",
)
QUEUE_HEARTBEAT_INTERVAL_SECONDS = _timeout_seconds_from_env(
    "AOS_AGENT_HEARTBEAT_SECONDS", default=30, minimum=1,
)
QUEUE_STUCK_TIMEOUT_SECONDS = _timeout_seconds_from_env(
    "AOS_AGENT_LEASE_SECONDS", default=90, minimum=5,
)
AGENT_GRACEFUL_TERMINATION_SECONDS = _timeout_seconds_from_env(
    "AOS_AGENT_GRACEFUL_TERMINATION_SECONDS", default=10, minimum=1,
)
QUEUE_FINALIZATION_TIMEOUT_SECONDS = _timeout_seconds_from_env(
    "AOS_AGENT_FINALIZATION_TIMEOUT_SECONDS", default=120, minimum=1,
)
AGENT_PARENT_TIMEOUT_SECONDS = (
    AGENT_STARTUP_TIMEOUT_SECONDS
    + AGENT_TIMEOUT_SECONDS
    + AGENT_GRACEFUL_TERMINATION_SECONDS
)
LOCAL_AGENT_ROUTE_LOG = LOGS_DIR / "local_agent_route.jsonl"


def _bounded_stream_tail(value: object, limit: int = 1200) -> str:
    text = _ANSI_ESCAPE_RE.sub("", str(value or "")).strip() if "_ANSI_ESCAPE_RE" in globals() else str(value or "").strip()
    return text if len(text) <= limit else text[-limit:]


def _classify_local_agent_failure(stderr: str, stdout: str, returncode: int | None) -> str:
    evidence = f"{stderr}\n{stdout}".lower()
    if any(marker in evidence for marker in ("not logged in", "authentication", "unauthorized", "login required", "401")):
        return "authentication_failure"
    if any(marker in evidence for marker in ("no such file or directory", "not found", "cannot execute")):
        return "binary_or_path_failure"
    if any(marker in evidence for marker in ("permission denied", "operation not permitted", "read-only file system")):
        return "permission_failure"
    if returncode not in (None, 0):
        return "agent_process_failure"
    return "agent_output_failure"


def _terminate_process_group(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        process.terminate()
    try:
        process.wait(timeout=AGENT_GRACEFUL_TERMINATION_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
        process.wait(timeout=5)


def _codex_json_summary(stdout: str) -> tuple[str, dict, str, bool]:
    final_message = ""
    usage: dict[str, int] = {}
    session_id = ""
    startup_confirmed = False
    counters = {key: UNAVAILABLE_CLI_VALUE for key in USAGE_COUNTER_FIELDS}
    for raw in str(stdout or "").splitlines():
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        event_type = str(event.get("type") or "")
        if event_type == "thread.started":
            startup_confirmed = True
            session_id = str(event.get("thread_id") or event.get("session_id") or event.get("id") or "")
        if event_type == "item.completed" and isinstance(event.get("item"), dict):
            item = event["item"]
            if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
                final_message = item["text"].strip()
        if event_type == "turn.completed" and isinstance(event.get("usage"), dict):
            for source, target in (
                ("input_tokens", "input_tokens"),
                ("output_tokens", "output_tokens"),
                ("cached_input_tokens", "cached_input_tokens"),
                ("reasoning_output_tokens", "reasoning_tokens"),
            ):
                value = event["usage"].get(source)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    usage[target] = value
            if "input_tokens" in usage and "output_tokens" in usage:
                usage["total_tokens"] = usage["input_tokens"] + usage["output_tokens"]
        containers = [event]
        containers.extend(event[key] for key in ("usage", "usage_counters", "metrics") if isinstance(event.get(key), dict))
        for container in containers:
            for source, target in (
                *((key, key) for key in USAGE_COUNTER_FIELDS),
                ("input_tokens", "total_input"),
                ("cached_input_tokens", "cached_input"),
                ("output_tokens", "output"),
                ("reasoning_output_tokens", "reasoning"),
            ):
                value = container.get(source)
                if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                    counters[target] = value
    # turn.completed counters are cumulative. The final event replaces every
    # preceding event; never sum snapshots or retain fields omitted by a
    # malformed terminal event.
    snapshot = cumulative_usage_snapshot(stdout)
    for key in ("total_input", "cached_input", "non_cached_input", "fresh_input", "output", "reasoning", "input_plus_output"):
        counters[key] = UNAVAILABLE_CLI_VALUE
    usage = {}
    if snapshot.get("available"):
        usage = {
            "input_tokens": snapshot["input_tokens"],
            "output_tokens": snapshot["output_tokens"],
            "total_tokens": snapshot["cumulative_tokens"],
        }
        counters["total_input"] = snapshot["input_tokens"]
        counters["output"] = snapshot["output_tokens"]
        if snapshot.get("cached_input_tokens") is not None:
            usage["cached_input_tokens"] = snapshot["cached_input_tokens"]
            counters["cached_input"] = snapshot["cached_input_tokens"]
        if snapshot.get("reasoning_output_tokens") is not None:
            usage["reasoning_tokens"] = snapshot["reasoning_output_tokens"]
            counters["reasoning"] = snapshot["reasoning_output_tokens"]
    elif any(marker in str(snapshot.get("reason") or "") for marker in ("exceeds provider", "exceeds provider output")):
        usage["normalization_error"] = str(snapshot["reason"])

    total_input = counters.get("total_input")
    cached_input = counters.get("cached_input")
    output = counters.get("output")
    if isinstance(total_input, int) and isinstance(cached_input, int) and cached_input <= total_input:
        counters["non_cached_input"] = total_input - cached_input
        counters["fresh_input"] = total_input - cached_input
        usage["fresh_input_tokens"] = total_input - cached_input
        usage["cache_ratio"] = round(cached_input / max(total_input - cached_input, 1), 6)
    elif isinstance(total_input, int) and isinstance(cached_input, int):
        usage["normalization_error"] = "cached_input_tokens exceeds provider-total input_tokens"
    if isinstance(total_input, int) and isinstance(output, int):
        counters["input_plus_output"] = total_input + output
    if usage:
        labels = (
            ("input_tokens", "input"),
            ("output_tokens", "output"),
            ("cached_input_tokens", "cached input"),
            ("reasoning_tokens", "reasoning"),
            ("total_tokens", "total"),
        )
        token_text = "Token usage: " + ", ".join(f"{label} {usage[key]}" for key, label in labels if key in usage)
        token_usage = {"available": True, **usage, **counters}
        if session_id:
            token_usage["session_id"] = session_id
    else:
        token_text = "Token usage: unavailable from current CLI output"
        token_usage = {"available": False, **counters}
    return final_message, token_usage, token_text, startup_confirmed or bool(session_id)


def _write_codex_stream_artifacts(invocation_id: str, stdout: str, stderr: str) -> list[str]:
    """Persist raw Codex streams; callers retain only bounded summaries."""
    artifact_dir = BASE_DIR / "logs" / "codex_sessions"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for suffix, content in (("stdout.jsonl", stdout), ("stderr.txt", stderr)):
        if not content:
            continue
        target = artifact_dir / f"{invocation_id}.{suffix}"
        durable_replace_text(target, content if content.endswith("\n") else content + "\n")
        paths.append(target.relative_to(BASE_DIR).as_posix())
    return paths


def _write_codex_context_handoff(
    invocation_id: str,
    session_id: str,
    prompt: str,
    usage: dict,
    stream_artifacts: list[str],
    final_message: str,
    item: dict | None,
) -> str:
    """Write a compact continuation receipt; raw evidence remains path-only."""
    directory = BASE_DIR / "logs" / "codex_handoffs"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{invocation_id}.md"
    task_summary = re.sub(r"\s+", " ", str(prompt or "")).strip()[:2_000]
    compact_result = re.sub(r"\s+", " ", str(final_message or "")).strip()[:600] or "No final agent message before supervised handoff."
    lines = [
        "# Codex context handoff receipt",
        "> Revisit: when the linked task continuation is complete. · Last touched: 2026-07-19.",
        "",
        "- Session mode: fresh ephemeral; transcript resume forbidden",
        f"- Completed session ID: `{session_id}`",
        f"- Work item ID: `{str((item or {}).get('id') or 'direct')}`",
        f"- Configured handoff boundary: 50% / {CONTEXT_HANDOFF_THRESHOLD_TOKENS} cumulative tokens",
        f"- Observed cumulative usage: `{json.dumps(usage, sort_keys=True)}`",
        f"- Original task summary: {task_summary}",
        f"- Compact result at boundary: {compact_result}",
        "- Raw evidence artifacts (inspect selectively; never paste wholesale):",
        *(f"  - `{path}`" for path in stream_artifacts),
        "",
        "Continue from repository state plus this receipt. Do not replay or recover the prior transcript.",
    ]
    durable_replace_text(target, "\n".join(lines).rstrip() + "\n")
    return target.relative_to(BASE_DIR).as_posix()


def _local_agent_route_log(payload: dict) -> str:
    path = LOCAL_AGENT_ROUTE_LOG if BASE_DIR == _IMPORTED_BASE_DIR else BASE_DIR / "logs" / "local_agent_route.jsonl"
    safe = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        **payload,
    }
    append_root, append_path = _authoritative_append_target(path)
    durable_append_text(append_root, append_path, json.dumps(safe, ensure_ascii=False, sort_keys=True) + "\n")
    return _safe_relative(path) if BASE_DIR == _IMPORTED_BASE_DIR else "logs/local_agent_route.jsonl"


def _run_codex_local(prompt: str, item: dict | None = None, *, _handoff_depth: int = 0) -> dict:
    """Run the real Codex CLI under the authoritative Linux user/root with split timeouts."""
    started_at = time.monotonic()
    item_id = str((item or {}).get("id") or "")
    invocation = {**codex_invocation_metadata(CODEX_TARGET), "invocation_id": f"codex-{uuid.uuid4().hex}"}
    try:
        validate_codex_runtime(BASE_DIR, CODEX_TARGET)
        command = build_codex_exec_command(CODEX_TARGET)
        env = build_codex_environment(CODEX_TARGET)
        prepared_prompt = prepare_codex_fresh_prompt(prompt)
        invocation["initial_prompt_bytes"] = len(prepared_prompt.encode("utf-8"))
    except CodexPolicyError as exc:
        detail = str(exc)
        log_path = _local_agent_route_log({
            "route": "codex", "item_id": item_id, "success": False,
            "failure_class": "configuration_defect", "stage": "policy_preflight",
            "elapsed_seconds": 0.0, "stderr_tail": detail, "stdout_tail": "",
            **invocation,
        })
        return {
            "success": False, "output": detail, "stdout": "", "stderr": detail,
            "returncode": 78, "failure_class": "configuration_defect", "command_stage": "policy_preflight",
            "log_path": log_path, "token_usage": {"available": False},
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "invocation": invocation,
        }

    try:
        process = subprocess.Popen(
            command,
            cwd=invocation["cwd"],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as exc:
        elapsed = round(time.monotonic() - started_at, 3)
        failure_class = _classify_local_agent_failure(str(exc), "", None)
        log_path = _local_agent_route_log({
            "route": "codex", "item_id": item_id, "success": False, "failure_class": failure_class,
            "stage": "process_start", "elapsed_seconds": elapsed, "stderr_tail": _bounded_stream_tail(exc), "stdout_tail": "",
            **invocation,
        })
        return {
            "success": False, "output": str(exc), "stdout": "", "stderr": str(exc), "returncode": -1,
            "failure_class": failure_class, "command_stage": "process_start", "elapsed_seconds": elapsed,
            "log_path": log_path, "token_usage": {"available": False},
            "token_usage_text": "Token usage: unavailable from current CLI output",
            "invocation": invocation,
        }

    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    startup_confirmed = False
    timed_out = False
    handoff_triggered = False
    handoff_usage: dict = {}
    command_stage = "startup"
    startup_deadline = time.monotonic() + AGENT_STARTUP_TIMEOUT_SECONDS
    execution_deadline: float | None = None
    selector = selectors.DefaultSelector()
    assert process.stdout is not None and process.stderr is not None and process.stdin is not None
    selector.register(process.stdout, selectors.EVENT_READ, stdout_chunks)
    selector.register(process.stderr, selectors.EVENT_READ, stderr_chunks)
    try:
        try:
            process.stdin.write(prepared_prompt.encode("utf-8"))
            process.stdin.close()
        except BrokenPipeError:
            pass
        while selector.get_map():
            now = time.monotonic()
            deadline = execution_deadline if startup_confirmed else startup_deadline
            if now >= deadline:
                timed_out = True
                command_stage = "execution" if startup_confirmed else "startup"
                _terminate_process_group(process)
                break
            events = selector.select(timeout=min(0.25, max(0.01, deadline - now)))
            for key, _ in events:
                try:
                    chunk = os.read(key.fileobj.fileno(), 65536)
                except OSError:
                    chunk = b""
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                key.data.append(chunk)
                if key.fileobj is process.stdout and not startup_confirmed:
                    partial = b"".join(stdout_chunks).decode("utf-8", errors="replace")
                    _, _, _, startup_confirmed = _codex_json_summary(partial)
                    if startup_confirmed:
                        command_stage = "execution"
                        execution_deadline = time.monotonic() + AGENT_TIMEOUT_SECONDS
                if key.fileobj is process.stdout and startup_confirmed:
                    partial = b"".join(stdout_chunks).decode("utf-8", errors="replace")
                    snapshot = cumulative_usage_snapshot(partial)
                    if (
                        snapshot.get("available")
                        and int(snapshot["cumulative_tokens"]) >= CONTEXT_HANDOFF_THRESHOLD_TOKENS
                        and process.poll() is None
                    ):
                        handoff_triggered = True
                        handoff_usage = snapshot
                        command_stage = "context_handoff"
                        _terminate_process_group(process)
                        break
            if handoff_triggered:
                break
            if process.poll() is not None and not events:
                for key in list(selector.get_map().values()):
                    try:
                        chunk = os.read(key.fileobj.fileno(), 65536)
                    except OSError:
                        chunk = b""
                    if chunk:
                        key.data.append(chunk)
                    else:
                        selector.unregister(key.fileobj)
        if process.poll() is None:
            process.wait(timeout=5)
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()

    stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
    stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")
    final_message, token_usage, token_usage_text, parsed_startup = _codex_json_summary(stdout)
    stream_artifacts = _write_codex_stream_artifacts(invocation["invocation_id"], stdout, stderr)
    try:
        clean_session_id = require_clean_session_id(stdout)
    except CodexPolicyError as exc:
        clean_session_id = ""
        clean_session_error = str(exc)
    else:
        clean_session_error = ""
        token_usage["session_id"] = clean_session_id
    token_usage.setdefault("invocation_id", invocation["invocation_id"])
    startup_confirmed = startup_confirmed or parsed_startup
    elapsed = round(time.monotonic() - started_at, 3)
    if handoff_triggered and not clean_session_error and _handoff_depth < MAX_CONTEXT_HANDOFFS:
        handoff_artifact = _write_codex_context_handoff(
            invocation["invocation_id"], clean_session_id, prompt, handoff_usage,
            stream_artifacts, final_message, item,
        )
        handoff_log_path = _local_agent_route_log({
            "route": "codex", "item_id": item_id, "success": True,
            "failure_class": None, "stage": "context_handoff",
            "elapsed_seconds": round(time.monotonic() - started_at, 3),
            "returncode": process.returncode,
            "startup_timeout_seconds": AGENT_STARTUP_TIMEOUT_SECONDS,
            "execution_timeout_seconds": AGENT_TIMEOUT_SECONDS,
            **invocation,
            "stdout_tail": _bounded_stream_tail(stdout),
            "stderr_tail": _bounded_stream_tail(stderr),
            "token_usage_text": token_usage_text,
            "session_id": clean_session_id,
            "stream_artifacts": stream_artifacts,
            "handoff_artifact": handoff_artifact,
        })
        continuation_prompt = "\n".join((
            "Continue the same bounded task in a new fresh ephemeral session.",
            f"Read the compact handoff receipt at `{handoff_artifact}` and inspect only its named repository/artifact paths as needed.",
            "Do not resume, recover, or replay the prior transcript. Do not paste raw logs, test output, diffs, screenshots, or browser evidence into this prompt or your closeout.",
            "Complete the remaining task, validate it, and return the required compact receipt.",
        ))
        continued = _run_codex_local(continuation_prompt, item, _handoff_depth=_handoff_depth + 1)
        prior_session = {
            "session_id": clean_session_id,
            "invocation": invocation,
            "token_usage": token_usage,
            "token_usage_text": token_usage_text,
            "handoff_artifact": handoff_artifact,
            "log_path": handoff_log_path,
            "stream_artifacts": stream_artifacts,
            "threshold_usage": handoff_usage,
        }
        return {
            **continued,
            "handoff_sessions": [prior_session, *list(continued.get("handoff_sessions") or [])],
            "handoff_artifacts": [handoff_artifact, *list(continued.get("handoff_artifacts") or [])],
            "stream_artifacts": [*stream_artifacts, handoff_artifact, *list(continued.get("stream_artifacts") or [])],
            "retained_output_truncated": bool(continued.get("retained_output_truncated")) or len(stdout) > 16_000 or len(stderr) > 16_000,
        }
    if handoff_triggered and not clean_session_error:
        failure_class = "context_handoff_limit"
        command_stage = "context_handoff"
        output = f"Codex reached the context handoff boundary after {MAX_CONTEXT_HANDOFFS} fresh continuations"
        returncode = 78
        success = False
    elif timed_out:
        failure_class = f"{command_stage}_timeout"
        boundary = AGENT_STARTUP_TIMEOUT_SECONDS if command_stage == "startup" else AGENT_TIMEOUT_SECONDS
        output = f"Codex {command_stage} timed out after {boundary}s"
        returncode = process.returncode if process.returncode is not None else -1
        success = False
    elif token_usage.get("normalization_error"):
        failure_class = "usage_semantics_failure"
        command_stage = "usage_normalization"
        output = f"Codex usage semantics invalid: {token_usage['normalization_error']}"
        returncode = process.returncode if process.returncode is not None else 78
        success = False
    elif clean_session_error:
        failure_class = "clean_session_creation_failure"
        command_stage = "clean_session_creation"
        output = clean_session_error
        returncode = process.returncode if process.returncode is not None else 78
        success = False
    else:
        returncode = int(process.returncode or 0)
        success = returncode == 0 and startup_confirmed
        failure_class = "" if success else _classify_local_agent_failure(stderr, stdout, returncode)
        output = final_message or _bounded_stream_tail(stdout or stderr, 4000) or "(no output)"
        if success:
            command_stage = "completion"
    log_path = _local_agent_route_log({
        "route": "codex", "item_id": item_id, "success": success,
        "failure_class": failure_class or None, "stage": command_stage,
        "elapsed_seconds": elapsed, "returncode": returncode,
        "startup_timeout_seconds": AGENT_STARTUP_TIMEOUT_SECONDS,
        "execution_timeout_seconds": AGENT_TIMEOUT_SECONDS,
        **invocation,
        "stdout_tail": _bounded_stream_tail(stdout), "stderr_tail": _bounded_stream_tail(stderr),
        "token_usage_text": token_usage_text,
        "session_id": clean_session_id or None,
        "stream_artifacts": stream_artifacts,
    })
    return {
        "success": success,
        "output": output,
        "stdout": stdout if len(stdout) <= 16_000 else _bounded_stream_tail(stdout, 4000),
        "stderr": stderr if len(stderr) <= 16_000 else _bounded_stream_tail(stderr, 4000),
        "stream_artifacts": stream_artifacts,
        "retained_output_truncated": len(stdout) > 16_000 or len(stderr) > 16_000,
        "returncode": returncode,
        "timed_out": timed_out,
        "timeout_seconds": AGENT_STARTUP_TIMEOUT_SECONDS if command_stage == "startup" else AGENT_TIMEOUT_SECONDS,
        "startup_timeout_seconds": AGENT_STARTUP_TIMEOUT_SECONDS,
        "execution_timeout_seconds": AGENT_TIMEOUT_SECONDS,
        "elapsed_seconds": elapsed,
        "failure_class": failure_class or None,
        "command_stage": command_stage,
        "log_path": log_path,
        "token_usage": token_usage,
        "token_usage_text": token_usage_text,
        "session_id": clean_session_id or None,
        "invocation": invocation,
    }


def _path_for_wsl_command(path) -> str:
    raw = str(path)
    if re.match(r"^[A-Za-z]:[\\/]", raw) or re.match(r"^/mnt/[a-z](?:/|$)", raw, re.IGNORECASE):
        raise AuthorityError("Windows and Windows-mounted paths are unsupported by the Linux backend runtime")
    return raw


def _quoted_linux_path(path: Path | str) -> str:
    raw = _path_for_wsl_command(path)
    return "'" + raw.replace("'", "'\"'\"'") + "'"


def _run_wsl(bash_cmd: str, timeout: int = 60) -> dict:
    """Compatibility helper for bounded commands in the authoritative Linux root."""
    root = _quoted_linux_path(BASE_DIR)
    full_cmd = f"{WSL_ENV}; export AOS_ROOT={root}; cd {root}; {bash_cmd}"
    try:
        result = subprocess.run(
            ["bash", "-lc", full_cmd],
            cwd=str(BASE_DIR),
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
        return {"success": False, "output": "bash not found — Linux runtime unavailable", "returncode": -1}
    except Exception as e:
        return {"success": False, "output": f"Error: {e}", "returncode": -1}


def _run_wsl_supervised(bash_cmd: str, timeout: int, *, on_process_start=None) -> dict:
    """Process-group-supervised helper for long-running Claude execution."""
    root = _quoted_linux_path(BASE_DIR)
    full_cmd = f"{WSL_ENV}; export AOS_ROOT={root}; cd {root}; {bash_cmd}"
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            ["bash", "-lc", full_cmd], cwd=str(BASE_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            start_new_session=True, close_fds=True,
        )
        if on_process_start is not None:
            try:
                on_process_start(process)
            except Exception:
                _terminate_process_group(process)
                raise
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            partial_stdout = str(exc.stdout or "")
            partial_stderr = str(exc.stderr or "")
            _terminate_process_group(process)
            final_stdout, final_stderr = process.communicate()
            stdout = partial_stdout + str(final_stdout or "")
            stderr = partial_stderr + str(final_stderr or "")
            timed_out = True
        stdout = stdout.strip()
        stderr = stderr.strip()
        elapsed = round(time.monotonic() - started, 3)
        if timed_out:
            return {
                "success": False, "output": f"Command timed out after {timeout}s",
                "stdout": stdout, "stderr": stderr or f"Command timed out after {timeout}s",
                "returncode": process.returncode if process.returncode is not None else -1,
                "timed_out": True, "timeout_seconds": timeout, "elapsed_seconds": elapsed,
                "graceful_termination_seconds": AGENT_GRACEFUL_TERMINATION_SECONDS,
            }
        return {
            "success": process.returncode == 0,
            "output": stdout or stderr or "(no output)",
            "stdout": stdout, "stderr": stderr, "returncode": process.returncode,
            "timeout_seconds": timeout, "elapsed_seconds": elapsed,
            "graceful_termination_seconds": AGENT_GRACEFUL_TERMINATION_SECONDS,
        }
    except FileNotFoundError:
        return {"success": False, "output": "bash not found — Linux runtime unavailable", "returncode": -1}
    except Exception as exc:
        return {"success": False, "output": f"Error: {exc}", "returncode": -1}


def _run_agentic_os_clean_bash(bash_cmd: str, timeout: int = 60) -> dict:
    """Run directly in the current supported Linux runtime."""
    return _run_wsl(bash_cmd, timeout=timeout)


def _http_endpoint_reachable(url: str, timeout: int = 2) -> bool:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True
    except (OSError, urllib.error.URLError):
        return False


def _http_endpoint_headers(url: str, timeout: int = 2) -> dict:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "success": True,
                "status_code": getattr(response, "status", 200),
                "final_url": response.geturl(),
                "headers": {key.lower(): value for key, value in response.headers.items()},
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        return {
            "success": True,
            "status_code": exc.code,
            "final_url": exc.geturl(),
            "headers": {key.lower(): value for key, value in exc.headers.items()},
            "error": "",
        }
    except (OSError, urllib.error.URLError) as exc:
        return {"success": False, "status_code": None, "final_url": "", "headers": {}, "error": str(exc)}


def _frame_ancestor_sources(csp: str) -> list[str]:
    for directive in str(csp or "").split(";"):
        parts = directive.strip().split()
        if parts and parts[0].lower() == "frame-ancestors":
            return parts[1:]
    return []


def _hermes_frame_status(headers: dict) -> tuple[bool, str]:
    x_frame = str(headers.get("x-frame-options") or "").strip()
    if x_frame:
        value = x_frame.lower()
        if value in {"deny", "sameorigin"} or value.startswith("allow-from"):
            return False, f"X-Frame-Options: {x_frame}"

    csp = str(headers.get("content-security-policy") or "").strip()
    sources = _frame_ancestor_sources(csp)
    if not sources:
        return True, ""

    normalized = {source.strip().strip('"').strip("'").lower() for source in sources}
    allowed_sources = {
        "*",
        "http://127.0.0.1:3010",
        "http://localhost:3010",
        "http://127.0.0.1:*",
        "http://localhost:*",
    }
    if "'none'" in normalized or "none" in normalized:
        return False, f"Content-Security-Policy: frame-ancestors {' '.join(sources)}"
    if "'self'" in normalized or "self" in normalized:
        return False, f"Content-Security-Policy: frame-ancestors {' '.join(sources)}"
    if normalized.intersection(allowed_sources):
        return True, ""
    return False, f"Content-Security-Policy: frame-ancestors {' '.join(sources)}"


def _poll_http_endpoint(url: str, timeout_seconds: float = 10.0, interval_seconds: float = 0.5) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        if _http_endpoint_reachable(url):
            return True
        time.sleep(interval_seconds)
    return False


def _parse_key_value_output(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in str(output or "").splitlines():
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", key):
            values[key] = value.strip()
    return values


def _hermes_dashboard_launcher_command(action: str) -> str:
    script = shlex.quote(_path_for_wsl_command(HERMES_DASHBOARD_LAUNCHER))
    workspace = shlex.quote(_path_for_wsl_command(BASE_DIR))
    return (
        f"cd {workspace} && "
        f"HERMES_DASHBOARD_HOST={shlex.quote(HERMES_DASHBOARD_HOST)} "
        f"HERMES_DASHBOARD_PORT={shlex.quote(str(HERMES_DASHBOARD_PORT))} "
        f"{script} {shlex.quote(action)}"
    )


def _hermes_dashboard_operator_command(action: str = "start") -> str:
    workspace = _path_for_wsl_command(BASE_DIR)
    return f"cd {shlex.quote(workspace)} && bash tools/aos-hermes-dashboard.sh {shlex.quote(action)}"


def _hermes_ui_status() -> dict:
    header_result = _http_endpoint_headers(HERMES_DASHBOARD_URL + "/")
    http_reachable = bool(header_result.get("success"))
    result = _run_agentic_os_clean_bash(_hermes_dashboard_launcher_command("status"), timeout=15)
    fields = _parse_key_value_output(result.get("stdout") or result.get("output") or "")
    state = fields.get("state")
    if http_reachable:
        state = "reachable"
    elif not result.get("success"):
        state = "configuration_missing"
    elif not state:
        state = "configuration_missing"

    supported = state not in {"unsupported", "configuration_missing"}
    embeddable, blocking_header = _hermes_frame_status(header_result.get("headers", {})) if http_reachable else (False, "")
    process_running = http_reachable or state in {"reachable", "starting"}
    launch_command = _hermes_dashboard_operator_command("start")
    final_state = "running_embedded" if http_reachable and embeddable else "running_window_only" if http_reachable else state
    return {
        "success": state != "configuration_missing",
        "state": final_state,
        "launcher_state": state,
        "reachable": http_reachable,
        "http_reachable": http_reachable,
        "process_running": process_running,
        "embeddable": embeddable,
        "blocking_header": blocking_header,
        "headers": {
            "x-frame-options": header_result.get("headers", {}).get("x-frame-options", ""),
            "content-security-policy": header_result.get("headers", {}).get("content-security-policy", ""),
        },
        "installed": supported,
        "supported": supported,
        "url": HERMES_DASHBOARD_URL,
        "iframe_url": HERMES_DASHBOARD_URL if http_reachable and embeddable else "",
        "host": HERMES_DASHBOARD_HOST,
        "port": HERMES_DASHBOARD_PORT,
        "version": fields.get("version", ""),
        "pid": fields.get("pid", ""),
        "root": fields.get("root", str(BASE_DIR)),
        "dist": fields.get("dist", ""),
        "reason": fields.get("reason", ""),
        "last_error": "" if http_reachable or result.get("success") else result.get("stderr") or result.get("output") or "",
        "target": "Hermes dashboard web UI",
        "runtime": WSL_DISTRO,
        "user": WSL_USER,
        "launcher": _safe_relative(HERMES_DASHBOARD_LAUNCHER),
        "launch_command": launch_command,
        "open_url": HERMES_DASHBOARD_URL if http_reachable else "",
        "headless_available": True,
        "headless_command": "aos-hermes status",
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


def _write_agent_prompt_file(prompt: str, prefix: str = "aos_prompt_") -> tuple[Path, str]:
    """Persist one prompt outside the shell command line and return Linux path."""
    _require_authority()
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


def _run_wsl_prompt_command(
    command_template: str,
    prompt: str,
    timeout: int,
    *,
    startup_timeout: int | None = None,
    on_process_start=None,
) -> dict:
    prompt_path, prompt_wsl_path = _write_agent_prompt_file(prompt)
    try:
        if startup_timeout is not None:
            startup = _run_wsl(
                "command -v aos-hermes >/dev/null && command -v aos-claude >/dev/null "
                "&& /home/liam/.local/npm/bin/claude --version",
                timeout=startup_timeout,
            )
            if not startup.get("success"):
                return {
                    **startup,
                    "command_stage": "startup",
                    "startup_timeout_seconds": startup_timeout,
                    "execution_timeout_seconds": timeout,
                    "parent_timeout_seconds": startup_timeout + timeout + AGENT_GRACEFUL_TERMINATION_SECONDS,
                }
        command = command_template.format(prompt_file=shlex.quote(prompt_wsl_path))
        result = (
            _run_wsl_supervised(command, timeout=timeout, on_process_start=on_process_start)
            if startup_timeout is not None
            else _run_wsl(command, timeout=timeout)
        )
        return {
            **result,
            "command_stage": "execution" if result.get("timed_out") else "completion",
            "startup_timeout_seconds": startup_timeout,
            "execution_timeout_seconds": timeout,
            "parent_timeout_seconds": (startup_timeout or 0) + timeout + AGENT_GRACEFUL_TERMINATION_SECONDS,
            "startup_output": startup.get("output", "") if startup_timeout is not None else "",
        }
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
    durable_replace_text(RESULTS_DIR / filename, content.rstrip() + "\n")
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


def _read_jsonl_file(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
    except OSError:
        return []
    return records


def _safe_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(BASE_DIR.resolve()).as_posix()
    except ValueError:
        return path.name


def _redacted_preview(text: str, limit: int = 4000) -> str:
    safe_lines = []
    secret_re = re.compile(r"(secret|token|api[_-]?key|oauth|password|credential|authorization|bearer)", re.IGNORECASE)
    for line in str(text or "").splitlines():
        safe_lines.append("[redacted sensitive line]" if secret_re.search(line) else line)
    return "\n".join(safe_lines)[:limit]


def _backend_env_path() -> Path:
    return Path(__file__).with_name(".env")


def _read_backend_env(keys: set[str] | None = None) -> dict[str, str]:
    """Read selected dashboard backend env values without printing or logging them."""
    values: dict[str, str] = {}
    path = _backend_env_path()
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    wanted = {key.upper() for key in keys} if keys else None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().upper()
        if wanted is not None and key not in wanted:
            continue
        values[key] = value.strip().strip("'\"")
    for key in keys or set():
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def _notifications_config() -> dict:
    try:
        value = json.loads(NOTIFICATIONS_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _public_latitude_status() -> dict:
    return latitude_telemetry.config_status()


def _latitude_safe_event(event_type: str, component: str, status: str, task_id: str = "wp11-phase-d", token_usage: dict | None = None) -> dict:
    payload = {
        "event_type": event_type,
        "task_id": task_id,
        "component": component,
        "status": status,
        "timestamp": _utc_now_iso(),
        "local_run_id": f"local-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
    }
    usage = token_usage if isinstance(token_usage, dict) else {}
    basis = usage.get("basis")
    if basis in {"exact", "estimate", "unavailable", "no_agent_invocation"}:
        payload["token_totals"] = {
            "basis": basis,
            "total": usage.get("total") if basis in {"exact", "estimate"} else None,
        }
    else:
        payload["token_totals"] = {"basis": "unavailable", "total": None}
    return payload


def _send_latitude_event(event: dict) -> dict:
    result = latitude_telemetry.send_event(event)
    return {
        "success": bool(result.get("sent")),
        "status": "sent" if result.get("sent") else "degraded",
        "event_sending": "sent" if result.get("sent") else "degraded",
        **_public_latitude_status(),
        "degraded_reason": result.get("degraded_reason") or _public_latitude_status().get("degraded_reason"),
    }


_DASHBOARD_MARKDOWN_BLOCK_RE = re.compile(
    r"(^|[/.])(\.env|.*secret.*|.*credential.*|.*password.*|.*token.*)|"
    r"north[\s_-]*shore|old[\s_-]*(?:ubuntu|hermes|vault|runtime)|legacy[_-]?harvest|old[_-]?zpc|\bzpc\b|"
    r"connectors?/.*(?:secret|credential|token|\.env)",
    re.IGNORECASE,
)


def _parse_frontmatter_value(value: str) -> object:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        text = text[1:-1]
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    return text


def _parse_markdown_frontmatter(text: str) -> dict:
    lines = str(text or "").splitlines()
    if not lines or lines[0].strip() != "---":
        return {"frontmatter": {}, "frontmatter_lines": [], "body": str(text or "")}
    closing = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing = index
            break
    if closing is None:
        return {"frontmatter": {}, "frontmatter_lines": [], "body": str(text or "")}

    metadata = {}
    frontmatter_lines = lines[1:closing]
    for line in frontmatter_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        if not key:
            continue
        metadata[key] = _parse_frontmatter_value(value)
    return {
        "frontmatter": metadata,
        "frontmatter_lines": frontmatter_lines,
        "body": "\n".join(lines[closing + 1:]).lstrip("\n"),
    }


def _frontmatter_text_value(metadata: dict, key: str, default: str = "") -> str:
    value = metadata.get(key)
    if value is None:
        return default
    return str(value).strip()


def _skill_lane_from_metadata(metadata: dict, fallback: str) -> str:
    lane = _frontmatter_text_value(metadata, "lane")
    if lane:
        return lane
    source = _frontmatter_text_value(metadata, "source")
    if source:
        return source
    when = _frontmatter_text_value(metadata, "when-to-use")
    owner = re.search(r"Owner:\s*aos-([A-Za-z_-]+)", when)
    return owner.group(1).replace("_", "-") if owner else fallback


def _skill_trust_from_metadata(metadata: dict, fallback: str = "") -> str:
    trust = _frontmatter_text_value(metadata, "trust")
    if trust:
        return trust
    when = _frontmatter_text_value(metadata, "when-to-use")
    found = re.search(r"Trust:\s*([^.;]+)", when)
    return found.group(1).strip() if found else fallback


def _render_markdown_frontmatter(frontmatter_lines: list[str], name: str, description: str, body: str) -> str:
    lines = list(frontmatter_lines or [])
    seen = set()

    def replace_or_append(key: str, value: str) -> None:
        safe_value = str(value or "").strip()
        serialized = json.dumps(safe_value) if any(ch in safe_value for ch in (":", "#", '"', "'")) else safe_value
        pattern = re.compile(rf"^\s*{re.escape(key)}\s*:")
        for index, line in enumerate(lines):
            if pattern.match(line):
                lines[index] = f"{key}: {serialized}"
                seen.add(key)
                return
        seen.add(key)
        lines.append(f"{key}: {serialized}")

    replace_or_append("name", name)
    replace_or_append("description", description)
    clean_body = str(body or "").strip("\n")
    return "---\n" + "\n".join(lines).rstrip() + "\n---\n" + clean_body + "\n"


def _safe_dashboard_markdown_path(path_value: str, *, require_writable: bool = False) -> Path:
    raw = str(path_value or "").strip().replace("\\", "/")
    if not raw:
        raise ValueError("path must not be empty")
    if Path(raw).is_absolute() or re.match(r"^[A-Za-z]:/", raw):
        raise ValueError("path must be workspace root-relative")
    if _DASHBOARD_MARKDOWN_BLOCK_RE.search(raw):
        raise ValueError("path is blocked by dashboard safety policy")
    target = (BASE_DIR / raw).resolve()
    try:
        rel = target.relative_to(BASE_DIR.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("path must stay inside the live workspace") from exc
    if _DASHBOARD_MARKDOWN_BLOCK_RE.search(rel):
        raise ValueError("path is blocked by dashboard safety policy")
    if target.suffix.lower() != ".md":
        raise ValueError("only markdown files are allowed")
    allowed = rel.startswith("skills/") or rel.startswith("workflows/")
    if require_writable and not allowed:
        raise ValueError("saves are limited to skills/ and workflows/ markdown files")
    if rel.startswith("skills/") and not rel.endswith("/SKILL.md"):
        raise ValueError("skill saves are limited to skills/*/SKILL.md")
    return target


def _markdown_title(text: str, fallback: str) -> str:
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
        if stripped:
            return stripped[:90]
    return fallback


_WORKFLOW_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
_WORKFLOW_MAX_BYTES = 512 * 1024


def _workflow_root() -> Path:
    return BASE_DIR / "workflows"


def _workflow_editor_roots() -> list[Path]:
    return [_workflow_root(), BASE_DIR / "dashboard" / "test-fixtures" / "workflows"]


def _workflow_registry_entries() -> list[dict]:
    path = _workflow_root() / "workflow_registry.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    return [row for row in payload.get("workflows", []) if isinstance(row, dict)] if isinstance(payload, dict) else []


def _meaningful_workflow_identifier(value: object) -> str:
    raw = str(value or "").strip()
    if not raw or re.fullmatch(r"[0-9a-fA-F-]{24,}", raw):
        return ""
    clean = re.sub(r"[_-]+", " ", raw).strip()
    return clean.title() if re.search(r"[A-Za-z]", clean) else ""


def _first_markdown_heading(text: str) -> str:
    parsed = _parse_markdown_frontmatter(text)
    for line in parsed["body"].splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match and match.group(1).strip() not in {"---", "..."}:
            return match.group(1).strip()
    return ""


def _workflow_display_name(path: Path, text: str, workflow_id: str = "", metadata: dict | None = None) -> str:
    parsed = _parse_markdown_frontmatter(text)
    combined = {**(metadata or {}), **parsed["frontmatter"]}
    for key in ("title", "name"):
        value = _frontmatter_text_value(combined, key)
        if value and value not in {"---", "..."}:
            return value
    identifier = combined.get("id") or combined.get("identifier") or workflow_id
    identifier_name = _meaningful_workflow_identifier(identifier)
    if identifier_name:
        return identifier_name
    heading = _first_markdown_heading(text)
    if heading:
        return heading
    fallback = path.stem if path.stem.lower() != "workflow" else path.parent.name
    return re.sub(r"[_-]+", " ", fallback).strip().title() or "Untitled workflow"


def _workflow_revision(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _workflow_path_for_id(workflow_id: str, *, writable: bool = False) -> Path:
    raw = str(workflow_id or "").strip()
    if not _WORKFLOW_ID_RE.fullmatch(raw):
        raise ValueError("workflow identifier is invalid; absolute paths and traversal are not allowed")
    existing = [(root, root / raw / "workflow.md") for root in _workflow_editor_roots() if (root / raw / "workflow.md").exists()]
    if len(existing) != 1:
        if not existing:
            raise FileNotFoundError(raw)
        raise ValueError("workflow identifier is ambiguous across approved roots")
    root, target = existing[0]
    resolved_root = root.resolve()
    try:
        resolved_target = target.resolve(strict=True)
        resolved_target.relative_to(resolved_root)
    except FileNotFoundError as exc:
        raise FileNotFoundError(raw) from exc
    except ValueError as exc:
        raise ValueError("workflow source must stay inside the approved workflow root") from exc
    if target.is_symlink() or any(part.is_symlink() for part in (target.parent,)):
        raise ValueError("symlinked workflow sources are read-only")
    if _DASHBOARD_MARKDOWN_BLOCK_RE.search(target.relative_to(BASE_DIR).as_posix()):
        raise ValueError("workflow source is blocked by dashboard safety policy")
    if not target.is_file():
        raise ValueError("workflow source must be a regular file")
    if target.suffix.lower() != ".md" or target.name != "workflow.md":
        raise ValueError("only canonical workflows/*/workflow.md sources are editable")
    if target.stat().st_size > _WORKFLOW_MAX_BYTES:
        raise ValueError("workflow source exceeds the editor size limit")
    return resolved_target if writable else target


def _validate_workflow_content(content: str) -> None:
    if not isinstance(content, str):
        raise ValueError("workflow content must be text")
    if "\x00" in content:
        raise ValueError("workflow content contains an invalid NUL character")
    if len(content.encode("utf-8")) > _WORKFLOW_MAX_BYTES:
        raise ValueError("workflow content exceeds the editor size limit")
    if not content.strip():
        raise ValueError("workflow content must not be blank")


def _token_component_total(record: dict) -> tuple[int | None, int | None]:
    usage = record.get("token_usage") if isinstance(record.get("token_usage"), dict) else {}
    totals = usage.get("totals") if isinstance(usage.get("totals"), dict) else {}
    try:
        input_tokens = int(totals.get("input", 0))
        output_tokens = int(totals.get("output", 0))
        return input_tokens, output_tokens
    except (TypeError, ValueError):
        return None, None


def _ledger_no_agent_invocation(record: dict) -> bool:
    usage = record.get("token_usage") if isinstance(record.get("token_usage"), dict) else {}
    unavailable = usage.get("unavailable") if isinstance(usage.get("unavailable"), list) else []
    return bool(
        record.get("no_agent_invocation")
        or usage.get("no_agent_invocation")
        or any(str(value).strip().lower() == "no agent invocation" for value in unavailable)
    )


def _ledger_exact_invocation(record: dict) -> bool:
    usage = record.get("token_usage") if isinstance(record.get("token_usage"), dict) else {}
    return any(
        isinstance(workbench, dict) and workbench.get("source") == "reported"
        for workbench in (usage.get("workbenches") or [])
    ) or ("tokens" in record and str(record.get("basis") or "exact") == "exact")


def _effective_token_ledger_records(records: list[dict]) -> list[dict]:
    """Deduplicate invocation identities and suppress item placeholders behind exact usage."""
    exact_items = {str(row.get("item_id") or row.get("task_id") or "") for row in records if _ledger_exact_invocation(row)}
    selected: dict[tuple[str, str], tuple[int, int, dict]] = {}
    passthrough: list[tuple[int, dict]] = []
    for position, row in enumerate(records):
        item_id = str(row.get("item_id") or row.get("task_id") or "")
        if item_id in exact_items and not row.get("session_id") and _ledger_no_agent_invocation(row):
            continue
        session_id = str(row.get("session_id") or row.get("invocation_id") or "")
        if not item_id or not session_id:
            passthrough.append((position, row))
            continue
        rank = 2 if _ledger_exact_invocation(row) else 0 if _ledger_no_agent_invocation(row) else 1
        key = (item_id, session_id)
        prior = selected.get(key)
        if prior is None or rank > prior[0] or (rank == prior[0] and position > prior[1]):
            selected[key] = (rank, position, row)
    combined = passthrough + [(position, row) for _, position, row in selected.values()]
    return [row for _, row in sorted(combined, key=lambda value: value[0])]


def _read_token_ledger_records() -> list[dict]:
    records = _read_jsonl_file(TOKEN_LEDGER_FILE)
    records.extend(_read_jsonl_file(ROOT_TOKEN_LEDGER_FILE))
    return _effective_token_ledger_records(records)


def _local_date_from_record(value: object, tz: datetime.tzinfo | None = None) -> datetime.date | None:
    timestamp = _parse_record_timestamp(value)
    if not timestamp:
        return None
    return timestamp.astimezone(tz or datetime.datetime.now().astimezone().tzinfo).date()


def _token_basis_bucket(record: dict) -> tuple[str, int | None]:
    tokens, basis = _ledger_tokens_basis(record)
    basis = str(basis or "unavailable")
    if tokens is None:
        usage = record.get("token_usage") if isinstance(record.get("token_usage"), dict) else {}
        if _ledger_no_agent_invocation(record):
            return "no_agent_invocation", None
        return "unavailable", None
    if basis == "estimate":
        return "estimate", tokens
    return "exact", tokens


def _token_totals_for_date(target_date: datetime.date) -> dict:
    totals = {
        "exact": 0,
        "estimate": 0,
        "unavailable": 0,
        "no_agent_invocation": 0,
        "rows": [],
    }
    for record in _read_token_ledger_records():
        if _local_date_from_record(_ledger_timestamp(record)) != target_date:
            continue
        bucket, tokens = _token_basis_bucket(record)
        if bucket in {"exact", "estimate"} and tokens is not None:
            totals[bucket] += tokens
        else:
            totals[bucket] += 1
        totals["rows"].append({
            "task_id": _ledger_task_id(record),
            "component": _ledger_component(record),
            "basis": bucket,
            "tokens": tokens,
        })
    return totals


def _completed_items_for_date(target_date: datetime.date) -> list[dict]:
    done = []
    for item in _read_queue_items():
        if item.get("status") != "done":
            continue
        item_date = _local_date_from_record(item.get("updated_at") or item.get("created_at"))
        if item_date == target_date:
            done.append(_queue_public_item(item))
    return done


def _agentmail_allowlist() -> list[str]:
    allowlist = (_notifications_config().get("allowlist") or {}).get("agentmail_internal") or []
    return [_normalize_agentmail_recipient(str(value)) for value in allowlist if _normalize_agentmail_recipient(str(value))]


def _safe_recipient_label(recipient: str) -> str:
    normalized = _normalize_agentmail_recipient(recipient)
    return normalized if normalized in _agentmail_allowlist() else "not_allowlisted"


_AGENTMAIL_DIGEST_LOCK = threading.Lock()
_AGENTMAIL_EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
_AGENTMAIL_INTERNAL_RE = re.compile(r"^[a-z0-9._%+-]+@internal$")
_AGENTMAIL_PROVIDER = "composio"
_AGENTMAIL_TOOLKIT = "agent_mail"
_AGENTMAIL_ACTION = "AGENT_MAIL_SEND_EMAIL"
_AGENTMAIL_DEFAULT_INBOX_ID = "olmec1@agentmail.to"


def _normalize_agentmail_recipient(recipient: str) -> str:
    return str(recipient or "").strip().lower()


def _agentmail_recipient_allowlist_result(recipient: str) -> dict:
    normalized = _normalize_agentmail_recipient(recipient)
    allowlist = set(_agentmail_allowlist())
    if not normalized:
        return {"allowed": False, "recipient": normalized, "reason": "recipient is required"}
    if any(value in normalized for value in ("example.com", "example", "placeholder", "your-email", "todo")):
        return {"allowed": False, "recipient": normalized, "reason": "placeholder recipient rejected"}
    if not (_AGENTMAIL_EMAIL_RE.fullmatch(normalized) or _AGENTMAIL_INTERNAL_RE.fullmatch(normalized)):
        return {"allowed": False, "recipient": normalized, "reason": "malformed recipient rejected"}
    if normalized not in allowlist:
        return {"allowed": False, "recipient": normalized, "reason": "recipient is not in queue/notifications.json allowlist.agentmail_internal"}
    return {"allowed": True, "recipient": normalized, "reason": "allowlisted internal recipient"}


def _agentmail_digest_content_hash(digest: dict) -> str:
    body = str(digest.get("body") or "")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _agentmail_digest_idempotency_key(digest: dict) -> str:
    source = "|".join([
        str(digest.get("digest_id") or digest.get("digest_date") or ""),
        _normalize_agentmail_recipient(str(digest.get("recipient") or "")),
        _agentmail_digest_content_hash(digest),
    ])
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _digest_receipt_path(digest_date: str, recipient: str, idempotency_key: str | None = None) -> Path:
    digest_hash = hashlib.sha256(_normalize_agentmail_recipient(recipient).encode("utf-8")).hexdigest()[:12]
    suffix = f"_{idempotency_key[:16]}" if idempotency_key else ""
    return QUEUE_DIR / "receipts" / f"agentmail_digest_{digest_date}_{digest_hash}{suffix}.json"


def _agentmail_attempt_receipt_path(digest_date: str, recipient: str, idempotency_key: str) -> Path:
    base = _digest_receipt_path(digest_date, recipient, idempotency_key)
    if not base.exists():
        return base
    stamp = _utc_now_iso().replace(":", "").replace("-", "").replace("Z", "Z")
    return QUEUE_DIR / "receipts" / f"{base.stem}_{stamp}.json"


def _agentmail_success_receipt_for_key(idempotency_key: str) -> dict | None:
    receipts = QUEUE_DIR / "receipts"
    if not receipts.exists():
        return None
    for path in sorted(receipts.glob("agentmail_digest_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("idempotency_key") == idempotency_key and payload.get("sent") is True:
            return {**payload, "receipt_path": _safe_relative(path)}
    return None


def _agentmail_config() -> dict:
    config = (_notifications_config().get("agentmail") or {})
    if not isinstance(config, dict):
        config = {}
    return {
        "provider": str(config.get("provider") or _AGENTMAIL_PROVIDER),
        "toolkit": str(config.get("toolkit") or _AGENTMAIL_TOOLKIT),
        "action": str(config.get("action") or _AGENTMAIL_ACTION).strip().upper(),
        "inbox_id": str(config.get("inbox_id") or _AGENTMAIL_DEFAULT_INBOX_ID).strip(),
    }


def _agentmail_text_html_present(payload: dict) -> bool:
    return bool(str(payload.get("text") or "").strip() or str(payload.get("html") or "").strip())


def _agentmail_provider_payload(digest: dict, idempotency_key: str, config: dict) -> tuple[dict | None, str]:
    action = str(config.get("action") or "").strip().upper()
    inbox_id = str(config.get("inbox_id") or "").strip()
    if action != _AGENTMAIL_ACTION:
        return None, "AgentMail Composio action must be AGENT_MAIL_SEND_EMAIL."
    if not inbox_id:
        return None, "AgentMail Composio send contract is not configured: missing inbox_id"
    payload = {
        "inbox_id": inbox_id,
        "to": [digest["recipient"]],
        "subject": digest["subject"],
        "text": digest["body"],
        "html": "",
        "cc": [],
        "bcc": [],
        "labels": [],
        "reply_to": [],
    }
    if not _agentmail_text_html_present(payload):
        return None, "AgentMail payload requires text or html."
    return {"provider": _AGENTMAIL_PROVIDER, "toolkit": _AGENTMAIL_TOOLKIT, "action": action, "payload": payload}, ""


def _run_agentmail_composio_send(action: str, payload: dict) -> dict:
    workspace = str(BASE_DIR)
    command = (
        f"cd {shlex.quote(workspace)}; python3 connectors/composio_access_adapter.py "
        f"run agent_mail {shlex.quote(action)} --data {shlex.quote(json.dumps(payload, separators=(',', ':')))} "
        "--execute --operator-command"
    )
    result = _run_agentic_os_clean_bash(command, timeout=120)
    try:
        parsed = json.loads(result["output"])
        return parsed if isinstance(parsed, dict) else {"ok": False, "error": "Adapter returned non-object JSON"}
    except (json.JSONDecodeError, TypeError):
        return {"ok": False, "error": _redacted_preview(result.get("output") or "AgentMail connector returned no parseable JSON")}


def _agentmail_provider_reference(response: dict) -> str | None:
    candidates = [response.get("id"), response.get("message_id"), response.get("thread_id"), response.get("reference_id")]
    result = response.get("result")
    if isinstance(result, dict):
        candidates.extend([result.get("id"), result.get("message_id"), result.get("thread_id"), result.get("reference_id")])
        data = result.get("data")
        if isinstance(data, dict):
            candidates.extend([data.get("id"), data.get("message_id"), data.get("thread_id"), data.get("reference_id")])
    for value in candidates:
        if value:
            return str(value)[:200]
    return None


def _write_agentmail_receipt(receipt: dict, path: Path) -> Path:
    durable_replace_text(path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return path


def _build_agentmail_digest(digest_date: datetime.date, recipient: str) -> dict:
    completed = _completed_items_for_date(digest_date)
    needs_me = _queue_human_needed_items(_read_queue_items())
    token_totals = _token_totals_for_date(digest_date)
    backup = _backup_status()
    lines = [
        f"Agentic OS daily digest for {digest_date.isoformat()}",
        "",
        f"Recipient: {recipient}",
        f"Completed items yesterday: {len(completed)}",
        f"Needs Me count now: {len(needs_me)}",
        "",
        "Completed items:",
    ]
    lines.extend([f"- {item.get('id')}: {item.get('title')}" for item in completed] or ["- None recorded."])
    lines.extend([
        "",
        "Token totals:",
        f"- exact: {token_totals['exact']}",
        f"- ~estimate: {token_totals['estimate']}",
        f"- unavailable records: {token_totals['unavailable']}",
        f"- no agent invocation records: {token_totals['no_agent_invocation']}",
    ])
    if not token_totals["rows"]:
        lines.append("- Note: token data is unavailable for this date; no numbers were invented.")
    lines.extend([
        "",
        f"Last backup status: {backup.get('state', 'unavailable')}",
        f"Backup receipt: {backup.get('latest_receipt_path') or 'unavailable'}",
        "",
        "Token usage: no agent invocation",
    ])
    return {
        "digest_date": digest_date.isoformat(),
        "recipient": recipient,
        "subject": f"Agentic OS daily digest - {digest_date.isoformat()}",
        "body": "\n".join(lines),
        "completed_items": completed,
        "needs_me_count": len(needs_me),
        "token_totals": token_totals,
        "backup": backup,
    }


def _agentmail_digest_attempt(
    digest_date: datetime.date | None = None,
    recipient: str | None = None,
    *,
    send: bool = False,
    dry_run: bool = True,
) -> dict:
    digest_date = digest_date or (datetime.datetime.now().astimezone().date() - datetime.timedelta(days=1))
    allowlist = _agentmail_allowlist()
    target = _normalize_agentmail_recipient(recipient or (allowlist[0] if allowlist else ""))
    allowlist_result = _agentmail_recipient_allowlist_result(target)
    if not allowlist_result["allowed"]:
        raise ValueError(allowlist_result["reason"])
    digest = _build_agentmail_digest(digest_date, target)
    idempotency_key = _agentmail_digest_idempotency_key(digest)
    content_hash = _agentmail_digest_content_hash(digest)
    config = _agentmail_config()
    contract, contract_blocker = _agentmail_provider_payload(digest, idempotency_key, config)
    provider = _AGENTMAIL_PROVIDER
    toolkit = _AGENTMAIL_TOOLKIT
    action = _AGENTMAIL_ACTION
    inbox_id = config["inbox_id"]
    if not send:
        return {
            "success": True,
            "digest_generated": True,
            "preview": True,
            "send_attempted": False,
            "sent": False,
            "dry_run": True,
            "recipient": _safe_recipient_label(target),
            "subject": digest["subject"],
            "body": digest["body"],
            "digest": digest,
            "allowlist_result": allowlist_result,
            "provider": provider,
            "toolkit": toolkit,
            "action": action or None,
            "inbox_id": inbox_id,
            "idempotency_key": idempotency_key,
            "content_hash": content_hash,
            "provider_payload": contract["payload"] if contract else None,
        }

    receipt_path: Path | None = None
    with _AGENTMAIL_DIGEST_LOCK:
        prior_success = _agentmail_success_receipt_for_key(idempotency_key)
        duplicate_blocker = ""
        if prior_success:
            duplicate_blocker = "Idempotency: prior sent=true receipt exists for digest date, recipient, and content hash."
        send_attempted = False
        sent = False
        provider_reference = None
        failure = ""
        status = "dry_run" if dry_run else "blocked"
        provider_response = None
        if duplicate_blocker:
            failure = duplicate_blocker
            status = "duplicate_suppressed"
        elif dry_run:
            failure = "Dry-run requested; provider call skipped."
        elif contract_blocker:
            failure = contract_blocker
        else:
            send_attempted = True
            provider_response = _run_agentmail_composio_send(contract["action"], contract["payload"])
            if provider_response.get("ok"):
                sent = True
                status = "sent"
                provider_reference = _agentmail_provider_reference(provider_response)
            else:
                failure = str(provider_response.get("error") or "AgentMail provider send failed")[:500]
                status = "failed_retryable"
        receipt = {
            "timestamp": _utc_now_iso(),
            "type": "agentmail_daily_digest",
            "action": "agentmail_internal_digest",
            "status": status,
            "digest_generated": True,
            "digest_date": digest_date.isoformat(),
            "digest_id": digest_date.isoformat(),
            "recipient": _safe_recipient_label(target),
            "subject": digest["subject"],
            "provider": provider,
            "toolkit": toolkit,
            "provider_action": action or None,
            "inbox_id": inbox_id,
            "idempotency_key": idempotency_key,
            "content_hash": content_hash,
            "allowlist_result": allowlist_result,
            "allowlisted": True,
            "dry_run": bool(dry_run),
            "send_attempted": send_attempted,
            "sent": sent,
            "transmitted": bool(sent),
            "provider_reference": provider_reference,
            "failure": failure,
            "blocker": failure if not sent else "",
            "retryable": bool(not sent and not duplicate_blocker and not dry_run),
            "digest": digest,
            "provider_response_summary": {
                "ok": bool(provider_response.get("ok")) if isinstance(provider_response, dict) else None,
                "mode": provider_response.get("mode") if isinstance(provider_response, dict) else None,
            },
            "token_usage_text": "Token usage: no agent invocation",
        }
        receipt_path = _write_agentmail_receipt(receipt, _agentmail_attempt_receipt_path(digest_date.isoformat(), target, idempotency_key))
    return {
        "success": True,
        "digest_generated": True,
        "preview": False,
        "send_attempted": send_attempted,
        "sent": sent,
        "dry_run": bool(dry_run),
        "already_sent": bool(duplicate_blocker),
        "recipient": _safe_recipient_label(target),
        "receipt_path": _safe_relative(receipt_path),
        "provider": provider,
        "toolkit": toolkit,
        "action": action or None,
        "inbox_id": inbox_id,
        "idempotency_key": idempotency_key,
        "provider_reference": provider_reference,
        "blocker": failure,
        "blocked_reason": failure,
        "allowlist_result": allowlist_result,
        "digest": digest,
    }


def _ledger_timestamp(record: dict) -> object:
    for key in ("timestamp", "ts", "event_timestamp", "completed_at", "updated_at", "created_at"):
        if record.get(key):
            return record[key]
    return None


def _ledger_task_id(record: dict) -> str:
    return str(record.get("item_id") or record.get("task_id") or "unavailable")


def _ledger_component(record: dict) -> str:
    component = record.get("component")
    if component:
        return str(component)
    usage = record.get("token_usage") if isinstance(record.get("token_usage"), dict) else {}
    workbenches = usage.get("workbenches") if isinstance(usage.get("workbenches"), list) else []
    if workbenches:
        return str(workbenches[0].get("tool") or record.get("lane") or "hermes")
    return str(record.get("lane") or record.get("profile") or "hermes")


def _ledger_tokens_basis(record: dict) -> tuple[int | None, str]:
    if "tokens" in record:
        try:
            return int(record.get("tokens")), str(record.get("basis") or "exact")
        except (TypeError, ValueError):
            return None, "unavailable"
    input_tokens, output_tokens = _token_component_total(record)
    if input_tokens is None or output_tokens is None:
        return None, "unavailable"
    usage = record.get("token_usage") if isinstance(record.get("token_usage"), dict) else {}
    unavailable = usage.get("unavailable") if isinstance(usage.get("unavailable"), list) else []
    if unavailable and input_tokens + output_tokens == 0:
        return None, "unavailable"
    return input_tokens + output_tokens, "exact"


def _token_invocation_source(record: dict) -> tuple[str, str]:
    """Return a source only when persisted invocation evidence names it."""
    if _ledger_no_agent_invocation(record):
        return "No agent invocation", "deterministic"
    explicit = str(record.get("invocation_source") or record.get("invocation_tool") or "").strip()
    if explicit:
        return explicit, "explicit ledger field"
    usage = record.get("token_usage") if isinstance(record.get("token_usage"), dict) else {}
    reported = {
        str(row.get("tool") or "").strip()
        for row in usage.get("workbenches") or []
        if isinstance(row, dict) and row.get("source") == "reported" and row.get("tool")
    }
    if len(reported) == 1:
        tool = next(iter(reported))
        return {"codex": "Codex", "claude": "Claude Code", "claude-code": "Claude Code", "hermes": "Hermes"}.get(tool.lower(), tool), "reported workbench invocation"
    orchestrator = usage.get("orchestrator") if isinstance(usage.get("orchestrator"), dict) else {}
    try:
        orchestrator_total = int(orchestrator.get("input") or 0) + int(orchestrator.get("output") or 0)
    except (TypeError, ValueError):
        orchestrator_total = 0
    if orchestrator_total > 0:
        return "Hermes", "persisted orchestrator usage"
    return "Unattributed", "no authoritative invocation source"


def _queue_invocation_attributions(records: list[dict] | None = None) -> dict[str, dict]:
    """Index the latest persisted, authoritative invocation source by item."""
    selected: dict[str, tuple[tuple[int, float, int], dict]] = {}
    source_records = _read_token_ledger_records() if records is None else records
    for position, record in enumerate(source_records):
        item_id = _ledger_task_id(record)
        source, evidence = _token_invocation_source(record)
        model_turns = record.get("model_turns")
        observed_turns = model_turns if isinstance(model_turns, int) and not isinstance(model_turns, bool) and model_turns >= 0 else None
        if not item_id or item_id == "unavailable":
            continue
        if source in {"Unattributed", "No agent invocation"} and observed_turns is None:
            continue
        timestamp = _parse_record_timestamp(_ledger_timestamp(record))
        rank = (
            1 if timestamp else 0,
            timestamp.timestamp() if timestamp else 0.0,
            position,
        )
        attribution = {
            "invocation_source": None if source in {"Unattributed", "No agent invocation"} else source,
            "invocation_source_evidence": evidence,
            "invocation_source_timestamp": (
                timestamp.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
                if timestamp else None
            ),
            "model_turns": observed_turns,
        }
        prior = selected.get(item_id)
        if prior is None or rank > prior[0]:
            selected[item_id] = (rank, attribution)
    return {item_id: value for item_id, (_, value) in selected.items()}


def _token_record_view(record: dict) -> dict:
    row = dict(record)
    parsed = _parse_record_timestamp(_ledger_timestamp(record))
    tokens, basis = _ledger_tokens_basis(record)
    source, source_evidence = _token_invocation_source(record)
    usage = record.get("token_usage") if isinstance(record.get("token_usage"), dict) else {}
    totals = usage.get("totals") if isinstance(usage.get("totals"), dict) else {}
    evidence = record.get("capture_evidence") if isinstance(record.get("capture_evidence"), dict) else {}
    reported_workbench = next(
        (
            work for work in usage.get("workbenches") or []
            if isinstance(work, dict) and work.get("source") == "reported"
        ),
        {},
    )
    no_agent = _ledger_no_agent_invocation(record)
    availability = "no_agent_invocation" if no_agent else basis if tokens is not None else "unavailable"
    row.update({
        "item_id": _ledger_task_id(record),
        "event_timestamp": _ledger_timestamp(record),
        "event_timestamp_utc": parsed.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z") if parsed else None,
        "timestamp_valid": parsed is not None,
        "invocation_source": source,
        "invocation_source_evidence": source_evidence,
        "availability_state": availability,
        "input_tokens": int(totals["input"]) if str(totals.get("input", "")).lstrip("-").isdigit() else None,
        "output_tokens": int(totals["output"]) if str(totals.get("output", "")).lstrip("-").isdigit() else None,
        "total_tokens": tokens,
        "cached_input_tokens": evidence.get("cached_input_tokens", reported_workbench.get("cached_input")),
        "reasoning_output_tokens": evidence.get("reasoning_output_tokens", reported_workbench.get("reasoning")),
        "model_identity": evidence.get("model_identity") or record.get("model_confirmed") or "unavailable",
    })
    return row


def _sort_token_records_newest(records: list[dict]) -> list[dict]:
    def key(record: dict) -> tuple:
        parsed = _parse_record_timestamp(_ledger_timestamp(record))
        identity = str(record.get("session_id") or record.get("invocation_id") or record.get("effect_id") or record.get("event") or "")
        digest = hashlib.sha256(json.dumps(record, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        return (0 if parsed else 1, -(parsed.timestamp() if parsed else 0), identity, digest)
    return sorted(records, key=key)


def _token_source_summary(records: list[dict]) -> list[dict]:
    order = ["Codex", "Claude Code", "Hermes", "Unattributed", "No agent invocation", "Unavailable"]
    def blank(name: str) -> dict:
        return {"source": name, "exact_rows": 0, "estimate_rows": 0, "unavailable_rows": 0, "no_agent_invocation_rows": 0, "input": 0, "output": 0, "total": 0, "cached_input": 0, "reasoning_output": 0}
    groups = {name: blank(name) for name in order}
    for original in records:
        row = _token_record_view(original)
        source = row["invocation_source"]
        group = groups.setdefault(source, blank(source))
        if row["availability_state"] == "no_agent_invocation":
            group["no_agent_invocation_rows"] += 1
        elif row["total_tokens"] is None:
            group["unavailable_rows"] += 1
        elif row["availability_state"] == "estimate":
            group["estimate_rows"] += 1
        elif row["availability_state"] == "exact":
            group["exact_rows"] += 1
            group["input"] += int(row["input_tokens"] or 0)
            group["output"] += int(row["output_tokens"] or 0)
            group["total"] += int(row["total_tokens"])
            group["cached_input"] += int(row["cached_input_tokens"] or 0)
            group["reasoning_output"] += int(row["reasoning_output_tokens"] or 0)
    return [groups[name] for name in order if name in groups] + [groups[name] for name in sorted(set(groups) - set(order))]


def _usage_counters_from_token_usage(token_usage: dict) -> dict:
    aliases = {
        "input_tokens": "total_input",
        "cache_read_tokens": "cached_input",
        "cached_input_tokens": "cached_input",
        "output_tokens": "output",
        "reasoning_tokens": "reasoning",
    }
    counters = {key: UNAVAILABLE_CLI_VALUE for key in USAGE_COUNTER_FIELDS}
    for key in USAGE_COUNTER_FIELDS:
        value = token_usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            counters[key] = value
    for source, target in aliases.items():
        value = token_usage.get(source)
        if counters[target] == UNAVAILABLE_CLI_VALUE and isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            counters[target] = value
    total_input = counters.get("total_input")
    cached_input = counters.get("cached_input")
    output = counters.get("output")
    if isinstance(total_input, int) and isinstance(cached_input, int) and cached_input <= total_input:
        counters["non_cached_input"] = total_input - cached_input
        counters["fresh_input"] = total_input - cached_input
    if isinstance(total_input, int) and isinstance(output, int):
        counters["input_plus_output"] = total_input + output
    return counters


def _simple_token_line(
    task_id: str,
    component: str,
    tokens: int | None,
    basis: str,
    token_usage: dict,
    metadata: dict | None = None,
) -> dict:
    metadata = metadata or {}
    line = {
        "ts": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "task_id": task_id or "unattributed",
        "component": component or "unattributed",
        "basis": basis if basis in {"exact", "unavailable"} else "unavailable",
        "role": str(metadata.get("role") or component or "unattributed"),
        "attempt": metadata.get("attempt"),
        **_usage_counters_from_token_usage(token_usage),
    }
    session_id = str(token_usage.get("session_id") or metadata.get("session_id") or "").strip()
    invocation_id = str(token_usage.get("invocation_id") or metadata.get("invocation_id") or "").strip()
    if session_id:
        line["session_id"] = session_id
    if invocation_id:
        line["invocation_id"] = invocation_id
    if tokens is not None:
        line["tokens"] = max(0, int(tokens))
    if str(component).strip().lower() == "codex":
        provider_input = line.get("total_input")
        output_tokens = line.get("output")
        if isinstance(provider_input, int) and isinstance(output_tokens, int):
            fresh = line.get("fresh_input")
            cached = line.get("cached_input")
            reasoning = line.get("reasoning")
            context_pct = line.get("context_pct_at_close")
            model = str(token_usage.get("model") or "unavailable")
            workbench = {
                "tool": "codex",
                "session_id": session_id or invocation_id or "unavailable",
                "model": model,
                "input": provider_input,
                "fresh_input": fresh,
                "cached_input": cached,
                "output": output_tokens,
                "reasoning": reasoning,
                "context_pct_at_close": context_pct,
                "source": "reported",
            }
            warnings = []
            if isinstance(fresh, int) and isinstance(cached, int):
                ratio = round(cached / max(fresh, 1), 6)
                workbench["cache_ratio"] = ratio
                if ratio > 20:
                    warnings.append(
                        f"cache_ratio > 20: codex session {workbench['session_id']} ratio={ratio}"
                    )
            if isinstance(context_pct, (int, float)) and not isinstance(context_pct, bool) and context_pct > 50:
                warnings.append(
                    f"context_pct_at_close > 50: codex session {workbench['session_id']} context_pct_at_close={context_pct}"
                )
            unavailable = []
            for key in ("fresh_input", "cached_input", "reasoning", "context_pct_at_close"):
                if not isinstance(workbench.get(key), (int, float)) or isinstance(workbench.get(key), bool):
                    unavailable.append(f"codex.{key}")
            if model == "unavailable":
                unavailable.extend(["Codex model identity", "cost for unavailable Codex model"])
            line.update({
                "item_id": task_id or "unattributed",
                "lane": "codex",
                "profile": "default",
                "timestamp": line["ts"],
                "escalated": False,
                "model_requested": "Codex workbench session",
                "model_confirmed": model,
                "budget_class": "standard",
                "token_usage": {
                    "orchestrator": {"input": 0, "output": 0},
                    "subagents": [],
                    "workbenches": [workbench],
                    "totals": {"input": provider_input, "output": output_tokens},
                    "est_cost_usd": 0.0,
                    "unavailable": unavailable,
                },
                "warnings": warnings,
            })
    return line


def _append_simple_token_ledger(task_id: str, component: str, token_usage: dict, metadata: dict | None = None) -> None:
    if token_usage.get("no_agent_invocation"):
        return
    total = token_usage.get("total_tokens")
    try:
        tokens = int(str(total).replace(",", "")) if total is not None else None
    except (TypeError, ValueError):
        tokens = None
    if tokens is None:
        input_tokens = token_usage.get("input_tokens")
        output_tokens = token_usage.get("output_tokens")
        try:
            tokens = int(str(input_tokens).replace(",", "")) + int(str(output_tokens).replace(",", ""))
        except (TypeError, ValueError):
            tokens = None
    try:
        append_root, append_path = _authoritative_append_target(ROOT_TOKEN_LEDGER_FILE)
        line = _simple_token_line(
            task_id, component, tokens, "exact" if tokens is not None else "unavailable", token_usage, metadata
        )
        durable_append_text(append_root, append_path, json.dumps(line, separators=(",", ":")) + "\n")
    except OSError:
        return


def _dashboard_token_summary() -> dict:
    records = _read_token_ledger_records()
    chronological_records = _sort_token_records_newest(records)
    now = datetime.datetime.now().astimezone()
    today = now.date()
    week_start = today - datetime.timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    periods = {
        "today": {"tokens": 0, "cost": 0.0, "known": 0, "unavailable": 0},
        "week": {"tokens": 0, "cost": 0.0, "known": 0, "unavailable": 0},
        "month": {"tokens": 0, "cost": 0.0, "known": 0, "unavailable": 0},
    }
    by_tool: dict[str, dict] = {}
    chart_days: dict[str, int] = {}
    highest = None

    def add_tool(name: str, input_tokens: int, output_tokens: int, cost: float | None = None):
        total = input_tokens + output_tokens
        entry = by_tool.setdefault(name, {"tool": name, "tokens": 0, "cost": 0.0, "flat_rate": name in {"codex", "claude-code", "antigravity"}, "unavailable": 0})
        entry["tokens"] += total
        if cost is not None and not entry["flat_rate"]:
            entry["cost"] += float(cost)

    for record in records:
        timestamp = _parse_record_timestamp(_ledger_timestamp(record))
        local_date = timestamp.astimezone(now.tzinfo).date() if timestamp else None
        lightweight_record = "tokens" in record
        input_tokens, output_tokens = _token_component_total(record)
        simple_tokens, simple_basis = _ledger_tokens_basis(record)
        unavailable = record.get("token_usage", {}).get("unavailable") if isinstance(record.get("token_usage"), dict) else []
        is_unavailable = simple_tokens is None and (bool(unavailable) or input_tokens is None or output_tokens is None)
        total_tokens = simple_tokens if simple_tokens is not None else (input_tokens or 0) + (output_tokens or 0)
        cost = record.get("token_usage", {}).get("est_cost_usd") if isinstance(record.get("token_usage"), dict) else record.get("est_cost_usd")
        try:
            cost_float = float(cost)
        except (TypeError, ValueError):
            cost_float = 0.0

        for name, start in (("today", today), ("week", week_start), ("month", month_start)):
            in_period = local_date == today if name == "today" else local_date is not None and start <= local_date <= today
            if not in_period:
                continue
            periods[name]["unavailable"] += int(is_unavailable)
            if not is_unavailable:
                periods[name]["tokens"] += total_tokens
                periods[name]["cost"] += cost_float
                periods[name]["known"] += 1

        if local_date is not None:
            chart_days.setdefault(local_date.isoformat(), 0)
            chart_days[local_date.isoformat()] += total_tokens

        if local_date == today:
            usage = record.get("token_usage") if isinstance(record.get("token_usage"), dict) else {}
            orch = usage.get("orchestrator") if isinstance(usage.get("orchestrator"), dict) else {}
            simple_component = _ledger_component(record)
            if lightweight_record and simple_tokens is not None:
                by_tool.setdefault(simple_component, {"tool": simple_component, "tokens": 0, "cost": 0.0, "flat_rate": simple_component in {"codex", "claude-code", "antigravity"}, "unavailable": 0, "estimated": 0})
                by_tool[simple_component].setdefault("estimated", 0)
                by_tool[simple_component]["tokens"] += simple_tokens
                by_tool[simple_component]["estimated"] += int(simple_basis == "estimate")
            elif is_unavailable:
                by_tool.setdefault("hermes", {"tool": "hermes", "tokens": 0, "cost": 0.0, "flat_rate": False, "unavailable": 0})["unavailable"] += 1
            else:
                add_tool("hermes", int(orch.get("input") or 0), int(orch.get("output") or 0), cost_float)
            for subagent in usage.get("subagents") or []:
                if isinstance(subagent, dict):
                    role = str(subagent.get("role") or "subagent").split("/")[0]
                    if is_unavailable:
                        by_tool.setdefault(role, {"tool": role, "tokens": 0, "cost": 0.0, "flat_rate": role in {"codex", "claude-code", "antigravity"}, "unavailable": 0})["unavailable"] += 1
                    else:
                        add_tool(role, int(subagent.get("input") or 0), int(subagent.get("output") or 0), None)
            for workbench in usage.get("workbenches") or []:
                if isinstance(workbench, dict):
                    name = str(workbench.get("tool") or "workbench")
                    if is_unavailable or str(workbench.get("source") or "") == "unavailable":
                        by_tool.setdefault(name, {"tool": name, "tokens": 0, "cost": 0.0, "flat_rate": True, "unavailable": 0})["unavailable"] += 1
                    else:
                        add_tool(name, int(workbench.get("input") or 0), int(workbench.get("output") or 0), None)

        if total_tokens and (highest is None or total_tokens > highest["tokens"]):
            highest = {
                "item_id": _ledger_task_id(record),
                "lane": record.get("lane"),
                "profile": record.get("profile"),
                "tokens": total_tokens,
                "timestamp": _ledger_timestamp(record),
            }

    for value in periods.values():
        value["cost"] = round(value["cost"], 4)

    return {
        "available": TOKEN_LEDGER_FILE.exists(),
        "path": _safe_relative(TOKEN_LEDGER_FILE),
        "periods": periods,
        "by_tool": sorted(by_tool.values(), key=lambda row: row["tokens"], reverse=True),
        "highest_task": highest,
        "unavailable_count": sum(row.get("unavailable", 0) for row in by_tool.values()) + periods["today"]["unavailable"],
        "records": [_token_record_view(record) for record in chronological_records[:100]],
        "source_summary": _token_source_summary(records),
        "strip": _dashboard_token_strip(records),
        "chart": [{"date": day, "tokens": tokens} for day, tokens in sorted(chart_days.items())[-14:]],
    }


def _token_label(record: dict | None) -> str:
    if not record:
        return "Token usage: unavailable from current CLI output"
    if _ledger_no_agent_invocation(record):
        return "Token usage: no agent invocation"
    tokens, basis = _ledger_tokens_basis(record)
    if tokens is None:
        return "Token usage: unavailable from current CLI output"
    prefix = "" if basis == "exact" else "~"
    suffix = " exact" if basis == "exact" else " est"
    return f"Token usage: {prefix}{tokens:,}{suffix}"


def _dashboard_token_strip(records: list[dict]) -> dict:
    dated = []
    for index, record in enumerate(records):
        dated.append((_parse_record_timestamp(_ledger_timestamp(record)), index, record))
    dated.sort(key=lambda row: (row[0] or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), row[1]))
    now = datetime.datetime.now().astimezone()
    today_records = [record for parsed, _, record in dated if parsed and parsed.astimezone(now.tzinfo).date() == now.date()]
    current = dated[-1][2] if dated else None
    previous = dated[-2][2] if len(dated) > 1 else None
    today_total = 0
    today_estimated = False
    today_unavailable = False
    for record in today_records:
        tokens, basis = _ledger_tokens_basis(record)
        if tokens is None:
            today_unavailable = True
            continue
        today_total += tokens
        today_estimated = today_estimated or basis == "estimate"
    if today_total:
        today_label = f"Token usage: {'~' if today_estimated else ''}{today_total:,}{' est' if today_estimated else ' exact'} today"
    else:
        today_label = "Token usage: unavailable from current CLI output" if today_unavailable else "Token usage: no task recorded today"
    return {
        "current_task": {"task_id": _ledger_task_id(current) if current else None, "label": _token_label(current)},
        "last_task": {"task_id": _ledger_task_id(previous) if previous else None, "label": _token_label(previous)},
        "today": {"label": today_label},
        "states": sorted({_token_label(record) for record in records if _ledger_no_agent_invocation(record)}),
    }


def _recent_file_items(limit: int = 200) -> list[dict]:
    """Return the most-recently-modified allowlisted files without reading every candidate's content.

    Candidates are ranked by a cheap stat() first; file content is only read for the
    top `limit` results, so this stays fast even as queue/receipts, results, and logs grow.
    """
    roots = [QUEUE_DIR / "receipts", RESULTS_DIR, LOGS_DIR]
    candidates: list[tuple[float, Path, str]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".json", ".jsonl"}:
                continue
            rel = _safe_relative(path)
            if _QUEUE_ARTIFACT_SECRET_RE.search(rel):
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            candidates.append((mtime, path, rel))
    candidates.sort(key=lambda row: row[0], reverse=True)

    items = []
    for mtime, path, rel in candidates[:limit]:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        items.append({
            "id": rel,
            "path": rel,
            "title": _markdown_title(content, path.name),
            "source": "receipt" if "queue/receipts" in rel or "/receipts/" in rel else ("result" if rel.startswith("results/") else "log"),
            "modified": datetime.datetime.fromtimestamp(mtime).isoformat(),
            "preview": _redacted_preview(content, 2400),
        })
    return items


def _dashboard_activity_feed(recent_sources: list[dict] | None = None) -> list[dict]:
    items = _read_queue_items()
    by_id = {str(item.get("id") or ""): item for item in items}
    records = _read_token_ledger_records()
    token_by_item: dict[str, list[dict]] = {}
    for record in records:
        token_by_item.setdefault(_ledger_task_id(record), []).append(record)
    sources = list(recent_sources) if recent_sources is not None else _recent_file_items()
    for receipt_root in [BASE_DIR / "search" / "receipts", BASE_DIR / "workflows"]:
        if not receipt_root.exists():
            continue
        pattern = "*" if receipt_root.name == "receipts" else "*/receipts/*"
        for path in receipt_root.glob(pattern):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".json", ".jsonl"}:
                continue
            try:
                relative = _safe_relative(path)
                content = path.read_text(encoding="utf-8", errors="replace")
                sources.append({
                    "id": relative,
                    "path": relative,
                    "title": _markdown_title(content, path.name),
                    "source": "workflow receipt" if relative.startswith("workflows/") else "search receipt",
                    "modified": datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
                    "preview": _redacted_preview(content, 2400),
                })
            except OSError:
                continue
    feed = []
    seen = set()
    for source in sorted(sources, key=lambda row: str(row.get("modified") or ""), reverse=True):
        path = str(source.get("path") or "")
        if not path or path in seen:
            continue
        seen.add(path)
        match = re.search(r"AOS-\d{4}-\d{4}", path + " " + str(source.get("preview") or ""))
        item_id = match.group(0) if match else ""
        item = by_id.get(item_id, {})
        token_records = token_by_item.get(item_id, [])
        token_records.sort(key=lambda row: str(_ledger_timestamp(row) or ""), reverse=True)
        token_line = _token_label(token_records[0] if token_records else None)
        status = str(item.get("status") or "recorded")
        next_action = {
            "human_review": "Liam review required",
            "needs_input": "Operator input required",
            "blocked": "Resolve recorded blocker",
            "agent_todo": "Claim through the existing queue",
            "agent_working": "Workbench execution in progress",
            "done": "Read-only record; no action required",
        }.get(status, "Read-only record; inspect source evidence")
        feed.append({
            **source,
            "time": source.get("modified"),
            "item_id": item_id or "unattributed",
            "lane": _queue_item_lane(item) if item else "unassigned",
            "component": str(item.get("owner") or source.get("source") or "unassigned"),
            "workbench": str(item.get("workbench") or ""),
            "status": status,
            "token_line": token_line if "unavailable" not in token_line.lower() else "Token usage: unavailable",
            "next_action": next_action,
            "receipt": path if path.startswith(("queue/receipts/", "workflows/", "search/receipts/")) else "",
            "artifact": path,
        })
    return feed


def _dashboard_backend_log(event: dict) -> None:
    payload = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        **event,
    }
    path = LOGS_DIR / "dashboard_backend.log"
    append_root, path = _authoritative_append_target(path)
    durable_append_text(append_root, path, json.dumps(payload, ensure_ascii=False) + "\n")


def _telegram_configured_operator_chat() -> str | None:
    allowed_file = BASE_DIR / "connectors" / "telegram_bridge" / "allowed_chats.json"
    try:
        data = json.loads(allowed_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    raw_ids = data.get("operator_chat_ids")
    if isinstance(raw_ids, list) and raw_ids:
        candidate = str(raw_ids[0]).strip()
        return candidate if re.fullmatch(r"-?\d+", candidate) else None
    candidate = str(data.get("operator_chat_id") or "").strip()
    return candidate if re.fullmatch(r"-?\d+", candidate) else None


def _telegram_reply_to(item: dict) -> str | None:
    dispatch = item.get("dispatch") if isinstance(item.get("dispatch"), dict) else {}
    reply_to = (
        item.get("reply_to") or item.get("chat_id") or item.get("telegram_chat_id")
        or dispatch.get("reply_to")
    )
    if reply_to:
        return str(reply_to)
    for ref in item.get("source_refs") or []:
        match = re.search(r"(?:reply_to|chat_id|telegram_chat_id)[:=](-?\d+)", str(ref))
        if match:
            return match.group(1)
    return _telegram_configured_operator_chat()


def _load_telegram_bridge_module():
    bridge_path = BASE_DIR / "connectors" / "telegram_bridge" / "telegram_bridge.py"
    spec = importlib.util.spec_from_file_location("aos_telegram_bridge", bridge_path)
    if spec is not None and spec.loader is not None:
        try:
            bridge = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bridge)
            return bridge
        except RuntimeError as exc:
            if ".env file not found" not in str(exc):
                raise

    source = bridge_path.read_text(encoding="utf-8")
    source = re.sub(
        r"^WORKSPACE = .*$",
        f"WORKSPACE = Path({str(BASE_DIR)!r})",
        source,
        count=1,
        flags=re.MULTILINE,
    )
    bridge = importlib.util.module_from_spec(
        importlib.util.spec_from_loader("aos_telegram_bridge_wsl", loader=None)
    )
    exec(compile(source, str(bridge_path), "exec"), bridge.__dict__)
    return bridge


def _telegram_reply_on_close(item: dict, status: str, note: str, receipt_path: str) -> dict | None:
    if str(item.get("source") or "").lower() != "telegram":
        return None
    reply_to = _telegram_reply_to(item)
    if not reply_to:
        _dashboard_backend_log({
            "event": "telegram_close_hook",
            "item_id": item.get("id"),
            "status": status,
            "result": "skipped",
            "reason": "chat_id_unavailable",
        })
        return {
            "mode": "live_bridge_send",
            "bridge_function": "connectors.telegram_bridge.telegram_bridge.send",
            "sent": False,
            "reason": "chat_id_unavailable",
        }

    message = aos_orchestration.format_operator_work_item_notification(
        item,
        status,
        summary=(note or f"{aos_orchestration.operator_task_title(item)} was closed from review."),
        next_action="None" if status == "done" else "Review the attached closeout.",
        receipt_path=receipt_path,
        receipt_attached=bool(receipt_path),
    )
    event = {
        "mode": "live_bridge_send",
        "bridge_function": "connectors.telegram_bridge.telegram_bridge.send",
        "item_id": item.get("id"),
        "status": status,
        "receipt_path": receipt_path,
        "message": message,
    }
    _dashboard_backend_log({"event": "telegram_close_hook", **event, "result": "send_invoked"})
    try:
        bridge = _load_telegram_bridge_module()
        send_result = {"ok": True, "error": None}
        bridge_api = bridge.api

        def tracking_api(method, data=None, timeout=60):
            try:
                return bridge_api(method, data, timeout)
            except Exception as exc:
                send_result["ok"] = False
                send_result["error"] = type(exc).__name__
                raise

        bridge.api = tracking_api
        docs = [str(BASE_DIR / receipt_path)] if receipt_path and (BASE_DIR / receipt_path).is_file() else []
        bridge.send(reply_to, message, preserve_format=True, document_paths=docs)
        if not send_result["ok"]:
            bridge.log(
                f"dashboard_close_hook_send_failed item={item.get('id')} status={status} "
                f"error={send_result['error']}"
            )
            _dashboard_backend_log({
                "event": "telegram_close_hook",
                **event,
                "result": "send_failed",
                "error": send_result["error"],
            })
            return {**event, "sent": False, "error": send_result["error"]}
        bridge.log(f"dashboard_close_hook_send item={item.get('id')} status={status}")
    except Exception as exc:
        _dashboard_backend_log({
            "event": "telegram_close_hook",
            **event,
            "result": "send_failed",
            "error": type(exc).__name__,
        })
        raise RuntimeError(f"Telegram bridge send failed: {type(exc).__name__}") from exc
    return {**event, "sent": True}


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
    append_root, append_path = _authoritative_append_target(TOKEN_USAGE_FILE)
    durable_append_text(append_root, append_path, json.dumps(record, ensure_ascii=False) + "\n")
    _append_simple_token_ledger(
        str((route_metadata or {}).get("item_id") or task[:80] or route),
        agent or route,
        token_usage,
        route_metadata,
    )
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
    if isinstance(result.get("token_usage"), dict) and result.get("token_usage_text"):
        token_usage = result["token_usage"]
        token_usage_text = str(result["token_usage_text"])
    else:
        token_usage, token_usage_text = _extract_token_usage(
            raw, str(result.get("stdout") or ""), str(result.get("stderr") or "")
        )
    command_stage = str(result.get("command_stage") or ("execution" if timed_out else "completion"))
    failure_class = str(result.get("failure_class") or ("agent_reported_task_failure" if agent_reported_failure else ""))
    log_path = str(result.get("log_path") or "logs/dashboard_backend.log")
    elapsed_seconds = result.get("elapsed_seconds")
    failure_detail = _field_from_output(raw, "Blockers") or _bounded_stream_tail(result.get("stderr") or raw, 500)
    values = {
        "Files touched": _field_from_output(raw, "Files touched") or "None reported",
        "Validation": _field_from_output(raw, "Validation") or (
            f"{route} route {command_stage} timed out after {timeout_seconds}s"
            if timed_out else ("Agent command completed" if passed else f"Agent command failed ({failure_class or 'unclassified_failure'})")
        ),
        "Connector access": _field_from_output(raw, "Connector access") or "No connector action reported",
        "Token usage": _token_usage_detail(token_usage_text),
        "Blockers": _field_from_output(raw, "Blockers") or (
            f"{failure_class} at {command_stage} after {elapsed_seconds}s; diagnostics: {log_path}"
            if not passed else "None"
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
    if result.get("invocation"):
        metadata = {**metadata, "invocation": result["invocation"]}
    if not result.get("token_usage_logged"):
        for index, handoff in enumerate(result.get("handoff_sessions") or [], start=1):
            prior_usage = handoff.get("token_usage") if isinstance(handoff, dict) else None
            if not isinstance(prior_usage, dict):
                continue
            _log_token_usage(
                route,
                agent,
                task,
                prior_usage,
                str(handoff.get("token_usage_text") or "Token usage: unavailable from current CLI output"),
                {
                    **metadata,
                    "role": "context_handoff",
                    "handoff_index": index,
                    "session_id": handoff.get("session_id"),
                    "handoff_artifact": handoff.get("handoff_artifact"),
                },
            )
        _log_token_usage(route, agent, task, token_usage, token_usage_text, metadata)
    return {
        "success": passed,
        "output": output,
        "returncode": result.get("returncode", -1),
        "token_usage": token_usage,
        "token_usage_text": token_usage_text,
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
        "startup_timeout_seconds": result.get("startup_timeout_seconds"),
        "execution_timeout_seconds": result.get("execution_timeout_seconds"),
        "parent_timeout_seconds": result.get("parent_timeout_seconds"),
        "graceful_termination_seconds": result.get("graceful_termination_seconds"),
        "elapsed_seconds": elapsed_seconds,
        "failure_class": failure_class or None,
        "command_stage": command_stage,
        "diagnostic_log": log_path,
        "captured_stdout_tail": _bounded_stream_tail(result.get("stdout"), 700),
        "captured_stderr_tail": _bounded_stream_tail(result.get("stderr"), 700),
        "stream_artifacts": list(result.get("stream_artifacts") or []),
        "handoff_sessions": list(result.get("handoff_sessions") or []),
        "handoff_artifacts": list(result.get("handoff_artifacts") or []),
        "retained_output_truncated": bool(result.get("retained_output_truncated")),
        "session_id": token_usage.get("session_id"),
        "review_output": _bounded_hermes_answer(raw, 4000),
        "failure_detail": failure_detail,
        "invocation": result.get("invocation") or {},
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
    """Report bridge and downstream operator-route health without invoking an agent."""
    return _operator_system_status_closeout()


@app.get("/api/hermes-ui/status")
def hermes_ui_status():
    """Report the real local Hermes dashboard reachability state."""
    return _hermes_ui_status()


@app.post("/api/hermes-ui/launch")
def hermes_ui_launch():
    """Start the supported Hermes dashboard on 127.0.0.1:8081 when needed."""
    before = _hermes_ui_status()
    if before.get("http_reachable"):
        return {**before, "success": True, "already_running": True, "launched": False, "message": "Hermes dashboard already reachable."}
    if not before.get("supported"):
        return {
            **before,
            "success": False,
            "already_running": False,
            "launched": False,
            "message": before.get("reason") or "Hermes dashboard command is unavailable.",
        }
    result = _run_agentic_os_clean_bash(_hermes_dashboard_launcher_command("start"), timeout=20)
    fields = _parse_key_value_output(result.get("stdout") or result.get("output") or "")
    ready = _poll_http_endpoint(HERMES_DASHBOARD_URL + "/", timeout_seconds=10, interval_seconds=0.5)
    after = _hermes_ui_status()
    http_reachable = bool(after.get("http_reachable") or ready)
    launch_succeeded = http_reachable
    return {
        **after,
        "success": launch_succeeded,
        "state": after.get("state") if http_reachable == after.get("http_reachable") else "running_embedded",
        "reachable": http_reachable,
        "http_reachable": http_reachable,
        "process_running": bool(after.get("process_running") or http_reachable),
        "open_url": HERMES_DASHBOARD_URL if http_reachable else "",
        "already_running": False,
        "launched": bool(result.get("success")),
        "launcher_state": fields.get("state", ""),
        "launcher_returncode": result.get("returncode"),
        "launcher_stdout": result.get("stdout", ""),
        "launcher_stderr": result.get("stderr", ""),
        "message": (
            "Hermes dashboard reachable."
            if launch_succeeded
            else "Hermes dashboard launch command returned, but http://127.0.0.1:8081 did not become reachable."
        ),
    }


class TaskRun(BaseModel):
    task: str
    source: str = "telegram"
    delivery_id: str = ""
    reply_to: str = ""


class HermesMessage(BaseModel):
    text: str
    source_refs: list[str] = []


class HermesChainStep(BaseModel):
    title: str
    owner: str = "hermes"
    workbench: str | None = "lane"
    priority: str | int = "normal"
    tags: list[str] = []
    context: str = ""
    source_refs: list[str] = []
    allowed_actions: list[str] = ["local_read", "local_edit", "local_test"]
    stop_conditions: list[str] = ["external_send", "secrets_exposure", "destructive_action_outside_scope"]
    definition_of_done: str = ""
    depends_on: list[str] = []
    on_complete: str | None = None


class HermesChainConfirm(BaseModel):
    title: str
    context: str = ""
    source_refs: list[str] = []
    steps: list[HermesChainStep]


class TelegramSendValidation(BaseModel):
    item_id: str
    recipient: str
    message: str = "Agentic OS validation send"


def _token_usage_from_hermes_usage_report(usage: dict | None) -> tuple[dict, str]:
    if not isinstance(usage, dict):
        return {"available": False}, "Token usage: unavailable from current CLI output"

    fields = {}
    for key in (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "reasoning_tokens",
        "total_tokens",
        "api_calls",
    ):
        value = usage.get(key)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, int):
            fields[key] = value
            continue
        if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
            fields[key] = int(value.strip())

    model = usage.get("model")
    provider = usage.get("provider")
    failed = bool(usage.get("failed"))
    failure = str(usage.get("failure") or "").strip()
    token_usage = {
        "available": bool(fields),
        **fields,
        "model": model,
        "provider": provider,
        "completed": usage.get("completed"),
        "failed": failed,
    }
    session_id = str(usage.get("session_id") or usage.get("thread_id") or "").strip()
    if session_id:
        token_usage["session_id"] = session_id
    input_tokens = fields.get("input_tokens")
    cached_input = fields.get("cache_read_tokens")
    output_tokens = fields.get("output_tokens")
    if isinstance(input_tokens, int):
        token_usage["total_input"] = input_tokens
    if isinstance(cached_input, int):
        token_usage["cached_input"] = cached_input
    if isinstance(input_tokens, int) and isinstance(cached_input, int) and cached_input <= input_tokens:
        token_usage["non_cached_input"] = input_tokens - cached_input
        token_usage["fresh_input"] = input_tokens - cached_input
    if isinstance(output_tokens, int):
        token_usage["output"] = output_tokens
    if isinstance(input_tokens, int) and isinstance(output_tokens, int):
        token_usage["input_plus_output"] = input_tokens + output_tokens
    if isinstance(fields.get("reasoning_tokens"), int):
        token_usage["reasoning"] = fields["reasoning_tokens"]
    if failure:
        token_usage["failure"] = failure

    if not fields:
        return token_usage, "Token usage: unavailable from current CLI output"

    labels = {
        "input_tokens": "input",
        "output_tokens": "output",
        "cache_read_tokens": "cache read",
        "cache_write_tokens": "cache write",
        "reasoning_tokens": "reasoning",
        "total_tokens": "total",
        "api_calls": "api calls",
    }
    summary = ", ".join(f"{labels[key]} {fields[key]}" for key in labels if key in fields)
    return token_usage, f"Token usage: {summary}"


def _read_hermes_usage_report(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _run_hermes_message(
    text: str,
    *,
    role: str = "conversation",
    attempt: int | None = None,
    item_id: str = "",
    timeout: int | None = None,
) -> dict:
    invocation_id = f"hermes-{uuid.uuid4().hex}"
    prompt_path, prompt_wsl_path = _write_agent_prompt_file(text, prefix="hermes_message_")
    usage_handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        prefix="hermes_usage_",
        suffix=".json",
        dir=prompt_path.parent,
        delete=False,
    )
    usage_path = Path(usage_handle.name)
    usage_handle.close()
    usage_wsl_path = _quoted_linux_path(usage_path)
    command = (
        f"{_quoted_linux_path(HERMES_COORDINATOR)} "
        f"--usage-file {usage_wsl_path} "
        f"--prompt-file {_quoted_linux_path(prompt_wsl_path)}"
    )
    try:
        result = _run_agentic_os_clean_bash(command, timeout=timeout or AGENT_TIMEOUT_SECONDS)
        usage_report = _read_hermes_usage_report(usage_path)
    finally:
        for path in (prompt_path, usage_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    reply = _clean_hermes_stream(result.get("stdout") or result.get("output") or "")
    token_usage, token_usage_text = _token_usage_from_hermes_usage_report(usage_report)
    token_usage.setdefault("invocation_id", invocation_id)
    metadata = {
        "requested_target": "hermes",
        "selected_route": "hermes_message",
        "delegation_reason": "direct Hermes one-shot API route",
        "codex_forbidden": "no",
        "profile_requested": "aos-orchestrator",
        "profile_used": "aos-orchestrator",
        "role": role,
        "attempt": attempt,
        "item_id": item_id,
        "invocation_id": invocation_id,
    }
    _log_token_usage("hermes", "hermes", text, token_usage, token_usage_text, metadata)
    return {
        "success": bool(result.get("success")) and not token_usage.get("failed", False),
        "reply": reply,
        "output": reply,
        "stdout": reply,
        "token_usage": token_usage,
        "token_usage_text": token_usage_text,
        "returncode": result.get("returncode", -1),
        "stderr": _clean_hermes_stream(result.get("stderr")),
        "raw_output_tail": "\n".join((str(result.get("stdout") or result.get("output") or "")).splitlines()[-20:]),
        "invocation_id": invocation_id,
        "session_id": token_usage.get("session_id"),
        "profile_requested": "aos-orchestrator",
        "profile_used": "aos-orchestrator",
        "role": role,
        "attempt": attempt,
        "token_usage_logged": True,
    }


def _looks_multi_step(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(marker in lowered for marker in ("multi-step", "chain", " then ", "after that", "step 1", "first ", "next "))


def _hermes_decomposition_prompt(text: str) -> str:
    return "\n".join((
        "Propose an editable Agentic OS queue chain for this operator command.",
        "Return a compact explanation, then a fenced JSON object with this shape:",
        '{"title":"...","steps":[{"title":"...","owner":"revenue|marketing|delivery|operations|codex|claude|hermes","workbench":"lane|codex|claude","definition_of_done":"...","on_complete":null}]}',
        "Use human_review or needs_input in on_complete only for real gates. Do not file queue items.",
        "",
        "Operator command:",
        text,
    ))


def _extract_json_objects(text: str) -> list[dict]:
    candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if "{" in text and "}" in text:
        candidates.append(text[text.find("{"):text.rfind("}") + 1])
    objects = []
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            objects.append(value)
    return objects


def _normalize_chain_proposal(text: str, original_text: str, source_refs: list[str] | None = None) -> dict | None:
    for obj in _extract_json_objects(text):
        raw_steps = obj.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            continue
        steps = []
        for index, step in enumerate(raw_steps, start=1):
            if not isinstance(step, dict):
                continue
            owner = str(step.get("owner") or "hermes").strip().lower()
            if owner not in {"hermes", "codex", "claude", "revenue", "marketing", "delivery", "operations"}:
                owner = "hermes"
            workbench = str(step.get("workbench") or ("codex" if owner == "codex" else "claude" if owner == "claude" else "lane")).strip()
            on_complete = str(step.get("on_complete") or "").strip()
            if on_complete not in {"human_review", "needs_input"}:
                on_complete = None
            steps.append({
                "title": str(step.get("title") or step.get("name") or f"Step {index}").strip(),
                "owner": owner,
                "workbench": workbench,
                "priority": step.get("priority") or "normal",
                "tags": step.get("tags") if isinstance(step.get("tags"), list) else ["hermes_chain"],
                "context": str(step.get("context") or original_text).strip(),
                "source_refs": step.get("source_refs") if isinstance(step.get("source_refs"), list) else [],
                "allowed_actions": step.get("allowed_actions") if isinstance(step.get("allowed_actions"), list) else ["local_read", "local_edit", "local_test"],
                "stop_conditions": step.get("stop_conditions") if isinstance(step.get("stop_conditions"), list) else ["external_send", "secrets_exposure", "destructive_action_outside_scope"],
                "definition_of_done": str(step.get("definition_of_done") or step.get("dod") or "").strip(),
                "depends_on": step.get("depends_on") if isinstance(step.get("depends_on"), list) else [],
                "on_complete": on_complete,
            })
        if steps:
            return {
                "title": str(obj.get("title") or f"Hermes chain: {original_text[:80]}").strip(),
                "context": original_text,
                "source_refs": list(source_refs or []),
                "steps": steps,
                "editable": True,
                "filed": False,
            }
    return None


def _append_hermes_decomposition_token_ledger(result: dict, item_id: str = "AOS-2026-0000") -> None:
    usage = result.get("token_usage") if isinstance(result, dict) else {}
    available = bool(isinstance(usage, dict) and usage.get("available"))
    input_tokens = int(usage.get("input_tokens") or 0) if available else 0
    output_tokens = int(usage.get("output_tokens") or 0) if available else 0
    record = {
        "item_id": item_id,
        "lane": "hermes",
        "profile": "default",
        "timestamp": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "escalated": False,
        "model_requested": "configured externally",
        "model_confirmed": str(usage.get("model") or ("reported" if available else "unavailable")),
        "budget_class": "light",
        "token_usage": {
            "orchestrator": {"input": input_tokens, "output": output_tokens},
            "subagents": [],
            "workbenches": [],
            "totals": {"input": input_tokens, "output": output_tokens},
            "est_cost_usd": 0.0,
            "unavailable": [] if available else ["Hermes decomposition usage unavailable"],
        },
        **_usage_counters_from_token_usage(usage if isinstance(usage, dict) else {}),
        "basis": "exact" if available else "unavailable",
        "event": "hermes_decomposition",
    }
    append_root, append_path = _authoritative_append_target(TOKEN_LEDGER_FILE)
    durable_append_text(append_root, append_path, json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _create_hermes_question_item(question: str, source_refs: list[str]) -> dict:
    item = _queue_create_dashboard_item(QueueItemCreate(
        title="Hermes needs clarification",
        owner="hermes",
        priority="high",
        tags="hermes,needs_input",
        source="dashboard/hermes_question",
        context=question.strip()[:2000],
        source_refs=",".join(source_refs or []),
        definition_of_done="Operator answers the clarifying question so the originating command can continue.",
        allowed_actions="local_read,local_edit",
        stop_conditions="external_send,secrets_exposure,destructive_action_outside_scope",
    ))
    return _load_queue_tool().update_status(BASE_DIR, item["id"], "needs_input")


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
        rf"\b(?:get|tell|use|ask|have)\s+{target}\b"
        rf"|\b(?:give|send|delegate|route|assign|hand)\b[^.!?\n]{{0,80}}\bto\s+{target}\b"
        rf"|(?:^|\n)\s*{target}(?:\s+code)?\s*:"
        rf"|(?:^|[/\s])work\s+{target}\b",
        re.IGNORECASE,
    )
    for target in ("codex", "claude", "hermes")
}
_HERMES_ORCHESTRATION_RE = re.compile(
    r"\b(?:coordinate|coordinator|oversee|orchestrate)\b"
    r"|\breview\s+(?:it|the\s+(?:work|result|receipt|diff|tests?))\b"
    r"|\bsend\s+(?:it|this|the\s+work)\s+back\b"
    r"|\b(?:request|make|apply)\s+(?:a\s+)?corrections?\b",
    re.IGNORECASE,
)
_QUEUE_CREATE_PREFIX = "Add this to the queue:"
_QUEUE_CREATE_RE = re.compile(rf"^{re.escape(_QUEUE_CREATE_PREFIX)}", re.IGNORECASE)
_QUEUE_LIST_PREFIX = "List queue:"
_QUEUE_LIST_RE = re.compile(rf"^{re.escape(_QUEUE_LIST_PREFIX)}", re.IGNORECASE)
_QUEUE_STATUS_INTENTS = {"queue status", "show queue status", "show queue summary"}
_SYSTEM_STATUS_INTENTS = {"/status", "status", "show status", "system status", "operator status", "show system status"}
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
_HISTORY_QUEUE_STATUSES = ("done", "cancelled")
_QUEUE_ITEM_SCOPES = {"active", "history", "all"}
_QUEUE_OWNER_RE = {
    owner: re.compile(rf"\b{re.escape(owner)}\b", re.IGNORECASE)
    for owner in ("codex", "claude", "revenue", "marketing", "delivery", "operations")
}


def _load_queue_tool():
    spec = importlib.util.spec_from_file_location("aos_queue", QUEUE_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError("Queue tool could not be loaded")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        if exc.name != "jsonschema":
            raise
        return _QueueToolFallback()
    return module


class _QueueToolFallback:
    """Small dashboard fallback when aos-queue.py's optional jsonschema import is absent."""

    @staticmethod
    def _refuse_done_transition(status: str | None):
        if status == "done":
            raise ValueError(
                "queue done-transition requires tools/aos-queue.py finalize_done(); "
                "jsonschema is unavailable, so the dashboard fallback refuses status=done"
            )

    @staticmethod
    def now_iso():
        return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def load_items(root: Path):
        return _read_queue_items()

    @staticmethod
    def save_items(root: Path, items: list[dict]):
        with queue_write_lock(root):
            durable_replace_text(
                Path(root) / "queue" / "work_items.jsonl",
                "".join(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n" for item in items),
            )

    @staticmethod
    def find_item(items: list[dict], item_id: str):
        for item in items:
            if item.get("id") == item_id:
                return item
        raise ValueError(f"Work item not found: {item_id}")

    @staticmethod
    def _next_id(items: list[dict], created_at: str):
        prefix = f"AOS-{created_at[:4]}-"
        max_number = 0
        for item in items:
            item_id = str(item.get("id", ""))
            if item_id.startswith(prefix):
                try:
                    max_number = max(max_number, int(item_id.rsplit("-", 1)[1]))
                except ValueError:
                    continue
        return f"{prefix}{max_number + 1:04d}"

    def create_item(self, root: Path, args):
        with queue_write_lock(root):
            items = self.load_items(root)
            idempotency_key = str(getattr(args, "idempotency_key", "") or "").strip()
            if idempotency_key:
                for existing in items:
                    dispatch = existing.get("dispatch")
                    if isinstance(dispatch, dict) and dispatch.get("idempotency_key") == idempotency_key:
                        setattr(args, "idempotency_duplicate", True)
                        return existing
            now = self.now_iso()
            item = {
            "id": self._next_id(items, now),
            "title": args.title,
            "requested_by": args.requested_by,
            "owner_type": args.owner_type,
            "owner": args.owner,
            "status": args.status,
            "priority": args.priority,
            "source": args.source,
            "tags": _queue_split_text(args.tags),
            "context": args.context,
            "sources": _queue_split_text(args.sources),
            "source_refs": [],
            "allowed_actions": _queue_split_text(args.allowed_actions),
            "stop_conditions": _queue_split_text(args.stop_conditions),
            "definition_of_done": args.definition_of_done,
            "parent_id": getattr(args, "parent_id", None) or None,
            "step_index": getattr(args, "step_index", None),
            "depends_on": _queue_split_text(getattr(args, "depends_on", "")),
            "on_complete": getattr(args, "on_complete", None) or None,
            "workbench": getattr(args, "workbench", None) or None,
            "review": getattr(args, "review", None) or "none",
            "receipts": [],
            "claim": {"claimed_by": None, "claimed_at": None},
            "created_at": now,
            "updated_at": now,
            }
            if idempotency_key:
                item["dispatch"] = {
                    "idempotency_key": idempotency_key,
                    "inbound_route": str(getattr(args, "inbound_route", "") or ""),
                    "delivery_id": str(getattr(args, "delivery_id", "") or ""),
                    "reply_to": str(getattr(args, "reply_to", "") or ""),
                    "accepted_at": now,
                }
                setattr(args, "idempotency_duplicate", False)
            for key in ("run_prompt_path", "needs_me"):
                value = getattr(args, key, None)
                if value:
                    item[key] = value
            items.append(item)
            self.save_items(root, items)
            return item

    def claim_item(self, root: Path, item_id: str, agent_id: str):
        with queue_write_lock(root):
            items = self.load_items(root)
            item = self.find_item(items, item_id)
            claimed_by = str((item.get("claim") or {}).get("claimed_by") or "")
            if claimed_by and claimed_by != agent_id:
                raise ValueError(f"Work item already claimed by {claimed_by}")
            now = self.now_iso()
            item["claim"] = {"claimed_by": agent_id, "claimed_at": now}
            item["worker_heartbeat_at"] = now
            item["status"] = "agent_working"
            item["updated_at"] = now
            self.save_items(root, items)
            return item

    def renew_claim(self, root: Path, item_id: str, agent_id: str):
        with queue_write_lock(root):
            items = self.load_items(root)
            item = self.find_item(items, item_id)
            if item.get("status") != "agent_working" or str((item.get("claim") or {}).get("claimed_by") or "") != agent_id:
                raise ValueError(f"Work item claim is not active for {agent_id}: {item_id}")
            now = self.now_iso()
            item["worker_heartbeat_at"] = now
            item["updated_at"] = now
            self.save_items(root, items)
            return item

    def release_item(self, root: Path, item_id: str, status: str):
        with queue_write_lock(root):
            self._refuse_done_transition(status)
            items = self.load_items(root)
            item = self.find_item(items, item_id)
            item["claim"] = {"claimed_by": None, "claimed_at": None}
            item["worker_heartbeat_at"] = None
            item["status"] = status
            item["updated_at"] = self.now_iso()
            self.save_items(root, items)
            return item

    def update_status(self, root: Path, item_id: str, status: str):
        with queue_write_lock(root):
            self._refuse_done_transition(status)
            items = self.load_items(root)
            item = self.find_item(items, item_id)
            item["status"] = status
            item["updated_at"] = self.now_iso()
            self.save_items(root, items)
            return item

    def attach_receipt(self, root: Path, item_id: str, receipt_path: str, status: str | None = None):
        with queue_write_lock(root):
            self._refuse_done_transition(status)
            items = self.load_items(root)
            item = self.find_item(items, item_id)
            receipt = {"path": receipt_path, "created_at": self.now_iso()}
            if status:
                receipt["status"] = status
                item["status"] = status
            item.setdefault("receipts", []).append(receipt)
            item["updated_at"] = self.now_iso()
            self.save_items(root, items)
            return item


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
        "profile_requested": "aos-orchestrator",
        "provider": "configured externally",
        "model": "configured externally",
        "escalation_profile": "orchestrator_escalated",
        "escalation_rule": "Use Operating Hermes triage when the queue owner is missing or unknown.",
        "policy": "Fallback to native Operating Hermes through a scoped aos-orchestrator invocation; never substitute a workbench.",
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
    scoped_orchestrator = profile_requested == "aos-orchestrator"
    profile_used = "aos-orchestrator" if scoped_orchestrator else "explicit_model_provider_route" if explicit_route else "default"
    profile_fallback_reason = "" if scoped_orchestrator or explicit_route else "explicit provider/model route missing or placeholder"
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


def _read_queue_items_with_diagnostics() -> tuple[list[dict], dict[str, int]]:
    path = _queue_items_path()
    if not path.exists():
        return [], {"invalidRecordCount": 0}
    items = []
    invalid_record_count = 0
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    invalid_record_count += 1
                    continue
                if isinstance(item, dict):
                    items.append(item)
                else:
                    invalid_record_count += 1
    except OSError as exc:
        raise ValueError("Queue file could not be read") from exc
    return items, {"invalidRecordCount": invalid_record_count}


def _read_queue_items() -> list[dict]:
    items, _diagnostics = _read_queue_items_with_diagnostics()
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


def _queue_apply_source_refs(queue_tool, item_id: str, source_refs: list[str]) -> dict:
    with queue_write_lock(BASE_DIR):
        items = queue_tool.load_items(BASE_DIR)
        item = queue_tool.find_item(items, item_id)
        item["source_refs"] = source_refs
        item["updated_at"] = queue_tool.now_iso()
        queue_tool.save_items(BASE_DIR, items)
        return item


def _queue_create_dashboard_item(body: QueueItemCreate) -> dict:
    title = body.title.strip()
    if not title:
        raise ValueError("title must not be empty")
    owner = body.owner.strip().lower() or "unassigned"
    if owner not in {"unassigned", "hermes", "codex", "claude", "revenue", "marketing", "delivery", "operations"}:
        raise ValueError(f"Unknown owner: {owner}")
    queue_tool = _load_queue_tool()
    review = str(body.review or "none").strip().lower()
    if review not in {"none", "model"}:
        raise ValueError("review must be none or model")
    source_refs = _queue_split_text(body.source_refs)
    args = argparse.Namespace(
        title=title,
        requested_by="Liam",
        owner_type="agent",
        owner=owner,
        status="agent_todo",
        priority=_queue_priority_value(body.priority),
        source=body.source.strip() or "dashboard",
        tags=",".join(_queue_split_text(body.tags)),
        context=body.context.strip(),
        sources=",".join(_queue_split_text(body.sources)),
        allowed_actions=",".join(_queue_split_text(body.allowed_actions)) or "local_read,local_edit,local_test",
        stop_conditions=",".join(_queue_split_text(body.stop_conditions)) or "external_send,secrets_exposure,destructive_action_outside_scope",
        definition_of_done=body.definition_of_done.strip(),
        parent_id=(body.parent_id or "").strip() or None,
        step_index=body.step_index,
        depends_on=",".join(_queue_split_text(body.depends_on)),
        on_complete=(body.on_complete or "").strip() or None,
        workbench=(body.workbench or "").strip() or None,
        review=review,
    )
    item = queue_tool.create_item(BASE_DIR, args)
    if source_refs:
        item = _queue_apply_source_refs(queue_tool, item["id"], source_refs)
    return item


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
    durable_replace_text(target, text.rstrip() + "\n")
    return receipt_path


def _queue_write_review_receipt(item_id: str, review_note: str, status: str = "done") -> str:
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
        f"- Status: {status}",
    ]
    if note:
        lines.extend(["", "Review note:", note])
    return _queue_write_receipt(item_id, "\n".join(lines))


def _queue_write_workflow_final_closeout_receipt(item_id: str, review_note: str) -> str:
    note = str(review_note or "").strip()
    if len(note) > 500:
        raise ValueError("review_note must be 500 characters or fewer")
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", item_id).strip("-") or "receipt"
    timestamp = datetime.datetime.now(datetime.timezone.utc)
    created_at = timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    receipt_path = (
        Path("queue") / "receipts"
        / f"{safe_id}-final-closeout-{timestamp.strftime('%Y%m%dT%H%M%SZ')}.md"
    ).as_posix()
    lines = [
        "PASS",
        "",
        "Review closeout:",
        "- Reviewed by: Liam",
        f"- Reviewed at: {created_at}",
        "- Status: done",
        "- Workflow result: final integrated review approved",
        "",
        "Token usage: no agent invocation.",
    ]
    if note:
        lines.extend(["", "Review note:", note])
    target = BASE_DIR / receipt_path
    durable_replace_text(target, "\n".join(lines).rstrip() + "\n")
    return receipt_path


def _queue_existing_review_receipt(item: dict, status: str = "done") -> str:
    for receipt in reversed(item.get("receipts") or []):
        path = str(receipt.get("path") if isinstance(receipt, dict) else receipt or "").strip()
        if not path or _queue_artifact_block_reason(path):
            continue
        if isinstance(receipt, dict) and status and receipt.get("status") != status:
            continue
        try:
            content = _queue_read_artifact(path, receipt_only=True)["content"]
        except (FileNotFoundError, ValueError, OSError):
            continue
        if "Review closeout:" in content:
            return path
    return ""


def _workflow_correction_tags(parent: dict) -> list[str]:
    identity = [
        str(tag) for tag in parent.get("tags") or []
        if str(tag).startswith(("pkg:", "pkgver:"))
    ]
    if len([tag for tag in identity if tag.startswith("pkg:")]) != 1 or \
            len([tag for tag in identity if tag.startswith("pkgver:")]) != 1:
        raise ValueError("workflow parent lacks one unambiguous package/version identity")
    return identity + ["pass:correction-1", "lane:operations"]


def _create_workflow_correction(parent: dict, review_note: str) -> tuple[dict, str]:
    note = str(review_note or "").strip()
    if not note:
        raise ValueError("Needs changes for a workflow parent requires one consolidated operator note")
    if len(note) > 500:
        raise ValueError("review_note must be 500 characters or fewer")
    tags = _workflow_correction_tags(parent)
    items = _read_queue_items()
    same_parent = [row for row in items if row.get("parent_id") == parent.get("id")]
    prior = [row for row in same_parent if "pass:correction-1" in (row.get("tags") or [])]
    if prior:
        raise ValueError(
            "one correction cycle has already been used for this package definition version; "
            "a new work item or package definition version is required"
        )
    if parent.get("status") != "human_review":
        raise ValueError("only human_review workflow parents can request a correction")
    step_index = max(
        [int(row["step_index"]) for row in same_parent if isinstance(row.get("step_index"), int)] or [0]
    ) + 1
    obligation = (
        "Implement the consolidated operator correction, then rerun the complete validation "
        "obligation for the package (all required repository tests, cache-free Python compilation, "
        "frontend production build, git diff --check, protected-boundary and live-mutation checks)."
    )
    queue_tool = _load_queue_tool()
    args = argparse.Namespace(
        title="Correction 1: consolidated workflow review changes",
        requested_by="Liam", owner_type="agent", owner="codex", workbench="codex",
        status="agent_todo", priority=int(parent.get("priority") or 5),
        source=str(parent.get("source") or "dashboard"), tags=",".join(tags),
        context=f"Operator note: {note}\n\nFull validation obligation: {obligation}",
        sources=",".join(str(value) for value in parent.get("sources") or []),
        allowed_actions="local reads,local edits,file creation,dependency installation,validation commands,local dev-server startup,browser preview,screenshot capture",
        stop_conditions="external or destructive action required,protected-boundary conflict,validation remains red",
        definition_of_done=f"Operator note is fully addressed. {obligation}",
        parent_id=str(parent.get("id")), step_index=step_index, depends_on="",
        on_complete=None,
    )
    correction = queue_tool.create_item(BASE_DIR, args)
    receipt_path = _queue_write_review_receipt(str(parent.get("id")), note, "inbox")
    queue_tool.attach_receipt(BASE_DIR, str(parent.get("id")), receipt_path, "inbox")
    return correction, receipt_path


def _external_dry_run_receipt_text(body: ExternalSendDryRun) -> str:
    return "\n".join([
        "PASS",
        f"External action dry-run receipt for {body.item_id or 'unattached'}",
        "",
        f"Action: {body.action}",
        f"Recipient: {body.recipient}",
        "dry_run: true",
        "transmitted: false",
        "Live third-party send: impossible in WP11; endpoint writes local receipt only.",
        "",
        "Payload/body that WOULD have been sent:",
        "```text",
        str(body.payload),
        "```",
        "",
        "Validation:",
        "- Confirmation matched SEND <recipient>.",
        "- No LinkedIn, CRM, Gmail, Calendar, GitHub, or third-party endpoint was called.",
        "- This is a local no-op/stub path.",
        "",
        "Token usage: no agent invocation",
    ])


def _write_external_dry_run_receipt(body: ExternalSendDryRun) -> dict:
    recipient = str(body.recipient or "").strip()
    action = str(body.action or "").strip()
    payload = str(body.payload or "")
    expected = f"SEND {recipient}"
    if not recipient:
        raise ValueError("recipient is required")
    if not action:
        raise ValueError("action is required")
    if not payload.strip():
        raise ValueError("payload/body is required")
    if str(body.confirmation or "").strip() != expected:
        raise ValueError(f"typed confirmation must exactly match: {expected}")
    item_id = body.item_id or "external-send-dry-run"
    receipt_path = _queue_write_receipt(item_id, _external_dry_run_receipt_text(body))
    updated = None
    if body.item_id:
        try:
            item = _queue_find_item(body.item_id)
            status = "done" if item.get("status") in {"human_review", "needs_input"} else item.get("status")
            updated = _load_queue_tool().attach_receipt(BASE_DIR, body.item_id, receipt_path, status)
        except (KeyError, ValueError):
            updated = None
    return {
        "success": True,
        "dry_run": True,
        "transmitted": False,
        "receipt_path": receipt_path,
        "item": _queue_detail_item(updated) if updated else None,
        "zero_outbound_evidence": "Backend endpoint has no transport/client branch; it only writes queue/receipts and optionally advances local queue status.",
    }


def _queue_run_receipt_path(item_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", item_id).strip("-") or "receipt"
    return (Path("queue") / "receipts" / f"{safe_id}.md").as_posix()


def _queue_write_run_receipt(item_id: str, receipt_text: str) -> str:
    text = receipt_text.strip()
    if not text:
        raise ValueError("receipt_text must not be empty")
    receipt_path = _queue_run_receipt_path(item_id)
    target = BASE_DIR / receipt_path
    durable_replace_text(target, text.rstrip() + "\n")
    return receipt_path


def _queue_artifact_block_reason(path_text: str) -> str | None:
    normalized = str(path_text or "").replace("\\", "/").lstrip("./")
    if _QUEUE_ARTIFACT_SECRET_RE.search(normalized):
        return "path is blocked because it looks like a secret or environment file"
    if Path(normalized).suffix.lower() not in _QUEUE_ARTIFACT_EXTENSIONS:
        return "only .md, .txt, .json, and .jsonl artifacts are readable"
    if not any(normalized.startswith(prefix) for prefix in _QUEUE_ARTIFACT_ALLOWED_PREFIXES):
        return "artifact path must stay under queue/receipts, results, workflows, packets, or logs"
    return None


def _queue_normalize_artifact_path(path_text: str) -> str:
    """Return one canonical POSIX path beneath the authoritative repository root."""
    raw = str(path_text or "").strip().strip("`'\"")
    if not raw:
        raise ValueError("artifact path is required")
    if "\\" in raw:
        raw = raw.replace("\\", "/")
    try:
        target = resolve_root_relative(raw, root=BASE_DIR)
        canonical = target.relative_to(BASE_DIR.resolve()).as_posix()
    except (AosPathError, ValueError) as exc:
        raise ValueError("artifact path must be root-relative and stay inside the authoritative Linux workspace") from exc
    blocked = _queue_artifact_block_reason(canonical)
    if blocked:
        raise ValueError(blocked)
    return canonical


_QUEUE_ARTIFACT_READ_CACHE: dict[str, tuple[float, int, dict]] = {}


def _queue_read_artifact(relative_path: str, *, receipt_only: bool = False) -> dict:
    path_text = str(relative_path or "").strip()
    root_relative = _queue_normalize_artifact_path(path_text)
    target = resolve_root_relative(root_relative, root=BASE_DIR)

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

    cache_key = str(target)
    cached = _QUEUE_ARTIFACT_READ_CACHE.get(cache_key)
    if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
        return {**cached[2], "path": root_relative}

    result = {
        "path": root_relative,
        "name": target.name,
        "extension": target.suffix.lower(),
        "size_bytes": stat.st_size,
        "modified": datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }
    _QUEUE_ARTIFACT_READ_CACHE[cache_key] = (stat.st_mtime, stat.st_size, result)
    return result


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


def _queue_canonical_token_usage(item_id: str) -> dict | None:
    """Read the existing canonical item sidecar; exact invocation data wins."""
    path = BASE_DIR / "queue" / "receipts" / f"{item_id}.token_usage.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    usage = payload.get("token_usage") if isinstance(payload.get("token_usage"), dict) else {}
    totals = usage.get("totals") if isinstance(usage.get("totals"), dict) else {}
    workbenches = usage.get("workbenches") if isinstance(usage.get("workbenches"), list) else []
    exact = any(
        isinstance(workbench, dict)
        and workbench.get("tool") == "codex"
        and workbench.get("source") == "reported"
        for workbench in workbenches
    )
    invocation = payload.get("profile_invocation") if isinstance(payload.get("profile_invocation"), dict) else {}
    evidence = payload.get("capture_evidence") if isinstance(payload.get("capture_evidence"), dict) else {}
    if exact:
        try:
            input_tokens = int(totals["input"])
            output_tokens = int(totals["output"])
            total_tokens = int(evidence.get("total_tokens", input_tokens + output_tokens))
        except (KeyError, TypeError, ValueError):
            return None
        if min(input_tokens, output_tokens, total_tokens) < 0 or total_tokens != input_tokens + output_tokens:
            return None
        cached = evidence.get("cached_input_tokens")
        reasoning = evidence.get("reasoning_output_tokens")
        try:
            if cached is not None and int(cached) < 0:
                return None
            if reasoning is not None:
                if int(reasoning) < 0 or int(reasoning) > output_tokens:
                    return None
        except (TypeError, ValueError):
            return None
        lines = [
            "Token usage: exact",
            f"Input: {input_tokens}",
            f"Output: {output_tokens}",
            f"Total: {total_tokens}",
            f"Cached input: {int(cached)}" if cached is not None else "Cached input: unavailable",
            f"Reasoning output (subset of output): {int(reasoning)}" if reasoning is not None else "Reasoning output (subset of output): unavailable",
            f"Model: {evidence.get('model_identity') or 'unavailable'}",
        ]
        return {
            "precedence": "exact",
            "lines": lines,
            "token_usage": usage,
            "profile_invocation": invocation,
            "capture_evidence": evidence,
        }
    if invocation.get("invoked") is True:
        return {
            "precedence": "unavailable",
            "lines": ["Token usage: unavailable from current CLI output."],
            "token_usage": usage,
            "profile_invocation": invocation,
            "capture_evidence": evidence,
        }
    if invocation.get("invoked") is False:
        return {
            "precedence": "no_agent_invocation",
            "lines": ["Token usage: no agent invocation"],
            "token_usage": usage,
            "profile_invocation": invocation,
            "capture_evidence": evidence,
        }
    return None


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
        try:
            cleaned = _queue_normalize_artifact_path(cleaned)
        except ValueError:
            pass
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
                    "path": artifact["path"],
                    "size_bytes": artifact["size_bytes"],
                    "modified": artifact["modified"],
                    "sha256": artifact["sha256"],
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
            lines.append(
                f"- AVAILABLE: {path} ({artifact.get('size_bytes', 0)} bytes; "
                f"sha256 {artifact.get('sha256', 'unavailable')})"
            )
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
        receipt_path = ""
        if isinstance(receipt, str):
            receipt_path = receipt
            raw_paths.append(receipt_path)
        elif isinstance(receipt, dict):
            receipt_path = str(receipt.get("path") or "").strip()
            raw_paths.append(receipt_path)
        if receipt_path and not _queue_artifact_block_reason(receipt_path):
            try:
                raw_paths.extend(_queue_artifact_candidates_from_text(_queue_read_artifact(receipt_path, receipt_only=True)["content"]))
            except (FileNotFoundError, ValueError, OSError):
                pass
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


def _queue_artifact_ref(path: str, *, receipt_only: bool = False) -> dict | None:
    if not path:
        return None
    ref = {"path": path}
    reason = _queue_artifact_block_reason(path)
    if reason:
        ref.update({"available": False, "reason": reason})
        return ref
    try:
        artifact = _queue_read_artifact(path, receipt_only=receipt_only)
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
    return ref


def _queue_unique_paths(paths: list[str]) -> list[str]:
    unique = []
    seen = set()
    for path in paths:
        value = str(path or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _queue_final_result_for_item(item: dict, items: list[dict] | None = None, events: list[dict] | None = None) -> dict | None:
    items = items if items is not None else _read_queue_items()
    events = events if events is not None else _read_jsonl_file(BASE_DIR / aos_orchestration.EVENTS_PATH)
    by_id = {str(row.get("id") or ""): row for row in items}
    item_id = str(item.get("id") or "")
    parent_id = str(item.get("parent_id") or item_id or "")
    parent = by_id.get(parent_id)
    children = [row for row in items if str(row.get("parent_id") or "") == parent_id]

    final_events = [
        row for row in events
        if row.get("event") == "acceptance_finalized"
        and str(row.get("parent_id") or row.get("key") or "") == parent_id
    ]
    final_event = final_events[-1] if final_events else None

    final_item_id = str((final_event or {}).get("item_id") or "")
    final_item = by_id.get(final_item_id) if final_item_id else None
    if not final_item:
        candidates = [
            row for row in children
            if row.get("step_index") == 3
            and str(row.get("owner") or "").lower() == "delivery"
            and str(row.get("workbench") or "").lower() == "local"
        ]
        final_item = sorted(candidates, key=_queue_item_sort_key)[0] if candidates else None
        final_item_id = str(final_item.get("id") or "") if final_item else ""

    reviewed_item_id = ""
    if final_item and final_item.get("depends_on"):
        reviewed_item_id = str(final_item.get("depends_on")[0] or "")
    if not reviewed_item_id:
        reviewed = [row for row in children if row.get("step_index") == 2 or row.get("on_complete") == "human_review"]
        reviewed_item_id = str((sorted(reviewed, key=_queue_item_sort_key)[0] if reviewed else {}).get("id") or "")

    relevant_ids = {parent_id, reviewed_item_id, final_item_id}
    if item_id not in relevant_ids:
        return None

    artifact_paths = []
    receipt_paths = []
    if final_event:
        artifact_paths.append(str(final_event.get("artifact_path") or ""))
        receipt_paths.append(str(final_event.get("receipt_path") or ""))

    if parent_id:
        convention = f"results/orchestration_acceptance/{parent_id}/03_final_review_package.md"
        if (BASE_DIR / convention).is_file():
            artifact_paths.append(convention)

    for candidate in [final_item, parent]:
        if not candidate:
            continue
        for receipt in candidate.get("receipts") or []:
            path = str(receipt.get("path") if isinstance(receipt, dict) else receipt or "").strip()
            if final_item_id and f"{final_item_id}-final-closeout-" in path:
                receipt_paths.append(path)

    if final_item_id:
        receipt_dir = BASE_DIR / "queue" / "receipts"
        if receipt_dir.exists():
            for path in sorted(receipt_dir.glob(f"{final_item_id}-final-closeout-*.md")):
                receipt_paths.append(_safe_relative(path))

    artifact_paths = _queue_unique_paths(artifact_paths)
    receipt_paths = _queue_unique_paths(receipt_paths)
    artifact_refs = [ref for ref in (_queue_artifact_ref(path) for path in artifact_paths) if ref]
    receipt_refs = [ref for ref in (_queue_artifact_ref(path, receipt_only=True) for path in receipt_paths) if ref]
    completed = bool(final_event or any(ref.get("available") for ref in artifact_refs) or (final_item or {}).get("status") == "done")

    if not completed and not final_item_id:
        return None

    return {
        "complete": completed and (final_item or {}).get("status") == "done" and (parent or {}).get("status") == "done",
        "parent_id": parent_id,
        "reviewed_item_id": reviewed_item_id,
        "final_item_id": final_item_id,
        "chain_status": (parent or {}).get("status", ""),
        "final_item_status": (final_item or {}).get("status", ""),
        "final_artifact_paths": artifact_paths,
        "final_receipt_paths": receipt_paths,
        "final_artifacts": artifact_refs,
        "final_receipts": receipt_refs,
        "output_folder_path": str(Path(artifact_paths[0]).parent).replace("\\", "/") if artifact_paths else "",
    }


def _queue_latest_receipt(item: dict) -> dict | None:
    receipts = item.get("receipts") or []
    if not receipts:
        return None
    latest = next(
        (
            row for row in reversed(receipts)
            if not any(
                marker in str(row if isinstance(row, str) else (row or {}).get("path") or "")
                for marker in ("-notification-", "-telegram-escalation-", "-review-note-")
            )
        ),
        receipts[-1],
    )
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

    canonical_usage = _queue_canonical_token_usage(str(item.get("id") or ""))
    return {
        "path": path,
        "status": latest.get("status") or item.get("status", ""),
        "created_at": latest.get("created_at"),
        "available": bool(content),
        "content": content,
        "token_usage_lines": canonical_usage["lines"] if canonical_usage else (_queue_token_usage_lines(content) if content else []),
        "token_usage": canonical_usage["token_usage"] if canonical_usage else None,
        "token_usage_precedence": canonical_usage["precedence"] if canonical_usage else "receipt_text",
        "profile_invocation": canonical_usage["profile_invocation"] if canonical_usage else None,
        "capture_evidence": canonical_usage["capture_evidence"] if canonical_usage else None,
        **metadata,
        "summary": _bounded_hermes_answer(summary or "Receipt summary unavailable.", 900),
    }


def _queue_review_details(item: dict, latest_receipt: dict | None) -> dict:
    content = str((latest_receipt or {}).get("content") or "")
    blocker = _receipt_section_value(content, "Blockers", "")
    if blocker.casefold() in {"none", "none reported", "- none"}:
        blocker = ""
    review_result = str(_field_from_output(content, "Review result") or "")
    if review_result.casefold() in {"", "pass", "passed", "none"}:
        review_result = ""
    attempts_text = _field_from_output(content, "Attempts used")
    try:
        attempts = int(attempts_text) if attempts_text else None
    except ValueError:
        attempts = attempts_text or None
    return {
        "summary": _queue_summary_for_operator(item, latest_receipt),
        "failure_explanation": blocker or review_result,
        "worker": _field_from_output(content, "Assigned worker") or str(item.get("owner") or "unassigned"),
        "attempts": attempts,
        "validation": _receipt_section_value(content, "Validation", ""),
        "token_usage_lines": (latest_receipt or {}).get("token_usage_lines") or _queue_token_usage_lines(content),
        "receipt_path": str((latest_receipt or {}).get("path") or ""),
        "receipt_content": content,
    }


def _queue_summary_for_operator(item: dict, latest_receipt: dict | None) -> str:
    """Return a deterministic useful operator summary; never just echo the title."""
    title = str(item.get("title") or "").strip()
    receipt_content = str((latest_receipt or {}).get("content") or "")
    candidates = [
        _receipt_section_value(receipt_content, "Summary for operator", ""),
        _receipt_section_value(receipt_content, "Root cause / behavior changed", ""),
        _receipt_section_value(receipt_content, "Validation", ""),
        _receipt_section_value(receipt_content, "Summary", ""),
        str(item.get("context") or ""),
        str(item.get("definition_of_done") or ""),
    ]
    for candidate in candidates:
        text = re.sub(r"\s+", " ", str(candidate or "")).strip(" -")
        if not text or text in {"None reported", "No validation reported"}:
            continue
        if title and text.casefold() == title.casefold():
            continue
        if title and text.casefold().startswith(title.casefold()) and len(text) <= len(title) + 24:
            continue
        summary = _bounded_hermes_answer(text, 320)
        status = str(item.get("status") or "").strip()
        if status == "human_review":
            return (
                f"{summary} Approving uses the existing local review-close path and deterministic resume tick; "
                "it does not send anything externally."
            )
        if status == "needs_input":
            return f"{summary} This needs operator input through the existing queue path; no external send is performed."
        return summary
    return (
        "Recorded queue metadata does not include a substantive closeout summary yet. "
        "Inspect the linked receipt/artifact before acting; dashboard actions remain local and do not send externally."
    )


def _queue_detail_item(item: dict, invocation_attributions: dict[str, dict] | None = None) -> dict:
    public = _queue_public_item(item, invocation_attributions)
    latest_receipt = _queue_latest_receipt(item)
    steps = _workflow_steps_for_item(item)
    step_index = item.get("step_index")
    step_progress = None
    if steps and isinstance(step_index, int):
        step_progress = {"current": max(0, min(step_index, len(steps))), "total": len(steps), "label": f"{max(0, min(step_index, len(steps)))} of {len(steps)}"}
    integrated_review_path = f"workflows/queue_artifacts/{item.get('id')}_final_integrated_dashboard_review.md"
    integrated_review = _queue_artifact_ref(integrated_review_path) if item.get("owner_type") == "workflow" and (BASE_DIR / integrated_review_path).is_file() else None
    run_artifacts = _queue_artifact_refs(item, latest_receipt.get("content", "") if latest_receipt else "")
    latest_receipt_path = str((latest_receipt or {}).get("path") or "")
    primary_artifact = next(
        (ref for ref in run_artifacts if ref.get("available") and ref.get("path") != latest_receipt_path),
        None,
    )
    if primary_artifact:
        try:
            primary_artifact = {**primary_artifact, "content": _queue_read_artifact(primary_artifact["path"])["content"]}
        except (FileNotFoundError, ValueError, OSError):
            primary_artifact = None
    public.update({
        "detail_loaded": True,
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
        "parent_id": item.get("parent_id"),
        "step_index": item.get("step_index"),
        "depends_on": item.get("depends_on") or [],
        "on_complete": item.get("on_complete"),
        "workbench": item.get("workbench"),
        "honest_status": _honest_status(item),
        "workflow_steps": steps,
        "step_progress": step_progress,
        "claim": item.get("claim") or {"claimed_by": None, "claimed_at": None},
        "receipts": item.get("receipts") or [],
        "latest_receipt": latest_receipt,
        "summary_for_operator": _queue_summary_for_operator(item, latest_receipt),
        "review_details": _queue_review_details(item, latest_receipt),
        "review_notes": item.get("review_notes") or [],
        "latest_review_note": (item.get("review_notes") or [None])[-1],
        "run_artifacts": run_artifacts,
        "primary_artifact": primary_artifact,
        "external_handoff_relevant": bool(_external_action_matches(
            f"{item.get('title', '')}\n{item.get('context', '')}"
        )),
        "final_result": _queue_final_result_for_item(item),
        "integrated_review_artifact": integrated_review,
        "client_scope": item.get("client_scope"),
        "brain_context_used": item.get("brain_context_used") or [],
        "capture_proposal": item.get("capture_proposal"),
        "pipeline": _queue_pipeline(item),
        "stuck_recovery": _queue_stuck_recovery(item),
    })
    return public


def _queue_list_item(item: dict, invocation_attributions: dict[str, dict] | None = None) -> dict:
    """Return a compact list row; load full artifact detail only on selection."""
    public = _queue_public_item(item, invocation_attributions)
    public.update({
        "detail_loaded": False,
        "source": item.get("source", ""),
        "workbench": item.get("workbench", ""),
        "lane": _queue_item_lane(item),
    })
    if item.get("status") in {"human_review", "needs_input"}:
        latest = _queue_latest_receipt(item)
        public["summary_for_operator"] = _queue_summary_for_operator(item, latest)
        if latest:
            public["latest_receipt"] = {
                key: latest.get(key)
                for key in ("path", "status", "created_at", "available", "summary")
            }
    return public


def _queue_pipeline(item: dict) -> dict:
    items = _read_queue_items()
    item_id = str(item.get("id") or "")
    parent_id = str(item.get("parent_id") or item_id)
    children = sorted(
        [row for row in items if str(row.get("parent_id") or "") == parent_id],
        key=lambda row: (row.get("step_index") if isinstance(row.get("step_index"), int) else 10_000, str(row.get("id") or "")),
    )
    if not children:
        return {
            "mode": "status_fallback",
            "parent_id": item_id,
            "nodes": [{
                "id": item_id,
                "name": item.get("title") or item_id,
                "status": item.get("status") or "unavailable",
                "timestamp": item.get("updated_at") or item.get("created_at"),
                "execution": "unavailable from recorded evidence",
                "gate": None,
                "depends_on": item.get("depends_on") or [],
                "receipts": item.get("receipts") or [],
                "artifacts": item.get("source_refs") or [],
            }],
            "history": [],
        }
    parent = next((row for row in items if row.get("id") == parent_id), {})
    token_records = _read_token_ledger_records()
    token_by_item: dict[str, list[dict]] = {}
    for record in token_records:
        token_by_item.setdefault(_ledger_task_id(record), []).append(record)
    nodes = []
    for row in [parent, *children]:
        row_id = str(row.get("id") or "")
        records = token_by_item.get(row_id, [])
        records.sort(key=lambda record: str(_ledger_timestamp(record) or ""), reverse=True)
        record = records[0] if records else None
        execution = "deterministic" if record and _ledger_no_agent_invocation(record) else "model spend recorded" if record and _ledger_tokens_basis(record)[0] is not None else "token evidence unavailable"
        nodes.append({
            "id": row_id,
            "name": row.get("title") or row_id,
            "step_index": row.get("step_index"),
            "status": row.get("status") or "unavailable",
            "timestamp": row.get("updated_at") or row.get("created_at"),
            "execution": execution,
            "gate": row.get("on_complete"),
            "depends_on": row.get("depends_on") or [],
            "receipts": row.get("receipts") or [],
            "artifacts": row.get("source_refs") or [],
        })
    events = [
        row for row in _read_jsonl_file(BASE_DIR / aos_orchestration.EVENTS_PATH)
        if str(row.get("parent_id") or "") == parent_id
    ]
    history = [
        {"event": row.get("event"), "item_id": row.get("item_id"), "timestamp": _ledger_timestamp(row), "status": row.get("status") or row.get("result")}
        for row in events
        if row.get("event") in {"step_advanced", "acceptance_finalized", "workflow_parent_review_ready"}
    ]
    return {"mode": "workflow_chain", "parent_id": parent_id, "nodes": nodes, "history": history}


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


def _process_marker_running(marker: str) -> bool:
    for proc in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            args = [
                part.decode("utf-8", errors="replace")
                for part in proc.read_bytes().split(b"\0")
                if part
            ]
        except OSError:
            continue
        for arg in args:
            if Path(arg).name != marker:
                continue
            if arg == marker or not any(character.isspace() for character in arg) or Path(arg).is_file():
                return True
    return False


def _binary_readiness(binary: str, *, login_status: bool = False) -> dict:
    executable = shutil.which(binary)
    if not executable:
        return {"available": False, "state": "missing", "executable": ""}
    try:
        version = subprocess.run(
            [executable, "--version"], cwd=str(BASE_DIR), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "state": type(exc).__name__, "executable": executable}
    result = {
        "available": version.returncode == 0,
        "state": "ready" if version.returncode == 0 else "version_probe_failed",
        "executable": executable,
        "version": _bounded_stream_tail(version.stdout or version.stderr, 160).splitlines()[-1] if (version.stdout or version.stderr) else "unavailable",
    }
    if login_status and result["available"]:
        try:
            auth = subprocess.run(
                [executable, "login", "status"], cwd=str(BASE_DIR), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=5, check=False,
            )
            result["authenticated"] = auth.returncode == 0 and "logged in" in (auth.stdout + auth.stderr).lower()
            if not result["authenticated"]:
                result["state"] = "authentication_unavailable"
                result["available"] = False
        except (OSError, subprocess.TimeoutExpired):
            result["authenticated"] = False
            result["state"] = "authentication_probe_failed"
            result["available"] = False
    return result


def _latest_route_failure() -> dict | None:
    path = LOCAL_AGENT_ROUTE_LOG if BASE_DIR == _IMPORTED_BASE_DIR else BASE_DIR / "logs" / "local_agent_route.jsonl"
    if not path.is_file():
        return None
    for raw in reversed(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or "success" not in row:
            continue
        if row.get("success") is not False:
            return None
        return {
            "timestamp": row.get("timestamp"),
            "route": row.get("route"),
            "item_id": row.get("item_id"),
            "failure_class": row.get("failure_class"),
            "stage": row.get("stage"),
            "log_path": "logs/local_agent_route.jsonl",
        }
    return None


def _operator_system_status_closeout() -> dict:
    try:
        items = _read_queue_items()
        queue_state = "healthy"
    except ValueError:
        items = []
        queue_state = "invalid"
    runner = _queue_runner_status(BASE_DIR)
    actionable = [
        item for item in items
        if "async_dispatch" in {str(tag) for tag in item.get("tags") or []}
        and item.get("status") in {"agent_todo", "agent_working"}
    ]
    if runner.get("available"):
        runner_state = "running"
    elif actionable:
        runner_state = "stopped_with_pending_work"
    else:
        runner_state = "on_demand_idle"
    codex = codex_policy_readiness(CODEX_TARGET)
    hermes = _binary_readiness("hermes")
    bridge_running = _process_marker_running("telegram_bridge.py")
    bridge_state = "running" if bridge_running else "not_running"
    failure = _latest_route_failure()
    downstream_ready = (
        queue_state == "healthy"
        and runner_state != "stopped_with_pending_work"
        and bool(codex.get("available"))
        and bool(hermes.get("available"))
        and failure is None
    )
    overall = "healthy" if bridge_running and downstream_ready else "degraded"
    last_failure = (
        f"{failure.get('failure_class')} at {failure.get('stage')} ({failure.get('item_id') or 'no item'})"
        if failure else "none recorded"
    )
    output = "\n".join((
        "PASS" if overall == "healthy" else "NEEDS ATTENTION",
        f"Operator system: {overall}",
        f"Bridge health: {bridge_state}",
        "Backend health: ready (this endpoint is responding)",
        f"Queue health: {queue_state}; items={len(items)}; actionable={len(actionable)}",
        f"Runner state: {runner_state}",
        f"Local agent route: {'ready' if downstream_ready else 'degraded'}",
        (
            f"Codex availability: {codex.get('state')}; executable={codex.get('executable') or 'missing'}; "
            f"user={codex.get('linux_user') or 'unknown'}; cwd={codex.get('cwd') or 'unknown'}; "
            f"sandbox={codex.get('sandbox') or 'unknown'}; approval_policy={codex.get('approval_policy') or 'unknown'}"
        ),
        f"Hermes availability: {hermes.get('state')}; executable={hermes.get('executable') or 'missing'}",
        f"Last route failure: {last_failure}",
        "Token usage: no agent invocation",
    ))
    return {
        "success": overall == "healthy",
        "output": output,
        "returncode": 0 if overall == "healthy" else 2,
        "state": overall,
        "bridge": {"state": bridge_state, "running": bridge_running},
        "backend": {"state": "ready", "available": True},
        "queue": {"state": queue_state, "items": len(items), "actionable": len(actionable)},
        "runner": {**runner, "state": runner_state},
        "local_agent_route": {"state": "ready" if downstream_ready else "degraded", "ready": downstream_ready},
        "codex": codex,
        "hermes": hermes,
        "last_route_failure": failure,
        "requested_target": "operator_status",
        "selected_route": "local_system_status",
        "delegation_reason": "bounded read-only system health intent",
        "codex_forbidden": "no",
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


def _queue_public_item(item: dict, invocation_attributions: dict[str, dict] | None = None) -> dict:
    attributions = _queue_invocation_attributions() if invocation_attributions is None else invocation_attributions
    attribution = attributions.get(str(item.get("id") or ""), {})
    needs_me = _queue_needs_me_reasons(item, attribution)
    return {
        "id": item.get("id", ""),
        "title": aos_orchestration.operator_task_title(item),
        "status": item.get("status", ""),
        "owner": item.get("owner", "unassigned"),
        "priority": item.get("priority", 0),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "invocation_source": attribution.get("invocation_source"),
        "invocation_source_evidence": attribution.get("invocation_source_evidence", "no authoritative invocation source"),
        "invocation_source_timestamp": attribution.get("invocation_source_timestamp"),
        "model_turns": attribution.get("model_turns"),
        "needs_me": needs_me,
    }


def _queue_active_items(items: list[dict]) -> list[dict]:
    return sorted(
        [item for item in items if item.get("status") in _ACTIVE_QUEUE_STATUSES],
        key=_queue_item_sort_key,
    )


_HUMAN_NEEDED_STATUSES = {"needs_input", "human_review", "blocked"}


def _queue_needs_me_reasons(item: dict, attribution: dict | None = None) -> list[str]:
    reasons = []
    for value in item.get("needs_me") or []:
        reason = str(value).strip()
        if reason and reason not in reasons:
            reasons.append(reason)
    turns = (attribution or {}).get("model_turns")
    if isinstance(turns, int) and not isinstance(turns, bool) and turns > MODEL_TURNS_THRESHOLD:
        if "excessive model turns" not in reasons:
            reasons.append("excessive model turns")
    return reasons


def _queue_human_needed_items(
    items: list[dict], invocation_attributions: dict[str, dict] | None = None
) -> list[dict]:
    attributions = _queue_invocation_attributions() if invocation_attributions is None else invocation_attributions
    return sorted(
        [
            item for item in items
            if item.get("status") in _HUMAN_NEEDED_STATUSES
            or _queue_needs_me_reasons(item, attributions.get(str(item.get("id") or "")))
        ],
        key=_queue_item_sort_key,
    )


def _queue_human_needed_count(counts: dict[str, int]) -> int:
    return sum(int(counts.get(status, 0) or 0) for status in _HUMAN_NEEDED_STATUSES)


_DASHBOARD_LANES = ("marketing", "revenue", "delivery", "operations", "unassigned")


def _queue_item_lane(item: dict) -> str:
    """Resolve the recorded lane without inventing a queue worker field."""
    for tag in item.get("tags") or []:
        value = str(tag or "").strip().lower()
        if value.startswith("lane:"):
            lane = value.split(":", 1)[1]
            if lane == "ops":
                lane = "operations"
            return lane if lane in _DASHBOARD_LANES else "unassigned"
    owner = str(item.get("owner") or "").strip().lower()
    if owner == "ops":
        owner = "operations"
    return owner if owner in _DASHBOARD_LANES else "unassigned"


def _dashboard_lane_activity(items: list[dict]) -> list[dict]:
    token_rows = [_token_record_view(row) for row in _read_token_ledger_records()]
    run_rows = _read_jsonl_file(BASE_DIR / "queue" / "run_ledger.jsonl")
    by_token: dict[str, list[dict]] = {}
    by_run: dict[str, list[dict]] = {}
    for row in token_rows:
        by_token.setdefault(str(row.get("item_id") or ""), []).append(row)
    for row in run_rows:
        by_run.setdefault(str(row.get("item_id") or ""), []).append(row)

    groups = []
    for lane in _DASHBOARD_LANES:
        lane_items = [item for item in items if _queue_item_lane(item) == lane]
        newest = sorted(
            lane_items,
            key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
            reverse=True,
        )
        current = [row for row in newest if row.get("status") in {"agent_todo", "agent_working"}]
        completed = [row for row in newest if row.get("status") == "done"]
        latest_receipt = next(
            (_queue_latest_receipt(row) for row in newest if row.get("receipts")),
            None,
        )
        artifact = next(
            (
                ref
                for row in newest
                for ref in row.get("run_artifacts") or []
                if ref.get("available") and ref.get("path") != (latest_receipt or {}).get("path")
            ),
            None,
        )
        lane_token_rows = [
            token
            for row in lane_items
            for token in by_token.get(str(row.get("id") or ""), [])
        ]
        exact_tokens = [row for row in lane_token_rows if row.get("availability_state") == "exact"]
        exact_tokens.sort(key=lambda row: str(row.get("event_timestamp_utc") or ""), reverse=True)
        latest_exact = exact_tokens[0] if exact_tokens else None
        successful_runs = [
            run
            for row in lane_items
            for run in by_run.get(str(row.get("id") or ""), [])
            if str(run.get("status") or run.get("result") or "").lower() in {"done", "success", "passed", "pass"}
        ]
        successful_runs.sort(key=lambda row: str(_ledger_timestamp(row) or ""), reverse=True)
        groups.append({
            "lane": lane,
            "items": newest,
            "current_assigned_work": current[:3],
            "last_completed_item": completed[0] if completed else None,
            "latest_receipt": latest_receipt,
            "latest_artifact": artifact,
            "counts": {
                status: sum(1 for row in lane_items if row.get("status") == status)
                for status in ("agent_todo", "agent_working", "blocked", "human_review")
            },
            "token_usage": ({
                "state": "exact",
                "input": latest_exact.get("input_tokens"),
                "output": latest_exact.get("output_tokens"),
                "total": latest_exact.get("total_tokens"),
                "item_id": latest_exact.get("item_id"),
            } if latest_exact else {"state": "unavailable"}),
            "last_successful_run": successful_runs[0] if successful_runs else None,
            "degraded": not bool(lane_items),
            "shortcut": {
                "lane": lane,
                "workbench": str((current[0] if current else newest[0] if newest else {}).get("workbench") or ""),
            },
        })
    return groups


@app.get("/api/queue/summary")
def queue_summary():
    """Read local queue state for the dashboard without mutating the queue."""
    try:
        items, diagnostics = _read_queue_items_with_diagnostics()
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
    invocation_attributions = _queue_invocation_attributions()
    human_needed_items = _queue_human_needed_items(items, invocation_attributions)
    needs_liam = len(human_needed_items)
    active_items = _queue_active_items(items)
    return {
        "success": True,
        "counts": counts,
        "totalCount": len(items),
        "diagnostics": diagnostics,
        "needsLiam": needs_liam,
        "needsMeCount": needs_liam,
        "humanNeededCount": needs_liam,
        "needsMeItems": [_queue_public_item(item, invocation_attributions) for item in human_needed_items],
        "activeCount": len(active_items),
        "activeItems": [_queue_public_item(item, invocation_attributions) for item in active_items[:10]],
        "nextItem": _queue_public_item(active_items[0], invocation_attributions) if active_items else None,
        "nextAction": _queue_next_action(active_items, counts),
    }


@app.get("/api/queue/status")
def queue_status():
    """Read-only dashboard queue status."""
    return queue_summary()


@app.get("/api/queue/items")
def queue_items(scope: str | None = None):
    """List local queue items without mutating or launching anything."""
    normalized_scope = str(scope or "all").strip().lower()
    if normalized_scope not in _QUEUE_ITEM_SCOPES:
        raise HTTPException(status_code=400, detail="scope must be active, history, or all")
    try:
        all_items, diagnostics = _read_queue_items_with_diagnostics()
    except ValueError as exc:
        return {"success": False, "message": "Queue unavailable", "reason": str(exc), "items": []}
    if normalized_scope == "active":
        items = [item for item in all_items if item.get("status") in _ACTIVE_QUEUE_STATUSES]
    elif normalized_scope == "history":
        items = [item for item in all_items if item.get("status") in _HISTORY_QUEUE_STATUSES]
    else:
        items = all_items
    items = sorted(items, key=_queue_item_sort_key)
    invocation_attributions = _queue_invocation_attributions()
    return {
        "success": True,
        "scope": normalized_scope,
        "itemCount": len(items),
        "totalCount": len(all_items),
        "diagnostics": diagnostics,
        "items": [_queue_list_item(item, invocation_attributions) for item in items],
    }


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
    latitude_telemetry.trace("queue.item_create", "queue", "ok", item_id=item.get("id"), owner=item.get("owner"), queue_status=item.get("status"), source=item.get("source"))
    return {"success": True, "item": _queue_detail_item(item)}


@app.post("/api/queue/chains")
def create_queue_chain(body: HermesChainConfirm):
    """File an operator-confirmed Hermes chain as linked local queue items."""
    if not body.steps:
        raise HTTPException(status_code=400, detail="chain must include at least one step")
    try:
        parent = _queue_create_dashboard_item(QueueItemCreate(
            title=body.title,
            owner="hermes",
            priority="normal",
            tags="hermes_chain,parent",
            source="dashboard/hermes_chain",
            context=body.context,
            source_refs=",".join(body.source_refs),
            definition_of_done="All linked chain steps reach done or an operator gate.",
            allowed_actions="local_read,local_edit,local_test",
            stop_conditions="external_send,secrets_exposure,destructive_action_outside_scope",
        ))
        created_steps = []
        previous_id = ""
        for index, step in enumerate(body.steps, start=1):
            depends_on = list(step.depends_on or [])
            if index > 1 and not depends_on and previous_id:
                depends_on = [previous_id]
            step_item = _queue_create_dashboard_item(QueueItemCreate(
                title=step.title,
                owner=step.owner,
                priority=step.priority,
                tags=",".join(step.tags or ["hermes_chain"]),
                source="dashboard/hermes_chain",
                context=step.context or body.context,
                sources="",
                source_refs=",".join((body.source_refs or []) + (step.source_refs or [])),
                definition_of_done=step.definition_of_done,
                allowed_actions=",".join(step.allowed_actions or ["local_read", "local_edit", "local_test"]),
                stop_conditions=",".join(step.stop_conditions or ["external_send", "secrets_exposure", "destructive_action_outside_scope"]),
                parent_id=parent["id"],
                step_index=index,
                depends_on=",".join(depends_on),
                on_complete=step.on_complete,
                workbench=step.workbench,
            ))
            if index > 1:
                step_item = _load_queue_tool().update_status(BASE_DIR, step_item["id"], "inbox")
            created_steps.append(step_item)
            previous_id = step_item["id"]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "success": True,
        "parent": _queue_detail_item(parent),
        "steps": [_queue_detail_item(step) for step in created_steps],
        "token_usage_text": "Token usage: no agent invocation",
    }


@app.post("/api/orchestration/tick")
def orchestration_tick():
    """Run one deterministic local orchestration tick; never invokes agents."""
    try:
        result = aos_orchestration.tick(BASE_DIR)
        latitude_telemetry.trace("runner.deterministic_tick", "orchestration", "ok", events=len(result.get("events", [])) if isinstance(result, dict) else None)
        return result
    except aos_orchestration.OrchestrationError as exc:
        latitude_telemetry.trace("runner.deterministic_tick", "orchestration", "blocked", error_type=type(exc).__name__)
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/orchestration/telegram-send-test")
def orchestration_telegram_send_test(body: TelegramSendValidation):
    """Validation hook for the allowlisted existing Telegram bridge send path."""
    with queue_write_lock(BASE_DIR):
        try:
            item = _queue_find_item(body.item_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="queue item not found")
        result = aos_orchestration.attempt_telegram_send(BASE_DIR, item, body.recipient, body.message, key="api_validation")
        aos_orchestration.append_jsonl(BASE_DIR / aos_orchestration.EVENTS_PATH, result)
        items = _read_queue_items()
        for index, existing in enumerate(items):
            if existing.get("id") == item.get("id"):
                items[index] = item
                break
        _load_queue_tool().save_items(BASE_DIR, items)
        return {"success": result.get("result") in {"sent", "already_sent", "blocked", "send_failed"}, **result}


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
    event_type = "queue.needs_me" if status in {"needs_input", "human_review", "blocked"} else "queue.status_change"
    latitude_telemetry.trace(event_type, "queue", status, item_id=item_id, queue_status=status)
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
    if status:
        event_type = "queue.needs_me" if status in {"needs_input", "human_review", "blocked"} else "queue.status_change"
        latitude_telemetry.trace(event_type, "queue", status, item_id=item_id, queue_status=status, receipt_path=receipt_path)
    return {
        "ok": True,
        "success": True,
        "item_id": item_id,
        "receipt_path": receipt_path,
        "status": item.get("status"),
        "item": _queue_detail_item(item),
    }


@app.post("/api/queue/items/{item_id}/review-note")
def save_queue_item_review_note(item_id: str, body: QueueReviewNote):
    """Save an optional local operator note without changing review state."""
    note = str(body.review_note or "").strip()
    if len(note) > 500:
        raise HTTPException(status_code=400, detail="review_note must be 500 characters or fewer")
    queue_tool = _load_queue_tool()
    try:
        _queue_find_item(item_id)
        with queue_write_lock(BASE_DIR):
            items = queue_tool.load_items(BASE_DIR)
            item = next(row for row in items if row.get("id") == item_id)
            if item.get("status") != "human_review":
                raise ValueError("review notes can only be saved while an item is in human_review")
            timestamp = queue_tool.now_iso()
            if note:
                item.setdefault("review_notes", []).append({
                    "note": note,
                    "created_at": timestamp,
                    "saved_by": "Liam",
                    "token_usage_text": "Token usage: no agent invocation",
                })
            item["updated_at"] = timestamp
            queue_tool.save_items(BASE_DIR, items)
    except (KeyError, StopIteration, ValueError) as exc:
        if isinstance(exc, (KeyError, StopIteration)):
            raise HTTPException(status_code=404, detail="queue item not found")
        raise HTTPException(status_code=400, detail=str(exc))
    refreshed = _queue_find_item(item_id)
    return {
        "ok": True,
        "success": True,
        "item_id": item_id,
        "status": refreshed.get("status"),
        "state_changed": False,
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
        "item": _queue_detail_item(refreshed),
    }


def _close_queue_item_review(item_id: str, body: QueueReviewClose, *, notify_telegram: bool) -> dict:
    """Apply the canonical review-close contract, optionally suppressing a second Telegram reply."""
    tick_result = None
    telegram_reply = None
    correction_item = None
    try:
        status = _queue_validate_status(body.status)
        if status not in {"done", "needs_input", "blocked"}:
            raise ValueError("review status must be done, needs_input, or blocked")
        existing = _queue_find_item(item_id)
        is_workflow_correction = existing.get("owner_type") == "workflow" and status == "needs_input"
        already_closed = existing.get("status") == status and status == "done"
        if existing.get("status") != "human_review" and not already_closed and not is_workflow_correction:
            raise ValueError("only human_review items can be closed from review")
        expected_actions = {
            "done": {"approve"},
            "needs_input": {"needs_changes"},
            "blocked": {"block", "reject"},
        }[status]
        if str(body.action or "").strip().lower() not in expected_actions:
            raise ValueError(
                f"explicit review action required for {status}: {', '.join(sorted(expected_actions))}"
            )
        if status in {"needs_input", "blocked"} and not str(body.review_note or "").strip():
            raise ValueError("Needs changes and Reject require an operator review note")
        if is_workflow_correction:
            correction_item, receipt_path = _create_workflow_correction(existing, body.review_note)
        elif already_closed:
            latest = (existing.get("receipts") or [""])[-1]
            latest_path = latest.get("path") if isinstance(latest, dict) else latest
            receipt_path = _queue_existing_review_receipt(existing, status) or str(latest_path or "")
        else:
            receipt_path = (
                _queue_write_workflow_final_closeout_receipt(item_id, body.review_note)
                if existing.get("owner_type") == "workflow" and status == "done"
                else _queue_write_review_receipt(item_id, body.review_note, status)
            )
            _load_queue_tool().attach_receipt(BASE_DIR, item_id, receipt_path, status)
            if notify_telegram:
                telegram_reply = _telegram_reply_on_close(existing, status, body.review_note, receipt_path)
        if status == "done":
            tick_result = aos_orchestration.tick(BASE_DIR, allow_telegram_escalation=False)
    except KeyError:
        raise HTTPException(status_code=404, detail="queue item not found")
    except aos_orchestration.OrchestrationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    latitude_telemetry.trace("queue.human_review_close", "queue", status, item_id=item_id, queue_status=status, receipt_path=receipt_path)
    refreshed = _queue_find_item(item_id)
    final_result = _queue_final_result_for_item(refreshed)
    advanced = tick_result.get("advanced", []) if isinstance(tick_result, dict) else []
    advanced_item_ids = _queue_unique_paths([str(row.get("item_id") or "") for row in advanced if row.get("item_id")])
    return {
        "ok": True,
        "success": True,
        "item_id": item_id,
        "reviewed_item_id": item_id,
        "receipt_path": receipt_path,
        "status": refreshed.get("status"),
        "item": _queue_detail_item(refreshed),
        "resume_tick": tick_result,
        "telegram_reply": telegram_reply,
        "parent_id": (final_result or {}).get("parent_id") or refreshed.get("parent_id"),
        "final_item_id": (final_result or {}).get("final_item_id", ""),
        "chain_status": (final_result or {}).get("chain_status", ""),
        "final_item_status": (final_result or {}).get("final_item_status", ""),
        "final_artifact_paths": (final_result or {}).get("final_artifact_paths", []),
        "final_receipt_paths": (final_result or {}).get("final_receipt_paths", []),
        "advanced_item_ids": advanced_item_ids,
        "correction_item": _queue_detail_item(correction_item) if correction_item else None,
        "final_result": final_result,
    }


@app.post("/api/queue/items/{item_id}/review-close")
def close_queue_item_review(item_id: str, body: QueueReviewClose):
    """Close one human_review queue item with an optional local review note."""
    return _close_queue_item_review(item_id, body, notify_telegram=True)


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


@app.post("/api/queue/artifact/open-folder")
def queue_artifact_open_folder(body: QueueArtifactFolderOpen):
    """Open the local folder containing a dashboard-safe queue artifact."""
    try:
        artifact = _queue_read_artifact(body.path)
        target = resolve_root_relative(artifact["path"], root=BASE_DIR).parent
        target.relative_to(BASE_DIR.resolve())
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen([opener, str(target)])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="artifact not found")
    except (AosPathError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"local open failed: {exc}")
    return {"success": True, "path": _safe_relative(target), "artifact_path": artifact["path"]}


@app.get("/api/dashboard/cockpit")
def dashboard_cockpit():
    try:
        invocation_attributions = _queue_invocation_attributions()
        items = [_queue_detail_item(item, invocation_attributions) for item in _read_queue_items()]
    except ValueError as exc:
        return {"success": False, "message": "Queue unavailable", "reason": str(exc)}
    counts = {status: 0 for status in _QUEUE_STATUSES}
    for item in items:
        status = item.get("status", "inbox")
        counts[status] = counts.get(status, 0) + 1
    needs_me_statuses = _HUMAN_NEEDED_STATUSES
    needs_me = _queue_human_needed_items(items)
    stalled = _stalled_items(items, 15)
    token_summary = _dashboard_token_summary()
    backup = _backup_status()
    latitude = _public_latitude_status()
    workbenches = []
    for name in ("hermes", "codex", "claude", "claude-code", "antigravity", "connectors", "graphify"):
        tool = next((row for row in token_summary["by_tool"] if row["tool"] == name), None)
        open_items = [item for item in items if str(item.get("owner") or "").lower() in {name, name.replace("-code", "")} and item.get("status") not in {"done", "cancelled"}]
        workbenches.append({
            "id": name,
            "name": name.replace("-", " ").title(),
            "status": "Unavailable" if name in {"antigravity", "graphify"} and not open_items else ("Needs Me" if any(item.get("status") in needs_me_statuses or item.get("needs_me") for item in open_items) else "Ready"),
            "last_task": open_items[0].get("title") if open_items else "No active task",
            "tokens_today": "unavailable" if not tool or tool.get("unavailable") else tool.get("tokens"),
            "unavailable": name in {"antigravity", "graphify"} and not open_items,
        })
    return {
        "success": True,
        "counts": counts,
        "needs_me": needs_me,
        "needs_me_count": len(needs_me),
        "human_needed_count": len(needs_me),
        "human_needed_statuses": sorted(_HUMAN_NEEDED_STATUSES),
        "stalled": stalled,
        "stalled_count": len(stalled),
        "queue_items": items,
        "lane_activity": _dashboard_lane_activity(items),
        "recent_output": _recent_file_items(limit=8),
        "tokens": token_summary,
        "workbenches": workbenches,
        "backup": backup,
        "latitude": latitude,
    }


@app.get("/api/dashboard/tokens")
def dashboard_tokens():
    return _dashboard_token_summary()


class MessageRouteRequest(BaseModel):
    text: str
    source_refs: list[str] = []


def _workflow_contract(workflow_id: str) -> dict:
    path = WORKFLOWS_DIR / workflow_id / "workflow.md"
    if not path.exists():
        return {
            "workflow": workflow_id,
            "path": _safe_relative(path),
            "definition_of_done": "",
            "allowed_actions": [],
            "stop_conditions": [],
            "steps": [],
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    definition = ""
    allowed = []
    stops = []
    steps = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("-").strip()
        if not definition and re.search(r"\bDone\b\s*=", line, re.IGNORECASE):
            definition = re.sub(r"^\*\*Done\*\*\s*=\s*", "", line).strip()
        elif not definition and line.lower().startswith("done ="):
            definition = line.split("=", 1)[1].strip()
        if re.search(r"Allowed unprompted", line, re.IGNORECASE):
            value = re.sub(r"^\*\*Allowed unprompted\*\*\s*=\s*", "", line).strip()
            allowed = [part.strip(" .") for part in re.split(r";|,", value) if part.strip(" .")]
        if re.search(r"Stop conditions", line, re.IGNORECASE):
            value = re.sub(r"^\*\*Stop conditions\*\*\s*=\s*", "", line).strip()
            stops = [part.strip(" .") for part in re.split(r";", value) if part.strip(" .")]
        numbered = re.match(r"^(\d+)\.\s+(.+)", raw.strip())
        if numbered:
            steps.append({"index": int(numbered.group(1)), "text": numbered.group(2).strip()})
    if not allowed:
        allowed = ["local_read", "local_edit", "local_test"]
    if not stops:
        stops = ["external_send", "destructive_action_outside_scope"]
    return {
        "workflow": workflow_id,
        "path": _safe_relative(path),
        "definition_of_done": definition,
        "allowed_actions": allowed,
        "stop_conditions": stops,
        "steps": steps,
    }


def _workflow_title_from_text(workflow_id: str, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip("# ").strip()
        if stripped.lower().startswith("workflow:"):
            return stripped.split(":", 1)[1].strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return workflow_id.replace("_", " ").title()


def _workflow_runner_contract(route: dict) -> dict:
    workflow_id = route.get("workflow") or route.get("id")
    contract = _workflow_contract(workflow_id)
    path = WORKFLOWS_DIR / workflow_id / "workflow.md"
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    steps = contract["steps"] or [{"index": 1, "text": "Run workflow contract from source markdown."}]
    return {
        "workflow_id": workflow_id,
        "name": _workflow_title_from_text(workflow_id, text),
        "route_id": route.get("id"),
        "patterns": route.get("patterns") or [],
        "skill_reference": route.get("skill") or "",
        "owner_lane": route.get("owner") or "unassigned",
        "workbench_profile": route.get("workbench") or "lane",
        "contract_path": contract["path"],
        "ordered_steps": [
            {
                "index": step.get("index", index),
                "text": step.get("text") or "",
                "definition_of_done": contract["definition_of_done"] or "Complete this step and leave a receipt.",
                "token_usage_text": "Token usage: no agent invocation for deterministic contract registration.",
            }
            for index, step in enumerate(steps, start=1)
        ],
        "definition_of_done": contract["definition_of_done"],
        "stop_conditions": contract["stop_conditions"],
        "artifact_expectations": _workflow_artifact_expectations(workflow_id, text),
        "review_gate": "human_review before done; third-party external actions require dry-run gate in WP11.",
        "external_action_policy": "No live third-party send/publish/mutation in WP11.",
    }


def _workflow_artifact_expectations(workflow_id: str, text: str) -> list[str]:
    explicit = []
    for raw in text.splitlines():
        line = raw.strip().strip("-").strip()
        if re.search(r"\b(output/|receipts/|post_package\.json|carousel\.pdf|brief artifact|receipt)\b", line, re.IGNORECASE):
            explicit.append(line)
    if explicit:
        return explicit[:12]
    return [f"Receipt under queue/receipts/ or workflows/{workflow_id}/receipts/ with token usage line."]


def _workflow_runner_contracts() -> dict:
    routes = _load_command_routes().get("routes") or []
    contracts = {
        "version": 1,
        "source": "queue/command_routes.json",
        "runner_consumable": True,
        "contracts": [_workflow_runner_contract(route) for route in routes],
        "token_usage_text": "Token usage: no agent invocation",
    }
    if WORKFLOW_REGISTRY_FILE.exists():
        contracts["registry_path"] = _safe_relative(WORKFLOW_REGISTRY_FILE)
    runner_registry = WORKFLOWS_DIR / "runner_contracts.json"
    if runner_registry.exists():
        contracts["runner_contracts_path"] = _safe_relative(runner_registry)
    return contracts


def _load_command_routes() -> dict:
    path = QUEUE_DIR / "command_routes.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"routes": [], "path": _safe_relative(path)}
    data["path"] = _safe_relative(path)
    return data


def _match_command_route(text: str) -> dict:
    command = str(text or "").lower()
    data = _load_command_routes()
    matches = []
    for route in data.get("routes") or []:
        patterns = route.get("patterns") or []
        hit = next((pattern for pattern in patterns if str(pattern).lower() in command), None)
        if hit:
            matches.append({"route": route, "pattern": hit})
    if not matches:
        return {
            "matched": False,
            "confidence": "unmatched",
            "token_usage_text": "Token usage: no agent invocation",
            "routes_path": data.get("path"),
        }
    chosen = matches[0]["route"]
    workflow = chosen.get("workflow") or chosen.get("id")
    contract = _workflow_contract(workflow)
    return {
        "matched": True,
        "confidence": "exact match" if len(matches) == 1 else "ambiguous",
        "ambiguous_matches": [match["route"].get("workflow") or match["route"].get("id") for match in matches[1:]],
        "pattern": matches[0]["pattern"],
        "route": chosen,
        "work_order": {
            "title": f"{workflow}: {str(text or '').strip()[:90]}",
            "owner": chosen.get("owner") or "unassigned",
            "priority": chosen.get("priority") or "normal",
            "tags": [workflow, chosen.get("skill"), "message_board"],
            "source": "message_board",
            "source_refs": [],
            "context": str(text or "").strip(),
            "allowed_actions": contract["allowed_actions"],
            "stop_conditions": contract["stop_conditions"],
            "definition_of_done": contract["definition_of_done"],
            "workbench": chosen.get("workbench"),
            "workflow": workflow,
            "steps": contract["steps"],
            "contract_path": contract["path"],
        },
        "token_usage_text": "Token usage: no agent invocation",
        "routes_path": data.get("path"),
    }


def _cockpit_command_title(text: str) -> str:
    """Keep verbose instructions intact in context without making them a garbled title."""
    compact = " ".join(text.split())
    if len(text) <= 120 and "\n" not in text:
        return compact

    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    title = aos_orchestration.operator_task_title({"title": first_line or compact, "context": text})
    if len(title) > 120:
        return f"{title[:117].rstrip()}..."
    return title


def _cockpit_command_needs_summary(text: str) -> bool:
    return "\n" in text or len(text) > 120


def _create_cockpit_command_item(command: str) -> tuple[dict, dict]:
    """Route one plain-language command into the local queue without running it."""
    text = str(command or "").strip()
    if not text:
        raise ValueError("command must not be empty")
    if len(text) > 2000:
        raise ValueError("command must be 2000 characters or fewer")

    routing = _match_command_route(text)
    work_order = routing.get("work_order") if routing.get("matched") else None
    if work_order:
        tags = [str(value) for value in work_order.get("tags") or [] if value]
        tags.extend(("cockpit_command", f"lane:{work_order.get('owner') or 'unassigned'}"))
        title = str(work_order.get("title") or text)
        if _cockpit_command_needs_summary(text):
            workflow = str(work_order.get("workflow") or "").strip()
            title = f"{workflow}: {_cockpit_command_title(text)}" if workflow else _cockpit_command_title(text)
        if len(title) > 200:
            title = f"{title[:197].rstrip()}..."
        body = QueueItemCreate(
            title=title,
            owner=str(work_order.get("owner") or "unassigned"),
            priority=work_order.get("priority") or "normal",
            tags=",".join(tags),
            source="dashboard/cockpit_command",
            context=text,
            source_refs=",".join(str(value) for value in work_order.get("source_refs") or []),
            allowed_actions=",".join(str(value) for value in work_order.get("allowed_actions") or []),
            stop_conditions=",".join(str(value) for value in work_order.get("stop_conditions") or []),
            definition_of_done=str(work_order.get("definition_of_done") or ""),
            workbench=work_order.get("workbench"),
            step_index=0 if work_order.get("steps") else None,
        )
        route_summary = {
            "matched": True,
            "confidence": routing.get("confidence"),
            "workflow": work_order.get("workflow"),
            "owner": work_order.get("owner"),
            "pattern": routing.get("pattern"),
        }
    else:
        inferred_owner = _infer_queue_owner(text)
        owner = inferred_owner if inferred_owner != "unassigned" else "hermes"
        workbench = owner if owner in {"codex", "claude"} else "lane"
        body = QueueItemCreate(
            title=_cockpit_command_title(text),
            owner=owner,
            priority="normal",
            tags=f"cockpit_command,intake:unmatched,lane:{owner if owner in _DASHBOARD_LANES else 'unassigned'}",
            source="dashboard/cockpit_command",
            context=text,
            definition_of_done="Triage the operator command, complete the routed work, and attach a durable receipt.",
            workbench=workbench,
        )
        route_summary = {
            "matched": False,
            "confidence": "fallback",
            "workflow": None,
            "owner": owner,
            "pattern": None,
        }

    return _queue_create_dashboard_item(body), route_summary


@app.get("/api/dashboard/command-routes")
def dashboard_command_routes():
    return _load_command_routes()


@app.post("/api/dashboard/message-board/route")
def dashboard_message_board_route(body: MessageRouteRequest):
    result = _match_command_route(body.text)
    if result.get("work_order") is not None:
        result["work_order"]["source_refs"] = list(body.source_refs or [])
    latitude_telemetry.trace(
        "message_board.route",
        "message_board",
        "matched" if result.get("matched") else "unmatched",
        matched=bool(result.get("matched")),
        confidence=result.get("confidence"),
    )
    return result


@app.post("/api/dashboard/cockpit/command")
def dashboard_cockpit_command(body: CockpitCommandCreate):
    """Create one deterministically routed local work item; never invoke a model or connector."""
    try:
        item, route = _create_cockpit_command_item(body.command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    latitude_telemetry.trace(
        "cockpit.command_create",
        "queue",
        "ok",
        item_id=item.get("id"),
        owner=item.get("owner"),
        matched=route.get("matched"),
    )
    return {
        "success": True,
        "item": _queue_detail_item(item),
        "route": route,
        "local_only": True,
        "token_usage_text": "Token usage: no agent invocation",
    }


@app.post("/api/dashboard/capture")
def dashboard_capture(body: CockpitCaptureCreate):
    """Append one raw note to the canonical Brain inbox; never create queue work."""
    try:
        capture = business_brain_inbox.capture_text(
            body.text,
            source="cockpit_capture",
            capture_id=body.capture_id,
            root=business_brain.BUSINESS_BRAIN_ROOT,
        )
    except business_brain_inbox.InboxCaptureError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "success": True,
        "capture_id": capture.capture_id,
        "pointer": capture.pointer,
        "duplicate": capture.duplicate,
        "queue_item_created": False,
        "promoted": False,
        "token_usage_text": "Token usage: no agent invocation",
    }


def _component_tokens(component: str, records: list[dict]) -> dict:
    total = 0
    estimated = 0
    unavailable = 0
    rows = []
    aliases = {component}
    if component == "operations":
        aliases.add("ops")
    if component == "claude":
        aliases.add("claude-code")
    for record in records:
        record_component = _ledger_component(record)
        lane = str(record.get("lane") or "")
        if record_component not in aliases and lane not in aliases:
            continue
        tokens, basis = _ledger_tokens_basis(record)
        rows.append({"task_id": _ledger_task_id(record), "tokens": tokens, "basis": basis, "ts": _ledger_timestamp(record)})
        if tokens is None:
            unavailable += 1
        else:
            total += tokens
            estimated += int(basis == "estimate")
    return {"tokens": total, "estimated": estimated, "unavailable": unavailable, "rows": rows[-20:]}


def _receipt_owner_match(path: Path, component: str) -> bool:
    name = path.name.lower()
    return component.lower() in name


@app.get("/api/dashboard/agents")
def dashboard_agents():
    items = [_queue_detail_item(item) for item in _read_queue_items()]
    token_records = _read_token_ledger_records()
    components = [
        {"id": "hermes", "name": "Hermes", "group": "orchestrator", "owner_filter": {"hermes", "orchestrator"}, "workbench_filter": set()},
        {"id": "revenue", "name": "Revenue", "group": "lane", "owner_filter": {"revenue"}, "workbench_filter": set()},
        {"id": "marketing", "name": "Marketing", "group": "lane", "owner_filter": {"marketing"}, "workbench_filter": set()},
        {"id": "delivery", "name": "Delivery", "group": "lane", "owner_filter": {"delivery"}, "workbench_filter": set()},
        {"id": "operations", "name": "Operations", "group": "lane", "owner_filter": {"operations", "ops"}, "workbench_filter": set()},
        {"id": "codex", "name": "Codex", "group": "executor", "owner_filter": {"codex"}, "workbench_filter": {"codex"}},
        {"id": "claude", "name": "Claude Code", "group": "executor", "owner_filter": {"claude"}, "workbench_filter": {"claude", "claude-code"}},
        {"id": "antigravity", "name": "Antigravity", "group": "executor", "owner_filter": {"antigravity"}, "workbench_filter": {"antigravity"}},
        {"id": "composio", "name": "Composio", "group": "connector", "owner_filter": set(), "workbench_filter": set(), "status_text": "Read-only status only in Phase A."},
        {"id": "agentmail", "name": "AgentMail", "group": "connector", "owner_filter": set(), "workbench_filter": set(), "status_text": "Read-only status only in Phase A."},
    ]
    receipt_paths = sorted((QUEUE_DIR / "receipts").glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) if (QUEUE_DIR / "receipts").exists() else []
    cards = []
    for component in components:
        owner_filter = component["owner_filter"]
        workbench_filter = component["workbench_filter"]
        filtered = [
            item for item in items
            if str(item.get("owner") or "").lower() in owner_filter
            or str(item.get("workbench") or "").lower() in workbench_filter
        ]
        counts = {
            "queued": sum(1 for item in filtered if item.get("status") in {"inbox", "agent_todo"}),
            "running": sum(1 for item in filtered if item.get("status") in {"agent_working"}),
            "done": sum(1 for item in filtered if item.get("status") == "done"),
        }
        cards.append({
            "id": component["id"],
            "name": component["name"],
            "group": component["group"],
            "status_text": component.get("status_text") or "Local queue and receipt view.",
            "counts": counts,
            "items": filtered[:80],
            "receipts": [{"path": _safe_relative(path), "modified": datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc).isoformat().replace("+00:00", "Z")} for path in receipt_paths if _receipt_owner_match(path, component["id"])][:20],
            "tokens": _component_tokens(component["id"], token_records),
        })
    return {"components": cards}


def _workflow_steps_for_item(item: dict) -> list[dict]:
    workflow = None
    for tag in item.get("tags") or []:
        candidate = WORKFLOWS_DIR / str(tag) / "workflow.md"
        if candidate.exists():
            workflow = str(tag)
            break
    if not workflow:
        return []
    return _workflow_contract(workflow).get("steps") or []


def _honest_status(item: dict) -> str:
    status = str(item.get("status") or "")
    if status == "inbox":
        return "queued"
    if status == "agent_todo":
        return "claimed" if (item.get("claim") or {}).get("claimed_by") else "queued"
    if status == "agent_working":
        return "running"
    if status in {"needs_input", "human_review", "blocked", "done"}:
        return status
    return status or "queued"


def _stalled_items(items: list[dict], minutes: int = 15) -> list[dict]:
    now = datetime.datetime.now(datetime.timezone.utc)
    stalled = []
    for item in items:
        if item.get("status") not in {"agent_todo", "agent_working"}:
            continue
        timestamp = _parse_record_timestamp(item.get("updated_at") or item.get("created_at"))
        if not timestamp:
            continue
        age_seconds = (now - timestamp.astimezone(datetime.timezone.utc)).total_seconds()
        if age_seconds >= minutes * 60:
            stalled.append({**item, "stalled_minutes": round(age_seconds / 60)})
    return stalled


def _dashboard_schedule_rows(backup: dict, checked_at: str) -> list[dict]:
    digest_records = []
    for path in (QUEUE_DIR / "receipts").glob("agentmail_digest_*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            digest_records.append((str(_ledger_timestamp(value) or value.get("digest_date") or ""), path, value))
    digest_records.sort(key=lambda row: row[0], reverse=True)
    ingestion = _read_jsonl_file(QUEUE_DIR / "receipts" / "ingestion.jsonl")
    ingestion.sort(key=lambda row: str(_ledger_timestamp(row) or ""), reverse=True)
    latest_digest = digest_records[0] if digest_records else None
    latest_ingestion = ingestion[0] if ingestion else None
    latest_backup = backup.get("latest") or {}
    return [
        {
            "id": "automated-backup",
            "name": "Automated backup",
            "next_run": "unknown",
            "last_run": latest_backup.get("ts"),
            "last_result": latest_backup.get("status") or "unavailable",
            "receipt": backup.get("latest_receipt_path"),
            "degraded": bool(backup.get("needs_attention")),
            "stale": backup.get("state") == "stale",
            "expected_cadence": "48 hours (existing backup status contract)",
        },
        {
            "id": "system-watch",
            "name": "System Watch",
            "next_run": "unknown",
            "last_run": checked_at,
            "last_result": "read-only check available",
            "receipt": None,
            "degraded": False,
            "stale": False,
            "expected_cadence": "unknown",
        },
        {
            "id": "agentmail-digest",
            "name": "AgentMail digest",
            "next_run": "unknown",
            "last_run": latest_digest[0] if latest_digest else None,
            "last_result": str((latest_digest[2] if latest_digest else {}).get("status") or "unavailable"),
            "receipt": _safe_relative(latest_digest[1]) if latest_digest else None,
            "degraded": latest_digest is None,
            "stale": False,
            "expected_cadence": "unknown",
        },
        {
            "id": "ingestion",
            "name": "Ingestion",
            "next_run": "unknown",
            "last_run": _ledger_timestamp(latest_ingestion or {}),
            "last_result": str((latest_ingestion or {}).get("status") or "unavailable"),
            "receipt": "queue/receipts/ingestion.jsonl" if ingestion else None,
            "degraded": latest_ingestion is None,
            "stale": False,
            "expected_cadence": "unknown",
        },
    ]


@app.get("/api/dashboard/system-watch")
def dashboard_system_watch(stalled_minutes: int = 15):
    items = [_queue_detail_item(item) for item in _read_queue_items()]
    stalled = _stalled_items(items, stalled_minutes)
    human_needed = _queue_human_needed_items(items)
    log_path = LOGS_DIR / "dashboard_backend.log"
    tail = []
    if log_path.exists():
        tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
    queue_tool_exists = QUEUE_TOOL.exists()
    backup = _backup_status()
    latitude = _public_latitude_status()
    checked_at = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "backend": {"status": "ok", "checked_at": checked_at},
        "queue_tooling": {"status": "ok" if queue_tool_exists else "missing", "path": _safe_relative(QUEUE_TOOL)},
        "bridge_status": {"status": "read-only check available outside this Phase A endpoint", "freshness": "not mutated"},
        "stalled_window_minutes": stalled_minutes,
        "stalled": stalled,
        "stalled_count": len(stalled),
        "error_log_tail": tail,
        "needs_me": [
            {"id": item["id"], "title": item["title"], "reason": item["status"], "status": item["status"]}
            for item in human_needed
        ],
        "needs_me_count": len(human_needed),
        "stalled_needs_attention": [
            {"id": item["id"], "title": item["title"], "reason": "stalled run", "status": item["status"], "stalled_minutes": item["stalled_minutes"]}
            for item in stalled
        ],
        "backup": backup,
        "schedule": _dashboard_schedule_rows(backup, checked_at),
        "schedule_read_only": True,
        "backup_needs_attention": backup.get("needs_attention", False),
        "latitude": latitude,
        "latitude_needs_attention": not latitude.get("configured"),
    }


@app.get("/api/dashboard/latitude/status")
def dashboard_latitude_status():
    return _public_latitude_status()


@app.post("/api/dashboard/latitude/heartbeat")
def dashboard_latitude_heartbeat():
    return latitude_telemetry.heartbeat()


@app.get("/api/latitude/status")
def latitude_status():
    return _public_latitude_status()


@app.post("/api/latitude/heartbeat")
def latitude_heartbeat():
    return latitude_telemetry.heartbeat()


@app.post("/api/agentmail/daily-digest")
def agentmail_daily_digest(body: AgentMailDigestRequest):
    try:
        digest_date = None
        if body.digest_date:
            digest_date = datetime.date.fromisoformat(body.digest_date)
        return _agentmail_digest_attempt(digest_date, body.recipient, send=bool(body.send), dry_run=bool(body.dry_run))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/external-actions/dry-run")
def external_action_dry_run(body: ExternalSendDryRun):
    try:
        result = _write_external_dry_run_receipt(body)
        latitude_telemetry.trace("third_party.dry_run_gate", "external_action_gate", "ok", item_id=body.item_id, action=body.action, dry_run=True, transmitted=False)
        return result
    except ValueError as exc:
        latitude_telemetry.trace("third_party.dry_run_gate", "external_action_gate", "blocked", item_id=body.item_id, action=body.action, dry_run=True, transmitted=False)
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/dashboard/results")
def dashboard_results():
    recent = _recent_file_items()
    return {"items": recent[:200], "activity": _dashboard_activity_feed(recent)[:200], "read_only": True, "token_usage_text": "Token usage: no agent invocation"}


@app.get("/api/dashboard/workflows")
def dashboard_workflows():
    workflows = []
    root = _workflow_root()
    registry = _workflow_registry_entries()
    registry_by_id = {str(row.get("id")): row for row in registry if row.get("id")}
    candidates: dict[str, tuple[Path, dict]] = {
        path.parent.name: (path, registry_by_id.get(path.parent.name, {}))
        for path in sorted(root.glob("*/workflow.md")) if root.exists()
    }
    fixture_root = BASE_DIR / "dashboard" / "test-fixtures" / "workflows"
    if fixture_root.exists():
        for path in sorted(fixture_root.glob("*/workflow.md")):
            candidates.setdefault(path.parent.name, (path, {"test_fixture": True}))
    for row in registry:
        slug = str(row.get("id") or "").strip()
        source = str(row.get("source_path") or "").strip().replace("\\", "/")
        if not slug or slug in candidates or not source.startswith("workflows/"):
            continue
        path = BASE_DIR / source
        candidates[slug] = (path, row)
    for slug in sorted(candidates):
        path, metadata = candidates[slug]
        try:
            content = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError):
            continue
        lane = str(metadata.get("owner_agent") or "").lower() or ("operations" if any(part in slug for part in ("ops", "weekly", "ai_operations")) else "marketing" if "marketing" in slug or "content" in slug else "revenue" if any(part in slug for part in ("lead", "sales", "fit")) else "delivery")
        receipts_dir = path.parent / "receipts"
        receipts = sorted(receipts_dir.glob("*")) if receipts_dir.exists() else []
        editable = False
        read_only_reason = "Only canonical workflows/*/workflow.md sources are editable."
        try:
            editable = _workflow_path_for_id(slug) == path
            if editable:
                read_only_reason = ""
        except (ValueError, FileNotFoundError, OSError):
            pass
        workflows.append({
            "id": slug,
            "identifier": slug,
            "name": _workflow_display_name(path, content, slug, metadata),
            "lane": lane,
            "path": _safe_relative(path),
            "last_run": datetime.datetime.fromtimestamp(receipts[-1].stat().st_mtime).isoformat() if receipts else None,
            "receipt_count": len(receipts),
            "avg_tokens": "unavailable",
            "content": _redacted_preview(content, 6000),
            "editable": editable,
            "test_fixture": bool(metadata.get("test_fixture")),
            "read_only_reason": read_only_reason,
            "revision": _workflow_revision(content),
        })
    return {"workflows": workflows}


@app.get("/api/dashboard/workflows/{workflow_id}")
def dashboard_workflow(workflow_id: str):
    try:
        path = _workflow_path_for_id(workflow_id)
        content = path.read_text(encoding="utf-8", errors="strict")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="editable workflow source not found")
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "success": True,
        "id": workflow_id,
        "name": _workflow_display_name(path, content, workflow_id),
        "path": _safe_relative(path),
        "content": content,
        "revision": _workflow_revision(content),
        "editable": True,
    }


@app.post("/api/dashboard/workflows/save")
def dashboard_save_workflow(body: DashboardWorkflowSave):
    try:
        path = _workflow_path_for_id(body.workflow_id, writable=True)
        existing = path.read_text(encoding="utf-8", errors="strict")
        if not body.expected_revision or body.expected_revision != _workflow_revision(existing):
            raise RuntimeError("workflow changed after it was loaded; reload before saving")
        _validate_workflow_content(body.content)
        durable_replace_text(path, body.content)
        persisted = path.read_text(encoding="utf-8", errors="strict")
        if persisted != body.content:
            raise OSError("workflow save verification failed")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="editable workflow source not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"workflow save failed: {exc}")
    return {
        "success": True,
        "id": body.workflow_id,
        "name": _workflow_display_name(path, persisted, body.workflow_id),
        "path": _safe_relative(path),
        "content": persisted,
        "revision": _workflow_revision(persisted),
        "executed": False,
    }


@app.get("/api/dashboard/workflow-contracts")
def dashboard_workflow_contracts():
    return _workflow_runner_contracts()


@app.get("/api/dashboard/skills")
def dashboard_skills():
    trust = _read_jsonl_file(SKILL_TRUST_FILE)
    by_skill: dict[str, dict] = {}
    for row in trust:
        slug = str(row.get("skill") or "").replace("-", "_")
        if not slug:
            continue
        entry = by_skill.setdefault(slug, {"uses": 0, "real_uses": 0, "last_used": None, "rows": []})
        entry["rows"].append(row)
        entry["uses"] += 1
        entry["real_uses"] += int(bool(row.get("real_use")))
        date = row.get("date")
        if date and (entry["last_used"] is None or str(date) > str(entry["last_used"])):
            entry["last_used"] = date
    skills = []
    if SKILLS_DIR.exists():
        for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            slug = path.parent.name
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            parsed = _parse_markdown_frontmatter(content)
            metadata = parsed["frontmatter"]
            body = parsed["body"]
            trust_entry = by_skill.get(slug, {"uses": 0, "real_uses": 0, "last_used": None, "rows": []})
            core_offer = slug in {"build_speed_to_lead", "build_voice_agent", "build_client_memory", "build_lead_gen_agent"}
            real_uses = trust_entry["real_uses"]
            state = "v0" if core_offer and real_uses < 3 else "earned" if real_uses >= 3 else "earning" if real_uses else "v0"
            name = _frontmatter_text_value(metadata, "name", slug.replace("_", " ").title())
            description = _frontmatter_text_value(metadata, "description")
            lane = _skill_lane_from_metadata(metadata, trust_entry["rows"][-1].get("lane") if trust_entry["rows"] else "delivery")
            skills.append({
                "id": slug,
                "name": name,
                "title": name,
                "description": description,
                "lane": lane,
                "state": state,
                "status": _frontmatter_text_value(metadata, "status", state),
                "source": _frontmatter_text_value(metadata, "source"),
                "trust": _skill_trust_from_metadata(metadata),
                "version": _frontmatter_text_value(metadata, "version"),
                "metadata": {key: metadata.get(key) for key in ("name", "description", "lane", "status", "source", "trust", "version") if key in metadata},
                "uses": trust_entry["uses"],
                "real_uses": real_uses,
                "last_used": trust_entry["last_used"],
                "avg_tokens": "unavailable",
                "core_offer": core_offer,
                "path": _safe_relative(path),
                "body": _redacted_preview(body, 20000),
                "content": _redacted_preview(body, 6000),
                "preview": _redacted_preview(body, 1200),
            })
    return {"skills": skills}


@app.post("/api/dashboard/skills/save")
def dashboard_save_skill(body: DashboardSkillSave):
    try:
        path = _safe_dashboard_markdown_path(body.path, require_writable=True)
        existing = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        parsed = _parse_markdown_frontmatter(existing)
        existing_name = _frontmatter_text_value(parsed["frontmatter"], "name", path.parent.name)
        name = body.name.strip() or existing_name
        description = body.description.strip()
        if not name:
            raise ValueError("name must not be empty")
        durable_replace_text(path, _render_markdown_frontmatter(parsed["frontmatter_lines"], name, description, body.body))
        updated = path.read_text(encoding="utf-8", errors="replace")
        updated_parsed = _parse_markdown_frontmatter(updated)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="skill file not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "success": True,
        "path": _safe_relative(path),
        "name": _frontmatter_text_value(updated_parsed["frontmatter"], "name", name),
        "description": _frontmatter_text_value(updated_parsed["frontmatter"], "description", description),
        "body": _redacted_preview(updated_parsed["body"], 20000),
    }


@app.post("/api/dashboard/open-path")
def dashboard_open_path(body: DashboardOpenPath):
    try:
        path = _safe_dashboard_markdown_path(body.path)
        target = path.parent if body.kind == "folder" else path
        if not target.exists():
            raise FileNotFoundError(str(target))
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen([opener, str(target)])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="path not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"local open failed: {exc}")
    return {"success": True, "path": _safe_relative(target)}


@app.get("/api/dashboard/memory")
def dashboard_memory():
    root_pointer = "business_brain:README.md"
    try:
        registry = business_brain_scope.load_registry()
        root_resolution = registry.resolve_brain_pointer("global", root_pointer)
        loader = business_brain_context.ScopedBrainLoader(registry=registry)
    except (business_brain.BusinessBrainPointerError, business_brain_scope.ClientScopeError) as exc:
        return {
            "brain": {
                "available": False,
                "root": root_pointer,
                "file_count": 0,
                "blocked_path_count": 0,
                "error": str(exc),
            },
            "files": [],
            "promotion_queue": [],
            "promotion_state": {
                "mode": "unavailable",
                "available": False,
                "reference_count": 0,
                "reason": "Promotion evaluation and writing are not active in Block 1.",
            },
        }
    vault = root_resolution.resolved_path.parent
    files = []
    backup_root = vault / "_backups"
    blocked = sum(1 for path in backup_root.rglob("*.md") if path.is_file()) if backup_root.is_dir() else 0
    context_used = []
    for pointer in registry.permitted_brain_pointers("global"):
        try:
            retrieved = loader.retrieve(work={"client_scope": "global"}, pointers=[pointer])
            read = retrieved.reads[0]
            path = registry.resolve_brain_pointer("global", pointer).resolved_path
            content = read.content
            frontmatter, body = aos_indexer.parse_frontmatter(content)
            files.append({
                "id": frontmatter.get("id"),
                "type": frontmatter.get("type"),
                "path": pointer,
                "title": _markdown_title(body, path.name),
                "modified": datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "preview": _redacted_preview(content, 3000),
                "revisit": next((line.strip() for line in content.splitlines() if "Revisit:" in line), ""),
            })
            context_used.extend(retrieved.brain_context_used)
        except (OSError, business_brain.BusinessBrainPointerError, business_brain_scope.ClientScopeError, business_brain_context.BrainContextError):
            continue
    files.sort(key=lambda item: item["modified"], reverse=True)
    promotion_references = []
    for record in _read_jsonl_file(BASE_DIR / "queue" / "run_ledger.jsonl"):
        values = record.get("memory_promotion")
        if isinstance(values, list):
            promotion_references.extend(str(value) for value in values if str(value).strip())
    promotion_receipts = []
    for path in sorted((BASE_DIR / "queue" / "receipts").glob("brain-promotion-*.json"), reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if record.get("status") == "success":
            promotion_receipts.append({
                "receipt": _safe_relative(path),
                "write_id": record.get("write_id"),
                "target": record.get("target"),
                "completed_at": record.get("completed_at"),
            })
    return {
        "brain": {
            "available": True,
            "root": root_pointer,
            "index": "business_brain:index/MEMORY_INDEX.md",
            "file_count": len(files),
            "blocked_path_count": blocked,
            "denied_pointer_count": len(registry.data.get("denied_brain_pointers") or []),
        },
        "files": files[:50],
        "brain_context_used": context_used,
        "promotion_queue": [],
        "promotion_state": {
            "mode": "operational",
            "available": True,
            "automatic_classes": ["generated_marker_section"],
            "review_route": "human_review",
            "reference_count": len(promotion_references) + len(promotion_receipts),
            "references": promotion_references[:20],
            "latest_safe_promotion": promotion_receipts[0] if promotion_receipts else None,
            "reason": "Scope-gated promotion machinery is available; queue titles and tags are never promotion state.",
        },
    }


@app.get("/api/dashboard/prompts")
def dashboard_prompts():
    prompts = []
    for root in PROMPT_LIBRARY_DIRS:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.md")):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            prompts.append({
                "id": _safe_relative(path),
                "title": _markdown_title(content, path.stem.replace("_", " ").title()),
                "category": path.parent.name,
                "target": "Hermes" if "hermes" in path.name else "Codex" if "codex" in path.name else "Claude" if "claude" in path.name else "Workbench",
                "path": _safe_relative(path),
                "content": _redacted_preview(content, 8000),
            })
    return {"prompts": prompts}


@app.get("/api/dashboard/graphify")
def dashboard_graphify():
    cli_path = shutil.which("graphify") or "/home/liam/.local/bin/graphify"
    repositories = GRAPHIFY_SERVICE.list_repositories()
    return {
        "available": Path(cli_path).is_file(),
        "installed": Path(cli_path).is_file(),
        "status": f"{len(repositories)} repository graph{'s' if len(repositories) != 1 else ''} available",
        "cli_path": cli_path,
        "version": GRAPHIFY_SERVICE._graphify_version(),
        "brain_root": str(GRAPHIFY_BRAIN_DIR),
        "graph_output_dir": str(GRAPHIFY_OUT_DIR),
        "data_inspected": True,
        "repos": repositories,
        "model_invoked": False,
        "token_usage_text": "Token usage: no agent invocation",
    }


@app.get("/api/dashboard/repo-ingest")
def dashboard_repo_ingest():
    return {
        "available": True,
        "steps": ["Fetch", "Quarantine scan", "Code-only Graphify", "Validate + publish", "Available"],
        "repos": GRAPHIFY_SERVICE.list_repositories(),
        "note": "All ingest steps are deterministic and model-free. Existing repositories require the explicit repository-specific Re-fetch action.",
        "canonical_roots": {"clones": str(GRAPHIFY_CLONE_DIR), "outputs": str(GRAPHIFY_OUT_DIR), "receipts": str(GRAPHIFY_RECEIPTS_DIR)},
        "model_invoked": False,
        "token_usage_text": "Token usage: no agent invocation",
    }


def _graphify_http_error(exc: GraphifyError) -> HTTPException:
    detail = str(exc)
    status = 409 if "already exists" in detail or "requires an existing" in detail else 400
    return HTTPException(status_code=status, detail=detail)


@app.post("/api/graphify/fetch")
def graphify_fetch(body: GraphifyFetchRequest):
    """Explicit deterministic fetch. URL validation itself never clones or invokes a model."""
    try:
        validate_github_url(body.url)
        return {"success": True, "repository": GRAPHIFY_SERVICE.ingest(body.url, refetch=False), "model_invoked": False}
    except GraphifyError as exc:
        raise _graphify_http_error(exc) from exc


@app.post("/api/graphify/refetch")
def graphify_refetch(body: GraphifyFetchRequest):
    """Explicit repository-specific replacement fetch with atomic publication."""
    try:
        validate_github_url(body.url)
        return {"success": True, "repository": GRAPHIFY_SERVICE.ingest(body.url, refetch=True), "model_invoked": False}
    except GraphifyError as exc:
        raise _graphify_http_error(exc) from exc


@app.post("/api/graphify/rebuild")
def graphify_rebuild(body: GraphifyRepositoryRequest):
    try:
        return {"success": True, "repository": GRAPHIFY_SERVICE.rebuild(body.owner, body.repository), "model_invoked": False}
    except GraphifyError as exc:
        raise _graphify_http_error(exc) from exc


@app.post("/api/graphify/action")
def graphify_action(body: GraphifyActionRequest):
    """Run only installed deterministic Graphify query/explain/affected/path commands."""
    try:
        return {"success": True, **GRAPHIFY_SERVICE.action(body.owner, body.repository, body.action, body.inputs)}
    except (GraphifyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/graphify/queue-model-work")
def graphify_queue_model_work(body: GraphifyQueueRequest):
    """Create a normal queue item; never launch a model from the Graphify page."""
    requested = body.requested_work.strip().lower()
    work = {
        "semantic-extraction": "Run a reviewed semantic extraction over this repository graph",
        "community-naming": "Name Graphify communities with reviewed model assistance",
        "implementation-context": "Prepare implementation context from deterministic Graphify artifacts",
    }
    if requested not in work:
        raise HTTPException(status_code=400, detail="unsupported model-assisted work request")
    try:
        repository = GRAPHIFY_SERVICE.repository(RepoIdentity(body.owner, body.repository))
        item = _queue_create_dashboard_item(QueueItemCreate(
            title=f"⚡ {work[requested]} — {repository['id']}",
            owner="hermes",
            priority="normal",
            tags=f"graphify,model-assisted,{requested}",
            source="dashboard/graphify",
            context="\n".join([
                f"Repository identity: {repository['id']}",
                f"Canonical URL: {repository['canonical_url']}",
                f"Requested work: {work[requested]}",
                "Relevant Graphify artifact paths:",
                *[f"- {value}" for value in repository["paths"].values() if value],
                "This queue creation does not run a model. Work begins only through the existing Open Engine/Work Queue flow.",
            ]),
            sources=",".join(value for value in repository["paths"].values() if value),
            source_refs=",".join(value for value in repository["paths"].values() if value),
            definition_of_done=f"{work[requested]} is produced with repository identity, cited Graphify paths, review evidence, receipt, and exact-or-unavailable token usage.",
            allowed_actions="local_read,local_graph_query,create_local_artifact,model_invocation_through_open_engine",
            stop_conditions="repository_identity_mismatch,missing_graph_artifact,external_write,secrets_exposure,destructive_action_outside_scope",
            workbench="local",
        ))
    except (GraphifyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "item": _queue_detail_item(item), "model_started": False, "queue_item_only": True}


@app.get("/api/graphify/artifacts/{owner}/{repository}/{artifact_path:path}")
def graphify_artifact(owner: str, repository: str, artifact_path: str):
    """Serve only approved, provenance-bound regular files below repo_graphs."""
    try:
        path, media_type = GRAPHIFY_SERVICE.artifact(owner, repository, artifact_path)
        content = path.read_bytes()
    except (GraphifyError, OSError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Cache-Control": "no-store",
    }
    if media_type.startswith("text/html"):
        headers["Content-Security-Policy"] = GRAPH_CSP
    if media_type == "application/json" and path.name == "graph.json":
        headers["Content-Disposition"] = f'attachment; filename="{path.name}"'
    return Response(content=content, media_type=media_type, headers=headers)


@app.post("/api/dashboard/create-task")
def dashboard_create_task(body: DashboardTaskCreate):
    try:
        item = _queue_create_dashboard_item(QueueItemCreate(
            title=body.title,
            owner=body.owner,
            priority=body.priority,
            tags=body.tags,
            source="dashboard",
            context=body.context,
            sources=body.sources,
            source_refs="",
            definition_of_done=body.definition_of_done,
            allowed_actions=body.allowed_actions,
            stop_conditions=body.stop_conditions,
        ))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"success": True, "item": _queue_detail_item(item)}


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
        f'export AOS_ROOT="${{AOS_ROOT:-$PWD}}"; cd "$AOS_ROOT"; command -v codex; codex --version; python3 tools/aos-queue.py codex-run {item.get("id", "")} --prompt-file -'
        if target == "codex"
        else 'export AOS_ROOT="${AOS_ROOT:-$PWD}"; cd "$AOS_ROOT"; aos-claude'
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
        "## Launch from Linux",
        "",
        'export AOS_ROOT="${AOS_ROOT:-$PWD}"; cd "$AOS_ROOT"',
        "",
        launch,
        "",
        "## Manual Launch",
        "",
        "Do not launch agents automatically. For Codex, pass this prompt on standard input to the command above; the explicit work-item ID is retained through process exit and token reconciliation.",
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
        "Summary for operator:",
        "- 1–2 sentences covering what changed, what approval does, and whether anything is sent externally",
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
        "",
        "Tool-output bounds:",
        "- Read files by relevant line range whenever possible.",
        "- For passing tests, retain only the tail summary; preserve detailed output only while investigating a failure.",
        "- Never dump work_items.jsonl, ledgers, receipt directories, complete queue history, or similarly large runtime collections into the model session.",
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
    max_attempts: int = 2,
    prior_worker_result: dict | None = None,
) -> str:
    if revision_instructions and owner == "codex":
        return _queue_codex_correction_prompt(
            item, revision_instructions, attempt, max_attempts, prior_worker_result or {},
        )
    run_prompt_path = str(item.get("run_prompt_path") or "").strip()
    if run_prompt_path:
        if not re.fullmatch(r"queue/run_prompts/[A-Za-z0-9_.-]+\.md", run_prompt_path):
            raise ValueError("invalid run_prompt_path")
        item = {**item, "context": (BASE_DIR / run_prompt_path).read_text(encoding="utf-8")}
    if owner in DEPARTMENT_PROMPT_TARGETS:
        return _queue_actual_department_run_prompt(item, owner, attempt, revision_instructions)
    prompt = _queue_render_prompt(item, owner)
    for marker in ("## Launch from Linux", "## Manual Launch", "## Manual launch"):
        if marker in prompt:
            prompt = prompt.split(marker, 1)[0].rstrip()
    prompt = "\n\n".join((
        prompt.rstrip(),
        f"Current attempt: {attempt}/{max_attempts}",
        "Required artifact/receipt shape:",
        _queue_required_receipt_shape(),
        f"Required local artifact path: {_queue_default_artifact_path(item)}",
        "If this task produces business output, write the durable output to that path and list it under Artifacts.",
        "Tool-output bounds:\n- Read files by relevant line range whenever possible.\n- For passing tests, retain only the tail summary; preserve detailed output only while investigating a failure.\n- Never dump work_items.jsonl, ledgers, receipt directories, complete queue history, or similarly large runtime collections into the model session.",
    ))
    if revision_instructions:
        prompt = "\n\n".join((
            prompt.rstrip(),
            "## Hermes Revision Instructions",
            revision_instructions.strip(),
            "Revise only what is needed to satisfy the queue item, stop conditions, and definition of done.",
        ))
    return prompt.rstrip() + "\n"


def _queue_codex_correction_prompt(
    item: dict,
    hermes_feedback: str,
    attempt: int,
    max_attempts: int,
    prior_worker_result: dict,
) -> str:
    """Build a fresh compact correction work order without orchestration replay."""
    context = str(item.get("context") or "No additional context provided.").strip()
    run_prompt_path = str(item.get("run_prompt_path") or "").strip()
    if run_prompt_path:
        context = f"Original bounded task is stored at `{run_prompt_path}`; inspect only relevant sections."
    elif len(context) > 8_000:
        context = context[:8_000].rstrip() + "\n[original context bounded at 8,000 characters]"
    verified = _queue_verified_artifacts_from_worker_result(item, prior_worker_result)
    paths = [str(row.get("path") or "") for row in verified if row.get("available")]
    paths.extend(str(path) for path in prior_worker_result.get("stream_artifacts") or [])
    diagnostic = str(prior_worker_result.get("diagnostic_log") or "").strip()
    if diagnostic:
        paths.append(diagnostic)
    artifact_paths = _queue_unique_artifact_paths(paths)
    prior_summary = _queue_result_summary(prior_worker_result, 1_600)
    repository_refs: list[str] = []
    for field in (item.get("sources"), item.get("source_refs")):
        repository_refs.extend(str(value) for value in (field if isinstance(field, list) else _queue_split_text(field)))
    return "\n".join((
        PERMISSION_HEADER,
        "",
        "## Fresh compact correction work order",
        "",
        "Start a new independently scoped Codex session. Do not resume or inherit the prior transcript, and do not replay orchestration history.",
        "",
        "Original bounded task:",
        f"- ID: {item.get('id', '')}",
        f"- Title: {item.get('title', '')}",
        f"- Attempt: {attempt}/{max_attempts}",
        f"- Context: {context}",
        "",
        "Essential repository context:",
        _queue_render_list(repository_refs),
        "",
        "Prior-result compact summary:",
        prior_summary,
        "",
        "Prior artifacts and raw evidence (inspect by path; do not paste whole files):",
        _queue_render_list(artifact_paths),
        "",
        "## Hermes Revision Instructions",
        _bounded_hermes_answer(hermes_feedback.strip(), 2_000),
        "",
        "Acceptance criteria:",
        str(item.get("definition_of_done") or "Complete the scoped correction and return the required closeout.").strip(),
        "Respect the original allowed actions and stop conditions. Revise only what is needed, store verbose output as artifacts, and return a compact receipt with artifact paths.",
    )).rstrip() + "\n"


def _queue_worker_owner(item: dict) -> str:
    owner = str(item.get("owner") or "unassigned").strip().lower()
    if owner in {"codex", "claude", "hermes", "revenue", "marketing", "delivery", "operations"}:
        return owner
    return "unassigned"


def _queue_token_task_label(item: dict, owner: str) -> str:
    return f"{item.get('id', '')} | {owner} | {str(item.get('title') or '')[:160]}"


def _hermes_coordinator_command_template(route_metadata: dict | None = None) -> str:
    command = _quoted_linux_path(HERMES_COORDINATOR)
    if route_metadata and route_metadata.get("explicit_model_provider_route"):
        command += f" --provider {shlex.quote(str(route_metadata['provider_requested']))}"
        command += f" --model {shlex.quote(str(route_metadata['model_requested']))}"
    return f"{command} --prompt-file {{prompt_file}}"


def _queue_run_worker(owner: str, prompt: str, item: dict, attempt: int = 1) -> dict:
    route_metadata = _queue_resolve_route_metadata(owner)
    metadata = {
        "requested_target": owner,
        "selected_route": "queue_worker",
        "delegation_reason": "assigned queue worker",
        "codex_forbidden": "no",
        "timeout_seconds": QUEUE_WORKER_TIMEOUT_SECONDS,
        "queue_item_id": item.get("id", ""),
        "item_id": item.get("id", ""),
        "role": "implementer",
        "attempt": attempt,
        "queue_item_title": item.get("title", ""),
        "queue_lane": route_metadata["lane"],
        **route_metadata,
    }
    if owner == "codex":
        result = _run_codex_local(prompt, item)
        return _compact_agent_closeout(result, "codex", "codex", _queue_token_task_label(item, owner), metadata)
    if owner == "claude":
        item_id = str(item.get("id") or "")

        def register_runtime(process: subprocess.Popen) -> None:
            start_id = _linux_process_start_id(process.pid)
            if not start_id:
                raise RuntimeError("Claude worker process identity could not be established")
            _load_queue_tool().register_worker_runtime(
                BASE_DIR, item_id, "claude", process.pid, start_id, "aos-claude",
            )

        result = _run_wsl_prompt_command(
            'aos-hermes claude "$(<{prompt_file})"',
            prompt,
            QUEUE_WORKER_TIMEOUT_SECONDS,
            startup_timeout=AGENT_STARTUP_TIMEOUT_SECONDS,
            on_process_start=register_runtime,
        )
        invocation = {
            "executable": "/home/liam/.local/npm/bin/claude",
            "wrapper": "/home/liam/.local/bin/aos-claude",
            "cwd": str(BASE_DIR),
            "aos_root": str(BASE_DIR),
            "invocation_count": 1,
        }
        log_path = _local_agent_route_log({
            "route": "claude", "item_id": str(item.get("id") or ""),
            "success": bool(result.get("success")),
            "failure_class": result.get("failure_class"),
            "stage": result.get("command_stage") or "completion",
            "elapsed_seconds": result.get("elapsed_seconds"),
            "returncode": result.get("returncode"),
            "startup_timeout_seconds": AGENT_STARTUP_TIMEOUT_SECONDS,
            "execution_timeout_seconds": QUEUE_WORKER_TIMEOUT_SECONDS,
            "parent_timeout_seconds": AGENT_PARENT_TIMEOUT_SECONDS,
            "stdout_tail": _bounded_stream_tail(result.get("stdout")),
            "stderr_tail": _bounded_stream_tail(result.get("stderr")),
            **invocation,
        })
        result = {**result, "invocation": invocation, "log_path": log_path}
        return _compact_agent_closeout(result, "claude", "claude", _queue_token_task_label(item, owner), metadata)
    command_template = _hermes_coordinator_command_template(route_metadata)
    result = _run_wsl_prompt_command(command_template, prompt, QUEUE_WORKER_TIMEOUT_SECONDS)
    agent = owner if owner in DEPARTMENT_PROMPT_TARGETS else "hermes"
    return _compact_agent_closeout(result, agent, agent, _queue_token_task_label(item, owner), metadata)


def _queue_hermes_review_prompt(item: dict, owner: str, attempt: int, worker_result: dict) -> str:
    verified_artifacts = _queue_verified_artifacts_from_worker_result(item, worker_result)
    review_input = _queue_final_review_input(item, worker_result, verified_artifacts)
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
        _queue_render_verified_artifacts(verified_artifacts, include_excerpt=False),
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
        f"Worker attempt {attempt} final review input only:",
        review_input,
    ))


def _queue_final_review_input(item: dict, worker_result: dict, verified_artifacts: list[dict] | None = None) -> str:
    """Return only a final artifact, or a bounded final closeout when no artifact exists."""
    artifacts = verified_artifacts or _queue_verified_artifacts_from_worker_result(item, worker_result)
    for artifact in artifacts:
        if not artifact.get("available"):
            continue
        try:
            content = _queue_read_artifact(str(artifact.get("path") or ""))["content"]
        except (FileNotFoundError, ValueError, OSError):
            continue
        return "\n".join((
            f"Final artifact: {artifact.get('path')}",
            _bounded_hermes_answer(content, 12_000),
        ))
    closeout = str(worker_result.get("review_output") or worker_result.get("output") or "").strip()
    return "\n".join(("Bounded final closeout:", _bounded_hermes_answer(closeout or "(no final closeout)", 4000)))


def _queue_model_review_requested(item: dict) -> bool:
    return str(item.get("review") or "none").strip().casefold() == "model"


def _queue_deterministic_review_result() -> dict:
    return {
        "success": True,
        "output": "PASS",
        "stdout": "",
        "stderr": "",
        "returncode": 0,
        "timed_out": False,
        "timeout_seconds": None,
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
        "review_mode": "deterministic",
    }


def _queue_run_hermes_review(item: dict, owner: str, attempt: int, worker_result: dict) -> dict:
    prompt = _queue_hermes_review_prompt(item, owner, attempt, worker_result)
    result = _run_hermes_message(
        prompt,
        role="reviewer",
        attempt=attempt,
        item_id=str(item.get("id") or ""),
        timeout=QUEUE_HERMES_REVIEW_TIMEOUT_SECONDS,
    )
    return {
        "success": bool(result.get("success")),
        "output": result.get("output") or result.get("stdout") or result.get("stderr") or "",
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "returncode": result.get("returncode", -1),
        "timed_out": bool(result.get("timed_out")),
        "timeout_seconds": result.get("timeout_seconds"),
        "token_usage": result.get("token_usage") or {"available": False},
        "token_usage_text": result.get("token_usage_text") or "Token usage: unavailable from current CLI output",
        "invocation_id": result.get("invocation_id"),
        "session_id": result.get("session_id"),
        "profile_requested": "aos-orchestrator",
        "profile_used": "aos-orchestrator",
        "role": "reviewer",
        "attempt": attempt,
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


_REVIEW_MISSING_ARTIFACT_RE = re.compile(
    r"(?is)\b(?:artifact|receipt|file|path)\b.{0,120}\b(?:missing|not found|does not exist|unavailable|blocked)\b"
    r"|\b(?:missing|not found|does not exist)\b.{0,120}\b(?:artifact|receipt|file|path)\b"
)


def _queue_review_decision(item: dict, worker_result: dict, review_result: dict) -> tuple[str, str]:
    """Combine Hermes quality review with authoritative local artifact evidence."""
    verified = _queue_verified_artifacts_from_worker_result(item, worker_result)
    claimed_paths = _queue_unique_artifact_paths(
        _queue_artifact_candidates_from_text(str(worker_result.get("output") or ""))
    )
    for required_path in claimed_paths:
        required = next((row for row in verified if row.get("path") == required_path), None)
        if not required or not required.get("available"):
            reason = (required or {}).get("reason") or "artifact was not reported"
            return "REVISE", f"Claimed canonical artifact is genuinely absent: {required_path} ({reason})."

    decision, instructions = _queue_parse_review(review_result)
    if decision == "REVISE" and _REVIEW_MISSING_ARTIFACT_RE.search(
        str(review_result.get("output") or instructions)
    ):
        return "PASS", (
            "PASS: authoritative Linux-root verification found the required canonical artifact; "
            "the reviewer path-missing claim was rejected without rerunning the worker."
        )
    return decision, instructions


def _queue_result_summary(result: dict, limit: int = 900) -> str:
    text = str(result.get("output") or result.get("stdout") or result.get("stderr") or "").strip()
    if not text:
        text = "(no worker output)"
    return _bounded_hermes_answer(text, limit)


def _queue_result_field(result: dict, label: str, default: str = "None reported") -> str:
    raw = str(result.get("output") or "")
    return _field_from_output(raw, label) or default


def _queue_operator_summary_from_result(item: dict, result: dict) -> str:
    """Return a useful safe summary even when a wrapper compacts the closeout."""
    explicit = _queue_result_field(result, "Summary for operator", "")
    if explicit:
        return explicit
    review_lines = [
        re.sub(r"\s+", " ", line).strip(" -*\t")
        for line in str(result.get("review_output") or "").splitlines()
    ]
    summary = next(
        (line for line in review_lines if line and line.upper() not in {"PASS", "NEEDS ATTENTION"}),
        f"{aos_orchestration.operator_task_title(item)} passed its assigned worker and configured review gate.",
    )
    summary = _bounded_hermes_answer(summary, 360).rstrip(". ") + "."
    return f"{summary} Approving closes this local review; it sends nothing externally."


def _queue_item_timestamp(item: dict) -> datetime.datetime | None:
    for key in ("worker_heartbeat_at", "claim", "updated_at", "created_at"):
        value = item.get(key)
        if key == "claim" and isinstance(value, dict):
            value = value.get("claimed_at")
        parsed = _parse_record_timestamp(value)
        if parsed:
            return parsed
    return None


def _linux_process_start_id(pid: int) -> str | None:
    """Return Linux /proc starttime for PID-reuse-safe liveness checks."""
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8")
        fields = stat.rsplit(") ", 1)[1].split()
        return fields[19]
    except (OSError, ValueError, IndexError):
        return None


def _queue_worker_runtime_live(item: dict) -> bool:
    runtime = item.get("worker_runtime")
    if not isinstance(runtime, dict):
        return False
    try:
        pid = int(runtime.get("pid"))
    except (TypeError, ValueError):
        return False
    expected = str(runtime.get("process_start_id") or "")
    return bool(expected and _linux_process_start_id(pid) == expected)


def _queue_heartbeat_loop(item_id: str, owner: str, stop: threading.Event) -> None:
    interval = min(QUEUE_HEARTBEAT_INTERVAL_SECONDS, max(1, QUEUE_STUCK_TIMEOUT_SECONDS // 3))
    while not stop.wait(interval):
        try:
            _load_queue_tool().renew_claim(BASE_DIR, item_id, owner)
        except Exception as exc:
            _dashboard_backend_log({
                "event": "queue_worker_heartbeat_stopped",
                "item_id": item_id,
                "owner": owner,
                "reason": type(exc).__name__,
            })
            return


def _queue_stuck_recovery(item: dict, now: datetime.datetime | None = None) -> dict:
    if item.get("status") != "agent_working":
        return {"stuck": False}
    started = _queue_item_timestamp(item)
    if not started:
        return {
            "stuck": True,
            "age_seconds": None,
            "timeout_seconds": QUEUE_STUCK_TIMEOUT_SECONDS,
            "reason": "agent_working item has no readable heartbeat/claim timestamp",
        }
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    age = max(0, int((now - started.astimezone(datetime.timezone.utc)).total_seconds()))
    runtime_live = age >= QUEUE_STUCK_TIMEOUT_SECONDS and _queue_worker_runtime_live(item)
    return {
        "stuck": age >= QUEUE_STUCK_TIMEOUT_SECONDS and not runtime_live,
        "age_seconds": age,
        "timeout_seconds": QUEUE_STUCK_TIMEOUT_SECONDS,
        "runtime_live": runtime_live,
        "reason": (
            f"last worker heartbeat was {age}s ago, but the exact worker process is still live"
            if runtime_live
            else f"last worker heartbeat was {age}s ago; lease threshold is {QUEUE_STUCK_TIMEOUT_SECONDS}s"
        ),
    }


def _queue_recovery_receipt_text(item: dict, owner: str, reason: str) -> str:
    route_metadata = _queue_resolve_route_metadata(owner)
    return "\n".join((
        "NEEDS ATTENTION",
        "",
        f"Work item title: {aos_orchestration.operator_task_title(item)}",
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
    review_label = "Hermes model review" if _queue_model_review_requested(item) else "deterministic review"
    for attempt in attempts:
        worker_token = attempt["worker_result"].get("token_usage_text") or "Token usage: unavailable from current CLI output"
        review_token = attempt["review_result"].get("token_usage_text") or "Token usage: unavailable from current CLI output"
        worker_usage = attempt["worker_result"].get("token_usage") or {}
        review_usage = attempt["review_result"].get("token_usage") or {}
        token_lines.append(
            f"- Attempt {attempt['attempt']} worker (role=implementer; session="
            f"{worker_usage.get('session_id') or worker_usage.get('invocation_id') or 'unavailable'}): "
            f"{_token_usage_detail(worker_token)}"
        )
        token_lines.append(
            f"- Attempt {attempt['attempt']} worker counters: "
            + json.dumps(_usage_counters_from_token_usage(worker_usage), sort_keys=True)
        )
        for handoff_index, handoff in enumerate(attempt["worker_result"].get("handoff_sessions") or [], start=1):
            handoff_usage = handoff.get("token_usage") if isinstance(handoff, dict) else {}
            token_lines.append(
                f"- Attempt {attempt['attempt']} context handoff {handoff_index} (fresh session="
                f"{handoff.get('session_id') or 'unavailable'}; artifact={handoff.get('handoff_artifact') or 'unavailable'}): "
                f"{_token_usage_detail(str(handoff.get('token_usage_text') or 'Token usage: unavailable from current CLI output'))}"
            )
            token_lines.append(
                f"- Attempt {attempt['attempt']} context handoff {handoff_index} counters: "
                + json.dumps(_usage_counters_from_token_usage(handoff_usage), sort_keys=True)
            )
        token_lines.append(
            f"- Attempt {attempt['attempt']} {review_label} (role=reviewer; session="
            f"{review_usage.get('session_id') or review_usage.get('invocation_id') or 'unavailable'}): "
            f"{_token_usage_detail(review_token)}"
        )
        token_lines.append(
            f"- Attempt {attempt['attempt']} reviewer counters: "
            + json.dumps(_usage_counters_from_token_usage(review_usage), sort_keys=True)
        )
    if not token_lines:
        token_lines.append("- unavailable/no agent invocation")
    verified_artifacts = _queue_verified_artifacts_from_worker_result(item, last_worker)
    diagnostic_lines = [
        f"- Failure class: {last_worker.get('failure_class') or 'none'}",
        f"- Command stage: {last_worker.get('command_stage') or 'completion'}",
        f"- Elapsed seconds: {last_worker.get('elapsed_seconds') if last_worker.get('elapsed_seconds') is not None else 'unavailable'}",
        f"- Startup timeout: {last_worker.get('startup_timeout_seconds') if last_worker.get('startup_timeout_seconds') is not None else 'not separately exposed'}",
        f"- Execution timeout: {last_worker.get('execution_timeout_seconds') if last_worker.get('execution_timeout_seconds') is not None else last_worker.get('timeout_seconds', 'unavailable')}",
        f"- Subprocess/parent timeout: {last_worker.get('parent_timeout_seconds') if last_worker.get('parent_timeout_seconds') is not None else AGENT_PARENT_TIMEOUT_SECONDS}",
        f"- Graceful termination allowance: {last_worker.get('graceful_termination_seconds') if last_worker.get('graceful_termination_seconds') is not None else AGENT_GRACEFUL_TERMINATION_SECONDS}",
        f"- Receipt/artifact finalization timeout: {QUEUE_FINALIZATION_TIMEOUT_SECONDS}",
        f"- Diagnostic log: {last_worker.get('diagnostic_log') or 'logs/dashboard_backend.log'}",
        f"- Captured stdout tail: {last_worker.get('captured_stdout_tail') or '(empty)'}",
        f"- Captured stderr tail: {last_worker.get('captured_stderr_tail') or '(empty)'}",
    ]
    if owner == "codex":
        invocation = last_worker.get("invocation") if isinstance(last_worker.get("invocation"), dict) else {}
        diagnostic_lines.extend((
            f"- Codex executable: {invocation.get('executable') or 'unavailable'}",
            f"- Effective Linux user: {invocation.get('linux_user') or 'unavailable'} (uid={invocation.get('effective_uid', 'unavailable')})",
            f"- Working directory: {invocation.get('cwd') or 'unavailable'}",
            f"- Sandbox: {invocation.get('sandbox') or 'unavailable'}",
            f"- Approval policy: {invocation.get('approval_policy') or invocation.get('ask_for_approval') or 'unavailable'}",
        ))
    if owner == "claude":
        invocation = last_worker.get("invocation") if isinstance(last_worker.get("invocation"), dict) else {}
        diagnostic_lines.extend((
            f"- Claude executable: {invocation.get('executable') or 'unavailable'}",
            f"- Claude wrapper: {invocation.get('wrapper') or 'unavailable'}",
            f"- Working directory: {invocation.get('cwd') or 'unavailable'}",
            f"- AOS_ROOT: {invocation.get('aos_root') or 'unavailable'}",
            f"- Claude invocation count: {invocation.get('invocation_count', 'unavailable')}",
        ))

    lines = [
        status_label,
        "",
        f"Work item title: {aos_orchestration.operator_task_title(item)}",
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
        f"Review mode: {'model' if _queue_model_review_requested(item) else 'none (deterministic proof)'}",
        f"Review result: {final_review.get('decision', 'REVISE')}",
        "",
        "Worker result summary:",
        _queue_result_summary(last_worker),
        "",
        "Summary for operator:",
        f"- {_queue_operator_summary_from_result(item, last_worker)}",
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
        "Route diagnostics:",
        *diagnostic_lines,
        "",
        "Blockers:",
        f"- {reason or _queue_result_field(last_worker, 'Blockers')}",
        "",
        "Next action:",
        (
            "- None; native Hermes accepted this orchestration child."
            if final_status == "done"
            else "- Liam review in dashboard."
            if final_status == "human_review"
            else "- Liam review of the parent orchestration escalation; no fourth child attempt is allowed."
            if _is_hermes_orchestration_child(item)
            else "- Liam input needed before another worker run."
        ),
        "",
        "Token usage:",
        *token_lines,
    ]
    return "\n".join(lines)


def _notify_queue_running(
    item_id: str,
    *,
    send_telegram=None,
) -> dict | None:
    """Notify a Telegram-originated item when the dashboard runner claims it."""
    try:
        with queue_write_lock(BASE_DIR):
            items = _read_queue_items()
            item = next((row for row in items if row.get("id") == item_id), None)
            if not item or str(item.get("source") or "").lower() != "telegram":
                return None
            recipient = _telegram_reply_to(item)
            if not recipient:
                return {"result": "skipped", "sent": False, "reason": "chat_id_unavailable"}
            message = aos_orchestration.format_operator_work_item_notification(
                item,
                "agent_working",
                summary=f"{aos_orchestration.operator_task_title(item)} is now running through the assigned worker.",
                next_action="None",
                receipt_attached=False,
            )
            result = aos_orchestration.attempt_telegram_send(
                BASE_DIR,
                item,
                recipient,
                message,
                send_telegram=send_telegram,
                key="async_running",
                document_paths=[],
            )
            aos_orchestration.append_jsonl(BASE_DIR / aos_orchestration.EVENTS_PATH, result)
            _load_queue_tool().save_items(BASE_DIR, items)
            return result
    except Exception as exc:
        _dashboard_backend_log({
            "event": "telegram_async_running",
            "item_id": item_id,
            "result": "send_failed",
            "reason": type(exc).__name__,
        })
        return {"result": "send_failed", "sent": False, "reason": type(exc).__name__}


def _notify_queue_completion(
    item_id: str,
    status: str,
    receipt_path: str,
    *,
    send_telegram=None,
) -> dict | None:
    """Notify a Telegram-originated item through the existing idempotent send path."""
    try:
        with queue_write_lock(BASE_DIR):
            items = _read_queue_items()
            item = next((row for row in items if row.get("id") == item_id), None)
            if not item or str(item.get("source") or "").lower() != "telegram":
                return None
            recipient = _telegram_reply_to(item)
            if not recipient:
                return {"result": "skipped", "sent": False, "reason": "chat_id_unavailable"}
            label = aos_orchestration.operator_status_label(status)
            message = aos_orchestration.format_operator_work_item_notification(
                item,
                status,
                summary=(
                    f"{aos_orchestration.operator_task_title(item)} is ready for operator review."
                    if status == "human_review"
                    else f"{aos_orchestration.operator_task_title(item)} finished as {label}."
                ),
                next_action="Review the attached closeout." if status == "human_review" else "Review the attached receipt or local logs.",
                receipt_path=receipt_path,
                receipt_attached=bool(receipt_path),
            )
            docs = [str(BASE_DIR / receipt_path)] if receipt_path and (BASE_DIR / receipt_path).is_file() else []
            result = aos_orchestration.attempt_telegram_send(
                BASE_DIR,
                item,
                recipient,
                message,
                send_telegram=send_telegram,
                key=f"async_completion:{status}",
                document_paths=docs,
            )
            aos_orchestration.append_jsonl(BASE_DIR / aos_orchestration.EVENTS_PATH, result)
            _load_queue_tool().save_items(BASE_DIR, items)
            return result
    except Exception as exc:
        _dashboard_backend_log({
            "event": "telegram_async_completion",
            "item_id": item_id,
            "status": status,
            "result": "send_failed",
            "reason": type(exc).__name__,
        })
        return {"result": "send_failed", "sent": False, "reason": type(exc).__name__}


def _is_hermes_orchestration_child(item: dict) -> bool:
    return (
        "hermes_orchestration_child" in {str(tag) for tag in item.get("tags") or []}
        and str(item.get("owner") or "").lower() == "codex"
        and str(item.get("review") or "").lower() == "model"
        and str((item.get("orchestration") or {}).get("outer_coordinator") or "hermes") == "hermes"
    )


def _escalate_hermes_orchestration_to_liam(item: dict, receipt_path: str, attempts_used: int) -> dict | None:
    parent_id = str(item.get("parent_id") or "")
    if not parent_id:
        return None
    queue_tool = _load_queue_tool()
    with queue_write_lock(BASE_DIR):
        items = queue_tool.load_items(BASE_DIR)
        try:
            parent = queue_tool.find_item(items, parent_id)
        except (KeyError, ValueError):
            return None
        reasons = [str(value) for value in parent.get("needs_me") or []]
        reason = f"Hermes rejected {item.get('id')} after the initial review and two corrections."
        if reason not in reasons:
            reasons.append(reason)
        parent["needs_me"] = reasons
        parent["status"] = "human_review"
        parent["updated_at"] = queue_tool.now_iso()
        queue_tool.save_items(BASE_DIR, items)
    event = {
        "event": "hermes_review_escalated_to_liam",
        "effect_id": aos_orchestration.effect_identity("hermes_review_escalated_to_liam", parent_id, str(item.get("id") or "")),
        "created_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "parent_id": parent_id,
        "item_id": item.get("id"),
        "attempts_used": attempts_used,
        "receipt_path": receipt_path,
        "fourth_attempt_allowed": False,
    }
    events_path = BASE_DIR / aos_orchestration.EVENTS_PATH
    if events_path.exists():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            try:
                existing_event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if existing_event.get("effect_id") == event["effect_id"]:
                return existing_event
    aos_orchestration.append_jsonl(BASE_DIR / aos_orchestration.EVENTS_PATH, event)
    return event


def _finalize_hermes_orchestration_parent(item: dict) -> dict | None:
    parent_id = str(item.get("parent_id") or "")
    if not parent_id:
        return None
    items = _read_queue_items()
    try:
        parent = next(row for row in items if row.get("id") == parent_id)
    except StopIteration:
        return None
    children = sorted(
        [row for row in items if row.get("parent_id") == parent_id and _is_hermes_orchestration_child(row)],
        key=lambda row: (int(row.get("step_index") or 0), str(row.get("id") or "")),
    )
    if not children or any(row.get("status") != "done" for row in children):
        return None
    if parent.get("status") == "done":
        return parent
    receipt_path = f"queue/receipts/{parent_id}-hermes-orchestration.md"
    receipt_target = BASE_DIR / receipt_path
    child_lines = []
    for child in children:
        latest = _queue_latest_receipt(child)
        child_lines.append(
            f"- {child.get('id')}: done; worker=codex; receipt={(latest or {}).get('path') or 'unavailable'}"
        )
    durable_replace_text(receipt_target, "\n".join((
        "PASS", "", f"Work item ID: {parent_id}",
        "Summary for operator:",
        "- Native Hermes coordinated and reviewed every bounded Codex child; all passed within the correction limit.",
        "", "Worker:", "- Codex implemented every child; Hermes was outer coordinator/reviewer only.",
        "", "Attempts:", *child_lines,
        "", "Validation:", "- Every child has status done and a substantive receipt.",
        "", "Blockers:", "- None",
        "", "Next action:", "- None; workflow closed without Liam review.",
        "", "Token usage:", "- Hermes and Codex invocations are recorded separately by invocation/session in the token ledgers.",
        "",
    )))
    updated = _load_queue_tool().attach_receipt(BASE_DIR, parent_id, receipt_path, "done")
    event = {
        "event": "hermes_orchestration_completed",
        "effect_id": aos_orchestration.effect_identity("hermes_orchestration_completed", parent_id),
        "created_at": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "parent_id": parent_id,
        "child_ids": [row.get("id") for row in children],
        "liam_review_required": False,
        "receipt_path": receipt_path,
    }
    aos_orchestration.append_jsonl(BASE_DIR / aos_orchestration.EVENTS_PATH, event)
    return updated


@app.post("/api/queue/items/{item_id}/run")
def run_queue_item(item_id: str):
    """Run one selected queue item through its assigned worker, then Hermes review."""
    heartbeat_stop: threading.Event | None = None
    heartbeat_thread: threading.Thread | None = None
    try:
        item = _queue_find_item(item_id)
        owner = _queue_worker_owner(item)
        orchestration_child = _is_hermes_orchestration_child(item)
        if orchestration_child and item.get("status") in {"done", "blocked"}:
            raise HTTPException(
                status_code=409,
                detail="Hermes orchestration child is terminal; no fourth or duplicate attempt is allowed",
            )
        latitude_telemetry.trace("runner.queue_run_start", "deterministic_runner", "agent_working", item_id=item_id, owner=owner)
        recovery = _queue_stuck_recovery(item)
        if item.get("status") == "agent_working":
            if not recovery.get("stuck"):
                raise HTTPException(status_code=409, detail="queue item is already agent_working; refresh before rerun")
            receipt_text = _queue_recovery_receipt_text(item, owner, recovery.get("reason") or "agent_working item exceeded local timeout")
            receipt_path = _queue_write_run_receipt(item_id, receipt_text)
            updated = _load_queue_tool().attach_receipt(BASE_DIR, item_id, receipt_path, "blocked")
            updated = _load_queue_tool().release_item(BASE_DIR, item_id, "blocked")
            notification = _notify_queue_completion(item_id, "blocked", receipt_path)
            latitude_telemetry.trace("runner.queue_run_recovered", "deterministic_runner", "blocked", item_id=item_id, owner=owner, receipt_path=receipt_path)
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
                "notification": notification,
                "item": _queue_detail_item(updated),
            }

        claim_owner = owner if owner != "unassigned" else "hermes"
        started = _load_queue_tool().claim_item(BASE_DIR, item_id, claim_owner)
        heartbeat_stop = threading.Event()
        heartbeat_thread = threading.Thread(
            target=_queue_heartbeat_loop,
            args=(item_id, claim_owner, heartbeat_stop),
            name=f"queue-heartbeat-{item_id}",
            daemon=True,
        )
        heartbeat_thread.start()
        running_notification = _notify_queue_running(item_id)
        attempts = []
        revision_instructions = None
        prior_worker_result: dict | None = None
        max_attempts = 3 if orchestration_child else 2
        passing_status = "done" if orchestration_child else "human_review"
        final_review = {"decision": "REVISE", "instructions": "No review completed."}
        final_status = "needs_input"
        reason = "The configured review gate did not pass the worker result."

        for attempt_number in range(1, max_attempts + 1):
            run_item = _queue_find_item(item_id)
            prompt = _queue_actual_run_prompt(
                run_item, owner if owner != "unassigned" else "hermes",
                revision_instructions, attempt_number, max_attempts, prior_worker_result,
            )
            worker_result = _queue_run_worker(owner, prompt, run_item, attempt_number)
            worker_failure_class = str(worker_result.get("failure_class") or "")
            if worker_result.get("success"):
                review_result = (
                    _queue_run_hermes_review(run_item, owner, attempt_number, worker_result)
                    if _queue_model_review_requested(run_item)
                    else _queue_deterministic_review_result()
                )
            else:
                review_result = {
                    "success": False,
                    "output": "REVISE: Worker route failed before review.",
                    "stdout": "",
                    "stderr": "",
                    "returncode": -1,
                    "timed_out": False,
                    "timeout_seconds": None,
                    "token_usage": {"available": False, "no_agent_invocation": True},
                    "token_usage_text": "Token usage: no agent invocation",
                }
            if worker_result.get("timed_out"):
                final_status = "blocked"
                decision = "REVISE"
                review_text = (
                    f"{worker_failure_class or 'agent_route_timeout'} during {worker_result.get('command_stage') or 'execution'} "
                    f"after {worker_result.get('elapsed_seconds', worker_result.get('timeout_seconds'))}s; "
                    f"diagnostics: {worker_result.get('diagnostic_log') or 'logs/dashboard_backend.log'}."
                )
                review_result["output"] = f"REVISE: {review_text}\n\nHermes review output:\n{review_result.get('output', '')}"
            elif int(worker_result.get("returncode", 0) or 0) != 0:
                final_status = "blocked"
                decision = "REVISE"
                review_text = (
                    f"{worker_failure_class or 'agent_process_failure'} at {worker_result.get('command_stage') or 'execution'}; "
                    f"worker exited with status {worker_result.get('returncode', -1)}. "
                    f"Diagnostics: {worker_result.get('diagnostic_log') or 'logs/dashboard_backend.log'}."
                )
                review_result["output"] = f"REVISE: {review_text}\n\nHermes review output:\n{review_result.get('output', '')}"
            elif not worker_result.get("success"):
                final_status = "blocked"
                decision = "REVISE"
                review_text = (
                    f"{worker_failure_class or 'agent_reported_task_failure'}: "
                    f"{worker_result.get('failure_detail') or _queue_result_field(worker_result, 'Blockers', 'worker did not report a blocker')}. "
                    f"Diagnostics: {worker_result.get('diagnostic_log') or 'logs/dashboard_backend.log'}."
                )
                review_result["output"] = f"REVISE: {review_text}\n\nHermes review output:\n{review_result.get('output', '')}"
            else:
                decision, review_text = _queue_review_decision(run_item, worker_result, review_result)
                if review_result.get("timed_out"):
                    final_status = "blocked"
                    review_text = f"Hermes review timed out after {review_result.get('timeout_seconds')}s."
                    review_result["output"] = f"REVISE: {review_text}"
            if final_status != "blocked":
                decision, review_text = _queue_review_decision(run_item, worker_result, review_result)
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
                final_status = passing_status
                reason = "None"
                break
            if review_text.startswith("Claimed canonical artifact is genuinely absent:"):
                reason = review_text
                break
            if final_status == "blocked":
                reason = review_text
                break
            revision_instructions = review_text
            prior_worker_result = worker_result

        if final_status != passing_status:
            reason = final_review.get("instructions") or f"The configured review gate requested revision after {max_attempts} attempts."
            if orchestration_child:
                final_status = "blocked"

        receipt_text = _queue_run_receipt_text(
            "PASS" if final_status in {"human_review", "done"} else "NEEDS ATTENTION",
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
        orchestration_event = None
        orchestration_parent = None
        if orchestration_child and final_status == "done":
            orchestration_parent = _finalize_hermes_orchestration_parent(updated)
        elif orchestration_child:
            orchestration_event = _escalate_hermes_orchestration_to_liam(updated, receipt_path, len(attempts))
        notification = _notify_queue_completion(item_id, final_status, receipt_path)
        event_type = "queue.needs_me" if final_status in {"needs_input", "human_review", "blocked"} else "runner.queue_run_complete"
        latitude_telemetry.trace(event_type, "deterministic_runner", final_status, item_id=item_id, owner=owner, receipt_path=receipt_path, attempts_used=len(attempts))
    except KeyError:
        raise HTTPException(status_code=404, detail="queue item not found")
    except HTTPException:
        raise
    except Exception as exc:
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
    finally:
        if heartbeat_stop is not None:
            heartbeat_stop.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=2)

    return {
        "ok": True,
        "success": final_status in {"human_review", "done"},
        "item_id": item_id,
        "assigned_worker": owner,
        "attempts_used": len(attempts),
        "status": updated.get("status"),
        "started_status": started.get("status"),
        "receipt_path": receipt_path,
        "hermes_review": final_review,
        "worker_result": attempts[-1]["worker_result"] if attempts else {},
        "attempts": attempts,
        "running_notification": running_notification,
        "notification": notification,
        "outer_coordinator": "hermes" if orchestration_child else None,
        "orchestration_event": orchestration_event,
        "orchestration_parent_status": (orchestration_parent or {}).get("status") if orchestration_parent else None,
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
        f"  - {aos_orchestration.operator_item_label(item)} | {item.get('status', '')} | {item.get('owner', 'unassigned')} | "
        f"{item.get('id', '')} | {item.get('status', '')} | {item.get('owner', 'unassigned')} | {item.get('title', '')}"
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
        aos_orchestration.operator_item_label(item),
        str(item.get("owner", "unassigned")),
        str(item.get("status", "")),
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


def _queue_recent_receipts_closeout() -> dict:
    items = sorted(_read_queue_items(), key=_queue_item_sort_key)
    rows = []
    for item in items:
        latest = _queue_latest_receipt(item)
        if not latest or not latest.get("path"):
            continue
        rows.append(
            f"  - {item.get('id')} | {item.get('status')} | {item.get('owner')} | {latest.get('path')} | {latest.get('summary')}"
        )
        if len(rows) >= 10:
            break
    return {
        "success": True,
        "output": "\n".join((
            "PASS", "Latest substantive receipts:", *(rows or ["  - None"]),
            "Lookup token usage: no agent invocation",
        )),
        "returncode": 0,
        "requested_target": "queue",
        "selected_route": "local_queue_receipts",
        "delegation_reason": "structured receipt-state read",
        "codex_forbidden": "no",
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


def _queue_token_state_closeout() -> dict:
    records = _read_token_ledger_records()
    views = [_token_record_view(row) for row in records]
    exact = [row for row in views if row.get("availability_state") == "exact" and row.get("total_tokens") is not None]
    unavailable = sum(row.get("availability_state") == "unavailable" for row in views)
    total_input = sum(int(row.get("input_tokens") or 0) for row in exact)
    total_output = sum(int(row.get("output_tokens") or 0) for row in exact)
    total = sum(int(row.get("total_tokens") or 0) for row in exact)
    latest = _sort_token_records_newest(records)[:5]
    latest_lines = [
        f"  - {_ledger_task_id(row)} | {_ledger_component(row)} | {_token_label(row)}"
        for row in latest
    ] or ["  - None"]
    return {
        "success": True,
        "output": "\n".join((
            "PASS", "Recorded token state:",
            f"  - exact sessions: {len(exact)}",
            f"  - total input: {total_input}",
            f"  - output: {total_output}",
            f"  - input plus output: {total}",
            f"  - unavailable sessions: {unavailable}",
            "Latest sessions:", *latest_lines,
            "Lookup token usage: no agent invocation",
        )),
        "returncode": 0,
        "requested_target": "queue",
        "selected_route": "local_token_state",
        "delegation_reason": "structured token-ledger read",
        "codex_forbidden": "no",
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


def _try_queue_read_task(task: str) -> dict | None:
    normalized = " ".join(task.strip().lower().split())
    normalized_without_punctuation = normalized.rstrip("?.!")
    if normalized in _SYSTEM_STATUS_INTENTS:
        return _operator_system_status_closeout()
    if normalized in _QUEUE_STATUS_INTENTS or normalized_without_punctuation in _QUEUE_STATUS_INTENTS:
        return _queue_status_closeout()
    filtered_intent = _QUEUE_FILTERED_READ_INTENTS.get(normalized)
    if filtered_intent is not None:
        return _queue_filtered_read_closeout(*filtered_intent)
    if re.search(r"\b(?:active|current|running|pending)\s+(?:queue\s+)?(?:tasks?|work|items?)\b|\bwhat\s+(?:is|are)\s+(?:currently\s+)?(?:active|running)\b", normalized):
        return _queue_list_closeout(None)
    if re.search(r"\b(?:show|list|read|what(?:'s| is)?|where(?:'s| is)?)\b[^.!?\n]{0,60}\b(?:latest\s+)?receipts?\b", normalized):
        return _queue_recent_receipts_closeout()
    if re.search(r"\b(?:how\s+many\s+tokens|token\s+usage|tokens?\s+(?:used|spent|reported))\b", normalized):
        return _queue_token_state_closeout()
    is_queue_list, status, invalid = _queue_status_filter(task)
    if invalid is not None:
        return invalid
    if is_queue_list:
        return _queue_list_closeout(status)
    return None


_EXISTING_ITEM_READ_RE = re.compile(
    r"\b(?:read|show|explain|report|retrieve|surface|attach|status|details?|why|what\s+happened|failed|blocked|receipt|artifact|worker|owner|complete|completed|done|tokens?|attempts?)\b",
    re.IGNORECASE,
)
_SUBSTANTIVE_CHANGE_RE = re.compile(
    r"\b(?:implement|repair|fix|build|create|modify|edit|update|rerun|resume|execute|run\s+(?:the|this|it))\b",
    re.IGNORECASE,
)


def _receipt_section_value(content: str, heading: str, default: str) -> str:
    lines = str(content or "").splitlines()
    for index, line in enumerate(lines):
        if line.strip().rstrip(":").casefold() != heading.casefold():
            continue
        values = []
        for candidate in lines[index + 1:]:
            stripped = candidate.strip()
            if not stripped:
                if values:
                    break
                continue
            if stripped.endswith(":") and not stripped.startswith(("-", "*")):
                break
            values.append(stripped.lstrip("-* "))
            if sum(len(value) for value in values) >= 700:
                break
        if values:
            return _bounded_hermes_answer(" ".join(values), 700)
    inline = _field_from_output(content, heading)
    return inline or default


def _try_existing_item_read_task(task: str, body: TaskRun | None = None) -> dict | None:
    ids = sorted({match.group(0).upper() for match in _TELEGRAM_APPROVAL_ITEM_RE.finditer(str(task or ""))})
    if not _EXISTING_ITEM_READ_RE.search(task):
        return None
    if _SUBSTANTIVE_CHANGE_RE.search(task) and "do not create" not in task.lower():
        return None
    if len(ids) > 1:
        return None
    if not ids:
        normalized = " ".join(str(task or "").lower().split())
        if normalized not in {"why was it blocked?", "why was it blocked", "why did it fail?", "why did it fail", "what happened?", "what happened"}:
            return None
        candidates = [
            row for row in _read_queue_items()
            if row.get("status") in {"blocked", "needs_input", "human_review"}
            and str(row.get("source") or "").lower() == "telegram"
            and str(row.get("requested_by") or "").casefold() == "liam"
        ]
        incoming_reply = str(getattr(body, "reply_to", "") or "") if body is not None else ""
        if incoming_reply:
            correlated = [row for row in candidates if _telegram_item_matches_operator(row, body, explicit_id=False)]
            candidates = correlated or candidates
        if not candidates:
            return None
        candidates.sort(key=lambda row: (str(row.get("updated_at") or ""), str(row.get("id") or "")), reverse=True)
        ids = [str(candidates[0].get("id") or "")]
    try:
        item = _queue_find_item(ids[0])
    except KeyError:
        return {
            "success": False,
            "created": False,
            "output": f"NEEDS ATTENTION\nExisting work item {ids[0]} was not found.\nNo new work item was created.",
            "returncode": 2,
            "requested_target": "queue",
            "selected_route": "local_existing_item_read",
            "delegation_reason": "bounded existing-item read intent",
            "token_usage": {"available": False, "no_agent_invocation": True},
            "token_usage_text": "Token usage: no agent invocation",
        }
    receipts = item.get("receipts") or []
    primary_path = f"queue/receipts/{item.get('id')}.md"
    receipt = next(
        (
            {"path": row} if isinstance(row, str) else row
            for row in receipts
            if str(row if isinstance(row, str) else (row or {}).get("path") or "") == primary_path
        ),
        None,
    )
    if receipt is None:
        receipt = next(
            (
                {"path": row} if isinstance(row, str) else row
                for row in reversed(receipts)
                if "-notification-" not in str(row if isinstance(row, str) else (row or {}).get("path") or "")
                and "-telegram-escalation-" not in str(row if isinstance(row, str) else (row or {}).get("path") or "")
            ),
            None,
        )
    if receipt is None:
        receipt = _queue_latest_receipt(item)
    receipt_path = str((receipt or {}).get("path") or "")
    receipt_content = ""
    if receipt_path:
        try:
            receipt_content = _queue_read_artifact(receipt_path, receipt_only=True).get("content", "")
        except (HTTPException, OSError, ValueError):
            receipt_content = ""
    files_touched = _receipt_section_value(receipt_content, "Files touched", "None reported")
    validation = _receipt_section_value(receipt_content, "Validation", "No validation reported")
    blockers = _receipt_section_value(receipt_content, "Blockers", "None reported")
    next_action = _receipt_section_value(receipt_content, "Next action", "Review the existing item")
    canonical_usage = _queue_canonical_token_usage(str(item.get("id") or ""))
    recorded_usage = "; ".join((canonical_usage or {}).get("lines") or _queue_token_usage_lines(receipt_content)) or "unavailable"
    artifacts = [row.get("path") for row in _queue_artifact_refs(item, receipt_content) if row.get("path")]
    title = aos_orchestration.operator_task_title(item)
    status = str(item.get("status") or "unavailable")
    output = "\n".join((
        f"[{title}]",
        f"Work item: {item.get('id')}",
        f"Status: {aos_orchestration.operator_status_label(status)}",
        f"Summary: Existing item read inline; no new queue item or agent invocation.",
        f"Files touched: {files_touched}",
        f"Validation: {validation}",
        f"Blockers: {blockers}",
        f"Next action: {next_action}",
        f"Receipt: {receipt_path or 'unavailable'}",
        f"Artifacts: {', '.join(artifacts) if artifacts else 'None reported'}",
        f"Recorded token accounting: {recorded_usage}",
        "Lookup token usage: no agent invocation",
    ))
    document_paths = [str(BASE_DIR / receipt_path)] if receipt_path and (BASE_DIR / receipt_path).is_file() else []
    return {
        "success": True,
        "accepted": True,
        "created": False,
        "output": output,
        "returncode": 0,
        "work_item_id": item.get("id"),
        "status": status,
        "receipt_path": receipt_path,
        "document_paths": document_paths,
        "artifacts": artifacts,
        "requested_target": "queue",
        "selected_route": "local_existing_item_read",
        "delegation_reason": "bounded existing-item receipt/status read",
        "codex_forbidden": "no",
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


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


_DISPATCH_PATH_PATTERNS = (
    re.compile(r"(?P<path>[A-Za-z]:\\[^\r\n`\"']+?)(?=(?:\s+(?:and|then)\s+(?:assess|review|compare|incorporate|implement|repair|build|test|validate)\b)|[.;,\n]|$)", re.IGNORECASE),
    re.compile(r"(?P<path>/(?:mnt/[a-z]|home|tmp)/[^\r\n`\"']+?)(?=(?:\s+(?:and|then)\s+(?:assess|review|compare|incorporate|implement|repair|build|test|validate)\b)|[.;,\n]|$)", re.IGNORECASE),
)
_DISPATCH_ASSESS_RE = re.compile(r"\b(?:assess(?:ment)?|review|compare|audit|inspect)\b", re.IGNORECASE)
_DISPATCH_IMPLEMENT_RE = re.compile(r"\b(?:implement|incorporate|repair|fix|build|create|modify|edit|update)\b", re.IGNORECASE)
_DISPATCH_VALIDATE_RE = re.compile(r"\b(?:tests?|testing|validate|validation|end[- ]to[- ]end|prove|proof)\b", re.IGNORECASE)
_DISPATCH_AGENT_RE = re.compile(r"\b(?:run|use|get|tell|ask)\s+(?:an?\s+)?(?:agent|workflow|hermes|codex|claude)\b", re.IGNORECASE)
_DISPATCH_ARTIFACT_RE = re.compile(r"\b(?:repository|repo|files?|folders?|artifacts?|codebase|workspace)\b", re.IGNORECASE)
_TELEGRAM_APPROVAL_PREFIX_RE = re.compile(
    r"^\s*(?:(?:i\s+)?approve(?:d)?|accept(?:ed)?|continue|resume|go\s+ahead|yes\s*,?\s*proceed)\b",
    re.IGNORECASE,
)
_TELEGRAM_APPROVAL_ITEM_RE = re.compile(r"\bAOS-\d{4}-\d{4}\b", re.IGNORECASE)
_TELEGRAM_SPLIT_WINDOW_SECONDS = 120
_TELEGRAM_CONTINUATION_RE = re.compile(
    r"^\s*(?:[-*•]\s+|\d+[.)]\s+|#{1,6}\s+|(?:validation|close\s*out|preserve\s+architecture)\b)",
    re.IGNORECASE,
)
_EXTERNAL_OR_DESTRUCTIVE_ACTION_RE = re.compile(
    r"\b(?:send(?:ing)?\b[^.;\n]{0,48}\b(?:email|draft|message)|"
    r"reply(?:ing)?(?:\s+to)?|forward(?:ing)?|schedule[-\s]?send)\b|"
    r"\b(?:change|update|replace|add|remove)(?:\s+(?:the\s+|a\s+))?recipients?\b|"
    r"\b(?:delete|remove)\b|"
    r"\b(?:credential|authentication|oauth|api[-\s]?key|secret)\b|"
    r"\b(?:recurring|scheduled)\s+(?:external\s+)?(?:job|task|send)\b|"
    r"\bgit\s+(?:commit|push)\b|\b(?:commit|push)\s+(?:to\s+)?git\b|"
    r"\b(?:publish|deploy|deployment)\b|"
    r"\b(?:pay|payment|transfer|money\s+movement|purchase)\b",
    re.IGNORECASE,
)
_NEGATED_EXTERNAL_ACTION_RE = re.compile(
    r"\b(?:do\s+not|don't|never|without|prohibit(?:s|ed|ing)?|block(?:s|ed|ing)?)\b[^.;\n]{0,48}$",
    re.IGNORECASE,
)


def _telegram_approval_intent(text: str) -> dict | None:
    """Recognize a bounded approval family without using a model or fuzzy task inference."""
    raw = str(text or "").strip()
    if not _TELEGRAM_APPROVAL_PREFIX_RE.search(raw):
        return None
    normalized = " ".join(raw.split())
    return {
        "normalized": normalized[:1000],
        "oversized": len(normalized) > 1000,
        "target_ids": sorted({match.group(0).upper() for match in _TELEGRAM_APPROVAL_ITEM_RE.finditer(normalized)}),
    }


def _telegram_split_request_guard(body: TaskRun) -> dict | None:
    """Merge a Telegram continuation into its existing oversized /work prompt."""
    if str(getattr(body, "source", "telegram") or "telegram").strip().casefold() != "telegram":
        return None
    text = str(body.task or "").strip()
    if not text or text.startswith("/") or not _TELEGRAM_CONTINUATION_RE.search(text):
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    candidates = []
    for item in _read_queue_items():
        run_prompt_path = str(item.get("run_prompt_path") or "").strip()
        if not re.fullmatch(r"queue/run_prompts/[A-Za-z0-9_.-]+\.md", run_prompt_path):
            continue
        prompt_path = BASE_DIR / run_prompt_path
        try:
            stored = prompt_path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if len(stored) <= _LONG_WORK_BODY_CHARS or not stored.casefold().startswith("/work") or not stored.endswith(":"):
            continue
        if not _telegram_item_matches_operator(item, body, explicit_id=False):
            continue
        created = _parse_record_timestamp(item.get("created_at"))
        if not created:
            continue
        age = (now - created.astimezone(datetime.timezone.utc)).total_seconds()
        if 0 <= age <= _TELEGRAM_SPLIT_WINDOW_SECONDS:
            candidates.append(item)
    if not candidates:
        return None
    prior = sorted(candidates, key=lambda row: str(row.get("created_at") or ""), reverse=True)[0]
    run_prompt_path = str(prior["run_prompt_path"])
    prompt_path = BASE_DIR / run_prompt_path
    with queue_write_lock(BASE_DIR):
        current = prompt_path.read_text(encoding="utf-8").rstrip()
        durable_replace_text(prompt_path, f"{current}\n{text.rstrip()}\n")
        items = _read_queue_items()
        stored_item = next((row for row in items if row.get("id") == prior.get("id")), None)
        if stored_item is not None:
            reasons = [str(value) for value in stored_item.get("needs_me") or []]
            if "consider decomposing" not in reasons:
                reasons.append("consider decomposing")
            stored_item["needs_me"] = reasons
            stored_item["updated_at"] = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            durable_replace_text(
                _queue_items_path(),
                "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in items),
            )
    return {
        "success": True,
        "accepted": True,
        "created": False,
        "duplicate": True,
        "state": "split-work-request-merged",
        "work_item_id": prior.get("id"),
        "runner_accepted": False,
        "output": "\n".join((
            "PASS",
            f"Merged the continuation into {aos_orchestration.operator_item_label(prior)}.",
            "No second work item or run-prompt file was created.",
        )),
        "returncode": 0,
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


def _telegram_item_conversation(item: dict) -> tuple[str, str]:
    dispatch = item.get("dispatch") if isinstance(item.get("dispatch"), dict) else {}
    source = str(item.get("source") or "").strip().lower()
    reply_to = str(
        item.get("reply_to") or item.get("chat_id") or item.get("telegram_chat_id")
        or dispatch.get("reply_to") or ""
    ).strip()
    return source, reply_to


def _safe_operator_telegram_chats() -> set[str]:
    """Read only the unprotected notification allowlist used by queue routing."""
    try:
        config = json.loads((BASE_DIR / "queue" / "notifications.json").read_text(encoding="utf-8"))
        values = ((config.get("allowlist") or {}).get("telegram") or [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return set()
    return {str(value).strip() for value in values if str(value).strip()}


def _telegram_item_matches_operator(item: dict, body: TaskRun, *, explicit_id: bool) -> bool:
    incoming_source = str(getattr(body, "source", "telegram") or "telegram").strip().lower()
    incoming_reply = str(getattr(body, "reply_to", "") or "").strip()
    item_source, item_reply = _telegram_item_conversation(item)
    requested_by = str(item.get("requested_by") or "").strip().casefold()
    if explicit_id and incoming_source == "telegram" and requested_by == "liam":
        if not incoming_reply or not item_reply or incoming_reply == item_reply:
            return True
    if item_source != incoming_source:
        return False
    if incoming_reply:
        if item_reply:
            return incoming_reply == item_reply
        return requested_by == "liam" and incoming_reply in _safe_operator_telegram_chats()
    return not item_reply and requested_by == "liam"


def _external_action_matches(text: str) -> list[str]:
    matches = []
    value = str(text or "")
    for match in _EXTERNAL_OR_DESTRUCTIVE_ACTION_RE.finditer(value):
        prefix = value[max(0, match.start() - 64):match.start()]
        if _NEGATED_EXTERNAL_ACTION_RE.search(prefix):
            continue
        action = " ".join(match.group(0).split()).lower()
        if action not in matches:
            matches.append(action)
    return matches


def _approval_external_boundaries(item: dict, approval_text: str) -> list[str]:
    values = [approval_text, item.get("title", ""), item.get("context", "")]
    values.extend(str(value) for value in item.get("allowed_actions") or [])
    matches = []
    for value in values:
        for match in _external_action_matches(value):
            if match not in matches:
                matches.append(match)
    return matches


def _telegram_approval_event_key(body: TaskRun, intent: dict) -> str:
    source = str(getattr(body, "source", "telegram") or "telegram").strip().casefold()
    reply_to = str(getattr(body, "reply_to", "") or "").strip()
    delivery_id = str(getattr(body, "delivery_id", "") or "").strip()
    stable_event = delivery_id or str(intent.get("normalized") or "").casefold()
    digest = hashlib.sha256(f"{source}\0{reply_to}\0{stable_event}".encode("utf-8")).hexdigest()
    return f"telegram-approval:{digest}"


def _approval_effect_replay(items: list[dict], event_key: str) -> tuple[dict, dict] | None:
    for item in items:
        effects = item.get("approval_effects")
        if isinstance(effects, dict) and isinstance(effects.get(event_key), dict):
            return item, effects[event_key]
    return None


def _approval_clarification(state: str, candidate_ids: list[str], message: str) -> dict:
    candidate_line = ", ".join(candidate_ids) if candidate_ids else "none"
    return {
        "success": False,
        "accepted": False,
        "created": False,
        "duplicate": False,
        "approval_routed": True,
        "clarification_required": True,
        "state": state,
        "candidate_ids": candidate_ids,
        "output": "\n".join((
            "NEEDS ATTENTION",
            message,
            f"Safe candidate IDs: {candidate_line}.",
            "No new work item was created and no runner or external action was started.",
        )),
        "returncode": 2,
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


def _approval_replay_closeout(item: dict, effect: dict) -> dict:
    status = str(item.get("status") or effect.get("target_status") or "")
    receipt_path = str(effect.get("receipt_path") or "")
    return {
        "success": True,
        "accepted": True,
        "created": False,
        "duplicate": True,
        "approval_routed": True,
        "state": "approval-replay",
        "work_item_id": item.get("id"),
        "status": status,
        "receipt_path": receipt_path,
        "runner_accepted": False,
        "output": aos_orchestration.format_operator_work_item_notification(
            item,
            status,
            summary="Approval event already applied; no duplicate transition or dispatch.",
            next_action="None",
            receipt_path=receipt_path,
            receipt_attached=bool(receipt_path),
        ),
        "returncode": 0,
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


def _save_approval_effect(item_id: str, event_key: str, **updates) -> dict:
    with queue_write_lock(BASE_DIR):
        queue_tool = _load_queue_tool()
        items = queue_tool.load_items(BASE_DIR)
        item = queue_tool.find_item(items, item_id)
        effect = item.setdefault("approval_effects", {}).setdefault(event_key, {})
        effect.update(updates)
        item["updated_at"] = queue_tool.now_iso()
        queue_tool.save_items(BASE_DIR, items)
        return item


def _approval_resume_receipt_path(item_id: str, event_key: str) -> str:
    digest = event_key.rsplit(":", 1)[-1][:16]
    return f"queue/receipts/{item_id}-telegram-approval-{digest}.md"


def _resume_needs_input_from_telegram(item: dict, event_key: str) -> dict:
    receipt_path = _approval_resume_receipt_path(str(item.get("id") or ""), event_key)
    target = BASE_DIR / receipt_path
    if not target.exists():
        durable_replace_text(target, "\n".join((
            "PASS",
            "",
            "Telegram approval routing:",
            f"- Work item ID: {item.get('id')}",
            "- Transition: needs_input -> agent_todo",
            "- Result: existing item resumed; no new work item created",
            "- External or destructive authority: not granted",
            "- Token usage: no agent invocation",
            "",
        )))
    refreshed = _queue_find_item(str(item.get("id") or ""))
    if refreshed.get("status") == "needs_input":
        receipt_attached = any(
            isinstance(row, dict) and row.get("path") == receipt_path
            for row in refreshed.get("receipts") or []
        )
        if receipt_attached:
            refreshed = _load_queue_tool().update_status(BASE_DIR, refreshed["id"], "agent_todo")
        else:
            refreshed = _load_queue_tool().attach_receipt(BASE_DIR, refreshed["id"], receipt_path, "agent_todo")
    runner = _accept_async_queue_runner(refreshed)
    refreshed = _queue_find_item(refreshed["id"])
    _save_approval_effect(
        refreshed["id"], event_key, status="applied", action="resume",
        target_status=refreshed.get("status"), receipt_path=receipt_path,
        runner_state=runner.get("state"), runner_mode=runner.get("mode"),
    )
    return {
        "success": True,
        "accepted": True,
        "created": False,
        "duplicate": False,
        "approval_routed": True,
        "state": "resumed",
        "work_item_id": refreshed["id"],
        "status": refreshed.get("status"),
        "receipt_path": receipt_path,
        "runner_available": runner.get("available", False),
        "runner_accepted": runner.get("accepted", False),
        "runner_state": runner.get("state", "unavailable"),
        "runner_mode": runner.get("mode", "existing_item"),
        "output": aos_orchestration.format_operator_work_item_notification(
            refreshed,
            refreshed.get("status"),
            summary="Existing needs_input item resumed; no new work item created.",
            next_action="None",
            receipt_path=receipt_path,
            receipt_attached=bool(receipt_path),
        ),
        "returncode": 0,
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


def _accept_human_review_from_telegram(item: dict, event_key: str) -> dict:
    refreshed = _queue_find_item(str(item.get("id") or ""))
    if refreshed.get("status") == "done":
        receipt_path = _queue_existing_review_receipt(refreshed, "done")
    else:
        closed = _close_queue_item_review(
            refreshed["id"],
            QueueReviewClose(status="done", review_note="Accepted through item-bound Telegram approval routing.", action="approve"),
            notify_telegram=False,
        )
        receipt_path = str(closed.get("receipt_path") or "")
        refreshed = _queue_find_item(refreshed["id"])
    _save_approval_effect(
        refreshed["id"], event_key, status="applied", action="accept",
        target_status=refreshed.get("status"), receipt_path=receipt_path,
    )
    return {
        "success": True,
        "accepted": True,
        "created": False,
        "duplicate": False,
        "approval_routed": True,
        "state": "accepted-review",
        "work_item_id": refreshed["id"],
        "status": refreshed.get("status"),
        "receipt_path": receipt_path,
        "runner_accepted": False,
        "output": aos_orchestration.format_operator_work_item_notification(
            refreshed,
            refreshed.get("status"),
            summary="Existing human_review item accepted; no new work item created.",
            next_action="None",
            receipt_path=receipt_path,
            receipt_attached=bool(receipt_path),
        ),
        "returncode": 0,
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


def _try_telegram_approval(body: TaskRun) -> dict | None:
    if str(getattr(body, "source", "telegram") or "telegram").strip().lower() != "telegram":
        return None
    intent = _telegram_approval_intent(body.task)
    if intent is None:
        return None
    if intent["oversized"]:
        return _approval_clarification(
            "approval-too-long", [],
            "Approval replies must be bounded; send the approval and any new substantive request separately.",
        )
    event_key = _telegram_approval_event_key(body, intent)
    pending_replay = _approval_effect_replay(_read_queue_items(), event_key)
    if pending_replay is not None and pending_replay[1].get("status") == "pending":
        if pending_replay[1].get("action") == "resume":
            return _resume_needs_input_from_telegram(pending_replay[0], event_key)
        return _accept_human_review_from_telegram(pending_replay[0], event_key)
    with queue_write_lock(BASE_DIR):
        queue_tool = _load_queue_tool()
        items = queue_tool.load_items(BASE_DIR)
        replay = _approval_effect_replay(items, event_key)
        if replay is not None and replay[1].get("status") == "applied":
            return _approval_replay_closeout(*replay)
        explicit_ids = intent["target_ids"]
        explicit = bool(explicit_ids)
        if explicit:
            candidates = [
                row for row in items
                if str(row.get("id") or "").upper() in explicit_ids
                and row.get("status") in {"needs_input", "human_review", "done"}
                and _telegram_item_matches_operator(row, body, explicit_id=True)
            ]
        else:
            candidates = [
                row for row in items
                if row.get("status") in {"needs_input", "human_review"}
                and _telegram_item_matches_operator(row, body, explicit_id=False)
            ]
        candidate_ids = sorted(aos_orchestration.operator_item_label(row) for row in candidates)
        if len(candidates) != 1:
            state = "approval-target-ambiguous" if len(candidates) > 1 else "approval-target-missing"
            message = (
                "Approval matches multiple pending items; reply with exactly one AOS item ID."
                if len(candidates) > 1
                else "No uniquely correlated pending approval exists; include the exact existing AOS item ID."
            )
            return _approval_clarification(state, candidate_ids, message)
        item = candidates[0]
        if item.get("status") == "done":
            return {
                **_approval_replay_closeout(item, {"target_status": "done"}),
                "duplicate": False,
                "state": "already-completed",
            }
        boundaries = _approval_external_boundaries(item, intent["normalized"])
        if boundaries:
            return _approval_clarification(
                "explicit-action-approval-required", [str(item.get("id") or "")],
                "This item proposes an external or destructive action. Generic approval cannot authorize it; use the item-bound gate naming the exact action and target.",
            ) | {"blocked_actions": boundaries}
        effect = item.setdefault("approval_effects", {}).setdefault(event_key, {
            "event": "telegram_approval",
            "status": "pending",
            "action": "resume" if item.get("status") == "needs_input" else "accept",
            "source": "telegram",
            "delivery_id": str(getattr(body, "delivery_id", "") or ""),
            "reply_to": str(getattr(body, "reply_to", "") or ""),
            "created_at": queue_tool.now_iso(),
        })
        queue_tool.save_items(BASE_DIR, items)
    if item.get("status") == "needs_input":
        return _resume_needs_input_from_telegram(item, event_key)
    return _accept_human_review_from_telegram(item, event_key)


def _dispatch_source_paths(text: str) -> list[str]:
    paths = []
    for pattern in _DISPATCH_PATH_PATTERNS:
        for match in pattern.finditer(str(text or "")):
            path = match.group("path").strip()
            if path and path not in paths:
                paths.append(path)
    return paths


def _substantial_dispatch_signals(text: str) -> list[str]:
    value = str(text or "")
    paths = _dispatch_source_paths(value)
    signals = []
    if paths:
        signals.append("supplied_path")
    if _DISPATCH_ASSESS_RE.search(value) and (_DISPATCH_ARTIFACT_RE.search(value) or paths):
        signals.append("file_assessment")
    if _DISPATCH_IMPLEMENT_RE.search(value):
        signals.append("implementation_or_artifact_change")
    if _DISPATCH_VALIDATE_RE.search(value):
        signals.append("validation_or_proof")
    if _looks_multi_step(value):
        signals.append("multiple_steps")
    if _DISPATCH_AGENT_RE.search(value):
        signals.append("explicit_agent_or_workflow")
    if _DISPATCH_ARTIFACT_RE.search(value):
        signals.append("repository_artifacts")
    return signals


def _dispatch_idempotency_key(task: str, source: str, delivery_id: str = "") -> str:
    source_key = str(source or "telegram").strip().lower() or "telegram"
    delivery_key = str(delivery_id or "").strip()
    instruction_key = " ".join(str(task or "").split()).casefold()
    stable_input = delivery_key if delivery_key else instruction_key
    digest = hashlib.sha256(f"{source_key}\0{stable_input}".encode("utf-8")).hexdigest()
    return f"telegram-dispatch:{digest}"


_LONG_WORK_BODY_CHARS = 4_000


def _long_work_prompt_path(idempotency_key: str) -> str:
    digest = idempotency_key.rsplit(":", 1)[-1]
    return f"queue/run_prompts/work_{digest[:24]}.md"


def _write_long_work_prompt(relative_path: str, body: str) -> None:
    target = BASE_DIR / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        durable_replace_text(target, body.rstrip() + "\n")


def _queue_runner_status(root: Path | None = None) -> dict:
    root = Path(root or BASE_DIR)
    pid_path = root / "logs" / "runtime" / "runner.pid"
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", errors="replace")
    except (OSError, ValueError):
        return {"available": False, "state": "unavailable", "pid": None}
    expected = str(root / "tools" / "aos-orchestration-runner.py")
    available = expected in cmdline
    return {"available": available, "state": "running" if available else "unavailable", "pid": pid if available else None}


def _accept_async_queue_runner(item: dict) -> dict:
    recurring = _queue_runner_status(BASE_DIR)
    if recurring["available"]:
        return {**recurring, "accepted": True, "mode": "recurring"}
    status = str(item.get("status") or "")
    if status != "agent_todo":
        return {
            "available": status == "agent_working",
            "accepted": status in {"agent_working", "human_review", "needs_input", "blocked", "done"},
            "state": status or "unavailable",
            "pid": None,
            "mode": "existing_item",
        }
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                str(BASE_DIR / "tools" / "aos-orchestration-runner.py"),
                "--root",
                str(BASE_DIR),
                "--dispatch-item",
                str(item.get("id") or ""),
            ],
            cwd=str(BASE_DIR),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as exc:
        return {
            "available": False,
            "accepted": False,
            "state": "unavailable",
            "pid": None,
            "mode": "one_shot",
            "reason": type(exc).__name__,
        }
    return {
        "available": True,
        "accepted": True,
        "state": "accepted",
        "pid": process.pid,
        "mode": "one_shot",
    }


def _create_async_dispatch_item(
    body: TaskRun,
    *,
    owner_override: str | None = None,
) -> tuple[dict, bool, list[str], list[str]]:
    text = str(body.task or "").strip()
    source = str(getattr(body, "source", "telegram") or "telegram").strip() or "telegram"
    delivery_id = str(getattr(body, "delivery_id", "") or "").strip()
    reply_to = str(getattr(body, "reply_to", "") or "").strip()
    paths = _dispatch_source_paths(text)
    signals = _substantial_dispatch_signals(text)
    owner = str(owner_override or _infer_queue_owner(text)).strip().lower()
    if _CODEX_FORBIDDEN_RE.search(text):
        owner = "hermes"
    elif owner == "unassigned":
        owner = "hermes"
    key = _dispatch_idempotency_key(text, source, delivery_id)
    oversized_work = text.casefold().startswith("/work") and len(text) > _LONG_WORK_BODY_CHARS
    run_prompt_path = _long_work_prompt_path(key) if oversized_work else ""
    if oversized_work:
        _write_long_work_prompt(run_prompt_path, text)
        paths = [*paths, run_prompt_path]
    tags = ["async_dispatch", "olmec", "deterministic_intake"]
    if source.casefold() == "telegram":
        tags.append("telegram")
    if oversized_work:
        tags.append("oversized_intake")
    args = argparse.Namespace(
        title=_cockpit_command_title(text),
        requested_by="Liam",
        owner_type="agent",
        owner=owner,
        status="agent_todo",
        priority=5,
        source=source,
        tags=",".join(tags),
        context=f"Run prompt file: {run_prompt_path}" if oversized_work else text,
        sources=",".join(paths),
        allowed_actions="local_read,local_edit,local_test",
        stop_conditions="external_send,secrets_exposure,destructive_action_outside_scope",
        definition_of_done="Complete the operator instruction, run relevant validation, attach a durable receipt, and return truthful success or failure state.",
        parent_id=None,
        step_index=None,
        depends_on="",
        on_complete="human_review",
        workbench=owner if owner in {"codex", "claude"} else "lane",
        review="none",
        run_prompt_path=run_prompt_path or None,
        needs_me=["consider decomposing"] if oversized_work else None,
        idempotency_key=key,
        inbound_route=f"{source}:/api/wsl/hermes",
        delivery_id=delivery_id,
        reply_to=reply_to,
        idempotency_duplicate=False,
    )
    item = _load_queue_tool().create_item(BASE_DIR, args)
    return item, not bool(args.idempotency_duplicate), paths, signals


def _async_dispatch_closeout(item: dict, created: bool, paths: list[str], signals: list[str]) -> dict:
    runner = _accept_async_queue_runner(item)
    state = "queued"
    action = "created" if created else "already queued"
    runner_line = "runner accepted" if runner["accepted"] else "runner unavailable; item remains queued"
    output = aos_orchestration.format_operator_work_item_notification(
        item,
        "agent_todo",
        summary=f"The task was {action} and {runner_line}.",
        next_action="None",
    )
    return {
        "success": True,
        "accepted": True,
        "created": created,
        "duplicate": not created,
        "output": output,
        "returncode": 0,
        "work_item_id": item["id"],
        "owner": item.get("owner"),
        "status": item.get("status"),
        "state": state,
        "runner_available": runner["available"],
        "runner_state": runner["state"],
        "runner_accepted": runner["accepted"],
        "runner_mode": runner["mode"],
        "request_returned_before_completion": True,
        "source_paths": paths,
        "routing_signals": signals or ["not_allowlisted_inline"],
        "requested_target": "queue",
        "selected_route": "async_queue",
        "delegation_reason": "deterministic non-inline Telegram dispatch",
        "codex_forbidden": "yes" if _CODEX_FORBIDDEN_RE.search(str(item.get("context") or "")) else "no",
        "token_usage": {"available": False, "no_agent_invocation": True},
        "token_usage_text": "Token usage: no agent invocation",
    }


def _queue_create_closeout(item: dict) -> dict:
    output = aos_orchestration.format_operator_work_item_notification(
        item,
        item.get("status"),
        summary=f"{aos_orchestration.operator_task_title(item)} was added to the local queue.",
        next_action="Review or claim the local queue item",
    ) + f"\nWork item ID: {item['id']}\nOwner: {item['owner']}\nStatus: {item['status']}"
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


def _is_hermes_orchestration_request(task: str) -> bool:
    """Require explicit Codex delegation plus an explicit coordinator/review instruction."""
    return bool(
        _EXPLICIT_TARGET_RE["codex"].search(str(task or ""))
        and not _CODEX_FORBIDDEN_RE.search(str(task or ""))
        and _HERMES_ORCHESTRATION_RE.search(str(task or ""))
    )


def _hermes_orchestration_plan_prompt(task: str) -> str:
    return "\n".join((
        "Act as Operating Hermes using the aos-orchestrator profile.",
        "Plan bounded Codex implementation children for the operator request below.",
        "Hermes coordinates and reviews only; Codex implements every child.",
        "Return one fenced JSON object and no prose outside it:",
        '{"title":"...","tasks":[{"title":"...","context":"...","definition_of_done":"..."}]}',
        "Use between 1 and 6 independent, locally executable children. Do not perform the implementation.",
        "Do not authorize external sends, destructive work, credential changes, commits, or pushes.",
        "",
        "Operator request:",
        str(task or "").strip(),
    ))


def _artifact_back_large_child_context(context: str) -> str:
    """Keep large Hermes-planned evidence out of a child prompt."""
    value = str(context or "").strip()
    if len(value.encode("utf-8")) <= 4_000:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    directory = BASE_DIR / "logs" / "codex_prompt_evidence"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"hermes-child-{digest[:20]}.txt"
    durable_replace_text(target, value if value.endswith("\n") else value + "\n")
    relative = target.relative_to(BASE_DIR).as_posix()
    return (
        f"Large child context is artifact-backed at `{relative}` "
        f"(sha256={digest}, bytes={len(value.encode('utf-8'))}). "
        "Inspect only relevant ranges; do not paste the artifact into the prompt or closeout."
    )


def _normalize_hermes_orchestration_plan(reply: str, task: str) -> dict | None:
    for candidate in _extract_json_objects(str(reply or "")):
        raw_tasks = candidate.get("tasks") or candidate.get("children") or candidate.get("steps")
        if not isinstance(raw_tasks, list) or not raw_tasks:
            continue
        children = []
        for index, raw in enumerate(raw_tasks[:6], start=1):
            if not isinstance(raw, dict):
                continue
            title = re.sub(r"\s+", " ", str(raw.get("title") or f"Codex child {index}")).strip()[:180]
            context = _artifact_back_large_child_context(str(raw.get("context") or task).strip())
            done = str(raw.get("definition_of_done") or raw.get("dod") or "").strip()[:2_000]
            if not done:
                done = "Implement the bounded child task, run relevant local validation, and leave a durable receipt."
            children.append({"title": title, "context": context, "definition_of_done": done})
        if children:
            return {
                "title": re.sub(r"\s+", " ", str(candidate.get("title") or "Hermes coordinated Codex workflow")).strip()[:180],
                "children": children,
            }
    return None


def _hermes_orchestration_existing(key: str) -> tuple[dict, list[dict]] | None:
    items = _read_queue_items()
    parent = next(
        (
            row for row in items
            if isinstance(row.get("dispatch"), dict)
            and row["dispatch"].get("idempotency_key") == key
            and "hermes_orchestration_parent" in {str(tag) for tag in row.get("tags") or []}
        ),
        None,
    )
    if not parent:
        return None
    children = sorted(
        [row for row in items if row.get("parent_id") == parent.get("id")],
        key=lambda row: (int(row.get("step_index") or 0), str(row.get("id") or "")),
    )
    return parent, children


def _create_hermes_orchestration_items(body: TaskRun, plan: dict, key: str) -> tuple[dict, list[dict]]:
    source = str(getattr(body, "source", "telegram") or "telegram").strip() or "telegram"
    queue_tool = _load_queue_tool()
    parent_args = argparse.Namespace(
        title=plan["title"], requested_by="Liam", owner_type="workflow", owner="hermes",
        status="agent_working", priority=8, source=source,
        tags="hermes_orchestration_parent,olmec", context=str(body.task or "").strip(), sources="",
        allowed_actions="local_read,local_edit,local_test",
        stop_conditions="external_send,secrets_exposure,destructive_action_outside_scope,git_commit,git_push",
        definition_of_done="Every bounded Codex child passes native Hermes review within at most three attempts.",
        parent_id=None, step_index=None, depends_on="", on_complete=None, workbench="hermes", review="model",
        idempotency_key=key, inbound_route=f"{source}:/api/wsl/hermes", delivery_id=str(getattr(body, "delivery_id", "") or ""),
        reply_to=str(getattr(body, "reply_to", "") or ""), idempotency_duplicate=False,
    )
    parent = queue_tool.create_item(BASE_DIR, parent_args)
    if parent_args.idempotency_duplicate:
        existing = _hermes_orchestration_existing(key)
        return existing if existing is not None else (parent, [])

    children = []
    for index, spec in enumerate(plan["children"], start=1):
        child_args = argparse.Namespace(
            title=spec["title"], requested_by="hermes", owner_type="agent", owner="codex",
            status="agent_todo", priority=8, source="hermes_orchestration",
            tags="async_dispatch,hermes_orchestration_child,olmec",
            context=spec["context"], sources="", allowed_actions="local_read,local_edit,local_test",
            stop_conditions="external_send,secrets_exposure,destructive_action_outside_scope,git_commit,git_push",
            definition_of_done=spec["definition_of_done"], parent_id=parent["id"], step_index=index,
            depends_on="", on_complete="done", workbench="codex", review="model",
            idempotency_key=f"{key}:child:{index}", inbound_route="hermes:aos-orchestrator",
            delivery_id="", reply_to="", idempotency_duplicate=False,
        )
        children.append(queue_tool.create_item(BASE_DIR, child_args))

    with queue_write_lock(BASE_DIR):
        items = queue_tool.load_items(BASE_DIR)
        ids = {parent["id"], *(child["id"] for child in children)}
        for row in items:
            if row.get("id") not in ids:
                continue
            row["orchestration"] = {
                "outer_coordinator": "hermes",
                "coordinator_profile": "aos-orchestrator",
                "implementer": "codex" if row.get("id") != parent["id"] else None,
                "max_attempts": 3,
                "liam_escalation_after_failed_attempt": 3,
            }
        queue_tool.save_items(BASE_DIR, items)
    refreshed = {row["id"]: row for row in _read_queue_items() if row.get("id") in ids}
    return refreshed[parent["id"]], [refreshed[child["id"]] for child in children]


def _hermes_orchestration_closeout(body: TaskRun) -> dict:
    key = _dispatch_idempotency_key(
        body.task,
        str(getattr(body, "source", "telegram") or "telegram"),
        str(getattr(body, "delivery_id", "") or ""),
    )
    existing = _hermes_orchestration_existing(key)
    if existing is not None:
        parent, children = existing
        return {
            "success": True, "accepted": True, "created": False, "duplicate": True,
            "work_item_id": parent.get("id"), "child_item_ids": [row.get("id") for row in children],
            "outer_coordinator": "hermes", "implementer": "codex", "selected_route": "hermes_orchestration",
            "requested_target": "hermes", "delegation_reason": "existing native Hermes orchestration workflow",
            "output": f"PASS\nExisting Hermes orchestration workflow: {parent.get('id')}\nCodex children: {', '.join(str(row.get('id')) for row in children)}",
            "token_usage": {"available": False, "no_agent_invocation": True},
            "token_usage_text": "Token usage: no agent invocation",
        }

    coordinator = _run_hermes_message(
        _hermes_orchestration_plan_prompt(body.task), role="coordinator", attempt=1,
        timeout=QUEUE_HERMES_REVIEW_TIMEOUT_SECONDS,
    )
    if not coordinator.get("success"):
        diagnostic = coordinator.get("stderr") or coordinator.get("output") or "Hermes did not start."
        return {
            "success": False, "accepted": False, "created": False,
            "requested_target": "hermes", "selected_route": "hermes_orchestration_failed",
            "outer_coordinator": "hermes", "codex_invoked": False,
            "delegation_reason": "native Hermes coordinator startup failed",
            "output": f"NEEDS ATTENTION\nHermes orchestration could not start.\nBlockers: {_bounded_hermes_answer(str(diagnostic), 700)}\nNo Codex child was started.",
            "token_usage": coordinator.get("token_usage") or {"available": False},
            "token_usage_text": coordinator.get("token_usage_text") or "Token usage: unavailable from current CLI output",
        }
    plan = _normalize_hermes_orchestration_plan(coordinator.get("reply") or coordinator.get("output") or "", body.task)
    if plan is None:
        return {
            "success": False, "accepted": False, "created": False,
            "requested_target": "hermes", "selected_route": "hermes_orchestration_failed",
            "outer_coordinator": "hermes", "codex_invoked": False,
            "delegation_reason": "native Hermes coordinator returned no bounded child plan",
            "output": "NEEDS ATTENTION\nHermes started but returned no valid bounded Codex child plan.\nNo Codex child was started.",
            "token_usage": coordinator.get("token_usage") or {"available": False},
            "token_usage_text": coordinator.get("token_usage_text") or "Token usage: unavailable from current CLI output",
        }
    parent, children = _create_hermes_orchestration_items(body, plan, key)
    runner_results = [_accept_async_queue_runner(child) for child in children]
    return {
        "success": True, "accepted": True, "created": True, "duplicate": False,
        "work_item_id": parent.get("id"), "child_item_ids": [row.get("id") for row in children],
        "outer_coordinator": "hermes", "coordinator_profile": "aos-orchestrator", "implementer": "codex",
        "selected_route": "hermes_orchestration", "requested_target": "hermes",
        "delegation_reason": "explicit Codex work plus coordinator/review instruction",
        "runner_accepted": all(row.get("accepted") for row in runner_results),
        "output": f"PASS\nHermes orchestration workflow: {parent.get('id')}\nCodex children: {', '.join(str(row.get('id')) for row in children)}\nHermes will review each child for up to three attempts; passing work closes without Liam review.",
        "token_usage": coordinator.get("token_usage") or {"available": False},
        "token_usage_text": coordinator.get("token_usage_text") or "Token usage: unavailable from current CLI output",
    }


def _run_composio_adapter(mode: str, subject: str | None = None, json_args: dict | None = None) -> dict:
    """Call the one shared Composio adapter; never create per-connector paths."""
    workspace = str(BASE_DIR)
    command = (
        f"cd {shlex.quote(workspace)}; python3 connectors/composio_access_adapter.py "
        f"{shlex.quote(mode)}"
    )
    if subject is not None:
        command += f" {shlex.quote(subject)}"
    if json_args is not None:
        payload = json.dumps(json_args, separators=(",", ":"))
        command += f" {shlex.quote(payload)}"
    result = _run_agentic_os_clean_bash(command, timeout=120)
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
    """Keep bounded operator reads inline and queue all substantive agent work."""
    if not body.task.strip():
        raise HTTPException(status_code=422, detail="task must not be empty")
    approval = _try_telegram_approval(body)
    if approval is not None:
        return approval
    split_guard = _telegram_split_request_guard(body)
    if split_guard is not None:
        return split_guard
    queue_text = _queue_create_text(body.task)
    if queue_text is not None:
        if not queue_text:
            raise HTTPException(status_code=422, detail="queue item text must not be empty")
        return _queue_create_closeout(_create_queue_item(queue_text))
    queue_read = _try_queue_read_task(body.task)
    if queue_read is not None:
        queue_read["timeout_contract"] = "inline_command"
        queue_read["timeout_seconds"] = INLINE_COMMAND_TIMEOUT_SECONDS
        return queue_read
    existing_read = _try_existing_item_read_task(body.task, body)
    if existing_read is not None:
        existing_read["timeout_contract"] = "inline_command"
        existing_read["timeout_seconds"] = INLINE_COMMAND_TIMEOUT_SECONDS
        return existing_read
    if _is_hermes_orchestration_request(body.task):
        return _hermes_orchestration_closeout(body)
    entry_route = _select_hermes_entry_route(body.task)
    if entry_route["selected_route"] in {"direct_codex", "direct_claude"}:
        target = "codex" if entry_route["selected_route"] == "direct_codex" else "claude"
        try:
            item, created, paths, signals = _create_async_dispatch_item(body, owner_override=target)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "accepted": False,
                    "state": "queue_creation_failed",
                    "reason": type(exc).__name__,
                    "message": f"The explicit {target} request was not queued and Hermes was not invoked.",
                },
            ) from exc
        result = _async_dispatch_closeout(item, created, paths, [f"explicit_{target}", *signals])
        result.update(entry_route)
        result["requested_target"] = target
        result["selected_route"] = entry_route["selected_route"]
        result["delegation_reason"] = f"explicit natural-language {target} delegation; Hermes not invoked"
        return result
    route = entry_route
    result = _run_hermes_message(body.task)
    if not result.get("success"):
        return _compact_agent_closeout(result, "hermes", "hermes", body.task, route)
    return _hermes_coordinator_closeout(result, body.task, route)


@app.post("/api/hermes/message")
def hermes_message(body: HermesMessage):
    """Send one direct, headless message through the project Hermes wrapper."""
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")
    original_text = body.text.strip()
    prompt_text = _hermes_decomposition_prompt(original_text) if _looks_multi_step(original_text) else original_text
    result = _run_hermes_message(prompt_text)
    if not result["success"]:
        raise HTTPException(status_code=502, detail=result)
    proposal = _normalize_chain_proposal(result.get("reply") or "", original_text, body.source_refs)
    if proposal:
        result["chain_proposal"] = proposal
        _append_hermes_decomposition_token_ledger(result)
    elif "?" in str(result.get("reply") or ""):
        question_item = _create_hermes_question_item(str(result.get("reply") or ""), body.source_refs)
        result["needs_input_item"] = _queue_detail_item(question_item)
    return result


@app.post("/api/wsl/claude")
def wsl_claude(body: TaskRun):
    """Route a task through aos-hermes to Claude inside AgenticOSClean."""
    if not body.task.strip():
        raise HTTPException(status_code=422, detail="task must not be empty")
    return _compact_agent_closeout(
        _run_wsl_prompt_command(
            'aos-hermes claude "$(<{prompt_file})"',
            body.task,
            AGENT_TIMEOUT_SECONDS,
            startup_timeout=AGENT_STARTUP_TIMEOUT_SECONDS,
        ),
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
    """Call the real Codex CLI directly in the authoritative Linux workspace."""
    if not body.task.strip():
        raise HTTPException(status_code=422, detail="task must not be empty")
    return _compact_agent_closeout(
        _run_codex_local(body.task),
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
    return {
        "status": "not_checked",
        "running": "unknown",
        "bridge_file": "not_checked",
        "env_file": "not_checked",
        "allowed_chats": "not_checked",
        "pilot_report_file": "not_checked",
        "pilot_report_count": "unknown",
        "operator_chat_configured": "unknown",
        "pilot_id": "unavailable",
        "reason": "Protected Telegram/North Shore runtime is outside the Linux-authority cutover and was not launched or inspected.",
        "workspace": str(BASE_DIR),
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

    _require_authority()
    workspace = BASE_DIR
    out_file = workspace / "connectors" / "composio_live_connections.txt"
    out_file.parent.mkdir(parents=True, exist_ok=True)

    composio = shutil.which("composio") or "composio"
    commands = [
        ("version", [composio, "version"]),
        ("whoami", [composio, "whoami"]),
        ("connections list", [composio, "connections", "list"]),
    ]

    sections = [
        "Agentic OS Composio CLI refresh",
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "Runtime: Linux/POSIX",
        f"CLI: {composio}",
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
    durable_replace_text(out_file, output + "\n")

    return {
        "success": ok,
        "output": output,
        "output_file": str(out_file),
    }
