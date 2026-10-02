"""Derived Memory entity index: deterministic, metadata-only, no silent merges."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import aos_entity_index as E
import aos_indexer


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


DOCS = {
    "sources/historical_calls/kenneth-june-30.md": '---\nid: hs-1\ntype: historical_source\nsource_document_kind: call_transcript\nparticipants_text: "Liam Duff; Kenneth (surname absent from metadata)"\nsource_date_text: "Jun 30"\nimported_at: "2026-08-17"\n---\n# Historical source — Call with Kenneth\n',
    "sources/historical_calls/cards/kenneth-june-30.card.md": '---\nid: card-1\ntype: source_card\nsource_path: "sources/historical_calls/kenneth-june-30.md"\nentities: "Ollie opportunity, budget constraints"\n---\n# June 30 call summary\n',
    "sources/historical_calls/moodley.md": '---\nid: hs-2\ntype: historical_source\nparticipants_text: "Liam Duff; Dr Kenneth Moodley"\nimported_at: "2026-08-17"\n---\n# Historical source — Call with Dr Kenneth Moodley\n',
    "sources/historical_calls/stanick.md": '---\nid: hs-3\ntype: historical_source\nparticipants_text: "Liam Duff; Ken Stanick"\nsource_date_text: "Jul 7"\nimported_at: "2026-08-17"\n---\n# Historical source — Quinn founder\n',
    "sources/historical_calls/kenneth-nikshen-targeting-2026-09-18.md": "# Kenneth / Nikshen Targeting — Historical Evidence (2026-09-18)\n\n**Temporal posture:** historical\n",
    "sources/historical_calls/cci-ttr-opportunity-2026-09-18.md": "# CCI / Time to Revenue Opportunity — Historical Evidence (2026-09-18)\n\n**Temporal posture:** historical\nKenneth said...\n",
    "memory/clients.md": "---\nid: clients\ntype: knowledge\n---\n# Clients\n\n- Contacts: Kenneth Moodley (referral).\n",
    "sources/historical_calls/INDEX.md": "---\nid: idx\ntype: index\n---\n# Index\nKenneth Moodley, Ken Stanick, Kenneth\n",
}


class MemoryEntityIndexTest(unittest.TestCase):
    def build(self, temp: Path) -> Path:
        vault, db = temp / "vault", temp / "search" / "os_index.db"
        conn = aos_indexer.connect(db)
        for relative, text in DOCS.items():
            write(vault / relative, text)
            aos_indexer.upsert_document(conn, {
                "path": f"business_brain:{relative}", "title": relative, "kind": "memory", "source": "business_brain",
                "source_root": str(vault), "client_scope": "global", "mtime": 1.0, "tags": "", "snippet": "",
                "body": text, "indexed_at": "2026-10-02T00:00:00Z", "size_bytes": len(text),
            })
        conn.commit()
        conn.close()
        receipts = temp / "receipts.jsonl"
        receipts.write_text(json.dumps({"outcome": "imported", "package_id": "MI-test", "outputs": [
            {"pointer": "business_brain:sources/historical_calls/kenneth-nikshen-targeting-2026-09-18.md"},
            {"pointer": "business_brain:sources/historical_calls/cci-ttr-opportunity-2026-09-18.md"},
        ]}) + "\n", encoding="utf-8")
        self.patch = patch.object(E, "MEMORY_EXCHANGE_RECEIPTS", receipts)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        result = E.rebuild(db, vault=vault)
        self.assertEqual(result["token_usage_text"], "Token usage: no agent invocation")
        return db

    def test_kenneth_variants_never_merge(self):
        with tempfile.TemporaryDirectory() as temp:
            db = self.build(Path(temp))
            found = E.search_entities("Kenneth", db_path=db)
            self.assertEqual(found["resolution"], "ambiguous")
            names = [row["display_name"] for row in found["entities"]]
            self.assertEqual(names[:2], ["Kenneth", "Kenneth Moodley"])
            self.assertNotIn("Ken Stanick", names)
            self.assertEqual(E.search_entities("Ken Stanick", db_path=db)["resolution"], "single")
            self.assertEqual(len(E.search_entities("Ken", db_path=db)["entities"]), 3)

    def test_entity_view_links_only_declared_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            db = self.build(Path(temp))
            view = E.entity_view("person:kenneth", db_path=db)
            basis = {item["path"].split("/")[-1]: item["basis"] for item in view["knowledge"] + view["sources"]}
            self.assertEqual(basis["kenneth-june-30.md"], "participants metadata")
            self.assertEqual(basis["kenneth-june-30.card.md"], "card of linked source")
            self.assertEqual(basis["kenneth-nikshen-targeting-2026-09-18.md"], "title mention")
            self.assertEqual(basis["cci-ttr-opportunity-2026-09-18.md"], "same Memory Ingest package")
            self.assertNotIn("moodley.md", basis)
            self.assertNotIn("INDEX.md", basis)
            self.assertEqual([item["path"].split("/")[-1] for item in view["sources"]], ["kenneth-june-30.md"])
            self.assertEqual(view["entity"]["latest_date"], "2026-09-18")
            self.assertEqual([row["display_name"] for row in view["similar_not_merged"]], ["Kenneth Moodley"])
            self.assertNotIn("Ken Stanick", [row["display_name"] for row in view["similar_not_merged"] + view["related"]])
            moodley = E.entity_view("person:kenneth-moodley", db_path=db)
            # import-only dates stay out of the chronology and never count as activity
            self.assertEqual(moodley["entity"]["latest_date"], "")
            self.assertEqual([item["path"].split("/")[-1] for item in moodley["import_dated"]], ["moodley.md"])
            self.assertTrue(all(item["date_basis"] != "imported_at" for item in moodley["timeline"]))
            self.assertIn("2026-09-18", [item["date"] for item in view["timeline"]])
            self.assertEqual({item["path"].split("/")[-1] for item in moodley["knowledge"] + moodley["sources"]}, {"moodley.md", "clients.md"})

    def test_declared_entity_key_resolves_surnameless_participant_only(self):
        declared = "sources/historical_calls/kenneth-june-30.md"
        DOCS_DECLARED = dict(DOCS)
        DOCS_DECLARED[declared] = DOCS[declared].replace("imported_at:", "entity_key: person:kenneth-moodley\nimported_at:")
        with patch.dict(DOCS, DOCS_DECLARED), tempfile.TemporaryDirectory() as temp:
            db = self.build(Path(temp))
            moodley = E.entity_view("person:kenneth-moodley", db_path=db)
            basis = {item["path"].split("/")[-1]: item["basis"] for item in moodley["knowledge"] + moodley["sources"]}
            self.assertEqual(basis["kenneth-june-30.md"], "entity_key metadata")
            self.assertEqual(basis["kenneth-june-30.card.md"], "card of linked source")
            # the only record that created bare "Kenneth" now declares its identity, so no bare entity is invented
            self.assertIsNone(E.entity_view("person:kenneth", db_path=db))
            self.assertNotIn("kenneth-nikshen-targeting-2026-09-18.md", basis)  # undeclared title mention is not silently merged
            self.assertEqual(E.search_entities("Ken Stanick", db_path=db)["entities"][0]["entity_id"], "person:ken-stanick")
            stanick = E.entity_view("person:ken-stanick", db_path=db)
            self.assertEqual([item["path"].split("/")[-1] for item in stanick["sources"]], ["stanick.md"])

    def test_classification_and_dates_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            db = self.build(Path(temp))
            meta = E.document_meta([
                "business_brain:sources/historical_calls/kenneth-june-30.md",
                "business_brain:sources/historical_calls/kenneth-nikshen-targeting-2026-09-18.md",
                "business_brain:memory/clients.md",
            ], db_path=db)
            source = meta["business_brain:sources/historical_calls/kenneth-june-30.md"]
            self.assertEqual((source["role"], source["type_label"], source["date"]), ("source", "Call transcript", "2026-06-30"))
            ingest = meta["business_brain:sources/historical_calls/kenneth-nikshen-targeting-2026-09-18.md"]
            self.assertEqual((ingest["role"], ingest["knowledge_type"], ingest["canonical"], ingest["package_id"]), ("knowledge", "historical_evidence", False, "MI-test"))
            self.assertTrue(meta["business_brain:memory/clients.md"]["canonical"])

    def test_ensure_current_rebuilds_only_on_change(self):
        with tempfile.TemporaryDirectory() as temp:
            db = self.build(Path(temp))
            with patch.object(E, "BUSINESS_BRAIN_ROOT", Path(temp) / "vault"):
                self.assertEqual(E.ensure_current(db)["status"], "current")


if __name__ == "__main__":
    unittest.main()
