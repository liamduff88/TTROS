#!/usr/bin/env python3
"""Capture focused local browser proof for the integrated lane workspace.

Revisit: remove after AOS-2026-0173 and parent AOS-2026-0169 are accepted. · Last touched: 2026-07-18.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "workflows" / "queue_artifacts" / "AOS-2026-0173_browser_proof"
FRONTEND = "http://127.0.0.1:3010"

ITEMS = [
    {
        "id": "OPS-REVIEW",
        "title": "Review the integrated lane workspace",
        "lane": "operations",
        "owner": "codex",
        "workbench": "codex",
        "owner_type": "agent",
        "status": "human_review",
        "updated_at": "2026-07-18T20:07:00Z",
    },
    {
        "id": "OPS-INPUT",
        "title": "Provide the required local answer",
        "lane": "operations",
        "owner": "codex",
        "workbench": "codex",
        "owner_type": "agent",
        "status": "needs_input",
        "updated_at": "2026-07-18T20:06:00Z",
    },
    {
        "id": "OPS-READY-1",
        "title": "Run the first ready item",
        "lane": "operations",
        "owner": "codex",
        "workbench": "codex",
        "status": "agent_todo",
        "updated_at": "2026-07-18T20:05:00Z",
    },
    {
        "id": "OPS-READY-2",
        "title": "Run the second ready item",
        "lane": "operations",
        "owner": "codex",
        "workbench": "codex",
        "status": "inbox",
        "updated_at": "2026-07-18T20:04:00Z",
    },
    {
        "id": "OPS-BLOCKED",
        "title": "Blocked local workflow",
        "lane": "operations",
        "owner": "codex",
        "workbench": "codex",
        "status": "blocked",
        "blocked_reason": "Waiting for the local fixture prerequisite.",
        "updated_at": "2026-07-18T20:03:00Z",
    },
    {
        "id": "OPS-DONE",
        "title": "Completed local workflow",
        "lane": "operations",
        "owner": "codex",
        "workbench": "codex",
        "status": "done",
        "updated_at": "2026-07-18T20:02:00Z",
    },
    {
        "id": "OPS-CANCELLED",
        "title": "Cancelled local workflow",
        "lane": "operations",
        "owner": "codex",
        "workbench": "codex",
        "status": "cancelled",
        "updated_at": "2026-07-18T20:01:00Z",
    },
    {
        "id": "MKT-OUTSIDE-LANE",
        "title": "Must not appear in operations",
        "lane": "marketing",
        "owner": "codex",
        "workbench": "codex",
        "status": "human_review",
        "updated_at": "2026-07-18T20:08:00Z",
    },
]

COUNTS = {
    "inbox": 1,
    "agent_todo": 1,
    "agent_working": 0,
    "needs_input": 1,
    "human_review": 1,
    "blocked": 1,
    "done": 1,
    "cancelled": 1,
}


def lane_activity() -> list[dict]:
    rows = []
    for lane in ("marketing", "revenue", "delivery", "operations", "unassigned"):
        lane_items = [item for item in ITEMS if item.get("lane") == lane]
        lane_counts = {
            status: sum(item.get("status") == status for item in lane_items)
            for status in COUNTS
        }
        rows.append(
            {
                "lane": lane,
                "items": lane_items,
                "counts": lane_counts,
                "current_assigned_work": [
                    item for item in lane_items if item.get("status") in {"agent_todo", "agent_working"}
                ],
                "last_completed_item": next(
                    (item for item in lane_items if item.get("status") == "done"), None
                ),
                "latest_receipt": None,
                "latest_artifact": None,
                "token_usage": {"state": "unavailable"},
                "last_successful_run": None,
                "shortcut": {"workbench": "codex"},
                "degraded": False,
            }
        )
    return rows


def mock_api(page: Page) -> None:
    def respond(route):
        path = urlsplit(route.request.url).path
        if path == "/api/queue/items":
            payload = {"success": True, "items": ITEMS}
        elif path == "/api/queue/summary":
            payload = {"success": True, "counts": COUNTS, "needsMeItems": []}
        elif path == "/api/dashboard/cockpit":
            payload = {
                "counts": COUNTS,
                "needs_me": [],
                "lane_activity": lane_activity(),
                "recent_output": [],
                "tokens": {"strip": {}},
                "backup": {},
            }
        elif path == "/api/health":
            payload = {"ok": True}
        elif path == "/api/overview":
            payload = {}
        else:
            payload = {"success": True}
        route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))

    page.route("**/api/**", respond)


def dimensions(page: Page) -> dict:
    return page.evaluate(
        """() => {
          const root = document.documentElement
          const main = document.querySelector('main')
          const workspace = document.querySelector('[data-lane-workspace]')
          const mainBox = main?.getBoundingClientRect()
          const workspaceBox = workspace?.getBoundingClientRect()
          return {
            document_client_width: root.clientWidth,
            document_scroll_width: root.scrollWidth,
            main_client_width: main?.clientWidth ?? null,
            main_scroll_width: main?.scrollWidth ?? null,
            workspace_left: workspaceBox?.left ?? null,
            workspace_right: workspaceBox?.right ?? null,
            main_left: mainBox?.left ?? null,
            main_right: mainBox?.right ?? null,
          }
        }"""
    )


def prepare_page(browser, width: int, height: int) -> Page:
    page = browser.new_page(viewport={"width": width, "height": height})
    mock_api(page)
    page.add_init_script("window.sessionStorage.clear(); window.localStorage.clear();")
    return page


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {
        "frontend": FRONTEND,
        "fixture": "local Playwright API interception only",
        "checks": {},
        "screenshots": [],
        "console_errors": [],
        "page_errors": [],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        desktop = prepare_page(browser, 1440, 1000)
        desktop.on(
            "console",
            lambda message: report["console_errors"].append(message.text)
            if message.type == "error"
            else None,
        )
        desktop.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        response = desktop.goto(f"{FRONTEND}/", wait_until="domcontentloaded")
        desktop.get_by_test_id("sidebar").get_by_role("button", name="Cockpit", exact=True).click()
        desktop.get_by_role("heading", name="Cockpit", exact=True).wait_for(timeout=20_000)
        desktop.locator("[data-lane-card]").first.wait_for(timeout=20_000)

        operations_card = desktop.locator('[data-lane-card="operations"]')
        card_tag = operations_card.evaluate("element => element.tagName")
        card_href = operations_card.get_attribute("href")
        card_buttons = operations_card.locator("button").count()
        separate_queue_cta = operations_card.get_by_text("Open filtered queue", exact=False).count()
        report["checks"]["cockpit_lane_navigation"] = {
            "lane_cards": desktop.locator("[data-lane-card]").count(),
            "operations_card_tag": card_tag,
            "operations_card_href": card_href,
            "nested_buttons": card_buttons,
            "separate_queue_cta": separate_queue_cta,
        }
        operations_card.scroll_into_view_if_needed()
        screenshot = OUTPUT / "desktop-cockpit-1440x1000.png"
        desktop.screenshot(path=str(screenshot))
        report["screenshots"].append(screenshot.relative_to(ROOT).as_posix())

        operations_card.click()
        desktop.locator('[data-lane-workspace="operations"]').wait_for(timeout=20_000)
        desktop.wait_for_url("**/lane/operations")
        filter_rows = desktop.locator("[data-lane-filter]")
        filter_ids = filter_rows.evaluate_all(
            "elements => elements.map(element => element.dataset.laneFilter)"
        )
        filter_counts = {
            filter_id: desktop.locator(
                f'[data-lane-filter-count="{filter_id}"]'
            ).inner_text()
            for filter_id in filter_ids
        }
        default_filter = desktop.locator('[data-lane-filter][aria-pressed="true"]').get_attribute(
            "data-lane-filter"
        )
        visible_default_ids = desktop.locator("[data-lane-action-card-id]").evaluate_all(
            "elements => elements.map(element => element.dataset.laneActionCardId)"
        )
        report["checks"]["lane_filters_and_default"] = {
            "url": desktop.url,
            "filter_ids": filter_ids,
            "counts": filter_counts,
            "default_filter": default_filter,
            "visible_item_ids": visible_default_ids,
            "outside_lane_visible": desktop.get_by_text("MKT-OUTSIDE-LANE", exact=False).count(),
        }

        review_wrapper = desktop.locator('[data-lane-action-card-id="OPS-REVIEW"]')
        review_card = review_wrapper.locator('[data-review-card-id="OPS-REVIEW"]')
        review_body = review_card.locator("[data-review-card-body]")
        review_actions = {
            label: review_wrapper.get_by_role("button", name=label, exact=True).count()
            for label in ("Approve", "Needs changes", "Reject")
        }
        review_structure = review_wrapper.evaluate(
            """wrapper => {
              const card = wrapper.querySelector('[data-review-card-id="OPS-REVIEW"]')
              const approve = [...wrapper.querySelectorAll('button')].find(button => button.textContent.trim() === 'Approve')
              return { card_contains_approve: card.contains(approve), wrapper_contains_both: Boolean(card && approve) }
            }"""
        )
        report["checks"]["human_review_card"] = {
            "card_visible": review_card.is_visible(),
            "body_visible": review_body.is_visible(),
            "receipt_field": review_card.get_by_label("Receipt for OPS-REVIEW").count(),
            "status_select": review_card.get_by_label("Review-close status for OPS-REVIEW").count(),
            "save_attach": review_card.get_by_role("button", name="Save/Attach", exact=True).count(),
            "required_lane_actions": review_actions,
            **review_structure,
        }
        screenshot = OUTPUT / "desktop-lane-needs-me-1440x1000.png"
        desktop.screenshot(path=str(screenshot))
        report["screenshots"].append(screenshot.relative_to(ROOT).as_posix())

        desktop.locator('[data-lane-filter="to_run"]').click()
        desktop.locator('[data-lane-results="to_run"]').wait_for()
        ready_ids = desktop.locator("[data-lane-action-card-id]").evaluate_all(
            "elements => elements.map(element => element.dataset.laneActionCardId)"
        )
        desktop.get_by_label("Select OPS-READY-1", exact=True).check()
        selected_text = desktop.locator('[data-lane-selection="to_run"]').inner_text()
        report["checks"]["ready_selection"] = {
            "visible_item_ids": ready_ids,
            "item_checkboxes": desktop.locator(
                '[data-lane-results="to_run"] input[type="checkbox"]'
            ).count(),
            "select_all": desktop.get_by_label(
                "Select all current-filter ready items", exact=True
            ).count(),
            "selected_text": selected_text,
            "run_selected_enabled": desktop.get_by_role(
                "button", name="Run selected", exact=True
            ).is_enabled(),
            "cancel_selected_enabled": desktop.get_by_role(
                "button", name="Cancel selected", exact=True
            ).is_enabled(),
            "per_item_run": desktop.locator('[data-lane-action="run"]').count(),
            "per_item_cancel": desktop.locator('[data-lane-action="cancel"]').count(),
        }
        screenshot = OUTPUT / "desktop-lane-ready-1440x1000.png"
        desktop.screenshot(path=str(screenshot))
        report["screenshots"].append(screenshot.relative_to(ROOT).as_posix())

        desktop.locator('[data-lane-filter="blocked"]').click()
        desktop.locator('[data-blocked-reason="OPS-BLOCKED"]').wait_for()
        report["checks"]["blocked_item"] = {
            "reason": desktop.locator('[data-blocked-reason="OPS-BLOCKED"]').inner_text(),
            "unblock_button": desktop.locator('[data-lane-action="unblock"]').count(),
            "unblock_enabled": desktop.get_by_role("button", name="Unblock", exact=True).is_enabled(),
        }
        screenshot = OUTPUT / "desktop-lane-blocked-1440x1000.png"
        desktop.screenshot(path=str(screenshot))
        report["screenshots"].append(screenshot.relative_to(ROOT).as_posix())
        desktop.close()

        narrow = prepare_page(browser, 390, 844)
        narrow.on(
            "console",
            lambda message: report["console_errors"].append(message.text)
            if message.type == "error"
            else None,
        )
        narrow.on("pageerror", lambda error: report["page_errors"].append(str(error)))
        narrow.goto(f"{FRONTEND}/lane/operations", wait_until="domcontentloaded")
        narrow.get_by_role("button", name="Collapse sidebar", exact=True).click()
        narrow.get_by_role("button", name="Collapse Needs Me", exact=True).click()
        narrow.locator('[data-lane-workspace="operations"]').wait_for(timeout=20_000)
        narrow.locator('[data-lane-filter="needs_me"]').click()
        narrow.locator('[data-review-card-id="OPS-REVIEW"]').wait_for()
        narrow_dimensions = dimensions(narrow)
        report["checks"]["narrow_layout"] = {
            "viewport": {"width": 390, "height": 844},
            "sidebar_collapsed": narrow.get_by_test_id("sidebar").get_attribute("data-collapsed"),
            "needs_me_collapsed": narrow.get_by_test_id("needs-me-rail").get_attribute(
                "data-collapsed"
            ),
            **narrow_dimensions,
        }
        screenshot = OUTPUT / "narrow-lane-needs-me-390x844.png"
        narrow.screenshot(path=str(screenshot))
        report["screenshots"].append(screenshot.relative_to(ROOT).as_posix())
        narrow.close()
        browser.close()

    checks = report["checks"]
    expected_filters = ["needs_me", "to_run", "blocked", "all_active", "done", "cancelled"]
    expected_counts = {
        "needs_me": "2",
        "to_run": "2",
        "blocked": "1",
        "all_active": "5",
        "done": "1",
        "cancelled": "1",
    }
    narrow = checks["narrow_layout"]
    report["pass"] = all(
        (
            response is not None and response.status == 200,
            checks["cockpit_lane_navigation"]["lane_cards"] == 5,
            checks["cockpit_lane_navigation"]["operations_card_tag"] == "A",
            checks["cockpit_lane_navigation"]["operations_card_href"] == "/lane/operations",
            checks["cockpit_lane_navigation"]["nested_buttons"] == 0,
            checks["cockpit_lane_navigation"]["separate_queue_cta"] == 0,
            checks["lane_filters_and_default"]["filter_ids"] == expected_filters,
            checks["lane_filters_and_default"]["counts"] == expected_counts,
            checks["lane_filters_and_default"]["default_filter"] == "needs_me",
            checks["lane_filters_and_default"]["visible_item_ids"]
            == ["OPS-REVIEW", "OPS-INPUT"],
            checks["lane_filters_and_default"]["outside_lane_visible"] == 0,
            checks["human_review_card"]["card_visible"],
            checks["human_review_card"]["body_visible"],
            checks["human_review_card"]["receipt_field"] == 1,
            checks["human_review_card"]["status_select"] == 1,
            checks["human_review_card"]["save_attach"] == 1,
            all(value == 1 for value in checks["human_review_card"]["required_lane_actions"].values()),
            not checks["human_review_card"]["card_contains_approve"],
            checks["human_review_card"]["wrapper_contains_both"],
            set(checks["ready_selection"]["visible_item_ids"])
            == {"OPS-READY-1", "OPS-READY-2"},
            checks["ready_selection"]["item_checkboxes"] == 2,
            checks["ready_selection"]["select_all"] == 1,
            "1 selected in current filter" in checks["ready_selection"]["selected_text"],
            checks["ready_selection"]["run_selected_enabled"],
            checks["ready_selection"]["cancel_selected_enabled"],
            checks["ready_selection"]["per_item_run"] == 2,
            checks["ready_selection"]["per_item_cancel"] == 2,
            checks["blocked_item"]["reason"] == "Waiting for the local fixture prerequisite.",
            checks["blocked_item"]["unblock_button"] == 1,
            checks["blocked_item"]["unblock_enabled"],
            narrow["document_scroll_width"] <= narrow["document_client_width"],
            narrow["main_scroll_width"] <= narrow["main_client_width"],
            narrow["workspace_left"] >= narrow["main_left"],
            narrow["workspace_right"] <= narrow["main_right"] + 1,
            not report["console_errors"],
            not report["page_errors"],
        )
    )
    proof = OUTPUT / "browser-proof.json"
    proof.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
