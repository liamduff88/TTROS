"""Promotion authority tiers and an atomic, recoverable Business Brain writer.

The vault mutation, validation, receipt, and optional run-ledger linkage are one
recoverable transaction. A transient preimage journal lives under the existing
queue lock convention and is removed after success or verified rollback.

Revisit: when an automatic change class is enabled or promotion policy changes. · Last touched: 2026-07-15.
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

try:
    from aos_queue_storage import durable_replace_text
    from business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry
except ModuleNotFoundError:  # package import in unittest/IDE contexts
    from tools.aos_queue_storage import durable_replace_text
    from tools.business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry


TOKEN_USAGE_TEXT = "Token usage: no agent invocation"
AUTOMATIC_TIER = "deterministic_automatic"
REVIEW_TIER = "liam_review_required"
NEVER_TIER = "never_promote"
ENABLED_AUTOMATIC_RULES = {
    "generated_marker_section": {
        "targets": {"business_brain:index/MEMORY_INDEX.md"},
        "markers": {"block-2-outcome-index"},
    }
}
REVIEW_CHANGE_CLASSES = {
    "positioning", "pricing", "offers", "client_commitment", "communications_fact",
    "strategy", "legal_conclusion", "financial_conclusion", "architecture_change",
    "authority_change", "protected_boundary_change", "new_policy", "conflict",
    "deletion", "supersession",
}
NEVER_CHANGE_CLASSES = {
    "secrets", "credentials", "authentication_material", "raw_queue_state",
    "runtime_state", "pid_service_state", "transient_logs", "full_receipt_tree",
    "full_artifact_tree", "speculation_as_fact", "source_tree", "cloned_repository",
    "raw_graphify_output", "raw_communications", "protected_out_of_scope",
}


class PromotionError(RuntimeError):
    pass


@dataclass(frozen=True)
class PromotionCandidate:
    target: str
    client_scope: str
    change_class: str
    marker: str
    content: str
    target_preimage_sha256: str
    provenance_refs: tuple[str, ...]
    reason: str
    safe_for_broad_receipt: bool = False

    @property
    def write_id(self) -> str:
        material = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def evaluate_promotion(candidate: PromotionCandidate, *, registry: ClientScopeRegistry | None = None) -> dict[str, Any]:
    gate = registry or load_registry()
    try:
        canonical = gate.validate_brain_pointer(candidate.client_scope, candidate.target)
        for reference in candidate.provenance_refs:
            gate.validate_evidence_identity(candidate.client_scope, reference)
    except ClientScopeError as exc:
        return {"tier": NEVER_TIER, "writable": False, "refusal_reason": f"scope_rejection: {exc}", "candidate_diff": None}
    if candidate.change_class in NEVER_CHANGE_CLASSES:
        return {"tier": NEVER_TIER, "writable": False, "refusal_reason": f"never_promote:{candidate.change_class}", "candidate_diff": None}
    if candidate.change_class in ENABLED_AUTOMATIC_RULES:
        rule = ENABLED_AUTOMATIC_RULES[candidate.change_class]
        if canonical in rule["targets"] and candidate.marker in rule["markers"]:
            return {"tier": AUTOMATIC_TIER, "writable": True, "reason": "exact allowlisted target and machine marker"}
        return {"tier": REVIEW_TIER, "writable": False, "reason_for_review_tier": "automatic rule target or marker mismatch"}
    if candidate.change_class in REVIEW_CHANGE_CLASSES:
        return {"tier": REVIEW_TIER, "writable": False, "reason_for_review_tier": f"always_review:{candidate.change_class}"}
    return {"tier": REVIEW_TIER, "writable": False, "reason_for_review_tier": "unclassifiable candidates fail closed to review"}


def _markers(marker: str) -> tuple[str, str]:
    if not marker or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in marker):
        raise PromotionError("machine marker must be a lowercase stable slug")
    return f"<!-- TTROS:MACHINE:{marker}:BEGIN -->", f"<!-- TTROS:MACHINE:{marker}:END -->"


def render_marker_update(preimage: str, candidate: PromotionCandidate) -> tuple[str, str, str]:
    begin, end = _markers(candidate.marker)
    if begin in candidate.content or end in candidate.content:
        raise PromotionError("candidate content may not contain machine marker delimiters")
    begin_count, end_count = preimage.count(begin), preimage.count(end)
    body = candidate.content.rstrip("\n")
    replacement = f"{begin}\n{body}\n{end}"
    if begin_count == end_count == 0:
        separator = "" if not preimage or preimage.endswith("\n") else "\n"
        return preimage + separator + replacement + "\n", preimage, ""
    if begin_count != 1 or end_count != 1 or preimage.index(begin) > preimage.index(end):
        raise PromotionError("machine marker boundary is missing, duplicated, or malformed")
    prefix, remainder = preimage.split(begin, 1)
    _old_body, suffix = remainder.split(end, 1)
    return prefix + replacement + suffix, prefix, suffix


def candidate_diff(preimage: str, postimage: str, *, target: str) -> str:
    return "".join(difflib.unified_diff(
        preimage.splitlines(keepends=True),
        postimage.splitlines(keepends=True),
        fromfile=f"a/{target}",
        tofile=f"b/{target}",
    ))


def review_proposal(candidate: PromotionCandidate, *, preimage: str, registry: ClientScopeRegistry | None = None) -> dict[str, Any]:
    evaluation = evaluate_promotion(candidate, registry=registry)
    if evaluation["tier"] != REVIEW_TIER:
        raise PromotionError("review proposal requires the Liam-review tier")
    postimage, _prefix, _suffix = render_marker_update(preimage, candidate)
    return {
        "canonical_target": candidate.target,
        "target_preimage_hash": candidate.target_preimage_sha256,
        "candidate_diff": candidate_diff(preimage, postimage, target=candidate.target),
        "source_provenance_references": list(candidate.provenance_refs),
        "client_scope": candidate.client_scope,
        "reason_for_review_tier": evaluation["reason_for_review_tier"],
        "write_id": candidate.write_id,
    }


class PromotionWriter:
    def __init__(
        self,
        *,
        repo_root: Path,
        vault_root: Path,
        registry: ClientScopeRegistry | None = None,
        vault_replace: Callable[[Path, str], None] | None = None,
        receipt_replace: Callable[[Path, str], None] = durable_replace_text,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.vault_root = Path(vault_root).resolve()
        self.registry = registry or load_registry()
        self.vault_replace = vault_replace or self._atomic_vault_replace
        self.receipt_replace = receipt_replace
        self.receipts = self.repo_root / "queue" / "receipts"
        self.locks = self.repo_root / "queue" / "locks"

    @staticmethod
    def _atomic_vault_replace(path: Path, text: str) -> None:
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            try:
                directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                # DrvFS may not support directory fsync; same-directory os.replace
                # and the fully-fsynced file still provide the atomic boundary.
                pass
        finally:
            temporary.unlink(missing_ok=True)

    def _receipt_path(self, write_id: str) -> Path:
        return self.receipts / f"brain-promotion-{write_id}.json"

    def _diff_path(self, write_id: str) -> Path:
        return self.receipts / f"brain-promotion-{write_id}.patch"

    def _journal_path(self, write_id: str) -> Path:
        return self.locks / f".brain-promotion-{write_id}.preimage.json"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        self.receipt_replace(path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    def _failed_receipt(self, candidate: PromotionCandidate, *, error: str, rolled_back: bool, target_hash: str | None) -> dict[str, Any]:
        payload = {
            "status": "failed",
            "write_id": candidate.write_id,
            "target": candidate.target,
            "client_scope": candidate.client_scope,
            "change_class": candidate.change_class,
            "error": error,
            "rolled_back_to_exact_preimage": rolled_back,
            "verified_target_sha256": target_hash,
            "completed_at": _utc_now(),
            "token_usage_text": TOKEN_USAGE_TEXT,
        }
        self._write_json(self._receipt_path(candidate.write_id), payload)
        return payload

    def apply(
        self,
        candidate: PromotionCandidate,
        *,
        approval_reference: str | None = None,
        ledger_linker: Callable[[str], None] | None = None,
        failure_injection: str | None = None,
    ) -> dict[str, Any]:
        evaluation = evaluate_promotion(candidate, registry=self.registry)
        if evaluation["tier"] == NEVER_TIER:
            raise PromotionError(evaluation["refusal_reason"])
        if evaluation["tier"] == REVIEW_TIER and not approval_reference:
            raise PromotionError("review-tier promotion has no accepted human_review reference")
        existing_path = self._receipt_path(candidate.write_id)
        if existing_path.exists():
            try:
                existing = json.loads(existing_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {}
            if existing.get("status") == "success":
                return {**existing, "duplicate": True, "idempotent": True}
            if existing.get("status") == "failed":
                attempt_key = hashlib.sha256(json.dumps(existing, sort_keys=True).encode("utf-8")).hexdigest()[:12]
                archived = self.receipts / f"brain-promotion-{candidate.write_id}-failed-{attempt_key}.json"
                if not archived.exists():
                    self.receipt_replace(archived, json.dumps(existing, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
                existing_path.unlink()

        try:
            resolved = self.registry.resolve_brain_pointer(candidate.client_scope, candidate.target, root=self.vault_root)
        except ClientScopeError as exc:
            raise PromotionError(str(exc)) from exc
        target = resolved.resolved_path
        try:
            target.relative_to(self.vault_root)
        except ValueError as exc:
            raise PromotionError("promotion target is outside the canonical vault") from exc
        if any(part.lower() == "_backups" for part in target.relative_to(self.vault_root).parts):
            raise PromotionError("promotion target under _backups is prohibited")
        preimage = target.read_text(encoding="utf-8", errors="strict")
        preimage_hash = sha256_text(preimage)
        if preimage_hash != candidate.target_preimage_sha256:
            self._failed_receipt(candidate, error="stale target preimage hash", rolled_back=False, target_hash=preimage_hash)
            raise PromotionError("stale target preimage hash")
        postimage, prefix, suffix = render_marker_update(preimage, candidate)
        if not postimage.startswith(prefix) or not postimage.endswith(suffix):
            raise PromotionError("text outside the authorised machine marker changed")
        postimage_hash = sha256_text(postimage)
        operation = "noop" if postimage == preimage else "write"
        diff_text = candidate_diff(preimage, postimage, target=candidate.target)

        if operation == "noop":
            payload = {
                "status": "success", "operation": "noop", "write_id": candidate.write_id,
                "target": candidate.target, "client_scope": candidate.client_scope,
                "tier": evaluation["tier"], "change_class": candidate.change_class,
                "marker": candidate.marker, "preimage_sha256": preimage_hash,
                "postimage_sha256": postimage_hash, "provenance_refs": list(candidate.provenance_refs),
                "refresh_state": {"search": "not_required", "graphify": "not_required"},
                "completed_at": _utc_now(), "token_usage_text": TOKEN_USAGE_TEXT,
            }
            self._write_json(existing_path, payload)
            return {**payload, "idempotent": True}

        self.locks.mkdir(parents=True, exist_ok=True)
        journal = self._journal_path(candidate.write_id)
        self._write_json(journal, {
            "write_id": candidate.write_id,
            "target": str(target),
            "preimage": preimage,
            "preimage_sha256": preimage_hash,
            "postimage_sha256": postimage_hash,
        })
        os.chmod(journal, 0o600)
        mutated = False
        rolled_back = False
        try:
            if failure_injection == "before_mutation":
                raise PromotionError("injected failure before mutation")
            if failure_injection == "partial_write":
                self.vault_replace(target, postimage[: max(1, len(postimage) // 2)])
                mutated = True
                raise PromotionError("injected partial write failure")
            self.vault_replace(target, postimage)
            mutated = True
            if failure_injection == "post_write_validation":
                raise PromotionError("injected post-write validation failure")
            verified = target.read_text(encoding="utf-8", errors="strict")
            if verified != postimage or sha256_text(verified) != postimage_hash:
                raise PromotionError("post-write validation failed")
            if failure_injection == "provenance_write":
                raise PromotionError("injected provenance-write failure")
            diff_reference = None
            if candidate.safe_for_broad_receipt:
                self.receipt_replace(self._diff_path(candidate.write_id), diff_text)
                diff_reference = str(self._diff_path(candidate.write_id).relative_to(self.repo_root))
            payload = {
                "status": "success",
                "operation": "write",
                "write_id": candidate.write_id,
                "target": candidate.target,
                "client_scope": candidate.client_scope,
                "tier": evaluation["tier"],
                "change_class": candidate.change_class,
                "marker": candidate.marker,
                "preimage_sha256": preimage_hash,
                "postimage_sha256": postimage_hash,
                "diff_reference": diff_reference,
                "diff_sha256": hashlib.sha256(diff_text.encode("utf-8")).hexdigest(),
                "provenance_refs": list(candidate.provenance_refs),
                "approval_reference": approval_reference,
                "refresh_state": {"search": "pending", "graphify": "stale"},
                "completed_at": _utc_now(),
                "token_usage_text": TOKEN_USAGE_TEXT,
            }
            self._write_json(existing_path, payload)
            durable_reference = str(existing_path.relative_to(self.repo_root))
            if failure_injection == "run_ledger_linkage":
                raise PromotionError("injected run-ledger linkage failure")
            if ledger_linker is not None:
                ledger_linker(durable_reference)
            journal.unlink(missing_ok=True)
            return {**payload, "durable_reference": durable_reference, "idempotent": False}
        except Exception as exc:
            if mutated:
                self.vault_replace(target, preimage)
                restored = target.read_text(encoding="utf-8", errors="strict")
                rolled_back = restored == preimage and sha256_text(restored) == preimage_hash
                if not rolled_back:
                    raise PromotionError("promotion failed and exact preimage restoration could not be verified") from exc
            failure = self._failed_receipt(
                candidate,
                error=str(exc),
                rolled_back=rolled_back,
                target_hash=sha256_text(target.read_text(encoding="utf-8", errors="strict")),
            )
            journal.unlink(missing_ok=True)
            raise PromotionError(f"promotion transaction failed: {failure['error']}") from exc

    def mark_refresh_complete(self, durable_reference: str, *, search_reference: str, graphify_reference: str) -> dict[str, Any]:
        path = (self.repo_root / durable_reference).resolve()
        try:
            path.relative_to(self.receipts.resolve())
        except ValueError as exc:
            raise PromotionError("promotion receipt reference escaped the receipt directory") from exc
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != "success":
            raise PromotionError("only a successful promotion receipt can be refreshed")
        payload["refresh_state"] = {
            "search": "current",
            "search_reference": search_reference,
            "graphify": "current",
            "graphify_reference": graphify_reference,
        }
        payload["refresh_completed_at"] = _utc_now()
        self._write_json(path, payload)
        return payload
