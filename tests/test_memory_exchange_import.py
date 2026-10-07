"""Memory Exchange v2 deterministic importer tests.

Revisit: when the Memory Ingest v2 contract changes. · Last touched: 2026-10-07.
"""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.memory_exchange_import import process, list_ready

REAL_KENNETH_PACKAGE = Path("/tmp/ttros-memory-exchange-acceptance/03_READY_FOR_TTROS/INGEST_20261001T004700-0700_kenneth-20260918-meeting")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def covered(paths):
    """A refresh that indexed and graphed every imported note."""
    return {"status": "success"}, {"status": "success", "coverage": [{"pointer": p} for p in paths]}


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ready = self.root / "03_READY_FOR_TTROS"
        self.pkg = self.ready / "MI-20261001T004700-0700-kenneth-sept18"
        self.pkg.mkdir(parents=True)
        self.brain = self.root / "TTROS Business Brain"
        self.brain.mkdir()
        self.payload = b"---\nid: kenneth-sept18\ntype: historical\n---\n# Kenneth September 18\nHistorical evidence.\n"
        self.name = "historical/kenneth-nikshen-targeting-2026-09-18.md"
        self.manifest = {
            "schema_version": "2.0", "semantic_contract_version": "2.0.0",
            "reconciliation_contract_version": "2.0.0", "transport_mode": "directory-v1",
            "status": "ready_for_ttros", "package_id": self.pkg.name,
            "batch_id": "kenneth-20260918-meeting", "batch_fingerprint_sha256": "31a8674fbce58a2ca507c0e8d79b9c5c476375b40690a2efa0b89cde1ceab878",
            "package_disposition": "evidence_only", "source_count": 1,
            "sources": [{"source_id": "SRC-001", "role": "batch_input", "title": "Kenneth meeting"}],
            "canonical_comparison": {"status": "partial"}, "has_conflicts": False, "requires_human_review": False, "output_count": 1,
            "package_files": [{"path": self.name, "size_bytes": len(self.payload), "sha256": sha(self.payload)}],
            "outputs": [{"package_path": self.name, "size_bytes": len(self.payload), "sha256": sha(self.payload),
                         "source_ids": ["SRC-001"], "requires_human_review": False, "conflict_ids": [],
                         "operation": "historical_record", "temporal_posture": "historical",
                         "target": {"namespace": "historical", "suggested_relative_path": self.name,
                                    "canonical_ref": None, "expected_base_sha256": None}}],
        }
        self.write()

    def write(self):
        path = self.pkg / self.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.payload)
        (self.pkg / "INGEST_MANIFEST.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def run_import(self, dry=True, refresh=None):
        return process(self.pkg, brain=self.brain, root=self.root, dry_run=dry,
                       refresh=refresh or covered)

    def test_valid_historical_and_dry_run_zero_writes(self):
        before = set(self.brain.rglob("*"))
        row = self.run_import()
        self.assertEqual(row["outcome"], "validated")
        self.assertEqual(row["outputs"][0]["pointer"], "business_brain:sources/historical_calls/kenneth-nikshen-targeting-2026-09-18.md")
        self.assertEqual(set(self.brain.rglob("*")), before)
        self.assertFalse((self.root / "queue/receipts/memory_exchange_import.jsonl").exists())

    def test_three_kenneth_outputs_stay_historical(self):
        for filename in ("cci-ttr-opportunity-2026-09-18.md", "kenneth-liam-collaboration-2026-09-18.md"):
            name = "historical/" + filename
            self.manifest["package_files"].append({"path": name, "size_bytes": len(self.payload), "sha256": sha(self.payload)})
            output = copy.deepcopy(self.manifest["outputs"][0])
            output["package_path"] = name
            output["target"]["suggested_relative_path"] = name
            self.manifest["outputs"].append(output)
            path = self.pkg / name
            path.write_bytes(self.payload)
        self.manifest["output_count"] = 3
        self.write()
        row = self.run_import()
        self.assertEqual(row["outcome"], "validated")
        self.assertEqual(len(row["outputs"]), 3)
        self.assertTrue(all(o["pointer"].startswith("business_brain:sources/historical_calls/") for o in row["outputs"]))
        self.assertFalse(any(self.brain.rglob("*.md")))

    @unittest.skipUnless(REAL_KENNETH_PACKAGE.is_dir(), "real Kenneth acceptance package unavailable")
    def test_real_kenneth_v2_manifest_dry_run(self):
        manifest = json.loads((REAL_KENNETH_PACKAGE / "INGEST_MANIFEST.json").read_text())
        self.assertEqual(manifest["source_count"], 5)
        self.assertEqual(len(manifest["sources"]), 5)
        self.assertEqual(manifest["output_count"], 3)
        before = set(self.brain.rglob("*"))
        result = process(REAL_KENNETH_PACKAGE, brain=self.brain, root=self.root, dry_run=True)
        self.assertEqual(result["outcome"], "validated", result)
        self.assertEqual({o["pointer"] for o in result["outputs"]}, {
            "business_brain:sources/historical_calls/kenneth-nikshen-targeting-2026-09-18.md",
            "business_brain:sources/historical_calls/cci-ttr-opportunity-2026-09-18.md",
            "business_brain:sources/historical_calls/kenneth-liam-collaboration-2026-09-18.md",
        })
        self.assertEqual(set(self.brain.rglob("*")), before)
        self.assertFalse((self.root / "queue/receipts/memory_exchange_import.jsonl").exists())

    def test_integrity_and_unsafe_paths(self):
        cases = [
            (lambda: self.manifest["package_files"][0].update(sha256="0" * 64), "SHA-256 mismatch"),
            (lambda: self.manifest["package_files"][0].update(size_bytes=1), "byte size mismatch"),
            (lambda: (self.pkg / self.name).unlink(), "missing or escaping"),
            (lambda: (self.pkg / "extra.md").write_text("x"), "unexpected or undeclared"),
            (lambda: self.manifest["outputs"][0]["target"].update(suggested_relative_path="../memory/company.md"), "unsafe path"),
            (lambda: self.manifest["outputs"][0]["target"].update(suggested_relative_path="/tmp/x.md"), "unsafe path"),
        ]
        for change, reason in cases:
            with self.subTest(reason=reason):
                self.setUp()
                change(); self.write() if (self.pkg / self.name).exists() else (self.pkg / "INGEST_MANIFEST.json").write_text(json.dumps(self.manifest))
                self.assertIn(reason, self.run_import()["reason"])

    def test_versions_operation_disposition(self):
        for key, value in (("schema_version", "3.0"), ("semantic_contract_version", "3.0"),
                           ("reconciliation_contract_version", "3.0")):
            old = self.manifest[key]
            self.manifest[key] = value; self.write()
            self.assertEqual(self.run_import()["outcome"], "rejected")
            self.manifest[key] = old
        self.manifest["outputs"][0]["operation"] = "guess_and_merge"; self.write()
        self.assertIn("unsupported operation", self.run_import()["reason"])
        self.manifest["outputs"][0]["operation"] = "historical_record"
        self.manifest["outputs"][0]["target"] = {"namespace": "canonical", "suggested_relative_path": "historical/kenneth-nikshen-targeting-2026-09-18.md"}; self.write()
        self.assertIn("evidence_only", self.run_import()["reason"])

    def test_v2_counts_review_and_target_path_fail_closed(self):
        changes = [
            (lambda: self.manifest.update(source_count=2), "source_count"),
            (lambda: self.manifest.update(output_count=2), "output_count"),
            (lambda: self.manifest.update(requires_human_review=True), "requires review"),
            (lambda: self.manifest["outputs"][0]["target"].update(
                suggested_relative_path="historical/other.md"), "differs from package_path"),
            (lambda: self.manifest["outputs"][0].update(source_ids=["SRC-999"]), "unknown sources"),
        ]
        for change, reason in changes:
            with self.subTest(reason=reason):
                self.setUp()
                change(); self.write()
                self.assertIn(reason, self.run_import()["reason"])

    def test_duplicates_and_restart(self):
        first = self.run_import(False)
        self.assertEqual(first["outcome"], "imported")
        target = Path(first["outputs"][0]["target"])
        self.assertEqual(target.read_bytes(), self.payload)
        self.assertEqual(self.run_import(False)["outcome"], "already_imported")
        self.manifest["package_id"] = "another-package"; self.write()
        self.assertIn("batch fingerprint", self.run_import(False)["reason"])
        self.manifest["package_id"] = self.pkg.name
        self.manifest["sources"][0]["title"] = "changed"; self.write()
        self.assertIn("package ID collision", self.run_import(False)["reason"])

    def test_existing_targets(self):
        target = self.brain / "sources/historical_calls" / Path(self.name).name
        target.parent.mkdir(parents=True)
        target.write_bytes(self.payload)
        self.assertEqual(self.run_import()["outputs"][0]["action"], "already_present")
        target.write_text("different")
        self.assertIn("target collision", self.run_import()["reason"])

    def test_canonical_replacement_guards(self):
        self.manifest["package_disposition"] = "canonical_changes"
        self.manifest["canonical_comparison"]["status"] = "complete"
        out = self.manifest["outputs"][0]
        out.update(operation="canonical_replace", temporal_posture="current",
                   target={"namespace": "canonical", "suggested_relative_path": self.name,
                           "canonical_ref": "business_brain:memory/historical/kenneth-nikshen-targeting-2026-09-18.md",
                           "expected_base_sha256": None})
        self.write()
        self.assertIn("expected_base_sha256", self.run_import()["reason"])
        out["target"]["expected_base_sha256"] = "0" * 64; self.write()
        target = self.brain / "memory" / self.name; target.parent.mkdir(parents=True)
        target.write_text("base")
        self.assertIn("base hash mismatch", self.run_import()["reason"])
        self.manifest["canonical_comparison"]["status"] = "partial"; self.write()
        self.assertIn("complete comparison", self.run_import()["reason"])

    def test_failed_preflight_zero_writes_and_recovery(self):
        self.manifest["package_files"][0]["sha256"] = "0" * 64; self.write()
        self.assertEqual(self.run_import(False)["outcome"], "rejected")
        self.assertFalse(any(self.brain.rglob("*.md")))
        self.manifest["package_files"][0]["sha256"] = sha(self.payload); self.write()
        target = self.brain / "sources/historical_calls" / Path(self.name).name
        target.parent.mkdir(parents=True); target.write_bytes(self.payload)
        recovered = self.run_import(False)
        self.assertEqual(recovered["outcome"], "imported")
        self.assertEqual(recovered["outputs"][0]["action"], "already_present")

    def test_refresh_retry(self):
        first = self.run_import(False, refresh=lambda p: ({"status": "failed"}, {"status": "pending"}))
        self.assertEqual(first["outcome"], "refresh_pending")
        second = self.run_import(False)
        self.assertEqual(second["outcome"], "imported")
        self.assertEqual(second["outputs"][0]["action"], "already_present")

    def test_discovery_is_one_level(self):
        nested = self.pkg / "nested"; nested.mkdir()
        (nested / "INGEST_MANIFEST.json").write_text("{}")
        self.assertEqual(list_ready(self.ready), [self.pkg])

    def test_cli_selects_one_ready_package_in_dry_run(self):
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "tools/memory_exchange_import.py"),
                   "--ready", str(self.ready), "--package", str(self.pkg),
                   "--brain", str(self.brain), "--root", str(self.root), "--dry-run"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"outcome": "validated"', result.stdout)
        self.assertFalse(any(self.brain.rglob("*.md")))

    def test_previously_imported_target_changed_is_rejected(self):
        first = self.run_import(False)
        Path(first["outputs"][0]["target"]).write_text("edited after import")
        again = self.run_import(False)
        self.assertEqual(again["outcome"], "rejected")
        self.assertIn("previously imported target changed", again["reason"])

    def test_graph_not_applicable_is_not_complete_and_is_retried(self):
        legacy = self.run_import(False, refresh=lambda p: ({"status": "success"}, {"status": "not_applicable"}))
        self.assertEqual(legacy["outcome"], "imported")
        target = Path(legacy["outputs"][0]["target"]); before = target.stat().st_mtime_ns
        retried = self.run_import(False)
        self.assertEqual(retried["outcome"], "imported")
        self.assertEqual(retried["graphify_refresh"]["status"], "success")
        self.assertEqual(target.stat().st_mtime_ns, before)
        self.assertEqual(self.run_import(False)["outcome"], "already_imported")

    def _actual_refresh(self, paths, *, allowed=True, bad_node=False):
        from unittest.mock import patch
        from dashboard.backend import business_brain_graph
        from tools import aos_indexer, business_brain_scope, memory_exchange_import as mod
        root, brain = self.root, self.brain

        class Graph:
            def __init__(self, **_kw):
                self.published = root / "published"; self.published.mkdir(exist_ok=True)

            def _published_target_allowlist(self):
                return (set(paths) if allowed else set()), ()

            def build(self):
                files, nodes = [], []
                for pointer in paths:
                    h = sha((brain / pointer.removeprefix("business_brain:")).read_bytes())
                    files.append({"source_path": pointer, "sha256": h})
                    nodes.append({"kind": "note", "source_path": pointer, "id": "node-1",
                                  "content_sha256": "0" * 64 if bad_node else h})
                (self.published / "source_manifest.json").write_text(json.dumps({"files": files}))
                (self.published / "graph.json").write_text(json.dumps({"nodes": nodes}))
                return {"status": "success", "receipt_path": "receipt"}
        with patch.object(aos_indexer, "index_one", lambda *a, **k: {"status": "success"}), \
                patch.object(business_brain_scope, "load_registry", lambda *a: object()), \
                patch.object(business_brain_graph, "BusinessBrainGraphService", Graph):
            return mod._refresh(paths, brain, root)

    def test_refresh_requires_graph_scope_and_matching_node(self):
        pointers = [o["pointer"] for o in self.run_import(False)["outputs"]]
        _search, graph = self._actual_refresh(pointers, allowed=False)
        self.assertEqual((graph["status"], graph["missing"]), ("pending", pointers))
        _search, graph = self._actual_refresh(pointers, bad_node=True)
        self.assertIn("coverage mismatch", graph["reason"])
        _search, graph = self._actual_refresh(pointers)
        self.assertEqual([row["pointer"] for row in graph["coverage"]], pointers)


class ConsumerReceiptTests(unittest.TestCase):
    """The timer path: move, importer-owned receipt beside the packet, recovery."""
    setUp, write = ImportTests.setUp, ImportTests.write

    def consume(self, *extra):
        from unittest.mock import patch
        from tools import memory_exchange_import as mod
        self.imported, self.rejected = self.root / "04_IMPORTED", self.root / "05_REJECTED"
        argv = ["memory_exchange_import.py", "--ready", str(self.ready), "--brain", str(self.brain),
                "--root", str(self.root), "--imported", str(self.imported), "--rejected", str(self.rejected),
                "--move", *extra]
        with patch.object(sys, "argv", argv), patch.object(mod, "_refresh", lambda p, b, r: covered(p)), \
                patch("builtins.print"):
            return mod.main()

    def test_receipt_published_recovered_and_not_rewritten(self):
        self.assertEqual(self.consume(), 0)
        receipt = self.imported / (self.pkg.name + ".IMPORT_RECEIPT.json")
        row = json.loads(receipt.read_text())
        self.assertEqual((row["outcome"], row["issuer"]), ("imported", "tools/memory_exchange_import.py"))
        self.assertEqual(row["sources"], self.manifest["sources"])
        self.assertTrue((self.imported / self.pkg.name / "INGEST_MANIFEST.json").is_file())
        self.assertNotIn("receipt_publication", row)
        receipt.unlink()
        (self.imported / "damaged").mkdir(); (self.imported / "damaged/INGEST_MANIFEST.json").write_text("{")
        self.assertEqual(self.consume(), 0)
        self.assertEqual(json.loads(receipt.read_text())["fingerprint"], row["fingerprint"])
        stamp = receipt.stat().st_mtime_ns
        self.assertEqual(self.consume(), 0)
        self.assertEqual(receipt.stat().st_mtime_ns, stamp)

    def test_rejected_manifest_gets_receipt_typed_package_does_not(self):
        import os
        from unittest.mock import patch
        self.manifest["package_files"][0]["sha256"] = "0" * 64; self.write()
        typed = self.ready / "typed-checkpoint"; typed.mkdir()
        (typed / "CHECKPOINT.json").write_text("{}"); (typed / "extra.txt").write_text("x")
        with patch.dict(os.environ, {"TTROS_SHARED_BRAIN_WRITE": "1"}):
            self.assertEqual(self.consume(), 1)
        row = json.loads((self.rejected / (self.pkg.name + ".IMPORT_RECEIPT.json")).read_text())
        self.assertIn("SHA-256 mismatch", row["reason"])
        self.assertTrue((self.rejected / "typed-checkpoint").is_dir())
        self.assertFalse((self.rejected / "typed-checkpoint.IMPORT_RECEIPT.json").exists())


class ConsumerConfigurationTests(unittest.TestCase):
    repo = Path(__file__).resolve().parents[1]

    def test_timer_service_consumes_full_ingest(self):
        text = (self.repo / "systemd/aos-memory-exchange-import.service").read_text()
        exec_start = [line for line in text.splitlines() if line.startswith("ExecStart=")]
        self.assertEqual(len(exec_start), 1)
        self.assertIn("--move", exec_start[0])
        self.assertNotIn("--typed-only", exec_start[0]); self.assertNotIn("--checkpoint-only", exec_start[0])

    def test_historical_calls_graph_scope_keeps_denies(self):
        registry = json.loads((self.repo / "context/client_scope_registry.json").read_text())
        glob = registry["scopes"]["global"]
        # Graph coverage only: brain_pointer_prefixes is also the dashboard save gate.
        self.assertNotIn("business_brain:sources/historical_calls/", glob["brain_pointer_prefixes"])
        self.assertIn("business_brain:sources/historical_calls/", glob["graphify_targets"][0]["path_prefixes"])
        self.assertEqual(registry["denied_brain_pointers"], ["business_brain:memory/north_shore_sales_coach.md"])


if __name__ == "__main__":
    unittest.main()
