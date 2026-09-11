"""STEP T8-BCD: open_note pointer resolution + bounded intake-passage retrieval.

Covers the card-pointer -> bounded-passage lever added to
tools/brain_memory_mcp.py::open_note -- pointer normalization (bare/prefixed,
with/without .md) and the query-scoped bounded excerpt that keeps a result
well under Hermes's MCP tool-result spill threshold.

Skipped where the `mcp` package (Hermes's own venv) isn't installed --
brain_memory_mcp.py imports it unconditionally at module scope.

Revisit: when open_note's pointer/query contract changes. · Last touched: 2026-09-10.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

pytest.importorskip("mcp.server.mcpserver")

from tools import brain_memory
from tools import brain_memory_mcp as bmm


RECORD_ID = "abc123fake0000000000000000000000000000000000000000000000000000"
RECORD_TEXT = (
    "---\n"
    "id: source-intake-abc123\n"
    "type: source\n"
    "status: historical-evidence\n"
    "---\n"
    "# Fixture meeting\n\n"
    "## Searchable source text\n\n"
    "Speaker: Small talk about the weather.\n"
    "Speaker: More small talk about the weather.\n"
    "Speaker: Even more filler about the weather today.\n"
    "Speaker: The exact number of widgets in the warehouse is forty-two.\n"
    "Speaker: Back to talking about the weather again.\n"
)


class OpenNoteIntakePassageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.vault)], check=True)
        (self.vault / "sources" / "intake" / "records").mkdir(parents=True)
        (self.vault / "sources" / "intake" / "records" / f"{RECORD_ID}.md").write_text(
            RECORD_TEXT, encoding="utf-8"
        )
        self.patch = mock.patch.object(brain_memory, "VAULT_ROOT", self.vault)
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.temp.cleanup()

    # -- pointer normalization -------------------------------------------------

    def test_bare_pointer_without_extension_resolves(self) -> None:
        pointer = f"sources/intake/records/{RECORD_ID}"
        result = bmm.open_note(pointer)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["pointer"], f"business_brain:sources/intake/records/{RECORD_ID}.md")

    def test_prefixed_pointer_with_extension_still_resolves(self) -> None:
        pointer = f"business_brain:sources/intake/records/{RECORD_ID}.md"
        result = bmm.open_note(pointer)
        self.assertTrue(result["success"], result)
        self.assertEqual(result["pointer"], pointer)

    def test_prefixed_pointer_without_extension_resolves(self) -> None:
        pointer = f"business_brain:sources/intake/records/{RECORD_ID}"
        result = bmm.open_note(pointer)
        self.assertTrue(result["success"], result)

    def test_pointer_with_a_real_non_markdown_extension_still_errors(self) -> None:
        # A pointer that already carries a (non-.md) extension must not be
        # mangled into a nonsense "<name>.txt.md" guess -- it should fail
        # exactly as before this change.
        result = bmm.open_note("notes/foo.txt")
        self.assertFalse(result["success"])
        self.assertIn("Markdown", result["error"])

    def test_open_note_without_query_keeps_original_truncate_behavior(self) -> None:
        result = bmm.open_note(f"sources/intake/records/{RECORD_ID}.md")
        self.assertTrue(result["success"])
        self.assertEqual(result["content"], RECORD_TEXT)
        self.assertFalse(result["truncated"])
        self.assertNotIn("matched", result)

    # -- bounded passage ---------------------------------------------------------

    def test_query_returns_bounded_passage_containing_match(self) -> None:
        result = bmm.open_note(f"sources/intake/records/{RECORD_ID}", query="widgets warehouse number")
        self.assertTrue(result["success"], result)
        self.assertTrue(result["matched"])
        self.assertIn("forty-two", result["content"])
        self.assertLess(len(result["content"]), len(RECORD_TEXT))

    def test_query_downweights_a_term_repeated_throughout_the_note(self) -> None:
        # "weather" appears in four of five speaker lines; "widgets" appears
        # in exactly one, the line that actually answers the question. A
        # naive raw-frequency scorer would be dominated by "weather"; the
        # inverse-frequency weighting must still surface the widgets line.
        result = bmm.open_note(
            f"sources/intake/records/{RECORD_ID}", query="weather widgets"
        )
        self.assertTrue(result["matched"])
        self.assertIn("forty-two", result["content"])

    def test_query_with_verified_absent_term_returns_no_passage(self) -> None:
        assert "giraffe" not in RECORD_TEXT.lower()
        result = bmm.open_note(f"sources/intake/records/{RECORD_ID}", query="giraffe")
        self.assertTrue(result["success"])
        self.assertFalse(result["matched"])
        self.assertEqual(result["content"], "")

    def test_bounded_passage_stays_under_the_cap_on_a_large_note(self) -> None:
        big_text = "\n".join(f"Speaker: filler line number {i} about nothing." for i in range(5000))
        big_text += "\nSpeaker: the exact secret code is xyzzy-plugh.\n"
        big_text += "\n".join(f"Speaker: filler line number {i} about nothing." for i in range(5000, 10000))
        result = bmm._bounded_passage(big_text, "secret code xyzzy")
        self.assertIsNotNone(result)
        self.assertIn("xyzzy-plugh", result)
        self.assertLessEqual(len(result), bmm.PASSAGE_MAX_CHARS + 1000)

    # -- tool description --------------------------------------------------------

    def test_docstring_covers_intake_records_and_when_to_use_query(self) -> None:
        doc = bmm.open_note.__doc__ or ""
        self.assertIn("intake", doc.lower())
        self.assertIn("query", doc.lower())


if __name__ == "__main__":
    unittest.main()
