"""Focused One Brain transaction and mandatory-context regression tests.

Revisit: when the One Brain binding or Context Assembler contract changes. · Last touched: 2026-08-04.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import brain_memory
from tools import context_assembler


NOTE = """---
id: prospect-test
type: prospect
status: active
human_field: keep-me
---
# Human title

Human-authored paragraph.
"""


class BrainTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.vault)], check=True)
        (self.vault / "prospects").mkdir()
        (self.vault / "memory").mkdir()
        (self.vault / "operating_context").mkdir()
        (self.vault / "inbox").mkdir()
        (self.vault / "prospects/test.md").write_text(NOTE, encoding="utf-8")
        for relative in (
            "memory/company.md",
            "operating_context/current_priorities.md",
            "operating_context/executive_view.md",
            "operating_context/open_loops.md",
            "inbox/contradictions.md",
        ):
            (self.vault / relative).write_text(NOTE, encoding="utf-8")
        subprocess.run(["git", "-C", str(self.vault), "add", "."], check=True)
        subprocess.run([
            "git", "-C", str(self.vault), "-c", "user.name=Fixture", "-c",
            "user.email=fixture@example.invalid", "commit", "-qm", "fixture",
        ], check=True)
        self.patch = mock.patch.object(brain_memory, "VAULT_ROOT", self.vault)
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.temp.cleanup()

    def test_atomic_managed_update_preserves_human_content_and_commits_exact_path(self) -> None:
        result = brain_memory.update_note_section(
            "prospects/test.md", section_id="correction", title="Operator correction",
            content="Knowledge state: `operator_correction`\n\nCorrected value.",
            source="test", session_id="session-test",
        )
        text = (self.vault / "prospects/test.md").read_text(encoding="utf-8")
        self.assertIn("human_field: keep-me", text)
        self.assertIn("Human-authored paragraph.", text)
        self.assertIn("TTROS:HERMES:correction:BEGIN", text)
        self.assertEqual(result.changed_paths, ("prospects/test.md",))
        self.assertTrue(result.commit)
        author = subprocess.check_output([
            "git", "-C", str(self.vault), "show", "-s", "--format=%an <%ae>", "HEAD"
        ], text=True).strip()
        self.assertEqual(author, "Hermes <hermes@local.ttros>")

    def test_invalid_candidate_never_replaces_source(self) -> None:
        before = (self.vault / "prospects/test.md").read_bytes()
        with self.assertRaises(brain_memory.BrainMemoryError):
            brain_memory.write_transaction(
                {"prospects/test.md": "# missing frontmatter\n"},
                source="test", session_id="invalid",
            )
        self.assertEqual((self.vault / "prospects/test.md").read_bytes(), before)

    def test_stale_expected_hash_preserves_concurrent_edit(self) -> None:
        path = self.vault / "prospects/test.md"
        stale = brain_memory.file_sha256(path)
        path.write_text(NOTE + "\nConcurrent Obsidian edit.\n", encoding="utf-8")
        with self.assertRaises(brain_memory.ConcurrentEditError):
            brain_memory.write_transaction(
                {"prospects/test.md": NOTE + "\nHermes overwrite.\n"},
                source="test", session_id="concurrent",
                expected_hashes={"prospects/test.md": stale},
            )
        self.assertIn("Concurrent Obsidian edit.", path.read_text(encoding="utf-8"))

    def test_ordinary_pointer_forms_normalize_to_one_contained_target(self) -> None:
        absolute = self.vault / "memory/company.md"
        for pointer in (
            "business_brain:memory/company.md",
            "memory/company.md",
            "company",
            str(absolute),
        ):
            self.assertEqual(brain_memory.resolve_ordinary_knowledge_pointer(pointer), "memory/company.md")

    def test_ordinary_pointer_rejects_traversal_and_outside_vault(self) -> None:
        for pointer in (
            "business_brain:../memory/company.md",
            "memory/../company.md",
            str(self.vault.parent / "company.md"),
            "business_brain:_backups/company.md",
        ):
            with self.subTest(pointer=pointer), self.assertRaises(brain_memory.BrainMemoryError):
                brain_memory.resolve_ordinary_knowledge_pointer(pointer)


class ContextAssemblerTests(unittest.TestCase):
    def test_matching_workflow_projection_keeps_selection_order_and_full_behavior_contract(self) -> None:
        block = context_assembler._matching_workflows_block("all and call liam live per work working")

        self.assertEqual(
            [source.split("#sha256=", 1)[0] for source in block.sources],
            [
                "fit_call_prep/workflow.md",
                "ai_operations_support/workflow.md",
                "aoa_working_session/SKILL.md",
                "fit_call_prep/SKILL.md",
            ],
        )
        self.assertIn("Selected 4/29; order preserved", block.content)
        self.assertIn("READ_SOURCE is the exact retrieved repo file", block.content)
        self.assertNotIn("Not loaded:", block.content)
        self.assertNotIn("> Revisit:", block.content)
        self.assertNotIn("lane: revenue", block.content)
        self.assertLess(block.byte_count, 8_000)

        # Identity, purpose, applicability, inputs, operative process, completion,
        # verification, boundaries, evidence/receipt, and exact retrieval route.
        for required in (
            "1. READ_SOURCE=fit_call_prep/workflow.md · relevance=",
            "route=repo_exact_file · id=fit_call_prep",
            "declared_skill_target=skills/fit_call_prep/SKILL.md",
            "declared_workflow_target=workflows/fit_call_prep/workflow.md",
            "PURPOSE: run a Fit Call prep for one named prospect",
            "APPLY:\nQueue item exists",
            "REQUIRES:\n- Prospect name, company, website/socials",
            "Research — public signals only",
            "COMPLETE:\n- Done = one-page brief artifact",
            "VERIFY:\nBrief exists, every research claim sourced",
            "BOUNDARIES:\n- Contact the prospect or touch their systems.",
            "Write receipt to receipts/ with token breakdown",
            "2. READ_SOURCE=ai_operations_support/workflow.md · relevance=",
            "both sessions supported per the skill's monthly cycle",
            "3. READ_SOURCE=aoa_working_session/SKILL.md · relevance=",
            "Audit — map the current workflow",
            "notes, takeaways, actions, and hub update exist within 24h",
            "4. READ_SOURCE=fit_call_prep/SKILL.md · relevance=",
            "apply=A System Fit Call is booked",
            "Update prospect entity page with research only (facts, sourced)",
        ):
            with self.subTest(required=required):
                self.assertIn(required, block.content)

    def test_compact_david_provenance_keeps_audit_evidence_without_model_hashes_or_duplicate_reads(self) -> None:
        digest = "a" * 64
        read = context_assembler.ActualRead(
            "business_brain:memory/company.md", "pointer", "global", digest,
        )
        selected = context_assembler.ContextBlock(
            "identity/company",
            "Fixture company.",
            (
                f"business_brain:memory/company.md#sha256={digest}#route=pointer",
                f"context/MORNING_BRIEF_FINDINGS.json#sha256={digest}",
            ),
            actual_reads=(read,),
        )

        provenance = context_assembler._provenance_block((selected,), compact=True)

        self.assertEqual(provenance.sources, selected.sources)
        self.assertEqual(selected.actual_reads, (read,))
        self.assertEqual(
            provenance.content,
            "\n".join((
                "- identity/company: business_brain:memory/company.md · route=pointer",
                "- identity/company: context/MORNING_BRIEF_FINDINGS.json",
            )),
        )
        self.assertNotIn("sha256=", provenance.content)
        self.assertNotIn("actual-read:", provenance.content)

        full = context_assembler._provenance_block((selected,))
        self.assertIn(f"sha256={digest}", full.content)
        self.assertIn("actual-read:", full.content)

        with mock.patch.object(context_assembler, "_deterministic_morning_brief", return_value=selected):
            david = context_assembler.assemble(
                "Run the Python unit tests.", surface="test", profile="david",
                classification="technical_only", write_artifact=False,
            )
            other = context_assembler.assemble(
                "Run the Python unit tests.", surface="test", profile="operator-lean",
                classification="technical_only", write_artifact=False,
            )
        self.assertNotIn(f"sha256={digest}", david.blocks[-1].content)
        self.assertIn(f"sha256={digest}", other.blocks[-1].content)

    def test_raw_prompt_is_rejected_at_model_boundary(self) -> None:
        with self.assertRaises(TypeError):
            context_assembler.require_assembled_context("raw prompt")

    def test_technical_only_has_explicit_na_and_visible_counts(self) -> None:
        context = context_assembler.assemble(
            "Run the Python unit tests for this repository module.",
            surface="test", classification="technical_only", write_artifact=False,
        )
        self.assertEqual(context.classification, "technical_only")
        self.assertTrue(all(block.byte_count >= 0 and block.token_count >= 0 for block in context.blocks))
        self.assertIn("N/A — genuinely technical-only", context.render())

    def test_revenue_entities_and_activity_are_selected_automatically(self) -> None:
        context = context_assembler.assemble(
            "Who are Loretta Davis and Evan Thompson, and what follow-up is owed?",
            surface="test", write_artifact=False,
        )
        provenance = "\n".join(context.provenance).casefold()
        self.assertIn("loretta-davis", provenance)
        self.assertIn("evan-thompson", provenance)
        self.assertIn("aos-2026-0174", provenance)
        self.assertIn("aos-2026-0175", provenance)

    def test_sticky_anaphora_reselects_canonical_notes_and_activity(self) -> None:
        durable = context_assembler.ContextBlock(
            "conversation summary",
            "We discussed Loretta Davis AOS-2026-0174 and Evan Thompson AOS-2026-0175.",
            ("business_brain:sessions/fixture.md#sha256=fixture",),
            False,
            "durable sticky session",
        )
        with mock.patch.object(context_assembler, "_conversation_block", return_value=durable):
            context = context_assembler.assemble(
                "After the backend restart, identify the two prospects we discussed.",
                surface="hermes:cli", session_key="fixture", write_artifact=False,
            )
        provenance = "\n".join(context.provenance).casefold()
        self.assertEqual(context.classification, "knowledge_sensitive")
        self.assertIn("loretta-davis", provenance)
        self.assertIn("evan-thompson", provenance)
        self.assertIn("aos-2026-0174", provenance)
        self.assertIn("aos-2026-0175", provenance)

    def test_worker_pack_is_fresh_and_excludes_wholesale_executive_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(context_assembler, "PACK_DIR", Path(tmp)):
                context, path = context_assembler.worker_context_pack({
                    "id": "AOS-2026-9999", "title": "Prepare local follow-up plan",
                    "context": "Loretta Davis and Evan Thompson; draft only.",
                    "sources": ["business_brain:prospects/2026-07-talent-harbour-loretta-davis.md"],
                    "definition_of_done": "A useful no-send call plan.",
                }, owner="revenue", execution_instructions="Write a local artifact.")
            content = path.read_text(encoding="utf-8")
            self.assertIn("Fresh task-scoped session: yes", content)
            self.assertIn("Hermes transcript included wholesale: no", content)
            self.assertIn(context.marker, content)


if __name__ == "__main__":
    unittest.main()
