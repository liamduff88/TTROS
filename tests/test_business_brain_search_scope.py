import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import aos_indexer
from business_brain_scope import ClientScopeError
from tests.business_brain_test_support import make_registry, write_note


class BusinessBrainSearchScopeTest(unittest.TestCase):
    def setUp(self):
        self.originals = {name: getattr(aos_indexer, name) for name in (
            "LIVE_ROOT", "BUSINESS_BRAIN_ROOT", "DB_PATH", "INGEST_CONFIG_PATH", "INGEST_RECEIPT_PATH", "CLIENT_SCOPE_REGISTRY_PATH"
        )}

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(aos_indexer, name, value)

    def configure(self, root: Path):
        live, vault = root / "live", root / "vault"
        live.mkdir()
        write_note(vault / "memory/client-a.md", "note-a", "Client A", "SHARED-SENTINEL alpha")
        write_note(vault / "memory/client-b.md", "note-b", "Client B", "SHARED-SENTINEL beta")
        write_note(vault / "memory/global.md", "note-global", "Global", "SHARED-SENTINEL global")
        write_note(vault / "README.md", "note-root", "Root", "navigation")
        write_note(vault / "index/MEMORY_INDEX.md", "note-index", "Index", "navigation")
        aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT = live, vault
        aos_indexer.DB_PATH = live / "search/os_index.db"
        aos_indexer.INGEST_CONFIG_PATH = live / "queue/ingest_watch.json"
        aos_indexer.INGEST_RECEIPT_PATH = live / "queue/receipts/ingestion.jsonl"
        return live, vault, aos_indexer.DB_PATH

    def test_scope_predicate_selects_before_public_rows_are_built(self):
        with tempfile.TemporaryDirectory() as temp:
            _live, vault, db = self.configure(Path(temp))
            registry = make_registry()
            self.assertEqual(aos_indexer.scan(db, roots=[vault], registry=registry)["status"], "success")
            seen = []
            real_public = aos_indexer.public_row

            def instrumented(row):
                seen.append(row["path"])
                return real_public(row)

            with patch.object(aos_indexer, "public_row", side_effect=instrumented):
                result = aos_indexer.search("SHARED-SENTINEL", db_path=db, client_scope="client-a", registry=registry)
            self.assertEqual(seen, ["business_brain:memory/client-a.md"])
            self.assertNotIn("client-b", str(result))
            with patch.object(aos_indexer, "connect", side_effect=AssertionError("database must not open")):
                with self.assertRaises(ClientScopeError):
                    aos_indexer.search("anything", db_path=db, client_scope=None, registry=registry)
            with self.assertRaises(ClientScopeError):
                aos_indexer.search("anything", db_path=db, client_scope="client-a", source="agentic_os_live", registry=registry)

    def test_failed_replacement_retains_previous_usable_index(self):
        with tempfile.TemporaryDirectory() as temp:
            _live, vault, db = self.configure(Path(temp))
            registry = make_registry()
            first = aos_indexer.scan(db, roots=[vault], registry=registry)
            self.assertTrue(first["published"])
            before = aos_indexer.search("alpha", db_path=db, client_scope="client-a", registry=registry)
            failed = aos_indexer.scan(db, roots=[vault], registry=registry, failure_injection="after_publish")
            self.assertEqual(failed["status"], "failed")
            self.assertTrue(failed["retained_previous"])
            after = aos_indexer.search("alpha", db_path=db, client_scope="client-a", registry=registry)
            self.assertEqual(after["count"], before["count"])
            self.assertEqual(after["groups"]["memory"][0]["path"], "business_brain:memory/client-a.md")


if __name__ == "__main__":
    unittest.main()
