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
from unittest import mock

import yaml

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


def historical_source_record(source_id: str, raw_text: str, *, kind: str = "call_transcript",
                              participants: str = "Liam Duff; Fixture Person", date_text: str = "unavailable") -> tuple[str, str]:
    digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    text = (
        "---\n"
        f"id: historical-source-{digest[:16]}\n"
        "type: historical_source\n"
        "status: evidence_only\n"
        "canonical_truth: false\n"
        f"source_document_kind: {kind}\n"
        f'original_filename: "{source_id}.txt"\n'
        f"source_sha256: {digest}\n"
        f"source_size_bytes: {len(raw_text.encode('utf-8'))}\n"
        'source_mime_type: "text/plain"\n'
        f'source_date_text: "{date_text}"\n'
        f'participants_text: "{participants}"\n'
        "---\n"
        f"# Historical source — {source_id}\n\n"
        f"<!-- TTROS:VERBATIM_SOURCE:BEGIN:{digest} -->\n{raw_text}<!-- TTROS:VERBATIM_SOURCE:END:{digest} -->\n"
    )
    return text, digest


HISTORICAL_INDEX_FIXTURE = (
    "---\nid: fixture-historical-calls-index\ntype: index\n---\n"
    "# Historical Calls — Records Index\n\n"
    "> fixture intro.\n\n"
    "## Historical records\n\n"
    "| Source | Date text | Participants / attribution | Kind | Exact record |\n|---|---|---|---|---|\n"
    "| Fixture | unavailable | Fixture | call_transcript | [[sources/historical_calls/fixture-call|source]] |\n\n"
    "## Elsewhere\n\n[[index/MEMORY_INDEX|Memory Index]]\n"
)


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

    def test_capture_trailing_whitespace_source_commits_cleanly_and_preserves_exact_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, brain, graph, _registry = self.fixture(root)
            raw = (
                b"# Fixture trailing whitespace 2026-09-09\n\n"
                b"Line one has trailing spaces.   \n"
                b"Line two has a trailing tab.\t\n"
                b"Line three is clean.\n"
                b"   \n"
                b"Line five follows a whitespace-only line.\n"
            )
            source = root / "input" / "fixture-trailing-ws.txt"
            write(source, raw)
            result = run_intake(
                source, repo_root=repo, brain_root=brain,
                registry_path=repo / "context/client_scope_registry.json",
                schema_path=ROOT / "context/client_scope_registry.schema.json",
                search_db=repo / "search/os_index.db", graphify_root=graph,
                commit=True, now=lambda: NOW,
            )
            self.assertEqual((result.scanned, result.imported, result.duplicates), (1, 1, 0))
            self.assertEqual(result.model_invocations, 0)
            self.assertTrue(result.retrieval_ready)
            self.assertIsNotNone(result.brain_commit)

            pointer = result.imported_pointers[0]
            record_path = brain / pointer.removeprefix("business_brain:")
            record_text = record_path.read_text(encoding="utf-8")

            # Requirement 1: exact original bytes and sha256 remain preserved unchanged.
            exact = extract_exact_bytes(record_text)
            self.assertEqual(exact, raw)
            self.assertEqual(hashlib.sha256(exact).hexdigest(), hashlib.sha256(raw).hexdigest())

            # Requirement 2: the derived searchable text carries no trailing whitespace on
            # any line -- the exact condition `git diff --cached --check` rejects, and the
            # real cause of the pre-fix failure against a real trailing-whitespace source.
            searchable = record_text.split("## Searchable source text\n\n", 1)[1].split(
                "\n\n## Exact source bytes", 1
            )[0]
            for line in searchable.splitlines():
                self.assertEqual(line, line.rstrip(), f"trailing whitespace survived: {line!r}")
            # Semantic content is unchanged -- only trailing whitespace differs.
            self.assertIn("Line one has trailing spaces.", searchable)
            self.assertIn("Line two has a trailing tab.", searchable)

            # Requirement 3: the normal run_intake() path completed for real, including the
            # real `git diff --cached --check` inside write_transaction (commit=True, no
            # mocking) -- had it failed, run_intake would have raised and this test would
            # have failed on the call above, not here.
            log = subprocess.run(
                ["git", "-C", str(brain), "log", "--format=%H", "-1"],
                capture_output=True, text=True, check=True,
            )
            self.assertEqual(log.stdout.strip(), result.brain_commit)

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

    def test_semantic_extraction_backfill_writes_card_and_claim_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, brain, graph, _registry = self.fixture(root)
            registry_path = repo / "context/client_scope_registry.json"
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            g = data["scopes"]["global"]
            g["brain_pointer_prefixes"].append("business_brain:sources/historical_calls/cards/")
            g["search_source_identities"].append({"source": "business_brain", "path_prefix": "business_brain:sources/historical_calls/cards/"})
            g["graphify_targets"][0]["paths"].extend([
                "business_brain:sources/historical_calls/cards/fixture-call.card.md",
                "business_brain:sources/historical_calls/INDEX.md",
            ])
            write(registry_path, json.dumps(data, indent=2) + "\n")

            raw_text = "Fixture Person\nWe should try the pilot next month.\n\nYou\nAgreed, let's do it.\n"
            record_text, _digest = historical_source_record("fixture-call", raw_text)
            write(brain / "sources/historical_calls/fixture-call.md", record_text)
            write(brain / "sources/historical_calls/INDEX.md", HISTORICAL_INDEX_FIXTURE)

            payload = {
                "claims": [
                    {
                        "claim": "Fixture Person proposed starting the pilot next month.",
                        "type": "advice_received", "attribution": "Fixture Person", "status": "historical",
                        "evidence": {"quote": "We should try the pilot next month.", "locator": "Fixture Person's first turn"},
                    },
                    {
                        "claim": "This one has a fabricated quote and must be dropped.",
                        "type": "fact_asserted", "attribution": "Fixture Person", "status": "historical",
                        "evidence": {"quote": "This text is not in the source at all.", "locator": "nowhere"},
                    },
                ],
                "card": {
                    "one_line_description": "Fixture call about a pilot",
                    "summary": "A short fixture summary of the call.",
                    "key_topics": ["pilot"],
                    "who_said_what": ["Fixture Person — proposed the pilot"],
                    "decisions": ["none recorded"],
                    "advice_and_opinions": ["Fixture Person suggested trying the pilot"],
                    "liam_positions": [], "commitments_and_actions": ["Agreed to do the pilot"],
                    "open_questions": [], "conflicts_and_caveats": [], "promotion_candidates": [],
                },
            }
            completed = subprocess.CompletedProcess(["hermes"], 0, json.dumps(payload), "")
            real_run = subprocess.run

            def fake_run(cmd, *args, **kwargs):
                # Only intercept the hermes extraction call -- graphify's own real
                # subprocess.run (invoked later, inside the same write_transaction) must
                # still run for real, since subprocess.run is one shared module-level
                # attribute and mock.patch on it is process-global, not call-site-scoped.
                if cmd and cmd[0] == "hermes":
                    return completed
                return real_run(cmd, *args, **kwargs)

            with mock.patch("tools.source_intake_semantic.subprocess.run", side_effect=fake_run) as run_mock:
                result = run_intake(
                    brain / "sources/historical_calls/fixture-call.md", repo_root=repo, brain_root=brain,
                    registry_path=registry_path, schema_path=ROOT / "context/client_scope_registry.schema.json",
                    search_db=repo / "search/os_index.db", graphify_root=graph,
                    mode="semantic", commit=False, now=lambda: NOW,
                )
            hermes_calls = [call for call in run_mock.call_args_list if call.args[0] and call.args[0][0] == "hermes"]
            self.assertEqual(len(hermes_calls), 1)
            self.assertEqual(result.model_invocations, 1)
            self.assertTrue(result.semantic_requested)
            self.assertEqual((result.scanned, result.imported, result.duplicates), (1, 2, 0))
            card_path = brain / "sources/historical_calls/cards/fixture-call.card.md"
            claim_path = repo / "queue/receipts/source_intake/claims/historical/fixture-call.claims.yaml"
            old_style_claim_path = brain / "sources/historical_calls/claims/fixture-call.md"
            self.assertTrue(card_path.is_file())
            self.assertTrue(claim_path.is_file())
            self.assertFalse(old_style_claim_path.exists())
            self.assertLessEqual(len(card_path.read_bytes()), 3000)
            card_text = card_path.read_text(encoding="utf-8")
            self.assertIn('canonical_truth: false', card_text)
            self.assertIn("queue/receipts/source_intake/claims/historical/fixture-call.claims.yaml", card_text)
            claim_text = claim_path.read_text(encoding="utf-8")
            self.assertIn("claim_count: 1", claim_text)
            self.assertIn("dropped_count: 1", claim_text)
            self.assertIn("does not resolve as an exact substring", claim_text)
            claim_document = yaml.safe_load(claim_text)
            self.assertEqual(claim_document["claim_count"], 1)
            self.assertEqual(len(claim_document["claims"]), 1)
            self.assertEqual(len(claim_document["dropped"]), 1)
            # Not indexable at all -- .claims.yaml is not in aos_indexer.INDEXABLE_EXTENSIONS,
            # and it is not registered under any brain_pointer/search_source_identity.
            self.assertIsNone(aos_indexer.document_from_path(claim_path))
            index_text = (brain / "sources/historical_calls/INDEX.md").read_text(encoding="utf-8")
            self.assertIn("Fixture call about a pilot", index_text)
            self.assertIn("[[sources/historical_calls/cards/fixture-call.card|card]]", index_text)
            self.assertIn("fixture intro.", index_text)  # preserved, not replaced

            with mock.patch("tools.source_intake_semantic.subprocess.run", return_value=completed) as run_mock_2:
                rerun = run_intake(
                    brain / "sources/historical_calls/fixture-call.md", repo_root=repo, brain_root=brain,
                    registry_path=registry_path, schema_path=ROOT / "context/client_scope_registry.schema.json",
                    search_db=repo / "search/os_index.db", graphify_root=graph,
                    mode="semantic", commit=False, now=lambda: NOW,
                )
            run_mock_2.assert_not_called()
            self.assertEqual(rerun.model_invocations, 0)
            self.assertEqual((rerun.imported, rerun.duplicates), (0, 1))

    def test_production_capture_source_feeds_semantic_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, brain, graph, _registry = self.fixture(root)
            registry_path = repo / "context/client_scope_registry.json"

            raw = (
                b"Fixture Person\n"
                b"We should try the pilot next month.   \n"
                b"\n"
                b"You\n"
                b"Agreed, let's do it.\n"
            )
            source_id = hashlib.sha256(raw).hexdigest()
            # Production-shape cards live under sources/intake/cards/ -- a
            # separate tree from the legacy sources/historical_calls/cards/
            # one -- and production intake must never mutate the
            # historical-only navigation index (STEP I2, 2026-09-10 repair).
            card_relative = f"sources/intake/cards/{source_id}.card.md"

            data = json.loads(registry_path.read_text(encoding="utf-8"))
            g = data["scopes"]["global"]
            g["brain_pointer_prefixes"].append("business_brain:sources/intake/cards/")
            g["search_source_identities"].append({"source": "business_brain", "path_prefix": "business_brain:sources/intake/cards/"})
            write(registry_path, json.dumps(data, indent=2) + "\n")
            write(brain / "sources/historical_calls/INDEX.md", HISTORICAL_INDEX_FIXTURE)
            historical_index_before = (brain / "sources/historical_calls/INDEX.md").read_text(encoding="utf-8")

            source = root / "input" / "fixture-production-call.txt"
            write(source, raw)

            # Part 1: real, unmocked production capture -- the same path STEP I2's
            # nominated fresh source went through, producing a `type: source` /
            # TTROS:SOURCE-BYTES record (not the legacy historical_source shape).
            capture = run_intake(
                source, repo_root=repo, brain_root=brain,
                registry_path=registry_path, schema_path=ROOT / "context/client_scope_registry.schema.json",
                search_db=repo / "search/os_index.db", graphify_root=graph,
                commit=False, now=lambda: NOW,
            )
            self.assertEqual((capture.scanned, capture.imported, capture.duplicates), (1, 1, 0))
            self.assertEqual(capture.model_invocations, 0)
            record_pointer = capture.imported_pointers[0]
            record_path = brain / record_pointer.removeprefix("business_brain:")
            record_text_before = record_path.read_text(encoding="utf-8")
            self.assertIn("type: source\n", record_text_before)
            self.assertEqual(record_path.stem, source_id)

            payload = {
                "claims": [{
                    "claim": "Fixture Person proposed starting the pilot next month.",
                    "type": "advice_received", "attribution": "Fixture Person", "status": "historical",
                    "evidence": {"quote": "We should try the pilot next month.", "locator": "Fixture Person's first turn"},
                }],
                "card": {
                    "one_line_description": "Fixture production call about a pilot",
                    "summary": "A short fixture summary of the production-captured call.",
                    "key_topics": ["pilot"], "who_said_what": ["Fixture Person — proposed the pilot"],
                    "decisions": [], "advice_and_opinions": ["Fixture Person suggested trying the pilot"],
                    "liam_positions": [], "commitments_and_actions": ["Agreed to do the pilot"],
                    "open_questions": [], "conflicts_and_caveats": [], "promotion_candidates": [],
                },
            }
            completed = subprocess.CompletedProcess(["hermes"], 0, json.dumps(payload), "")
            real_run = subprocess.run
            prompts: list[str] = []

            def fake_run(cmd, *args, **kwargs):
                if cmd and cmd[0] == "hermes":
                    prompts.append(cmd[cmd.index("-z") + 1])
                    return completed
                return real_run(cmd, *args, **kwargs)

            # Part 2: point semantic mode directly at capture mode's own output --
            # the chain STEP I2 found had never been exercised before this fix.
            with mock.patch("tools.source_intake_semantic.subprocess.run", side_effect=fake_run) as run_mock:
                result = run_intake(
                    record_path, repo_root=repo, brain_root=brain,
                    registry_path=registry_path, schema_path=ROOT / "context/client_scope_registry.schema.json",
                    search_db=repo / "search/os_index.db", graphify_root=graph,
                    mode="semantic", commit=False, now=lambda: NOW,
                )
            hermes_calls = [call for call in run_mock.call_args_list if call.args[0] and call.args[0][0] == "hermes"]
            self.assertEqual(len(hermes_calls), 1)
            self.assertEqual(result.model_invocations, 1)
            self.assertEqual((result.scanned, result.imported, result.duplicates), (1, 2, 0))

            # The body sent for extraction is the exact original text (trailing
            # whitespace intact), not the trailing-whitespace-stripped "Searchable
            # source text" rendering that FTS actually uses.
            self.assertIn("We should try the pilot next month.   \n", prompts[0])

            card_path = brain / card_relative
            claim_path = repo / f"queue/receipts/source_intake/claims/{source_id}.claims.yaml"
            self.assertTrue(card_path.is_file())
            self.assertTrue(claim_path.is_file())
            card_text = card_path.read_text(encoding="utf-8")
            self.assertIn("canonical_truth: false", card_text)
            claim_document = yaml.safe_load(claim_path.read_text(encoding="utf-8"))
            self.assertEqual(claim_document["claim_count"], 1)
            self.assertEqual(claim_document["dropped_count"], 0)
            # Not indexable and not a brain_pointer, same guarantee as the
            # historical_source claim receipt.
            self.assertIsNone(aos_indexer.document_from_path(claim_path))

            # The card's "Original" link must resolve to where the production
            # capture record actually lives (sources/intake/records/<sha256>),
            # not the legacy sources/historical_calls/<slug> location.
            original_link = f"sources/intake/records/{source_id}"
            self.assertIn(f"[[{original_link}|source]]", card_text)
            self.assertTrue((brain / f"{original_link}.md").is_file())

            # Production intake must not mutate the historical-only navigation
            # index -- it is a curated table over the pre-existing
            # historical_source imports, not a general card registry.
            historical_index_after = (brain / "sources/historical_calls/INDEX.md").read_text(encoding="utf-8")
            self.assertEqual(historical_index_after, historical_index_before)
            self.assertNotIn(source_id, historical_index_after)
            self.assertFalse((brain / f"sources/historical_calls/cards/{source_id}.card.md").exists())

            # Requirement: no re-preservation of the original -- the capture
            # record is byte-identical to before semantic mode ran, and it
            # remains the only record under sources/intake/records/.
            self.assertEqual(record_path.read_text(encoding="utf-8"), record_text_before)
            self.assertEqual(extract_exact_bytes(record_text_before), raw)
            self.assertEqual(len(list((brain / "sources/intake/records").glob("*.md"))), 1)

    def test_extract_verbatim_source_rejects_unknown_type(self):
        from tools.source_intake_semantic import SemanticExtractionError, extract_verbatim_source
        # Negative-case rehearsal for the type dispatch this step added: neither
        # accepted shape's marker is present, and the record's own `type` field
        # names neither accepted value -- must be refused, not silently coerced.
        with self.assertRaisesRegex(SemanticExtractionError, "historical_source or type: source"):
            extract_verbatim_source("---\ntype: something_else\n---\nbody\n")

    def test_semantic_extraction_budget_hard_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, brain, graph, _registry = self.fixture(root)
            registry_path = repo / "context/client_scope_registry.json"
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            g = data["scopes"]["global"]
            g["brain_pointer_prefixes"].append("business_brain:sources/historical_calls/cards/")
            g["search_source_identities"].append({"source": "business_brain", "path_prefix": "business_brain:sources/historical_calls/cards/"})
            write(registry_path, json.dumps(data, indent=2) + "\n")
            raw_text = "Fixture Person\nHello there.\n"
            record_text, _digest = historical_source_record("fixture-call", raw_text)
            write(brain / "sources/historical_calls/fixture-call.md", record_text)
            write(brain / "sources/historical_calls/INDEX.md", HISTORICAL_INDEX_FIXTURE)

            from tools import source_intake_semantic as sis
            budget = sis.ModelCallBudget(maximum=0)
            with self.assertRaisesRegex(Exception, "budget exceeded"):
                run_intake(
                    brain / "sources/historical_calls/fixture-call.md", repo_root=repo, brain_root=brain,
                    registry_path=registry_path, schema_path=ROOT / "context/client_scope_registry.schema.json",
                    search_db=repo / "search/os_index.db", graphify_root=graph,
                    mode="semantic", commit=False, now=lambda: NOW, semantic_budget=budget,
                )
            self.assertFalse((brain / "sources/historical_calls/cards/fixture-call.card.md").exists())

    def test_david_capability_matching_finds_source_intake(self):
        block = context_assembler._matching_workflows_block(
            "Import these transcripts as historical business context"
        )
        self.assertIn("source-intake/SKILL.md", block.content)
        self.assertIn("CAPTURE (DEFAULT)", block.content)


if __name__ == "__main__":
    unittest.main()
