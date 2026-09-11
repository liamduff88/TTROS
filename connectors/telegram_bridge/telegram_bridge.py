import hashlib
import json
import mimetypes
import os
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import fcntl

WORKSPACE = Path("/home/liam/agentic-os-live")
BRIDGE_DIR = WORKSPACE / "connectors" / "telegram_bridge"
ENV_FILE = BRIDGE_DIR / ".env"
ALLOWED_FILE = BRIDGE_DIR / "allowed_chats.json"
LOG_DIR = WORKSPACE / "logs"
RUNTIME_DIR = LOG_DIR / "runtime"
UPDATE_STATE_FILE = RUNTIME_DIR / "telegram_bridge_updates.json"
# Conversational state, deliberately NOT in allowed_chats.json, which is
# authorization/pilot config written non-atomically.
MODE_STATE_FILE = RUNTIME_DIR / "telegram_bridge_modes.json"
BRIDGE_LOCK_FILE = RUNTIME_DIR / "telegram_bridge.lock"
PILOT_ID = "northshore_honda_sales_demo"
BACKEND = "http://127.0.0.1:8010"
TOOLS_DIR = WORKSPACE / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import business_brain
import business_brain_inbox

LOG_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def load_token():
    if not ENV_FILE.exists():
        raise RuntimeError(".env file not found")
    for raw in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().upper()
        value = value.strip().strip('"').strip("'")
        if key in {"TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "TELEGRAM_TOKEN", "TOKEN"}:
            return value
    for raw in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" in raw and "TOKEN" in raw.upper():
            return raw.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("Telegram token variable not found in .env")


TOKEN = load_token()
API = f"https://api.telegram.org/bot{TOKEN}"


def _parse_chat_ids(raw):
    ids = []
    for part in re.split(r"[,;\s]+", raw or ""):
        value = part.strip()
        if re.fullmatch(r"-?\d+", value):
            ids.append(int(value))
    return ids


def _allowed_file():
    path = os.environ.get("TELEGRAM_ALLOWED_CHATS_FILE", "").strip()
    return Path(path).expanduser() if path else ALLOWED_FILE


def _env_allowed():
    operator_ids = _parse_chat_ids(os.environ.get("TELEGRAM_OPERATOR_CHAT_IDS", ""))
    pilots = {}
    for item in re.split(r"[,;\n]+", os.environ.get("TELEGRAM_PILOT_CHAT_IDS", "")):
        if not item.strip() or ":" not in item:
            continue
        chat_id, pilot_id = item.split(":", 1)
        chat_id = chat_id.strip()
        pilot_id = pilot_id.strip()
        if re.fullmatch(r"-?\d+", chat_id) and pilot_id:
            pilots[chat_id] = pilot_id
    return {"operator_chat_ids": operator_ids, "pilots": pilots}


def api(method, data=None, timeout=60):
    body = urllib.parse.urlencode(data or {}).encode("utf-8")
    req = urllib.request.Request(f"{API}/{method}", data=body)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


_CLOSEOUT_FIELDS = ("Files touched", "Validation", "Connector access", "Token usage", "Blockers", "Next action")
_RAW_METADATA = re.compile(
    r"(?i)(?:session\s*id|prompt\s*dump|command\s*transcript|raw\s+(?:codex|claude|hermes\s+)?transcript|sandbox\s+(?:metadata|mode|permissions))"
)
_QUEUE_OUTPUT_MARKER = re.compile(r"(?im)^\s*Work item(?:\s+ID)?\s*:")
_AOS_ID_RE = re.compile(r"\bAOS-\d{4}-\d{4}\b")
_DOC_REF_RE = re.compile(
    r"(?P<path>(?:queue/receipts|workflows/queue_artifacts|results|packets|logs)/[^\s`'\"<>]+?\.(?:md|txt|json|jsonl|pdf|html))"
)
_ALLOWED_DOC_PREFIXES = ("queue/receipts/", "workflows/queue_artifacts/", "results/", "packets/", "logs/")
_MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
SUBMISSION_ACK_TIMEOUT_SECONDS = 20
# Direct Hermes conversation includes deterministic Context Assembler work and
# one bounded model turn. Keep its client window above the backend's 90-second
# operator timeout without making Telegram intake unbounded.
AGENT_RESPONSE_TIMEOUT_SECONDS = 120
STATUS_BACKEND_TIMEOUT_SECONDS = 1.5
STATUS_SEND_TIMEOUT_SECONDS = 3
# David's executive route measured ~33s end to end (2026-08-11 proof). The
# delegate default of 20s would time out every call, so it gets its own budget.
DAVID_TIMEOUT_SECONDS = 180
MODE_DAVID = "david"
MODE_ORCHESTRATOR = "orchestrator"
# FIRST word only. Anchored at ^, so "Ask David, ..." mid-sentence never switches.
_MODE_SWITCH_RE = re.compile(r"^\s*(david|orchestrator)\s*[,:]\s*", re.IGNORECASE)
MAX_RECORDED_UPDATE_IDS = 512
_CAPTURE_COMMAND_RE = re.compile(r"^/(?:inbox|capture)(?:@[A-Za-z0-9_]+)?(?:\s+([\s\S]*))?$", re.IGNORECASE)
_SUPPORTED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx", ".rtf", ".csv", ".json", ".yaml", ".yml"}
_SUPPORTED_DOCUMENT_MIME_TYPES = {
    "text/plain", "text/markdown", "text/csv", "application/json", "application/pdf",
    "application/rtf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_DIRECT_ASYNC_WORK_RE = re.compile(r"^\s*/work\s+(?:codex|claude)\b", re.IGNORECASE)
_HERMES_COORDINATION_RE = re.compile(
    r"\b(?:coordinate|coordinator|oversee|orchestrate)\b"
    r"|\breview\s+(?:it|the\s+(?:work|result|receipt|diff|tests?))\b"
    r"|\bsend\s+(?:it|this|the\s+work)\s+back\b"
    r"|\b(?:request|make|apply)\s+(?:a\s+)?corrections?\b",
    re.IGNORECASE,
)
_UPDATE_STATE_LOCK = threading.Lock()
_MODE_STATE_LOCK = threading.Lock()
_AGENT_REQUEST_LOCK = threading.Lock()
_ACTIVE_AGENT_REQUESTS = set()
_BRIDGE_LOCK_HANDLE = None


def compact_telegram_closeout(text, success=None):
    """Make every outbound Telegram message a compact, single-line-field closeout."""
    raw = str(text or "").strip()
    first_line = raw.splitlines()[0].strip().upper() if raw else ""
    passed = success if success is not None else first_line != "NEEDS ATTENTION"
    values = {}
    for field in _CLOSEOUT_FIELDS:
        match = re.search(rf"(?im)^\s*{re.escape(field)}\s*:\s*([^\r\n]*)", raw)
        value = match.group(1).strip(" -*\t")[:700] if match else ""
        if value and not _RAW_METADATA.search(value):
            values[field] = value
    defaults = {
        "Files touched": "None reported",
        "Validation": raw.splitlines()[0][:700] if raw and not _RAW_METADATA.search(raw.splitlines()[0]) else ("Completed" if passed else "Failed"),
        "Connector access": "No connector action reported",
        "Token usage": "unavailable from current CLI output",
        "Blockers": "None" if passed else "See local logs",
        "Next action": "None" if passed else "Review local logs",
    }
    work_item = _extract_work_item_id(raw) or "unavailable"
    title = _extract_work_item_title(raw)
    final_state = _extract_final_state(raw, passed)
    if title and work_item != "unavailable":
        status = "done" if passed else "failed"
        summary = (
            f"{title} completed with final state {final_state}."
            if passed else f"{title} needs attention after final state {final_state}."
        )
        next_action = "None" if passed else "Review local logs"
        return "\n".join(
            [
                f"[{work_item} — {title}]",
                f"Work item: {work_item}",
                f"Status: {status}",
                f"Summary: {summary}",
                f"Next action: {next_action}",
                "Receipt: attached",
                f"Final state: {final_state}",
            ]
            + [f"{field}: {values.get(field) or defaults[field]}" for field in _CLOSEOUT_FIELDS]
        )
    return "\n".join(
        ["PASS" if passed else "NEEDS ATTENTION", f"Work item: {work_item}", f"Final state: {final_state}"]
        + [f"{field}: {values.get(field) or defaults[field]}" for field in _CLOSEOUT_FIELDS]
    )


def _extract_work_item_id(text):
    match = _AOS_ID_RE.search(str(text or ""))
    return match.group(0) if match else ""


def _extract_work_item_title(text):
    raw = str(text or "")
    bracket = re.search(r"(?m)^\s*\[([^\]\r\n]+)\]\s*$", raw)
    if bracket:
        bracket_text = bracket.group(1).strip()
        bracket_text = re.sub(r"^AOS-\d{4}-\d{4}\s+[—-]\s+", "", bracket_text)
        if bracket_text and not _AOS_ID_RE.fullmatch(bracket_text):
            return bracket_text[:160]
    for pattern in (
        r"(?im)^\s*Work item title\s*:\s*([^\r\n]+)",
        r"(?im)^\s*Task title\s*:\s*([^\r\n]+)",
        r"(?im)^\s*Title\s*:\s*([^\r\n]+)",
    ):
        match = re.search(pattern, raw)
        if match:
            title = re.sub(r"\s+", " ", match.group(1).strip(" -*\t"))
            if title and not _AOS_ID_RE.fullmatch(title):
                return title[:160]
    return ""


def _extract_final_state(text, passed):
    raw = str(text or "")
    for pattern in (
        r"(?im)^\s*Final state\s*:\s*([^\r\n]+)",
        r"(?im)^\s*Final status\s*:\s*([^\r\n]+)",
        r"(?im)^\s*Status\s*:\s*([^\r\n]+)",
    ):
        match = re.search(pattern, raw)
        if match:
            return match.group(1).strip(" -*\t")[:120]
    return "done" if passed else "needs_attention"


def _clean_doc_ref(path):
    text = str(path or "").strip().strip(".,);]")
    if not text.startswith(_ALLOWED_DOC_PREFIXES):
        return ""
    if ".." in Path(text).parts:
        return ""
    return text


def _is_completion_closeout(text):
    raw = str(text or "").strip()
    if not raw.startswith(("PASS", "NEEDS ATTENTION", "[")):
        return False
    if raw.startswith("[") and re.search(r"(?im)^\s*Work item\s*:", raw) and re.search(r"(?im)^\s*Status\s*:", raw):
        return True
    if re.search(r"(?im)^\s*Status\s*:\s*-?\s*(?:agent_todo|inbox|human_review|needs_input)\s*$", raw):
        return False
    return bool(re.search(r"(?im)^\s*(Files touched|Artifacts|Final state|Final status|Validation)\s*:", raw))


def document_paths_for_completion(result, text):
    """Return small local documents to attach to completed queue notifications."""
    raw = str(text or "")
    if not _is_completion_closeout(raw):
        return []
    refs = []
    if isinstance(result, dict):
        for key in ("receipt_path", "receipt", "artifact_path"):
            value = result.get(key)
            if isinstance(value, str):
                refs.append(value)
        for key in ("attachments", "artifact_paths", "proof_paths"):
            value = result.get(key)
            if isinstance(value, list):
                refs.extend(str(item) for item in value)
    item_id = _extract_work_item_id(raw)
    if item_id:
        refs.append(f"queue/receipts/{item_id}.md")
    refs.extend(match.group("path") for match in _DOC_REF_RE.finditer(raw))
    docs = []
    for ref in refs:
        cleaned = _clean_doc_ref(ref)
        if not cleaned:
            continue
        allowed_prefix = next((prefix for prefix in _ALLOWED_DOC_PREFIXES if cleaned.startswith(prefix)), "")
        try:
            workspace_root = WORKSPACE.resolve(strict=True)
            allowed_root = (WORKSPACE / allowed_prefix.rstrip("/")).resolve(strict=True)
            target = (WORKSPACE / cleaned).resolve(strict=True)
            if not allowed_root.is_relative_to(workspace_root):
                continue
            if not target.is_relative_to(allowed_root):
                continue
            if not target.is_file() or target.stat().st_size > _MAX_DOCUMENT_BYTES:
                continue
        except (OSError, RuntimeError):
            continue
        path_text = str(target)
        if path_text not in docs:
            docs.append(path_text)
    return docs


def is_queue_specific_output(text):
    return bool(_QUEUE_OUTPUT_MARKER.search(str(text or "")))


def is_queue_backend_result(result):
    if not isinstance(result, dict):
        return False
    output = str(result.get("output") or "")
    return (
        str(result.get("selected_route") or "") == "local_queue"
        or str(result.get("requested_target") or "") == "queue"
        or is_queue_specific_output(output)
    )


def _multipart_api(method, fields, files, timeout=60):
    boundary = f"----aos{int(time.time() * 1000)}"
    chunks = []
    for key, value in (fields or {}).items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for key, path in (files or {}).items():
        file_path = Path(path)
        filename = file_path.name
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode("utf-8"))
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        chunks.append(file_path.read_bytes())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    req = urllib.request.Request(
        f"{API}/{method}",
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def send_document(chat_id, document_path, caption=""):
    path = Path(document_path)
    if not path.is_file():
        log(f"send_document_missing chat={chat_id} path={path}")
        return False
    try:
        _multipart_api(
            "sendDocument",
            {"chat_id": str(chat_id), "caption": str(caption or "")[:1024]},
            {"document": str(path)},
            timeout=60,
        )
        return True
    except Exception as e:
        log(f"send_document_error chat={chat_id} path={path} error={type(e).__name__}")
        return False


def send(chat_id, text, preserve_format=False, document_paths=None, api_timeout=20):
    text = str(text or "").strip()
    if not preserve_format and not is_queue_specific_output(text):
        text = compact_telegram_closeout(text)
    if len(text) > 3500:
        text = text[:3400] + "\n\n[trimmed]"
    try:
        api("sendMessage", {"chat_id": str(chat_id), "text": text}, timeout=api_timeout)
        message_sent = True
    except Exception as e:
        log(f"send_error chat={chat_id} error={type(e).__name__}")
        message_sent = False
    caption = _receipt_caption(text)
    documents = []
    for document_path in document_paths or []:
        documents.append({"path": str(document_path), "sent": send_document(chat_id, document_path, caption=caption)})
    return {"message_sent": message_sent, "documents": documents}


def _receipt_caption(text):
    raw = str(text or "")
    title = _extract_work_item_title(raw)
    id_match = _AOS_ID_RE.search(raw)
    final_state = _extract_final_state(raw, True)
    status_suffix = f" {final_state}" if final_state else ""
    if title and id_match:
        return f"{id_match.group(0)} — {title}{status_suffix} receipt"
    if id_match:
        return f"{id_match.group(0)}{status_suffix} receipt"
    return "Receipt"


def send_completion(chat_id, text, document_paths=None, preserve_format=True):
    send(chat_id, text, preserve_format=preserve_format, document_paths=document_paths or [])


def log(message):
    stamp = datetime.now(timezone.utc).isoformat()
    with (LOG_DIR / "telegram_bridge.log").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": stamp, "message": message}, ensure_ascii=False) + "\n")


def load_allowed():
    allowed_file = _allowed_file()
    data = _env_allowed()
    if not allowed_file.exists():
        return data
    try:
        file_data = json.loads(allowed_file.read_text(encoding="utf-8"))
    except Exception:
        return data

    file_operator_ids = []
    if "operator_chat_ids" in file_data:
        raw_operator_ids = file_data.get("operator_chat_ids")
        if isinstance(raw_operator_ids, list):
            file_operator_ids = [
                int(chat_id)
                for chat_id in raw_operator_ids
                if re.fullmatch(r"-?\d+", str(chat_id))
            ]
        else:
            file_operator_ids = _parse_chat_ids(str(raw_operator_ids or ""))
    elif re.fullmatch(r"-?\d+", str(file_data.get("operator_chat_id", ""))):
        file_operator_ids = [int(file_data["operator_chat_id"])]

    data["operator_chat_ids"].extend(
        chat_id for chat_id in file_operator_ids if chat_id not in data["operator_chat_ids"]
    )
    data.setdefault("pilots", {})
    if isinstance(file_data.get("pilots"), dict):
        data["pilots"].update({
            str(chat_id): str(pilot_id)
            for chat_id, pilot_id in file_data["pilots"].items()
            if re.fullmatch(r"-?\d+", str(chat_id))
        })
    return data


def save_report(chat_id, text, source="natural_language"):
    pilots_dir = WORKSPACE / "pilots" / PILOT_ID
    pilots_dir.mkdir(parents=True, exist_ok=True)
    report_file = pilots_dir / "sales_reports.jsonl"
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "chat_id": chat_id,
        "pilot_id": PILOT_ID,
        "source": source,
        "text": text.strip()
    }
    with report_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _agent_request_timeout(task):
    raw = str(task or "")
    if _DIRECT_ASYNC_WORK_RE.search(raw) and not _HERMES_COORDINATION_RE.search(raw):
        return SUBMISSION_ACK_TIMEOUT_SECONDS
    return AGENT_RESPONSE_TIMEOUT_SECONDS


def post_agent(route, task, timeout=None, source="telegram", delivery_id="", reply_to=""):
    timeout = _agent_request_timeout(task) if timeout is None else timeout
    payload = json.dumps({
        "task": task,
        "source": source,
        "delivery_id": str(delivery_id or ""),
        "reply_to": str(reply_to or ""),
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BACKEND}{route}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def get_backend_status(timeout=STATUS_BACKEND_TIMEOUT_SECONDS):
    req = urllib.request.Request(f"{BACKEND}/api/wsl/status", method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        payload = json.loads(res.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("backend status returned a non-object response")
    return payload


def _capture_requested(message, text):
    return bool(_CAPTURE_COMMAND_RE.match(text or "") or _is_forwarded(message))


def _is_forwarded(message):
    return any(key in message for key in ("forward_origin", "forward_date", "forward_from", "forward_sender_name", "forward_from_chat"))


def _capture_text_payload(text):
    match = _CAPTURE_COMMAND_RE.match(text or "")
    return (match.group(1) or "") if match else str(text or "")


def _telegram_capture_id(message, kind):
    identity = f"{message.get('chat', {}).get('id', '')}:{message.get('message_id', '')}:{kind}"
    return f"telegram-{hashlib.sha256(identity.encode('utf-8')).hexdigest()}"


def _message_timestamp(message):
    try:
        return datetime.fromtimestamp(int(message.get("date")), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc)


def _download_telegram_file(file_id, *, max_bytes=business_brain_inbox.MAX_ATTACHMENT_BYTES):
    """Download one Telegram-owned file without logging its protected URL."""
    try:
        result = api("getFile", {"file_id": str(file_id)}, timeout=20).get("result") or {}
        file_path = str(result.get("file_path") or "")
        if not file_path or ".." in Path(file_path).parts or not re.fullmatch(r"[A-Za-z0-9_./-]+", file_path):
            raise ValueError
        request = urllib.request.Request(f"https://api.telegram.org/file/bot{TOKEN}/{file_path}")
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(max_bytes + 1)
    except Exception as exc:
        raise business_brain_inbox.InboxCaptureError("Telegram attachment download failed") from exc
    if len(data) > max_bytes:
        raise business_brain_inbox.InboxCaptureError("Telegram attachment exceeds the inbox size limit")
    return data


def _document_supported(document):
    name = business_brain_inbox.sanitize_filename(document.get("file_name") or "attachment.bin")
    mime = str(document.get("mime_type") or "").lower()
    return Path(name).suffix.lower() in _SUPPORTED_DOCUMENT_EXTENSIONS and (
        not mime or mime == "application/octet-stream" or mime in _SUPPORTED_DOCUMENT_MIME_TYPES
    )


def _declared_file_size(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        raise business_brain_inbox.InboxCaptureError("Telegram attachment size is invalid")


def _transcribe_voice_local(audio_path):
    """Run only an explicitly configured local argv adapter; never use cloud STT."""
    configured = os.environ.get("AOS_VOICE_TRANSCRIBE_COMMAND", "").strip()
    if not configured:
        return None, "unavailable: configure a local Whisper-compatible AOS_VOICE_TRANSCRIBE_COMMAND containing {audio}"
    try:
        argv = shlex.split(configured)
    except ValueError as exc:
        raise business_brain_inbox.InboxCaptureError("local voice transcription command is invalid") from exc
    if not argv or not any("{audio}" in value for value in argv):
        raise business_brain_inbox.InboxCaptureError("local voice transcription command must contain {audio}")
    argv = [value.replace("{audio}", str(audio_path)) for value in argv]
    try:
        result = subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise business_brain_inbox.InboxCaptureError("local voice transcription failed") from exc
    transcript = str(result.stdout or "").strip()
    if result.returncode or not transcript:
        raise business_brain_inbox.InboxCaptureError("local voice transcription failed")
    return transcript[:business_brain_inbox.MAX_TEXT_CHARS], "complete"


def capture_operator_message(message):
    """Capture one explicit or forwarded operator message without queue routing."""
    text = str(message.get("text") or message.get("caption") or "")
    payload = _capture_text_payload(text)
    forwarded = _is_forwarded(message)
    stamp = _message_timestamp(message)
    root = business_brain.BUSINESS_BRAIN_ROOT
    base_metadata = {"telegram_forwarded": forwarded}
    document = message.get("document") if isinstance(message.get("document"), dict) else None
    voice = message.get("voice") if isinstance(message.get("voice"), dict) else None

    if document:
        if not _document_supported(document):
            raise business_brain_inbox.InboxCaptureError("unsupported Telegram document type")
        if _declared_file_size(document.get("file_size")) > business_brain_inbox.MAX_ATTACHMENT_BYTES:
            raise business_brain_inbox.InboxCaptureError("Telegram attachment exceeds the inbox size limit")
        capture_id = _telegram_capture_id(message, "file")
        data = _download_telegram_file(document.get("file_id"))
        return business_brain_inbox.capture_attachment(
            data,
            original_filename=document.get("file_name") or "attachment.bin",
            mime_type=document.get("mime_type") or "application/octet-stream",
            capture_id=capture_id,
            captured_at=stamp,
            body=payload or "Attachment captured without transformation.",
            metadata={**base_metadata, "telegram_message_type": "file"},
            root=root,
        )

    if voice:
        if _declared_file_size(voice.get("file_size")) > business_brain_inbox.MAX_ATTACHMENT_BYTES:
            raise business_brain_inbox.InboxCaptureError("Telegram attachment exceeds the inbox size limit")
        capture_id = _telegram_capture_id(message, "voice")
        data = _download_telegram_file(voice.get("file_id"))
        with tempfile.NamedTemporaryFile(prefix="aos-voice-", suffix=".ogg") as temporary:
            temporary.write(data)
            temporary.flush()
            try:
                transcript, transcription_status = _transcribe_voice_local(Path(temporary.name))
            except business_brain_inbox.InboxCaptureError as exc:
                transcript, transcription_status = None, f"failed: {exc}"
        body = transcript or (payload if payload else "Voice note captured; transcription is unavailable on this host.")
        return business_brain_inbox.capture_attachment(
            data,
            original_filename="voice-note.ogg",
            mime_type=voice.get("mime_type") or "audio/ogg",
            capture_id=capture_id,
            captured_at=stamp,
            body=body,
            content_type="voice",
            metadata={
                **base_metadata,
                "telegram_message_type": "voice",
                "transcription_status": transcription_status,
            },
            root=root,
        )

    if not payload.strip():
        raise business_brain_inbox.InboxCaptureError("use /inbox <text>, attach a supported file, or forward content")
    return business_brain_inbox.capture_text(
        payload,
        source="telegram_bot",
        capture_id=_telegram_capture_id(message, "text"),
        captured_at=stamp,
        content_type="forwarded_text" if forwarded else "text",
        metadata={**base_metadata, "telegram_message_type": "text"},
        root=root,
    )


def format_operator_status(payload, mode="unregistered", chat_mode=MODE_ORCHESTRATOR):
    """Render only bounded operational fields from the backend status contract."""
    data = payload if isinstance(payload, dict) else {}
    bridge = data.get("bridge") if isinstance(data.get("bridge"), dict) else {}
    queue = data.get("queue") if isinstance(data.get("queue"), dict) else {}
    runner = data.get("runner") if isinstance(data.get("runner"), dict) else {}
    codex = data.get("codex") if isinstance(data.get("codex"), dict) else {}
    hermes = data.get("hermes") if isinstance(data.get("hermes"), dict) else {}
    local_route = data.get("local_agent_route") if isinstance(data.get("local_agent_route"), dict) else {}
    failure = data.get("last_route_failure") if isinstance(data.get("last_route_failure"), dict) else None
    state = "healthy" if data.get("state") == "healthy" and data.get("success") is True else "degraded"
    failure_text = "none recorded"
    if failure:
        failure_class = str(failure.get("failure_class") or "unclassified")[:80]
        stage = str(failure.get("stage") or "unknown stage")[:80]
        failure_text = f"{failure_class} at {stage}"
    return "\n".join((
        "PASS" if state == "healthy" else "NEEDS ATTENTION",
        f"Overall: {state}",
        f"Bridge: live handler; backend_process={str(bridge.get('state') or 'unknown')[:80]}; mode={mode}",
        f"Conversation mode: {chat_mode}",
        "Backend: ready",
        f"Queue: {str(queue.get('state') or 'unknown')[:80]}; items={int(queue.get('items') or 0)}; actionable={int(queue.get('actionable') or 0)}",
        f"Runner: {str(runner.get('state') or 'unknown')[:80]}",
        f"Codex: {str(codex.get('state') or 'unknown')[:80]}",
        f"Hermes: {str(hermes.get('state') or 'unknown')[:80]}",
        f"Local-agent readiness: {str(local_route.get('state') or 'unknown')[:80]}",
        f"Last route failure: {failure_text}",
        "Token usage: no agent invocation",
    ))


def backend_unavailable_status(mode="unregistered", reason="unavailable", chat_mode=MODE_ORCHESTRATOR):
    return "\n".join((
        "NEEDS ATTENTION",
        "Overall: degraded",
        f"Bridge: live handler; backend_process=unknown; mode={mode}",
        f"Conversation mode: {chat_mode}",
        "Backend: unavailable",
        "Queue: unknown",
        "Runner: unknown",
        "Codex: unknown",
        "Hermes: unknown",
        "Local-agent readiness: degraded",
        f"Last route failure: backend_status_{str(reason or 'unavailable')[:80]}",
        "Token usage: no agent invocation",
    ))


def summarize_agent_result(result):
    """Keep Telegram compact unless the backend already returned a queue closeout."""
    output = str(result.get("output") or "") if isinstance(result, dict) else ""
    success = bool(isinstance(result, dict) and result.get("success"))
    if isinstance(result, dict) and result.get("direct_reply") and output.strip():
        return output.strip()
    if is_queue_backend_result(result) and _is_completion_closeout(output):
        return compact_telegram_closeout(output, success=success)
    if is_queue_backend_result(result) and output.strip():
        return output.strip()
    return compact_telegram_closeout(output, success=success)


def preserve_agent_result_format(result, summary):
    """Keep direct conversation text and non-completion queue intake intact."""
    return bool(
        (isinstance(result, dict) and result.get("direct_reply"))
        or (is_queue_backend_result(result) and not _is_completion_closeout(summary))
    )


def deliver_agent_result(chat_id, result, reply_tag=""):
    """Deliver one backend result using its explicit formatting contract."""
    summary = summarize_agent_result(result)
    # Decide format and attachments on the UNTAGGED text so the existing
    # closeout parsers see exactly what they saw before Patch B.
    preserve = preserve_agent_result_format(result, summary)
    documents = document_paths_for_completion(result, summary)
    if reply_tag:
        summary = f"{reply_tag} {summary}"
        preserve = True
    return send(
        chat_id,
        summary,
        preserve_format=preserve,
        document_paths=documents,
    )


def failed_agent_closeout(message):
    return "\n".join([
        "NEEDS ATTENTION",
        "Files touched: None reported",
        f"Validation: {message}",
        "Connector access: No connector action reported",
        "Token usage: unavailable from current CLI output",
        "Blockers: Local agent route failed",
        "Next action: Review the backend and local agent logs",
    ])


def failed_conversation_reply(failure_class):
    """Return a direct executive-route failure without inventing queue work."""
    reason = "timed out before the reply reached Telegram" if failure_class == "TimeoutError" else "failed before the reply reached Telegram"
    return (
        f"I couldn't complete that executive reply because the local conversation route {reason}. "
        "No queue item or worker was created, and no fallback profile response was used."
    )


def _run_agent_request(chat_id, task, source, delivery_id, reply_tag=""):
    """Submit one request off the polling thread and send its intake result once."""
    try:
        result = post_agent(
            "/api/wsl/hermes",
            task,
            source=source,
            delivery_id=delivery_id,
            reply_to=str(chat_id),
        )
        if isinstance(result, dict) and result.get("duplicate"):
            log(f"agent_request_duplicate delivery_id={delivery_id}")
            return
        deliver_agent_result(chat_id, result, reply_tag=reply_tag)
    except Exception as exc:
        failure_class = type(exc).__name__
        is_work_request = bool(re.match(r"^\s*/work\b", str(task or ""), re.IGNORECASE))
        log(
            f"agent_request_failed route={'work' if is_work_request else 'conversation'} "
            f"failure={failure_class} delivery_id={delivery_id}"
        )
        if is_work_request:
            send(chat_id, failed_agent_closeout(f"Agent route failed: {failure_class}"))
        else:
            send(chat_id, failed_conversation_reply(failure_class), preserve_format=True)
    finally:
        with _AGENT_REQUEST_LOCK:
            _ACTIVE_AGENT_REQUESTS.discard(delivery_id)


def dispatch_agent_request(chat_id, task, source="telegram", delivery_id="", reply_tag=""):
    """Single-flight one Telegram delivery while keeping polling responsive."""
    request_id = str(delivery_id or "").strip()
    if not request_id:
        digest = hashlib.sha256(f"{chat_id}\0{task}".encode("utf-8")).hexdigest()
        request_id = f"{source}-request-{digest}"
    with _AGENT_REQUEST_LOCK:
        if request_id in _ACTIVE_AGENT_REQUESTS:
            log(f"agent_request_inflight_duplicate delivery_id={request_id}")
            return False
        _ACTIVE_AGENT_REQUESTS.add(request_id)
    worker = threading.Thread(
        target=_run_agent_request,
        args=(chat_id, task, source, request_id, reply_tag),
        name=f"telegram-agent-{request_id[-16:]}",
        daemon=True,
    )
    try:
        worker.start()
    except Exception:
        with _AGENT_REQUEST_LOCK:
            _ACTIVE_AGENT_REQUESTS.discard(request_id)
        raise
    return True


# Lane keys accepted by /delegate. Values are the queue owner, which must be the
# LANE key from queue/lane_profiles.json, never a Hermes profile name.
DELEGATION_LANES = {
    "revenue": "revenue",
    "marketing": "marketing",
    "delivery": "delivery",
    "operations": "operations",
    "ops": "operations",
    "orchestrator": "orchestrator",
}

# next_async_item() in the orchestration runner only ever considers items carrying
# this tag. Without it an item is created and then never dispatches.
ASYNC_DISPATCH_TAG = "async_dispatch"
QUEUE_CREATE_ROUTE = "/api/queue/items"
ASK_DAVID_ROUTE = "/api/dashboard/ask-david"
DELEGATE_TIMEOUT_SECONDS = 20

# /chain has to go through David because decomposing the objective is the point.
# Routed as an explicit /work request so the backend conversation-path guard
# ("only an explicit /work request may create or execute work") does not apply.
CHAIN_INSTRUCTION = (
    "\n\n---\n"
    "Break the objective above into the smallest sensible sequence of steps.\n"
    "\n"
    "Use the queue MCP tool named delegate_task - the one that returns work item ids of "
    "the form AOS-YYYY-NNNN. Do not use Hermes native delegation or any other handoff "
    "mechanism. If a delegation returns an id that is not in AOS-YYYY-NNNN form, you used "
    "the wrong tool: stop and say so rather than continuing.\n"
    "\n"
    "Call delegate_task once per step. For each one set:\n"
    "  delegate_to  - revenue, marketing, delivery, ops or orchestrator\n"
    "  depends_on   - the AOS id returned by the previous step, as the parameter, not "
    "as text inside context. The first step leaves it empty.\n"
    "  context      - self-contained, since the receiving agent has no memory of this.\n"
    "\n"
    "Do not do the work yourself and do not poll for results. Reply with the ordered AOS "
    "ids, the lane each went to, and one line on what each will do."
)


def post_backend_json(route, payload, timeout=DELEGATE_TIMEOUT_SECONDS):
    """POST one JSON body to the local backend and return the decoded response."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{BACKEND}{route}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_chat_modes():
    """Read the per-chat conversation mode map. Missing or corrupt -> empty."""
    try:
        payload = json.loads(MODE_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    modes = payload.get("chat_modes") if isinstance(payload, dict) else {}
    if not isinstance(modes, dict):
        return {}
    return {
        str(chat_id): str(mode)
        for chat_id, mode in modes.items()
        if str(mode) in {MODE_DAVID, MODE_ORCHESTRATOR}
    }


def get_chat_mode(chat_id):
    """Default is orchestrator: nothing changes until the operator says David."""
    with _MODE_STATE_LOCK:
        return _load_chat_modes().get(str(chat_id), MODE_ORCHESTRATOR)


def set_chat_mode(chat_id, mode):
    """Durably persist one chat's mode using the claim_update atomic pattern."""
    if mode not in {MODE_DAVID, MODE_ORCHESTRATOR}:
        raise ValueError(f"unknown chat mode: {mode}")
    with _MODE_STATE_LOCK:
        modes = _load_chat_modes()
        modes[str(chat_id)] = mode
        MODE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            prefix=".telegram_bridge_modes.",
            suffix=".tmp",
            dir=MODE_STATE_FILE.parent,
            delete=False,
        )
        temporary = Path(handle.name)
        try:
            with handle:
                json.dump({"chat_modes": modes}, handle, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, MODE_STATE_FILE)
        except Exception:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise
    return mode


def resolve_chat_mode(chat_id, text):
    """Apply a leading "David,"/"Orchestrator:" switch. FIRST word only.

    Returns (mode, remaining_text, switched). Without a leading token the stored
    mode is returned unchanged, which is what makes the mode sticky.
    """
    raw = str(text or "")
    match = _MODE_SWITCH_RE.match(raw)
    if not match:
        return get_chat_mode(chat_id), raw.strip(), False
    mode = match.group(1).lower()
    set_chat_mode(chat_id, mode)
    log(f"chat_mode_switched chat={chat_id} mode={mode}")
    return mode, raw[match.end():].strip(), True


def format_david_reply(result):
    """Render one ask-david response for Telegram, tagged with the active mode."""
    data = result if isinstance(result, dict) else {}
    kind = str(data.get("kind") or "")
    if kind == "queue_created":
        item = data.get("item") if isinstance(data.get("item"), dict) else {}
        item_id = str(item.get("id") or data.get("item_id") or "unavailable")
        owner = str(data.get("owner") or item.get("owner") or "hermes")
        lines = [f"[David] Queued {item_id} to {owner}."]
        handed = str(data.get("handed_objective") or "").strip()
        if handed:
            lines.append(f"Handed to Hermes: \"{handed}\"")
        else:
            lines.append("Handed to Hermes: (not reported by the backend)")
        note = str(data.get("david_note") or "").strip()
        if note:
            lines.append("")
            lines.append(note)
        lines.append("")
        lines.append("Check progress with /status.")
        return "\n".join(lines)
    body = ""
    for key in ("response", "output", "message", "text", "summary"):
        candidate = str(data.get(key) or "").strip()
        if candidate:
            body = candidate
            break
    if not body:
        body = f"David replied with no text (kind={kind or 'unknown'})."
    return f"[David] {body}"


def _run_david_request(chat_id, text, delivery_id):
    """Ask David off the polling thread; ~33s is normal for this route."""
    try:
        result = post_backend_json(
            ASK_DAVID_ROUTE,
            {"text": text},
            timeout=DAVID_TIMEOUT_SECONDS,
        )
        kind = str(result.get("kind") or "unknown") if isinstance(result, dict) else "unknown"
        log(f"david_reply_delivered chat={chat_id} kind={kind} delivery_id={delivery_id}")
        send(chat_id, format_david_reply(result), preserve_format=True)
    except Exception as exc:
        failure_class = type(exc).__name__
        log(f"david_request_failed chat={chat_id} failure={failure_class} delivery_id={delivery_id}")
        send(
            chat_id,
            "[David] "
            + failed_conversation_reply(failure_class)
            + "\nStill in David mode. Send \"Orchestrator, ...\" to switch back.",
            preserve_format=True,
        )
    finally:
        with _AGENT_REQUEST_LOCK:
            _ACTIVE_AGENT_REQUESTS.discard(delivery_id)


def dispatch_david_request(chat_id, task, source="telegram", delivery_id=""):
    """Single-flight David exactly the way dispatch_agent_request single-flights Hermes."""
    request_id = str(delivery_id or "").strip()
    if not request_id:
        digest = hashlib.sha256(f"{chat_id}\0david\0{task}".encode("utf-8")).hexdigest()
        request_id = f"{source}-david-{digest}"
    with _AGENT_REQUEST_LOCK:
        if request_id in _ACTIVE_AGENT_REQUESTS:
            log(f"david_request_inflight_duplicate delivery_id={request_id}")
            return False
        _ACTIVE_AGENT_REQUESTS.add(request_id)
    worker = threading.Thread(
        target=_run_david_request,
        args=(chat_id, task, request_id),
        name=f"telegram-david-{request_id[-16:]}",
        daemon=True,
    )
    try:
        worker.start()
    except Exception:
        with _AGENT_REQUEST_LOCK:
            _ACTIVE_AGENT_REQUESTS.discard(request_id)
        raise
    return True


def _delegation_title(task):
    """First sentence of the request, bounded to the queue title limit."""
    stripped = str(task or "").strip()
    first = re.split(r"(?<=[.!?])\s+", stripped)[0].strip() if stripped else ""
    return (first or stripped)[:150]


def handle_delegate(chat_id, text):
    """Create one queue item owned by a business lane. No model in the loop."""
    parts = text.split(" ", 2)
    usage = "Use: /delegate revenue|marketing|delivery|operations|orchestrator <task>"
    if len(parts) < 3 or not parts[2].strip():
        send(chat_id, usage, preserve_format=True)
        return
    lane = DELEGATION_LANES.get(parts[1].strip().lower())
    if not lane:
        send(chat_id, f"Unknown lane: {parts[1].strip()}\n{usage}", preserve_format=True)
        return

    task = parts[2].strip()
    payload = {
        "title": _delegation_title(task),
        "owner": lane,
        "priority": "normal",
        "tags": ASYNC_DISPATCH_TAG,
        "source": "telegram/delegate",
        "context": task,
        "definition_of_done": (
            "The task described in context is complete and a receipt records what was done."
        ),
    }
    try:
        result = post_backend_json(QUEUE_CREATE_ROUTE, payload)
    except Exception as exc:
        log(f"delegate_failed lane={lane} error={type(exc).__name__}")
        send(
            chat_id,
            f"NEEDS ATTENTION\nDelegation failed: {type(exc).__name__}. No work item was created.",
            preserve_format=True,
        )
        return

    item = result.get("item") if isinstance(result, dict) else None
    item_id = (item or {}).get("id") or "unavailable"
    log(f"delegate_created item={item_id} lane={lane}")
    send(
        chat_id,
        f"Queued {item_id} to {lane}.\nThe runner picks it up within about five seconds.\nCheck progress with /status.",
        preserve_format=True,
    )


def handle_chain(chat_id, text, source="telegram", delivery_id=""):
    """Ask David to decompose an objective and file it as a depends_on sequence."""
    objective = text.split(" ", 1)[1].strip() if " " in text else ""
    if not objective:
        send(chat_id, "Use: /chain <objective to break into steps>", preserve_format=True)
        return
    # Objective leads so the backend derives a readable work item title from it;
    # the instruction follows the separator.
    dispatch_agent_request(
        chat_id,
        f"/work hermes {objective}{CHAIN_INSTRUCTION}",
        source=source,
        delivery_id=delivery_id,
    )


def handle_operator(chat_id, text, source="telegram", delivery_id=""):
    if text.startswith("/delegate"):
        handle_delegate(chat_id, text)
        return

    if text.startswith("/chain"):
        handle_chain(chat_id, text, source=source, delivery_id=delivery_id)
        return

    if text.startswith("/work "):
        parts = text.split(" ", 2)
        if len(parts) < 3 or parts[1].lower() not in {"codex", "claude", "hermes"}:
            send(
                chat_id,
                "Use: /work codex|claude|hermes <task>\nTo hand work to a business lane use /delegate instead.",
                preserve_format=True,
            )
            return
        target = parts[1].lower()
        task = parts[2].strip()
        dispatch_agent_request(
            chat_id,
            f"/work {target} {task}",
            source=source,
            delivery_id=delivery_id,
        )
        return

    if text.startswith("/pilot_add "):
        parts = text.split()
        if len(parts) >= 3:
            data = load_allowed()
            data.setdefault("pilots", {})[parts[1]] = parts[2]
            allowed_file = _allowed_file()
            allowed_file.parent.mkdir(parents=True, exist_ok=True)
            allowed_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            send(chat_id, "Pilot added.", preserve_format=True)
        else:
            send(chat_id, "Use: /pilot_add <chat_id> <pilot_id>", preserve_format=True)
        return

    if text.startswith("/"):
        send(
            chat_id,
            "Commands:\n"
            "/status\n"
            "/inbox <text>\n"
            "/delegate <lane> <task>  - hand work to revenue, marketing, delivery, operations or orchestrator\n"
            "/chain <objective>       - David breaks it into steps and runs them in order\n"
            "/work codex|claude|hermes <task>\n"
            "/pilot_add <chat_id> <pilot_id>",
            preserve_format=True,
        )
        return

    # Every slash command has already returned above, so mode never sees one.
    mode, remainder, switched = resolve_chat_mode(chat_id, text)
    if switched and not remainder:
        target = "David" if mode == MODE_DAVID else "the orchestrator"
        send(
            chat_id,
            f"[{mode.capitalize()}] Mode set. Messages now go to {target} until you switch back.",
            preserve_format=True,
        )
        return

    if mode == MODE_DAVID:
        dispatch_david_request(chat_id, remainder, source=source, delivery_id=delivery_id)
        return

    dispatch_agent_request(
        chat_id,
        remainder,
        source=source,
        delivery_id=delivery_id,
        reply_tag="[Orchestrator]",
    )


def handle_message(msg, source="telegram", delivery_id=""):
    chat = msg.get("chat") or {}
    chat_id = int(chat.get("id"))
    text = (msg.get("text") or msg.get("caption") or "").strip()

    allowed = load_allowed()
    is_operator = chat_id in set(allowed.get("operator_chat_ids", []))
    pilot_id = allowed.get("pilots", {}).get(str(chat_id))

    if text.startswith("/status"):
        mode = "operator" if is_operator else ("pilot" if pilot_id else "unregistered")
        chat_mode = get_chat_mode(chat_id) if is_operator else MODE_ORCHESTRATOR
        try:
            status = format_operator_status(get_backend_status(), mode=mode, chat_mode=chat_mode)
        except Exception as exc:
            status = backend_unavailable_status(
                mode=mode,
                reason=type(exc).__name__,
                chat_mode=chat_mode,
            )
        send(chat_id, status, preserve_format=True, api_timeout=STATUS_SEND_TIMEOUT_SECONDS)
        return

    if text.startswith("/whoami"):
        send(chat_id, f"chat_id={chat_id}", api_timeout=STATUS_SEND_TIMEOUT_SECONDS)
        return

    if is_operator and _capture_requested(msg, text):
        try:
            capture = capture_operator_message(msg)
            acknowledgement = "Already captured ✓" if capture.duplicate else "Captured ✓"
        except business_brain_inbox.InboxCaptureError as exc:
            acknowledgement = f"Capture failed: {exc}"
        send(chat_id, acknowledgement, preserve_format=True)
        return

    if not text:
        return

    if is_operator:
        handle_operator(chat_id, text, source=source, delivery_id=delivery_id)
        return

    if pilot_id == PILOT_ID:
        if text.startswith("/report "):
            save_report(chat_id, text[len("/report "):], source="slash_report")
            send(chat_id, "Report saved.")
            return
        if text.startswith("/"):
            send(chat_id, "Send a normal sales update, or use /report <text>.")
            return
        save_report(chat_id, text, source="natural_language")
        send(chat_id, "Report saved.")
        return

    if text.startswith("/"):
        send(chat_id, f"Unregistered chat. Send /whoami to get chat_id={chat_id}")


def _load_recorded_update_ids():
    try:
        payload = json.loads(UPDATE_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    values = payload.get("processed_update_ids") if isinstance(payload, dict) else []
    return sorted({
        int(value) for value in values
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0
    })


def claim_update(update_id):
    """Durably claim a Telegram update before dispatching any agent work."""
    value = int(update_id)
    with _UPDATE_STATE_LOCK:
        recorded = _load_recorded_update_ids()
        if value in recorded:
            return False
        recorded = sorted([*recorded, value])[-MAX_RECORDED_UPDATE_IDS:]
        UPDATE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            prefix=".telegram_bridge_updates.",
            suffix=".tmp",
            dir=UPDATE_STATE_FILE.parent,
            delete=False,
        )
        temporary = Path(handle.name)
        try:
            with handle:
                json.dump({"processed_update_ids": recorded}, handle, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, UPDATE_STATE_FILE)
        except Exception:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise
    return True


def acquire_bridge_singleton():
    """Hold one canonical Linux bridge lock without killing unrelated processes."""
    global _BRIDGE_LOCK_HANDLE
    BRIDGE_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle = BRIDGE_LOCK_FILE.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return False
    handle.seek(0)
    handle.truncate()
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    os.fsync(handle.fileno())
    _BRIDGE_LOCK_HANDLE = handle
    return True


def main():
    if not acquire_bridge_singleton():
        print("PASS bridge_already_running", flush=True)
        return
    recorded = _load_recorded_update_ids()
    offset = (recorded[-1] + 1) if recorded else 0
    me = api("getMe", {}, timeout=20).get("result", {})
    load_allowed()
    print(f"PASS bridge_live bot=@{me.get('username')} operator_configured={bool(load_allowed().get('operator_chat_ids'))}", flush=True)
    log("bridge_live")
    while True:
        try:
            res = api("getUpdates", {"timeout": "45", "offset": str(offset)}, timeout=60)
            for update in res.get("result", []):
                update_id = int(update.get("update_id", 0))
                offset = max(offset, update_id + 1)
                if not claim_update(update_id):
                    log(f"duplicate_update update_id={update_id}")
                    continue
                msg = update.get("message") or update.get("edited_message")
                if msg:
                    handle_message(msg, delivery_id=f"telegram-update-{update_id}")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log(f"loop_error {type(e).__name__}")
            time.sleep(3)


if __name__ == "__main__":
    main()
