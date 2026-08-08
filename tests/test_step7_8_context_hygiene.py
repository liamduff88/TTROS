"""Context Assembler v2 and nightly knowledge-hygiene completion proofs.

Revisit: when Step 7 retrieval routes or Step 8 transaction boundaries change. · Last touched: 2026-08-04.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dashboard.backend.business_brain_graph import BusinessBrainGraphService
from tests.business_brain_test_support import make_registry
from tools import aos_indexer, brain_memory, context_assembler, nightly_knowledge_hygiene


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def note(note_id: str, title: str, body: str, *, note_type: str = "knowledge", extra: str = "") -> str:
    return f"---\nid: {note_id}\ntype: {note_type}\n{extra}---\n# {title}\n\n{body.rstrip()}\n"


def hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file() and ".git" not in path.parts
    }


class StepFixture:
    def __init__(self, base: Path):
        self.base = base
        self.root = base / "live"
        self.brain = base / "brain"
        self.graph = base / "graph"
        self.db = self.root / "search/os_index.db"
        (self.root / "queue").mkdir(parents=True)
        pointers = [
            "business_brain:README.md",
            "business_brain:index/MEMORY_INDEX.md",
            "business_brain:memory/company.md",
            "business_brain:memory/global.md",
            "business_brain:memory/client-a.md",
            "business_brain:memory/client-b.md",
            "business_brain:operating_context/current_priorities.md",
            "business_brain:operating_context/executive_view.md",
            "business_brain:operating_context/open_loops.md",
            "business_brain:inbox/contradictions.md",
            "business_brain:prospects/client-a.md",
            "business_brain:prospects/client-b.md",
        ]
        common = [pointer for pointer in pointers if pointer not in {
            "business_brain:memory/client-a.md", "business_brain:memory/client-b.md",
            "business_brain:prospects/client-a.md", "business_brain:prospects/client-b.md",
        }]

        def scope(kind: str, allowed: list[str]) -> dict:
            return {
                "kind": kind,
                "enabled": True,
                "brain_pointers": allowed,
                "search_source_identities": [{"source": "business_brain", "paths": allowed}],
                "graphify_targets": [{"namespace": "ttros-business-brain", "paths": allowed}],
                "evidence_identities": [],
            }

        data = {
            "schema_version": 1,
            "default_deny": True,
            "global_scope_id": "global",
            "denied_brain_pointers": [],
            "scopes": {
                "global": scope("global", common),
                "client-a": scope("client", common + ["business_brain:memory/client-a.md", "business_brain:prospects/client-a.md"]),
                "client-b": scope("client", common + ["business_brain:memory/client-b.md", "business_brain:prospects/client-b.md"]),
            },
        }
        self.registry = make_registry(data)
        all_links = " · ".join(f"[[{pointer.removeprefix('business_brain:').removesuffix('.md')}]]" for pointer in pointers if pointer not in {"business_brain:README.md", "business_brain:index/MEMORY_INDEX.md"})
        write(self.brain / "README.md", note("fixture-root", "Fixture Brain", "[[index/MEMORY_INDEX|Index]]", note_type="navigation"))
        write(self.brain / "index/MEMORY_INDEX.md", note("fixture-index", "Index", all_links, note_type="index"))
        write(self.brain / "memory/company.md", note("fixture-company", "Company", "Shared safe company identity."))
        write(self.brain / "memory/global.md", note("fixture-global", "Global Fact", "Original durable fact."))
        write(self.brain / "memory/client-a.md", note("fixture-client-a", "Client A", "CLIENT-A-BRAIN-SENTINEL exact isolation phrase."))
        write(self.brain / "memory/client-b.md", note("fixture-client-b", "Client B", "CLIENT-B-BRAIN-SENTINEL exact isolation phrase."))
        write(self.brain / "operating_context/current_priorities.md", note("fixture-priorities", "Current Priorities", "Keep the fixture bounded.", note_type="operating_state"))
        write(self.brain / "operating_context/executive_view.md", note("fixture-executive", "Executive View", "Existing synthesis.", note_type="operating_context"))
        write(self.brain / "operating_context/open_loops.md", note(
            "fixture-loops", "Open Loops",
            "## Open\n\n- [client-a] CLIENT-A-LOOP-SENTINEL follow up AOS-2026-9001.\n- [client-b] CLIENT-B-LOOP-SENTINEL follow up AOS-2026-9002.",
            note_type="operating_context",
        ))
        write(self.brain / "inbox/contradictions.md", note("fixture-contradictions", "Contradictions", "## Open\n\n- None.\n\n## Resolved\n\n- None.", note_type="inbox"))
        write(self.brain / "prospects/client-a.md", note(
            "fixture-prospect-a", "Alex Alpha — Client A", "CLIENT-A-GRAPH-SENTINEL relationship evidence.",
            note_type="prospect", extra="status: human_review\nqueue_ids:\n  - AOS-2026-9001\n",
        ))
        write(self.brain / "prospects/client-b.md", note(
            "fixture-prospect-b", "Blair Beta — Client B", "CLIENT-B-GRAPH-SENTINEL relationship evidence.",
            note_type="prospect", extra="status: human_review\nqueue_ids:\n  - AOS-2026-9002\n",
        ))
        write(self.brain / "sessions/2026-08-04_client-a.md", note(
            "fixture-session-a", "Client A session", "## Conversation\n\n### Turn · 2026-08-04T10:00:00Z\n\nCLIENT-A-SESSION-SENTINEL AOS-2026-9001 recent outcome.",
            note_type="session", extra="client_scope: client-a\nstatus: active\n",
        ))
        write(self.brain / "sessions/2026-08-04_client-b.md", note(
            "fixture-session-b", "Client B session", "## Conversation\n\n### Turn · 2026-08-04T11:00:00Z\n\nCLIENT-B-SESSION-SENTINEL AOS-2026-9002 recent outcome.",
            note_type="session", extra="client_scope: client-b\nstatus: active\n",
        ))
        write(self.root / "queue/work_items.jsonl", "\n".join((
            json.dumps({"id": "AOS-2026-9001", "title": "CLIENT-A-COMMITMENT-SENTINEL follow up", "status": "agent_todo", "client_scope": "client-a", "updated_at": "2026-08-04T10:00:00Z", "receipts": [{"path": "queue/receipts/a.md", "created_at": "2026-08-04T10:00:00Z"}]}),
            json.dumps({"id": "AOS-2026-9002", "title": "CLIENT-B-COMMITMENT-SENTINEL follow up", "status": "agent_todo", "client_scope": "client-b", "updated_at": "2026-08-04T11:00:00Z", "receipts": [{"path": "queue/receipts/b.md", "created_at": "2026-08-04T11:00:00Z"}]}),
        )) + "\n")
        write(self.root / "queue/prospects.jsonl", "")
        write(self.root / "queue/ingest_watch.json", json.dumps({"inboxes": ["queue/inbox"], "watch_roots": [], "business_brain_read_index_only": True}) + "\n")
        write(
            self.root / nightly_knowledge_hygiene.REVENUE_GATE_PROOF,
            "# Revenue Gate\n\nVerdict: **PASS** for Steps 0–3 and the Revenue Gate.\n",
        )
        for name in ("app.json", "appearance.json", "core-plugins.json", "workspace.json"):
            write(self.brain / ".obsidian" / name, "{}\n")
        write(self.brain / ".obsidian/graph.json", json.dumps({"search": "-path:_backups"}) + "\n")

    def add_learning_session(self) -> None:
        write(self.brain / "sessions/2026-08-04_learning.md", note(
            "fixture-session-learning", "Learning session", "Historical conversation evidence remains here.",
            note_type="session",
            extra=(
                "client_scope: global\nstatus: active\nknowledge_candidates:\n"
                "  - id: verified-safe-fact\n    state: verified_fact\n    statement: The fixture durable fact is verified.\n"
                "    target: business_brain:memory/global.md\n    evidence: proof:fixture-safe-fact\n    verified: true\n"
                "  - id: executive-pattern\n    state: interpretation\n    statement: The verified fact changes the fixture priority.\n"
                "    evidence: proof:fixture-safe-fact\n"
                "  - id: gated-commitment\n    state: formal_commitment\n    statement: Commit to a formal client term.\n"
                "    evidence: proof:fixture-formal\n"
            ),
        ))

    def init_git_and_publications(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.brain)], check=True)
        subprocess.run(["git", "-C", str(self.brain), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.brain), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
        BusinessBrainGraphService(graphify_root=self.graph, vault_root=self.brain, registry=self.registry).build()
        old = (aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT, aos_indexer.INGEST_CONFIG_PATH)
        aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT, aos_indexer.INGEST_CONFIG_PATH = self.root, self.brain, self.root / "queue/ingest_watch.json"
        try:
            result = aos_indexer.scan(self.db, roots=[self.root, self.brain], registry=self.registry)
            if result["status"] != "success":
                raise AssertionError(result)
        finally:
            aos_indexer.LIVE_ROOT, aos_indexer.BUSINESS_BRAIN_ROOT, aos_indexer.INGEST_CONFIG_PATH = old


class ContextAssemblerV2Tests(unittest.TestCase):
    def test_relationship_episodic_loop_commitment_and_two_client_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = StepFixture(Path(temp))
            fixture.init_git_and_publications()
            service = BusinessBrainGraphService(graphify_root=fixture.graph, vault_root=fixture.brain, registry=fixture.registry)
            context = context_assembler.assemble(
                "For AOS-2026-9001, explain the relationship, recent outcome, open loop, and current commitment.",
                surface="test", client_scope="client-a", write_artifact=False,
                root=fixture.root, vault_root=fixture.brain, registry=fixture.registry,
                graph_service=service, search_db_path=fixture.db,
            )
            rendered = context.render()
            for sentinel in ("CLIENT-A-GRAPH-SENTINEL", "CLIENT-A-SESSION-SENTINEL", "CLIENT-A-LOOP-SENTINEL", "CLIENT-A-COMMITMENT-SENTINEL"):
                self.assertIn(sentinel, rendered)
            self.assertNotIn("CLIENT-B-", rendered)
            manifest = context.manifest()
            self.assertEqual(manifest["assembler_version"], 2)
            self.assertFalse(manifest["whole_vault_default"])
            self.assertEqual(manifest["source_discovery_token_usage"], {"model_invocations": 0, "input_tokens": 0, "output_tokens": 0})
            graph_reads = [row for row in manifest["actual_reads"] if row["retrieval_route"] == "graphify"]
            self.assertEqual([row["identity"] for row in graph_reads], ["business_brain:prospects/client-a.md"])
            self.assertLessEqual(len(manifest["actual_reads"]), 9)

    def test_exact_search_is_scope_filtered_before_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = StepFixture(Path(temp))
            fixture.init_git_and_publications()
            block = context_assembler._scoped_note_block(
                "CLIENT-A-BRAIN-SENTINEL exact isolation phrase",
                classification="knowledge_sensitive", client_scope="client-a",
                vault_root=fixture.brain, registry=fixture.registry,
                graph_service=None, search_db_path=fixture.db,
            )
            self.assertIn("CLIENT-A-BRAIN-SENTINEL", block.content)
            self.assertNotIn("CLIENT-B-BRAIN-SENTINEL", block.content)
            self.assertEqual([read.retrieval_route for read in block.actual_reads], ["search"])


class NightlyHygieneTests(unittest.TestCase):
    def fixture(self, base: Path) -> StepFixture:
        fixture = StepFixture(base)
        fixture.add_learning_session()
        fixture.init_git_and_publications()
        return fixture

    def run_fixture(self, fixture: StepFixture, **kwargs):
        return nightly_knowledge_hygiene.run(
            root=fixture.root, brain_root=fixture.brain, graphify_root=fixture.graph,
            search_db_path=fixture.db, registry=fixture.registry, **kwargs,
        )

    def test_dry_run_real_fold_commit_graph_search_and_idempotent_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = self.fixture(Path(temp))
            before = hashes(fixture.brain)
            dry = self.run_fixture(fixture, dry_run=True)
            self.assertEqual(dry["status"], "dry_run")
            self.assertFalse(dry["mutated"])
            self.assertEqual(hashes(fixture.brain), before)
            self.assertEqual(dry["plan"]["changed_paths"], ["memory/global.md", "operating_context/executive_view.md"])
            self.assertEqual(len(dry["plan"]["deferred_formal_commitments"]), 1)

            result = self.run_fixture(fixture)
            self.assertEqual(result["status"], "changed")
            self.assertTrue(result["commit"])
            self.assertEqual(result["changed_paths"], ["memory/global.md", "operating_context/executive_view.md"])
            self.assertIn("The fixture durable fact is verified.", (fixture.brain / "memory/global.md").read_text())
            self.assertIn("The verified fact changes the fixture priority.", (fixture.brain / "operating_context/executive_view.md").read_text())
            self.assertNotIn("Commit to a formal client term.", (fixture.brain / "memory/global.md").read_text())
            self.assertEqual(BusinessBrainGraphService(graphify_root=fixture.graph, vault_root=fixture.brain, registry=fixture.registry).status()["state"], "fresh")
            author = subprocess.check_output(["git", "-C", str(fixture.brain), "show", "-s", "--format=%an <%ae>", "HEAD"], text=True).strip()
            self.assertEqual(author, "Hermes <hermes@local.ttros>")

            rerun = self.run_fixture(fixture)
            self.assertEqual(rerun["status"], "unchanged")
            self.assertFalse(rerun["mutated"])
            self.assertIsNone(rerun["commit"])
            self.assertEqual(subprocess.check_output(["git", "-C", str(fixture.brain), "rev-list", "--count", "HEAD"], text=True).strip(), "2")

    def test_closed_release_gate_requires_pass_proof_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            proof = root / nightly_knowledge_hygiene.REVENUE_GATE_PROOF
            write(proof, "# Revenue Gate\n\nVerdict: pending\n")
            original = note(
                "fixture-loops", "Open Loops",
                "## One Brain release\n\n- Revenue Gate must prove restart recall, automatic canonical/activity retrieval, and zero external action before Step 4.",
                note_type="operating_context",
            )
            unchanged, records = nightly_knowledge_hygiene._reconcile_closed_release_gate(original, root=root)
            self.assertEqual((unchanged, records), (original, []))
            write(proof, "# Revenue Gate\n\nVerdict: **PASS** for Steps 0–3 and the Revenue Gate.\n")
            updated, records = nightly_knowledge_hygiene._reconcile_closed_release_gate(original, root=root)
            self.assertEqual(len(records), 1)
            self.assertIn("- None.", updated)
            self.assertIn("Resolved architecture release gates", updated)
            rerun, rerun_records = nightly_knowledge_hygiene._reconcile_closed_release_gate(updated, root=root)
            self.assertEqual((rerun, rerun_records), (updated, []))

    def test_expected_hash_write_and_provenance_failures_roll_back(self) -> None:
        for injection in ("expected_hash", "write", "provenance"):
            with self.subTest(injection=injection), tempfile.TemporaryDirectory() as temp:
                fixture = self.fixture(Path(temp))
                before_files = hashes(fixture.brain)
                before_head = subprocess.check_output(["git", "-C", str(fixture.brain), "rev-parse", "HEAD"], text=True).strip()
                service = BusinessBrainGraphService(graphify_root=fixture.graph, vault_root=fixture.brain, registry=fixture.registry)
                graph_before = service._artifact_hashes(service.published)
                with self.assertRaises(Exception):
                    self.run_fixture(fixture, failure_injection=injection)
                self.assertEqual(hashes(fixture.brain), before_files)
                self.assertEqual(subprocess.check_output(["git", "-C", str(fixture.brain), "rev-parse", "HEAD"], text=True).strip(), before_head)
                self.assertEqual(service._artifact_hashes(service.published), graph_before)

    def test_graphify_reindex_and_validation_failures_preserve_all_publications(self) -> None:
        for injection in ("graphify", "reindex", "validation"):
            with self.subTest(injection=injection), tempfile.TemporaryDirectory() as temp:
                fixture = self.fixture(Path(temp))
                before_files = hashes(fixture.brain)
                service = BusinessBrainGraphService(graphify_root=fixture.graph, vault_root=fixture.brain, registry=fixture.registry)
                graph_before = service._artifact_hashes(service.published)
                search_before = hashlib.sha256(fixture.db.read_bytes()).hexdigest()
                with self.assertRaises(Exception):
                    self.run_fixture(fixture, failure_injection=injection)
                self.assertEqual(hashes(fixture.brain), before_files)
                self.assertEqual(service._artifact_hashes(service.published), graph_before)
                self.assertEqual(hashlib.sha256(fixture.db.read_bytes()).hexdigest(), search_before)
                self.assertEqual(service.status()["state"], "fresh")


if __name__ == "__main__":
    unittest.main()
