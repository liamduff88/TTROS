#!/usr/bin/env python3
"""Step 5 -- deterministic canonical-map generator.

Generates `.hermes.md` at the repo root from `canonical.manifest`, growing
ONE canonical fact class at a time (manifest id order, declared before any
B7 rescoring -- not chosen after seeing scores).

Per-class extraction is marker-based (finds known substrings and slices
between them), not line-number based, so it fails loudly (KeyError/ValueError)
if a source file's structure has drifted, rather than silently mis-extracting.

Reads are vault reads (direct, allowed). Nothing is written to the vault by
this script. The only write is the repo-root `.hermes.md` plus an immutable
archive copy.

Usage:
  step5_map_generator.py generate --classes 1-9   [--dry-run]
  step5_map_generator.py generate --classes 1-3   [--dry-run]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path("/home/liam/agentic-os-live")
VAULT = Path("/mnt/c/Users/Admin/Documents/A-Time to revenue/TTROS Business Brain")
MANIFEST_PATH = ROOT / "canonical.manifest"
HERMES_MD_PATH = ROOT / ".hermes.md"
ARCHIVE_DIR = Path("/home/liam/ttros_backups/step5_maps")

NOT_ALLOWED_REQUIRED_LINE = (
    "Do not claim that Liam/TTR has niched down; company scope is settled broad."
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_vault(rel_path: str) -> str:
    return (VAULT / rel_path).read_text(encoding="utf-8")


def strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.index("\n---\n", 4)
        return text[end + 5 :]
    return text


def slice_between(body: str, start_marker: str, end_marker: str | None) -> str:
    start = body.index(start_marker)
    if end_marker is None:
        return body[start:].strip()
    end = body.index(end_marker, start)
    return body[start:end].strip()


def cut_before(body: str, marker: str) -> str:
    """Everything before the first occurrence of marker."""
    idx = body.index(marker)
    return body[:idx]


# ---------------------------------------------------------------------------
# Prompt-injection scan (bounds: "Context files pass a prompt-injection scan")
# ---------------------------------------------------------------------------

INJECTION_PATTERNS = [
    r"ignore (all|previous|prior) instructions",
    r"disregard (all|previous|prior) instructions",
    r"you are now",
    r"system prompt",
    r"</?(system|assistant|user)>",
    r"act as (?:if you|a) ",
    r"jailbreak",
    r"reveal your instructions",
]
INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def injection_scan(text: str) -> list[str]:
    hits = []
    for pat in INJECTION_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            hits.append(f"{pat!r} @ offset {m.start()}: {text[max(0, m.start()-30):m.start()+30]!r}")
    return hits


# ---------------------------------------------------------------------------
# Per-class extraction (manifest id order, fixed before any B7 rescoring)
# ---------------------------------------------------------------------------

def class_1_business_model() -> str:
    body = strip_frontmatter(read_vault("memory/company.md"))
    body = cut_before(body, "\n\nTODO:")
    lines = [
        l for l in body.splitlines()
        if not l.startswith("# Company") and not l.startswith("Revisit:")
    ]
    return "\n".join(lines).strip()


def class_2_offers() -> str:
    body = strip_frontmatter(read_vault("memory/offers.md"))
    body = cut_before(body, "\n\nTODO:")
    ladder = slice_between(body, "Ladder", "What TTR builds")
    principles = slice_between(body, "Principles", None)
    return ladder + "\n\n" + principles


def class_3_delivery() -> str:
    body = strip_frontmatter(read_vault("memory/delivery_model.md"))
    body = cut_before(body, "\n\nTODO:")
    direction = slice_between(body, "Current delivery direction", "Manual-first rule:")
    approval = slice_between(body, "Human approval required for:", None)
    return direction + "\n\n" + approval


def class_4_icp() -> str:
    positioning = strip_frontmatter(read_vault("memory/positioning.md"))
    register = slice_between(positioning, "Register discipline:", "Buyer:")
    buyer = slice_between(positioning, "Buyer:", "Anchors:")
    anchors = slice_between(positioning, "Anchors:", "Proof strategy:")
    positioning_part = buyer + "\n\n" + register + "\n\n" + anchors

    ideal_clients = strip_frontmatter(read_vault("memory/ideal_clients.md"))
    router = cut_before(ideal_clients, "Shared rules:")
    router_lines = [
        l for l in router.splitlines()
        if not l.startswith("# ") and not l.startswith("> Revisit")
    ]
    router_part = "\n".join(router_lines).strip()
    return positioning_part + "\n\n" + router_part


def class_5_not_allowed_to_claim() -> str:
    offers = strip_frontmatter(read_vault("memory/offers.md"))
    offers_claim = slice_between(offers, "Do not claim:", None)

    positioning = strip_frontmatter(read_vault("memory/positioning.md"))
    scope_settled = slice_between(positioning, "Scope settled broad", "Do not claim:")
    positioning_claim = slice_between(positioning, "Do not claim:", None)

    company = strip_frontmatter(read_vault("memory/company.md"))
    company_claim_full = slice_between(company, "Do not claim:", None)
    company_claim = cut_before(company_claim_full, "<!--").strip()

    delivery = strip_frontmatter(read_vault("memory/delivery_model.md"))
    delivery_do = slice_between(delivery, "Do not do:", None)

    current_priorities = read_vault("operating_context/current_priorities.md")
    begin = "<!-- TTROS:HERMES:current_priorities:BEGIN -->"
    end = "<!-- TTROS:HERMES:current_priorities:END -->"
    market_scope_block = current_priorities[
        current_priorities.index(begin) + len(begin) : current_priorities.index(end)
    ].strip()
    # Drop the "## Verified Fact" / provenance-quote scaffolding; keep the fact prose.
    market_scope_fact = market_scope_block.split("\n\n")[-1].strip()

    return "\n\n".join([
        f"Do not claim (explicit requirement): {NOT_ALLOWED_REQUIRED_LINE}",
        offers_claim,
        scope_settled + "\n\n" + positioning_claim,
        company_claim,
        delivery_do,
        f"Market scope (verified fact, current_priorities.md): {market_scope_fact}",
    ])


def class_6_key_entities_projects() -> str:
    active_projects = strip_frontmatter(read_vault("operating_context/active_projects.md"))
    ap_kept = "\n\n".join([
        "## TTROS Business Brain — live\nDurable business memory root. Keep small, current, commercially useful.",
        "## Agentic OS Live — live\nLocal cockpit, queue, and workflow shell.",
        "## North Shore Sales Coach — live pilot\nIsolated Telegram sales-coaching bot for North Shore Honda.",
        "## Website rebuild — live\nSystems-led repositioning of timetorevenue.com. See memory/website_and_content.md.",
        "## LinkedIn prospecting engine — live hardening\nRevenue-owned, queue-aware, ledger-backed, draft-only, and approval-gated.",
        "## Benched\n- CCI/TRACC AI BD system — memory preserved; no active work unless Liam reactivates.\n"
        "- Lead Gen Workflow V4.1 — lives in ChatGPT; blueprint preserved for possible Agentic OS rebuild.",
    ])

    clients = strip_frontmatter(read_vault("memory/clients.md"))
    clients_kept = "\n\n".join([
        "## Active pilot: North Shore Honda\n"
        "- Contact: Ryan McVeigh, Sales Manager. Dealership connected to Dilawri group.\n"
        "- Project: North Shore Sales Coach (see memory/north_shore_sales_coach.md).\n"
        "- Principle: the tool should feel like coaching support, not surveillance.\n"
        "- Salespeople use Telegram DM only; no Sheet access. Ryan gets admin group + Google Sheet dashboard.\n"
        "- If proven, potentially repeatable across other dealerships.",
        "## Benched: CCI / TRACC (Competitive Capabilities International)\n"
        "- AI-powered BD intelligence system (\"Loss Mirror\" thesis: encode CCI's operational-excellence expertise into a diagnostic layer over public data).\n"
        "- Contacts: Ollie (sales lead, primary contact), Graham (Operations Director), Kenneth Moodley (independent contractor, original introduction; referral arrangement).\n"
        "- Stage naming: Stage 1a/1b/2a/2/3 (old Flow A/B/C labels retired — never use them).",
    ])

    nssc = strip_frontmatter(read_vault("memory/north_shore_sales_coach.md"))
    nssc_kept = cut_before(nssc, "\n\nTODO:").strip()
    nssc_lines = [l for l in nssc_kept.splitlines() if not l.startswith("# ")]
    nssc_kept = "\n".join(nssc_lines).strip()

    aos = strip_frontmatter(read_vault("memory/agentic_os.md"))
    identity_line = "Agentic OS Live is Liam's local operator cockpit and workflow shell."
    memory_boundary = slice_between(aos, "Memory boundary:", "Do not touch without explicit scope:")
    do_not_touch = slice_between(aos, "Do not touch without explicit scope:", "\n\nTODO:")
    aos_kept = identity_line + "\n\n" + memory_boundary + "\n\n" + do_not_touch

    sales_rev = strip_frontmatter(read_vault("memory/sales_and_revenue.md"))
    leadgen = slice_between(sales_rev, "## Lead Gen Workflow V4.1", "\n\nTODO:")

    return "\n\n".join([ap_kept, clients_kept, nssc_kept, aos_kept, leadgen])


def class_7_settled_decisions() -> str:
    decisions = strip_frontmatter(read_vault("decisions/DECISIONS.md"))
    durable = slice_between(decisions, "## Durable Decisions", "## 2026-07-16")
    dated_entry = slice_between(
        decisions,
        "## 2026-07-16 — Integrate the LinkedIn prospecting engine as Revenue v0",
        "## Decision Log Format",
    )
    pointer = (
        "Market-scope filing: see the not-allowed-to-claim class (class 5) for the settled "
        "2026-09-03 broad-scope filing recorded against current_priorities.md. Not duplicated here."
    )
    return "\n\n".join([durable, dated_entry, pointer])


def class_8_brain_taxonomy_pointers() -> str:
    index = strip_frontmatter(read_vault("index/MEMORY_INDEX.md"))
    protected = strip_frontmatter(read_vault("operating_context/protected_paths.md"))
    return index.strip() + "\n\n" + protected.strip()


def class_9_career() -> str:
    return strip_frontmatter(read_vault("memory/career.md")).strip()


CLASS_EXTRACTORS = {
    1: ("business_model", class_1_business_model),
    2: ("offers", class_2_offers),
    3: ("delivery", class_3_delivery),
    4: ("icp", class_4_icp),
    5: ("not_allowed_to_claim", class_5_not_allowed_to_claim),
    6: ("key_entities_projects", class_6_key_entities_projects),
    7: ("settled_decisions", class_7_settled_decisions),
    8: ("brain_taxonomy_pointers", class_8_brain_taxonomy_pointers),
    9: ("career", class_9_career),
}

CLASS_HEADINGS = {
    1: "## Business model",
    2: "## Offers",
    3: "## Delivery",
    4: "## Ideal client / positioning",
    5: "## Not allowed to claim",
    6: "## Key entities and projects",
    7: "## Settled decisions",
    8: "## Brain taxonomy pointers",
    9: "## Career",
}


def load_manifest() -> dict:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    # Only need n_classes for the assertion; class bodies are hand-declared
    # above per the manifest's own "extract" instructions (read at generation
    # time, not memorized), so a change to canonical.manifest's class *content*
    # instructions requires updating CLASS_EXTRACTORS, and this assertion
    # catches a change to *how many* classes exist.
    m = re.search(r"^n_classes:\s*(\d+)", text, re.MULTILINE)
    if not m:
        raise ValueError("canonical.manifest: n_classes not found")
    return {"n_classes": int(m.group(1)), "sha256": sha256_file(MANIFEST_PATH)}


def generate_map(k: int) -> tuple[str, list[str]]:
    """Returns (map_text, injection_hits)."""
    manifest = load_manifest()
    if k < 1 or k > manifest["n_classes"]:
        raise ValueError(f"k={k} out of range 1..{manifest['n_classes']}")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    header = [
        "<!-- GENERATED by scripts/step5_map_generator.py -- do not hand-edit. -->",
        f"<!-- generated_at_utc: {now} -->",
        f"<!-- source_manifest: canonical.manifest sha256={manifest['sha256']} -->",
        f"<!-- classes_included: 1..{k} of {manifest['n_classes']} (manifest id order) -->",
        "# TTR / TTROS canonical map",
        "",
    ]
    body_parts = []
    for cid in range(1, k + 1):
        name, fn = CLASS_EXTRACTORS[cid]
        content = fn()
        body_parts.append(f"{CLASS_HEADINGS[cid]}\n\n{content}")
    full_text = "\n".join(header) + "\n\n".join(body_parts) + "\n"
    hits = injection_scan(full_text)
    return full_text, hits


def cmd_generate(args: argparse.Namespace) -> int:
    lo, hi = (int(x) for x in args.classes.split("-")) if "-" in args.classes else (int(args.classes), int(args.classes))
    assert lo == 1, "growth always starts at class 1 (manifest id order, no cherry-picking)"
    k = hi
    map_text, hits = generate_map(k)
    surviving_bytes = len(map_text.encode("utf-8"))

    print(f"k={k} classes included (1..{k}). Surviving byte count: {surviving_bytes} B.")
    if hits:
        print("INJECTION SCAN: HITS FOUND -- refusing to write:", file=sys.stderr)
        for h in hits:
            print(f"  {h}", file=sys.stderr)
        return 3
    print("INJECTION SCAN: clean (0 hits).")

    if args.dry_run:
        print("--dry-run: not writing .hermes.md or archive.")
        print("----- MAP TEXT -----")
        print(map_text)
        return 0

    manifest = load_manifest()
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = ARCHIVE_DIR / f"{ts}_map_k{k}.hermes.md"
    sidecar_path = ARCHIVE_DIR / f"{ts}_map_k{k}.meta.json"
    if archive_path.exists():
        print(f"REFUSING to overwrite existing archive {archive_path}", file=sys.stderr)
        return 2
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(map_text, encoding="utf-8")
    archive_path.chmod(0o444)
    sidecar_path.write_text(json.dumps({
        "generated_at_utc": ts,
        "classes_included": list(range(1, k + 1)),
        "source_manifest_sha256": manifest["sha256"],
        "map_sha256": sha256_text(map_text),
        "surviving_bytes": surviving_bytes,
    }, indent=2), encoding="utf-8")
    sidecar_path.chmod(0o444)

    HERMES_MD_PATH.write_text(map_text, encoding="utf-8")
    print(f"Wrote {HERMES_MD_PATH} ({surviving_bytes} B).")
    print(f"Archived: {archive_path}")
    print(f"Sidecar: {sidecar_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_gen = sub.add_parser("generate")
    p_gen.add_argument("--classes", required=True, help="e.g. 1-3 or 1")
    p_gen.add_argument("--dry-run", action="store_true")
    p_gen.set_defaults(func=cmd_generate)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
