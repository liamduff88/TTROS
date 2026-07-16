import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from dashboard.backend.business_brain_graph import BusinessBrainGraphError, BusinessBrainGraphService
from tests.business_brain_test_support import make_registry, write_note


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class FailingBusinessBrainGraphService(BusinessBrainGraphService):
    def _run_graphify_structural(self, mirror: Path, output: Path):
        raise BusinessBrainGraphError("injected extractor failure")


class BusinessBrainGraphTest(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path]:
        vault = root / "vault"
        graphify = root / "graphify"
        write(vault / "README.md", "---\nid: fixture-root\ntype: navigation\n---\n# Fixture Brain\n\n[[memory/company|Company]] · [[memory/offers|Offers]]\n")
        write(vault / "memory" / "company.md", "---\nid: fixture-company\ntype: knowledge\n---\n# Company\n\nSee [[memory/offers|Offers]].\n")
        write(vault / "memory" / "offers.md", "---\nid: fixture-offers\ntype: knowledge\n---\n# Offers\n\nScoped workflow builds.\n")
        write(vault / "_backups" / "old.md", "# Backup body must never surface\n")
        return vault, graphify

    def test_real_graphify_markdown_projection_and_ranked_paths_only(self):
        with tempfile.TemporaryDirectory() as temp:
            vault, graphify = self.fixture(Path(temp))
            before = tree_hashes(vault)
            service = BusinessBrainGraphService(graphify_root=graphify, vault_root=vault)
            built = service.build()
            self.assertEqual(built["status"], "success")
            self.assertEqual(tree_hashes(vault), before)
            graph = json.loads((service.published / "graph.json").read_text(encoding="utf-8"))
            manifest = json.loads((service.published / "source_manifest.json").read_text(encoding="utf-8"))
            projection = json.loads((service.published / "projection_manifest.json").read_text(encoding="utf-8"))
            note_ids = {node["id"] for node in graph["nodes"] if node["kind"] == "note"}
            self.assertEqual(note_ids, {"fixture-root", "fixture-company", "fixture-offers"})
            self.assertEqual(len(manifest["files"]), 3)
            self.assertTrue(all("_backups" not in row["relative_path"] for row in manifest["files"]))
            explicit = [edge for edge in graph["edges"] if edge["edge_kind"] == "explicit"]
            self.assertEqual(len(explicit), 3)
            self.assertGreaterEqual(projection["package_confirmed_wiki_edge_count"], 2)
            self.assertGreaterEqual(projection["ttros_repaired_wiki_edge_count"], 1)
            result = service.query_targets("offers workflow", client_scope="global")
            self.assertEqual(result["graph_state"], "fresh")
            self.assertTrue(result["trusted_for_model"])
            self.assertTrue(result["targets"])
            self.assertEqual(set(result["targets"][0]), {"path", "score"})
            self.assertNotIn("Scoped workflow builds", json.dumps(result))

    def test_unchanged_build_is_idempotent_and_failure_preserves_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            vault, graphify = self.fixture(Path(temp))
            service = BusinessBrainGraphService(graphify_root=graphify, vault_root=vault)
            first = service.build()
            first_hashes = service._artifact_hashes(service.published)
            second = service.build()
            self.assertEqual(second["operation"], "unchanged")
            self.assertEqual(service._artifact_hashes(service.published), first_hashes)
            failing = FailingBusinessBrainGraphService(graphify_root=graphify, vault_root=vault)
            with self.assertRaises(BusinessBrainGraphError):
                failing.build()
            self.assertEqual(service._artifact_hashes(service.published), first_hashes)
            self.assertEqual(service.status()["state"], "fresh")
            self.assertEqual(first["artifact_hashes"], second["artifact_hashes"])

    def test_stale_and_unavailable_graphs_fall_back_without_targets(self):
        with tempfile.TemporaryDirectory() as temp:
            vault, graphify = self.fixture(Path(temp))
            service = BusinessBrainGraphService(graphify_root=graphify, vault_root=vault)
            unavailable = service.query_targets("offers", client_scope="global")
            self.assertEqual(unavailable["graph_state"], "unavailable")
            self.assertEqual(unavailable["fallback"]["route"], "pointers_search")
            service.build()
            with (vault / "memory" / "offers.md").open("a", encoding="utf-8") as handle:
                handle.write("Changed after build.\n")
            stale = service.query_targets("offers", client_scope="global")
            self.assertEqual(stale["graph_state"], "stale")
            self.assertEqual(stale["targets"], [])
            self.assertEqual(stale["fallback"]["route"], "pointers_search")

    def test_two_client_targets_are_filtered_before_return_and_contain_no_bodies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vault, graphify = root / "vault", root / "graphify"
            write_note(vault / "memory/client-a.md", "note-a", "Shared Discovery", "CLIENT-A-BODY-SENTINEL")
            write_note(vault / "memory/client-b.md", "note-b", "Shared Discovery", "CLIENT-B-BODY-SENTINEL")
            write_note(vault / "memory/global.md", "note-global", "Global", "global")
            write_note(vault / "README.md", "note-root", "Root", "root")
            write_note(vault / "index/MEMORY_INDEX.md", "note-index", "Index", "index")
            registry = make_registry()
            service = BusinessBrainGraphService(graphify_root=graphify, vault_root=vault, registry=registry)
            service.build()
            result = service.query_targets("shared discovery", client_scope="client-a", registry=registry)
            self.assertEqual(result["targets"], [{"path": "business_brain:memory/client-a.md", "score": 6.0}])
            self.assertNotIn("client-b", json.dumps(result))
            self.assertNotIn("BODY-SENTINEL", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
