import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tools import aos_indexer
from tools.business_brain import BUSINESS_BRAIN_ROOT
from tools.business_brain_inbox import (
    InboxCaptureError,
    capture_attachment,
    capture_text,
    resolve_canonical_inbox,
    sanitize_filename,
)
from tools.validate_business_brain import analyze_vault


def make_vault(root: Path) -> Path:
    for name in ("app.json", "appearance.json", "core-plugins.json", "graph.json", "workspace.json"):
        path = root / ".obsidian" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"search": "-path:_backups"} if name == "graph.json" else {}), encoding="utf-8")
    notes = {
        "README.md": "---\nid: root\ntype: navigation\n---\n# Root\n\n[[index/MEMORY_INDEX|Index]]\n",
        "index/MEMORY_INDEX.md": "---\nid: index\ntype: index\n---\n# Index\n\n[[README|Root]] · [[inbox/README|Inbox]]\n",
        "inbox/README.md": "---\nid: ttros-brain-inbox\ntype: intake\n---\n# Inbox\n\n[[README|Root]] · [[index/MEMORY_INDEX|Index]]\n",
    }
    for relative, text in notes.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (root / "inbox" / "source_notes").mkdir(parents=True)
    return root


class BusinessBrainInboxTests(unittest.TestCase):
    def test_canonical_resolution_sanitization_and_containment(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = make_vault(Path(temp))
            self.assertEqual(resolve_canonical_inbox(root=vault), (vault / "inbox/source_notes").resolve())
            self.assertEqual(sanitize_filename("../../Résumé notes?.MD"), "Résumé-notes.md")
            outside = vault / "elsewhere"
            outside.mkdir()
            (vault / "inbox/source_notes").rmdir()
            (vault / "inbox/source_notes").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(InboxCaptureError):
                resolve_canonical_inbox(root=vault)

    def test_unicode_multiline_capture_is_atomic_and_replay_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = make_vault(Path(temp))
            text = "  Héllo, 世界\nsecond line\n"
            stamp = datetime(2026, 7, 19, 20, 30, tzinfo=timezone.utc)
            first = capture_text(text, source="cockpit_capture", capture_id="dashboard-replay", captured_at=stamp, root=vault)
            replay = capture_text(text, source="cockpit_capture", capture_id="dashboard-replay", root=vault)
            self.assertFalse(first.duplicate)
            self.assertTrue(replay.duplicate)
            self.assertEqual(first.path, replay.path)
            self.assertRegex(first.path.name, r"^capture_[0-9a-f]{16}\.md$")
            self.assertTrue(first.path.read_text(encoding="utf-8").endswith(text))
            self.assertEqual(list((vault / "inbox/source_notes").glob("capture_*.md")), [first.path])
            with self.assertRaises(InboxCaptureError):
                capture_text("changed", source="cockpit_capture", capture_id="dashboard-replay", root=vault)

    def test_attachment_name_is_safe_and_companion_note_stays_in_same_inbox(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = make_vault(Path(temp))
            result = capture_attachment(
                b"raw attachment",
                original_filename="../../brief?.txt",
                mime_type="text/plain",
                capture_id="telegram-file",
                root=vault,
            )
            inbox = (vault / "inbox/source_notes").resolve()
            self.assertTrue(result.path.resolve().is_relative_to(inbox))
            self.assertTrue(result.attachment_path.resolve().is_relative_to(inbox))
            self.assertNotIn("..", result.attachment_path.name)
            self.assertEqual(result.attachment_path.read_bytes(), b"raw attachment")

    def test_attachment_replay_with_missing_captured_at_does_not_orphan_file(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = make_vault(Path(temp))
            stamp = datetime(2026, 7, 19, 20, 30, tzinfo=timezone.utc)
            first = capture_attachment(
                b"raw attachment",
                original_filename="brief.txt",
                mime_type="text/plain",
                capture_id="dup-attach",
                captured_at=stamp,
                root=vault,
            )
            self.assertFalse(first.duplicate)
            original_note_text = first.path.read_text(encoding="utf-8")

            replay = capture_attachment(
                b"raw attachment",
                original_filename="brief.txt",
                mime_type="text/plain",
                capture_id="dup-attach",
                captured_at=None,
                root=vault,
            )
            self.assertTrue(replay.duplicate)
            self.assertEqual(replay.path, first.path)
            self.assertEqual(replay.attachment_path, first.attachment_path)
            self.assertEqual(first.path.read_text(encoding="utf-8"), original_note_text)

            attachments = (vault / "inbox/source_notes/attachments")
            self.assertEqual(list(attachments.glob("tg_*")), [first.attachment_path])

    def test_concurrent_same_capture_id_text_captures_share_one_file(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = make_vault(Path(temp))
            barrier = threading.Barrier(2)
            results: list = []
            errors: list = []

            def worker():
                barrier.wait()
                try:
                    results.append(
                        capture_text("shared race body", source="cockpit_capture", capture_id="race-id", root=vault)
                    )
                except Exception as exc:  # pragma: no cover - failure path surfaced via assertion
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            self.assertEqual(len(results), 2)
            self.assertEqual({result.path for result in results}, {results[0].path})

            files = list((vault / "inbox/source_notes").glob("capture_*.md"))
            self.assertEqual(len(files), 1)

            replay = capture_text("shared race body", source="cockpit_capture", capture_id="race-id", root=vault)
            self.assertTrue(replay.duplicate)
            self.assertEqual(replay.path, files[0])

    def test_raw_intake_is_not_indexed_or_part_of_durable_vault_graph(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = make_vault(Path(temp))
            raw = vault / "inbox/source_notes/raw.md"
            raw.write_text("# Raw\n[[missing-target]]\n", encoding="utf-8")
            self.assertTrue(aos_indexer.is_excluded(raw, root=vault))
            result = analyze_vault(vault)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["checks"]["canonical_note_count"], 3)
            self.assertEqual(result["intake_capture_paths"], ["inbox/source_notes/raw.md"])
            self.assertEqual(result["broken_links"], [])

    def test_live_readme_preserves_stable_contract_and_documents_capture(self):
        readme = BUSINESS_BRAIN_ROOT / "inbox/README.md"
        text = readme.read_text(encoding="utf-8")
        self.assertIn("id: ttros-brain-inbox", text)
        self.assertIn("type: intake", text)
        self.assertIn("[[README|Vault Root]]", text)
        self.assertIn("[[index/MEMORY_INDEX|Memory Index]]", text)
        self.assertIn("source_notes/", text)
        self.assertIn("distilled_packets/", text)
        self.assertIn("/inbox", text)
        self.assertIn("memory_promotion", text)


if __name__ == "__main__":
    unittest.main()
