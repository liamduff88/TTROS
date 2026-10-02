"""Memory entity browser endpoints: read-only by default, edit gate never wider than save, no model calls."""

import importlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

EVIDENCE = "sources/historical_calls/call-kenneth-after-first-cci.md"
KNOWLEDGE = "memory/clients.md"
OUT_OF_EDIT_SCOPE = "sources/historical_calls/kenneth-liam-collaboration-2026-09-18.md"


def _no_process(*_args, **_kwargs):
    raise AssertionError("Memory browsing must not start a process (model or otherwise)")


class MemoryBrowserApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = importlib.import_module("dashboard.backend.main")

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.vault = Path(temp.name) / "vault"
        files = {
            EVIDENCE: "---\nid: hs\ntype: historical_source\ncanonical_truth: false\n---\n# Call with Kenneth\n",
            KNOWLEDGE: "---\nid: clients\ntype: knowledge\n---\n# Clients\n\nKenneth Moodley.\n",
            OUT_OF_EDIT_SCOPE: "# Kenneth / Liam Collaboration — Historical Evidence (2026-09-18)\n",
        }
        for relative, text in files.items():
            (self.vault / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.vault / relative).write_text(text, encoding="utf-8")
        for patcher in (
            mock.patch.object(self.backend.business_brain, "BUSINESS_BRAIN_ROOT", self.vault),
            mock.patch.object(self.backend.aos_entity_index, "ensure_current", return_value={"status": "current"}),
            mock.patch.object(self.backend.aos_entity_index, "document_meta", return_value={}),
            mock.patch.object(self.backend, "GRAPHIFY_BRAIN_DIR", Path(temp.name) / "graphify"),
            mock.patch.object(subprocess, "Popen", _no_process),
            mock.patch.object(subprocess, "run", _no_process),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def doc(self, relative):
        return self.backend.memory_document(f"business_brain:{relative}")

    def test_full_document_is_returned_with_windows_path_and_no_model(self):
        result = self.doc(KNOWLEDGE)
        self.assertEqual(result["content"], (self.vault / KNOWLEDGE).read_text(encoding="utf-8"))
        self.assertFalse(result["model_invoked"])
        self.assertEqual(result["graphify"]["available"], False)

    def test_edit_flag_matches_save_gate_and_never_widens_it(self):
        self.assertTrue(self.doc(KNOWLEDGE)["editable"])
        evidence = self.doc(EVIDENCE)
        self.assertFalse(evidence["editable"])
        self.assertIn("preserved source evidence", evidence["edit_block_reason"])
        readable_only = self.doc(OUT_OF_EDIT_SCOPE)
        self.assertFalse(readable_only["editable"])
        with self.assertRaises(HTTPException):  # the real save gate agrees it is not writable
            self.backend.dashboard_save_memory(self.backend.DashboardMemorySave(
                path=f"business_brain:{OUT_OF_EDIT_SCOPE}", content="x", expected_revision=readable_only["revision"]))

    def test_paths_outside_the_vault_or_scope_are_refused(self):
        for pointer in ("business_brain:../etc/passwd", "/etc/passwd", "business_brain:_backups/x.md"):
            with self.assertRaises(HTTPException):
                self.backend.memory_document(pointer)
        with self.assertRaises(HTTPException) as caught:
            self.backend.memory_browse("../")
        self.assertEqual(caught.exception.status_code, 400)
        with self.assertRaises(HTTPException) as caught:
            self.backend.memory_open(self.backend.MemoryOpenRequest(path=f"business_brain:{KNOWLEDGE}", kind="exec"))
        self.assertEqual(caught.exception.status_code, 400)

    def test_browse_lists_one_folder(self):
        listing = self.backend.memory_browse("sources/historical_calls")
        self.assertEqual({row["name"] for row in listing["files"]}, {Path(EVIDENCE).name, Path(OUT_OF_EDIT_SCOPE).name})
        self.assertEqual(listing["folders"], [])
        self.assertFalse(listing["model_invoked"])


if __name__ == "__main__":
    unittest.main()
