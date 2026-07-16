"""Failure-preserving Graphify projection for the canonical Business Brain.

Graphify is a derived selector, never the authority. Published targets contain
canonical logical paths and scores only; note bodies are never returned.

Revisit: when Graphify's Markdown/manifest contracts change. · Last touched: 2026-07-15.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import business_brain
from business_brain_scope import ClientScopeError, ClientScopeRegistry, load_registry
from validate_business_brain import WIKI_LINK_RE, canonical_markdown, canonical_wiki_target, parse_frontmatter


TOKEN_USAGE_TEXT = "Token usage: no agent invocation"
DEFAULT_GRAPHIFY_ROOT = Path("/home/liam/graphify-brain")
DEFAULT_NAMESPACE = "ttros-business-brain"
DEFAULT_GRAPHIFY_PYTHON = Path("/home/liam/.local/share/pipx/venvs/graphifyy/bin/python")
WORD_RE = re.compile(r"[a-z0-9]+")


class BusinessBrainGraphError(RuntimeError):
    pass


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_env() -> dict[str, str]:
    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONNOUSERSITE": "1",
    }


class BusinessBrainGraphService:
    def __init__(
        self,
        *,
        graphify_root: Path = DEFAULT_GRAPHIFY_ROOT,
        vault_root: Path | None = None,
        namespace: str = DEFAULT_NAMESPACE,
        graphify_python: Path = DEFAULT_GRAPHIFY_PYTHON,
        extractor_script: Path | None = None,
        registry: ClientScopeRegistry | None = None,
    ):
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?", namespace):
            raise BusinessBrainGraphError("namespace must be a safe lowercase slug")
        self.graphify_root = Path(graphify_root).resolve()
        self.vault_root = Path(vault_root or business_brain.BUSINESS_BRAIN_ROOT).resolve()
        self.namespace = namespace
        self.document_root = self.graphify_root / "document_graphs"
        self.namespace_root = self.document_root / namespace
        self.published = self.namespace_root / "published"
        self.history = self.namespace_root / ".history"
        self.receipts = self.namespace_root / "receipts"
        self.graphify_python = Path(graphify_python)
        self.extractor_script = extractor_script or TOOLS_DIR / "aos_graphify_markdown_extract.py"
        self.registry = registry or load_registry()

    def _published_target_allowlist(self) -> set[str]:
        allowed = set()
        denied = set(self.registry.data.get("denied_brain_pointers") or [])
        for record in self.registry.data.get("scopes", {}).values():
            if record.get("enabled") is not True:
                continue
            for target in record.get("graphify_targets") or []:
                if target.get("namespace") == self.namespace:
                    allowed.update(target.get("paths") or [])
        return allowed - denied

    def _notes(self) -> list[Path]:
        allowed = self._published_target_allowlist()
        notes = [
            path for path in canonical_markdown(self.vault_root)
            if f"business_brain:{path.relative_to(self.vault_root).as_posix()}" in allowed
        ]
        if not notes:
            raise BusinessBrainGraphError("canonical Business Brain has no Markdown notes")
        return notes

    def source_manifest(self) -> dict[str, Any]:
        files = []
        ids = set()
        for path in self._notes():
            relative = path.relative_to(self.vault_root).as_posix()
            raw = path.read_bytes()
            fields, _body = parse_frontmatter(raw.decode("utf-8", errors="strict"))
            note_id = fields.get("id", "")
            if not note_id or note_id in ids:
                raise BusinessBrainGraphError(f"missing or duplicate canonical note id: {relative}")
            ids.add(note_id)
            files.append({
                "id": note_id,
                "relative_path": relative,
                "source_path": f"business_brain:{relative}",
                "sha256": _sha256_bytes(raw),
                "size_bytes": len(raw),
                "type": fields.get("type") or None,
                "status": fields.get("status") or None,
            })
        aggregate = _sha256_bytes(_json_bytes(files))
        return {
            "schema_version": 1,
            "source": "business_brain:README.md",
            "excludes": ["_backups/**"],
            "files": files,
            "aggregate_sha256": aggregate,
        }

    def _run_graphify_structural(self, mirror: Path, output: Path) -> dict[str, Any]:
        if not self.graphify_python.is_file():
            raise BusinessBrainGraphError("installed Graphify Python runtime is unavailable")
        argv = [str(self.graphify_python), str(self.extractor_script), "--root", str(mirror), "--output", str(output)]
        result = subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=120, check=False, env=_safe_env(), stdin=subprocess.DEVNULL)
        if result.returncode:
            raise BusinessBrainGraphError(f"Graphify structural Markdown extraction failed: {(result.stderr or result.stdout)[-3000:]}")
        try:
            raw = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BusinessBrainGraphError("Graphify structural output is missing or invalid") from exc
        if not isinstance(raw.get("nodes"), list) or not isinstance(raw.get("edges"), list):
            raise BusinessBrainGraphError("Graphify structural output lacks nodes/edges")
        return raw

    def _projection(self, source_manifest: dict[str, Any], raw_graph: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        file_records = {row["relative_path"]: row for row in source_manifest["files"]}
        note_nodes = []
        wiki_pairs = []
        heading_nodes = []
        structural_edges = []
        raw_file_ids = {}
        raw_reference_count = 0

        for node in raw_graph["nodes"]:
            relative = str(node.get("source_file") or "")
            if relative not in file_records:
                continue
            if str(node.get("source_location") or "") == "L1" and str(node.get("label") or "").lower().endswith(".md"):
                raw_file_ids[str(node.get("id"))] = file_records[relative]["id"]
                continue
            label = str(node.get("label") or "").strip()
            if not label:
                continue
            stable = f"{file_records[relative]['id']}#heading-{len([item for item in heading_nodes if item['relative_path'] == relative]) + 1}"
            heading_nodes.append({
                "id": stable,
                "kind": "heading",
                "label": label,
                "relative_path": relative,
                "source_path": file_records[relative]["source_path"],
                "source_location": node.get("source_location"),
                "graphify_original_id": node.get("id"),
            })
            structural_edges.append({
                "source": file_records[relative]["id"],
                "target": stable,
                "relation": "contains",
                "confidence": "EXTRACTED",
                "edge_kind": "structural",
                "extractor": "graphify.markdown",
            })

        id_for_path = {row["relative_path"]: row["id"] for row in source_manifest["files"]}
        for relative, record in file_records.items():
            path = self.vault_root / relative
            text = path.read_text(encoding="utf-8", errors="strict")
            fields, body = parse_frontmatter(text)
            title = next((line.lstrip("#").strip() for line in body.splitlines() if line.startswith("#")), path.stem)
            note_nodes.append({
                "id": record["id"],
                "kind": "note",
                "title": title,
                "relative_path": relative,
                "source_path": record["source_path"],
                "content_sha256": record["sha256"],
                "metadata": {key: value for key, value in fields.items() if key in {"id", "type", "status", "last_touched"}},
            })
            seen = set()
            for raw_target in WIKI_LINK_RE.findall(body):
                target = canonical_wiki_target(raw_target)
                if target in id_for_path and target not in seen:
                    seen.add(target)
                    wiki_pairs.append((relative, target))

        raw_reference_pairs = set()
        for edge in raw_graph["edges"]:
            if edge.get("relation") != "references":
                continue
            raw_reference_count += 1
            source_id = raw_file_ids.get(str(edge.get("source")))
            target_id = raw_file_ids.get(str(edge.get("target")))
            if source_id and target_id:
                raw_reference_pairs.add((source_id, target_id))

        explicit_edges = []
        for source_path, target_path in sorted(set(wiki_pairs)):
            source_id, target_id = id_for_path[source_path], id_for_path[target_path]
            explicit_edges.append({
                "source": source_id,
                "target": target_id,
                "relation": "wiki_link",
                "confidence": "EXTRACTED",
                "edge_kind": "explicit",
                "extractor": "graphify.markdown+ttros-obsidian-resolution",
                "package_edge_confirmed": (source_id, target_id) in raw_reference_pairs,
                "source_path": f"business_brain:{source_path}",
            })

        nodes = sorted(note_nodes + heading_nodes, key=lambda row: row["id"])
        edges = sorted(explicit_edges + structural_edges, key=lambda row: (row["source"], row["target"], row["relation"]))
        graph = {
            "schema_version": 1,
            "namespace": self.namespace,
            "source_manifest_sha256": _sha256_bytes(_json_bytes(source_manifest)),
            "directed": True,
            "nodes": nodes,
            "edges": edges,
        }
        projection = {
            "schema_version": 1,
            "namespace": self.namespace,
            "graphify_mode": "installed_graphify_structural_markdown",
            "graphify_cli_documents_mode": "requires external LLM key in graphify 0.9.11; TTROS uses the installed local Markdown extractor API",
            "source_count": len(file_records),
            "raw_graphify_node_count": len(raw_graph["nodes"]),
            "raw_graphify_edge_count": len(raw_graph["edges"]),
            "raw_graphify_reference_count": raw_reference_count,
            "explicit_wiki_edge_count": len(explicit_edges),
            "package_confirmed_wiki_edge_count": sum(1 for edge in explicit_edges if edge["package_edge_confirmed"]),
            "ttros_repaired_wiki_edge_count": sum(1 for edge in explicit_edges if not edge["package_edge_confirmed"]),
            "stable_note_id_count": len(note_nodes),
            "heading_node_count": len(heading_nodes),
            "input_tokens": int(raw_graph.get("input_tokens") or 0),
            "output_tokens": int(raw_graph.get("output_tokens") or 0),
            "bodies_in_projection": False,
            "token_usage_text": TOKEN_USAGE_TEXT,
        }
        return graph, projection

    @staticmethod
    def _artifact_hashes(directory: Path) -> dict[str, str]:
        return {
            name: _sha256_bytes((directory / name).read_bytes())
            for name in ("graph.json", "source_manifest.json", "projection_manifest.json")
        }

    def _write_receipt(self, payload: dict[str, Any]) -> Path:
        path = self.receipts / f"{_stamp()}-{payload['operation']}-{payload['status']}.json"
        _atomic_write(path, _json_bytes(payload))
        return path

    def build(self) -> dict[str, Any]:
        self.document_root.mkdir(parents=True, exist_ok=True)
        self.namespace_root.mkdir(parents=True, exist_ok=True)
        temp_root = Path(tempfile.mkdtemp(prefix=f".tmp-{self.namespace}-", dir=self.document_root))
        try:
            source_manifest = self.source_manifest()
            mirror = temp_root / "source"
            for record in source_manifest["files"]:
                source = self.vault_root / record["relative_path"]
                target = mirror / record["relative_path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            raw_path = temp_root / "raw_graphify.json"
            raw_graph = self._run_graphify_structural(mirror, raw_path)
            graph, projection = self._projection(source_manifest, raw_graph)
            candidate = temp_root / "published"
            candidate.mkdir()
            _atomic_write(candidate / "graph.json", _json_bytes(graph))
            _atomic_write(candidate / "source_manifest.json", _json_bytes(source_manifest))
            _atomic_write(candidate / "projection_manifest.json", _json_bytes(projection))
            candidate_hashes = self._artifact_hashes(candidate)
            operation = "build"
            if self.published.is_dir() and self._artifact_hashes(self.published) == candidate_hashes:
                operation = "unchanged"
            else:
                moved_previous = None
                try:
                    if self.published.exists():
                        moved_previous = self.history / _stamp() / "published"
                        moved_previous.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(self.published, moved_previous)
                    self.published.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(candidate, self.published)
                except Exception:
                    if moved_previous and moved_previous.exists() and not self.published.exists():
                        os.replace(moved_previous, self.published)
                    raise
            receipt = {
                "status": "success",
                "operation": operation,
                "timestamp": _iso_now(),
                "namespace": self.namespace,
                "source_manifest_sha256": source_manifest["aggregate_sha256"],
                "artifact_hashes": candidate_hashes,
                "published": str(self.published),
                "token_usage_text": TOKEN_USAGE_TEXT,
            }
            receipt_path = self._write_receipt(receipt)
            return {**receipt, "receipt_path": str(receipt_path), "projection": projection}
        except Exception as exc:
            failure = {
                "status": "failed",
                "operation": "build",
                "timestamp": _iso_now(),
                "namespace": self.namespace,
                "error": str(exc),
                "previous_published_usable": self._published_is_usable(),
                "token_usage_text": TOKEN_USAGE_TEXT,
            }
            self._write_receipt(failure)
            if isinstance(exc, BusinessBrainGraphError):
                raise
            raise BusinessBrainGraphError(str(exc)) from exc
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)

    def _published_is_usable(self) -> bool:
        try:
            graph = json.loads((self.published / "graph.json").read_text(encoding="utf-8"))
            manifest = json.loads((self.published / "source_manifest.json").read_text(encoding="utf-8"))
            return isinstance(graph.get("nodes"), list) and isinstance(manifest.get("files"), list)
        except (OSError, json.JSONDecodeError, AttributeError):
            return False

    def status(self) -> dict[str, Any]:
        if not self._published_is_usable():
            return {"state": "unavailable", "trusted": False, "fallback": "pointers_search", "reason": "published graph is missing or invalid"}
        try:
            current = self.source_manifest()
            published = json.loads((self.published / "source_manifest.json").read_text(encoding="utf-8"))
        except (BusinessBrainGraphError, OSError, json.JSONDecodeError) as exc:
            return {"state": "unavailable", "trusted": False, "fallback": "pointers_search", "reason": str(exc)}
        if current.get("aggregate_sha256") != published.get("aggregate_sha256"):
            return {"state": "stale", "trusted": False, "fallback": "pointers_search", "reason": "source manifest changed since publication"}
        return {"state": "fresh", "trusted": True, "fallback": None, "source_manifest_sha256": current["aggregate_sha256"]}

    def query_targets(
        self,
        query: str,
        *,
        limit: int = 5,
        client_scope: str | None = None,
        registry: ClientScopeRegistry | None = None,
    ) -> dict[str, Any]:
        gate = registry or self.registry
        identity = gate.validate_graph_namespace(client_scope, self.namespace)
        state = self.status()
        if state["state"] != "fresh":
            return {"query": query, "targets": [], "graph_state": state["state"], "trusted_for_model": False, "fallback": {"route": "pointers_search", "reason": state["reason"]}, "token_usage_text": TOKEN_USAGE_TEXT}
        terms = set(WORD_RE.findall(str(query).lower()))
        graph = json.loads((self.published / "graph.json").read_text(encoding="utf-8"))
        headings: dict[str, list[str]] = {}
        for edge in graph["edges"]:
            if edge.get("relation") == "contains":
                headings.setdefault(edge["source"], []).append(edge["target"])
        nodes = {node["id"]: node for node in graph["nodes"]}
        ranked = []
        for node in graph["nodes"]:
            if node.get("kind") != "note":
                continue
            try:
                scoped_path = gate.validate_graph_target(identity.scope_id, self.namespace, str(node.get("source_path") or ""))
            except ClientScopeError:
                continue
            searchable = " ".join([str(node.get("title") or ""), str(node.get("relative_path") or ""), str(node.get("metadata") or "")] + [str(nodes.get(child, {}).get("label") or "") for child in headings.get(node["id"], [])]).lower()
            score = sum(3 if term in str(node.get("title") or "").lower() else 2 if term in str(node.get("relative_path") or "").lower() else 1 for term in terms if term in searchable)
            if score:
                ranked.append({"path": scoped_path, "score": float(score)})
        ranked.sort(key=lambda row: (-row["score"], row["path"]))
        return {
            "query": query,
            "targets": ranked[: max(1, min(int(limit), 20))],
            "graph_state": "fresh",
            "trusted_for_model": True,
            "client_scope": identity.scope_id,
            "trust_note": "Targets passed the Block 2 scope registry before return; authoritative note loading remains separate.",
            "fallback": None,
            "token_usage_text": TOKEN_USAGE_TEXT,
        }

    def publish_capture_metadata(self, records: list[dict[str, Any]] | list[Any]) -> dict[str, Any]:
        """Publish typed evidence leaves beside, never inside, the Brain graph."""
        try:
            from aos_capture import CaptureMetadataProjection
        except ModuleNotFoundError:
            from tools.aos_capture import CaptureMetadataProjection
        rows = []
        for value in records:
            row = CaptureMetadataProjection.from_mapping(value.to_dict()) if hasattr(value, "to_dict") else CaptureMetadataProjection.from_mapping(dict(value))
            self.registry.validate_capture_evidence_reference(row.client_scope, row.reference_path)
            rows.append(row)
        nodes = []
        edges = []
        for row in sorted(rows, key=lambda item: item.reference_path):
            nodes.append({
                "id": f"capture-evidence:{row.record_id}",
                "kind": "capture_evidence",
                "reference_path": row.reference_path,
                "client_scope": row.client_scope,
                "linked_item_id": row.linked_item_id,
                "subject_classification": row.subject_classification,
                "timestamp": row.timestamp,
                "source_type": row.source_type,
                "triage_state": row.triage_state,
                "proposal_state": row.proposal_state,
                "authoritative": False,
            })
            if row.linked_item_id:
                edges.append({
                    "source": f"capture-evidence:{row.record_id}",
                    "target": f"work-item:{row.linked_item_id}",
                    "relation": "proposes",
                    "client_scope": row.client_scope,
                    "authoritative": False,
                })
        graph = {
            "schema_version": 1,
            "namespace": self.namespace,
            "projection": "capture_metadata_only",
            "source_authority": False,
            "nodes": nodes,
            "edges": edges,
            "raw_content_fields_serializable": False,
        }
        self.published.mkdir(parents=True, exist_ok=True)
        target = self.published / "capture_evidence.graph.json"
        _atomic_write(target, _json_bytes(graph))
        receipt = {
            "operation": "capture-metadata-projection",
            "status": "success",
            "created_at": _iso_now(),
            "namespace": self.namespace,
            "artifact": str(target),
            "sha256": _sha256_bytes(target.read_bytes()),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "metadata_only": True,
            "token_usage_text": TOKEN_USAGE_TEXT,
        }
        receipt_path = self._write_receipt(receipt)
        return {**receipt, "receipt": str(receipt_path)}

    def query_capture_targets(
        self,
        query: str,
        *,
        client_scope: str | None,
        limit: int = 10,
        registry: ClientScopeRegistry | None = None,
    ) -> dict[str, Any]:
        gate = registry or self.registry
        identity = gate.resolve_scope(client_scope)
        path = self.published / "capture_evidence.graph.json"
        if not path.is_file():
            return {"query": query, "targets": [], "graph_state": "unavailable", "fallback": "search"}
        try:
            graph = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BusinessBrainGraphError("capture evidence projection is invalid") from exc
        terms = WORD_RE.findall(query.lower())
        ranked = []
        for node in graph.get("nodes") or []:
            if node.get("kind") != "capture_evidence" or node.get("client_scope") != identity.scope_id:
                continue
            reference = gate.validate_capture_evidence_reference(identity.scope_id, str(node.get("reference_path") or ""))
            searchable = " ".join(str(node.get(key) or "") for key in ("subject_classification", "triage_state", "proposal_state", "source_type")).lower()
            score = sum(1 for term in terms if term in searchable) if terms else 1
            if score:
                ranked.append({"path": reference, "score": float(score)})
        ranked.sort(key=lambda row: (-row["score"], row["path"]))
        return {"query": query, "targets": ranked[: max(1, min(int(limit), 20))], "graph_state": "fresh", "fallback": None}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("build", "status", "query"))
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--vault", type=Path, default=business_brain.BUSINESS_BRAIN_ROOT)
    parser.add_argument("--graphify-root", type=Path, default=DEFAULT_GRAPHIFY_ROOT)
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--client-scope")
    args = parser.parse_args()
    service = BusinessBrainGraphService(graphify_root=args.graphify_root, vault_root=args.vault, namespace=args.namespace)
    if args.command == "build":
        result = service.build()
    elif args.command == "status":
        result = service.status()
    else:
        result = service.query_targets(args.query, client_scope=args.client_scope)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
