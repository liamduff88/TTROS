"""Focused Drive staging, conversion, and reconciliation tests.

Revisit: when Drive Memory Intake staging or source formats change. · Created 2026-09-23.
"""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from zipfile import ZipFile

from tools import aos_indexer
from tools import drive_memory_intake as drive
from tools.source_intake import BYTES_BEGIN, BYTES_END


def docx_fixture() -> bytes:
    xml = (f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Report</w:t></w:r></w:p>'
           f'<w:p><w:r><w:t>First paragraph</w:t></w:r></w:p>'
           f'<w:p><w:pPr><w:numPr/></w:pPr><w:r><w:t>Item one</w:t></w:r></w:p>'
           f'<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Name</w:t></w:r></w:p></w:tc>'
           f'<w:tc><w:p><w:r><w:t>Value</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
           f'</w:body></w:document>')
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return output.getvalue()


def pdf_fixture(text: str | None) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    command = f"BT /F1 12 Tf 20 250 Td ({text}) Tj ET".encode() if text else b"q Q"
    objects.append(b"<< /Length " + str(len(command)).encode() + b" >>\nstream\n" + command + b"\nendstream")
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    start = len(result)
    result += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        result += f"{offset:010d} 00000 n \n".encode()
    result += f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    return bytes(result)


class DriveMemoryIntakeTest(unittest.TestCase):
    def test_markdown_preserves_bytes_and_text_becomes_markdown(self):
        source = b"# Existing\r\n\r\nKeep this.\r\n"
        self.assertEqual(drive.normalize(source, ".md"), source)
        self.assertEqual(drive.normalize(b"\xef\xbb\xbfLine one\r\nLine two", ".txt"), b"Line one\r\nLine two\n")

    def test_docx_preserves_structure(self):
        text = drive.normalize(docx_fixture(), ".docx").decode()
        self.assertIn("# Report", text)
        self.assertIn("First paragraph", text)
        self.assertIn("- Item one", text)
        self.assertIn("| Name | Value |", text)

    def test_text_pdf_and_scanned_pdf(self):
        self.assertIn("Hello PDF", drive.normalize(pdf_fixture("Hello PDF"), ".pdf").decode())
        with self.assertRaisesRegex(drive.DriveIntakeError, "scanned PDFs need OCR"):
            drive.normalize(pdf_fixture(None), ".pdf")

    def test_bad_and_empty_sources_fail(self):
        for raw, suffix in [(b"", ".txt"), (b"\xef\xbb\xbf  \n", ".txt"),
                            (b"not a zip", ".docx"), (b"broken", ".pdf"), (b"hello", ".rtf")]:
            with self.subTest(suffix=suffix, raw=raw), self.assertRaises(drive.DriveIntakeError):
                drive.normalize(raw, suffix)

    def test_reconcile_completed_raw_record_and_prior_drive_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            brain = root / "brain"
            raw = b"# Existing source\n"
            digest = hashlib.sha256(raw).hexdigest()
            record = brain / drive.source_intake.RECORDS_RELATIVE / f"{digest}.md"
            card = brain / drive.source_intake.CARDS_RELATIVE / f"{digest}.card.md"
            index = brain / drive.source_intake.INDEX_RELATIVE
            record.parent.mkdir(parents=True)
            card.parent.mkdir(parents=True)
            record.write_text(f"{BYTES_BEGIN}\n" + __import__("base64").b64encode(raw).decode() + f"\n{BYTES_END}")
            card.write_text("# Card\n")
            index.write_text(f"[[sources/intake/records/{digest}|source]] [[sources/intake/cards/{digest}.card|card]]\n")
            self.assertTrue(drive.reconcile(digest, root=root, brain_root=brain))
            with mock.patch("dashboard.backend.main._memory_intake_ingest_and_record") as canonical:
                self.assertEqual(drive.process(digest, ".md", "existing.md", root=root,
                                               brain_root=brain, ingest=True)["status"], "reconciled")
                canonical.assert_not_called()
            other = "a" * 64
            receipt_dir = root / "queue/receipts/memory_intake"
            receipt_dir.mkdir(parents=True)
            (receipt_dir / "drive.json").write_text(json.dumps({"success": True, "status": "ingested", "source_sha256": other,
                "source_record": f"business_brain:sources/intake/records/{digest}.md"}))
            self.assertTrue(drive.reconcile(other, root=root, brain_root=brain))
            card.unlink()
            self.assertFalse(drive.reconcile(other, root=root, brain_root=brain))

    def test_staged_source_preserved_and_canonical_helper_only_on_ingest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = b"# Source\n"
            digest = hashlib.sha256(raw).hexdigest()
            folder = root / drive.STAGING_RELATIVE / digest
            folder.mkdir(parents=True)
            original = folder / "source.md"
            original.write_bytes(raw)
            brain = root / "brain"
            with mock.patch("tools.source_intake_semantic.call_hermes_semantic") as model:
                prepared = drive.process(digest, ".md", "real-name.md", root=root, brain_root=brain)
                self.assertEqual(prepared["status"], "eligible")
                self.assertFalse((folder / "normalized.md").exists())
                self.assertEqual(original.read_bytes(), raw)
                model.assert_not_called()
            from dashboard.backend import main as backend
            with mock.patch.object(backend, "_memory_intake_ingest_and_record", return_value={"success": True, "status": "ingested"}) as canonical:
                drive.process(digest, ".md", "real-name.md", root=root, brain_root=brain, ingest=True)
            canonical.assert_called_once()
            self.assertEqual(canonical.call_args.args, (folder / "normalized.md",))
            self.assertEqual(canonical.call_args.kwargs["filename"], "real-name.md")
            self.assertEqual(canonical.call_args.kwargs["key"], f"drive-{digest}")
            self.assertEqual(canonical.call_args.kwargs["source_provenance"]["source_sha256"], digest)
            self.assertEqual(canonical.call_args.kwargs["source_provenance"]["original_filename"], "real-name.md")
            self.assertEqual(original.read_bytes(), raw)
            self.assertEqual((folder / "normalized.md").read_bytes(), raw)
            with self.assertRaisesRegex(drive.DriveIntakeError, "mismatch"):
                original.write_bytes(b"changed")
                drive.process(digest, ".md", "real-name.md", root=root, brain_root=brain)

    def test_staging_is_not_published_by_general_search_scan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = root / "queue/inbox/staging/drive/example/normalized.md"
            visible = root / "queue/inbox/visible.md"
            staged.parent.mkdir(parents=True)
            staged.write_text("private staging")
            visible.write_text("visible")
            with mock.patch.object(aos_indexer, "LIVE_ROOT", root):
                self.assertEqual(list(aos_indexer.iter_indexable(root / "queue/inbox")), [visible])

    def test_canonical_receipt_retains_drive_provenance(self):
        from dashboard.backend import main as backend
        provenance = {"source_sha256": "a" * 64, "source_type": ".docx", "original_filename": "notes.docx"}
        with mock.patch.object(backend, "_run_memory_intake_capture", return_value={"success": True, "status": "ingested"}), \
             mock.patch.object(backend, "_write_memory_intake_receipt") as write_receipt, \
             mock.patch.object(backend.latitude_telemetry, "trace"):
            receipt = backend._memory_intake_ingest_and_record(Path("normalized.md"), filename="notes.docx",
                                                                key="drive-test", source_provenance=provenance)
        self.assertEqual(receipt["source_sha256"], provenance["source_sha256"])
        self.assertEqual(receipt["source_type"], ".docx")
        write_receipt.assert_called_once_with(receipt)


if __name__ == "__main__":
    unittest.main()
