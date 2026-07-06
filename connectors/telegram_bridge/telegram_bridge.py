import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(r"C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live")
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
_QUEUE_OUTPUT_MARKER = re.compile(r"(?im)^\s*Work item ID\s*:")


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
    return "\n".join(
        ["PASS" if passed else "NEEDS ATTENTION"]
        + [f"{field}: {values.get(field) or defaults[field]}" for field in _CLOSEOUT_FIELDS]
    )


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


def send(chat_id, text, preserve_format=False):
    text = str(text or "").strip()
    if not preserve_format and not is_queue_specific_output(text):
        text = compact_telegram_closeout(text)
    if len(text) > 3500:
        text = text[:3400] + "\n\n[trimmed]"
    try:
        api("sendMessage", {"chat_id": str(chat_id), "text": text}, timeout=20)
    except Exception as e:
        log(f"send_error chat={chat_id} error={type(e).__name__}")


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


def post_agent(route, task, timeout=180):
    payload = json.dumps({"task": task}).encode("utf-8")
    req = urllib.request.Request(
        f"{BACKEND}{route}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def summarize_agent_result(result):
    """Keep Telegram compact unless the backend already returned a queue closeout."""
    output = str(result.get("output") or "") if isinstance(result, dict) else ""
    success = bool(isinstance(result, dict) and result.get("success"))
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


def handle_operator(chat_id, text):
    if text.startswith("/work "):
        parts = text.split(" ", 2)
        if len(parts) < 3 or parts[1].lower() not in {"codex", "claude", "hermes"}:
            send(chat_id, "Use: /work codex|claude|hermes <task>")
            return
        target = parts[1].lower()
        task = parts[2].strip()
        route = {"codex": "/api/wsl/codex", "claude": "/api/wsl/claude", "hermes": "/api/wsl/hermes"}[target]
        try:
            result = post_agent(route, task)
            send(chat_id, summarize_agent_result(result), preserve_format=is_queue_backend_result(result))
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
        result = post_agent("/api/wsl/hermes", text)
        send(chat_id, summarize_agent_result(result), preserve_format=is_queue_backend_result(result))
    except Exception as e:
        send(chat_id, failed_agent_closeout(f"Hermes route failed: {type(e).__name__}"))


def handle_message(msg):
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
        send(chat_id, f"PASS bridge_live mode={mode} pilot={pilot_id or '-'}")
        return

    if text.startswith("/whoami"):
        send(chat_id, f"chat_id={chat_id}")
        return

    if is_operator:
        handle_operator(chat_id, text)
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
