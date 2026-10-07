"""Deterministic TTROS Memory Exchange directory-v1 importer.

Revisit: when the frozen Memory Ingest manifest contract changes. · Last touched: 2026-10-07.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.business_brain import BUSINESS_BRAIN_ROOT

TOKEN_USAGE = "Token usage: no agent invocation."
SHA = re.compile(r"[0-9a-f]{64}\Z")
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
# Package namespaces are deliberately mapped to fixed Brain roots.
TARGET_ROOTS = {"historical": "sources/historical_calls", "canonical": "memory"}
OPERATIONS = {"historical_record", "canonical_replace"}


class ImportFailure(ValueError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def relative(value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ImportFailure("unsafe path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")) or ":" in value:
        raise ImportFailure(f"unsafe path: {value}")
    return Path(*path.parts)


def required_dict(value: object, name: str) -> dict:
    if not isinstance(value, dict) or not value:
        raise ImportFailure(f"{name} must be a nonempty object")
    return value


def safe_file(root: Path, value: str) -> Path:
    path = root / relative(value)
    if any(part.is_symlink() for part in (path, *path.parents) if part != root and root in part.parents):
        raise ImportFailure(f"symlink path: {value}")
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ImportFailure(f"missing or escaping package file: {value}")
    return path


def _manifest(package: Path) -> tuple[dict, str]:
    if package.is_symlink() or not package.is_dir():
        raise ImportFailure("package directory is unsafe")
    raw = safe_file(package, "INGEST_MANIFEST.json").read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImportFailure("manifest is not valid JSON") from exc
    return required_dict(value, "manifest"), digest(raw)


def _target(brain: Path, output: dict, disposition: str, comparison: dict) -> tuple[Path, str]:
    operation = output.get("operation")
    if operation not in OPERATIONS:
        raise ImportFailure(f"unsupported operation: {operation}")
    target = required_dict(output.get("target"), "output.target")
    namespace = target.get("namespace")
    name = target.get("suggested_relative_path")
    if namespace not in TARGET_ROOTS or not isinstance(name, str):
        raise ImportFailure("unsupported target namespace or missing path")
    rel = relative(name)
    if rel.parts[0] == namespace:
        rel = Path(*rel.parts[1:])
    if not rel.parts or rel.suffix != ".md":
        raise ImportFailure("target must be a Markdown file beneath its namespace")
    if disposition == "evidence_only" and (operation != "historical_record" or namespace != "historical"):
        raise ImportFailure("evidence_only may write historical records only")
    if operation == "historical_record" and namespace != "historical":
        raise ImportFailure("historical_record requires historical namespace")
    if operation == "canonical_replace":
        if disposition != "canonical_changes" or namespace != "canonical":
            raise ImportFailure("canonical_replace requires canonical_changes disposition")
        if comparison.get("status") != "complete":
            raise ImportFailure("canonical replacement requires complete comparison")
        if not isinstance(target.get("canonical_ref"), str) or not target["canonical_ref"].startswith("business_brain:memory/"):
            raise ImportFailure("canonical replacement requires canonical_ref")
        if not SHA.fullmatch(str(target.get("expected_base_sha256"))):
            raise ImportFailure("canonical replacement requires expected_base_sha256")
        if rel.name == "north_shore_sales_coach.md":
            raise ImportFailure("protected canonical target")
    destination = brain / TARGET_ROOTS[namespace] / rel
    if not destination.resolve().is_relative_to(brain.resolve()) or any(p.is_symlink() for p in (destination, *destination.parents) if p != brain and brain in p.parents):
        raise ImportFailure("target escapes Business Brain")
    pointer = "business_brain:" + destination.relative_to(brain).as_posix()
    if operation == "canonical_replace" and target["canonical_ref"] != pointer:
        raise ImportFailure("canonical_ref does not match target")
    return destination, pointer


def validate(package: Path, brain: Path) -> dict:
    manifest, fingerprint = _manifest(package)
    for key, expected in (("schema_version", "2.0"), ("semantic_contract_version", "2.0.0"),
                          ("reconciliation_contract_version", "2.0.0"), ("transport_mode", "directory-v1"),
                          ("status", "ready_for_ttros")):
        if manifest.get(key) != expected:
            raise ImportFailure(f"unsupported {key}: {manifest.get(key)}")
    for key in ("package_id", "batch_id"):
        if not isinstance(manifest.get(key), str) or not IDENT.fullmatch(manifest[key]):
            raise ImportFailure(f"invalid {key}")
    batch_hash = manifest.get("batch_fingerprint_sha256")
    if not isinstance(batch_hash, str) or not SHA.fullmatch(batch_hash):
        raise ImportFailure("invalid batch_fingerprint_sha256")
    disposition = manifest.get("package_disposition")
    if disposition not in {"evidence_only", "canonical_changes"}:
        raise ImportFailure("unsupported package_disposition")
    sources = manifest.get("sources")
    if (not isinstance(sources, list) or not sources or type(manifest.get("source_count")) is not int
            or manifest["source_count"] != len(sources)):
        raise ImportFailure("source_count must match a nonempty sources list")
    source_ids = set()
    for source in sources:
        row = required_dict(source, "source")
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not IDENT.fullmatch(source_id) or source_id in source_ids:
            raise ImportFailure("invalid or duplicate source_id")
        source_ids.add(source_id)
    comparison = required_dict(manifest.get("canonical_comparison"), "canonical_comparison")
    if comparison.get("status") not in {"partial", "complete", "none"}:
        raise ImportFailure("invalid canonical_comparison.status")
    for flag in ("has_conflicts", "requires_human_review"):
        if not isinstance(manifest.get(flag), bool):
            raise ImportFailure(f"missing boolean {flag}")
    if manifest["has_conflicts"] or manifest["requires_human_review"]:
        raise ImportFailure("package has conflicts or requires review")
    files = manifest.get("package_files")
    outputs = manifest.get("outputs")
    if not isinstance(files, list) or not files or not isinstance(outputs, list) or not outputs:
        raise ImportFailure("package_files and outputs must be nonempty lists")
    if type(manifest.get("output_count")) is not int or manifest["output_count"] != len(outputs):
        raise ImportFailure("output_count does not match outputs")
    file_map = {}
    for item in files:
        row = required_dict(item, "package file")
        name, size, sha = row.get("path"), row.get("size_bytes"), row.get("sha256")
        if not isinstance(name, str) or not isinstance(size, int) or isinstance(size, bool) or size < 0 or not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise ImportFailure("invalid package file metadata")
        relative(name)
        if name in file_map:
            raise ImportFailure("duplicate package file")
        raw = safe_file(package, name).read_bytes()
        if len(raw) != size:
            raise ImportFailure(f"byte size mismatch: {name}")
        if digest(raw) != sha:
            raise ImportFailure(f"SHA-256 mismatch: {name}")
        file_map[name] = raw
    # All regular files other than the manifest must be declared; no hidden payloads.
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != set(file_map) | {"INGEST_MANIFEST.json"}:
        raise ImportFailure("unexpected or undeclared package file")
    planned = []
    seen_targets = set()
    for item in outputs:
        row = required_dict(item, "output")
        source = row.get("package_path")
        sha = row.get("sha256")
        size = row.get("size_bytes")
        if source not in file_map or sha != digest(file_map[source]) or size != len(file_map[source]):
            raise ImportFailure("output file is not correctly declared")
        if not isinstance(row.get("source_ids"), list) or not row["source_ids"] or any(
            source_id not in source_ids for source_id in row["source_ids"]
        ):
            raise ImportFailure("output references unknown sources")
        if row.get("requires_human_review") is not False or row.get("conflict_ids") != []:
            raise ImportFailure("output has conflicts or requires review")
        if row.get("temporal_posture") not in {"historical", "current"}:
            raise ImportFailure("invalid temporal_posture")
        if disposition == "evidence_only" and row["temporal_posture"] != "historical":
            raise ImportFailure("evidence_only requires historical temporal_posture")
        if row.get("operation") == "historical_record" and row["temporal_posture"] != "historical":
            raise ImportFailure("historical_record requires historical temporal_posture")
        if row.get("operation") == "canonical_replace" and row["temporal_posture"] != "current":
            raise ImportFailure("canonical_replace requires current temporal_posture")
        destination, pointer = _target(brain, row, disposition, comparison)
        if row["target"]["suggested_relative_path"] != source:
            raise ImportFailure("output target path differs from package_path")
        if destination in seen_targets:
            raise ImportFailure("duplicate output target")
        seen_targets.add(destination)
        planned.append({"source": source, "target": str(destination), "pointer": pointer,
                        "sha256": sha, "operation": row["operation"], "expected_base_sha256": row["target"].get("expected_base_sha256")})
    return {"manifest": manifest, "fingerprint": fingerprint, "outputs": planned, "bytes": file_map}


@contextmanager
def locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def ledger_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except json.JSONDecodeError as exc:
        raise ImportFailure("import ledger is malformed") from exc


def append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def process_checkpoint_package(package: Path, *, brain: Path, dry_run: bool = False) -> dict:
    """Route a typed Drive checkpoint to the same function as HTTP and stdio."""
    from tools import shared_brain_checkpoint

    if not dry_run and os.environ.get("TTROS_SHARED_BRAIN_WRITE", "").strip().lower() not in {"1", "true", "yes"}:
        return {"outcome": "disabled", "operation": "checkpoint",
                "reason": "Shared Brain checkpoint writes are disabled"}

    source = package / "CHECKPOINT.json"
    try:
        if package.is_symlink() or not package.is_dir() or source.is_symlink():
            raise ImportFailure("unsafe checkpoint package")
        if {p.name for p in package.iterdir()} != {"CHECKPOINT.json"} or not source.is_file():
            raise ImportFailure("checkpoint package must contain only CHECKPOINT.json")
        raw = source.read_bytes()
        if len(raw) > 8_000:
            raise ImportFailure("checkpoint package exceeds 8000 bytes")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != "shared-brain-checkpoint-v1" or payload.get("operation") != "checkpoint":
            raise ImportFailure("invalid checkpoint package schema")
        if set(payload) - {"schema_version", "operation", "workstream_id", "fields", "expected_version", "actor", "identity", "surface", "authenticated_identity", "actor_class", "surface_source"}:
            raise ImportFailure("unknown checkpoint package field")
        result = shared_brain_checkpoint.checkpoint(
            payload.get("workstream_id"), payload.get("fields"), payload.get("expected_version"),
            attribution={"authenticated_identity": "liam-drive-channel", "surface": "chatgpt",
                         "actor_class": "authorised_client", "surface_source": "address"}, root=brain,
            validate_only=dry_run,
        )
        if not result["success"]:
            return {"outcome": "rejected", "operation": "checkpoint", "reason": result["error"],
                    "current": result.get("current")}
        if dry_run:
            return {"outcome": "validated", "operation": "checkpoint", "workstream_id": payload["workstream_id"]}
        return {"outcome": "imported", "operation": "checkpoint", "note": result["note"],
                "drive_projection": result["drive_projection"]}
    except ImportFailure as exc:
        return {"outcome": "rejected", "operation": "checkpoint", "reason": str(exc)}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"outcome": "rejected", "operation": "checkpoint", "reason": "checkpoint package unavailable or malformed"}


def process_submit_package(package: Path, *, brain: Path, dry_run: bool = False) -> dict:
    """A typed Drive submit uses exactly the remote submit implementation."""
    from tools import shared_brain_submit
    if os.environ.get("TTROS_SHARED_BRAIN_SUBMIT", "").strip().lower() not in {"1", "true", "yes"}:
        return {"outcome": "disabled", "operation": "submit", "reason": "Shared Brain submit is disabled"}
    source = package / "SUBMIT.json"
    try:
        if package.is_symlink() or not package.is_dir() or source.is_symlink():
            raise ImportFailure("unsafe submit package")
        if {p.name for p in package.iterdir()} != {"SUBMIT.json"} or not source.is_file():
            raise ImportFailure("submit package must contain only SUBMIT.json")
        raw = source.read_bytes()
        if len(raw) > 32_000:
            raise ImportFailure("submit package exceeds 32000 bytes")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != "shared-brain-submit-v1" or payload.get("operation") != "submit":
            raise ImportFailure("invalid submit package schema")
        allowed = {"schema_version", "operation", "type", "title", "body", "source_refs", "workstream_id", "idempotency_key"}
        if set(payload) - allowed:
            raise ImportFailure("unknown submit package field")
        arguments = {key: payload.get(key) for key in ("type", "title", "body", "source_refs", "idempotency_key", "workstream_id")}
        error = shared_brain_submit._validate(**arguments)
        if error:
            raise ImportFailure(error)
        if dry_run:
            return {"outcome": "validated", "operation": "submit"}
        result = shared_brain_submit.submit(**arguments, attribution={
            "authenticated_identity": "liam-drive-channel", "surface": "chatgpt",
            "actor_class": "authorised_client", "surface_source": "address"})
        return {"outcome": "imported" if result["success"] else "rejected", "operation": "submit", **result}
    except (ImportFailure, OSError, UnicodeError, ValueError, TypeError) as exc:
        return {"outcome": "rejected", "operation": "submit", "reason": str(exc)}


def _refresh(paths: list[str], brain: Path, root: Path) -> tuple[dict, dict]:
    from tools import aos_indexer
    from tools.business_brain_scope import load_registry
    from dashboard.backend.business_brain_graph import BusinessBrainGraphService
    registry = load_registry(root / "context/client_scope_registry.json")
    indexed = [aos_indexer.index_one(str(brain / pointer.removeprefix("business_brain:")),
                                    db_path=root / "search/os_index.db", registry=registry)
               for pointer in paths]
    search = {"status": "success" if all(row.get("status") == "success" for row in indexed) else "failed",
              "indexed": len([row for row in indexed if row.get("status") == "success"]),
              "results": indexed}
    if search["status"] != "success":
        return search, {"status": "pending", "reason": "search refresh failed"}
    graph = BusinessBrainGraphService(vault_root=brain, registry=registry)
    allowed, prefixes = graph._published_target_allowlist()
    missing = [pointer for pointer in paths
               if not (pointer in allowed or any(pointer.startswith(prefix) for prefix in prefixes))]
    if missing:
        return search, {"status": "pending", "reason": "imported notes missing Graphify scope", "missing": missing}
    try:
        result = graph.build()
        if result.get("status") != "success":
            return search, {"status": "pending", "reason": "Graphify build did not succeed"}
        manifest = json.loads((graph.published / "source_manifest.json").read_text(encoding="utf-8"))
        projection = json.loads((graph.published / "graph.json").read_text(encoding="utf-8"))
        files = {row["source_path"]: row for row in manifest["files"]}
        nodes = {row["source_path"]: row for row in projection["nodes"] if row.get("kind") == "note"}
        covered = []
        for pointer in paths:
            raw = (brain / pointer.removeprefix("business_brain:")).read_bytes()
            expected = digest(raw)
            if files.get(pointer, {}).get("sha256") != expected or nodes.get(pointer, {}).get("content_sha256") != expected:
                return search, {"status": "pending", "reason": "Graphify source/node coverage mismatch", "missing": [pointer]}
            covered.append({"pointer": pointer, "sha256": expected, "node_id": nodes[pointer]["id"]})
        return search, {"status": "success", "receipt_path": result.get("receipt_path"),
                        "source_manifest_sha256": digest((graph.published / "source_manifest.json").read_bytes()),
                        "coverage": covered}
    except Exception as exc:
        return search, {"status": "pending", "reason": str(exc)}


def process(package: Path, *, brain: Path = BUSINESS_BRAIN_ROOT, root: Path = ROOT,
            dry_run: bool = False, refresh=None) -> dict:
    if (package / "CHECKPOINT.json").exists():
        return process_checkpoint_package(package, brain=brain, dry_run=dry_run)
    if (package / "SUBMIT.json").exists():
        return process_submit_package(package, brain=brain, dry_run=dry_run)
    ledger = root / "queue/receipts/memory_exchange_import.jsonl"
    with locked(root / "queue/locks/memory_exchange_import.lock") if not dry_run else _null_context():
        try:
            plan = validate(package, brain)
            manifest, fingerprint, outputs = plan["manifest"], plan["fingerprint"], plan["outputs"]
            rows = ledger_rows(ledger)
            prior = [row for row in rows if row.get("package_id") == manifest["package_id"] and row.get("outcome") != "rejected"]
            if any(row.get("fingerprint") != fingerprint for row in prior):
                raise ImportFailure("package ID collision with different fingerprint")
            same_batch = [row for row in rows if row.get("batch_fingerprint_sha256") == manifest["batch_fingerprint_sha256"] and row.get("package_id") != manifest["package_id"] and row.get("outcome") in {"in_progress", "committed", "imported", "refresh_pending"}]
            if same_batch:
                raise ImportFailure("batch fingerprint already imported under another package ID")
            previous = prior[-1] if prior else None
            # The Brain transaction stamps provenance, so a written note differs from its package
            # bytes; reruns compare against the hash the importer recorded after writing.
            written = {}
            for row in prior:
                for item in row.get("outputs") or []:
                    if row.get("fingerprint") == fingerprint and item.get("written_sha256"):
                        written[item.get("pointer")] = item["written_sha256"]
            for output in outputs:
                target = Path(output["target"])
                if target.is_symlink() or not target.resolve().is_relative_to(brain.resolve()):
                    raise ImportFailure("unsafe target path")
                if target.exists():
                    current = digest(target.read_bytes())
                    if current == output["sha256"]:
                        output["action"] = "already_present"
                    elif previous and previous.get("fingerprint") == fingerprint and previous.get("outcome") in {"committed", "imported", "refresh_pending", "already_imported"}:
                        # Rows written before written_sha256 existed keep their original trust.
                        if written.get(output["pointer"], current) != current:
                            raise ImportFailure(f"previously imported target changed: {output['pointer']}")
                        output["action"] = "already_present"
                    elif output["operation"] == "canonical_replace" and current == output["expected_base_sha256"]:
                        output["action"] = "replace"
                    else:
                        raise ImportFailure(f"target collision or base hash mismatch: {output['pointer']}")
                else:
                    if output["operation"] == "canonical_replace":
                        raise ImportFailure("canonical replacement target is missing")
                    output["action"] = "write"
            if (previous and previous.get("outcome") in {"imported", "already_imported"}
                    and previous.get("search_refresh", {}).get("status") == "success"
                    and previous.get("graphify_refresh", {}).get("status") == "success"
                    and {row.get("pointer") for row in previous.get("graphify_refresh", {}).get("coverage", [])}
                        == {row["pointer"] for row in outputs}
                    and all(o["action"] == "already_present" for o in outputs)):
                outcome = "already_imported"
            else:
                outcome = "validated" if dry_run else "committed"
            receipt = {"package_id": manifest["package_id"], "batch_id": manifest["batch_id"],
                       "batch_fingerprint_sha256": manifest["batch_fingerprint_sha256"],
                       "package_disposition": manifest["package_disposition"], "fingerprint": fingerprint,
                       "outcome": outcome, "outputs": outputs, "validated": True,
                       "search_refresh": {"status": "not_run"}, "graphify_refresh": {"status": "not_run"},
                       "external_package_move": "pending", "token_usage": TOKEN_USAGE}
            receipt["sources"] = manifest["sources"]
            receipt["knowledge_types_present"] = manifest.get("knowledge_types_present", [])
            if outcome == "already_imported":
                # Preserve the successful refresh/closure evidence on an idempotent rerun.
                for key in ("search_refresh", "graphify_refresh", "commit", "sync_status"):
                    if key in previous:
                        receipt[key] = previous[key]
            if dry_run or outcome == "already_imported":
                return receipt
            if previous and all(o["action"] == "already_present" for o in outputs):
                for key in ("commit", "sync_status"):
                    if key in previous:
                        receipt[key] = previous[key]
            # Durable intent precedes target writes. A crash can be reconciled
            # from destination hashes without opening the batch to a new ID.
            append(ledger, {**receipt, "outcome": "in_progress", "timestamp": dt.datetime.now(dt.timezone.utc).isoformat()})
            staged = []
            from tools import brain_memory
            use_transaction = (brain / ".git").is_dir() and brain.resolve() == brain_memory.VAULT_ROOT
            if use_transaction:
                documents = {Path(o["target"]).relative_to(brain).as_posix():
                             plan["bytes"][o["source"]].decode("utf-8") for o in outputs if o["action"] != "already_present"}
                if documents:
                    write = brain_memory.write_transaction(
                        documents, source="memory-exchange-import", session_id=manifest["package_id"],
                        expected_hashes={relative: digest((brain / relative).read_bytes()) if (brain / relative).is_file() else None
                                         for relative in documents},
                        attribution={"authenticated_identity": "liam-drive-channel", "surface": "chatgpt",
                                     "actor_class": "authorised_client", "surface_source": "address"},
                    )
                    receipt["commit"] = write.commit
                    receipt["sync_status"] = write.sync_status
            else:
                try:
                    for output in outputs:
                        if output["action"] == "already_present":
                            continue
                        target = Path(output["target"])
                        target.parent.mkdir(parents=True, exist_ok=True)
                        fd, tmp = tempfile.mkstemp(prefix=".memory-exchange-", dir=target.parent)
                        staged.append((Path(tmp), target))
                        with os.fdopen(fd, "wb") as handle:
                            handle.write(plan["bytes"][output["source"]])
                            handle.flush()
                            os.fsync(handle.fileno())
                    # Recheck all targets after staging, before the first commit.
                    for output in outputs:
                        target = Path(output["target"])
                        current = digest(target.read_bytes()) if target.is_file() and not target.is_symlink() else None
                        allowed = (output["sha256"],) if output["action"] == "already_present" else (
                            (output["expected_base_sha256"],) if output["action"] == "replace" else (None,))
                        if current not in allowed:
                            raise ImportFailure(f"target changed during staging: {output['pointer']}")
                    for tmp, target in staged:
                        os.replace(tmp, target)
                finally:
                    for tmp, _ in staged:
                        tmp.unlink(missing_ok=True)
            for output in outputs:
                output["written_sha256"] = digest(Path(output["target"]).read_bytes())
            receipt["timestamp"] = dt.datetime.now(dt.timezone.utc).isoformat()
            append(ledger, receipt)
            fn = refresh or (lambda pointers: _refresh(pointers, brain, root))
            try:
                search, graph = fn([o["pointer"] for o in outputs])
            except Exception as exc:
                search, graph = {"status": "pending", "reason": str(exc)}, {"status": "pending"}
            receipt["search_refresh"], receipt["graphify_refresh"] = search, graph
            receipt["outcome"] = "imported" if search.get("status") == "success" and graph.get("status") in {"success", "not_applicable"} else "refresh_pending"
            append(ledger, receipt)
            return receipt
        except ImportFailure as exc:
            receipt = {"outcome": "rejected", "reason": str(exc), "package": package.name,
                       "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(), "token_usage": TOKEN_USAGE}
            if "plan" in locals():
                receipt.update({"package_id": plan["manifest"]["package_id"],
                                "batch_id": plan["manifest"]["batch_id"],
                                "batch_fingerprint_sha256": plan["manifest"]["batch_fingerprint_sha256"],
                                "package_disposition": plan["manifest"]["package_disposition"],
                                "fingerprint": plan["fingerprint"], "outputs": plan["outputs"]})
            if not dry_run:
                append(ledger, receipt)
            return receipt


@contextmanager
def _null_context():
    yield


def list_ready(ready: Path) -> list[Path]:
    if not ready.is_dir():
        return []
    return sorted(p for p in ready.iterdir() if p.is_dir() and not p.is_symlink()
                  and ((p / "INGEST_MANIFEST.json").is_file() or (p / "CHECKPOINT.json").is_file() or (p / "SUBMIT.json").is_file()))


class DirectoryTransport:
    """A materialized Drive folder adapter; never used by dry-run."""

    def __init__(self, ready: Path, imported: Path | None = None, rejected: Path | None = None,
                 source: Path | None = None):
        self.source, self.ready, self.imported, self.rejected = source, ready, imported, rejected

    def list_ready_packages(self) -> list[Path]:
        return list_ready(self.ready)

    def materialize(self, package: Path) -> Path:
        if package.parent != self.ready or package not in self.list_ready_packages():
            raise ImportFailure("package is not immediately beneath ready folder")
        return package

    def mark_success(self, package: Path) -> Path:
        return self._move(package, self.imported)

    def mark_rejected(self, package: Path) -> Path:
        return self._move(package, self.rejected)

    def _move(self, package: Path, destination: Path | None) -> Path:
        if destination is None:
            raise ImportFailure("destination is not configured")
        self.materialize(package)
        target = destination / package.name
        if target.exists():
            raise ImportFailure("destination package already exists")
        destination.mkdir(parents=True, exist_ok=True)
        shutil.move(str(package), str(target))
        return target


def _publish_import_receipt(destination: Path, package_name: str, result: dict) -> Path:
    """Projection of existing importer ledger beside, never inside, hashed packets."""
    if not IDENT.fullmatch(package_name) or destination.is_symlink() or not destination.is_dir():
        raise ImportFailure("unsafe receipt destination")
    path = destination / (package_name + ".IMPORT_RECEIPT.json")
    if path.is_symlink():
        raise ImportFailure("unsafe receipt path")
    payload = {**result, "receipt_projection_version": "memory-exchange-import-receipt-v1",
               "issuer": "tools/memory_exchange_import.py"}
    payload.pop("receipt_publication", None)
    raw = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    # The timer republishes every pass; an unchanged receipt is not rewritten on Drive.
    if path.is_file() and path.read_bytes() == raw:
        return path
    fd, temporary = tempfile.mkstemp(prefix=".import-receipt-", dir=destination)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


def _republish_import_receipts(imported: Path | None, root: Path) -> None:
    """Repair receipt transport after a move without rerunning semantic/import work."""
    if imported is None or not imported.is_dir() or imported.is_symlink():
        return
    # Best effort: a damaged imported folder must never block typed packages on this pass.
    try:
        rows = ledger_rows(root / "queue/receipts/memory_exchange_import.jsonl")
        packages = sorted(imported.iterdir())
    except (ImportFailure, OSError):
        return
    for package in packages:
        try:
            if package.is_symlink() or not package.is_dir() or not (package / "INGEST_MANIFEST.json").is_file():
                continue
            manifest, fingerprint = _manifest(package)
            matches = [row for row in rows if row.get("package_id") == manifest.get("package_id")
                       and row.get("fingerprint") == fingerprint
                       and row.get("outcome") in {"imported", "already_imported"}]
            if not matches:
                continue
            result = {**matches[-1], "sources": manifest.get("sources", []),
                      "external_package_move": "completed: " + str(package)}
            _publish_import_receipt(imported, package.name, result)
        except (ImportFailure, OSError, ValueError):
            continue


def main() -> int:
    parser = argparse.ArgumentParser(description="TTROS deterministic Memory Exchange importer")
    parser.add_argument("--ready", type=Path, default=Path(os.environ["TTROS_MEMORY_READY"]) if os.environ.get("TTROS_MEMORY_READY") else None,
                        help="materialized 03_READY_FOR_TTROS directory")
    parser.add_argument("--package", type=Path, help="one materialized package directory")
    parser.add_argument("--brain", type=Path, default=BUSINESS_BRAIN_ROOT)
    parser.add_argument("--source", type=Path, help="optional source folder for transport configuration")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--imported", type=Path, help="configured 04_IMPORTED directory")
    parser.add_argument("--rejected", type=Path, help="configured rejection directory")
    parser.add_argument("--move", action="store_true", help="move completed packages; operator authorization required")
    parser.add_argument("--checkpoint-only", action="store_true", help="process only CHECKPOINT.json packages")
    parser.add_argument("--typed-only", action="store_true",
                        help="process only typed Shared Brain CHECKPOINT.json and SUBMIT.json packages")
    args = parser.parse_args()
    if not (args.ready or args.package):
        parser.error("provide --ready or --package")
    if args.move and not args.ready:
        parser.error("--move requires --ready")
    transport = DirectoryTransport(args.ready, args.imported, args.rejected, args.source) if args.ready else None
    if args.package and transport:
        packages = [transport.materialize(args.package)]
    else:
        packages = [args.package] if args.package else transport.list_ready_packages()
    if args.checkpoint_only:
        packages = [package for package in packages if (package / "CHECKPOINT.json").is_file()]
    if args.typed_only:
        packages = [package for package in packages
                    if (package / "CHECKPOINT.json").is_file() or (package / "SUBMIT.json").is_file()]
    if args.move and not args.dry_run:
        _republish_import_receipts(args.imported, args.root)
    results = []
    for package in packages:
        result = process(package, brain=args.brain, root=args.root, dry_run=args.dry_run)
        if result["outcome"] == "disabled":
            results.append(result)
            continue
        if args.move and not args.dry_run and transport:
            try:
                if result["outcome"] in {"imported", "already_imported"} and args.imported:
                    result["external_package_move"] = "completed: " + str(transport.mark_success(package))
                elif result["outcome"] == "rejected" and args.rejected:
                    result["external_package_move"] = "completed: " + str(transport.mark_rejected(package))
            except (ImportFailure, OSError) as exc:
                result["external_package_move"] = "pending: " + str(exc)
            if result.get("external_package_move", "") != "pending":
                with locked(args.root / "queue/locks/memory_exchange_import.lock"):
                    append(args.root / "queue/receipts/memory_exchange_import.jsonl", result)
            # Typed packages retain their existing route/semantics. Full manifests gain readback receipts.
            if "operation" not in result and str(result.get("external_package_move", "")).startswith("completed:"):
                destination = args.imported if result["outcome"] in {"imported", "already_imported"} else args.rejected
                try:
                    path = _publish_import_receipt(destination, package.name, result)
                    result["receipt_publication"] = "completed: " + str(path)
                except (ImportFailure, OSError) as exc:
                    result["receipt_publication"] = "pending: " + str(exc)
                    with locked(args.root / "queue/locks/memory_exchange_import.lock"):
                        append(args.root / "queue/receipts/memory_exchange_import.jsonl", result)
        results.append(result)
    print(json.dumps(results, indent=2))
    print(TOKEN_USAGE)
    return 1 if any(r["outcome"] in {"rejected", "refresh_pending", "disabled"} or
                    str(r.get("external_package_move", "")).startswith("pending:") or
                    str(r.get("receipt_publication", "")).startswith("pending:") for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
