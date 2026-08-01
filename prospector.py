#!/usr/bin/env python3
"""Operational entry point for the existing Agentic OS prospecting engine.

This is deliberately a thin coordinator.  Prospect reconciliation, ledger
snapshots, Gmail draft-only effects, and human-review cards remain owned by
``workflows/prospecting_daily_run/outreach_handoff.py``.

Revisit: after the first three real runs or when the V3.1 handoff changes. · Last touched: 2026-07-31.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.aos_queue_storage import durable_replace_text
from tools.business_brain_context import ScopedBrainLoader
from workflows.prospecting_daily_run.outreach_handoff import (
    PROSPECTS_PATH,
    WORK_ITEMS_PATH,
    _read_jsonl,
    import_handoff,
    parse_handoff,
    reconcile_prospect,
    validate_handoff,
)

DEFAULT_HANDOFF = ROOT / "workflows/prospecting_daily_run/input/TTR_ICP_A_OUTREACH_HANDOFF_2026-07-22_METRO_VANCOUVER_MSP_RECRUITMENT.md"
CONTEXT_POINTERS = (
    "business_brain:index/MEMORY_INDEX.md",
    "business_brain:memory/ideal_clients.md",
    "business_brain:memory/ideal_clients_A.md",
    "business_brain:memory/ideal_clients_B.md",
    "business_brain:memory/prospecting_rotation_plan.md",
    "business_brain:memory/prospecting_query_bank.md",
    "business_brain:memory/prospecting_scoring_contract.md",
    "business_brain:memory/positioning.md",
    "business_brain:memory/offers.md",
)
USER_AGENT = "TTROS-Agentic-OS/1.0 public-signal-verification"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_ref(value: str) -> str:
    return _sha(value)[:16]


def _verify_url(url: str, timeout: int = 15) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.getcode() or 0)
            response.read(512)
        return {"url": url, "reachable": 200 <= status < 400, "http_status": status}
    except urllib.error.HTTPError as exc:
        return {"url": url, "reachable": False, "http_status": int(exc.code), "failure_class": "http_error"}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"url": url, "reachable": False, "http_status": None, "failure_class": "transport_unavailable"}


def _load_context(loader: ScopedBrainLoader | None = None) -> list[dict[str, Any]]:
    result = (loader or ScopedBrainLoader()).retrieve(
        work={"client_scope": "global", "business_output": True},
        pointers=CONTEXT_POINTERS,
    )
    return result.brain_context_used


def _cards_for_source(root: Path, source_hash: str) -> list[dict[str, Any]]:
    cards = []
    for item in _read_jsonl(root / WORK_ITEMS_PATH):
        review = item.get("outreach_review") if isinstance(item.get("outreach_review"), dict) else {}
        if review.get("source_hash") == source_hash:
            cards.append(item)
    return cards


def _safe_packages(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packages = []
    for item in cards:
        review = item.get("outreach_review") or {}
        prospect = review.get("prospect") or {}
        packages.append({
            "review_item_id": item.get("id"),
            "queue_status": item.get("status"),
            "prospect_reference": _safe_ref(str(prospect.get("prospect_id") or "")),
            "person_name": prospect.get("person_name"),
            "company_name": prospect.get("company_name"),
            "channel": review.get("channel"),
            "stage": review.get("stage"),
            "score": review.get("score"),
            "primary_signal": review.get("primary_signal"),
            "reconciliation": review.get("reconciliation"),
            "gmail_draft_reference": review.get("gmail_draft_reference"),
            "linkedin_profile_url": review.get("profile_url"),
            "manual_action_required": True,
            "external_action_performed": False,
        })
    return packages


def _render_artifact(result: dict[str, Any]) -> str:
    lines = [
        "# Prospecting operational package",
        "> Revisit: when this review package is resolved. · Last touched: 2026-07-31.",
        "",
        f"- Work item: {result['work_item_id']}",
        "- Lane/profile: revenue / aos-revenue",
        f"- Business Brain context notes read: {len(result['brain_context_used'])}",
        f"- Public signals checked: {len(result['signal_verification'])}",
        f"- Prospect packages: {len(result['prospect_packages'])}",
        f"- Duplicate replay prospects: {len(result['engine_result'].get('duplicate_replay_prospects') or [])}",
        "- External sends/messages/posts: 0",
        "- Gmail authority: draft-only",
        "- Queue gate: human review / Needs Me",
        "",
        "## Review packages",
    ]
    for package in result["prospect_packages"]:
        channel = package.get("channel") or "unknown"
        lines.extend((
            "",
            f"### {package.get('person_name')} — {package.get('company_name')}",
            f"- Review item: {package.get('review_item_id')}",
            f"- Channel/stage: {channel} / {package.get('stage')}",
            f"- Score: {package.get('score')}",
            f"- Signal: {package.get('primary_signal')}",
            f"- Gmail draft reference: {package.get('gmail_draft_reference') or 'not applicable'}",
            f"- LinkedIn manual package: {'ready' if channel == 'linkedin' else 'available as inactive fallback only'}",
            "- Action: Liam reviews and acts manually; Agentic OS did not send or post.",
        ))
    lines.extend(("", "Token usage: unavailable from current CLI output.", ""))
    return "\n".join(lines)


def _render_receipt(result: dict[str, Any]) -> str:
    all_reachable = all(row.get("reachable") for row in result["signal_verification"])
    return "\n".join((
        "PASS" if result["status"] == "PASS" else "NEEDS ATTENTION",
        "",
        f"Work item ID: {result['work_item_id']}",
        "Lane: revenue",
        "Profile requested: aos-revenue",
        "Profile used: aos-revenue",
        f"Brain context: {len(result['brain_context_used'])} scoped notes retrieved with provenance",
        f"Discovery/validation: {len(result['signal_verification'])} public signals checked; all reachable={str(all_reachable).lower()}",
        f"Duplicate/prior-contact controls: {result['reconciliation_summary']}",
        f"Prospect packages: {len(result['prospect_packages'])}",
        f"Gmail drafts ready: {sum(bool(row.get('gmail_draft_reference')) for row in result['prospect_packages'])}",
        f"LinkedIn manual-action packages: {sum(row.get('channel') == 'linkedin' for row in result['prospect_packages'])}",
        "External effects: Gmail draft-only; email sent=0; LinkedIn actions=0; CRM mutations=0",
        "Queue status: human_review / Needs Me",
        "",
        "Artifacts:",
        f"- {result['artifact_path']}",
        f"- {result['private_package_path']}",
        "",
        "Token usage: unavailable from current CLI output.",
        "",
    ))


def run(
    *,
    work_item_id: str,
    handoff: Path = DEFAULT_HANDOFF,
    root: Path = ROOT,
    verify_public_signals: bool = True,
    adapter: Any | None = None,
    context_loader: ScopedBrainLoader | None = None,
) -> dict[str, Any]:
    root = Path(root)
    handoff = Path(handoff)
    brain_context_used = _load_context(context_loader)
    header, prospects, source_hash = parse_handoff(handoff)
    validate_handoff(header, prospects)

    ledger = _read_jsonl(root / PROSPECTS_PATH)
    items = _read_jsonl(root / WORK_ITEMS_PATH)
    reconciliations = [reconcile_prospect(prospect, ledger, items) for prospect in prospects]
    signal_verification = [
        _verify_url(str(prospect.get("primary_signal_source_url") or prospect.get("signal_source_url") or prospect.get("evidence_url") or ""))
        for prospect in prospects
    ] if verify_public_signals else [
        {"url": str(prospect.get("primary_signal_source_url") or prospect.get("signal_source_url") or prospect.get("evidence_url") or ""), "reachable": None, "http_status": None, "failure_class": "verification_not_requested"}
        for prospect in prospects
    ]
    if any(not row.get("url") for row in signal_verification):
        raise ValueError("every prospect requires a public signal URL")

    engine_result = import_handoff(handoff, root=root, adapter=adapter)
    cards = _cards_for_source(root, source_hash)
    packages = _safe_packages(cards)
    if not packages:
        raise RuntimeError("prospecting engine produced no review packages")

    reconciliation_summary = {
        "checked": len(reconciliations),
        "clear": sum(row.get("status") == "clear_for_prepared_action" for row in reconciliations),
        "conflicts": sum(row.get("status") == "conflict" for row in reconciliations),
        "matched_ledger_snapshots": sum(int(row.get("matched_ledger_snapshots") or 0) for row in reconciliations),
        "matched_review_items": sum(int(row.get("matched_review_items") or 0) for row in reconciliations),
    }
    status = "PASS" if engine_result.get("status") == "PASS" and all(row.get("reachable") is not False for row in signal_verification) else "NEEDS ATTENTION"
    artifact_rel = f"workflows/queue_artifacts/{work_item_id}_prospecting_activation.md"
    receipt_rel = f"queue/receipts/{work_item_id}-prospector.md"
    private_rel = f"queue/draft_runtime/prospecting/{work_item_id}.json"
    result: dict[str, Any] = {
        "status": status,
        "work_item_id": work_item_id,
        "workflow": "prospecting_daily_run",
        "lane": "revenue",
        "profile_requested": "aos-revenue",
        "profile_used": "aos-revenue",
        "brain_context_used": brain_context_used,
        "signal_verification": signal_verification,
        "reconciliation_summary": reconciliation_summary,
        "engine_result": engine_result,
        "prospect_packages": packages,
        "queue_status": "human_review",
        "needs_me": True,
        "external_actions": {"gmail_drafts_only": True, "emails_sent": 0, "linkedin_actions": 0, "crm_mutations": 0},
        "artifact_path": artifact_rel,
        "receipt_path": receipt_rel,
        "private_package_path": private_rel,
        "token_usage": {"available": False},
    }
    durable_replace_text(root / private_rel, json.dumps(result, indent=2, sort_keys=True) + "\n")
    durable_replace_text(root / artifact_rel, _render_artifact(result))
    durable_replace_text(root / receipt_rel, _render_receipt(result))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the existing TTROS prospecting engine end to end")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--no-verify-public-signals", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(
            work_item_id=args.work_item_id,
            handoff=args.handoff,
            root=args.root,
            verify_public_signals=not args.no_verify_public_signals,
        )
    except Exception as exc:
        print(json.dumps({"status": "NEEDS ATTENTION", "failure_class": type(exc).__name__, "token_usage": {"available": False}}, sort_keys=True))
        return 2
    safe = {
        "status": result["status"],
        "work_item_id": result["work_item_id"],
        "profile_used": result["profile_used"],
        "brain_context_count": len(result["brain_context_used"]),
        "signals_checked": len(result["signal_verification"]),
        "prospect_packages": len(result["prospect_packages"]),
        "queue_status": result["queue_status"],
        "external_actions": result["external_actions"],
        "artifact_path": result["artifact_path"],
        "receipt_path": result["receipt_path"],
        "token_usage": result["token_usage"],
    }
    print(json.dumps(safe, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
