import inspect
import unittest
from unittest.mock import MagicMock

from src import apps_script_webapp_provider as provider
from src import sheets_adapter


def sample_request(tab_name="Raw_Logs"):
    return sheets_adapter.SheetWriteRequest(
        tab_name=tab_name,
        headers=("a", "b"),
        rows=(("one", 2),),
    )


class AppsScriptWebAppProviderTests(unittest.TestCase):
    def test_blocked_by_default(self):
        bridge = provider.AppsScriptWebAppProvider(environ={})
        with self.assertRaisesRegex(provider.AppsScriptWebAppProviderError, "PROVIDER|provider"):
            bridge.append_rows((sample_request(),))

    def test_missing_url_fails_closed(self):
        http = MagicMock()
        bridge = provider.AppsScriptWebAppProvider(
            {
                "provider": "apps_script_webapp",
                "execution_enabled": True,
                "writes_enabled": True,
            },
            environ={},
            http_client=http,
        )
        with self.assertRaisesRegex(provider.AppsScriptWebAppProviderError, "WEBAPP_URL"):
            bridge.append_rows((sample_request(),))
        self.assertEqual(http.mock_calls, [])

    def test_non_https_url_fails_closed(self):
        http = MagicMock()
        bridge = provider.AppsScriptWebAppProvider(
            {
                "provider": "apps_script_webapp",
                "webapp_url": "http://example.invalid/north-shore-webapp",
                "execution_enabled": True,
                "writes_enabled": True,
            },
            environ={},
            http_client=http,
        )
        with self.assertRaisesRegex(provider.AppsScriptWebAppProviderError, "HTTPS"):
            bridge.append_objects((sample_request(),))
        self.assertEqual(http.mock_calls, [])

    def test_writes_disabled_blocks_post(self):
        http = MagicMock()
        bridge = provider.AppsScriptWebAppProvider(
            {
                "provider": "apps_script_webapp",
                "webapp_url": "https://example.invalid/north-shore-webapp",
                "webapp_secret": "test-shared-token",
                "execution_enabled": True,
                "writes_enabled": False,
            },
            environ={},
            http_client=http,
        )
        with self.assertRaisesRegex(provider.AppsScriptWebAppProviderError, "writes are disabled"):
            bridge.append_objects((sample_request(),))
        self.assertEqual(http.mock_calls, [])

    def test_status_check_uses_fake_http_without_read_or_write_gate(self):
        http = MagicMock()
        http.post.return_value = {"ok": True}
        bridge = provider.AppsScriptWebAppProvider(
            {
                "provider": "apps_script_webapp",
                "webapp_url": "https://example.invalid/north-shore-webapp",
                "webapp_secret_required": False,
                "execution_enabled": True,
                "reads_enabled": False,
                "writes_enabled": False,
            },
            environ={},
            http_client=http,
            timeout=2.0,
        )
        self.assertEqual(bridge.status_check(), {"ok": True})
        _, kwargs = http.post.call_args
        self.assertEqual(kwargs["json"]["action"], "status")
        self.assertNotIn("_shared_secret", kwargs["json"])
        self.assertEqual(kwargs["timeout"], 2.0)

    def test_allowed_tab_and_action_produces_expected_fake_object_payload(self):
        payload = provider.build_append_objects_payload(
            sample_request("QA_Checks"),
            webapp_url="https://example.invalid/north-shore-webapp",
            request_id="req-1",
            timestamp="2026-06-24T00:00:00+00:00",
        )
        self.assertEqual(payload.url, "https://example.invalid/north-shore-webapp")
        self.assertNotIn("X-North-Shore-Sheets-Secret", payload.headers)
        self.assertNotIn("_shared_secret", payload.body)
        self.assertEqual(payload.body["action"], "append_objects")
        self.assertEqual(payload.body["target_tab"], "QA_Checks")
        self.assertEqual(payload.body["rows"], (("one", 2),))
        self.assertEqual(payload.body["objects"], ({"a": "one", "b": 2},))
        self.assertEqual(payload.body["request_id"], "req-1")
        self.assertEqual(payload.body["timestamp"], "2026-06-24T00:00:00+00:00")

    def test_provider_uses_fake_http_client_only_when_all_gates_are_open(self):
        http = MagicMock()
        bridge = provider.AppsScriptWebAppProvider(
            {
                "provider": "apps_script_webapp",
                "webapp_url": "https://example.invalid/north-shore-webapp",
                "webapp_secret": "test-shared-token",
                "execution_enabled": True,
                "writes_enabled": True,
                "reads_enabled": False,
            },
            environ={},
            http_client=http,
            timeout=3.0,
        )
        bridge.append_objects((sample_request("Users"),))
        self.assertEqual(http.post.call_count, 1)
        _, kwargs = http.post.call_args
        self.assertEqual(kwargs["json"]["target_tab"], "Users")
        self.assertEqual(kwargs["json"]["action"], "append_objects")
        self.assertEqual(kwargs["json"]["rows"], (("one", 2),))
        self.assertEqual(kwargs["json"]["objects"], ({"a": "one", "b": 2},))
        self.assertIn("X-North-Shore-Sheets-Secret", kwargs["headers"])
        self.assertIn("_shared_secret", kwargs["json"])
        self.assertEqual(kwargs["timeout"], 3.0)

    def test_missing_required_secret_fails_closed(self):
        http = MagicMock()
        bridge = provider.AppsScriptWebAppProvider(
            {
                "provider": "apps_script_webapp",
                "webapp_url": "https://example.invalid/north-shore-webapp",
                "execution_enabled": True,
                "writes_enabled": True,
            },
            environ={},
            http_client=http,
        )
        with self.assertRaisesRegex(provider.AppsScriptWebAppProviderError, "WEBAPP_SECRET"):
            bridge.append_objects((sample_request("Users"),))
        self.assertEqual(http.mock_calls, [])

    def test_raw_log_append_uses_append_raw_log_action(self):
        http = MagicMock()
        bridge = provider.AppsScriptWebAppProvider(
            {
                "provider": "apps_script_webapp",
                "webapp_url": "https://example.invalid/north-shore-webapp",
                "webapp_secret": "test-shared-token",
                "execution_enabled": True,
                "writes_enabled": True,
            },
            environ={},
            http_client=http,
        )
        bridge.append_raw_log((sample_request("Raw_Logs"),))
        _, kwargs = http.post.call_args
        self.assertEqual(kwargs["json"]["action"], "append_raw_log")
        self.assertEqual(kwargs["json"]["target_tab"], "Raw_Logs")

    def test_unknown_tab_and_action_fail_closed(self):
        with self.assertRaisesRegex(provider.AppsScriptWebAppProviderError, "action"):
            provider.build_append_objects_payload(
                sample_request("Users"),
                webapp_url="https://example.invalid/north-shore-webapp",
                action="delete_sheet",
            )
        with self.assertRaisesRegex(provider.AppsScriptWebAppProviderError, "target tab"):
            provider.build_append_objects_payload(
                sample_request("Dashboard_Daily"),
                webapp_url="https://example.invalid/north-shore-webapp",
            )
        with self.assertRaisesRegex(provider.AppsScriptWebAppProviderError, "Raw_Logs"):
            provider.build_raw_log_payload(
                sample_request("Users"),
                webapp_url="https://example.invalid/north-shore-webapp",
            )

    def test_reads_are_status_only(self):
        bridge = provider.AppsScriptWebAppProvider(environ={})
        with self.assertRaisesRegex(provider.AppsScriptWebAppProviderError, "status-only"):
            bridge.read(sheets_adapter.SheetReadRequest("Users"))

    def test_no_external_backend_routes_are_imported_or_called(self):
        source = inspect.getsource(provider).lower()
        for forbidden in (
            "import " + "composio",
            "from " + "composio",
            "import " + "requests",
            "import " + "urllib",
            "dashboard/backend",
            "connectors/composio_access_adapter.py",
            "hermes",
            "agentic_os_backend",
            "telegram",
            "openai",
            "anthropic",
            "googleapiclient",
            "spreadsheetapp",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
