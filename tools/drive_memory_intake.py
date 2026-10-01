#!/usr/bin/env python3
"""Deterministic DriveFS staging adapter for the existing Memory Intake spine.

Revisit: when source formats or Memory Intake provenance contracts change. · Created 2026-09-23.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import source_intake
from tools.business_brain import BUSINESS_BRAIN_ROOT

STAGING_RELATIVE = Path("queue/inbox/staging/drive")
SUPPORTED = frozenset({".md", ".txt", ".docx", ".pdf"})
MAX_BYTES = 25 * 1024 * 1024
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DriveIntakeError(ValueError):
    pass


def _complete_record(digest: str, brain_root: Path) -> bool:
    record = brain_root / source_intake.RECORDS_RELATIVE / f"{digest}.md"
    card = brain_root / source_intake.CARDS_RELATIVE / f"{digest}.card.md"
    index = brain_root / source_intake.INDEX_RELATIVE
    if not (record.is_file() and card.is_file() and index.is_file()):
        return False
    try:
        text = index.read_text(encoding="utf-8")
        source_intake._assert_index_links_source_and_card(text, digest)
        return hashlib.sha256(source_intake.extract_exact_bytes(record.read_text(encoding="utf-8"))).hexdigest() == digest
    except (OSError, UnicodeError, source_intake.SourceIntakeError):
        return False


def reconcile(source_sha256: str, *, root: Path = ROOT, brain_root: Path = BUSINESS_BRAIN_ROOT) -> bool:
    """Trust completed canonical artifacts, including older raw .md/.txt intake."""
    if not _DIGEST.fullmatch(source_sha256):
        raise DriveIntakeError("invalid SHA-256")
    if _complete_record(source_sha256, brain_root):
        return True
    receipts = root / "queue/receipts/memory_intake"
    if not receipts.is_dir():
        return False
    for path in receipts.glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            pointer = str(row.get("source_record") or "")
            match = re.fullmatch(r"business_brain:sources/intake/records/([0-9a-f]{64})\.md", pointer)
            if row.get("success") and row.get("status") in {"ingested", "duplicate"} and row.get("source_sha256") == source_sha256 and match and _complete_record(match.group(1), brain_root):
                return True
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
    return False


def _paragraph(element: ET.Element) -> str:
    return "".join(node.text or "" for node in element.iter(_W + "t")).strip()


def _docx_markdown(raw: bytes) -> str:
    from io import BytesIO
    try:
        with ZipFile(BytesIO(raw)) as archive:
            document = ET.fromstring(archive.read("word/document.xml"))
    except (BadZipFile, KeyError, ET.ParseError) as exc:
        raise DriveIntakeError("broken DOCX document") from exc
    body = document.find(_W + "body")
    if body is None:
        raise DriveIntakeError("DOCX has no body")
    blocks: list[str] = []
    for element in body:
        if element.tag == _W + "p":
            value = _paragraph(element)
            if not value:
                continue
            style = element.find(f"{_W}pPr/{_W}pStyle")
            kind = style.get(_W + "val", "") if style is not None else ""
            heading = re.fullmatch(r"Heading([1-6])", kind, re.IGNORECASE)
            if heading:
                value = f"{'#' * int(heading.group(1))} {value}"
            elif element.find(f"{_W}pPr/{_W}numPr") is not None or "list" in kind.lower():
                value = f"- {value}"
            blocks.append(value)
        elif element.tag == _W + "tbl":
            rows = []
            for row in element.findall(_W + "tr"):
                cells = [" ".join(filter(None, (_paragraph(p) for p in cell.iter(_W + "p")))).replace("|", "\\|") for cell in row.findall(_W + "tc")]
                if cells:
                    rows.append(cells)
            if rows:
                width = max(map(len, rows))
                rows = [row + [""] * (width - len(row)) for row in rows]
                blocks.append("\n".join(["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"] + ["| " + " | ".join(row) + " |" for row in rows[1:]]))
    return "\n\n".join(blocks)


def normalize(raw: bytes, suffix: str) -> bytes:
    """No model access: produce nonempty UTF-8 Markdown or fail explicitly."""
    suffix = suffix.lower()
    if suffix not in SUPPORTED:
        raise DriveIntakeError(f"unsupported source type: {suffix}")
    if not raw or len(raw) > MAX_BYTES:
        raise DriveIntakeError("source is empty or exceeds 25 MiB")
    if suffix == ".md":
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DriveIntakeError("Markdown is not UTF-8") from exc
        if not text.strip():
            raise DriveIntakeError("Markdown has no content")
        return raw
    if suffix == ".txt":
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DriveIntakeError("text file is not UTF-8") from exc
    elif suffix == ".docx":
        text = _docx_markdown(raw)
    else:
        try:
            from pypdf import PdfReader
            from io import BytesIO
            reader = PdfReader(BytesIO(raw), strict=True)
            pages = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
        except ImportError as exc:
            raise DriveIntakeError("pypdf is required for PDF conversion") from exc
        except Exception as exc:
            raise DriveIntakeError("broken or unreadable PDF") from exc
        if not re.search(r"\w", " ".join(pages), re.UNICODE):
            raise DriveIntakeError("PDF has no extractable text; scanned PDFs need OCR")
        text = "\n\n".join(f"## Page {number}\n\n{body}" for number, body in enumerate(pages, 1))
    if not text.strip():
        raise DriveIntakeError("conversion produced empty Markdown")
    return (text.rstrip() + "\n").encode("utf-8")


def process(source_sha256: str, suffix: str, original_filename: str, *, root: Path = ROOT,
            brain_root: Path = BUSINESS_BRAIN_ROOT, ingest: bool = False) -> dict:
    """The staged source is immutable; only the canonical ingest helper writes memory."""
    if not _DIGEST.fullmatch(source_sha256) or suffix.lower() not in SUPPORTED or not re.fullmatch(r"\.[a-z0-9]+", suffix):
        raise DriveIntakeError("invalid staged source selector")
    if reconcile(source_sha256, root=root, brain_root=brain_root):
        return {"status": "reconciled", "source_sha256": source_sha256}
    folder = root / STAGING_RELATIVE / source_sha256
    source = folder / f"source{suffix.lower()}"
    if source.is_symlink() or not source.is_file():
        raise DriveIntakeError("staged source is missing or unsafe")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source_sha256:
        raise DriveIntakeError("staged source SHA-256 mismatch")
    normalized = normalize(raw, suffix)
    normalized_sha256 = hashlib.sha256(normalized).hexdigest()
    if not ingest:
        return {"status": "eligible", "source_sha256": source_sha256, "normalized_sha256": normalized_sha256}
    target = folder / "normalized.md"
    if target.exists():
        if target.is_symlink() or target.read_bytes() != normalized:
            raise DriveIntakeError("existing normalized file differs")
    else:
        target.write_bytes(normalized)
    from dashboard.backend import main as backend
    return backend._memory_intake_ingest_and_record(
        target, filename=original_filename, key=f"drive-{source_sha256}",
        source_provenance={"source_sha256": source_sha256, "source_type": suffix.lower(),
                           "original_filename": original_filename, "staged_source": str(source.relative_to(root)),
                           "normalized_sha256": normalized_sha256},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "prepare", "ingest"))
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--suffix", required=True)
    parser.add_argument("--name-b64", default="")
    args = parser.parse_args()
    try:
        name = base64.b64decode(args.name_b64, validate=True).decode("utf-8") if args.name_b64 else f"source{args.suffix}"
        name = Path(name.replace("\\", "/")).name
        if args.action == "check":
            result = {"status": "reconciled" if reconcile(args.sha256) else "eligible", "source_sha256": args.sha256}
        else:
            result = process(args.sha256, args.suffix, name, ingest=args.action == "ingest")
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("success", True) else 2
    except (DriveIntakeError, OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"status": "needs_attention", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
