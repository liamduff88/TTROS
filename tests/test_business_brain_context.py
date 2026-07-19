import sqlite3
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import aos_indexer
from business_brain_context import (
    BrainContextError, ScopedBrainLoader, classify_work, validate_completion_context, validate_degraded_context,
)
from tests.business_brain_test_support import make_registry, write_note


class BusinessBrainContextTest(unittest.TestCase):
    def test_classification_is_fail_closed(self):
        for work in (
            {"sources": ["business_brain:README.md"]},
            {"client_scope": "global"},
            {"business_facing_skill": True},
            {"business_output": True},
            {"promotion_candidate": True},
            {"implications": ["pricing"]},
            {"client_commitment": True},
            {"legal_implication": True},
            {"financial_implication": True},
        ):
            self.assertEqual(classify_work(work)["classification"], "knowledge_sensitive")
        technical = classify_work({"technical_only": True, "classification": "technical_only"})
        self.assertEqual(technical["brain_context_status"], "not_applicable")
        ambiguous = classify_work({"title": "unclear"})
        self.assertEqual(ambiguous["classification"], "ambiguous")
        self.assertEqual(ambiguous["required_status_on_missing"], "needs_input")

    def test_completion_and_degradation_contracts(self):
        registry = make_registry()
        record = {"note_id": "note-a", "path": "business_brain:memory/client-a.md", "client_scope": "client-a", "retrieval_route": "pointer"}
        validated = validate_completion_context({"client_scope": "client-a"}, brain_context_used=[record], registry=registry)
        self.assertEqual(len(validated["brain_context_used"]), 1)
        with self.assertRaises(BrainContextError):
            validate_completion_context({"client_scope": "client-a"}, registry=registry)
        technical = validate_completion_context({"technical_only": True, "classification": "technical_only"}, brain_context_status="not_applicable", registry=registry)
        self.assertEqual(technical["classification"]["classification"], "technical_only")
        global_technical = validate_completion_context(
            {"client_scope": "global", "context_classification": "technical_only"},
            brain_context_status="not_applicable",
            registry=registry,
        )
        self.assertEqual(global_technical["classification"]["classification"], "technical_only")
        safe = {
            "missing_source": "derived graph", "reason_unavailable": "graph stale", "fallback_used": "scoped exact search",
            "why_safe": "authoritative note remains available", "client_scope": "client-a", "explicit_safe_without_source": True,
        }
        self.assertEqual(validate_degraded_context(safe, classification=classify_work({"client_scope": "client-a"})), safe)
        for reason in ("unresolved scope", "cross-client conflict", "missing pricing context"):
            with self.assertRaises(BrainContextError):
                validate_degraded_context({**safe, "reason_unavailable": reason}, classification=classify_work({"client_scope": "client-a"}))

    def test_loader_hierarchy_routes_and_actual_reads_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vault, live = root / "vault", root / "live"
            live.mkdir()
            write_note(vault / "memory/client-a.md", "note-a", "Client A", "exact durable phrase")
            write_note(vault / "memory/client-b.md", "note-b", "Client B", "exact durable phrase")
            registry = make_registry()
            db = live / "search/index.db"
            old = (aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT, aos_indexer.INGEST_CONFIG_PATH)
            aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT = live, vault
            aos_indexer.INGEST_CONFIG_PATH = live / "queue/ingest_watch.json"
            try:
                scanned = aos_indexer.scan(db, roots=[vault], registry=registry)
                self.assertEqual(scanned["status"], "success")
                graph = Mock()
                pointer_loader = ScopedBrainLoader(registry=registry, vault_root=vault, graph_service=graph, search_db_path=db)
                pointer = pointer_loader.retrieve(work={"client_scope": "client-a"}, pointers=["business_brain:memory/client-a.md"], query="exact durable phrase", discovery_mode="unclear")
                self.assertEqual(pointer.brain_context_used[0]["retrieval_route"], "pointer")
                graph.query_targets.assert_not_called()

                graph.query_targets.return_value = {"targets": [{"path": "business_brain:memory/client-a.md", "score": 3.0}], "graph_state": "fresh", "fallback": None}
                graph_result = pointer_loader.retrieve(work={"client_scope": "client-a"}, query="relationship", discovery_mode="relationship_dependent")
                self.assertEqual(graph_result.brain_context_used[0]["retrieval_route"], "graphify")

                graph.query_targets.return_value = {"targets": [], "graph_state": "stale", "fallback": {"route": "pointers_search", "reason": "stale"}}
                search_result = pointer_loader.retrieve(work={"client_scope": "client-a"}, query="exact durable phrase", discovery_mode="unclear")
                self.assertEqual(search_result.brain_context_used[0]["retrieval_route"], "search")
                self.assertEqual(search_result.graph_state["state"], "stale")

                direct = pointer_loader.retrieve(work={"client_scope": "client-a"}, direct_fallback="business_brain:memory/client-a.md")
                self.assertEqual(direct.brain_context_used[0]["retrieval_route"], "direct_fallback")
            finally:
                aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT, aos_indexer.INGEST_CONFIG_PATH = old


if __name__ == "__main__":
    unittest.main()
