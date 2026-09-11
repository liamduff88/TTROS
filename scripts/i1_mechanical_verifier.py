#!/usr/bin/env python3
"""STEP I1 Phase 5 mechanical verifier -- deterministic only, no semantic judgment.

Checks (see scripts/i1_source_intake_semantic_extraction_transcript.md for the full spec):
  - 15 originals present, sha256 unchanged
  - 15 cards, 15 claim receipts, no duplicate Trent card
  - every card links to its existing original, every link resolves
  - every card <=3000 B, measured on the card's own generated content -- i.e. excluding the
    `hermes_last_write` provenance submapping that the vault's write_transaction() unconditionally
    stamps onto every document's frontmatter after generation (Liam's 2026-09-09 ruling: the
    3,000 B figure is a practical compactness bound on the generated card, not a gate on mandatory
    system metadata added afterward). Final on-disk size (including the stamp) is still reported,
    for visibility only -- it never produces a finding.
  - canonical_truth: false, required front matter present
  - every claim's quote resolves as an exact substring of its source (whitespace-normalized)
  - every attribution matches a speaker label in the source, or is an explicit imprecision value
  - every claim type/status is in vocabulary
  - claim_count/dropped_count front matter matches the actual list lengths
  - INDEX has exactly 15 rows and every link resolves
  - nothing typed canonical, nothing promoted
  - the new path never reads MANIFEST.md (checked structurally, not by re-reading it)

Post-reconciliation shape (2026-09-09): cards live in the vault at
sources/historical_calls/cards/<slug>.card.md; claim receipts are NOT in the vault -- they live
outside it at <repo_root>/queue/receipts/source_intake/claims/historical/<slug>.claims.yaml, real
YAML (rendered by tools.source_intake_semantic.render_claim_receipt), never a brain_pointer, never
search-indexed. This verifier reads both real locations; it does not re-derive or redesign them.

Supports --root (vault) and --repo-root (receipts) overrides so the same instrument can run
against scratch copies for the Phase 5 negative control. Tees a .txt transcript beside itself;
refuses to overwrite without --overwrite.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.source_intake_semantic import normalize_whitespace, CLAIM_TYPES, CLAIM_STATUSES, IMPRECISE_ATTRIBUTIONS  # noqa: E402

SLUGS = [
    "andrea-roberts-june-26", "andrea-second-call-june-30", "call-dr-kenneth-after-second-cci",
    "call-kenneth-after-first-cci", "cci-second-call-june-15", "first-call-cci",
    "hermes-water-treatment-summary-trent", "kenneth-june-30", "kenneth-meeting-may-27",
    "kenneth-sme-june-18", "meeting-ken-stanick", "mike-knapp-gtm-context-july-22",
    "mike-knapp-july-21", "trent-first-call", "trent-july-9",
]
# Baseline sha256 of each ORIGINAL RECORD FILE (whole file, not the marker digest inside it --
# that marker is the pre-2026-08-17-import file's own hash and is a label, not a live check),
# captured in Phase 0 recon before any backfill write, 2026-09-09. Used to prove "15 originals
# present, none mutated or copied" -- the only mechanically meaningful form of that check.
ORIGINAL_FILE_BASELINE_SHA256 = {
    "andrea-roberts-june-26": "cd41f23c3275008c5694f172ad1e2a194604760ae7371e425668fc196cf8af7c",
    "andrea-second-call-june-30": "039a4f950f2e599ffad6859e49ed1b9a6a968878f951abdc5af6f338ab573234",
    "call-dr-kenneth-after-second-cci": "5e0ee105e275b439d7d3bdccff63048ea6fb02e599cc69f81120ab8205496bad",
    "call-kenneth-after-first-cci": "cecabecebf6f3434126be166e552ecc7dd44cf7e869c2c5fffc2b78992991998",
    "cci-second-call-june-15": "eaf9e3f41857fb8860513e02ff7f2160c2f44ad623d9e0e090db6852e3ce1f3f",
    "first-call-cci": "bb23cd692564dca7235d5d358c85fad9bf24fc2b61070640fa87b467adc71628",
    "hermes-water-treatment-summary-trent": "46ad2a2944d04af29373ccb7218de30ec872fada4843b37567a177d0c60badd4",
    "kenneth-june-30": "ce38963705327436da1124b1f3755aeb78c32418ade839ec4bf9edd7dcf21d5c",
    "kenneth-meeting-may-27": "b661dfface4f774581b749c2c515e3f0735d18ac48523fb528328306a2a74968",
    "kenneth-sme-june-18": "ac53ffc150235da4a9a3779cdafc422c2ba262bf56fd3ccd81ecb34e6565fc4d",
    "meeting-ken-stanick": "6ea8b3e69919c75565f9da054d8a2856a6c8a8f34fc6dc3d233d88045dbf965a",
    "mike-knapp-gtm-context-july-22": "dd4ae9b7846214f5d9905f55eddd45a85b9a2c3b8886aec98e41815275867f62",
    "mike-knapp-july-21": "47749fcf9c6b929365f08a2f2a1e10ac541f759f80b17a4da87b091a5cbdd58f",
    "trent-first-call": "3a5aa5649d8f6631270ee82bcb004abc7906d803680b1a094c578393610665b0",
    "trent-july-9": "3e0d9492c77bd3f49d38a21a086697d4a5414f5fc928fb4a571dd106b27d3232",
}
VERBATIM_RE = re.compile(
    r"<!-- TTROS:VERBATIM_SOURCE:BEGIN:([0-9a-f]{64}) -->\n(.*)<!-- TTROS:VERBATIM_SOURCE:END:\1 -->",
    re.DOTALL,
)
PROVENANCE_KEY = "hermes_last_write"


def _strip_provenance_block(text: str) -> str:
    """Remove the hermes_last_write frontmatter submapping tools/brain_memory.py's
    apply_provenance() unconditionally injects on every gated write, so byte-cap
    measurement reflects the card as generated, not the card plus a mandatory,
    non-semantic system stamp added afterward. Mirrors apply_provenance()'s own
    exact detection: a line reading exactly "hermes_last_write:" inside the
    frontmatter block, followed by its indented ("  "-prefixed) or blank
    continuation lines, up to the frontmatter's closing "---". If no such block
    is present the text is returned unchanged (nothing to strip)."""
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
    calls_dir = root / "sources" / "historical_calls"
    cards_dir = calls_dir / "cards"
    claims_dir = repo_root / "queue" / "receipts" / "source_intake" / "claims" / "historical"
    index_path = calls_dir / "INDEX.md"

    # 1. 15 originals present, sha256 unchanged (whole-file hash vs. the Phase 0 baseline --
    # none mutated or copied since recon, before any backfill write).
    original_texts: dict[str, str] = {}
    for slug in SLUGS:
        path = calls_dir / f"{slug}.md"
        if not path.is_file():
            findings.append(f"MISSING original: {slug}")
            continue
        whole_file_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        baseline = ORIGINAL_FILE_BASELINE_SHA256.get(slug)
        if baseline and whole_file_digest != baseline:
            findings.append(f"original file mutated since Phase 0 baseline: {slug}")
        text = path.read_text(encoding="utf-8")
        fields = _frontmatter(text)
        match = VERBATIM_RE.search(text)
        if not match:
            findings.append(f"original has no verbatim block: {slug}")
            continue
        digest, body = match.group(1), match.group(2)
        if fields.get("source_sha256") and fields["source_sha256"] != digest:
            findings.append(f"original frontmatter sha256 does not match its own verbatim marker: {slug}")
        original_texts[slug] = body

    # 2. 15 cards, 15 claim receipts, no duplicate Trent card (distinct sha256 per card).
    card_paths = sorted(cards_dir.glob("*.card.md")) if cards_dir.is_dir() else []
    claim_paths = sorted(claims_dir.glob("*.claims.yaml")) if claims_dir.is_dir() else []
    if len(card_paths) != 15:
        findings.append(f"expected 15 cards, found {len(card_paths)}")
    if len(claim_paths) != 15:
        findings.append(f"expected 15 claim receipts, found {len(claim_paths)}")
    card_hashes: dict[str, str] = {}
    for path in card_paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        stem = path.name[: -len(".card.md")]
        if digest in card_hashes.values():
            findings.append(f"duplicate card content: {stem} matches another card byte-for-byte")
        card_hashes[stem] = digest

    # 3-5. per-card / per-claim-receipt checks.
    claim_quote_checks = 0
    claim_attr_checks = 0
    imprecise_count = 0
    substantive_claim_count = 0
    card_sizes: dict[str, dict[str, int]] = {}
    for slug in SLUGS:
        card_path = cards_dir / f"{slug}.card.md"
        if not card_path.is_file():
            continue
        card_text = card_path.read_text(encoding="utf-8")
        fields = _frontmatter(card_text)
        on_disk_bytes = len(card_text.encode("utf-8"))
        compact_bytes = len(_strip_provenance_block(card_text).encode("utf-8"))
        card_sizes[slug] = {"compact_bytes": compact_bytes, "on_disk_bytes": on_disk_bytes}
        if compact_bytes > 3000:
            findings.append(
                f"card exceeds 3000 B compactness bound (excluding hermes_last_write provenance): "
                f"{slug} ({compact_bytes} B; {on_disk_bytes} B on disk with provenance stamp)"
            )
        if fields.get("canonical_truth") != "false":
            findings.append(f"card canonical_truth is not false: {slug}")
        if fields.get("type") != "source_card":
            findings.append(f"card type field is not source_card: {slug}")
        for required in ("id", "source_id", "source_path", "source_sha256", "card_version"):
            if not fields.get(required):
                findings.append(f"card missing required front matter '{required}': {slug}")
        if f"[[sources/historical_calls/{slug}|source]]" not in card_text:
            findings.append(f"card does not link to its existing original: {slug}")
        if not (calls_dir / f"{slug}.md").is_file():
            findings.append(f"card's linked original does not resolve: {slug}")
        if "MANIFEST" in card_text:
            findings.append(f"card mentions MANIFEST -- unexpected: {slug}")

        claim_path = claims_dir / f"{slug}.claims.yaml"
        if not claim_path.is_file():
            continue
        try:
            claim_doc = yaml.safe_load(claim_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            findings.append(f"claim receipt is not valid YAML: {slug}: {exc}")
            continue
        if not isinstance(claim_doc, dict):
            findings.append(f"claim receipt does not decode to a mapping: {slug}")
            continue
        if claim_doc.get("canonical_truth") is not False:
            findings.append(f"claim receipt canonical_truth is not false: {slug}")
        if claim_doc.get("type") != "claim_record":
            findings.append(f"claim receipt type field is not claim_record: {slug}")
        if claim_doc.get("source_id") != slug:
            findings.append(f"claim receipt source_id does not match its filename: {slug}")

        kept = claim_doc.get("claims") if isinstance(claim_doc.get("claims"), list) else []
        dropped = claim_doc.get("dropped") if isinstance(claim_doc.get("dropped"), list) else []
        if claim_doc.get("claim_count") != len(kept):
            findings.append(f"claim receipt claim_count does not match its claims list length: {slug}")
        if claim_doc.get("dropped_count") != len(dropped):
            findings.append(f"claim receipt dropped_count does not match its dropped list length: {slug}")

        source_text = original_texts.get(slug, "")
        normalized_source = normalize_whitespace(source_text)
        source_casefold = source_text.casefold()
        for claim in kept:
            if not isinstance(claim, dict):
                findings.append(f"claim entry is not a mapping: {slug}")
                continue
            substantive_claim_count += 1
            claim_type = claim.get("type")
            status = claim.get("status")
            attribution = str(claim.get("attribution") or "").strip()
            evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
            quote = str(evidence.get("quote") or "")
            if claim_type not in CLAIM_TYPES:
                findings.append(f"claim type not in vocabulary: {slug}: {claim_type!r}")
            if status not in CLAIM_STATUSES:
                findings.append(f"claim status not in vocabulary: {slug}: {status!r}")
            claim_quote_checks += 1
            if normalize_whitespace(quote) not in normalized_source:
                findings.append(f"claim quote does not resolve in source: {slug}: {quote!r}")
            claim_attr_checks += 1
            if attribution in IMPRECISE_ATTRIBUTIONS:
                imprecise_count += 1
            elif attribution.casefold() not in source_casefold:
                findings.append(f"claim attribution not found in source: {slug}: {attribution!r}")

    # 6. INDEX exactly 15 rows, links resolve.
    if index_path.is_file():
        index_text = index_path.read_text(encoding="utf-8")
        row_lines = [
            line for line in index_text.splitlines()
            if line.startswith("|") and not line.startswith("|---") and "Date" not in line.split("|")[1]
        ]
        if len(row_lines) != 15:
            findings.append(f"INDEX does not have exactly 15 rows: found {len(row_lines)}")
        for line in row_lines:
            for m in re.finditer(r"\[\[([^\]|]+)\|[^\]]+\]\]", line):
                target = m.group(1)
                candidate = root / f"{target}.md"
                if not candidate.is_file():
                    findings.append(f"INDEX link does not resolve: {target}")
        if "MANIFEST" in index_text.split("## Elsewhere")[0]:
            findings.append("INDEX table section mentions MANIFEST before '## Elsewhere'")
    else:
        findings.append("INDEX.md is missing")

    imprecision_rate = (imprecise_count / substantive_claim_count) if substantive_claim_count else 0.0
    if imprecision_rate > 0.20:
        findings.append(f"attribution imprecision rate {imprecision_rate:.1%} exceeds the 20% reportable threshold")

    return {
        "findings": findings, "passed": not findings, "cards_found": len(card_paths),
        "claim_records_found": len(claim_paths), "index_rows_checked": True,
        "substantive_claim_count": substantive_claim_count, "quote_checks": claim_quote_checks,
        "attribution_checks": claim_attr_checks, "imprecise_attribution_count": imprecise_count,
        "imprecision_rate": imprecision_rate, "card_sizes": card_sizes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=None, help="vault root override (for the negative control)")
    parser.add_argument("--repo-root", type=Path, default=None, help="repo root override, for claim receipts (for the negative control)")
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
    lines = [f"STEP I1 Phase 5 mechanical verifier -- vault root: {root} -- repo root: {repo_root}", ""]
    lines.append(f"PASSED: {report['passed']}")
    lines.append(f"cards_found={report['cards_found']} claim_records_found={report['claim_records_found']}")
    lines.append(
        f"substantive_claim_count={report['substantive_claim_count']} "
        f"quote_checks={report['quote_checks']} attribution_checks={report['attribution_checks']} "
        f"imprecise_attribution_count={report['imprecise_attribution_count']} "
        f"imprecision_rate={report['imprecision_rate']:.1%}"
    )
    lines.append("")
    if report["findings"]:
        lines.append("FINDINGS:")
        lines.extend(f"- {f}" for f in report["findings"])
    else:
        lines.append("No findings.")
    lines.append("")
    lines.append("CARD SIZES (informational only, not gating -- compact excludes hermes_last_write, on_disk includes it):")
    for slug in sorted(report["card_sizes"]):
        sizes = report["card_sizes"][slug]
        lines.append(f"- {slug}: compact={sizes['compact_bytes']} B on_disk={sizes['on_disk_bytes']} B")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {out_path}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
