"""Remote PC: authorised Windows PowerShell, files and desktop status for the operator Dashboard.

Every route requires a verified operator identity at the backend: a Cloudflare Access JWT on the
Cloudflare path, or the Tailscale Serve identity header on the tailnet path. A request carrying
neither is refused, so nothing here is reachable as an unauthenticated shell. Consequential actions
(a PowerShell run, a file upload) need a single-use confirmation token bound to the exact action,
and every executed action writes a durable receipt.

Revisit: when the Dashboard's Access application, Tailscale Serve config or the Windows host changes. · Last touched: 2026-10-26.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import jwt
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from jwt import PyJWKClient
from pydantic import BaseModel

from aos_paths import aos_root

POWERSHELL = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
TAILSCALE = Path("/mnt/c/Program Files/Tailscale/tailscale.exe")
EXPLORER = Path("/mnt/c/Windows/explorer.exe")
WINDOWS_HOME = Path("/mnt/c/Users/Admin")
RECEIPTS_DIR = aos_root() / "queue" / "receipts" / "remote_pc"
DENIED_LOG = RECEIPTS_DIR / "denied.jsonl"

REQUIRED_HEADER = "x-ttros-remote-pc"
CLOUDFLARE_HEADERS = ("cf-ray", "cf-connecting-ip", "cf-visitor", "cf-access-jwt-assertion")
DEFAULT_ORIGIN_HOSTS = {"ttros.timetorevenue.com", "vrs-global.tailb38520.ts.net", "localhost", "127.0.0.1"}

MAX_COMMAND_CHARS = 8000
TIMEOUT_CHOICES = (30, 60, 120, 300)
STREAM_CAP_BYTES = 2 * 1024 * 1024
CONFIRMATION_TTL_SECONDS = 180
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024
MAX_LISTING_ENTRIES = 2000
MAX_CONCURRENT_RUNS = 2

router = APIRouter(prefix="/api/remote-pc")

_secret = secrets.token_bytes(32)
_used_nonces: dict[str, float] = {}
_nonce_lock = threading.Lock()
_run_slots = threading.BoundedSemaphore(MAX_CONCURRENT_RUNS)
_jwk_clients: dict[str, PyJWKClient] = {}
_status_cache: dict[str, Any] = {}
_observed_aud: set[str] = set()


def _env_set(name: str, default: str = "") -> set[str]:
    return {value.strip().lower() for value in os.environ.get(name, default).split(",") if value.strip()}


def allowed_identities() -> set[str]:
    return _env_set("TTROS_REMOTE_PC_IDENTITIES", "liamduff88@gmail.com")


def allowed_origin_hosts() -> set[str]:
    return DEFAULT_ORIGIN_HOSTS | _env_set("TTROS_REMOTE_PC_ORIGIN_HOSTS")


def access_domain() -> str:
    return (os.environ.get("TTROS_DASHBOARD_ACCESS_AUTH_DOMAIN") or os.environ.get("TTROS_BRAIN_ACCESS_AUTH_DOMAIN") or "").strip().lower()


def access_audiences() -> set[str]:
    return _env_set("TTROS_DASHBOARD_ACCESS_AUD")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

class RemoteAccessDenied(Exception):
    def __init__(self, reason: str, identity: str = "", access_path: str = ""):
        super().__init__(reason)
        self.identity = identity
        self.access_path = access_path


def verify_dashboard_access_jwt(assertion: str) -> str | None:
    """Verify a Cloudflare Access JWT for the Dashboard; return the verified email.

    Signature, issuer and expiry are always enforced. The audience is pinned when
    TTROS_DASHBOARD_ACCESS_AUD is set; until then any audience issued by the team domain is
    accepted and recorded so it can be pinned, and status reports aud_pinned=false.
    """
    domain = access_domain()
    if not assertion or not domain or "/" in domain or ":" in domain:
        return None
    issuer = f"https://{domain}"
    audiences = access_audiences()
    try:
        client = _jwk_clients.setdefault(
            domain, PyJWKClient(f"{issuer}/cdn-cgi/access/certs", cache_jwk_set=True, lifespan=300)
        )
        signing_key = client.get_signing_key_from_jwt(assertion)
        claims = jwt.decode(
            assertion, signing_key.key, algorithms=["RS256"], issuer=issuer,
            audience=list(audiences) if audiences else None,
            options={"require": ["exp", "iss", "aud"], "verify_aud": bool(audiences)},
        )
    except (jwt.PyJWTError, ValueError, OSError):
        return None
    aud = claims.get("aud")
    _observed_aud.update(aud if isinstance(aud, list) else [str(aud)])
    email = claims.get("email")
    return str(email) if email else None


def authenticate(headers: Any) -> dict[str, str]:
    """Return the verified operator for a request, or raise RemoteAccessDenied."""
    if headers.get(REQUIRED_HEADER) != "1":
        raise RemoteAccessDenied("missing Remote PC request header")
    origin = headers.get("origin")
    if origin:
        host = (urlsplit(origin).hostname or "").lower()
        if host not in allowed_origin_hosts():
            raise RemoteAccessDenied("cross-site origin refused")
    if headers.get("sec-fetch-site", "same-origin") not in {"same-origin", "none"}:
        raise RemoteAccessDenied("cross-site request refused")
    if headers.get("tailscale-funnel-request"):
        raise RemoteAccessDenied("Tailscale Funnel (public) requests are refused")
    if any(headers.get(name) for name in CLOUDFLARE_HEADERS):
        identity = verify_dashboard_access_jwt(headers.get("cf-access-jwt-assertion", ""))
        if not identity:
            raise RemoteAccessDenied("Cloudflare Access assertion missing or invalid")
        path = "cloudflare_access"
    else:
        # Tailscale Serve deletes any client-supplied Tailscale-User-* headers and sets them
        # only for requests from a user-owned tailnet device.
        identity = headers.get("tailscale-user-login", "").strip()
        if not identity:
            raise RemoteAccessDenied("no verified operator identity (Cloudflare Access or Tailscale)")
        path = "tailscale_serve"
    if identity.lower() not in allowed_identities():
        # Name the refused identity so the operator can see which account Access or Tailscale
        # actually verified; it is never added to the allowlist from here.
        raise RemoteAccessDenied(f"identity {identity} ({path}) is not authorised for Remote PC", identity, path)
    return {"identity": identity, "access_path": path}


def require_operator(request: Request) -> dict[str, str]:
    try:
        return authenticate(request.headers)
    except RemoteAccessDenied as exc:
        _record_denial(request, str(exc), exc.identity, exc.access_path)
        raise HTTPException(status_code=403, detail=f"Remote PC refused: {exc}")


def _record_denial(request: Request, reason: str, identity: str = "", access_path: str = "") -> None:
    headers = request.headers
    row = {
        "at": _now(),
        "method": request.method,
        "path": request.url.path,
        "reason": reason,
        "identity": identity,
        "access_path": access_path,
        "origin": headers.get("origin", ""),
        "cloudflare": any(headers.get(name) for name in CLOUDFLARE_HEADERS),
        "tailscale_login": headers.get("tailscale-user-login", ""),
    }
    try:
        RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
        with DENIED_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Confirmation tokens
# ---------------------------------------------------------------------------

def issue_confirmation(action: str, digest: str, identity: str) -> dict[str, Any]:
    nonce = secrets.token_hex(8)
    expires = int(time.time()) + CONFIRMATION_TTL_SECONDS
    mac = hmac.new(_secret, f"{action}|{digest}|{identity.lower()}|{nonce}|{expires}".encode(), hashlib.sha256).hexdigest()
    return {"confirmation_token": f"{nonce}.{expires}.{mac}", "expires_in_seconds": CONFIRMATION_TTL_SECONDS}


def consume_confirmation(token: str, action: str, digest: str, identity: str) -> str:
    try:
        nonce, expires_text, mac = str(token or "").split(".")
        expires = int(expires_text)
    except ValueError:
        raise HTTPException(status_code=409, detail="confirmation required: prepare and confirm this exact action first")
    expected = hmac.new(_secret, f"{action}|{digest}|{identity.lower()}|{nonce}|{expires}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, mac):
        raise HTTPException(status_code=409, detail="confirmation does not match this exact action")
    now = time.time()
    if expires < now:
        raise HTTPException(status_code=409, detail="confirmation expired; confirm again")
    with _nonce_lock:
        for stale in [key for key, until in _used_nonces.items() if until < now]:
            _used_nonces.pop(stale, None)
        if nonce in _used_nonces:
            raise HTTPException(status_code=409, detail="confirmation already used")
        _used_nonces[nonce] = expires
    return nonce


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------

def _new_receipt_id(kind: str) -> str:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"RPC-{stamp}-{kind}-{uuid.uuid4().hex[:6]}"


def write_receipt(receipt: dict[str, Any]) -> Path:
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RECEIPTS_DIR / f"{receipt['receipt_id']}.json"
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    return path


def _receipt_path(receipt_id: str) -> Path:
    if not re.fullmatch(r"RPC-\d{8}T\d{6}Z-[a-z_]+-[0-9a-f]{6}", receipt_id or ""):
        raise HTTPException(status_code=400, detail="invalid receipt id")
    return RECEIPTS_DIR / f"{receipt_id}.json"


# ---------------------------------------------------------------------------
# PowerShell execution
# ---------------------------------------------------------------------------

def build_wrapper(command: str, run_id: str) -> str:
    """Wrap the operator's command without altering it.

    The command travels as UTF-8 base64 and runs as a ScriptBlock, so its text, quoting and line
    numbers reach PowerShell exactly as typed. The wrapper only fixes output encoding and maps the
    result to an exit code: a native non-zero exit code wins, then 1 if any error was recorded.
    """
    operator = base64.b64encode(command.encode("utf-8")).decode("ascii")
    return (
        f"# ttros-remote-pc {run_id}\n"
        "$ProgressPreference='SilentlyContinue'\n"
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)\n"
        "$OutputEncoding=[System.Text.UTF8Encoding]::new($false)\n"
        f"$__ttros_op=[System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{operator}'))\n"
        "$global:LASTEXITCODE=0\n"
        "$Error.Clear()\n"
        "try { & ([ScriptBlock]::Create($__ttros_op)) } catch { [Console]::Error.WriteLine(($_ | Out-String)) ; exit 1 }\n"
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }\n"
        "if ($Error.Count -gt 0) { exit 1 }\n"
        "exit 0\n"
    )


def decode_clixml(raw: str) -> str:
    """Render PowerShell's CLIXML error stream as the text a console would show."""
    if "#< CLIXML" not in raw:
        return raw
    out: list[str] = []
    for chunk in raw.split("#< CLIXML"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if not chunk.startswith("<Objs"):
            out.append(chunk)
            continue
        try:
            root = ET.fromstring(chunk)
        except ET.ParseError:
            out.append(chunk)
            continue
        for node in root.iter():
            if node.tag.endswith("}S") and node.text:
                text = re.sub(r"_x([0-9A-Fa-f]{4})_", lambda m: chr(int(m.group(1), 16)), node.text)
                stream = (node.get("S") or "").lower()
                prefix = {"warning": "WARNING: ", "verbose": "VERBOSE: ", "debug": "DEBUG: "}.get(stream, "")
                out.append(prefix + text if prefix else text)
    return "".join(out).replace("\r\n", "\n")


def _capped_reader(stream, sink: dict[str, Any]) -> None:
    kept = bytearray()
    total = 0
    while True:
        chunk = stream.read(65536)
        if not chunk:
            break
        total += len(chunk)
        room = STREAM_CAP_BYTES - len(kept)
        if room > 0:
            kept.extend(chunk[:room])
    sink["bytes"] = bytes(kept)
    sink["total"] = total


def _kill_windows_run(marker: str) -> str:
    """Terminate the Windows process tree whose encoded command line carries this run's marker."""
    script = (
        "$m='" + marker + "'; "
        "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | "
        "Where-Object { $_.CommandLine -and $_.CommandLine.Contains($m) } | "
        "ForEach-Object { taskkill.exe /T /F /PID $_.ProcessId | Out-Null; $_.ProcessId }"
    )
    try:
        result = subprocess.run(
            [str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
            cwd=str(_windows_cwd()), capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
        )
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"kill failed: {exc}"


def _windows_cwd() -> Path:
    return WINDOWS_HOME if WINDOWS_HOME.is_dir() else Path("/mnt/c")


def execute_powershell(command: str, timeout_seconds: int, run_id: str) -> dict[str, Any]:
    wrapper = build_wrapper(command, run_id)
    encoded = base64.b64encode(wrapper.encode("utf-16-le")).decode("ascii")
    # The first 160 base64 characters encode 120 whole bytes, which include the unique run id.
    marker = encoded[:160]
    argv = [str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]
    started = time.monotonic()
    started_at = _now()
    stdout_sink: dict[str, Any] = {}
    stderr_sink: dict[str, Any] = {}
    timed_out = False
    killed = ""
    proc = subprocess.Popen(argv, cwd=str(_windows_cwd()), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    readers = [
        threading.Thread(target=_capped_reader, args=(proc.stdout, stdout_sink), daemon=True),
        threading.Thread(target=_capped_reader, args=(proc.stderr, stderr_sink), daemon=True),
    ]
    for reader in readers:
        reader.start()
    try:
        exit_code = proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        killed = _kill_windows_run(marker)
        proc.kill()
        exit_code = proc.wait(timeout=30)
    for reader in readers:
        reader.join(timeout=10)
    stdout_raw = stdout_sink.get("bytes", b"").decode("utf-8", errors="replace").replace("\r\n", "\n")
    stderr_raw = stderr_sink.get("bytes", b"").decode("utf-8", errors="replace")
    return {
        "started_at": started_at,
        "finished_at": _now(),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
        "windows_processes_killed": killed,
        "stdout": stdout_raw,
        "stderr": decode_clixml(stderr_raw),
        "stdout_bytes_total": stdout_sink.get("total", 0),
        "stderr_bytes_total": stderr_sink.get("total", 0),
        "stdout_truncated": stdout_sink.get("total", 0) > STREAM_CAP_BYTES,
        "stderr_truncated": stderr_sink.get("total", 0) > STREAM_CAP_BYTES,
        "stderr_format": "clixml_decoded" if "#< CLIXML" in stderr_raw else "text",
    }


def _command_digest(command: str, timeout_seconds: int) -> str:
    return hashlib.sha256(f"{timeout_seconds}\n{command}".encode("utf-8")).hexdigest()


def _validate_command(command: str, timeout_seconds: int) -> None:
    if not isinstance(command, str) or not command.strip():
        raise HTTPException(status_code=400, detail="command is empty")
    if len(command) > MAX_COMMAND_CHARS:
        raise HTTPException(status_code=400, detail=f"command exceeds {MAX_COMMAND_CHARS} characters")
    if timeout_seconds not in TIMEOUT_CHOICES:
        raise HTTPException(status_code=400, detail=f"timeout_seconds must be one of {list(TIMEOUT_CHOICES)}")


class PowerShellRequest(BaseModel):
    command: str
    timeout_seconds: int = 60
    confirmation_token: str = ""


@router.post("/powershell/prepare")
def powershell_prepare(body: PowerShellRequest, request: Request):
    operator = require_operator(request)
    _validate_command(body.command, body.timeout_seconds)
    command_sha256 = hashlib.sha256(body.command.encode("utf-8")).hexdigest()
    token = issue_confirmation("powershell", _command_digest(body.command, body.timeout_seconds), operator["identity"])
    return {**token, "command_sha256": command_sha256, "timeout_seconds": body.timeout_seconds, "characters": len(body.command)}


@router.post("/powershell/run")
def powershell_run(body: PowerShellRequest, request: Request):
    operator = require_operator(request)
    _validate_command(body.command, body.timeout_seconds)
    nonce = consume_confirmation(body.confirmation_token, "powershell", _command_digest(body.command, body.timeout_seconds), operator["identity"])
    if not POWERSHELL.is_file():
        raise HTTPException(status_code=503, detail="Windows PowerShell is not reachable from this runtime (WSL interop)")
    if not _run_slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail=f"{MAX_CONCURRENT_RUNS} Windows commands are already running")
    try:
        run_id = _new_receipt_id("powershell")
        result = execute_powershell(body.command, body.timeout_seconds, run_id)
    finally:
        _run_slots.release()
    receipt = {
        "receipt_id": run_id,
        "action": "powershell",
        "operator": operator,
        "confirmation_nonce": nonce,
        "command": body.command,
        "command_sha256": hashlib.sha256(body.command.encode("utf-8")).hexdigest(),
        "executor": {
            "mechanism": "WSL interop → Windows PowerShell 5.1 (-NoProfile -NonInteractive -EncodedCommand)",
            "powershell": str(POWERSHELL),
            "working_directory": str(_windows_cwd()),
        },
        **result,
    }
    path = write_receipt(receipt)
    return {**receipt, "receipt_path": str(path)}


# ---------------------------------------------------------------------------
# Receipts listing
# ---------------------------------------------------------------------------

@router.get("/receipts")
def receipts_list(request: Request, limit: int = 30):
    require_operator(request)
    if not RECEIPTS_DIR.is_dir():
        return {"receipts": []}
    rows = []
    for path in sorted(RECEIPTS_DIR.glob("RPC-*.json"), reverse=True)[: max(1, min(limit, 200))]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows.append({
            "receipt_id": data.get("receipt_id"),
            "action": data.get("action"),
            "started_at": data.get("started_at") or data.get("at"),
            "exit_code": data.get("exit_code"),
            "timed_out": data.get("timed_out", False),
            "summary": (data.get("command") or data.get("windows_path") or "")[:160],
            "identity": (data.get("operator") or {}).get("identity"),
            "access_path": (data.get("operator") or {}).get("access_path"),
        })
    return {"receipts": rows, "receipts_dir": str(RECEIPTS_DIR)}


@router.get("/receipts/{receipt_id}")
def receipt_detail(receipt_id: str, request: Request):
    require_operator(request)
    path = _receipt_path(receipt_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="receipt not found")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def windows_to_linux(windows_path: str) -> Path:
    """Map an absolute drive path (C:\\...) onto its WSL mount, refusing anything outside it."""
    match = re.fullmatch(r"\s*([A-Za-z]):(?:[\\/](.*))?\s*", windows_path or "")
    if not match:
        raise HTTPException(status_code=400, detail="use an absolute Windows path such as C:\\Users\\Admin")
    drive = match.group(1).lower()
    base = Path(f"/mnt/{drive}")
    if not os.path.ismount(base):
        raise HTTPException(status_code=404, detail=f"drive {drive.upper()}: is not mounted")
    rest = (match.group(2) or "").replace("\\", "/")
    target = Path(os.path.normpath(base / rest))
    if target != base and base not in target.parents:
        raise HTTPException(status_code=400, detail="path escapes its drive")
    return target


def linux_to_windows(path: Path) -> str:
    parts = path.parts
    if len(parts) < 3 or parts[1] != "mnt" or len(parts[2]) != 1:
        return str(path)
    rest = "\\".join(parts[3:])
    return f"{parts[2].upper()}:\\{rest}"


def mounted_drives() -> list[str]:
    return [f"{p.name.upper()}:\\" for p in sorted(Path("/mnt").iterdir()) if len(p.name) == 1 and os.path.ismount(p)]


@router.get("/files")
def files_list(request: Request, path: str = "C:\\Users\\Admin"):
    require_operator(request)
    target = windows_to_linux(path)
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="folder not found")
    entries = []
    truncated = False
    try:
        with os.scandir(target) as iterator:
            for entry in iterator:
                if len(entries) >= MAX_LISTING_ENTRIES:
                    truncated = True
                    break
                try:
                    stat = entry.stat(follow_symlinks=False)
                    is_dir = entry.is_dir(follow_symlinks=True)
                except OSError:
                    entries.append({"name": entry.name, "type": "unreadable", "size": None, "modified": None})
                    continue
                entries.append({
                    "name": entry.name,
                    "type": "folder" if is_dir else "file",
                    "size": None if is_dir else stat.st_size,
                    "modified": datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc).isoformat(timespec="seconds"),
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Windows denied access to this folder")
    entries.sort(key=lambda item: (item["type"] != "folder", item["name"].lower()))
    parent = linux_to_windows(target.parent) if len(target.parts) > 3 else None
    return {
        "path": linux_to_windows(target),
        "parent": parent,
        "drives": mounted_drives(),
        "entries": entries,
        "truncated": truncated,
    }


@router.get("/files/download")
def files_download(request: Request, path: str):
    operator = require_operator(request)
    target = windows_to_linux(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    size = target.stat().st_size
    if size > MAX_DOWNLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"file exceeds the {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB download limit")
    receipt_id = _new_receipt_id("file_download")
    write_receipt({
        "receipt_id": receipt_id, "action": "file_download", "operator": operator,
        "started_at": _now(), "windows_path": linux_to_windows(target), "bytes": size,
    })
    return FileResponse(target, filename=target.name, headers={"X-Remote-PC-Receipt": receipt_id})


class UploadPrepareRequest(BaseModel):
    directory: str
    filename: str
    size: int


def _upload_target(directory: str, filename: str) -> Path:
    folder = windows_to_linux(directory)
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail="destination folder not found")
    name = (filename or "").strip()
    if not name or name in {".", ".."} or re.search(r'[\\/:*?"<>|\x00-\x1f]', name):
        raise HTTPException(status_code=400, detail="invalid Windows file name")
    return folder / name


def _upload_digest(target: Path, size: int) -> str:
    return hashlib.sha256(f"{target}\n{size}".encode("utf-8")).hexdigest()


@router.post("/files/upload/prepare")
def files_upload_prepare(body: UploadPrepareRequest, request: Request):
    operator = require_operator(request)
    target = _upload_target(body.directory, body.filename)
    if not 0 <= body.size <= MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
    if target.exists():
        raise HTTPException(status_code=409, detail="a file with that name already exists; uploads never overwrite")
    return {**issue_confirmation("file_upload", _upload_digest(target, body.size), operator["identity"]), "windows_path": linux_to_windows(target)}


@router.post("/files/upload")
async def files_upload(
    request: Request,
    directory: str = Form(...),
    filename: str = Form(...),
    size: int = Form(...),
    confirmation_token: str = Form(...),
    file: UploadFile = File(...),
):
    operator = require_operator(request)
    target = _upload_target(directory, filename)
    nonce = consume_confirmation(confirmation_token, "file_upload", _upload_digest(target, size), operator["identity"])
    written = 0
    digest = hashlib.sha256()
    try:
        with target.open("xb") as handle:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > size:
                    raise HTTPException(status_code=400, detail="upload is larger than the confirmed size")
                digest.update(chunk)
                handle.write(chunk)
        if written != size:
            raise HTTPException(status_code=400, detail="upload is smaller than the confirmed size")
    except FileExistsError:
        raise HTTPException(status_code=409, detail="a file with that name already exists; uploads never overwrite")
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    except OSError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"write failed: {exc}")
    receipt = {
        "receipt_id": _new_receipt_id("file_upload"), "action": "file_upload", "operator": operator,
        "confirmation_nonce": nonce, "started_at": _now(), "windows_path": linux_to_windows(target),
        "bytes": written, "sha256": digest.hexdigest(),
    }
    write_receipt(receipt)
    return receipt


class RevealRequest(BaseModel):
    path: str


@router.post("/files/reveal")
def files_reveal(body: RevealRequest, request: Request):
    """Open a folder (or select a file) in Explorer on the Windows desktop — the existing Explorer route."""
    require_operator(request)
    target = windows_to_linux(body.path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="path not found")
    if not EXPLORER.is_file():
        raise HTTPException(status_code=503, detail="Windows Explorer is not reachable from this runtime")
    windows_path = linux_to_windows(target)
    argv = [str(EXPLORER), windows_path] if target.is_dir() else [str(EXPLORER), f"/select,{windows_path}"]
    subprocess.Popen(argv, cwd="/mnt/c", stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"success": True, "windows_path": windows_path}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

STATUS_PROBE = r"""
$os = Get-CimInstance Win32_OperatingSystem
$crdPaths = @('C:\Program Files\Google\Chrome Remote Desktop','C:\Program Files (x86)\Google\Chrome Remote Desktop')
$crd = Get-Service -Name chromoting -ErrorAction SilentlyContinue
$rd = Get-Service -Name RustDesk -ErrorAction SilentlyContinue
[pscustomobject]@{
  computer = $env:COMPUTERNAME
  user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
  os = $os.Caption
  build = $os.BuildNumber
  last_boot = $os.LastBootUpTime.ToUniversalTime().ToString('o')
  crd_installed = [bool]($crdPaths | Where-Object { Test-Path -LiteralPath $_ })
  crd_service = if ($crd) { [string]$crd.Status } else { $null }
  rustdesk_service = if ($rd) { [string]$rd.Status } else { $null }
  rustdesk_installed = Test-Path -LiteralPath 'C:\Program Files\RustDesk\rustdesk.exe'
} | ConvertTo-Json -Compress
"""


def _probe_windows() -> dict[str, Any]:
    if not POWERSHELL.is_file():
        return {"reachable": False, "error": "powershell.exe not visible from WSL (interop disabled?)"}
    started = time.monotonic()
    try:
        result = subprocess.run(
            [str(POWERSHELL), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", STATUS_PROBE],
            cwd=str(_windows_cwd()), capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
        )
        data = json.loads(result.stdout.strip() or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return {"reachable": False, "error": str(exc)[:300]}
    return {"reachable": result.returncode == 0, "probe_ms": int((time.monotonic() - started) * 1000), **data}


def _probe_tailscale() -> dict[str, Any]:
    if not TAILSCALE.is_file():
        return {"installed": False}
    try:
        status = json.loads(subprocess.run([str(TAILSCALE), "status", "--json"], cwd="/mnt/c", capture_output=True, text=True, timeout=15).stdout or "{}")
        serve = json.loads(subprocess.run([str(TAILSCALE), "serve", "status", "--json"], cwd="/mnt/c", capture_output=True, text=True, timeout=15).stdout or "{}")
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return {"installed": True, "error": str(exc)[:300]}
    me = status.get("Self") or {}
    return {
        "installed": True,
        "backend_state": status.get("BackendState"),
        "online": bool(me.get("Online")),
        "dns_name": (me.get("DNSName") or "").rstrip("."),
        "tailnet_ips": me.get("TailscaleIPs") or [],
        "serve_web": sorted((serve.get("Web") or {}).keys()),
        "funnel_enabled": bool(serve.get("AllowFunnel")),
    }


def _cached(key: str, ttl: float, producer) -> dict[str, Any]:
    hit = _status_cache.get(key)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    value = producer()
    _status_cache[key] = (time.monotonic(), value)
    return value


def desktop_status(windows: dict[str, Any]) -> dict[str, Any]:
    crd_running = windows.get("crd_service") == "Running"
    if crd_running:
        state = "ready"
    elif windows.get("crd_installed"):
        state = "installed_not_running"
    else:
        state = "not_installed"
    return {
        "solution": "Chrome Remote Desktop",
        "state": state,
        "launch_url": "https://remotedesktop.google.com/access" if crd_running else None,
        "setup_url": "https://remotedesktop.google.com/access",
        "rustdesk_installed": bool(windows.get("rustdesk_installed")),
        "why": "Windows 11 Home cannot host RDP. Chrome Remote Desktop is free, supported on Home, needs no inbound ports, "
               "and is reachable from the iPhone app or any browser behind Google sign-in plus a host PIN.",
        "requires_at_pc": "Host install needs one UAC approval at the PC (TTROS runs at medium integrity and cannot elevate), "
                          "plus Google sign-in and choosing a PIN.",
    }


@router.get("/status")
def remote_status(request: Request, refresh: bool = False):
    operator = require_operator(request)
    if refresh:
        _status_cache.clear()
    windows = _cached("windows", 20, _probe_windows)
    tailscale = _cached("tailscale", 20, _probe_tailscale)
    return {
        "operator": operator,
        "checked_at": _now(),
        "windows": windows,
        "tailscale": tailscale,
        "desktop": desktop_status(windows),
        "access": {
            "cloudflare_domain": access_domain(),
            "aud_pinned": bool(access_audiences()),
            "observed_aud": sorted(_observed_aud),
            "allowed_identities": sorted(allowed_identities()),
        },
        "executor": {
            "mechanism": "WSL interop → Windows PowerShell 5.1",
            "powershell": str(POWERSHELL),
            "timeouts": list(TIMEOUT_CHOICES),
            "max_command_chars": MAX_COMMAND_CHARS,
            "receipts_dir": str(RECEIPTS_DIR),
        },
    }
