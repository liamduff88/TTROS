"""Dark communications capture, triage, and scoped proposal runtime.

All provider and model boundaries are disabled or deterministic fixtures in
Stage A. Raw evidence is never projected; only CaptureMetadataProjection may
enter search or Graphify.

Revisit: at the explicit live-capture activation gate. · Last touched: 2026-07-15.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

import jsonschema

try:
    from aos_paths import aos_root, assert_authoritative_root
    from aos_queue_storage import durable_append_text, durable_replace_text, fsync_directory, queue_write_lock
    from business_brain_context import BrainContextError, ScopedBrainLoader
    from business_brain_scope import CaptureIdentityResolution, ClientScopeError, ClientScopeRegistry, load_registry
except ModuleNotFoundError:  # package import in unittest/IDE contexts
    from tools.aos_paths import aos_root, assert_authoritative_root
    from tools.aos_queue_storage import durable_append_text, durable_replace_text, fsync_directory, queue_write_lock
    from tools.business_brain_context import BrainContextError, ScopedBrainLoader
    from tools.business_brain_scope import CaptureIdentityResolution, ClientScopeError, ClientScopeRegistry, load_registry


REPO_ROOT = aos_root()
DEFAULT_RUNTIME_ROOT = REPO_ROOT / "capture" / "runtime"
STAGE2_EVENT = "capture.stage2.local_deterministic_stub"
STAGE3_EVENT = "capture.stage3.deterministic_proposer"
LIVE_STAGE3_EVENT = "capture.stage3.live_deterministic_needs_input"
TOKEN_USAGE_TEXT = "Token usage: no agent invocation"
SAFE_HEADER_KEYS = {"list_id_present", "auto_submitted", "precedence", "category", "ambiguous_candidate"}
NOISE_CATEGORIES = {"newsletter", "notification", "spam", "vendor_noise", "list_mail"}
NOISE_PRECEDENCE = {"bulk", "list", "junk"}
METADATA_FIELDS = {
    "record_id",
    "reference_path",
    "client_scope",
    "linked_item_id",
    "subject_classification",
    "timestamp",
    "source_type",
    "triage_state",
    "proposal_state",
}


class CaptureError(RuntimeError):
    pass


class CaptureStorageError(CaptureError):
    pass


class LiveCaptureDisabled(CaptureError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def stable_hash(*parts: object) -> str:
    return hashlib.sha256("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "--", value.strip().lower()).strip("-")
    if not slug:
        raise CaptureStorageError("scope/provider key cannot be empty")
    return slug


def _history_sort_key(record: "CaptureEnvelope") -> tuple[int, str, str]:
    raw = str(record.history_id)
    return (int(raw) if raw.isdigit() else 2**63 - 1, raw, record.message_id)


@dataclass(frozen=True)
class CaptureEnvelope:
    provider: str
    message_id: str
    thread_id: str
    history_id: str
    timestamp: str
    sender: str
    subject: str
    source_type: str = "gmail"
    linked_item_id: str = ""
    headers: dict[str, Any] | None = None

    def validate(self) -> "CaptureEnvelope":
        if self.provider not in {"gmail_fixture", "gmail_composio"}:
            raise CaptureError("unsupported capture provider")
        for field_name in ("message_id", "thread_id", "history_id", "timestamp", "sender"):
            if not str(getattr(self, field_name) or "").strip():
                raise CaptureError(f"capture envelope requires {field_name}")
        headers = self.headers or {}
        unknown = set(headers) - SAFE_HEADER_KEYS
        if unknown:
            raise CaptureError(f"capture envelope contains unapproved header fields: {', '.join(sorted(unknown))}")
        return self

    @property
    def deduplication_key(self) -> str:
        return stable_hash(self.provider, self.message_id)

    @property
    def record_id(self) -> str:
        return f"cap-{self.deduplication_key[:24]}"


@dataclass(frozen=True)
class DeltaBatch:
    next_cursor: str
    envelopes: tuple[CaptureEnvelope, ...]


class DeltaAdapter(Protocol):
    provider_key: str
    live: bool

    def read_delta(self, cursor: str | None) -> DeltaBatch: ...


@dataclass(frozen=True)
class CaptureMetadataProjection:
    record_id: str
    reference_path: str
    client_scope: str
    linked_item_id: str
    subject_classification: str
    timestamp: str
    source_type: str
    triage_state: str
    proposal_state: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "CaptureMetadataProjection":
        if set(value) != METADATA_FIELDS:
            extra = sorted(set(value) - METADATA_FIELDS)
            missing = sorted(METADATA_FIELDS - set(value))
            raise CaptureError(f"capture projection fields are not allowlisted; extra={extra}, missing={missing}")
        row = cls(**{key: str(value[key] or "") for key in METADATA_FIELDS})
        if not row.record_id.startswith("cap-"):
            raise CaptureError("capture projection record_id is malformed")
        if not row.reference_path.startswith(f"capture:{row.client_scope}:"):
            raise CaptureError("capture projection reference is not scope-bound")
        if row.source_type not in {"gmail", "gmail_fixture"}:
            raise CaptureError("capture projection source_type is unsupported")
        return row

    def to_dict(self) -> dict[str, str]:
        return {key: str(getattr(self, key)) for key in sorted(METADATA_FIELDS)}


class CaptureStorage:
    """One permission-restricted, append-only capture runtime."""

    def __init__(self, root: Path = DEFAULT_RUNTIME_ROOT, *, repo_root: Path = REPO_ROOT):
        self.root = Path(root).resolve()
        self.repo_root = Path(repo_root).resolve()
        assert_authoritative_root(self.root.parent)
        try:
            self.root.relative_to(self.repo_root)
        except ValueError as exc:
            raise CaptureStorageError("capture runtime must stay inside the authoritative Linux repository") from exc
        self._ensure_directory(self.root)
        for child in ("control", "providers", "scopes"):
            self._ensure_directory(self.root / child)
        if not self.control_path.exists():
            self._replace_json(self.control_path, {"live_capture_enabled": False, "kill_switch": False})
        self.enforce_permissions()

    @property
    def control_path(self) -> Path:
        return self.root / "control" / "state.json"

    def _ensure_directory(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path, 0o700)

    def _ensure_parent(self, path: Path) -> None:
        current = path.parent
        missing = []
        while current != self.root.parent and not current.exists():
            missing.append(current)
            current = current.parent
        for directory in reversed(missing):
            self._ensure_directory(directory)
        for directory in [path.parent, *path.parent.parents]:
            if directory == self.root.parent:
                break
            if directory.exists():
                os.chmod(directory, 0o700)

    def _replace_json(self, path: Path, value: dict[str, Any]) -> None:
        self._ensure_parent(path)
        durable_replace_text(path, json.dumps(value, sort_keys=True) + "\n")
        os.chmod(path, 0o600)

    def _append_json(self, path: Path, value: dict[str, Any]) -> None:
        self._ensure_parent(path)
        encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        existed = path.exists()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)
        if not existed:
            fsync_directory(path.parent)

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CaptureStorageError(f"invalid capture JSONL at {path.name}:{line_number}") from exc
            if not isinstance(value, dict):
                raise CaptureStorageError("capture JSONL record must be an object")
            rows.append(value)
        return rows

    def control_state(self) -> dict[str, bool]:
        try:
            value = json.loads(self.control_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CaptureStorageError("capture control state is unavailable") from exc
        if set(value) != {"live_capture_enabled", "kill_switch"} or not all(isinstance(value[key], bool) for key in value):
            raise CaptureStorageError("capture control state is malformed")
        return value

    def set_control_for_fixture(self, *, kill_switch: bool) -> None:
        """Local-only test control; never creates live activation authority."""
        self._replace_json(self.control_path, {"live_capture_enabled": False, "kill_switch": bool(kill_switch)})

    def set_control(self, *, live_capture_enabled: bool, kill_switch: bool) -> None:
        """Publish the two-field production control atomically."""
        self._replace_json(self.control_path, {
            "live_capture_enabled": bool(live_capture_enabled),
            "kill_switch": bool(kill_switch),
        })

    def provider_dir(self, provider_key: str) -> Path:
        path = self.root / "providers" / _safe_slug(provider_key)
        self._ensure_directory(path)
        return path

    def scope_dir(self, client_scope: str | None) -> Path:
        scope = client_scope or "_unresolved"
        path = self.root / "scopes" / _safe_slug(scope)
        for child in (path, path / "raw", path / "derived"):
            self._ensure_directory(child)
        return path

    def cursor(self, provider_key: str) -> str | None:
        path = self.provider_dir(provider_key) / "cursor.json"
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CaptureStorageError("capture cursor is invalid") from exc
        cursor = str(value.get("cursor") or "")
        return cursor or None

    def publish_cursor(self, provider_key: str, cursor: str, *, failure_injection: str | None = None) -> None:
        path = self.provider_dir(provider_key) / "cursor.json"
        self._ensure_parent(path)
        candidate = path.with_name(f".{path.name}.{uuid.uuid4().hex}.candidate")
        try:
            with candidate.open("w", encoding="utf-8") as handle:
                json.dump({"cursor": str(cursor), "updated_at": utc_now()}, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fchmod(handle.fileno(), 0o600)
                os.fsync(handle.fileno())
            if failure_injection == "during_cursor_publication":
                raise CaptureStorageError("injected cursor publication failure")
            os.replace(candidate, path)
            fsync_directory(path.parent)
            os.chmod(path, 0o600)
        finally:
            candidate.unlink(missing_ok=True)

    def processing_rows(self, provider_key: str) -> list[dict[str, Any]]:
        return self._read_jsonl(self.provider_dir(provider_key) / "processing.jsonl")

    def append_processing(self, provider_key: str, value: dict[str, Any]) -> None:
        self._append_json(self.provider_dir(provider_key) / "processing.jsonl", value)

    def raw_records(self) -> list[dict[str, Any]]:
        rows = []
        for path in sorted((self.root / "scopes").glob("*/raw/records.jsonl")):
            rows.extend(self._read_jsonl(path))
        return rows

    def raw_record(self, record_id: str) -> dict[str, Any]:
        matches = [row for row in self.raw_records() if row.get("record_id") == record_id]
        if len(matches) != 1:
            raise CaptureStorageError("capture raw record is missing or duplicated")
        return matches[0]

    def append_raw(self, client_scope: str | None, value: dict[str, Any]) -> bool:
        record_id = str(value.get("record_id") or "")
        if any(row.get("record_id") == record_id for row in self.raw_records()):
            return False
        self._append_json(self.scope_dir(client_scope) / "raw" / "records.jsonl", value)
        return True

    def append_fixture_evidence(
        self,
        *,
        client_scope: str,
        record_id: str,
        body: str,
        thread_text: str,
        attachments: list[str],
    ) -> str:
        raw = self.raw_record(record_id)
        if raw.get("client_scope") != client_scope or raw.get("scope_state") != "matched":
            raise ClientScopeError("fixture evidence scope does not match the immutable raw record")
        path = self.scope_dir(client_scope) / "raw" / "evidence.jsonl"
        if any(row.get("record_id") == record_id for row in self._read_jsonl(path)):
            return str(raw["evidence_reference"])
        self._append_json(path, {
            "record_id": record_id,
            "body": str(body),
            "thread_text": str(thread_text),
            "attachments": [str(value) for value in attachments],
            "fixture_only": True,
        })
        return str(raw["evidence_reference"])

    def load_fixture_evidence(
        self,
        *,
        client_scope: str,
        reference: str,
        record_id: str,
        on_open: Callable[[str, str], None] | None = None,
    ) -> dict[str, Any]:
        raw = self.raw_record(record_id)
        if raw.get("client_scope") != client_scope or raw.get("evidence_reference") != reference:
            raise ClientScopeError("capture evidence reference is cross-scope or invalid")
        if on_open:
            on_open("evidence", client_scope)
        path = self.scope_dir(client_scope) / "raw" / "evidence.jsonl"
        matches = [row for row in self._read_jsonl(path) if row.get("record_id") == record_id]
        if len(matches) != 1:
            raise CaptureStorageError("fixture evidence is missing or duplicated")
        return matches[0]

    def append_derived(self, client_scope: str | None, kind: str, value: dict[str, Any]) -> bool:
        if kind not in {"triage", "proposals", "metadata", "operational_receipts"}:
            raise CaptureStorageError("unknown capture derived record class")
        path = self.scope_dir(client_scope) / "derived" / f"{kind}.jsonl"
        if value in self._read_jsonl(path):
            return False
        self._append_json(path, value)
        return True

    def metadata_rows(self) -> list[CaptureMetadataProjection]:
        latest: dict[str, CaptureMetadataProjection] = {}
        for path in sorted((self.root / "scopes").glob("*/derived/metadata.jsonl")):
            for value in self._read_jsonl(path):
                row = CaptureMetadataProjection.from_mapping(value)
                latest[row.reference_path] = row
        return [latest[key] for key in sorted(latest)]

    def enforce_permissions(self) -> None:
        for dirpath, dirnames, filenames in os.walk(self.root):
            os.chmod(dirpath, 0o700)
            for name in dirnames:
                os.chmod(Path(dirpath) / name, 0o700)
            for name in filenames:
                os.chmod(Path(dirpath) / name, 0o600)

    def permission_report(self) -> dict[str, Any]:
        wrong = []
        for dirpath, _dirnames, filenames in os.walk(self.root):
            if (os.stat(dirpath).st_mode & 0o777) != 0o700:
                wrong.append(str(Path(dirpath)))
            for name in filenames:
                path = Path(dirpath) / name
                if (os.stat(path).st_mode & 0o777) != 0o600:
                    wrong.append(str(path))
        return {"directories": "0700", "files": "0600", "wrong": wrong, "ok": not wrong}


class FixtureDeltaAdapter:
    live = False

    def __init__(self, batch: DeltaBatch, *, provider_key: str = "gmail-fixture"):
        self.batch = batch
        self.provider_key = provider_key
        self.activity_count = 0

    def read_delta(self, cursor: str | None) -> DeltaBatch:
        self.activity_count += 1
        return self.batch


class ComposioGmailLiveAdapter:
    """Production-facing delta contract; guarded and never activated in Stage A."""

    live = True
    provider_key = "gmail-live"

    def __init__(
        self,
        *,
        storage: CaptureStorage,
        executor: Callable[[str, dict[str, Any]], dict[str, Any]],
        activation_path: Path,
        no_live: bool = True,
    ):
        self.storage = storage
        self.executor = executor
        self.activation_path = Path(activation_path)
        self.no_live = no_live

    def _guard(self) -> None:
        state = self.storage.control_state()
        if self.no_live or not state["live_capture_enabled"] or state["kill_switch"]:
            raise LiveCaptureDisabled("live Gmail capture is dark/disabled")
        try:
            activation = json.loads(self.activation_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LiveCaptureDisabled("separate live-capture activation record is absent") from exc
        if activation != {"approved": True, "contract": "gmail_history_metadata_read_only"}:
            raise LiveCaptureDisabled("separate live-capture activation record is invalid")

    def read_delta(self, cursor: str | None) -> DeltaBatch:
        self._guard()
        if cursor is None:
            profile = self.executor("GMAIL_GET_PROFILE", {})
            checkpoint = str(profile.get("historyId") or profile.get("history_id") or "")
            if not checkpoint:
                raise CaptureError("GMAIL_GET_PROFILE did not return a historyId checkpoint")
            return DeltaBatch(next_cursor=checkpoint, envelopes=())
        response = self.executor("GMAIL_LIST_HISTORY", {"start_history_id": cursor})
        next_cursor = str(response.get("historyId") or response.get("history_id") or cursor)
        envelopes = tuple(CaptureEnvelope(**row).validate() for row in response.get("envelopes") or [])
        return DeltaBatch(next_cursor=next_cursor, envelopes=envelopes)

    def timestamp_fallback(self, *, after_timestamp: str) -> DeltaBatch:
        self._guard()
        response = self.executor("GMAIL_FETCH_EMAILS", {
            "query": f"after:{after_timestamp}",
            "label_ids": ["INBOX"],
            "include_payload": False,
            "include_spam_trash": False,
            "max_results": 100,
        })
        envelopes = tuple(CaptureEnvelope(**row).validate() for row in response.get("envelopes") or [])
        return DeltaBatch(next_cursor=str(response.get("historyId") or ""), envelopes=envelopes)


class CaptureEngine:
    def __init__(self, storage: CaptureStorage, registry: ClientScopeRegistry | None = None):
        self.storage = storage
        self.registry = registry or load_registry()

    @staticmethod
    def _validate_cursor(previous: str | None, next_cursor: str) -> None:
        if not str(next_cursor or ""):
            raise CaptureError("delta batch requires a next cursor")
        if previous and previous.isdigit() and next_cursor.isdigit() and int(next_cursor) < int(previous):
            raise CaptureError("delta cursor moved backwards")

    def run_once(self, adapter: DeltaAdapter, *, failure_injection: str | None = None) -> dict[str, Any]:
        if self.storage.control_state()["kill_switch"]:
            raise LiveCaptureDisabled("capture kill switch is active")
        previous = self.storage.cursor(adapter.provider_key)
        batch = adapter.read_delta(previous)
        self._validate_cursor(previous, batch.next_cursor)
        envelopes = sorted((record.validate() for record in batch.envelopes), key=_history_sort_key)
        processed_ids = {str(row.get("record_id") or "") for row in self.storage.processing_rows(adapter.provider_key)}
        captured = []
        with queue_write_lock(self.storage.repo_root):
            for envelope in envelopes:
                resolution = self.registry.resolve_capture_identity(sender=envelope.sender, thread_id=envelope.thread_id)
                client_scope = resolution.client_scope
                evidence_reference = f"capture:{client_scope or '_unresolved'}:{envelope.record_id}"
                raw = {
                    "schema_version": 1,
                    "record_id": envelope.record_id,
                    "deduplication_key": envelope.deduplication_key,
                    "provider": envelope.provider,
                    "provider_message_id": envelope.message_id,
                    "provider_thread_id": envelope.thread_id,
                    "history_id": envelope.history_id,
                    "timestamp": envelope.timestamp,
                    "sender_sha256": self.registry.capture_identity_hash(envelope.sender),
                    "thread_sha256": self.registry.capture_identity_hash(envelope.thread_id),
                    "subject": envelope.subject,
                    "source_type": envelope.source_type,
                    "linked_item_id": envelope.linked_item_id,
                    "safe_headers": dict(envelope.headers or {}),
                    "scope_state": resolution.state,
                    "client_scope": client_scope,
                    "scope_kind": resolution.scope_kind,
                    "matched_by": list(resolution.matched_by),
                    "evidence_reference": evidence_reference,
                }
                if failure_injection == "before_raw_append":
                    raise CaptureStorageError("injected failure before raw append")
                appended = self.storage.append_raw(client_scope, raw)
                if failure_injection == "after_raw_append":
                    raise CaptureStorageError("injected failure after raw append")
                if envelope.record_id not in processed_ids:
                    self.storage.append_processing(adapter.provider_key, {
                        "record_id": envelope.record_id,
                        "deduplication_key": envelope.deduplication_key,
                        "client_scope": client_scope,
                        "processed_at": utc_now(),
                    })
                    processed_ids.add(envelope.record_id)
                if failure_injection == "after_processing_state":
                    raise CaptureStorageError("injected failure after processing state")
                captured.append({"record_id": envelope.record_id, "raw_appended": appended, "client_scope": client_scope, "scope_state": resolution.state})
            self.storage.publish_cursor(adapter.provider_key, batch.next_cursor, failure_injection=failure_injection)
        self.storage.enforce_permissions()
        return {
            "status": "success",
            "previous_cursor": previous,
            "cursor": batch.next_cursor,
            "records": captured,
            "token_usage_text": TOKEN_USAGE_TEXT,
        }


class LocalDeterministicClassifier:
    """Fully local Stage 2 interface stub; it never receives content."""

    def __init__(self, decision: bool = True):
        self.decision = bool(decision)
        self.invocations: list[dict[str, Any]] = []

    def classify(self, metadata: dict[str, Any]) -> bool:
        allowed = {"record_id", "timestamp", "source_type", "subject_classification", "header_flags"}
        if set(metadata) != allowed:
            raise CaptureError("Stage 2 classifier received fields outside its metadata allowlist")
        self.invocations.append(json.loads(json.dumps(metadata)))
        return self.decision


def subject_classification(subject: str) -> str:
    value = str(subject or "").lower()
    if any(term in value for term in ("newsletter", "unsubscribe", "weekly digest")):
        return "newsletter"
    if any(term in value for term in ("notification", "alert", "automated")):
        return "notification"
    if any(term in value for term in ("approved", "go ahead", "please proceed")):
        return "inbound_claimed_approval"
    return "business_message"


@dataclass(frozen=True)
class TriageDecision:
    record_id: str
    state: str
    route: str
    client_scope: str | None
    subject_classification: str
    classifier_invocation_id: str | None = None
    classifier_result: bool | None = None

    def to_safe_dict(self) -> dict[str, Any]:
        return asdict(self)


class CaptureTriage:
    def __init__(self, storage: CaptureStorage):
        self.storage = storage

    def triage(self, record_id: str, *, classifier: LocalDeterministicClassifier | None = None) -> TriageDecision:
        raw = self.storage.raw_record(record_id)
        headers = dict(raw.get("safe_headers") or {})
        classification = subject_classification(str(raw.get("subject") or ""))
        is_noise = (
            classification in {"newsletter", "notification"}
            or bool(headers.get("list_id_present"))
            or str(headers.get("auto_submitted") or "").lower() not in {"", "no"}
            or str(headers.get("precedence") or "").lower() in NOISE_PRECEDENCE
            or str(headers.get("category") or "").lower() in NOISE_CATEGORIES
        )
        if is_noise:
            decision = TriageDecision(record_id, "triaged", "discard", raw.get("client_scope"), classification)
        elif raw.get("scope_state") in {"ambiguous", "conflicting"}:
            decision = TriageDecision(record_id, "needs_input", str(raw.get("scope_state")), None, classification)
        elif raw.get("scope_state") == "matched":
            route = "internal_global" if raw.get("scope_kind") == "global" else "client"
            decision = TriageDecision(record_id, "triaged", route, str(raw.get("client_scope")), classification)
        elif headers.get("ambiguous_candidate") is True:
            if classifier is None:
                raise CaptureError("ambiguous survivor requires the local deterministic classifier interface")
            payload = {
                "record_id": record_id,
                "timestamp": str(raw.get("timestamp") or ""),
                "source_type": str(raw.get("source_type") or ""),
                "subject_classification": classification,
                "header_flags": sorted(key for key, value in headers.items() if bool(value)),
            }
            result = classifier.classify(payload)
            invocation = f"stage2-{stable_hash(record_id, json.dumps(payload, sort_keys=True))[:20]}"
            decision = TriageDecision(record_id, "needs_input" if result else "triaged", "survivor_unresolved" if result else "discard", None, classification, invocation, result)
        else:
            decision = TriageDecision(record_id, "needs_input", "unresolved_identity", None, classification)
        self.storage.append_derived(decision.client_scope, "triage", decision.to_safe_dict())
        return decision


def zero_token_usage() -> dict[str, Any]:
    return {
        "orchestrator": {"input": 0, "output": 0},
        "subagents": [],
        "workbenches": [],
        "totals": {"input": 0, "output": 0},
        "est_cost_usd": 0,
        "unavailable": [],
    }


class CaptureLedgerWriter:
    def __init__(self, root: Path = REPO_ROOT, *, skill: str = "capture_dark_fixture"):
        self.root = Path(root).resolve()
        self.skill = skill

    def _append_unique(self, relative_path: str, schema_path: str, row: dict[str, Any], effect_id: str) -> bool:
        target = self.root / relative_path
        if target.exists():
            for line in target.read_text(encoding="utf-8").splitlines():
                try:
                    if json.loads(line).get("effect_id") == effect_id:
                        return False
                except json.JSONDecodeError:
                    continue
        schema = json.loads((self.root / schema_path).read_text(encoding="utf-8"))
        jsonschema.validate(row, schema)
        row = {**row, "effect_id": effect_id}
        durable_append_text(self.root, target, json.dumps(row, sort_keys=True) + "\n")
        return True

    def token(self, *, item_id: str, event: str, invocation_id: str, model_requested: str) -> bool:
        row = {
            "item_id": item_id,
            "invocation_id": invocation_id,
            "event": event,
            "lane": "operations",
            "profile": "aos-ops",
            "timestamp": utc_now(),
            "escalated": False,
            "model_requested": model_requested,
            "model_confirmed": "no-agent-invocation",
            "budget_class": "light",
            "token_usage": zero_token_usage(),
        }
        return self._append_unique("queue/token_ledger.jsonl", "queue/token_ledger_schema.json", row, f"{event}:{invocation_id}")

    def run(self, *, item_id: str, status: str, receipt: str, brain_context_used: list[dict[str, Any]]) -> bool:
        row = {
            "item_id": item_id,
            "lane": "operations",
            "profile": "aos-ops",
            "skill": self.skill,
            "created": utc_now(),
            "status": status,
            "escalated": False,
            "budget_class": "light",
            "receipt": receipt,
            "memory_promotion": [],
            "brain_context_status": "used" if brain_context_used else "missing",
            "brain_context_used": brain_context_used,
        }
        effect = f"capture-stage3:{item_id}:{stable_hash(receipt)[:16]}"
        return self._append_unique("queue/run_ledger.jsonl", "queue/run_ledger_schema.json", row, effect)


_QUEUE_TOOL = None


def _queue_tool():
    global _QUEUE_TOOL
    if _QUEUE_TOOL is None:
        path = REPO_ROOT / "tools" / "aos-queue.py"
        spec = importlib.util.spec_from_file_location("aos_queue_capture_runtime", path)
        if spec is None or spec.loader is None:
            raise CaptureError("existing queue tool could not be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _QUEUE_TOOL = module
    return _QUEUE_TOOL


class CaptureQueueWriter:
    def __init__(
        self,
        root: Path = REPO_ROOT,
        *,
        ledger: CaptureLedgerWriter | None = None,
        capture_mode: str = "fixture",
    ):
        if capture_mode not in {"fixture", "live"}:
            raise CaptureError("capture queue mode must be fixture or live")
        self.root = Path(root).resolve()
        self.capture_mode = capture_mode
        self.ledger = ledger or CaptureLedgerWriter(
            self.root,
            skill="capture_dark_fixture" if capture_mode == "fixture" else "capture_live_read_only",
        )

    def create_or_get(self, *, status: str, proposal: dict[str, Any]) -> tuple[dict[str, Any], bool, str]:
        if status not in {"human_review", "needs_input"}:
            raise CaptureError("capture proposals use only human_review or needs_input")
        tool = _queue_tool()
        proposal_key = str(proposal["proposal_key"])
        with tool.queue_write_lock(self.root):
            tool.ensure_queue(self.root)
            items = tool.load_items(self.root)
            existing = next((row for row in items if (row.get("capture_proposal") or {}).get("proposal_key") == proposal_key), None)
            if existing:
                latest = (existing.get("receipts") or [{}])[-1]
                return existing, False, str(latest.get("path") or "") if isinstance(latest, dict) else str(latest)
            fixture = self.capture_mode == "fixture"
            args = argparse.Namespace(
                title=(f"Block 3 fixture capture proposal {proposal['record_id']}" if fixture else "Live Gmail capture requires review"),
                requested_by="Block 3 fixture" if fixture else "Phase 6B live capture",
                owner_type="agent",
                owner="operations",
                status=status,
                priority=1,
                source="capture/fixture" if fixture else "capture/gmail-live-read-only",
                tags="block-3-fixture,proposed_from_capture" if fixture else "phase-6b-live,proposed_from_capture",
                context=(
                    f"Synthetic Block 3 capture fixture. Intent: {proposal['intent']}. No external action is authorized."
                    if fixture else
                    f"Read-only live Gmail evidence requires Liam review. Intent: {proposal['intent']}. No message content or external action is included."
                ),
                sources=",".join(proposal.get("evidence_references") or []),
                allowed_actions="local_read,local_review,review_close_blocked",
                stop_conditions="external_send,connector_action,calendar_action,brain_auto_promotion",
                definition_of_done="Review the synthetic proposal through the existing Needs Me path without external action.",
                parent_id=None,
                step_index=None,
                depends_on="",
                on_complete=None,
                workbench=None,
                client_scope=proposal.get("client_scope") or "",
                context_classification="knowledge_sensitive",
                brain_context_status="used" if proposal.get("brain_context_used") else "missing",
                brain_context_used=json.dumps(proposal.get("brain_context_used") or []),
                degraded_context=None,
                promotion_proposal=None,
                capture_proposal=json.dumps(proposal),
            )
            item = tool.create_item(self.root, args)
            receipt_path = (
                f"queue/receipts/{item['id']}-block-3-capture-fixture.json"
                if fixture else f"queue/receipts/{item['id']}-phase-6b-capture-live.json"
            )
            receipt = {
                "schema_version": 1,
                "item_id": item["id"],
                "status": status,
                "proposal_key": proposal_key,
                "record_id": proposal["record_id"],
                "client_scope": proposal.get("client_scope"),
                "evidence_references": proposal.get("evidence_references") or [],
                "brain_context_used": proposal.get("brain_context_used") or [],
                "external_action": "none",
                "token_usage_text": TOKEN_USAGE_TEXT,
            }
            durable_replace_text(self.root / receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
            item = tool.attach_receipt(self.root, item["id"], receipt_path, status)
            items = tool.load_items(self.root)
            item = tool.find_item(items, item["id"])
            item["capture_proposal"]["receipt_reference"] = receipt_path
            item["updated_at"] = tool.now_iso()
            tool.save_items(self.root, items)
        return item, True, receipt_path

    def update_token_references(self, item_id: str, references: list[str]) -> dict[str, Any]:
        tool = _queue_tool()
        with tool.queue_write_lock(self.root):
            items = tool.load_items(self.root)
            item = tool.find_item(items, item_id)
            proposal = item.get("capture_proposal")
            if not isinstance(proposal, dict):
                raise CaptureError("capture proposal is missing from its queue item")
            exact = list(dict.fromkeys(str(value) for value in references if str(value)))
            if proposal.get("token_references") != exact:
                proposal["token_references"] = exact
                item["updated_at"] = tool.now_iso()
                tool.save_items(self.root, items)
            return item


class CaptureProposer:
    def __init__(
        self,
        *,
        storage: CaptureStorage,
        registry: ClientScopeRegistry,
        brain_loader: ScopedBrainLoader | None,
        queue_writer: CaptureQueueWriter,
        evidence_loader: Callable[..., dict[str, Any]],
        search_selector: Callable[..., dict[str, Any]] | None = None,
        graph_selector: Callable[..., dict[str, Any]] | None = None,
    ):
        self.storage = storage
        self.registry = registry
        self.brain_loader = brain_loader
        self.queue_writer = queue_writer
        self.evidence_loader = evidence_loader
        self.search_selector = search_selector
        self.graph_selector = graph_selector

    def _safe_proposal(
        self,
        *,
        raw: dict[str, Any],
        decision: TriageDecision,
        client_scope: str | None,
        brain_context_used: list[dict[str, Any]],
        search_targets: list[str],
        graph_targets: list[str],
        intent: str,
    ) -> dict[str, Any]:
        record_id = str(raw["record_id"])
        proposal_key = stable_hash("capture-proposal", record_id, decision.route)
        reference = str(raw["evidence_reference"])
        proposal = {
            "fixture_marker": "block-3-synthetic" if self.queue_writer.capture_mode == "fixture" else "phase-6b-live",
            "proposal_key": proposal_key,
            "record_id": record_id,
            "evidence_references": [reference],
            "client_scope": client_scope,
            "linked_item_id": str(raw.get("linked_item_id") or ""),
            "intent": intent,
            "confidence": "deterministic_fixture" if self.queue_writer.capture_mode == "fixture" else "deterministic_fail_closed",
            "permitted_metadata": {
                "subject_classification": decision.subject_classification,
                "timestamp": str(raw["timestamp"]),
                "source_type": str(raw["source_type"]),
                "triage_state": decision.state,
            },
            "brain_context_used": brain_context_used,
            "search_targets": search_targets,
            "graphify_targets": graph_targets,
            "receipt_reference": "pending",
            "token_references": [value for value in (decision.classifier_invocation_id,) if value],
            "communications_fact_promotion": "liam_review_required",
            "inbound_approval_language_is_evidence_only": True,
            "external_actions_allowed": False,
        }
        if self.queue_writer.capture_mode == "fixture":
            proposal["source_fixture_ids"] = {
                "provider": str(raw["provider"]),
                "message_id": str(raw["provider_message_id"]),
                "thread_id": str(raw["provider_thread_id"]),
            }
        return proposal

    @staticmethod
    def _search_paths(result: dict[str, Any]) -> list[str]:
        paths = []
        for group in (result.get("groups") or {}).values():
            paths.extend(str(row.get("path") or "") for row in group if row.get("path"))
        return sorted(set(paths))

    def propose(
        self,
        decision: TriageDecision,
        *,
        brain_pointers: Iterable[str] = (),
        query: str = "",
    ) -> dict[str, Any]:
        raw = self.storage.raw_record(decision.record_id)
        client_scope = decision.client_scope
        if not client_scope:
            proposal = self._safe_proposal(
                raw=raw,
                decision=decision,
                client_scope=None,
                brain_context_used=[],
                search_targets=[],
                graph_targets=[],
                intent="scope_resolution_required",
            )
            item, created, receipt_path = self.queue_writer.create_or_get(status="needs_input", proposal=proposal)
            token_refs = self._record_ledgers(item, decision, receipt_path, [])
            item = self.queue_writer.update_token_references(str(item["id"]), token_refs)
            self._record_projection(raw, decision, "needs_input", item.get("id", ""))
            return {"status": "needs_input", "item": item, "created": created, "content_opened": False}

        self.registry.resolve_scope(client_scope)
        reference = self.registry.validate_capture_evidence_reference(client_scope, str(raw["evidence_reference"]))
        evidence = self.evidence_loader(client_scope=client_scope, reference=reference, record_id=decision.record_id)
        if self.brain_loader is None:
            raise BrainContextError("Stage 3 requires the Block 2 scoped Brain loader")
        brain = self.brain_loader.retrieve(
            work={"client_scope": client_scope, "business_output": True},
            pointers=brain_pointers,
            query=query,
            discovery_mode="explicit",
        )
        search_targets: list[str] = []
        if self.search_selector is not None:
            search_result = self.search_selector(query=query, client_scope=client_scope)
            search_targets = self._search_paths(search_result)
        graph_targets: list[str] = []
        if self.graph_selector is not None:
            graph_result = self.graph_selector(query=query, client_scope=client_scope)
            graph_targets = sorted(str(row.get("path") or "") for row in graph_result.get("targets") or [] if row.get("path"))
        intent = "review_inbound_evidence"
        if any(term in str(evidence.get("body") or "").lower() for term in ("approved", "go ahead", "please proceed")):
            intent = "review_inbound_claimed_approval_as_evidence"
        proposal = self._safe_proposal(
            raw=raw,
            decision=decision,
            client_scope=client_scope,
            brain_context_used=brain.brain_context_used,
            search_targets=search_targets,
            graph_targets=graph_targets,
            intent=intent,
        )
        item, created, receipt_path = self.queue_writer.create_or_get(status="human_review", proposal=proposal)
        token_refs = self._record_ledgers(item, decision, receipt_path, brain.brain_context_used)
        item = self.queue_writer.update_token_references(str(item["id"]), token_refs)
        self._record_projection(raw, decision, "human_review", item.get("id", ""))
        return {"status": "human_review", "item": item, "created": created, "content_opened": True}

    def propose_needs_input(self, decision: TriageDecision, *, intent: str) -> dict[str, Any]:
        """Create a bounded proposal without opening content or scoped knowledge."""
        raw = self.storage.raw_record(decision.record_id)
        proposal = self._safe_proposal(
            raw=raw,
            decision=decision,
            client_scope=decision.client_scope,
            brain_context_used=[],
            search_targets=[],
            graph_targets=[],
            intent=intent,
        )
        item, created, receipt_path = self.queue_writer.create_or_get(status="needs_input", proposal=proposal)
        token_refs = self._record_ledgers(item, decision, receipt_path, [])
        item = self.queue_writer.update_token_references(str(item["id"]), token_refs)
        self._record_projection(raw, decision, "needs_input", item.get("id", ""))
        return {"status": "needs_input", "item": item, "created": created, "content_opened": False}

    def _record_ledgers(self, item: dict[str, Any], decision: TriageDecision, receipt_path: str, brain_context_used: list[dict[str, Any]]) -> list[str]:
        item_id = str(item["id"])
        references = []
        if decision.classifier_invocation_id:
            self.queue_writer.ledger.token(
                item_id=item_id,
                event=STAGE2_EVENT,
                invocation_id=decision.classifier_invocation_id,
                model_requested="local-deterministic-stub",
            )
            references.append(decision.classifier_invocation_id)
        stage3_invocation = f"stage3-{stable_hash(item_id, decision.record_id)[:20]}"
        self.queue_writer.ledger.token(
            item_id=item_id,
            event=STAGE3_EVENT if self.queue_writer.capture_mode == "fixture" else LIVE_STAGE3_EVENT,
            invocation_id=stage3_invocation,
            model_requested="none",
        )
        self.queue_writer.ledger.run(item_id=item_id, status=str(item["status"]), receipt=receipt_path, brain_context_used=brain_context_used)
        references.append(stage3_invocation)
        return references

    def _record_projection(self, raw: dict[str, Any], decision: TriageDecision, proposal_state: str, linked_item_id: str) -> None:
        projection = CaptureMetadataProjection(
            record_id=str(raw["record_id"]),
            reference_path=str(raw["evidence_reference"]),
            client_scope=str(decision.client_scope or "_unresolved"),
            linked_item_id=linked_item_id,
            subject_classification=decision.subject_classification,
            timestamp=str(raw["timestamp"]),
            source_type="gmail_fixture" if raw.get("provider") == "gmail_fixture" else "gmail",
            triage_state=decision.state,
            proposal_state=proposal_state,
        )
        self.storage.append_derived(decision.client_scope, "metadata", projection.to_dict())
        self.storage.append_derived(decision.client_scope, "operational_receipts", {
            "record_id": projection.record_id,
            "reference_path": projection.reference_path,
            "client_scope": projection.client_scope,
            "proposal_state": proposal_state,
            "linked_item_id": linked_item_id,
            "token_usage_text": TOKEN_USAGE_TEXT,
        })


def capture_document(row: CaptureMetadataProjection, *, registry: ClientScopeRegistry) -> dict[str, Any]:
    registry.validate_search_source(row.client_scope, "capture_metadata")
    resolved = registry.scope_for_search_identity("capture_metadata", row.reference_path)
    if resolved != row.client_scope:
        raise ClientScopeError("capture projection search identity is not uniquely scoped")
    generated = f"Capture evidence {row.subject_classification} {row.triage_state} {row.proposal_state}"
    return {
        "path": row.reference_path,
        "title": generated,
        "kind": "capture_evidence",
        "source": "capture_metadata",
        "source_root": "capture/runtime/derived/metadata",
        "client_scope": row.client_scope,
        "mtime": dt.datetime.fromisoformat(row.timestamp.replace("Z", "+00:00")).timestamp(),
        "tags": ",".join(filter(None, ("capture_metadata", row.triage_state, row.proposal_state))),
        "snippet": generated,
        "body": "",
        "indexed_at": utc_now(),
        "size_bytes": 0,
    }


def load_capture_metadata(root: Path = DEFAULT_RUNTIME_ROOT) -> list[CaptureMetadataProjection]:
    root = Path(root)
    if not root.exists():
        return []
    return CaptureStorage(root, repo_root=root.resolve().parents[1]).metadata_rows()
