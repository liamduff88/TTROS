#!/usr/bin/env python3
"""Disposable browser proof for the AOS-2026-0168 review-card contract repair."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "workflows" / "queue_artifacts" / "AOS-2026-0168_contract_repair_browser_proof"
FRONTEND = os.environ.get("AOS_BROWSER_PROOF_FRONTEND", "http://127.0.0.1:3010")


def fixture_item(status: str = "human_review", *, detailed: bool = False) -> dict:
    item = {
        "id": "AOS-FIXTURE-REVIEW",
        "title": "Review the repaired local routing contract",
        "lane": "operations",
        "owner": "codex",
        "workbench": "codex",
        "owner_type": "agent",
        "status": status,
        "priority": 8,
        "source": "local_fixture",
        "created_at": "2026-07-18T21:00:00Z",
        "updated_at": "2026-07-18T21:01:00Z",
        "summary_for_operator": "The actual routing repair passed focused validation.",
    }
    if detailed:
        item.update({
            "detail_loaded": True,
            "review_details": {
                "summary": "The actual routing repair passed focused validation.",
                "failure_explanation": "",
                "worker": "codex",
                "attempts": 2,
                "validation": "Routing, orchestration, queue, backend, and frontend fixtures passed.",
                "token_usage_lines": [
                    "Total input: 120",
                    "Cached input: 90",
                    "Non-cached input: 30",
                    "Output: 18",
                ],
                "receipt_path": "queue/receipts/AOS-FIXTURE-REVIEW.md",
                "receipt_content": "PASS\n\nACTUAL SUBSTANTIVE RECEIPT\n\nValidation:\n- focused browser fixture passed",
            },
            "latest_receipt": {
                "path": "queue/receipts/AOS-FIXTURE-REVIEW.md",
                "available": True,
                "content": "PASS\n\nACTUAL SUBSTANTIVE RECEIPT\n\nValidation:\n- focused browser fixture passed",
            },
            "primary_artifact": {
                "path": "workflows/queue_artifacts/AOS-FIXTURE-REVIEW_result.md",
                "available": True,
                "content": "CONSOLIDATED ACTUAL ARTIFACT\nDirect review-card proof.",
            },
        })
    return item


def mock_api(page: Page, state: dict) -> None:
    def respond(route):
        request = route.request
        path = urlsplit(request.url).path
        if path == "/api/queue/status":
            payload = {"success": True, "counts": {state["status"]: 1}, "next": fixture_item(state["status"])}
        elif path == "/api/queue/items" and request.method == "GET":
            payload = {"success": True, "items": [fixture_item(state["status"])]}
        elif path == "/api/queue/items/AOS-FIXTURE-REVIEW" and request.method == "GET":
            state["detail_gets"] += 1
            payload = {"success": True, "item": fixture_item(state["status"], detailed=True)}
        elif path == "/api/queue/items/AOS-FIXTURE-REVIEW/review-note" and request.method == "POST":
            body = json.loads(request.post_data or "{}")
            state["note_requests"].append(body)
            payload = {
                "success": True,
                "ok": True,
                "status": state["status"],
                "state_changed": False,
                "token_usage_text": "Token usage: no agent invocation",
                "item": fixture_item(state["status"], detailed=True),
            }
        elif path == "/api/queue/items/AOS-FIXTURE-REVIEW/review-close" and request.method == "POST":
            body = json.loads(request.post_data or "{}")
            state["close_requests"].append(body)
            if body == {"status": "done", "review_note": "Browser approval note", "action": "approve"}:
                state["status"] = "done"
            payload = {
                "success": True,
                "ok": True,
                "status": state["status"],
                "item": fixture_item(state["status"], detailed=True),
            }
        elif path == "/api/health":
            payload = {"ok": True}
        else:
            payload = {"success": True}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    page.route("**/api/**", respond)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    state = {"status": "human_review", "detail_gets": 0, "note_requests": [], "close_requests": []}
    report = {
        "frontend": FRONTEND,
        "fixture": "disposable local Playwright API interception; no historical queue mutation",
        "checks": {},
        "screenshots": [],
        "console_errors": [],
        "page_errors": [],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        mock_api(page, state)
        page.add_init_script("window.sessionStorage.clear(); window.localStorage.clear();")
        page.on("console", lambda message: report["console_errors"].append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        page.goto(FRONTEND, wait_until="domcontentloaded")
        page.get_by_test_id("sidebar").get_by_role("button", name="Work Queue", exact=True).click()
        page.get_by_role("heading", name="Agentic OS Work Queue", exact=True).wait_for(timeout=20_000)
        card = page.locator('[data-review-card-id="AOS-FIXTURE-REVIEW"]')
        card.wait_for(timeout=20_000)
        card.get_by_text("ACTUAL SUBSTANTIVE RECEIPT", exact=False).wait_for(timeout=20_000)

        report["checks"]["actual_content"] = {
            "detail_gets": state["detail_gets"],
            "receipt_visible": card.get_by_text("ACTUAL SUBSTANTIVE RECEIPT", exact=False).is_visible(),
            "artifact_visible": card.get_by_text("CONSOLIDATED ACTUAL ARTIFACT", exact=False).is_visible(),
            "summary_visible": card.get_by_text("actual routing repair passed", exact=False).is_visible(),
            "worker_visible": card.get_by_text("codex", exact=True).count() > 0,
            "attempts_visible": card.get_by_text("2", exact=True).count() > 0,
            "validation_visible": card.get_by_text("Routing, orchestration", exact=False).is_visible(),
            "token_usage_visible": card.get_by_text("Total input: 120", exact=False).is_visible(),
            "full_receipt_link": card.get_by_role("link", name="Full receipt", exact=True).count(),
            "full_artifact_link": card.get_by_role("link", name="Full artifact", exact=True).count(),
            "generic_save_attach": card.get_by_role("button", name="Save/Attach", exact=True).count(),
            "status_selects": card.locator("select").count(),
        }
        before = OUTPUT / "review-card-actual-receipt.png"
        card.screenshot(path=str(before))
        report["screenshots"].append(before.relative_to(ROOT).as_posix())

        note = card.get_by_label("Review note for AOS-FIXTURE-REVIEW", exact=True)
        note.fill("Browser note")
        card.get_by_role("button", name="Save review note", exact=True).click()
        card.get_by_text("Status is still human review", exact=False).wait_for(timeout=20_000)
        report["checks"]["note_save"] = {
            "request": state["note_requests"],
            "status_after_save": state["status"],
            "card_still_visible": card.is_visible(),
            "close_request_count": len(state["close_requests"]),
        }

        note.fill("Browser approval note")
        dialogs = []
        page.once("dialog", lambda dialog: (dialogs.append(dialog.message), dialog.accept()))
        card.get_by_role("button", name="Approve", exact=True).click()
        page.locator('[data-review-card-id="AOS-FIXTURE-REVIEW"]').wait_for(state="detached", timeout=20_000)
        report["checks"]["explicit_approve"] = {
            "confirmation_messages": dialogs,
            "request": state["close_requests"],
            "status_after_approve": state["status"],
            "review_card_remaining": page.locator('[data-review-card-id="AOS-FIXTURE-REVIEW"]').count(),
        }
        after = OUTPUT / "review-card-after-explicit-approve.png"
        page.screenshot(path=str(after), full_page=True)
        report["screenshots"].append(after.relative_to(ROOT).as_posix())
        browser.close()

    checks = report["checks"]
    passed = (
        all(value for key, value in checks["actual_content"].items() if key not in {"generic_save_attach", "status_selects"})
        and checks["actual_content"]["generic_save_attach"] == 0
        and checks["actual_content"]["status_selects"] == 0
        and checks["note_save"]["status_after_save"] == "human_review"
        and checks["note_save"]["close_request_count"] == 0
        and checks["explicit_approve"]["status_after_approve"] == "done"
        and len(checks["explicit_approve"]["request"]) == 1
        and checks["explicit_approve"]["review_card_remaining"] == 0
        and bool(checks["explicit_approve"]["confirmation_messages"])
        and not report["console_errors"]
        and not report["page_errors"]
    )
    report["result"] = "PASS" if passed else "NEEDS ATTENTION"
    (OUTPUT / "browser-proof.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
