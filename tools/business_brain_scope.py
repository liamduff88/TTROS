"""Schema-backed, default-deny client scope enforcement for Business Brain reads.

All content-bearing callers validate a declared scope and exact source identity
here before opening a note, executing search SQL, loading evidence, or returning
a Graphify target.

Revisit: when a verified client identity or retrieval boundary is added. · Last touched: 2026-07-15.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

try:
    import business_brain
except ModuleNotFoundError:  # package import in unittest/IDE contexts
    from tools import business_brain


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "context" / "client_scope_registry.json"
DEFAULT_SCHEMA_PATH = REPO_ROOT / "context" / "client_scope_registry.schema.json"


class ClientScopeError(PermissionError):
    """A request lacks one exact, enabled scope or requests an unowned source."""


@dataclass(frozen=True)
class ScopeIdentity:
    scope_id: str
    kind: str


@dataclass(frozen=True)
class CaptureIdentityResolution:
    state: str
    client_scope: str | None = None
    scope_kind: str | None = None
    matched_by: tuple[str, ...] = ()


class ClientScopeRegistry:
    def __init__(
        self,
        *,
        registry_path: Path = DEFAULT_REGISTRY_PATH,
        schema_path: Path = DEFAULT_SCHEMA_PATH,
        data: dict[str, Any] | None = None,
    ):
        self.registry_path = Path(registry_path)
        self.schema_path = Path(schema_path)
        try:
            self.data = data if data is not None else json.loads(self.registry_path.read_text(encoding="utf-8"))
            schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
            jsonschema.validate(self.data, schema)
        except (OSError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
            raise ClientScopeError(f"client scope registry is unavailable or invalid: {exc}") from exc
        if self.data.get("default_deny") is not True:
            raise ClientScopeError("client scope registry must be default-deny")

    def resolve_scope(self, client_scope: str | None) -> ScopeIdentity:
        raw = "" if client_scope is None else str(client_scope)
        if not raw or raw != raw.strip():
            raise ClientScopeError("client_scope is required and must be exact")
        record = self.data["scopes"].get(raw)
        if not isinstance(record, dict):
            raise ClientScopeError(f"unresolved client_scope: {raw}")
        if record.get("enabled") is not True:
            raise ClientScopeError(f"client_scope is disabled: {raw}")
        return ScopeIdentity(scope_id=raw, kind=str(record["kind"]))

    def _scope_record(self, client_scope: str | None) -> tuple[ScopeIdentity, dict[str, Any]]:
        identity = self.resolve_scope(client_scope)
        return identity, self.data["scopes"][identity.scope_id]

    @staticmethod
    def canonical_pointer(pointer: str) -> str:
        return business_brain.resolve_business_brain_pointer(pointer, require_exists=False).pointer

    def validate_brain_pointer(self, client_scope: str | None, pointer: str) -> str:
        identity, record = self._scope_record(client_scope)
        try:
            canonical = self.canonical_pointer(pointer)
        except business_brain.BusinessBrainPointerError as exc:
            raise ClientScopeError(str(exc)) from exc
        if canonical in set(self.data.get("denied_brain_pointers") or []):
            raise ClientScopeError(f"Business Brain pointer is explicitly unavailable: {canonical}")
        if canonical not in set(record.get("brain_pointers") or []):
            raise ClientScopeError(f"Business Brain pointer does not belong to {identity.scope_id}: {canonical}")
        return canonical

    def resolve_brain_pointer(
        self,
        client_scope: str | None,
        pointer: str,
        *,
        root: Path | None = None,
    ) -> business_brain.ResolvedBusinessBrainPointer:
        canonical = self.validate_brain_pointer(client_scope, pointer)
        return business_brain.resolve_business_brain_pointer(canonical, root=root)

    def permitted_brain_pointers(self, client_scope: str | None) -> tuple[str, ...]:
        _identity, record = self._scope_record(client_scope)
        denied = set(self.data.get("denied_brain_pointers") or [])
        return tuple(pointer for pointer in record.get("brain_pointers") or [] if pointer not in denied)

    def validate_search_source(self, client_scope: str | None, source: str | None) -> ScopeIdentity:
        identity, record = self._scope_record(client_scope)
        raw = "" if source is None else str(source)
        if raw and raw not in {str(rule.get("source") or "") for rule in record.get("search_source_identities") or []}:
            raise ClientScopeError(f"search source does not belong to {identity.scope_id}: {raw}")
        return identity

    def scope_for_search_identity(self, source: str, path: str) -> str | None:
        if path in set(self.data.get("denied_brain_pointers") or []):
            return None
        matches = []
        for scope_id, record in self.data.get("scopes", {}).items():
            if record.get("enabled") is not True:
                continue
            for rule in record.get("search_source_identities") or []:
                if rule.get("source") != source:
                    continue
                if path in set(rule.get("paths") or []):
                    matches.append(scope_id)
                prefix = str(rule.get("path_prefix") or "")
                if prefix and path.startswith(prefix):
                    matches.append(scope_id)
        return matches[0] if len(set(matches)) == 1 else None

    def validate_graph_namespace(self, client_scope: str | None, namespace: str) -> ScopeIdentity:
        identity, record = self._scope_record(client_scope)
        if namespace not in {str(rule.get("namespace") or "") for rule in record.get("graphify_targets") or []}:
            raise ClientScopeError(f"Graphify namespace does not belong to {identity.scope_id}: {namespace}")
        return identity

    def validate_graph_target(self, client_scope: str | None, namespace: str, pointer: str) -> str:
        identity = self.validate_graph_namespace(client_scope, namespace)
        canonical = self.validate_brain_pointer(identity.scope_id, pointer)
        record = self.data["scopes"][identity.scope_id]
        allowed = set()
        for rule in record.get("graphify_targets") or []:
            if rule.get("namespace") == namespace:
                allowed.update(rule.get("paths") or [])
        if canonical not in allowed:
            raise ClientScopeError(f"Graphify target does not belong to {identity.scope_id}: {canonical}")
        return canonical

    def validate_evidence_identity(self, client_scope: str | None, evidence_identity: str) -> str:
        identity, record = self._scope_record(client_scope)
        raw = str(evidence_identity or "")
        if not raw or raw not in set(record.get("evidence_identities") or []):
            raise ClientScopeError(f"evidence identity does not belong to {identity.scope_id}: {raw or '(missing)'}")
        return raw

    @staticmethod
    def capture_identity_hash(value: str | None) -> str:
        normalized = str(value or "").strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""

    def resolve_capture_identity(
        self,
        *,
        sender: str | None = None,
        thread_id: str | None = None,
        sender_sha256: str | None = None,
        thread_sha256: str | None = None,
    ) -> CaptureIdentityResolution:
        """Resolve hashed capture metadata without opening message content."""
        values = {
            "sender": sender_sha256 or self.capture_identity_hash(sender),
            "thread": thread_sha256 or self.capture_identity_hash(thread_id),
        }
        matches_by_type: dict[str, set[str]] = {"sender": set(), "thread": set()}
        for scope_id, record in self.data.get("scopes", {}).items():
            if record.get("enabled") is not True:
                continue
            for identity in record.get("capture_identities") or []:
                match_type = str(identity.get("match_type") or "")
                if match_type in values and values[match_type] and identity.get("value_sha256") == values[match_type]:
                    matches_by_type[match_type].add(scope_id)
        if any(len(matches) > 1 for matches in matches_by_type.values()):
            return CaptureIdentityResolution(state="ambiguous")
        combined = set().union(*matches_by_type.values())
        if len(combined) > 1:
            return CaptureIdentityResolution(state="conflicting")
        if not combined:
            return CaptureIdentityResolution(state="unresolved")
        scope_id = next(iter(combined))
        identity = self.resolve_scope(scope_id)
        return CaptureIdentityResolution(
            state="matched",
            client_scope=scope_id,
            scope_kind=identity.kind,
            matched_by=tuple(sorted(key for key, matches in matches_by_type.items() if scope_id in matches)),
        )

    def validate_capture_evidence_reference(self, client_scope: str | None, reference: str) -> str:
        identity, record = self._scope_record(client_scope)
        raw = str(reference or "")
        prefixes = tuple(str(value) for value in record.get("capture_evidence_prefixes") or [])
        matching = tuple(prefix for prefix in prefixes if raw.startswith(prefix))
        if not raw or not matching:
            raise ClientScopeError(f"capture evidence does not belong to {identity.scope_id}")
        suffix = raw[len(max(matching, key=len)) :]
        if not suffix or not all(character.isalnum() or character in "-_" for character in suffix):
            raise ClientScopeError("capture evidence reference is malformed")
        return raw


def load_registry(path: Path | None = None) -> ClientScopeRegistry:
    return ClientScopeRegistry(registry_path=Path(path or DEFAULT_REGISTRY_PATH))
