#!/usr/bin/env python3
"""Validation A blind-run deterministic fidelity detector instrument.

Rebuilt 2026-09-09 per operator ruling: the model-assisted path (see
``phase2_instrument_defect_report.md``) is abandoned pre-provider-call and
does not contaminate this run. Contract §6.4: "Validation A may be
deterministic or model-assisted; that is an implementation choice." This is
the deterministic choice -- zero model calls, pure Python, mechanical rules
operationalizing the nine §5 categories directly.

Authored with the 12 resolved candidates' 14 source documents unreadable
(Phase 2A guard extension). Designed only from the frozen contract text
(docs/ttros/TTROS_B7_SCORING_FIDELITY_CONTRACT_v2.1_2026-09-08.md §5/§6.1) and
rehearsed only against synthetic fixtures constructed for this file -- never
against historical labels, adjudication, prior reports, or sealed material.

Because this instrument makes zero model calls, the §6.4 call-budget cap does
not bind it (operator ruling 2026-09-09): no call counter, no Hermes
plumbing, no subprocess, no network.

Output contract (unchanged from the abandoned model-assisted instrument):
  verdict: "SUPPORTED" | "NOT SUPPORTED"
  reason_tags: zero or more of the nine §6.1 tags
  evidence: minimum span/proposition string
SOURCE_UNAVAILABLE is a source-status convention (§0.7 / operator ruling),
never a verdict or reason tag -- enforced structurally below (it is not a
member of ALLOWED_VERDICTS or ALLOWED_TAGS, and score_real_item() returns it
as a distinct top-level ``status`` before the detector is ever reached).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ALLOWED_VERDICTS = {"SUPPORTED", "NOT SUPPORTED"}
ALLOWED_TAGS = {
    "normalization", "list_coverage", "essential_qualifier", "attribution",
    "polarity_assertion", "temporal_status", "prohibited_opposite", "locality",
    "source_contract",
}
FORBIDDEN_AS_VERDICT_OR_TAG = "SOURCE_UNAVAILABLE"
assert FORBIDDEN_AS_VERDICT_OR_TAG not in ALLOWED_VERDICTS
assert FORBIDDEN_AS_VERDICT_OR_TAG not in ALLOWED_TAGS


# ----------------------------------------------------------------------------
# Generic text primitives -- no real TTROS content, no historical labels.
# ----------------------------------------------------------------------------

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "of", "to", "in", "on", "at", "for", "with", "by",
    "this", "that", "it", "its", "as", "from", "into", "than", "then", "so",
    "there", "their", "they", "them", "these", "those", "which", "who",
    "whom", "will", "would", "can", "could", "about", "over", "also",
}

_QUOTE_TRANSLATION = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
})


def normalize_text(text: str) -> str:
    """Representation-only normalization per §5.1: quotes, hyphen/space,
    case, whitespace. Never touches wording, numbers, or polarity."""
    t = text.translate(_QUOTE_TRANSLATION)
    t = t.replace("'", "")
    t = re.sub(r"-", " ", t)
    t = t.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    return [p.strip() for p in parts if p.strip()]


def split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]


def content_words(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z']+", normalize_text(text))
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS}


def overlap_score(a_words: set[str], sentence: str) -> int:
    return len(a_words & content_words(sentence))


def relevant_sentences(claim: str, source: str) -> list[str]:
    """Every source sentence sharing at least one content word with the
    claim, ranked by overlap descending (ties keep source order)."""
    claim_words = content_words(claim)
    sentences = split_sentences(source)
    scored = [(overlap_score(claim_words, s), i, s) for i, s in enumerate(sentences)]
    scored = [x for x in scored if x[0] > 0]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [s for _, _, s in scored]


def best_sentence(claim: str, source: str) -> str | None:
    rel = relevant_sentences(claim, source)
    return rel[0] if rel else None


# ----------------------------------------------------------------------------
# §5.4 Attribution -- generic actor-vs-predicate extraction.
# ----------------------------------------------------------------------------

_ATTRIBUTION_VERBS = (
    "advised", "suggested", "decided", "said", "stated", "recommended",
    "proposed", "intended", "chose", "described", "rejected", "confirmed",
    "claimed", "reported", "determined", "concluded", "requested",
)
_ACTOR_PHRASE = r"(?:the\s+)?(?:[A-Z][a-z]+(?:\s[A-Z][a-z]+)*|[a-z]+(?:\s[a-z]+){0,3})"

_ATTR_BY_RE = re.compile(r"\bby\s+(" + _ACTOR_PHRASE + r")\b", re.IGNORECASE)
_ATTR_VERB_RE = re.compile(
    r"\b(" + _ACTOR_PHRASE + r")\s+(?:" + "|".join(_ATTRIBUTION_VERBS) + r")\b"
)


def extract_actor(text: str) -> str | None:
    m = _ATTR_BY_RE.search(text)
    if m:
        return normalize_text(m.group(1))
    m = _ATTR_VERB_RE.search(text)
    if m:
        return normalize_text(m.group(1))
    return None


def check_attribution(claim: str, source: str) -> tuple[bool, str | None]:
    claim_actor = extract_actor(claim)
    if not claim_actor:
        return False, None
    for sentence in relevant_sentences(claim, source):
        source_actor = extract_actor(sentence)
        if source_actor and source_actor != claim_actor:
            # Only a real conflict if the two actor phrases don't share their
            # head word (avoids "the team" vs "the wider team" false hits).
            if not (set(claim_actor.split()) & set(source_actor.split())):
                return True, sentence
    return False, None


# ----------------------------------------------------------------------------
# §5.5 Polarity/assertion and §5.7 Prohibited opposites.
# ----------------------------------------------------------------------------

_NEGATION_CUES = (
    "not", "never", "no longer", "does not", "did not", "won't", "will not",
    "rejected", "declined", "denies", "denied", "ruled out", "against",
    "without",
)

_OPPOSITE_PAIRS = [
    ("confirmed", "unconfirmed"), ("free", "paid"), ("active", "benched"),
    ("active", "inactive"), ("allowed", "prohibited"), ("approved", "rejected"),
    ("current", "historical"), ("accepted", "declined"), ("open", "closed"),
    ("internal", "external"), ("chosen", "rejected"),
]


def check_polarity(claim: str, source: str) -> tuple[bool, str | None]:
    claim_norm = normalize_text(claim)
    for sentence in relevant_sentences(claim, source):
        sent_norm = normalize_text(sentence)
        for cue in _NEGATION_CUES:
            if cue in sent_norm and cue not in claim_norm:
                # A negation cue in a sentence that otherwise shares claim
                # content is evidence the source denies/opposes what the
                # claim asserts positively.
                return True, sentence
    return False, None


def check_prohibited_opposite(claim: str, source: str) -> tuple[bool, str | None]:
    claim_norm = normalize_text(claim)
    for sentence in relevant_sentences(claim, source):
        sent_norm = normalize_text(sentence)
        for a, b in _OPPOSITE_PAIRS:
            if a in claim_norm and b in sent_norm:
                return True, sentence
            if b in claim_norm and a in sent_norm:
                return True, sentence
    return False, None


# ----------------------------------------------------------------------------
# §5.6 Temporal / status validity.
# ----------------------------------------------------------------------------

_CURRENT_MARKERS = (
    "currently", "is considering", "are considering", "ongoing", "still open",
    "unresolved", "exploring", "in progress", "under review",
)
_SETTLED_MARKERS = (
    "finalized", "closed", "settled", "completed", "historical",
    "concluded", "not up for reconsideration", "already decided",
    "previously", "last month", "last year", "last quarter",
)


def check_temporal(claim: str, source: str) -> tuple[bool, str | None]:
    claim_norm = normalize_text(claim)
    claim_current = any(m in claim_norm for m in (normalize_text(x) for x in _CURRENT_MARKERS))
    claim_settled = any(m in claim_norm for m in (normalize_text(x) for x in _SETTLED_MARKERS))
    for sentence in relevant_sentences(claim, source):
        sent_norm = normalize_text(sentence)
        sent_settled = any(m in sent_norm for m in (normalize_text(x) for x in _SETTLED_MARKERS))
        sent_current = any(m in sent_norm for m in (normalize_text(x) for x in _CURRENT_MARKERS))
        if claim_current and sent_settled:
            return True, sentence
        if claim_settled and sent_current and not claim_current:
            return True, sentence
    return False, None


# ----------------------------------------------------------------------------
# §5.3 Essential / composite qualifiers.
# ----------------------------------------------------------------------------

_QUALIFIER_MARKERS = (
    "only", "except", "unless", "not up for reconsideration", "explicitly",
    "exclusively", "provided that", "as long as", "must", "required",
    "before any", "pending", "tentative", "provisional",
)


def check_essential_qualifier(claim: str, source: str) -> tuple[bool, str | None]:
    claim_norm = normalize_text(claim)
    for sentence in relevant_sentences(claim, source):
        sent_norm = normalize_text(sentence)
        for marker in _QUALIFIER_MARKERS:
            m_norm = normalize_text(marker)
            if m_norm in sent_norm and m_norm not in claim_norm:
                # The qualifying clause itself must be substantially absent
                # from the claim (not just the keyword) to count as dropped.
                qualifier_words = content_words(sentence) - content_words(claim)
                if len(qualifier_words) >= 2:
                    return True, sentence
    return False, None


# ----------------------------------------------------------------------------
# §5.2 List coverage.
# ----------------------------------------------------------------------------

_LIST_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9' ]*?),\s*([A-Za-z][A-Za-z0-9' ]*?),?\s*(?:and|or)\s+([A-Za-z][A-Za-z0-9' ]+)"
)


def extract_list_items(claim: str) -> list[str]:
    m = _LIST_RE.search(claim)
    if not m:
        return []
    items = []
    for group in m.groups():
        # Keep only the final short noun phrase of each comma segment.
        piece = group.strip().split(",")[-1].strip()
        words = piece.split()
        piece = " ".join(words[-3:]) if len(words) > 3 else piece
        if piece:
            items.append(piece)
    return items


def check_list_coverage(claim: str, source: str) -> tuple[bool, str | None, list[str]]:
    items = extract_list_items(claim)
    if len(items) < 2:
        return False, None, []
    missing = []
    for item in items:
        item_words = content_words(item)
        if not item_words:
            continue
        found = any(item_words <= content_words(s) for s in split_sentences(source))
        if not found:
            missing.append(item)
    return (len(missing) > 0), (missing[0] if missing else None), items


# ----------------------------------------------------------------------------
# §5.8 Locality.
# ----------------------------------------------------------------------------

def check_locality(claim: str, source: str, list_items: list[str]) -> tuple[bool, str | None]:
    """Where a claim stitches together >=2 elements, each element's support
    must come from the same paragraph. Scattered support across disconnected
    paragraphs is the locality defect."""
    paragraphs = split_paragraphs(source)
    if len(paragraphs) < 2:
        return False, None

    elements = list_items if list_items else []
    if not elements:
        # Generic two-clause check: does the claim assert two distinct
        # propositions (split on "and"/"," at the top level) that only find
        # combined support across different paragraphs?
        clauses = [c.strip() for c in re.split(r"\band\b|,", claim) if len(c.strip()) > 8]
        elements = clauses[:3]
    if len(elements) < 2:
        return False, None

    support_paragraphs = set()
    for element in elements:
        words = content_words(element)
        if not words:
            continue
        for idx, para in enumerate(paragraphs):
            if words & content_words(para):
                support_paragraphs.add(idx)
                break
    if len(support_paragraphs) >= 2:
        evidence = " | ".join(paragraphs[i][:120] for i in sorted(support_paragraphs))
        return True, evidence
    return False, None


# ----------------------------------------------------------------------------
# §5.9 Source-contract defect.
# ----------------------------------------------------------------------------

_EXCLUSION_MARKERS = (
    "excluded from this source", "not among this source", "not declared as",
    "not independently verified", "explicitly excluded",
)


def check_source_contract(claim: str, source: str) -> tuple[bool, str | None]:
    for sentence in relevant_sentences(claim, source):
        sent_norm = normalize_text(sentence)
        for marker in _EXCLUSION_MARKERS:
            if normalize_text(marker) in sent_norm:
                return True, sentence
    return False, None


# ----------------------------------------------------------------------------
# §5.1 Normalization.
# ----------------------------------------------------------------------------

def check_normalization(claim: str, source: str) -> tuple[bool, str | None]:
    import difflib
    sentence = best_sentence(claim, source)
    if not sentence:
        return False, None
    claim_norm = normalize_text(claim)
    sent_norm = normalize_text(sentence)
    if claim_norm == sent_norm and claim.strip() != sentence.strip():
        return True, sentence
    ratio = difflib.SequenceMatcher(None, claim_norm, sent_norm).ratio()
    if ratio >= 0.92 and claim_norm != sent_norm:
        return False, None  # near-identical but not a pure representation change; not asserted
    return False, None


# ----------------------------------------------------------------------------
# Top-level deterministic detection.
# ----------------------------------------------------------------------------

def detect(candidate_claim: str, source_text: str) -> dict:
    """Deterministic implementation of the frozen §6.1 output contract.
    Runs every §5 check; any NOT-SUPPORTED-triggering check that fires wins
    the verdict. normalization is the only SUPPORTED-side tag."""
    tags: list[str] = []
    evidences: list[str] = []
    not_supported = False

    fired, ev = check_attribution(candidate_claim, source_text)
    if fired:
        tags.append("attribution"); evidences.append(ev); not_supported = True

    fired, ev = check_polarity(candidate_claim, source_text)
    if fired:
        tags.append("polarity_assertion"); evidences.append(ev); not_supported = True

    fired, ev = check_prohibited_opposite(candidate_claim, source_text)
    if fired:
        tags.append("prohibited_opposite"); evidences.append(ev); not_supported = True

    fired, ev = check_temporal(candidate_claim, source_text)
    if fired:
        tags.append("temporal_status"); evidences.append(ev); not_supported = True

    fired, ev = check_essential_qualifier(candidate_claim, source_text)
    if fired:
        tags.append("essential_qualifier"); evidences.append(ev); not_supported = True

    list_missing, list_ev, list_items = check_list_coverage(candidate_claim, source_text)
    if list_missing:
        tags.append("list_coverage"); evidences.append(list_ev or "missing list member"); not_supported = True

    fired, ev = check_locality(candidate_claim, source_text, list_items)
    if fired:
        tags.append("locality"); evidences.append(ev); not_supported = True

    fired, ev = check_source_contract(candidate_claim, source_text)
    if fired:
        tags.append("source_contract"); evidences.append(ev); not_supported = True

    fired, ev = check_normalization(candidate_claim, source_text)
    if fired:
        tags.append("normalization"); evidences.append(ev)

    if not_supported:
        verdict = "NOT SUPPORTED"
    else:
        claim_words = content_words(candidate_claim)
        source_words = content_words(source_text)
        coverage = len(claim_words & source_words) / max(1, len(claim_words))
        verdict = "SUPPORTED" if coverage >= 0.6 else "NOT SUPPORTED"

    if not evidences:
        evidences = [best_sentence(candidate_claim, source_text) or "(no overlapping source content found)"]

    result = {"verdict": verdict, "reason_tags": tags, "evidence": " ; ".join(dict.fromkeys(evidences))}
    assert result["verdict"] in ALLOWED_VERDICTS
    assert result["verdict"] != FORBIDDEN_AS_VERDICT_OR_TAG
    for t in result["reason_tags"]:
        assert t in ALLOWED_TAGS
        assert t != FORBIDDEN_AS_VERDICT_OR_TAG
    return result


def source_available(source_paths: list[str]) -> bool:
    return all(Path(p).is_file() for p in source_paths)


def score_real_item(item_id: str, candidate_claim: str, source_paths: list[str], source_text: str | None) -> dict:
    """SOURCE_UNAVAILABLE is decided BEFORE the detector runs -- zero cost,
    fixed positional slot preserved, never a detector verdict or tag."""
    if not source_available(source_paths):
        return {"item_id": item_id, "status": "SOURCE_UNAVAILABLE", "result": None}
    result = detect(candidate_claim, source_text or "")
    return {"item_id": item_id, "status": "OK", "result": result}


# ----------------------------------------------------------------------------
# Rehearsal -- constructed synthetic fixtures ONLY. Never real TTROS content.
# ----------------------------------------------------------------------------

REHEARSAL_FIXTURES = [
    {
        "id": "r1-normalization",
        "claim": "The clients plan is a 90 day pilot before any long term commitment.",
        "source": "The client's plan is a 90-day pilot before any long-term commitment.",
        "expected_verdict": "SUPPORTED",
        "expected_tags_any": ["normalization"],
    },
    {
        "id": "r2-list-coverage",
        "claim": "The toolkit covers onboarding, billing, and reporting.",
        "source": "The toolkit covers onboarding and billing for new customers.",
        "expected_verdict": "NOT SUPPORTED",
        "expected_tags_any": ["list_coverage"],
    },
    {
        "id": "r3-essential-qualifier",
        "claim": "The pilot is free for new customers.",
        "source": (
            "The pilot is free for new customers, but only for the first 90 days and "
            "only within the UK region."
        ),
        "expected_verdict": "NOT SUPPORTED",
        "expected_tags_any": ["essential_qualifier"],
    },
    {
        "id": "r4-attribution",
        "claim": "The finance team decided to delay the launch.",
        "source": "The engineering lead decided to delay the launch due to a testing gap.",
        "expected_verdict": "NOT SUPPORTED",
        "expected_tags_any": ["attribution"],
    },
    {
        "id": "r5-polarity",
        "claim": "The team currently offers a discount to new customers.",
        "source": "The team does not offer a discount to new customers this quarter.",
        "expected_verdict": "NOT SUPPORTED",
        "expected_tags_any": ["polarity_assertion"],
    },
    {
        "id": "r6-temporal",
        "claim": "The pricing review is still open and unresolved.",
        "source": "The pricing review was finalized and closed last month.",
        "expected_verdict": "NOT SUPPORTED",
        "expected_tags_any": ["temporal_status"],
    },
    {
        "id": "r7-prohibited-opposite",
        "claim": "The vendor contract is confirmed.",
        "source": "The vendor contract remains unconfirmed pending legal review.",
        "expected_verdict": "NOT SUPPORTED",
        "expected_tags_any": ["prohibited_opposite"],
    },
    {
        "id": "r8-locality",
        "claim": "The new hire has approved budget and finished onboarding.",
        "source": (
            "Section A: The new hire has approved budget for their role this quarter.\n\n"
            "Section B, an unrelated update: a separate contractor finished onboarding "
            "last quarter."
        ),
        "expected_verdict": "NOT SUPPORTED",
        "expected_tags_any": ["locality"],
    },
    {
        "id": "r9-source-contract",
        "claim": "This document gives full visibility into the vendor's internal pricing model.",
        "source": (
            "The vendor's internal pricing model is discussed only in an internal memo "
            "explicitly excluded from this source and not among this source's own "
            "declared content."
        ),
        "expected_verdict": "NOT SUPPORTED",
        "expected_tags_any": ["source_contract"],
    },
    {
        "id": "r10-multitag",
        "claim": "Liam is currently considering offering a free tier, as advised by the team.",
        "source": (
            "A marketing contractor suggested TTROS might eventually offer a free tier. "
            "Liam explicitly rejected this and confirmed pricing stays paid-only. That "
            "decision was finalized in August and is not up for reconsideration."
        ),
        "expected_verdict": "NOT SUPPORTED",
        "expected_tags_any": [
            "attribution", "polarity_assertion", "prohibited_opposite", "temporal_status",
        ],
    },
    {
        "id": "r11-plain-supported-no-tags",
        "claim": "The pilot lasts 90 days.",
        "source": "The pilot lasts 90 days for all new customers.",
        "expected_verdict": "SUPPORTED",
        "expected_tags_any": [],
    },
]


def run_rehearsal() -> dict:
    outcomes = []
    for fx in REHEARSAL_FIXTURES:
        result = detect(fx["claim"], fx["source"])
        verdict_ok = result["verdict"] == fx["expected_verdict"]
        tags_hit = sorted(set(result["reason_tags"]) & set(fx["expected_tags_any"]))
        expected_ok = (not fx["expected_tags_any"]) or bool(tags_hit)
        outcomes.append({
            "fixture_id": fx["id"],
            "expected_verdict": fx["expected_verdict"],
            "expected_tags_any": fx["expected_tags_any"],
            "actual_result": result,
            "verdict_matched": verdict_ok,
            "expected_tags_hit": tags_hit,
            "fixture_pass": verdict_ok and expected_ok,
        })
    all_tags_hit = set()
    verdict_directions_hit = set()
    for o in outcomes:
        all_tags_hit |= set(o["expected_tags_hit"])
        verdict_directions_hit.add(o["actual_result"]["verdict"])
    return {
        "outcomes": outcomes,
        "all_fixtures_pass": all(o["fixture_pass"] for o in outcomes),
        "all_nine_tags_hit": sorted(all_tags_hit),
        "tags_missing": sorted(ALLOWED_TAGS - all_tags_hit),
        "verdict_directions_hit": sorted(verdict_directions_hit),
        "both_directions_hit": verdict_directions_hit == {"SUPPORTED", "NOT SUPPORTED"},
    }


def run_source_unavailable_mechanical_test() -> dict:
    """SOURCE_UNAVAILABLE tested mechanically as a source-status convention:
    proves it is reachable as a status and structurally impossible as a
    verdict or tag -- zero detector calls, zero real content."""
    outcome = score_real_item(
        "selftest-missing-source", "irrelevant claim",
        ["/nonexistent/path/does-not-exist.md"], None,
    )
    return {
        "status_returned": outcome["status"],
        "expected_status": "SOURCE_UNAVAILABLE",
        "pass": outcome["status"] == "SOURCE_UNAVAILABLE" and outcome["result"] is None,
        "structurally_excluded_from_verdicts": FORBIDDEN_AS_VERDICT_OR_TAG not in ALLOWED_VERDICTS,
        "structurally_excluded_from_tags": FORBIDDEN_AS_VERDICT_OR_TAG not in ALLOWED_TAGS,
    }


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "rehearse"
    if cmd == "rehearse":
        r = run_rehearsal()
        su = run_source_unavailable_mechanical_test()
        out = {"rehearsal": r, "source_unavailable_mechanical_test": su}
        print(json.dumps(out, indent=2))
        ok = r["all_fixtures_pass"] and r["both_directions_hit"] and not r["tags_missing"] and su["pass"]
        sys.exit(0 if ok else 1)
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)
