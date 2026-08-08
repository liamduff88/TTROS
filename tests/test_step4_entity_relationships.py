import json
import tempfile
import unittest
from pathlib import Path

from dashboard.backend.business_brain_graph import (
    BusinessBrainGraphService,
    frontmatter_sequence,
    targeted_entity_type,
)
from business_brain_scope import ClientScopeError
from tests.business_brain_test_support import make_registry, registry_data
from tools.validate_business_brain import resolve_wiki_target


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class Step4EntityRelationshipTest(unittest.TestCase):
    def test_targeted_entity_classification_and_exclusions(self):
        self.assertEqual(targeted_entity_type("prospects/person.md", {"type": "prospect"}), "prospect")
        self.assertEqual(targeted_entity_type("offers/fit-call.md", {"type": "offer"}), "offer")
        for relative in (
            "README.md",
            "prospects/index.md",
            "sessions/turn.md",
            "operating_context/executive_view.md",
            "operating_context/open_loops.md",
            "operating_context/TTROS_ARCHITECTURE_NOTE.md",
        ):
            self.assertIsNone(targeted_entity_type(relative, {"type": "prospect"}))
        self.assertIsNone(targeted_entity_type("memory/company.md", {"type": "knowledge"}))

    def test_frontmatter_sequence_is_narrow_and_preserves_source(self):
        text = "---\nid: prospect\ntype: prospect\nqueue_ids:\n  - AOS-2026-0174\nauthor: human\n---\n# Exact body\n"
        before = text.encode("utf-8")
        self.assertEqual(frontmatter_sequence(text, "queue_ids"), ("AOS-2026-0174",))
        self.assertEqual(text.encode("utf-8"), before)

    def test_sibling_wiki_link_resolves_canonically_without_basename_guessing(self):
        paths = {"prospects/index.md", "prospects/loretta.md", "other/loretta.md"}
        self.assertEqual(
            resolve_wiki_target("loretta", source="prospects/index.md", paths=paths),
            "prospects/loretta.md",
        )
        self.assertEqual(
            resolve_wiki_target("missing", source="prospects/index.md", paths=paths),
            "missing.md",
        )

    def test_typed_activity_relationship_and_one_hop_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vault, graphify = root / "vault", root / "graphify"
            write(vault / "README.md", "---\nid: root\ntype: navigation\n---\n# Root\n\n[[index/MEMORY_INDEX|Index]]\n")
            write(vault / "index/MEMORY_INDEX.md", "---\nid: index\ntype: index\n---\n# Index\n\n[[memory/global|Prospect]]\n")
            write(
                vault / "memory/global.md",
                "---\nid: prospect-loretta\ntype: prospect\nstatus: human_review\ndate: 2026-07-22\nqueue_ids:\n  - AOS-2026-0174\nauthor: human\n---\n# Loretta Davis\n\nBODY-SENTINEL\n",
            )
            write(
                vault / "memory/other.md",
                "---\nid: prospect-evan\ntype: prospect\nstatus: human_review\ndate: 2026-07-22\nqueue_ids:\n  - AOS-2026-0175\n---\n# Evan Thompson\n\nOTHER-BODY-SENTINEL\n",
            )
            data = registry_data()
            extra = "business_brain:memory/other.md"
            data["scopes"]["global"]["brain_pointers"].append(extra)
            data["scopes"]["global"]["search_source_identities"][-1]["paths"].append(extra)
            data["scopes"]["global"]["graphify_targets"][0]["paths"].append(extra)
            registry = make_registry(data)
            service = BusinessBrainGraphService(graphify_root=graphify, vault_root=vault, registry=registry)
            before = (vault / "memory/global.md").read_bytes()
            service.build()
            self.assertEqual((vault / "memory/global.md").read_bytes(), before)

            manifest = json.loads((service.published / "source_manifest.json").read_text(encoding="utf-8"))
            prospect = next(row for row in manifest["files"] if row["id"] == "prospect-loretta")
            self.assertEqual(prospect["entity_type"], "prospect")
            self.assertEqual(prospect["status"], "human_review")
            self.assertEqual(prospect["date"], "2026-07-22")

            graph = json.loads((service.published / "graph.json").read_text(encoding="utf-8"))
            touched = [edge for edge in graph["edges"] if edge.get("relation") == "touched"]
            self.assertEqual(len(touched), 2)
            loretta_edge = next(edge for edge in touched if edge["source"] == "activity:AOS-2026-0174")
            self.assertEqual(loretta_edge["edge_kind"], "derived")
            self.assertEqual(loretta_edge["target_path"], "business_brain:memory/global.md")
            self.assertTrue(any(edge.get("edge_kind") == "explicit" for edge in graph["edges"]))

            result = service.query_targets("AOS-2026-0174", client_scope="global")
            self.assertEqual([row["path"] for row in result["targets"]], ["business_brain:memory/global.md"])
            self.assertIn("one-hop derived touched", result["targets"][0]["relationship_reasons"][0])
            self.assertNotIn("BODY-SENTINEL", json.dumps(result))
            by_name = service.query_targets("Loretta Davis activity", client_scope="global")
            self.assertEqual([row["path"] for row in by_name["targets"]], ["business_brain:memory/global.md"])
            self.assertNotIn("other.md", json.dumps(by_name))
            with self.assertRaises(ClientScopeError):
                service.query_targets("AOS-2026-0174", client_scope=None)


if __name__ == "__main__":
    unittest.main()
