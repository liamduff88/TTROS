#!/usr/bin/env python3
"""Capture deterministic local dashboard screenshots and browser error evidence.

Revisit: when the dashboard URL, proof viewports, or Playwright contract changes. · Last touched: 2026-07-12.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:3010/")
    parser.add_argument("--output", required=True)
    parser.add_argument("--viewports", default="1440x1000,1100x850")
    parser.add_argument("--view", default="Cockpit")
    parser.add_argument("--heading", default="")
    parser.add_argument("--selector", default="[data-lane-card]")
    parser.add_argument("--expected-count", type=int, default=5)
    parser.add_argument("--item", default="")
    parser.add_argument("--sweep", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    viewports = []
    for value in args.viewports.split(","):
        width, height = value.lower().split("x", 1)
        viewports.append((int(width), int(height)))

    report = {"url": args.url, "viewports": [], "console_errors": [], "page_errors": [], "http_errors": []}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width, height in viewports:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.on("console", lambda message: report["console_errors"].append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
            page.on(
                "response",
                lambda response: report["http_errors"].append({"status": response.status, "url": response.url})
                if response.status >= 400 else None,
            )
            response = page.goto(args.url, wait_until="domcontentloaded")
            sweep_rows = []
            if args.sweep:
                destinations = [
                    ("Cockpit", "Cockpit"),
                    ("Work Queue", "Agentic OS Work Queue"),
                    ("Workflow Bench", "Workflow Bench"),
                    ("Message Board", "Message Board"),
                    ("Skills Board", "Skills Board"),
                    ("Memory Board", "Memory Board"),
                    ("Prompt Library", "Prompt Library"),
                    ("Graphify", "Graphify"),
                    ("Repo Ingest", "Repo Ingest"),
                    ("Results & Receipts", "Activity & Receipts"),
                    ("Tokens & ROI", "Tokens & ROI"),
                    ("Artifacts", "Artifacts"),
                    ("Connections / Spine", "Connections / Spine"),
                    ("Mission Control", "Mission Control"),
                    ("Settings / Launchers", "Settings / Launchers"),
                ]
                for label, heading in destinations:
                    page.get_by_role("button", name=label, exact=True).click()
                    page.get_by_role("heading", name=heading).wait_for(timeout=20000)
                    page.wait_for_timeout(500)
                    sweep_rows.append({"destination": label, "heading": heading, "reachable": True})
            if args.view == "Cockpit":
                page.get_by_role("tab", name="Cockpit").click()
            else:
                page.get_by_role("button", name=args.view, exact=True).click()
            page.get_by_role("heading", name=args.heading or args.view).wait_for()
            if args.item:
                page.get_by_text(args.item, exact=True).first.click()
            page.wait_for_timeout(12000)
            lane_cards = page.locator(args.selector).count()
            needs_me_count = page.locator("[data-testid=needs-me-count]").inner_text()
            body_box = page.locator("body").bounding_box() or {}
            viewport_report = {
                "width": width,
                "height": height,
                "status": response.status if response else None,
                "lane_cards": lane_cards,
                "needs_me_count": needs_me_count,
                "body_width": body_box.get("width"),
                "scroll_width": page.evaluate("document.documentElement.scrollWidth"),
                "client_width": page.evaluate("document.documentElement.clientWidth"),
                "destinations": sweep_rows,
            }
            screenshot = output / f"dashboard-{width}x{height}.png"
            page.screenshot(path=str(screenshot), full_page=True)
            viewport_report["screenshot"] = screenshot.as_posix()
            report["viewports"].append(viewport_report)
            page.close()
        browser.close()
    report["pass"] = (
        not report["console_errors"]
        and not report["page_errors"]
        and not report["http_errors"]
        and all(row["status"] == 200 and row["lane_cards"] >= args.expected_count and row["scroll_width"] <= row["client_width"] and (not args.sweep or len(row["destinations"]) == 15) for row in report["viewports"])
    )
    (output / "browser-proof.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
