import json
import tempfile
import unittest
from pathlib import Path

from src.sheets_manual_sync import SheetsManualSyncError, run_manual_sheets_sync


class FakeHttpClient:
    def __init__(self):
        self.posts = []

    def post(self, url, *, json, headers, timeout):
        self.posts.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return {"ok": True}


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def append_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def make_root(directory: str) -> Path:
    root = Path(directory)
    write_json(
        root / "config" / "roles.json",
        {"users": {"1": {"role": "salesperson", "active": True, "salesperson_id": "sp-1", "display_name": "Demo Rep"}}},
    )
    write_json(
        root / "data" / "local_state.json",
        {"salespeople": {"sp-1": {"salesperson_id": "sp-1", "display_name": "Demo Rep", "active": True}}},
    )
    append_jsonl(
        root / "data" / "sales_logs.jsonl",
        [
            {
                "log_id": "log-1",
                "submitted_at": "2026-06-23T12:00:00Z",
                "telegram_user_id": "1",
                "salesperson_id": "sp-1",
                "source": "telegram_dm",
                "raw_text": "CR-V walk-in, test drive, asked for business.",
                "parsed": {
                    "vehicle_interest": "CR-V",
                    "interaction_type": "walk-in",
                    "people_spoken_to": 1,
                    "test_drive": True,
                    "worksheet_or_offer_presented": True,
                    "asked_for_business": True,
                    "outcome": "thinking",
                    "next_step": "follow up tomorrow",
                },
                "missing_fields": [],
                "coaching_flags": [],
                "confidence": 1.0,
                "status": "complete",
                "llm_used": False,
                "llm_tokens_estimate": None,
            }
        ],
    )
    append_jsonl(
        root / "data" / "report_archive.jsonl",
        [
            {
                "report_id": "report-1",
                "generated_at": "2026-06-23T13:00:00Z",
                "report_type": "daily",
                "date": "2026-06-23",
                "summary_metrics": {
                    "total_updates": 1,
                    "active_salespeople": 1,
                    "people_spoken_to": 1,
                    "appointments": 0,
                    "test_drives": 1,
                    "worksheets_offers": 1,
                    "asks_for_business": 1,
                    "outcomes": 1,
                    "followups_due": 0,
                    "missing_incomplete_updates": 0,
                    "coaching_flags": 0,
                },
                "flags": [],
                "llm_used": False,
            }
        ],
    )
    return root


class SheetsManualSyncTests(unittest.TestCase):
    def test_missing_url_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_root(directory)
            http = FakeHttpClient()
            with self.assertRaisesRegex(SheetsManualSyncError, "WEBAPP_URL"):
                run_manual_sheets_sync(
                    root=root,
                    environ={
                        "NORTH_SHORE_SHEETS_PROVIDER": "apps_script_webapp",
                        "NORTH_SHORE_SHEETS_WEBAPP_SECRET": "test-shared-token",
                        "NORTH_SHORE_SHEETS_EXECUTION_ENABLED": "true",
                        "NORTH_SHORE_SHEETS_WRITES_ENABLED": "true",
                    },
                    http_client=http,
                    tab_names=("Raw_Logs", "Report_Archive"),
                )
            self.assertEqual(http.posts, [])

    def test_missing_secret_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_root(directory)
            http = FakeHttpClient()
            with self.assertRaisesRegex(SheetsManualSyncError, "WEBAPP_SECRET"):
                run_manual_sheets_sync(
                    root=root,
                    environ={
                        "NORTH_SHORE_SHEETS_PROVIDER": "apps_script_webapp",
                        "NORTH_SHORE_SHEETS_WEBAPP_URL": "https://example.invalid/north-shore-webapp",
                        "NORTH_SHORE_SHEETS_EXECUTION_ENABLED": "true",
                        "NORTH_SHORE_SHEETS_WRITES_ENABLED": "true",
                    },
                    http_client=http,
                    tab_names=("Raw_Logs", "Report_Archive"),
                )
            self.assertEqual(http.posts, [])

    def test_writes_disabled_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_root(directory)
            http = FakeHttpClient()
            with self.assertRaisesRegex(SheetsManualSyncError, "writes are disabled"):
                run_manual_sheets_sync(
                    root=root,
                    environ={
                        "NORTH_SHORE_SHEETS_PROVIDER": "apps_script_webapp",
                        "NORTH_SHORE_SHEETS_WEBAPP_URL": "https://example.invalid/north-shore-webapp",
                        "NORTH_SHORE_SHEETS_WEBAPP_SECRET": "test-shared-token",
                        "NORTH_SHORE_SHEETS_EXECUTION_ENABLED": "true",
                        "NORTH_SHORE_SHEETS_WRITES_ENABLED": "false",
                    },
                    http_client=http,
                    tab_names=("Raw_Logs", "Report_Archive"),
                )
            self.assertEqual(http.posts, [])

    def test_successful_fake_sync_posts_expected_tabs_and_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = make_root(directory)
            http = FakeHttpClient()
            result = run_manual_sheets_sync(
                root=root,
                environ={
                    "NORTH_SHORE_SHEETS_PROVIDER": "apps_script_webapp",
                    "NORTH_SHORE_SHEETS_WEBAPP_URL": "https://example.invalid/north-shore-webapp",
                    "NORTH_SHORE_SHEETS_WEBAPP_SECRET": "test-shared-token",
                    "NORTH_SHORE_SHEETS_EXECUTION_ENABLED": "true",
                    "NORTH_SHORE_SHEETS_WRITES_ENABLED": "true",
                },
                http_client=http,
                tab_names=("Raw_Logs", "Report_Archive"),
            )
            self.assertEqual(result.tabs, ("Raw_Logs", "Report_Archive"))
            self.assertEqual(result.post_count, 2)
            self.assertEqual([post["json"]["target_tab"] for post in http.posts], ["Raw_Logs", "Report_Archive"])
            self.assertEqual([post["json"]["action"] for post in http.posts], ["append_objects", "append_objects"])
            self.assertTrue(all(isinstance(post["json"]["objects"], tuple) for post in http.posts))
            self.assertTrue(all("X-North-Shore-Sheets-Secret" in post["headers"] for post in http.posts))


if __name__ == "__main__":
    unittest.main()
