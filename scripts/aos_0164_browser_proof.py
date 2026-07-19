#!/usr/bin/env python3
"""Browser proof for AOS-2026-0164 queue/Needs Me behavior.

Revisit: remove after AOS-2026-0164 is accepted. · Last touched: 2026-07-18.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "workflows" / "queue_artifacts" / "AOS-2026-0164-browser-proof"
FRONTEND = "http://127.0.0.1:3010/"
BACKEND_NETLOC = "127.0.0.1:8011"


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {
        "frontend": FRONTEND,
        "backend": f"http://{BACKEND_NETLOC}",
        "checks": {},
        "console_errors": [],
        "expected_console_errors": [],
        "page_errors": [],
    }
    fail_next_status = {"value": False}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda message: report["console_errors"].append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: report["page_errors"].append(str(error)))

        def route_api(route):
            parts = urlsplit(route.request.url)
            if fail_next_status["value"] and parts.path == "/api/queue/status":
                fail_next_status["value"] = False
                route.fulfill(status=503, content_type="application/json", body='{"detail":"controlled queue refresh failure"}')
                return
            route.continue_(url=urlunsplit(("http", BACKEND_NETLOC, parts.path, parts.query, "")))

        page.route("**/api/**", route_api)
        response = page.goto(FRONTEND, wait_until="domcontentloaded")
        page.get_by_test_id("sidebar").get_by_role("button", name="Work Queue", exact=True).click()
        page.get_by_role("heading", name="Agentic OS Work Queue").wait_for(timeout=20_000)
        page.locator('[data-queue-card-id="AOS-2026-0160"]').wait_for(timeout=20_000)
        initial_cards = page.locator("[data-queue-card-id]").count()
        report["checks"]["initial_load"] = {
            "http_status": response.status if response else None,
            "cards": initial_cards,
            "aos_0160_visible": page.locator('[data-queue-card-id="AOS-2026-0160"]').count() == 1,
            "aos_0160_text": page.locator('[data-queue-card-id="AOS-2026-0160"]').inner_text(),
        }

        page.locator("body").click(position={"x": 500, "y": 500})
        page.keyboard.press("Slash")
        expand_items = page.get_by_role("button", name="Expand work items", exact=True)
        if expand_items.count() and expand_items.is_visible():
            expand_items.click()
        page.get_by_text("Needs Me — human review & needs input, newest first", exact=False).wait_for()
        needs_cards = page.locator("[data-queue-card-id]").count()
        report["checks"]["needs_me_shortcut"] = {"cards": needs_cards, "opened": needs_cards > 0}

        artifact_card = page.locator('[data-queue-card-id="AOS-2026-0130"]')
        artifact_card.click()
        selected = page.locator('[data-testid="queue-selected-detail"][data-selected-item-id="AOS-2026-0130"]')
        selected.wait_for(timeout=20_000)
        inline = page.locator('[data-testid="inline-primary-artifact"]')
        inline.wait_for(timeout=20_000)
        collapsed_text = inline.inner_text()
        expand = inline.get_by_role("button", name="Expand output in place")
        expand.click()
        expanded_text = inline.inner_text()
        report["checks"]["inline_artifact"] = {
            "collapsed_chars": len(collapsed_text),
            "expanded_chars": len(expanded_text),
            "expanded_in_place": len(expanded_text) > len(collapsed_text),
            "internal_handoff_hidden": page.locator('[data-testid="manual-handoff-details"]').count() == 0,
        }

        page.get_by_role("button", name="Cockpit", exact=True).click()
        page.get_by_role("heading", name="Cockpit").wait_for()
        page.get_by_test_id("sidebar").get_by_role("button", name="Work Queue", exact=True).click()
        page.get_by_role("heading", name="Agentic OS Work Queue").wait_for()
        page.locator('[data-queue-card-id="AOS-2026-0160"]').wait_for(timeout=20_000)
        report["checks"]["navigation_reload"] = {"cards": page.locator("[data-queue-card-id]").count()}

        counts_before_error = page.get_by_text("Status counts", exact=True).locator("xpath=../..").inner_text()
        fail_next_status["value"] = True
        page.get_by_role("button", name="Refresh", exact=True).click()
        page.get_by_text("Queue load failed", exact=True).wait_for(timeout=10_000)
        counts_after_error = page.get_by_text("Status counts", exact=True).locator("xpath=../..").inner_text()
        report["checks"]["failed_refresh_preserves_counts"] = {
            "preserved": counts_after_error == counts_before_error,
            "before": counts_before_error,
            "after": counts_after_error,
        }

        review_tile = page.get_by_role("button", name=re.compile(r"^human review\s+\d+$", re.IGNORECASE))
        review_before = review_tile.inner_text()
        fixture_card = page.locator('[data-queue-card-id="AOS-2026-0163"]')
        fixture_card.click()
        page.locator('[data-testid="queue-selected-detail"][data-selected-item-id="AOS-2026-0163"]').wait_for(timeout=20_000)
        page.get_by_role("button", name="Approve", exact=True).click()
        page.wait_for_timeout(2_000)
        review_after = page.get_by_role("button", name=re.compile(r"^human review\s+\d+$", re.IGNORECASE)).inner_text()
        report["checks"]["automatic_mutation_refresh"] = {
            "before": review_before,
            "after": review_after,
            "changed": review_before != review_after,
        }

        page.get_by_role("button", name="Refresh", exact=True).click()
        page.get_by_text("Queue load failed", exact=True).wait_for(state="hidden", timeout=10_000)

        screenshot = OUTPUT / "dashboard-1440x1000.png"
        page.screenshot(path=str(screenshot), full_page=True)
        report["screenshot"] = screenshot.relative_to(ROOT).as_posix()
        browser.close()

    checks = report["checks"]
    expected_console = [
        message for message in report["console_errors"]
        if "503 (Service Unavailable)" in message
    ]
    report["expected_console_errors"] = expected_console
    unexpected_console = [
        message for message in report["console_errors"]
        if message not in expected_console
    ]
    report["pass"] = all((
        checks["initial_load"]["http_status"] == 200,
        checks["initial_load"]["cards"] > 100,
        checks["initial_load"]["aos_0160_visible"],
        "—" in checks["initial_load"]["aos_0160_text"],
        checks["needs_me_shortcut"]["opened"],
        checks["inline_artifact"]["expanded_in_place"],
        checks["inline_artifact"]["internal_handoff_hidden"],
        checks["navigation_reload"]["cards"] > 100,
        checks["failed_refresh_preserves_counts"]["preserved"],
        checks["automatic_mutation_refresh"]["changed"],
        len(expected_console) == 1,
        not unexpected_console,
        not report["page_errors"],
    ))
    proof = OUTPUT / "browser-proof.json"
    proof.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
