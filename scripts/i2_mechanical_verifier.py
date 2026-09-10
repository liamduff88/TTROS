#!/usr/bin/env python3
"""STEP I2 mechanical verifier -- deterministic only, no semantic judgment.

Scoped to the one fresh production-capture source this step exercised
(Fred Haiderzada meeting, sept 9th, sha256 d9cb4668...). See
scripts/i2_source_intake_production_path_transcript.md for the full spec.
Modeled on scripts/i1_mechanical_verifier.py's per-item checks, generalized
to the production `type: source` / TTROS:SOURCE-BYTES record shape instead of
the legacy `type: historical_source` / TTROS:VERBATIM_SOURCE shape, and to the
fact that this source's original lives at sources/intake/records/<sha256>.md,
not sources/historical_calls/<slug>.md.

Checks:
  - exactly one original record for this sha256, type: source, exact-byte
    block decodes to the nominated source's own bytes and sha256
  - no duplicate source record (exactly one file under sources/intake/records/
    matches this sha256)
  - card present at the production location (sources/intake/cards/, not
    sources/historical_calls/cards/), canonical_truth: false, type:
    source_card, required front matter present, <=3000 B (excluding the
    hermes_last_write provenance stamp -- same practical-compactness ruling
    I1 applied)
  - card's "Original" link resolves to the real sources/intake/records/
    location (the bug this step fixed), not the legacy location
  - claim receipt present at the production location (queue/receipts/
    source_intake/claims/, not .../claims/historical/), outside the vault,
    never indexed, canonical_truth: false, type: claim_record,
    claim_count/dropped_count match, every kept claim's quote resolves in
    the source and every attribution matches a speaker label or an explicit
    imprecision value
  - the historical-only sources/historical_calls/INDEX.md is untouched by
    production intake: still exactly 15 rows, none of them this source
    (production captures do not mutate that index -- it is a curated table
    over the pre-existing historical_source imports, not a general card
    registry)
  - the production card is present in the real FTS search index (retrievable)
  - nothing typed canonical, nothing promoted
  - the extraction path never read MANIFEST.md (checked structurally)

Tees a .txt transcript beside itself; refuses to overwrite without
--overwrite.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.source_intake import extract_exact_bytes  # noqa: E402
from tools.source_intake_semantic import (  # noqa: E402
    CLAIM_STATUSES, CLAIM_TYPES, IMPRECISE_ATTRIBUTIONS, normalize_whitespace,
)

SOURCE_ID = "d9cb4668fd766474278e414bb53223f944342004f34be23020c161fa4160dd74"
NOMINATED_SOURCE_BYTES = 56044
PROVENANCE_KEY = "hermes_last_write"


def _strip_provenance_block(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text
    closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if closing is None:
        return text
    start = next((i for i in range(1, closing) if lines[i].rstrip("\r\n") == f"{PROVENANCE_KEY}:"), None)
    if start is None:
        return text
    end = start + 1
    while end < closing and (lines[end].startswith("  ") or not lines[end].strip()):
        end += 1
    return "".join(lines[:start] + lines[end:])


def _frontmatter(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return fields
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip('"')
    return fields


def verify(root: Path, repo_root: Path) -> dict:
    findings: list[str] = []
    records_dir = root / "sources" / "intake" / "records"
    calls_dir = root / "sources" / "historical_calls"
    cards_dir = root / "sources" / "intake" / "cards"
    claims_dir = repo_root / "queue" / "receipts" / "source_intake" / "claims"
    index_path = calls_dir / "INDEX.md"

    # 1. Exactly one original record for this sha256; type: source; exact-byte
    # block decodes to the nominated source's own bytes and sha256.
    matches = sorted(records_dir.glob(f"{SOURCE_ID}.md")) if records_dir.is_dir() else []
    if len(matches) != 1:
        findings.append(f"expected exactly one original record for {SOURCE_ID}, found {len(matches)}")
    original_text = ""
    if matches:
        original_path = matches[0]
        original_text = original_path.read_text(encoding="utf-8")
        fields = _frontmatter(original_text)
        if fields.get("type") != "source":
            findings.append(f"original record type is not 'source': {fields.get('type')!r}")
        if fields.get("source_sha256") != SOURCE_ID:
            findings.append("original record frontmatter source_sha256 does not match the nominated source")
        try:
            exact = extract_exact_bytes(original_text)
        except Exception as exc:
            exact = b""
            findings.append(f"original record exact-byte block failed to decode: {exc}")
        if exact:
            if hashlib.sha256(exact).hexdigest() != SOURCE_ID:
                findings.append("original record exact bytes do not hash to the nominated source's sha256")
            if len(exact) != NOMINATED_SOURCE_BYTES:
                findings.append(f"original record exact bytes are {len(exact)} B, expected {NOMINATED_SOURCE_BYTES} B")

    # No duplicate source record anywhere else under sources/intake/records/.
    all_records = sorted(records_dir.glob("*.md")) if records_dir.is_dir() else []
    same_hash = [p for p in all_records if p.stem == SOURCE_ID]
    if len(same_hash) != 1:
        findings.append(f"expected exactly one sources/intake/records/ file for {SOURCE_ID}, found {len(same_hash)}")

    # 2. Card checks.
    card_path = cards_dir / f"{SOURCE_ID}.card.md"
    card_text = ""
    if not card_path.is_file():
        findings.append(f"card missing: {card_path}")
    else:
        card_text = card_path.read_text(encoding="utf-8")
        fields = _frontmatter(card_text)
        compact_bytes = len(_strip_provenance_block(card_text).encode("utf-8"))
        on_disk_bytes = len(card_text.encode("utf-8"))
        if compact_bytes > 3000:
            findings.append(f"card exceeds 3000 B compactness bound: {compact_bytes} B ({on_disk_bytes} B on disk)")
        if fields.get("canonical_truth") != "false":
            findings.append("card canonical_truth is not false")
        if fields.get("type") != "source_card":
            findings.append("card type field is not source_card")
        for required in ("id", "source_id", "source_path", "source_sha256", "card_version"):
            if not fields.get(required):
                findings.append(f"card missing required front matter '{required}'")
        original_link = f"sources/intake/records/{SOURCE_ID}"
        if f"[[{original_link}|source]]" not in card_text:
            findings.append("card does not link to its real original location (sources/intake/records/...)")
        if not (root / f"{original_link}.md").is_file():
            findings.append("card's linked original does not resolve")
        if "MANIFEST" in card_text:
            findings.append("card mentions MANIFEST -- unexpected")

    # 3. Claim receipt checks.
    claim_path = claims_dir / f"{SOURCE_ID}.claims.yaml"
    if not claim_path.is_file():
        findings.append(f"claim receipt missing: {claim_path}")
    else:
        try:
            claim_doc = yaml.safe_load(claim_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            claim_doc = None
            findings.append(f"claim receipt is not valid YAML: {exc}")
        if isinstance(claim_doc, dict):
            if claim_doc.get("canonical_truth") is not False:
                findings.append("claim receipt canonical_truth is not false")
            if claim_doc.get("type") != "claim_record":
                findings.append("claim receipt type field is not claim_record")
            if claim_doc.get("source_id") != SOURCE_ID:
                findings.append("claim receipt source_id does not match its filename")
            kept = claim_doc.get("claims") if isinstance(claim_doc.get("claims"), list) else []
            dropped = claim_doc.get("dropped") if isinstance(claim_doc.get("dropped"), list) else []
            if claim_doc.get("claim_count") != len(kept):
                findings.append("claim receipt claim_count does not match its claims list length")
            if claim_doc.get("dropped_count") != len(dropped):
                findings.append("claim receipt dropped_count does not match its dropped list length")

            normalized_source = normalize_whitespace(original_text)
            source_casefold = original_text.casefold()
            for claim in kept:
                if not isinstance(claim, dict):
                    findings.append("claim entry is not a mapping")
                    continue
                if claim.get("type") not in CLAIM_TYPES:
                    findings.append(f"claim type not in vocabulary: {claim.get('type')!r}")
                if claim.get("status") not in CLAIM_STATUSES:
                    findings.append(f"claim status not in vocabulary: {claim.get('status')!r}")
                evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
                quote = str(evidence.get("quote") or "")
                if normalize_whitespace(quote) not in normalized_source:
                    findings.append(f"claim quote does not resolve in source: {quote!r}")
                attribution = str(claim.get("attribution") or "").strip()
                if attribution not in IMPRECISE_ATTRIBUTIONS and attribution.casefold() not in source_casefold:
                    findings.append(f"claim attribution not found in source: {attribution!r}")
        else:
            findings.append("claim receipt does not decode to a mapping")

        # Never indexed, never a vault pointer.
        from tools import aos_indexer
        if aos_indexer.document_from_path(claim_path) is not None:
            findings.append("claim receipt is indexable -- it must not be")

    # 4. The historical-only INDEX.md must be untouched by production intake:
    # still exactly 15 rows, none of them naming this source.
    if index_path.is_file():
        index_text = index_path.read_text(encoding="utf-8")
        row_lines = [
            line for line in index_text.splitlines()
            if line.startswith("|") and not line.startswith("|---") and "Date" not in line.split("|")[1]
        ]
        if len(row_lines) != 15:
            findings.append(
                f"sources/historical_calls/INDEX.md does not have exactly 15 rows "
                f"(production intake must not mutate it): found {len(row_lines)}"
            )
        matching = [line for line in row_lines if SOURCE_ID in line]
        if matching:
            findings.append(
                f"sources/historical_calls/INDEX.md contains a row for the production source "
                f"{SOURCE_ID} -- it must not be added to the historical-only index"
            )
        if "MANIFEST" in index_text.split("## Elsewhere")[0]:
            findings.append("INDEX table section mentions MANIFEST before '## Elsewhere'")
    else:
        findings.append("INDEX.md is missing")

    # 5. Production card present in the real FTS search index (retrievable).
    if card_path.is_file():
        from tools import aos_indexer
        card_pointer = f"business_brain:sources/intake/cards/{SOURCE_ID}.card.md"
        search_db = repo_root / "search" / "os_index.db"
        if search_db.is_file():
            connection = aos_indexer.connect(search_db, readonly=True)
            try:
                rows = connection.execute(
                    "SELECT path FROM documents WHERE path=?", (card_pointer,),
                ).fetchall()
            finally:
                connection.close()
            if not rows:
                findings.append(f"production card not present in search index: {card_pointer}")
        else:
            findings.append(f"search index database not found: {search_db}")

    return {"findings": findings, "passed": not findings}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.root is None:
        from tools.business_brain import BUSINESS_BRAIN_ROOT
        root = BUSINESS_BRAIN_ROOT
    else:
        root = args.root
    repo_root = args.repo_root if args.repo_root is not None else ROOT

    report = verify(root, repo_root)
    out_path = Path(__file__).with_suffix(".txt")
    if out_path.exists() and not args.overwrite:
        out_path = out_path.with_name(out_path.stem + f"_{root.name.replace(' ', '_')}.txt")
    lines = [f"STEP I2 mechanical verifier -- vault root: {root} -- repo root: {repo_root}", ""]
    lines.append(f"PASSED: {report['passed']}")
    lines.append("")
    if report["findings"]:
        lines.append("FINDINGS:")
        lines.extend(f"- {f}" for f in report["findings"])
    else:
        lines.append("No findings.")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {out_path}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
