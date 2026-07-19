import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path("/home/liam/agentic-os-live")
BRIDGE_DIR = WORKSPACE / "connectors" / "telegram_bridge"
ENV_FILE = BRIDGE_DIR / ".env"
ALLOWED_FILE = BRIDGE_DIR / "allowed_chats.json"
LOG_DIR = WORKSPACE / "logs"
PILOT_ID = "northshore_honda_sales_demo"
BACKEND = "http://127.0.0.1:8010"

LOG_DIR.mkdir(parents=True, exist_ok=True)


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
AGENT_RESPONSE_TIMEOUT_SECONDS = 180
_DIRECT_ASYNC_WORK_RE = re.compile(r"^\s*/work\s+(?:codex|claude)\b", re.IGNORECASE)
_HERMES_COORDINATION_RE = re.compile(
    r"\b(?:coordinate|coordinator|oversee|orchestrate)\b"
    r"|\breview\s+(?:it|the\s+(?:work|result|receipt|diff|tests?))\b"
    r"|\bsend\s+(?:it|this|the\s+work)\s+back\b"
    r"|\b(?:request|make|apply)\s+(?:a\s+)?corrections?\b",
    re.IGNORECASE,
)


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


def send(chat_id, text, preserve_format=False, document_paths=None):
    text = str(text or "").strip()
    if not preserve_format and not is_queue_specific_output(text):
        text = compact_telegram_closeout(text)
    if len(text) > 3500:
        text = text[:3400] + "\n\n[trimmed]"
    try:
        api("sendMessage", {"chat_id": str(chat_id), "text": text}, timeout=20)
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


def post_agent(route, task, timeout=None, source="telegram"):
    timeout = _agent_request_timeout(task) if timeout is None else timeout
    payload = json.dumps({"task": task, "source": source}).encode("utf-8")
    req = urllib.request.Request(
        f"{BACKEND}{route}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def get_backend_status(timeout=5):
    req = urllib.request.Request(f"{BACKEND}/api/wsl/status", method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        payload = json.loads(res.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("backend status returned a non-object response")
    return payload


def format_operator_status(payload, mode="unregistered"):
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
        "Backend: ready",
        f"Queue: {str(queue.get('state') or 'unknown')[:80]}; items={int(queue.get('items') or 0)}; actionable={int(queue.get('actionable') or 0)}",
        f"Runner: {str(runner.get('state') or 'unknown')[:80]}",
        f"Codex: {str(codex.get('state') or 'unknown')[:80]}",
        f"Hermes: {str(hermes.get('state') or 'unknown')[:80]}",
        f"Local-agent readiness: {str(local_route.get('state') or 'unknown')[:80]}",
        f"Last route failure: {failure_text}",
        "Token usage: no agent invocation",
    ))


def backend_unavailable_status(mode="unregistered", reason="unavailable"):
    return "\n".join((
        "NEEDS ATTENTION",
        "Overall: degraded",
        f"Bridge: live handler; backend_process=unknown; mode={mode}",
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
    if is_queue_backend_result(result) and _is_completion_closeout(output):
        return compact_telegram_closeout(output, success=success)
    if is_queue_backend_result(result) and output.strip():
        return output.strip()
    return compact_telegram_closeout(output, success=success)


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


def handle_operator(chat_id, text, source="telegram"):
    if text.startswith("/work "):
        parts = text.split(" ", 2)
        if len(parts) < 3 or parts[1].lower() not in {"codex", "claude", "hermes"}:
            send(chat_id, "Use: /work codex|claude|hermes <task>")
            return
        target = parts[1].lower()
        task = parts[2].strip()
        try:
            result = post_agent("/api/wsl/hermes", f"/work {target} {task}", source=source)
            summary = summarize_agent_result(result)
            send(
                chat_id,
                summary,
                preserve_format=is_queue_backend_result(result) and not _is_completion_closeout(summary),
                document_paths=document_paths_for_completion(result, summary),
            )
        except Exception as e:
            send(chat_id, failed_agent_closeout(f"{target} route failed: {type(e).__name__}"))
        return

    if text.startswith("/pilot_add "):
        parts = text.split()
        if len(parts) >= 3:
            data = load_allowed()
            data.setdefault("pilots", {})[parts[1]] = parts[2]
            allowed_file = _allowed_file()
            allowed_file.parent.mkdir(parents=True, exist_ok=True)
            allowed_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            send(chat_id, "Pilot added.")
        else:
            send(chat_id, "Use: /pilot_add <chat_id> <pilot_id>")
        return

    if text.startswith("/"):
        send(chat_id, "Commands: /status, /work codex|claude|hermes <task>, /pilot_add <chat_id> <pilot_id>")
        return

    try:
        result = post_agent("/api/wsl/hermes", text, source=source)
        summary = summarize_agent_result(result)
        send(
            chat_id,
            summary,
            preserve_format=is_queue_backend_result(result) and not _is_completion_closeout(summary),
            document_paths=document_paths_for_completion(result, summary),
        )
    except Exception as e:
        send(chat_id, failed_agent_closeout(f"Hermes route failed: {type(e).__name__}"))


def handle_message(msg, source="telegram"):
    chat = msg.get("chat") or {}
    chat_id = int(chat.get("id"))
    text = (msg.get("text") or "").strip()
    if not text:
        return

    allowed = load_allowed()
    is_operator = chat_id in set(allowed.get("operator_chat_ids", []))
    pilot_id = allowed.get("pilots", {}).get(str(chat_id))

    if text.startswith("/status"):
        mode = "operator" if is_operator else ("pilot" if pilot_id else "unregistered")
        try:
            status = format_operator_status(get_backend_status(), mode=mode)
        except Exception as exc:
            status = backend_unavailable_status(mode=mode, reason=type(exc).__name__)
        send(chat_id, status, preserve_format=True)
        return

    if text.startswith("/whoami"):
        send(chat_id, f"chat_id={chat_id}")
        return

    if is_operator:
        handle_operator(chat_id, text, source=source)
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


def main():
    offset = 0
    me = api("getMe", {}, timeout=20).get("result", {})
    load_allowed()
    print(f"PASS bridge_live bot=@{me.get('username')} operator_configured={bool(load_allowed().get('operator_chat_ids'))}", flush=True)
    log("bridge_live")
    while True:
        try:
            res = api("getUpdates", {"timeout": "45", "offset": str(offset)}, timeout=60)
            for update in res.get("result", []):
                offset = max(offset, int(update.get("update_id", 0)) + 1)
                msg = update.get("message") or update.get("edited_message")
                if msg:
                    handle_message(msg)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log(f"loop_error {type(e).__name__}")
            time.sleep(3)


if __name__ == "__main__":
    main()
