"""Focused deterministic source-intake contract tests.

Revisit: when source intake, scope, search, or Graphify contracts change. · Last touched: 2026-08-17.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.business_brain_test_support import registry_data
from tools import aos_indexer
from tools import context_assembler
from tools.business_brain_context import ScopedBrainLoader
from tools.business_brain_scope import ClientScopeError, ClientScopeRegistry
from tools.source_intake import extract_exact_bytes, run_intake

ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-08-17T12:00:00Z"


def write(path: Path, value: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else value.encode("utf-8"))


def note(note_id: str, title: str, body: str) -> str:
    return f"---\nid: {note_id}\ntype: knowledge\n---\n# {title}\n\n{body}\n"


def hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file() and ".git" not in path.parts
    }


class SourceIntakeTest(unittest.TestCase):
    def fixture(self, root: Path):
        repo, brain, graph = root / "repo", root / "brain", root / "graphify"
        write(repo / "queue/ingest_watch.json", json.dumps({"inboxes": ["queue/inbox"], "watch_roots": []}))
        data = registry_data()
        global_scope = data["scopes"]["global"]
        global_scope["brain_pointer_prefixes"] = ["business_brain:sources/intake/records/"]
        global_scope["brain_pointers"].append("business_brain:sources/intake/INDEX.md")
        global_scope["search_source_identities"].append({
            "source": "business_brain", "path_prefix": "business_brain:sources/intake/records/",
        })
        global_scope["search_source_identities"][-2]["paths"].append("business_brain:sources/intake/INDEX.md")
        global_scope["graphify_targets"][0]["paths"].append("business_brain:sources/intake/INDEX.md")
        write(repo / "context/client_scope_registry.json", json.dumps(data, indent=2) + "\n")
        write(brain / "README.md", note("root", "Root", "[[index/MEMORY_INDEX|Index]]"))
        write(brain / "index/MEMORY_INDEX.md", note("index", "Index", "[[memory/global|Global]]"))
        write(brain / "memory/global.md", note("global", "Global", "fixture knowledge"))
        for name in ("app.json", "appearance.json", "core-plugins.json", "workspace.json"):
            write(brain / ".obsidian" / name, "{}\n")
        write(brain / ".obsidian/graph.json", json.dumps({"search": "-path:_backups"}) + "\n")
        subprocess.run(["git", "init", "-q", str(brain)], check=True)
        registry = ClientScopeRegistry(
            registry_path=repo / "context/client_scope_registry.json",
            schema_path=ROOT / "context/client_scope_registry.schema.json",
        )
        return repo, brain, graph, registry

    def test_capture_exact_retrieval_duplicate_zero_model_and_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, brain, graph, registry = self.fixture(root)
            raw = b"# Fixture call 2026-08-17\n\nIntake sentinel zephyr-lantern.\r\n"
            source = root / "input" / "fixture-call-2026-08-17.txt"
            write(source, raw)
            result = run_intake(
                source, repo_root=repo, brain_root=brain,
                registry_path=repo / "context/client_scope_registry.json",
                schema_path=ROOT / "context/client_scope_registry.schema.json",
                search_db=repo / "search/os_index.db", graphify_root=graph,
                commit=False, now=lambda: NOW,
            )
            self.assertEqual((result.scanned, result.imported, result.duplicates), (1, 1, 0))
            self.assertEqual(result.model_invocations, 0)
            self.assertTrue(result.retrieval_ready)
            self.assertEqual(
                result.compact(),
                "1 file scanned | 1 imported | 0 duplicates | 0 model calls | retrieval ready",
            )
            pointer = result.imported_pointers[0]
            record = brain / pointer.removeprefix("business_brain:")
            self.assertEqual(extract_exact_bytes(record.read_text(encoding="utf-8")), raw)
            self.assertEqual(hashlib.sha256(extract_exact_bytes(record.read_text(encoding="utf-8"))).hexdigest(), hashlib.sha256(raw).hexdigest())

            loader = ScopedBrainLoader(
                registry=registry, vault_root=brain, search_db_path=repo / "search/os_index.db",
                search_module=aos_indexer,
            )
            retrieved = loader.retrieve(work={"client_scope": "global"}, query="zephyr lantern")
            self.assertEqual(retrieved.reads[0].provenance.path, pointer)
            self.assertEqual(retrieved.reads[0].provenance.retrieval_route, "search")

            before_duplicate = hashes(root)
            duplicate = run_intake(
                source, repo_root=repo, brain_root=brain,
                registry_path=repo / "context/client_scope_registry.json",
                schema_path=ROOT / "context/client_scope_registry.schema.json",
                search_db=repo / "search/os_index.db", graphify_root=graph,
                commit=False, now=lambda: NOW,
            )
            self.assertEqual((duplicate.imported, duplicate.duplicates), (0, 1))
            self.assertEqual(hashes(root), before_duplicate)

            with self.assertRaises(ClientScopeError):
                registry.validate_brain_pointer("client-a", pointer)
            with self.assertRaisesRegex(Exception, "global-only"):
                run_intake(source, repo_root=repo, brain_root=brain, registry_path=repo / "context/client_scope_registry.json",
                           schema_path=ROOT / "context/client_scope_registry.schema.json", client_scope="client-a", commit=False)

    def test_unsupported_input_fails_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, brain, graph, _registry = self.fixture(root)
            source = root / "input" / "unsupported.pdf"
            write(source, b"%PDF fixture")
            before = hashes(root)
            with self.assertRaisesRegex(Exception, "unsupported input"):
                run_intake(
                    source, repo_root=repo, brain_root=brain,
                    registry_path=repo / "context/client_scope_registry.json",
                    schema_path=ROOT / "context/client_scope_registry.schema.json",
                    search_db=repo / "search/os_index.db", graphify_root=graph,
                    commit=False, now=lambda: NOW,
                )
            self.assertEqual(hashes(root), before)

    def test_david_capability_matching_finds_source_intake(self):
        block = context_assembler._matching_workflows_block(
            "Import these transcripts as historical business context"
        )
        self.assertIn("source-intake/SKILL.md", block.content)
        self.assertIn("CAPTURE (DEFAULT)", block.content)


if __name__ == "__main__":
    unittest.main()
