"""Search ranking for Memory Ingest v3: topic notes and source indexes above raw intake records.

Revisit: when the v3 Brain layout or aos_indexer.search ordering changes. · Last touched: 2026-11-07.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import aos_indexer
from business_brain_scope import load_registry

FOLDER = "sources/historical_calls/2026-10-14-jordan-ellis-intro-call-4bbd735b"
RECORD = "sources/intake/records/4bbd735bd750c2a6cee5b5669f8a0ceb8a5b2e2dd9eb077a71ba698b55911111.md"
FILLER = "and the then we so it was a lot of talk about the week " * 30

DOCS = {
    # The raw original: every word, many times over.
    RECORD: "Date: Oct 14\n" + ("missed calls trial pricing plumbing referral brother " * 40) + "zebrafish",
    f"{FOLDER}/INDEX.md": "# Jordan Ellis intro call (index)\nTopics: missed calls, trial.\n" + FILLER,
    f"{FOLDER}/missed-calls-problem.md": "# Jordan Ellis: missed calls problem\nJordan misses calls on jobs.\n" + FILLER,
    f"{FOLDER}/nested/deeper.md": "# Not a v3 note\nmissed calls\n" + FILLER,
    "sources/historical_calls/cards/jordan.card.md": "# Card\nmissed calls\n" + FILLER,
    "sources/historical_calls/old-v2-call.md": "# Old call\nmissed calls\n" + FILLER,
    "people/jordan-ellis.md": "# Jordan Ellis\nPerson hub.\n",
}


class SearchRankingV3Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "search" / "os_index.db"
        conn = aos_indexer.connect(self.db)
        for relative, text in DOCS.items():
            aos_indexer.upsert_document(conn, {
                "path": f"business_brain:{relative}", "title": text.splitlines()[0].lstrip("# "), "kind": "memory",
                "source": "business_brain", "source_root": "/vault", "client_scope": "global", "mtime": 1.0,
                "tags": "", "snippet": "", "body": text, "indexed_at": "2026-11-07T00:00:00Z", "size_bytes": len(text),
            })
        conn.commit()
        conn.close()
        self.registry = load_registry(aos_indexer.CLIENT_SCOPE_REGISTRY_PATH)

    def paths(self, query, **kwargs):
        result = aos_indexer.search(query, source="business_brain", client_scope="global", db_path=self.db,
                                    registry=self.registry, **kwargs)
        return [row["path"].removeprefix("business_brain:") for group in result["groups"].values() for row in group]

    def test_bm25_alone_would_put_the_record_first(self):
        # The detector can say NO: on raw bm25 order the record wins this query.
        conn = aos_indexer.connect(self.db, readonly=True)
        rows = conn.execute(
            "SELECT d.path FROM documents d JOIN documents_fts f ON d.id = f.rowid WHERE documents_fts MATCH ? "
            "ORDER BY bm25(documents_fts)", (aos_indexer.quote_fts_query("missed calls"),)).fetchall()
        conn.close()
        self.assertEqual("business_brain:" + RECORD, rows[0][0])

    def test_topic_notes_and_index_rank_above_the_record(self):
        paths = self.paths("missed calls")
        self.assertEqual({f"{FOLDER}/missed-calls-problem.md", f"{FOLDER}/INDEX.md"}, set(paths[:2]))
        self.assertEqual(RECORD, paths[-1])  # still searchable, last
        # A nested file and the cards folder are not v3 notes; they keep plain bm25 weight.
        self.assertIn(f"{FOLDER}/nested/deeper.md", paths)
        self.assertIn("sources/historical_calls/cards/jordan.card.md", paths)

    def test_exact_and_path_only_searches_use_the_same_order(self):
        paths = self.paths("missed calls", exact=True, path_only=True)
        self.assertEqual(f"{FOLDER}/missed-calls-problem.md", paths[0])
        self.assertEqual(RECORD, paths[-1])

    def test_record_wins_when_nothing_else_matches(self):
        self.assertEqual([RECORD], self.paths("zebrafish"))

    def test_matching_is_unchanged(self):
        self.assertEqual(["people/jordan-ellis.md"], self.paths("hub"))
        self.assertEqual(len(DOCS) - 1, len(self.paths("missed calls")))


if __name__ == "__main__":
    unittest.main()
