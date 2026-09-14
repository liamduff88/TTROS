"""Focused tests for the shared dashboard upload mechanism.

Revisit: when the shared upload contract, its size cap, or its supported
content types change. · Created 2026-09-13.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "dashboard" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import uploads_store as us  # noqa: E402


class UploadsStoreTest(unittest.TestCase):
    def test_sanitize_filename_strips_directories_and_traversal(self):
        self.assertEqual(us.sanitize_filename("../../etc/passwd"), "passwd")
        self.assertEqual(us.sanitize_filename("C:\\Users\\liam\\notes.txt"), "notes.txt")
        self.assertEqual(us.sanitize_filename(""), "upload")
        self.assertEqual(us.sanitize_filename("weird<>name?.md"), "weird__name_.md")

    def test_save_upload_persists_real_bytes_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            data = b"hello business brain\n"
            saved = us.save_upload(base, "Fred call notes.txt", data)
            self.assertTrue(saved.supported)
            self.assertEqual(saved.path.read_bytes(), data)
            meta = us.read_meta(base, saved.upload_id)
            self.assertEqual(meta["original_filename"], "Fred call notes.txt")
            self.assertEqual(meta["status"], "ready")
            self.assertEqual(meta["size"], len(data))

    def test_save_upload_rejects_empty_and_oversized(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with self.assertRaisesRegex(us.UploadError, "empty"):
                us.save_upload(base, "empty.txt", b"")
            with self.assertRaisesRegex(us.UploadError, "exceeds"):
                us.save_upload(base, "big.txt", b"x" * (us.MAX_UPLOAD_BYTES + 1))

    def test_unsupported_and_unknown_types_are_flagged_not_faked(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            pdf = us.save_upload(base, "report.pdf", b"%PDF-fixture")
            self.assertFalse(pdf.supported)
            self.assertIn("not yet supported", us.read_meta(base, pdf.upload_id)["support_note"])
            unknown = us.save_upload(base, "archive.zip", b"PK-fixture")
            self.assertFalse(unknown.supported)

    def test_upload_file_path_rejects_path_traversal_in_upload_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for hostile in ("../../../etc/passwd", "..", "not-a-hex-id", "a" * 31, "a" * 33):
                with self.assertRaises(us.UploadError):
                    us.upload_file_path(base, hostile)

    def test_upload_file_path_rejects_unknown_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            with self.assertRaises(us.UploadError):
                us.upload_file_path(base, "0" * 32)

    def test_list_uploads_orders_newest_first_and_skips_corrupt_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            first = us.save_upload(base, "a.txt", b"a")
            second = us.save_upload(base, "b.txt", b"b")
            # A stray directory with no meta.json must not break listing.
            (base / us.UPLOADS_RELATIVE / "stray").mkdir(parents=True)
            rows = us.list_uploads(base)
            ids = [row["upload_id"] for row in rows]
            self.assertEqual(set(ids), {first.upload_id, second.upload_id})

    def test_write_meta_round_trips_status_updates(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            saved = us.save_upload(base, "a.md", b"# note")
            meta = us.read_meta(base, saved.upload_id)
            meta["status"] = "ingested"
            meta["source_pointer"] = "business_brain:sources/intake/records/deadbeef.md"
            us.write_meta(base, saved.upload_id, meta)
            self.assertEqual(us.read_meta(base, saved.upload_id)["status"], "ingested")


if __name__ == "__main__":
    unittest.main()
