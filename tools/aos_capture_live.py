#!/usr/bin/env python3
"""Phase 6B read-only Gmail capture entry point.

This is the single production entry point used by direct observation and the
existing Hermes scheduler. It delegates durable capture to ``aos_capture`` and
provider access to the existing Composio adapter. It has no Gmail mutation,
send, draft, label, attachment, Calendar, Drive, CRM, or whitelist operation.

Revisit: after the Phase 6B observation window or a Gmail/Composio schema change. · Last touched: 2026-07-19.
"""

from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.backend.business_brain_graph import BusinessBrainGraphService
from tools import aos_indexer
from tools.aos_capture import (
    CaptureEngine,
    CaptureEnvelope,
    CaptureError,
    CaptureMetadataProjection,
    CaptureProposer,
    CaptureQueueWriter,
    CaptureStorage,
    CaptureStorageError,
    CaptureTriage,
    DeltaBatch,
    LiveCaptureDisabled,
    capture_document,
    stable_hash,
    subject_classification,
    utc_now,
)
from tools.aos_queue_storage import durable_replace_text, fsync_directory
from tools.business_brain_scope import ClientScopeError, load_registry


PROVIDER_KEY = "gmail-live"
PROVIDER_NAME = "gmail_composio"
ACTIVATION_PATH = ROOT / "capture" / "runtime" / "control" / "activation.json"
OBSERVATION_PATH = ROOT / "capture" / "runtime" / "control" / "observation.json"
POLL_RECEIPTS_PATH = ROOT / "capture" / "runtime" / "control" / "poll_receipts.jsonl"
LOCK_PATH = ROOT / "capture" / "runtime" / "control" / "poll.lock"
COMPOSIO_ADAPTER = ROOT / "connectors" / "composio_access_adapter.py"
SEARCH_DB = ROOT / "search" / "os_index.db"
CAPTURE_ROLLUPS = ROOT / "capture" / "runtime" / "rollups"
ACTIVATION_CONTRACT = {"approved": True, "contract": "gmail_history_metadata_read_only"}
ALLOWED_ACTIONS = {
    "GMAIL_GET_PROFILE",
    "GMAIL_LIST_HISTORY",
    "GMAIL_FETCH_EMAILS",
    "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
}
PROHIBITED_LABELS = {"SPAM", "TRASH", "SENT"}
MAX_HISTORY_PAGES = 5
MAX_BOOTSTRAP_RESULTS = 100
POLL_TIMEOUT_SECONDS = 180


def _sha(value: str | bytes) -> str:
    raw = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _safe_error(exc: BaseException) -> str:
    known = (
        LiveCaptureDisabled,
        CaptureStorageError,
        ClientScopeError,
        CaptureError,
        TimeoutError,
        subprocess.TimeoutExpired,
    )
    return type(exc).__name__ if isinstance(exc, known) else "UnexpectedCaptureError"


def _append_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    existed = path.exists()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    if not existed:
        fsync_directory(path.parent)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


class PollLock:
    def __init__(self, path: Path = LOCK_PATH):
        self.path = path
        self.handle: Any = None

    def __enter__(self) -> "PollLock":
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.handle = self.path.open("a+", encoding="utf-8")
        os.chmod(self.path, 0o600)
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.handle.close()
            raise LiveCaptureDisabled("capture poll already running") from exc
        return self

    def __exit__(self, *_args: object) -> None:
        if self.handle is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()


class PreparedDeltaAdapter:
    live = True
    provider_key = PROVIDER_KEY

    def __init__(self, batch: DeltaBatch):
        self.batch = batch

    def read_delta(self, _cursor: str | None) -> DeltaBatch:
        return self.batch


class ComposioReadOnlyExecutor:
    """Validated read-only calls through the repository's one Composio spine."""

    def __init__(self):
        self.action_counts: Counter[str] = Counter()

    @staticmethod
    def _validate(action: str, payload: dict[str, Any]) -> None:
        if action not in ALLOWED_ACTIONS:
            raise CaptureError("Composio action is outside the read-only Gmail allowlist")
        if payload.get("user_id", "me") != "me":
            raise CaptureError("Gmail user_id must remain the connected mailbox alias")
        if action == "GMAIL_LIST_HISTORY":
            if payload.get("label_id") != "INBOX" or payload.get("history_types") != ["messageAdded"]:
                raise CaptureError("Gmail history scope must be INBOX message additions only")
            if not str(payload.get("start_history_id") or "").isdigit():
                raise CaptureError("Gmail history start cursor is invalid")
            if int(payload.get("max_results", 0)) not in range(1, 501):
                raise CaptureError("Gmail history page size is invalid")
        elif action == "GMAIL_FETCH_EMAILS":
            if payload.get("label_ids") != ["INBOX"]:
                raise CaptureError("Gmail bootstrap must be INBOX-only")
            if payload.get("include_payload") is not False or payload.get("include_spam_trash") is not False:
                raise CaptureError("Gmail bootstrap must be metadata-only and exclude spam/trash")
            if int(payload.get("max_results", 0)) not in range(1, MAX_BOOTSTRAP_RESULTS + 1):
                raise CaptureError("Gmail bootstrap size is invalid")
        elif action == "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID":
            if payload.get("format") != "metadata" or not str(payload.get("message_id") or ""):
                raise CaptureError("Gmail item retrieval must be one metadata-only message")

    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate(action, payload)
        command = [
            sys.executable,
            str(COMPOSIO_ADAPTER),
            "tool-run",
            action,
            json.dumps(payload, separators=(",", ":")),
        ]
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.action_counts[action] += 1
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise CaptureError("Composio adapter returned invalid JSON") from exc
        if result.returncode or response.get("ok") is not True:
            raise CaptureError("Composio read-only Gmail action failed")
        value = response.get("result")
        if not isinstance(value, dict) or value.get("successful") is False:
            raise CaptureError("Composio read-only Gmail result was unsuccessful")
        data = value.get("data")
        if not isinstance(data, dict):
            raise CaptureError("Composio read-only Gmail result lacked object data")
        return data


def _labels(value: dict[str, Any]) -> set[str]:
    raw = value.get("labelIds") or value.get("label_ids") or value.get("labels") or []
    if isinstance(raw, str):
        raw = [raw]
    return {str(item).upper() for item in raw if str(item)}


def _headers(value: dict[str, Any]) -> dict[str, str]:
    payload = value.get("payload") if isinstance(value.get("payload"), dict) else {}
    raw = value.get("headers") or payload.get("headers") or []
    headers: dict[str, str] = {}
    if isinstance(raw, dict):
        return {str(k).lower(): str(v) for k, v in raw.items()}
    for row in raw if isinstance(raw, list) else []:
        if isinstance(row, dict) and row.get("name"):
            headers[str(row["name"]).lower()] = str(row.get("value") or "")
    return headers


def _text_field(value: dict[str, Any], *names: str) -> str:
    for name in names:
        raw = value.get(name)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        if isinstance(raw, dict):
            candidate = raw.get("email") or raw.get("address") or raw.get("value")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def _timestamp(value: dict[str, Any], headers: dict[str, str]) -> str:
    raw = _text_field(value, "timestamp", "received_at", "date", "internalDate", "internal_date")
    if raw.isdigit():
        number = int(raw)
        if number > 10_000_000_000:
            number //= 1000
        return dt.datetime.fromtimestamp(number, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")
    candidate = raw or headers.get("date", "")
    if candidate:
        try:
            parsed = email.utils.parsedate_to_datetime(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError, OverflowError):
            try:
                parsed = dt.datetime.fromisoformat(candidate.replace("Z", "+00:00"))
                return parsed.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")
            except ValueError:
                pass
    return utc_now()


def _message_identity(value: dict[str, Any]) -> tuple[str, str]:
    message_id = _text_field(value, "id", "messageId", "message_id")
    thread_id = _text_field(value, "threadId", "thread_id")
    return message_id, thread_id


def _normalize_message(
    value: dict[str, Any],
    *,
    history_id: str,
    mailbox_sender_sha256: str,
) -> CaptureEnvelope | None:
    nested = value.get("message") if isinstance(value.get("message"), dict) else value
    labels = _labels(nested)
    if labels and ("INBOX" not in labels or labels.intersection(PROHIBITED_LABELS)):
        return None
    headers = _headers(nested)
    message_id, thread_id = _message_identity(nested)
    sender_raw = _text_field(nested, "sender", "from", "from_address") or headers.get("from", "")
    sender = email.utils.parseaddr(sender_raw)[1].strip().lower()
    if not message_id or not thread_id or not sender:
        return None
    if _sha(sender) == mailbox_sender_sha256:
        return None
    subject = _text_field(nested, "subject") or headers.get("subject", "")
    safe_headers = {
        "list_id_present": bool(headers.get("list-id")),
        "auto_submitted": headers.get("auto-submitted", ""),
        "precedence": headers.get("precedence", ""),
        "category": _text_field(nested, "category"),
        "ambiguous_candidate": False,
    }
    return CaptureEnvelope(
        provider=PROVIDER_NAME,
        message_id=message_id,
        thread_id=thread_id,
        history_id=str(history_id),
        timestamp=_timestamp(nested, headers),
        sender=sender,
        subject=subject,
        source_type="gmail",
        headers=safe_headers,
    ).validate()


def _history_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("history") or data.get("histories") or data.get("history_records") or []
    return [row for row in raw if isinstance(row, dict)] if isinstance(raw, list) else []


def _added_refs(rows: Iterable[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    refs: list[tuple[str, dict[str, Any]]] = []
    seen = set()
    for row in rows:
        history_id = str(row.get("id") or row.get("historyId") or row.get("history_id") or "")
        additions = row.get("messagesAdded") or row.get("messages_added") or []
        for addition in additions if isinstance(additions, list) else []:
            if not isinstance(addition, dict):
                continue
            message = addition.get("message") if isinstance(addition.get("message"), dict) else addition
            message_id, _thread_id = _message_identity(message)
            if not message_id or message_id in seen:
                continue
            labels = _labels(message)
            if labels and ("INBOX" not in labels or labels.intersection(PROHIBITED_LABELS)):
                continue
            refs.append((history_id, message))
            seen.add(message_id)
    return refs


def _bootstrap_messages(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("messages", "emails", "items"):
        raw = data.get(key)
        if isinstance(raw, list):
            return [row for row in raw if isinstance(row, dict)]
    return []


def _metadata_message(executor: ComposioReadOnlyExecutor, value: dict[str, Any]) -> dict[str, Any]:
    message_id, _thread_id = _message_identity(value)
    if not message_id:
        raise CaptureError("Gmail metadata row lacked a message identifier")
    return executor.execute("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", {
        "user_id": "me",
        "message_id": message_id,
        "format": "metadata",
    })


def _profile(executor: ComposioReadOnlyExecutor) -> tuple[str, str]:
    profile = executor.execute("GMAIL_GET_PROFILE", {"user_id": "me"})
    history_id = str(profile.get("historyId") or profile.get("history_id") or "")
    mailbox = _text_field(profile, "emailAddress", "email_address", "email").lower()
    if not history_id.isdigit() or not mailbox:
        raise CaptureError("Gmail profile lacked a usable checkpoint or mailbox identity")
    return history_id, _sha(mailbox)


def _prepare_delta(
    executor: ComposioReadOnlyExecutor,
    *,
    cursor: str | None,
    bootstrap_hours: int,
) -> tuple[DeltaBatch, dict[str, Any]]:
    current_history, mailbox_hash = _profile(executor)
    envelopes: list[CaptureEnvelope] = []
    history_entries = 0
    boundary: str | None = None
    if cursor is None:
        start = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=bootstrap_hours)
        boundary = start.isoformat().replace("+00:00", "Z")
        data = executor.execute("GMAIL_FETCH_EMAILS", {
            "user_id": "me",
            "label_ids": ["INBOX"],
            "query": f"after:{int(start.timestamp())}",
            "include_payload": False,
            "include_spam_trash": False,
            "ids_only": False,
            "verbose": False,
            "max_results": MAX_BOOTSTRAP_RESULTS,
        })
        rows = _bootstrap_messages(data)
        history_entries = len(rows)
        for row in rows:
            candidate = _normalize_message(
                row,
                history_id=current_history,
                mailbox_sender_sha256=mailbox_hash,
            )
            if candidate is None:
                detailed = _metadata_message(executor, row)
                candidate = _normalize_message(
                    detailed,
                    history_id=current_history,
                    mailbox_sender_sha256=mailbox_hash,
                )
            if candidate is not None:
                envelopes.append(candidate)
    else:
        page_token = ""
        refs: list[tuple[str, dict[str, Any]]] = []
        next_history = current_history
        for _page in range(MAX_HISTORY_PAGES):
            payload: dict[str, Any] = {
                "user_id": "me",
                "start_history_id": cursor,
                "history_types": ["messageAdded"],
                "label_id": "INBOX",
                "max_results": 100,
            }
            if page_token:
                payload["page_token"] = page_token
            data = executor.execute("GMAIL_LIST_HISTORY", payload)
            rows = _history_rows(data)
            history_entries += len(rows)
            refs.extend(_added_refs(rows))
            next_history = str(data.get("historyId") or data.get("history_id") or next_history)
            page_token = str(data.get("nextPageToken") or data.get("next_page_token") or "")
            if not page_token:
                break
        else:
            raise CaptureError("Gmail history pagination exceeded the bounded page limit")
        seen = set()
        for history_id, ref in refs:
            message_id, _thread_id = _message_identity(ref)
            if not message_id or message_id in seen:
                continue
            seen.add(message_id)
            detailed = _metadata_message(executor, ref)
            candidate = _normalize_message(
                detailed,
                history_id=history_id or next_history,
                mailbox_sender_sha256=mailbox_hash,
            )
            if candidate is not None:
                envelopes.append(candidate)
        current_history = next_history
    unique = {row.message_id: row for row in envelopes}
    return DeltaBatch(next_cursor=current_history, envelopes=tuple(unique.values())), {
        "bootstrap_boundary_utc": boundary,
        "bootstrap_hours": bootstrap_hours if cursor is None else 0,
        "history_entries_received": history_entries,
        "authorized_envelopes": len(unique),
    }


def _projection_for_discard(storage: CaptureStorage, decision: Any) -> None:
    raw = storage.raw_record(decision.record_id)
    row = CaptureMetadataProjection(
        record_id=str(raw["record_id"]),
        reference_path=str(raw["evidence_reference"]),
        client_scope=str(decision.client_scope or "_unresolved"),
        linked_item_id="",
        subject_classification=decision.subject_classification,
        timestamp=str(raw["timestamp"]),
        source_type="gmail",
        triage_state=decision.state,
        proposal_state="discarded",
    )
    storage.append_derived(decision.client_scope, "metadata", row.to_dict())
    storage.append_derived(decision.client_scope, "operational_receipts", {
        "record_id": row.record_id,
        "reference_path": row.reference_path,
        "client_scope": row.client_scope,
        "proposal_state": "discarded",
        "linked_item_id": "",
        "token_usage_text": "Token usage: no agent invocation",
    })


def _publish_metadata(storage: CaptureStorage) -> dict[str, Any]:
    rows = storage.metadata_rows()
    index_result = aos_indexer.scan(capture_runtime_root=storage.root)
    if index_result.get("status") != "success":
        raise CaptureError("metadata-only search publication failed")
    registry = load_registry()
    graph_rows = []
    unresolved_rows = 0
    for row in rows:
        try:
            registry.resolve_scope(row.client_scope)
            registry.validate_capture_evidence_reference(row.client_scope, row.reference_path)
        except ClientScopeError:
            unresolved_rows += 1
            continue
        graph_rows.append(row)
    graph_result = BusinessBrainGraphService().publish_capture_metadata(graph_rows)
    if graph_result.get("metadata_only") is not True:
        raise CaptureError("metadata-only Graphify publication failed")
    return {
        "metadata_rows": len(rows),
        "metadata_rows_scope_unresolved": unresolved_rows,
        "search_status": "success",
        "graph_metadata_only": True,
        "graph_nodes": int(graph_result.get("node_count", len(rows))),
    }


def _restore_cursor(storage: CaptureStorage, prior: str | None) -> None:
    path = storage.provider_dir(PROVIDER_KEY) / "cursor.json"
    if prior is not None:
        storage.publish_cursor(PROVIDER_KEY, prior)
    elif path.exists():
        path.unlink()
        fsync_directory(path.parent)


def _receipt_base(status: str, *, scheduled: bool, action_counts: Counter[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "poll_id": "poll-" + stable_hash(utc_now(), os.getpid())[:20],
        "timestamp": utc_now(),
        "status": status,
        "provider": "composio-gmail-read-only",
        "mailbox_scope": "INBOX",
        "exclude_labels": ["SPAM", "TRASH", "SENT"],
        "direction": "inbound",
        "scheduled_entry": bool(scheduled),
        "provider_actions": dict(sorted(action_counts.items())),
        "gmail_mutations": 0,
        "attachments_opened": 0,
        "body_or_thread_reads": 0,
        "external_actions": 0,
        "token_usage_text": "Token usage: no agent invocation",
    }


def _week_key(timestamp: str) -> str:
    value = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    year, week, _day = value.isocalendar()
    return f"{year}-W{week:02d}"


def _capture_metrics(rows: list[dict[str, Any]], week: str) -> dict[str, Any]:
    selected = [row for row in rows if _week_key(str(row["timestamp"])) == week]
    attempts = [row for row in selected if row.get("status") not in {"correction", "connection_check"}]
    triage = Counter()
    actions = Counter()
    for row in selected:
        triage.update(row.get("deterministic_triage") or {})
        actions.update(row.get("provider_actions") or {})
    return {
        "polls_attempted": len(attempts),
        "polls_completed": sum(row.get("status") == "success" for row in attempts),
        "history_entries_received": sum(int(row.get("history_entries_received", 0)) for row in selected),
        "records_deduplicated": sum(int(row.get("records_deduplicated", 0)) for row in selected),
        "deterministic_triage": dict(sorted(triage.items())),
        "ambiguous_classifier_calls": sum(int(row.get("ambiguous_classifier_calls", 0)) for row in attempts),
        "stage2_exact_tokens": {"input": 0, "output": 0},
        "stage3_exact_tokens": {"input": 0, "output": 0},
        "human_review_proposals": sum(int(row.get("human_review_proposals", 0)) for row in selected),
        "needs_input_proposals": sum(int(row.get("needs_input_proposals", 0)) for row in selected),
        "processing_failures": sum(row.get("status") == "failed" for row in attempts),
        "cursor_replays": sum(bool(row.get("cursor_replay")) for row in attempts),
        "false_positive_findings": 0,
        "false_negative_findings": 0,
        "isolation_incidents": sum(bool(row.get("isolation_incident")) for row in attempts),
        "kill_switch_events": sum(row.get("status") == "kill_switch" for row in attempts),
        "provider_action_counts": dict(sorted(actions.items())),
        "contains_message_content": False,
        "whitelist_entries": 0,
    }


def _update_rollup() -> None:
    rows = _read_jsonl(POLL_RECEIPTS_PATH)
    if not rows:
        return
    week = _week_key(rows[-1]["timestamp"])
    CAPTURE_ROLLUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(CAPTURE_ROLLUPS, 0o700)
    path = CAPTURE_ROLLUPS / f"week-{week}.json"
    value = {"week": week, "capture": _capture_metrics(rows, week)}
    durable_replace_text(path, _json_bytes(value).decode("utf-8"))
    index_path = CAPTURE_ROLLUPS / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"weeks": [], "files": []}
    index["weeks"] = sorted(set(index.get("weeks") or []) | {week})
    index["files"] = [f"week-{item}.json" for item in index["weeks"]]
    durable_replace_text(index_path, _json_bytes(index).decode("utf-8"))


def _write_poll_receipt(value: dict[str, Any]) -> None:
    _append_json(POLL_RECEIPTS_PATH, value)
    _update_rollup()


def _assert_activation(storage: CaptureStorage) -> None:
    state = storage.control_state()
    if state["kill_switch"]:
        raise LiveCaptureDisabled("capture kill switch is active")
    if not state["live_capture_enabled"]:
        raise LiveCaptureDisabled("live capture control is disabled")
    try:
        activation = json.loads(ACTIVATION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiveCaptureDisabled("activation record is unavailable") from exc
    if activation != ACTIVATION_CONTRACT:
        raise LiveCaptureDisabled("activation record is invalid")


def poll_once(*, scheduled: bool, bootstrap_hours: int = 24) -> dict[str, Any]:
    storage = CaptureStorage()
    executor = ComposioReadOnlyExecutor()
    capture_result: dict[str, Any] | None = None
    try:
        with PollLock():
            try:
                _assert_activation(storage)
            except LiveCaptureDisabled:
                state = storage.control_state()
                status = "kill_switch" if state["kill_switch"] else "disabled"
                receipt = _receipt_base(status, scheduled=scheduled, action_counts=executor.action_counts)
                receipt.update({"cursor_advanced": False, "records_added": 0})
                _write_poll_receipt(receipt)
                return receipt
            prior = storage.cursor(PROVIDER_KEY)
            try:
                batch, metadata = _prepare_delta(
                    executor,
                    cursor=prior,
                    bootstrap_hours=max(1, min(int(bootstrap_hours), 24)),
                )
                capture = CaptureEngine(storage).run_once(PreparedDeltaAdapter(batch))
                capture_result = capture
                triage_counts: Counter[str] = Counter()
                created_needs_input = 0
                created_human_review = 0
                proposer = CaptureProposer(
                    storage=storage,
                    registry=load_registry(),
                    brain_loader=None,
                    queue_writer=CaptureQueueWriter(capture_mode="live"),
                    evidence_loader=lambda **_kwargs: (_ for _ in ()).throw(CaptureError("live content loader is disabled")),
                )
                for record in capture["records"]:
                    decision = CaptureTriage(storage).triage(record["record_id"])
                    triage_counts[decision.route] += 1
                    if decision.route == "discard":
                        _projection_for_discard(storage, decision)
                        continue
                    intent = (
                        "scope_resolution_required"
                        if decision.client_scope is None
                        else "stage3_model_unavailable_requires_liam"
                    )
                    proposal = proposer.propose_needs_input(decision, intent=intent)
                    created_needs_input += int(proposal["created"])
                projection = _publish_metadata(storage)
                receipt = _receipt_base("success", scheduled=scheduled, action_counts=executor.action_counts)
                receipt.update(metadata)
                receipt.update(projection)
                receipt.update({
                    "previous_cursor_sha256": _sha(prior) if prior else None,
                    "cursor_sha256": _sha(capture["cursor"]),
                    "cursor_advanced": capture["cursor"] != prior,
                    "cursor_replay": capture["cursor"] == prior,
                    "records_seen": len(capture["records"]),
                    "records_added": sum(bool(row["raw_appended"]) for row in capture["records"]),
                    "records_deduplicated": sum(not bool(row["raw_appended"]) for row in capture["records"]),
                    "deterministic_triage": dict(sorted(triage_counts.items())),
                    "ambiguous_classifier_calls": 0,
                    "human_review_proposals": created_human_review,
                    "needs_input_proposals": created_needs_input,
                    "client_scope_before_content_open": True,
                    "content_opened": False,
                    "isolation_incident": False,
                })
                _write_poll_receipt(receipt)
                storage.enforce_permissions()
                return receipt
            except Exception:
                _restore_cursor(storage, prior)
                raise
    except LiveCaptureDisabled as exc:
        receipt = _receipt_base("already_running", scheduled=scheduled, action_counts=executor.action_counts)
        receipt.update({"cursor_advanced": False, "records_added": 0, "error_class": _safe_error(exc)})
        _write_poll_receipt(receipt)
        return receipt
    except Exception as exc:
        isolation = isinstance(exc, ClientScopeError) or type(exc).__name__ == "ClientScopeError"
        if isolation:
            storage.set_control(live_capture_enabled=False, kill_switch=True)
        receipt = _receipt_base("failed", scheduled=scheduled, action_counts=executor.action_counts)
        added = sum(bool(row.get("raw_appended")) for row in (capture_result or {}).get("records", []))
        deduplicated = sum(not bool(row.get("raw_appended")) for row in (capture_result or {}).get("records", []))
        receipt.update({
            "cursor_advanced": False,
            "records_added": added,
            "records_deduplicated": deduplicated,
            "error_class": _safe_error(exc),
            "isolation_incident": isolation,
            "capture_disabled": isolation,
        })
        _write_poll_receipt(receipt)
        return receipt


def command_activate(args: argparse.Namespace) -> int:
    proof = Path(args.decision_proof).resolve()
    expected_root = (ROOT / "proofs" / "brain-reconciliation" / "activation").resolve()
    try:
        proof.relative_to(expected_root)
    except ValueError:
        raise SystemExit("activation decision proof is outside the adopted proof family")
    if not proof.is_file():
        raise SystemExit("activation decision proof is missing")
    storage = CaptureStorage()
    storage._replace_json(ACTIVATION_PATH, ACTIVATION_CONTRACT)
    storage.set_control(live_capture_enabled=True, kill_switch=False)
    result = {
        "status": "activated",
        "live_capture_enabled": True,
        "kill_switch": False,
        "activation_contract": ACTIVATION_CONTRACT["contract"],
        "decision_proof_sha256": _sha(proof.read_bytes()),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


def command_control(args: argparse.Namespace) -> int:
    storage = CaptureStorage()
    state = storage.control_state()
    if args.live is not None:
        state["live_capture_enabled"] = args.live == "on"
    if args.kill_switch is not None:
        state["kill_switch"] = args.kill_switch == "on"
    storage.set_control(**state)
    print(json.dumps({"status": "updated", **state}, sort_keys=True))
    return 0


def command_poll(args: argparse.Namespace) -> int:
    result = poll_once(scheduled=args.scheduled, bootstrap_hours=args.bootstrap_hours)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {"success", "disabled", "kill_switch", "already_running"} else 2


def command_lock_probe(args: argparse.Namespace) -> int:
    with PollLock():
        time.sleep(max(0.0, min(float(args.hold_seconds), 10.0)))
    print(json.dumps({"status": "lock_probe_complete"}))
    return 0


def command_observation_start(args: argparse.Namespace) -> int:
    storage = CaptureStorage()
    _assert_activation(storage)
    successful = [row for row in _read_jsonl(POLL_RECEIPTS_PATH) if row.get("status") == "success"]
    if not successful:
        raise SystemExit("observation cannot start before a successful live poll")
    now = dt.datetime.now(dt.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        local = now.astimezone(ZoneInfo("Europe/Dublin"))
    except Exception:
        local = now
    value = {
        "schema_version": 1,
        "started_at_utc": now.isoformat().replace("+00:00", "Z"),
        "started_at_europe_dublin": local.isoformat(),
        "start_condition": "successful_first_cycle_and_enabled_recurring_job_and_durable_activation_record",
        "schedule_job_sha256": str(args.schedule_job_sha256),
        "whitelist_entries": 0,
        "whitelist_active": False,
    }
    storage._replace_json(OBSERVATION_PATH, value)
    print(json.dumps(value, sort_keys=True))
    return 0


def command_status(_args: argparse.Namespace) -> int:
    storage = CaptureStorage()
    cursor = storage.cursor(PROVIDER_KEY)
    receipts = _read_jsonl(POLL_RECEIPTS_PATH)
    observation = None
    if OBSERVATION_PATH.exists():
        observation = json.loads(OBSERVATION_PATH.read_text(encoding="utf-8"))
    value = {
        "live_capture_enabled": storage.control_state()["live_capture_enabled"],
        "kill_switch": storage.control_state()["kill_switch"],
        "provider": "composio-gmail-read-only",
        "mailbox_scope": "INBOX",
        "poll_timeout_seconds": POLL_TIMEOUT_SECONDS,
        "cursor_initialized": cursor is not None,
        "cursor_sha256": _sha(cursor) if cursor else None,
        "last_poll": receipts[-1] if receipts else None,
        "observation": observation,
        "whitelist_entries": 0,
        "whitelist_active": False,
    }
    print(json.dumps(value, sort_keys=True))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="TTROS Phase 6B read-only Gmail capture")
    commands = root.add_subparsers(dest="command", required=True)
    activate = commands.add_parser("activate")
    activate.add_argument("--decision-proof", required=True)
    activate.set_defaults(handler=command_activate)
    control = commands.add_parser("control")
    control.add_argument("--live", choices=("on", "off"))
    control.add_argument("--kill-switch", choices=("on", "off"))
    control.set_defaults(handler=command_control)
    poll = commands.add_parser("poll")
    poll.add_argument("--scheduled", action="store_true")
    poll.add_argument("--bootstrap-hours", type=int, default=24)
    poll.set_defaults(handler=command_poll)
    lock = commands.add_parser("lock-probe")
    lock.add_argument("--hold-seconds", type=float, default=2.0)
    lock.set_defaults(handler=command_lock_probe)
    observe = commands.add_parser("observation-start")
    observe.add_argument("--schedule-job-sha256", required=True)
    observe.set_defaults(handler=command_observation_start)
    status = commands.add_parser("status")
    status.set_defaults(handler=command_status)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
