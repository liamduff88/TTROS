import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from tools import aos_indexer
from tools import business_brain_inbox as inbox_module
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
        "inbox/README.md": (
            "---\nid: ttros-brain-inbox\ntype: intake\n---\n# Inbox\n\n"
            "[[README|Vault Root]] · [[index/MEMORY_INDEX|Memory Index]]\n\n"
            "Raw captures enter `source_notes/`; reviewed packets use `distilled_packets/`.\n"
            "Use `/inbox` for capture and `memory_promotion` for durable knowledge.\n"
        ),
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

    def test_attachment_replay_conflicts_when_identity_bytes_change(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = make_vault(Path(temp))
            first = capture_attachment(
                b"first bytes",
                original_filename="brief.txt",
                mime_type="text/plain",
                capture_id="attachment-byte-conflict",
                root=vault,
            )

            with self.assertRaisesRegex(InboxCaptureError, "different content"):
                capture_attachment(
                    b"different bytes",
                    original_filename="brief.txt",
                    mime_type="text/plain",
                    capture_id="attachment-byte-conflict",
                    root=vault,
                )

            self.assertEqual(first.attachment_path.read_bytes(), b"first bytes")
            self.assertEqual(len(list((vault / "inbox/source_notes").glob("tg_*.md"))), 1)
            self.assertEqual(len(list((vault / "inbox/source_notes/attachments").glob("tg_*"))), 1)

    def test_concurrent_first_attachment_capture_publishes_one_complete_pair(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = make_vault(Path(temp))
            worker_count = 12
            barrier = threading.Barrier(worker_count)
            results: list = []
            errors: list = []

            def worker(worker_index: int):
                barrier.wait()
                try:
                    results.append(
                        capture_attachment(
                            b"shared concurrent attachment",
                            original_filename=f"concurrency-proof-{worker_index}.txt",
                            mime_type="text/plain",
                            capture_id="concurrent-attachment",
                            root=vault,
                        )
                    )
                except Exception as exc:  # pragma: no cover - surfaced below
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(index,)) for index in range(worker_count)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            self.assertEqual(len(results), worker_count)
            self.assertEqual(sum(not result.duplicate for result in results), 1)
            self.assertEqual(len({result.path for result in results}), 1)
            self.assertEqual(len({result.attachment_path for result in results}), 1)

            inbox = vault / "inbox/source_notes"
            notes = list(inbox.glob("tg_*.md"))
            attachments = list((inbox / "attachments").glob("tg_*"))
            self.assertEqual(notes, [results[0].path])
            self.assertEqual(attachments, [results[0].attachment_path])
            self.assertEqual(attachments[0].read_bytes(), b"shared concurrent attachment")
            self.assertIn(results[0].attachment_pointer, notes[0].read_text(encoding="utf-8"))
            self.assertEqual(list(inbox.rglob("*.tmp")), [])

    def test_concurrent_conflicting_note_does_not_remove_winning_attachment(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = make_vault(Path(temp))
            owner_at_note = threading.Event()
            contender_done = threading.Event()
            original_capture_text = inbox_module.capture_text
            results: list = []
            errors: list = []

            def ordered_capture_text(text, **kwargs):
                if text == "attachment owner note":
                    owner_at_note.set()
                    self.assertTrue(contender_done.wait(5))
                try:
                    return original_capture_text(text, **kwargs)
                finally:
                    if text == "concurrent winner note":
                        contender_done.set()

            def capture(body: str):
                try:
                    results.append(
                        capture_attachment(
                            b"shared attachment bytes",
                            original_filename="race.txt",
                            mime_type="text/plain",
                            capture_id="concurrent-note-conflict",
                            body=body,
                            root=vault,
                        )
                    )
                except Exception as exc:  # pragma: no cover - surfaced below
                    errors.append(exc)

            with patch.object(inbox_module, "capture_text", side_effect=ordered_capture_text):
                owner = threading.Thread(target=capture, args=("attachment owner note",))
                owner.start()
                self.assertTrue(owner_at_note.wait(5))
                contender = threading.Thread(target=capture, args=("concurrent winner note",))
                contender.start()
                contender.join(timeout=5)
                owner.join(timeout=5)

            self.assertFalse(owner.is_alive())
            self.assertFalse(contender.is_alive())
            self.assertEqual(len(results), 1)
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], InboxCaptureError)
            self.assertIn("different content", str(errors[0]))
            self.assertTrue(results[0].path.is_file())
            self.assertTrue(results[0].attachment_path.is_file())
            self.assertIn(results[0].attachment_pointer, results[0].path.read_text(encoding="utf-8"))
            self.assertEqual(results[0].attachment_path.read_bytes(), b"shared attachment bytes")

    def test_legacy_timestamped_note_and_attachment_remain_replay_discoverable(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = make_vault(Path(temp))
            first = capture_attachment(
                b"legacy attachment",
                original_filename="legacy.txt",
                mime_type="text/plain",
                capture_id="legacy-attachment-replay",
                root=vault,
            )
            legacy_note = first.path.with_name(first.path.name.replace("tg_", "tg_2026-07-19_203000_", 1))
            legacy_attachment = first.attachment_path.with_name(
                first.attachment_path.name.replace("tg_", "tg_2026-07-19_203000000000_", 1)
            )
            first.path.rename(legacy_note)
            first.attachment_path.rename(legacy_attachment)
            legacy_pointer = f"business_brain:{legacy_attachment.relative_to(vault).as_posix()}"
            legacy_note.write_text(
                legacy_note.read_text(encoding="utf-8").replace(first.attachment_pointer, legacy_pointer),
                encoding="utf-8",
            )

            replay = capture_attachment(
                b"legacy attachment",
                original_filename="legacy.txt",
                mime_type="text/plain",
                capture_id="legacy-attachment-replay",
                root=vault,
            )

            self.assertTrue(replay.duplicate)
            self.assertEqual(replay.path, legacy_note.resolve())
            self.assertEqual(replay.attachment_path, legacy_attachment.resolve())

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

    def test_fixture_readme_preserves_stable_contract_and_documents_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = make_vault(Path(temp))
            text = (vault / "inbox/README.md").read_text(encoding="utf-8")
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
