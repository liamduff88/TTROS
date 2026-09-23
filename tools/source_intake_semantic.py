#!/usr/bin/env python3
"""Semantic extraction for tools/source_intake.py's mode="semantic".

Turns one already-preserved source record -- either the legacy `type:
historical_source` shape (2026-08-17 import) or the current production capture
shape (`type: source`, tools/source_intake.py::render_record) -- into a
structured claim record and a compact source card -- "what this source says",
never canonical TTROS truth. Every model call is blind by construction: the
fixed template at ``TEMPLATE_PATH`` interpolates only the schema instructions
and the one nominated source's verbatim text (see
``tools/context_assembler.py::assemble_source_intake_semantic_extraction`` for
the matching runtime-context restriction). STEP I1, 2026-09-09; see
scripts/i1_source_intake_semantic_extraction_transcript.md. Production-shape
support added STEP I2, 2026-09-09; see
scripts/i2_source_intake_production_path_transcript.md.

Revisit: when the claim/card schema, the extraction template, the blindness
contamination guard, or the Hermes usage-sidecar schema changes. · Last touched: 2026-09-22.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.source_intake import SourceIntakeError, _frontmatter, extract_exact_bytes  # noqa: E402
from tools.step6_cost_control import (  # noqa: E402
    CostControlError,
    canonical_usage,
    derive_scope,
    preflight,
    record_invocation,
    record_unavailable_invocation,
)

TEMPLATE_PATH = ROOT / "tools" / "source_intake_semantic_extraction_template.md"
HERMES_PROFILE = "source-intake-semantic"
ENV_SENTINEL = "TTROS_SOURCE_INTAKE_SEMANTIC_EXTRACTION"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING = "medium"
CARD_BYTE_CAP = 3000
CLAIM_TYPES = frozenset({
    "advice_received", "liam_position", "decision", "commitment",
    "third_party_statement", "fact_asserted", "offer_made", "open_question",
})
CLAIM_STATUSES = frozenset({"historical", "current", "superseded"})
IMPRECISE_ATTRIBUTIONS = frozenset({"group_unattributed", "speaker_unresolved"})
VERBATIM_RE = re.compile(
    r"<!-- TTROS:VERBATIM_SOURCE:BEGIN:([0-9a-f]{64}) -->\n(.*)<!-- TTROS:VERBATIM_SOURCE:END:\1 -->",
    re.DOTALL,
)
# Contamination deny-list: document-structure/candidate-classification vocabulary
# observed only as operator (Phase 0 recon, git history of a now-superseded
# INDEX.md revision) -- never the corrections' content itself, which Phase 1
# forbids reading before the Phase 5 freeze. Used only to defend the blind
# template against accidental interpolation bugs; the template never
# interpolates any of this by construction.
BLINDNESS_DENY_LIST = (
    "MANIFEST", "manifest.md", "liam_intention", "third_party_statement:",
    "third_party_opinion", "review_tier", "open_loop`", "knowledge candidate",
    "Validation A", "adjudicat",
)


class SemanticExtractionError(SourceIntakeError):
    pass


def render_prompt(source_text: str) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if "{{SOURCE_TEXT}}" not in template:
        raise SemanticExtractionError("extraction template is missing its {{SOURCE_TEXT}} placeholder")
    return template.replace("{{SOURCE_TEXT}}", source_text)


def assert_blind(prompt: str) -> None:
    lowered = prompt.lower()
    hits = [needle for needle in BLINDNESS_DENY_LIST if needle.lower() in lowered]
    if hits:
        raise SemanticExtractionError(f"blindness assertion failed: prompt contains {hits}")


def rehearse_blind_assertion() -> bool:
    """Prove the assertion can return both answers (negative case) before trusting it."""
    contaminated = render_prompt("normal source text") + "\nSee sources/historical_calls/MANIFEST.md."
    try:
        assert_blind(contaminated)
    except SemanticExtractionError:
        return True
    return False


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def extract_verbatim_source(record_text: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter fields, verbatim plaintext body) for either record shape
    semantic mode accepts: the legacy `type: historical_source` shape (2026-08-17
    import, TTROS:VERBATIM_SOURCE marker) and the current production capture shape
    (`tools/source_intake.py::render_record`, `type: source`, TTROS:SOURCE-BYTES
    block). STEP I2, 2026-09-09; see
    scripts/i2_source_intake_production_path_transcript.md.
    """
    fields: dict[str, str] = {}
    with_frontmatter = record_text.startswith("---\n")
    if with_frontmatter:
        lines = record_text.split("\n")
        idx = 1
        while idx < len(lines) and lines[idx].strip() != "---":
            key, sep, value = lines[idx].partition(":")
            if sep:
                fields[key.strip()] = value.strip().strip('"')
            idx += 1
    record_type = fields.get("type")
    if record_type == "historical_source":
        match = VERBATIM_RE.search(record_text)
        if not match:
            raise SemanticExtractionError("historical_source record has no TTROS:VERBATIM_SOURCE block")
        digest, body = match.group(1), match.group(2)
        # The marker's digest is the ORIGINAL pre-import file's sha256 (matches
        # source_sha256, and the frontmatter's own `actual_source_read:
        # full_bytes_for_sha256_and_import`) -- not a hash of this reformatted
        # `body` text, which the 2026-08-17 legacy import tool normalized from the
        # original .txt/.eml. The only valid mechanical check here is internal
        # label consistency between the two places that carry the same digest.
        if fields.get("source_sha256") and fields["source_sha256"] != digest:
            raise SemanticExtractionError("record frontmatter source_sha256 does not match its verbatim block marker")
        return fields, body
    if record_type == "source":
        # Production capture record: the TTROS:SOURCE-BYTES block (base64 of the
        # exact original bytes) is the only verbatim text this shape carries. The
        # "Searchable source text" section is a lossy, FTS-oriented rendering
        # (bracket-escaped, sensitive lines dropped, trailing whitespace
        # stripped, see tools/source_intake.py::_searchable) -- not fit for
        # extraction input. This mirrors the historical_source branch's check
        # above: an independent mechanical consistency check between the
        # frontmatter's declared source_sha256 and the actual payload, computed
        # directly from the decoded bytes rather than a marker-embedded digest.
        raw = extract_exact_bytes(record_text)
        digest = hashlib.sha256(raw).hexdigest()
        if fields.get("source_sha256") and fields["source_sha256"] != digest:
            raise SemanticExtractionError("record frontmatter source_sha256 does not match its exact-byte payload")
        return fields, raw.decode("utf-8", errors="replace")
    raise SemanticExtractionError(
        f"semantic mode requires a type: historical_source or type: source record, got {record_type!r}"
    )


@dataclass
class ModelCallBudget:
    maximum: int
    calls: list[dict[str, Any]] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.calls)

    def record(self, entry: dict[str, Any]) -> None:
        if self.count >= self.maximum:
            raise SemanticExtractionError(
                f"semantic extraction model-call budget exceeded: {self.count} of {self.maximum} already spent"
            )
        self.calls.append(entry)


def _record_semantic_usage(
    usage_file: Path,
    *,
    source_id: str,
    fallback_invocation_id: str,
    model: str,
    root: Path,
) -> dict[str, Any]:
    """Move one Hermes usage sidecar through the canonical Step 6 writer."""
    try:
        usage = json.loads(usage_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        usage = None
    invocation_id = str((usage or {}).get("session_id") or fallback_invocation_id).strip()
    scope = derive_scope(session_id=f"source-intake-semantic-{source_id}")
    if isinstance(usage, dict) and usage.get("input_tokens") is not None and usage.get("output_tokens") is not None:
        try:
            canonical_usage(usage)
        except CostControlError as exc:
            # Provider counters that cannot be normalized are unavailable, not
            # zero.  Preserve that fact in the same canonical ledger.
            return record_unavailable_invocation(
                scope,
                invocation_id=invocation_id,
                provider=str(usage.get("provider") or "unknown"),
                model=str(usage.get("model") or model or "unavailable"),
                reason=f"Memory Intake usage report invalid: {exc}",
                root=root,
                surface="memory-intake:semantic",
            )
        return record_invocation(
            scope,
            invocation_id=invocation_id,
            provider=str(usage.get("provider") or "unknown"),
            model=str(usage.get("model") or model or "unavailable"),
            usage=usage,
            root=root,
            surface="memory-intake:semantic",
        )
    return record_unavailable_invocation(
        scope,
        invocation_id=invocation_id,
        provider=str((usage or {}).get("provider") or "unknown"),
        model=str((usage or {}).get("model") or model or "unavailable"),
        reason="Memory Intake usage report missing or corrupt",
        root=root,
        surface="memory-intake:semantic",
    )


def call_hermes_semantic(
    prompt: str, *, budget: ModelCallBudget, source_id: str,
    model: str = DEFAULT_MODEL, reasoning: str = DEFAULT_REASONING,
    usage_dir: Path | None = None, timeout: int = 240, root: Path = ROOT,
) -> dict[str, Any]:
    if budget.count >= budget.maximum:
        raise SemanticExtractionError(
            f"semantic extraction model-call budget exceeded: refusing call {budget.count + 1} of {budget.maximum}"
        )
    assert_blind(prompt)
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    usage_dir = usage_dir or (root / "queue" / "context_assemblies")
    usage_dir.mkdir(parents=True, exist_ok=True)
    usage_file = usage_dir / f"source-intake-semantic-{source_id}-{digest[:12]}.usage.json"
    fallback_invocation_id = f"source-intake-semantic-{uuid.uuid4().hex}"
    scope = derive_scope(session_id=f"source-intake-semantic-{source_id}")
    preflight(scope, root=root)
    env = dict(os.environ)
    env[ENV_SENTINEL] = "1"
    env.pop("HERMES_HOME", None)
    cmd = [
        "hermes", "-p", HERMES_PROFILE, "-m", model, "--reasoning", reasoning, "-t", "",
        "-z", prompt, "--usage-file", str(usage_file),
    ]
    try:
        result = subprocess.run(cmd, cwd="/tmp", env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _record_semantic_usage(
            usage_file,
            source_id=source_id,
            fallback_invocation_id=fallback_invocation_id,
            model=model,
            root=root,
        )
        raise SemanticExtractionError(f"semantic extraction model call timed out for {source_id}") from exc
    call_entry = {
        "index": budget.count + 1, "source_id": source_id, "prompt_sha256": digest,
        "prompt_bytes": len(prompt.encode("utf-8")), "model": model, "reasoning": reasoning,
        "returncode": result.returncode, "usage_file": str(usage_file),
    }
    budget.record(call_entry)
    accounting = _record_semantic_usage(
        usage_file,
        source_id=source_id,
        fallback_invocation_id=fallback_invocation_id,
        model=model,
        root=root,
    )
    call_entry["invocation_id"] = accounting["row"].get("invocation_id")
    call_entry["usage_recorded"] = bool(accounting.get("recorded"))
    if result.returncode != 0:
        raise SemanticExtractionError(
            f"semantic extraction model call failed for {source_id}: {(result.stderr or result.stdout).strip()[:400]}"
        )
    raw = result.stdout.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SemanticExtractionError(f"semantic extraction response was not valid JSON for {source_id}: {exc}") from exc
    if not isinstance(payload, dict) or "claims" not in payload or "card" not in payload:
        raise SemanticExtractionError(f"semantic extraction response missing claims/card for {source_id}")
    return payload


def validate_claims(claims: list[Any], source_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized_source = normalize_whitespace(source_text)
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []

    def drop(claim: Any, reason: str) -> None:
        dropped.append({"claim": claim if isinstance(claim, dict) else {"raw": claim}, "reason": reason})

    for claim in claims if isinstance(claims, list) else []:
        if not isinstance(claim, dict):
            drop(claim, "claim was not a JSON object")
            continue
        claim_type = str(claim.get("type") or "")
        status = str(claim.get("status") or "")
        attribution = str(claim.get("attribution") or "").strip()
        text = str(claim.get("claim") or "").strip()
        evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
        quote = str(evidence.get("quote") or "")
        locator = str(evidence.get("locator") or "").strip()
        if not text:
            drop(claim, "empty claim text")
            continue
        if claim_type not in CLAIM_TYPES:
            drop(claim, f"claim type not in vocabulary: {claim_type!r}")
            continue
        if status not in CLAIM_STATUSES:
            drop(claim, f"status not in vocabulary: {status!r}")
            continue
        if not quote.strip():
            drop(claim, "empty evidence quote")
            continue
        if normalize_whitespace(quote) not in normalized_source:
            drop(claim, "evidence quote does not resolve as an exact substring of the source")
            continue
        if not locator:
            drop(claim, "missing evidence locator")
            continue
        if not attribution:
            drop(claim, "empty attribution")
            continue
        if attribution not in IMPRECISE_ATTRIBUTIONS and attribution.casefold() not in source_text.casefold():
            drop(claim, f"attribution {attribution!r} does not match a speaker label present in the source")
            continue
        kept.append({
            "claim": text, "type": claim_type, "attribution": attribution, "status": status,
            "evidence": {"quote": quote.strip(), "locator": locator},
        })
    return kept, dropped


def render_claim_receipt(
    *, source_id: str, source_path: str, source_sha256: str, generated_at: str,
    model: str, kept: list[dict[str, Any]], dropped: list[dict[str, Any]],
) -> str:
    """System-evidence receipt for one source's structured claims.

    Lives at queue/receipts/source_intake/claims/... -- outside the Business
    Brain vault, never a brain_pointer, never indexed (the .claims.yaml
    extension is not in aos_indexer.INDEXABLE_EXTENSIONS). Detailed claim
    records are system evidence, not normal Brain retrieval context.
    """
    document = {
        "id": f"source-intake-claim-{source_id}",
        "type": "claim_record",
        "source_id": source_id,
        "source_path": source_path,
        "source_sha256": source_sha256,
        "generated_at": generated_at,
        "model": model,
        "claim_count": len(kept),
        "dropped_count": len(dropped),
        "canonical_truth": False,
        "claims": kept,
        "dropped": dropped,
    }
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True, default_flow_style=False)


def _clip(text: str, limit: int) -> str:
    text = str(text or "").strip()
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"


def render_source_card(
    *, source_id: str, source_path: str, source_sha256: str, source_date: str, ingested_at: str,
    kind: str, participants: str, card: dict[str, Any], receipt_relative: str, card_version: int = 1,
) -> str:
    def bullets(key: str, item_chars: int, empty_ok: str = "none recorded") -> list[str]:
        values = card.get(key)
        items = [str(v).strip() for v in values] if isinstance(values, list) else []
        items = [_clip(item, item_chars) for item in items if item]
        return [f"- {item}" for item in items] or [f"- {empty_ok}"]

    def build(summary_words: int, list_items: int, item_chars: int) -> str:
        summary = _clip(" ".join(str(card.get("summary") or "").split()[:summary_words]), item_chars * 4)
        y = lambda value: json.dumps(str(value), ensure_ascii=False)
        entities = sorted({_clip(str(v).strip(), 40) for v in (card.get("key_topics") or []) if str(v).strip()})[:list_items]
        # The original's vault location is whatever source_path actually says --
        # sources/historical_calls/<slug>.md for the legacy shape, but
        # sources/intake/records/<sha256>.md for a production capture record.
        # Never assume the legacy location (STEP I2, 2026-09-09).
        original_link = source_path.removesuffix(".md")
        lines = [
            "---", f"id: source-intake-card-{source_id}", "type: source_card", "canonical_truth: false", f"source_id: {y(source_id)}",
            f"source_path: {y(source_path)}", f"source_sha256: {source_sha256}", f"source_date: {y(source_date)}",
            f"ingested_at: {y(ingested_at)}", f"kind: {y(kind)}", f"participants: {y(participants)}",
            f"entities: {y(', '.join(entities))}", f"card_version: {card_version}", "---",
            f"# {_clip(card.get('one_line_description') or source_id, 140)}", "",
            "> Card meaning: what this source says. Not canonical TTROS truth. Points back to the", "> existing original.", "",
            f"- Original: [[{original_link}|source]]",
            f"- Claim evidence: {receipt_relative} (system evidence, outside Business Brain, not indexed)", "",
            "## Summary", "", summary, "", "## Key topics", "",
        ]
        lines.extend(bullets("key_topics", item_chars, "no key topics recorded")[:list_items])
        lines.extend(("", "## Who said what",))
        lines.extend(bullets("who_said_what", item_chars, "not distinguishable in this source")[:list_items])
        lines.extend(("", "## Decisions",))
        lines.extend(bullets("decisions", item_chars)[:list_items])
        lines.extend(("", "## Advice and opinions received",))
        lines.extend(bullets("advice_and_opinions", item_chars, "none recorded")[:list_items])
        lines.extend(("", "## Liam's stated positions",))
        lines.extend(bullets("liam_positions", item_chars, "none stated in this source")[:list_items])
        lines.extend(("", "## Commitments and actions",))
        lines.extend(bullets("commitments_and_actions", item_chars, "none recorded")[:list_items])
        lines.extend(("", "## Open questions and uncertainty",))
        lines.extend(bullets("open_questions", item_chars, "none recorded")[:list_items])
        lines.extend(("", "## Conflicts and caveats",))
        lines.extend(bullets("conflicts_and_caveats", item_chars, "none recorded")[:list_items])
        lines.extend(("", "## Promotion candidates (flagged only, not canonical)",))
        lines.extend(bullets("promotion_candidates", item_chars, "none flagged")[:list_items])
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    for summary_words, list_items, item_chars in (
        (120, 20, 300), (90, 10, 220), (60, 6, 160), (40, 4, 120), (25, 2, 90), (12, 1, 60),
    ):
        rendered = build(summary_words, list_items, item_chars)
        if len(rendered.encode("utf-8")) <= CARD_BYTE_CAP:
            return rendered
    raise SemanticExtractionError(f"source card for {source_id} could not fit the {CARD_BYTE_CAP} B cap")


def slug_for(source_path: Path) -> str:
    return source_path.stem


INDEX_TABLE_HEADER = "| Date | Type | People/Topic | One-line description | Card | Original |\n|---|---|---|---|---|---|\n"
INDEX_SECTION_RE = re.compile(r"(?s)(.*?## Historical records\n\n)(.*?)(\n## Elsewhere.*)")
CARD_HEADING_RE = re.compile(r"(?m)^# (.+)$")


def _card_frontmatter(card_text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    lines = card_text.split("\n")
    if not lines or lines[0].strip() != "---":
        return fields
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip('"')
    return fields


def evolve_historical_calls_index(current_text: str, cards_by_id: dict[str, str]) -> str:
    """Evolve the existing INDEX.md table in place; every other line is preserved verbatim."""
    match = INDEX_SECTION_RE.match(current_text)
    if not match:
        raise SemanticExtractionError(
            "sources/historical_calls/INDEX.md does not match the expected evolvable shape "
            "(a '## Historical records' section followed by '## Elsewhere')"
        )
    prefix, _old_table, suffix = match.groups()
    rows = []
    for source_id in sorted(cards_by_id):
        card_text = cards_by_id[source_id]
        fields = _card_frontmatter(card_text)
        heading_match = CARD_HEADING_RE.search(card_text)
        heading = heading_match.group(1).strip() if heading_match else source_id
        date = fields.get("source_date") or "unavailable"
        kind = fields.get("kind") or ""
        participants = fields.get("participants") or ""
        # Same fix as render_source_card's "Original" link: derive the original's
        # location from the card's own recorded source_path rather than assuming
        # the legacy sources/historical_calls/<slug>.md shape (STEP I2, 2026-09-09).
        original_path = (fields.get("source_path") or f"sources/historical_calls/{source_id}.md").removesuffix(".md")
        rows.append(
            f"| {date} | {kind} | {participants} | {heading} | "
            f"[[sources/historical_calls/cards/{source_id}.card|card]] | [[{original_path}|source]] |"
        )
    note = (
        "One row per record. Card links to the compact evidence-only card (STEP I1, 2026-09-09); "
        "Original is the byte-preserved source, unchanged.\n\n"
    )
    table = INDEX_TABLE_HEADER + "\n".join(rows) + "\n"
    return prefix + note + table + suffix
