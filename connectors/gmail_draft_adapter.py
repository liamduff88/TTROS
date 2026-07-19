#!/usr/bin/env python3
"""Draft-only Gmail adapter over the existing Composio CLI spine.

The adapter passes message content to Gmail over stdin, retains any recovery
copy only in an ignored/search-excluded private runtime, and emits safe
metadata.  It has no send, reply, forward, schedule, update, delete, or label
mutation path.

Revisit: when GMAIL_CREATE_EMAIL_DRAFT schema/response changes. · Last touched: 2026-07-17.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

try:
    from gmail_draft_policy import GMAIL_CREATE_DRAFT_ACTION, authorize_draft_action
except ModuleNotFoundError:  # package import in tests/IDE contexts
    from connectors.gmail_draft_policy import GMAIL_CREATE_DRAFT_ACTION, authorize_draft_action


ROOT = Path(__file__).resolve().parents[1]
COMPOSIO = Path("/home/liam/.composio/composio")
PROVIDER = "composio-gmail"
PRIVATE_RUNTIME = Path("queue/draft_runtime")
RECEIPTS = Path("queue/receipts")
LOCKS = Path("queue/locks")
TIMEOUT_SECONDS = 60
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
EMAIL_RE = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")


class DraftValidationError(ValueError):
    """Draft input failed local validation before any provider call."""


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def idempotency_key(work_item_id: str, message_identity: str) -> str:
    work = str(work_item_id or "").strip()
    identity = str(message_identity or "").strip()
    if not work or not identity:
        raise DraftValidationError("work_item_id and message_identity are required")
    return sha256_text(f"gmail-draft-v1\0{work}\0{identity}")


def _validate_address(value: str, field: str) -> str:
    candidate = str(value or "").strip()
    if not candidate or "\r" in candidate or "\n" in candidate:
        raise DraftValidationError(f"{field} contains an invalid email address")
    display, address = parseaddr(candidate)
    if not address or not EMAIL_RE.fullmatch(address):
        raise DraftValidationError(f"{field} contains an invalid email address")
    if display and candidate != f"{display} <{address}>" and candidate != address:
        # parseaddr is deliberately permissive; reject ambiguous trailing text.
        if not candidate.endswith(f"<{address}>"):
            raise DraftValidationError(f"{field} contains an invalid email address")
    return candidate


def _validate_addresses(values: Sequence[str] | None, field: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        raise DraftValidationError(f"{field} must be a list of email addresses")
    return tuple(_validate_address(value, field) for value in values)


@dataclass(frozen=True)
class DraftRequest:
    work_item_id: str
    message_identity: str
    recipient: str
    subject: str
    body: str
    cc: tuple[str, ...] = ()
    bcc: tuple[str, ...] = ()

    @classmethod
    def validated(
        cls,
        *,
        work_item_id: str,
        message_identity: str,
        recipient: str,
        subject: str,
        body: str,
        cc: Sequence[str] | None = None,
        bcc: Sequence[str] | None = None,
    ) -> "DraftRequest":
        key = idempotency_key(work_item_id, message_identity)
        del key
        clean_subject = str(subject or "").strip()
        clean_body = str(body or "")
        if not clean_subject or "\r" in clean_subject or "\n" in clean_subject or len(clean_subject) > 998:
            raise DraftValidationError("subject is required and must be one safe header line")
        if not clean_body.strip():
            raise DraftValidationError("body is required")
        if len(clean_body.encode("utf-8")) > 5_000_000:
            raise DraftValidationError("body exceeds the local draft size limit")
        return cls(
            work_item_id=str(work_item_id).strip(),
            message_identity=str(message_identity).strip(),
            recipient=_validate_address(recipient, "recipient"),
            subject=clean_subject,
            body=clean_body,
            cc=_validate_addresses(cc, "cc"),
            bcc=_validate_addresses(bcc, "bcc"),
        )

    @property
    def key(self) -> str:
        return idempotency_key(self.work_item_id, self.message_identity)

    def provider_payload(self) -> dict[str, Any]:
        return {
            "recipient_email": self.recipient,
            "extra_recipients": [],
            "subject": self.subject,
            "body": self.body,
            "cc": list(self.cc),
            "bcc": list(self.bcc),
            "is_html": False,
            "user_id": "me",
        }


@dataclass(frozen=True)
class ProviderResult:
    ok: bool
    draft_id: str | None = None
    failure_class: str | None = None
    response_shape: dict[str, list[str]] | None = None


def _parse_cli_json(stdout: str) -> Any | None:
    plain = ANSI_RE.sub("", stdout).strip()
    if not plain:
        return None
    try:
        return json.loads(plain)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        candidates: list[tuple[int, Any]] = []
        for index, char in enumerate(plain):
            if char not in "[{":
                continue
            with contextlib.suppress(json.JSONDecodeError):
                value, end = decoder.raw_decode(plain, index)
                candidates.append((end - index, value))
        return max(candidates, key=lambda row: row[0])[1] if candidates else None


def _response_shape(value: Any) -> dict[str, list[str]]:
    shape: dict[str, list[str]] = {}
    if isinstance(value, dict):
        shape["top_level"] = sorted(str(key) for key in value)
        data = value.get("data")
        if isinstance(data, dict):
            shape["data"] = sorted(str(key) for key in data)
    return shape


def _draft_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    data = value.get("data")
    if isinstance(data, dict) and isinstance(data.get("id"), str) and data["id"].strip():
        return data["id"].strip()
    if isinstance(data, dict) and isinstance(data.get("draft"), dict):
        draft = data["draft"]
        if isinstance(draft.get("id"), str) and draft["id"].strip():
            return draft["id"].strip()
    if isinstance(value.get("id"), str) and value["id"].strip():
        return value["id"].strip()
    return None


def _failure_class(returncode: int | None, text: str, *, timed_out: bool = False) -> str:
    lowered = text.lower()
    if timed_out:
        return "provider_timeout"
    if "scope" in lowered and ("insufficient" in lowered or "missing" in lowered):
        return "oauth_scope_missing"
    if "permission_denied" in lowered or "permission denied" in lowered or "403" in lowered:
        return "provider_permission_denied"
    if "not connected" in lowered or "authentication" in lowered or "unauthorized" in lowered or "401" in lowered:
        return "connection_authentication_failed"
    if "invalid" in lowered or "validation" in lowered or "400" in lowered:
        return "provider_validation_failed"
    if returncode is None:
        return "provider_unavailable"
    return "provider_execution_failed"


class ComposioDraftExecutor:
    """One exact Composio action, with content supplied on stdin only."""

    def __init__(self, composio: Path = COMPOSIO, timeout: int = TIMEOUT_SECONDS):
        self.composio = Path(composio)
        self.timeout = timeout

    def execute(self, action: str, payload: dict[str, Any]) -> ProviderResult:
        authorize_draft_action(action)
        if not self.composio.is_file():
            return ProviderResult(ok=False, failure_class="provider_unavailable")
        command = [str(self.composio), "execute", GMAIL_CREATE_DRAFT_ACTION, "-d", "-"]
        try:
            result = subprocess.run(
                command,
                input=json.dumps(payload, separators=(",", ":")),
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ProviderResult(ok=False, failure_class="provider_timeout")
        parsed = _parse_cli_json(result.stdout)
        draft_id = _draft_id(parsed)
        if result.returncode == 0 and draft_id:
            return ProviderResult(ok=True, draft_id=draft_id, response_shape=_response_shape(parsed))
        safe_class = _failure_class(result.returncode, f"{result.stderr}\n{result.stdout}")
        if result.returncode == 0 and not draft_id:
            safe_class = "provider_response_invalid"
        return ProviderResult(ok=False, failure_class=safe_class, response_shape=_response_shape(parsed))


class DraftStore:
    """Private recovery state plus canonical safe queue receipts."""

    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.runtime = self.root / PRIVATE_RUNTIME
        self.receipts = self.root / RECEIPTS
        self.locks = self.root / LOCKS

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any], mode: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700 if mode == 0o600 else 0o755)
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                os.fchmod(handle.fileno(), mode)
                json.dump(value, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except Exception:
            with contextlib.suppress(OSError):
                temp.unlink()
            raise

    def state_path(self, key: str) -> Path:
        return self.runtime / "effects" / f"{key}.json"

    def receipt_path(self, key: str) -> Path:
        return self.receipts / f"gmail-draft-{key[:24]}.json"

    def review_path(self, work_item_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", work_item_id).strip("-") or "unknown"
        return self.runtime / "review_packages" / f"{safe}.json"

    def read_state(self, key: str) -> dict[str, Any] | None:
        path = self.state_path(key)
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None

    def write_private_state(self, key: str, value: dict[str, Any]) -> None:
        self._atomic_json(self.state_path(key), value, 0o600)

    def write_safe_receipt(self, key: str, value: dict[str, Any]) -> None:
        self._atomic_json(self.receipt_path(key), value, 0o644)

    def write_private_review(self, work_item_id: str, value: dict[str, Any]) -> Path:
        path = self.review_path(work_item_id)
        self._atomic_json(path, value, 0o600)
        return path

    @contextmanager
    def effect_lock(self, key: str) -> Iterator[None]:
        self.locks.mkdir(parents=True, exist_ok=True)
        path = self.locks / f"gmail-draft-{key}.lock"
        handle = path.open("a+", encoding="utf-8")
        os.chmod(path, 0o600)
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()


def _safe_receipt(
    request: DraftRequest,
    *,
    status: str,
    timestamp: str,
    safe_draft_reference: str | None = None,
    failure_class: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "work_item_id": request.work_item_id,
        "status": status,
        "recipient_count": 1 + len(request.cc) + len(request.bcc),
        "subject_sha256": sha256_text(request.subject),
        "timestamp": timestamp,
        "provider": PROVIDER,
        "safe_draft_reference": safe_draft_reference,
        "idempotency_key": request.key,
        "token_usage": {"available": False},
    }
    if failure_class:
        value["failure_class"] = failure_class
    return value


class GmailDraftAdapter:
    def __init__(
        self,
        *,
        root: Path = ROOT,
        executor: ComposioDraftExecutor | Any | None = None,
        clock: Callable[[], str] = now_utc,
    ):
        self.store = DraftStore(root)
        self.executor = executor or ComposioDraftExecutor()
        self.clock = clock

    def create_draft(
        self,
        *,
        work_item_id: str,
        message_identity: str,
        recipient: str,
        subject: str,
        body: str,
        cc: Sequence[str] | None = None,
        bcc: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        request = DraftRequest.validated(
            work_item_id=work_item_id,
            message_identity=message_identity,
            recipient=recipient,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
        )
        authorize_draft_action(GMAIL_CREATE_DRAFT_ACTION)
        with self.store.effect_lock(request.key):
            prior = self.store.read_state(request.key)
            if prior:
                canonical_status = str(prior.get("status") or "indeterminate")
                if canonical_status == "draft-created":
                    return {
                        **_safe_receipt(
                            request,
                            status="duplicate-replay",
                            timestamp=self.clock(),
                            safe_draft_reference=prior.get("safe_draft_reference"),
                        ),
                        "canonical_status": "draft-created",
                        "duplicate_replay": True,
                    }
                return {
                    **_safe_receipt(
                        request,
                        status="blocked-recovery",
                        timestamp=self.clock(),
                        failure_class=str(prior.get("failure_class") or "indeterminate_prior_attempt"),
                    ),
                    "canonical_status": canonical_status,
                    "duplicate_replay": True,
                }

            started = self.clock()
            # Persist before calling Gmail.  A crash can leave an indeterminate
            # attempt for review, but a replay can never blindly create twice.
            private_state = {
                "status": "provider-call-pending",
                "action": GMAIL_CREATE_DRAFT_ACTION,
                "work_item_id": request.work_item_id,
                "message_identity": request.message_identity,
                "idempotency_key": request.key,
                "started_at": started,
                "recipient": request.recipient,
                "cc": list(request.cc),
                "bcc": list(request.bcc),
                "subject": request.subject,
                "body": request.body,
            }
            self.store.write_private_state(request.key, private_state)
            result = self.executor.execute(GMAIL_CREATE_DRAFT_ACTION, request.provider_payload())
            finished = self.clock()
            if not result.ok or not result.draft_id:
                failure = result.failure_class or "provider_execution_failed"
                private_state.update({"status": "draft-failed", "failure_class": failure, "finished_at": finished})
                self.store.write_private_state(request.key, private_state)
                receipt = _safe_receipt(request, status="draft-failed", timestamp=finished, failure_class=failure)
                self.store.write_safe_receipt(request.key, receipt)
                return receipt

            safe_reference = f"gmail-draft:{sha256_text(result.draft_id)[:24]}"
            # Success state retains only the provider ID needed for bounded
            # verification/recovery; recipient, subject and body are scrubbed.
            success_state = {
                "status": "draft-created",
                "action": GMAIL_CREATE_DRAFT_ACTION,
                "work_item_id": request.work_item_id,
                "message_identity": request.message_identity,
                "idempotency_key": request.key,
                "provider_draft_id": result.draft_id,
                "safe_draft_reference": safe_reference,
                "created_at": finished,
                "response_shape": result.response_shape or {},
            }
            self.store.write_private_state(request.key, success_state)
            receipt = _safe_receipt(
                request,
                status="draft-created",
                timestamp=finished,
                safe_draft_reference=safe_reference,
            )
            self.store.write_safe_receipt(request.key, receipt)
            return receipt


def _tailored_to_signal(body: str, signal: str) -> bool:
    body_words = set(re.findall(r"[a-z0-9]{4,}", body.lower()))
    signal_words = set(re.findall(r"[a-z0-9]{4,}", signal.lower()))
    return bool(body_words.intersection(signal_words))


def create_prospecting_drafts(
    package: dict[str, Any],
    *,
    adapter: GmailDraftAdapter,
) -> dict[str, Any]:
    """Extend the canonical prospecting effect with one draft per prospect."""
    work_item_id = str(package.get("work_item_id") or "").strip()
    prospects = package.get("prospects")
    if not work_item_id or not isinstance(prospects, list):
        raise DraftValidationError("prospecting package requires work_item_id and prospects list")

    # The full research/draft package is private, ignored, and search-excluded.
    private_path = adapter.store.write_private_review(work_item_id, package)
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    failed = False
    for prospect in prospects:
        if not isinstance(prospect, dict):
            failed = True
            results.append({"status": "draft-failed", "failure_class": "invalid_prospect_record"})
            continue
        identity = str(prospect.get("prospect_id") or prospect.get("message_identity") or "").strip()
        safe_identity = sha256_text(identity)[:16] if identity else None
        if not identity or identity in seen:
            failed = True
            results.append({
                "prospect_reference": safe_identity,
                "status": "draft-failed",
                "failure_class": "duplicate_or_missing_prospect_identity",
            })
            continue
        seen.add(identity)
        signal = str(prospect.get("signal") or prospect.get("wedge") or "").strip()
        body = str(prospect.get("body") or "")
        gates_passed = (
            prospect.get("validated") is True
            and prospect.get("email_drafted") is True
            and prospect.get("tailored") is True
            and prospect.get("do_not_contact") is not True
            and bool(str(prospect.get("outreach_basis") or "").strip())
            and bool(signal)
            and _tailored_to_signal(body, signal)
        )
        if not gates_passed:
            failed = True
            results.append({
                "prospect_reference": safe_identity,
                "status": "draft-failed",
                "failure_class": "prospect_validation_or_tailoring_failed",
            })
            continue
        try:
            receipt = adapter.create_draft(
                work_item_id=work_item_id,
                message_identity=identity,
                recipient=str(prospect.get("recipient") or ""),
                subject=str(prospect.get("subject") or ""),
                body=body,
                cc=prospect.get("cc"),
                bcc=prospect.get("bcc"),
            )
        except DraftValidationError:
            receipt = {"status": "draft-failed", "failure_class": "draft_input_validation_failed"}
        if receipt["status"] not in {"draft-created", "duplicate-replay"}:
            failed = True
        results.append({
            "prospect_reference": safe_identity,
            "status": receipt["status"],
            "safe_draft_reference": receipt.get("safe_draft_reference"),
            "idempotency_key": receipt.get("idempotency_key"),
            "failure_class": receipt.get("failure_class"),
        })

    return {
        "workflow": "prospecting_daily_run",
        "work_item_id": work_item_id,
        "status": "draft-preparation-blocked" if failed else "review-package-ready",
        "queue_status": "blocked" if failed else "human_review",
        "provider": PROVIDER,
        "prospect_count": len(prospects),
        "results": results,
        "private_review_reference": private_path.relative_to(adapter.store.root).as_posix(),
        "contains_message_body": False,
        "token_usage": {"available": False},
    }


def _load_input(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise DraftValidationError("input must be one JSON object")
    return value


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Agentic OS Gmail draft-only adapter")
    root.add_argument("--root", default=str(ROOT))
    commands = root.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--input", default="-", help="JSON file or - for stdin")
    prospecting = commands.add_parser("prospecting")
    prospecting.add_argument("--input", default="-", help="JSON file or - for stdin")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        value = _load_input(args.input)
        adapter = GmailDraftAdapter(root=Path(args.root))
        if args.command == "create":
            result = adapter.create_draft(
                work_item_id=str(value.get("work_item_id") or ""),
                message_identity=str(value.get("message_identity") or ""),
                recipient=str(value.get("recipient") or ""),
                subject=str(value.get("subject") or ""),
                body=str(value.get("body") or ""),
                cc=value.get("cc"),
                bcc=value.get("bcc"),
            )
        else:
            result = create_prospecting_drafts(value, adapter=adapter)
    except (DraftValidationError, json.JSONDecodeError, OSError) as exc:
        result = {"status": "draft-failed", "failure_class": type(exc).__name__, "token_usage": {"available": False}}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") not in {"draft-failed", "draft-preparation-blocked", "blocked-recovery"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
