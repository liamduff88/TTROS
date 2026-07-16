import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import aos_indexer
from business_brain_context import ScopedBrainLoader, classify_work
from business_brain_promotion import AUTOMATIC_TIER, PromotionCandidate, PromotionWriter, evaluate_promotion, sha256_text
from tests.business_brain_test_support import make_registry, write_note


class BusinessBrainFullLoopTest(unittest.TestCase):
    def test_fixture_classify_retrieve_promote_provenance_and_later_retrieve(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo, vault, live = root / "repo", root / "vault", root / "live"
            (repo / "queue/receipts").mkdir(parents=True)
            (repo / "queue/locks").mkdir(parents=True)
            live.mkdir()
            write_note(vault / "README.md", "note-root", "Root", "root")
            write_note(vault / "memory/global.md", "note-global", "Global", "global")
            write_note(vault / "index/MEMORY_INDEX.md", "note-index", "Memory Index", "Human navigation")
            registry = make_registry()
            work = {"client_scope": "global", "sources": ["business_brain:index/MEMORY_INDEX.md"], "promotion_candidate": True}
            self.assertEqual(classify_work(work)["classification"], "knowledge_sensitive")
            initial = ScopedBrainLoader(registry=registry, vault_root=vault).retrieve(work=work, pointers=work["sources"])
            self.assertEqual(initial.brain_context_used[0]["retrieval_route"], "pointer")
            target = vault / "index/MEMORY_INDEX.md"
            candidate = PromotionCandidate(
                target="business_brain:index/MEMORY_INDEX.md", client_scope="global",
                change_class="generated_marker_section", marker="block-2-outcome-index",
                content="## Verified outcomes\n\n- Fixture durable promotion loop.",
                target_preimage_sha256=sha256_text(target.read_text()),
                provenance_refs=("proof:block-2:accepted-block-1",), reason="fixture full loop",
            )
            self.assertEqual(evaluate_promotion(candidate, registry=registry)["tier"], AUTOMATIC_TIER)
            written = PromotionWriter(repo_root=repo, vault_root=vault, registry=registry).apply(candidate)
            self.assertEqual(written["status"], "success")
            old = (aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT, aos_indexer.INGEST_CONFIG_PATH)
            aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT = live, vault
            aos_indexer.INGEST_CONFIG_PATH = live / "queue/ingest_watch.json"
            db = live / "search/os_index.db"
            try:
                self.assertEqual(aos_indexer.scan(db, roots=[vault], registry=registry)["status"], "success")
                later = ScopedBrainLoader(registry=registry, vault_root=vault, search_db_path=db).retrieve(
                    work={"client_scope": "global"}, query="Fixture durable promotion loop"
                )
                self.assertEqual(later.brain_context_used[0]["retrieval_route"], "search")
                self.assertIn("Fixture durable promotion loop", later.contents[0])
            finally:
                aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT, aos_indexer.INGEST_CONFIG_PATH = old


if __name__ == "__main__":
    unittest.main()
