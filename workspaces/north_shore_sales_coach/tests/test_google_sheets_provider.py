import inspect
import io
import json
import os
import unittest
from collections import OrderedDict
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from src import google_sheets_provider as provider
from src import sheets_adapter, sheets_sync_adapter


ROOT = Path(__file__).resolve().parents[1]


def empty_payloads():
    headers = sheets_sync_adapter.load_headers()
    return OrderedDict((tab, []) for tab in sheets_sync_adapter.SYNC_TABS)


def empty_requests():
    return sheets_adapter.build_write_requests(empty_payloads())


def fake_credentials_json():
    return json.dumps(
        {
            "type": "service_account",
            "project_id": "example-project",
            "private_key_id": "example-key-id",
            "private_key": "not-real-credential-material",
            "client_email": "north-shore@example-project.iam.gserviceaccount.com",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )


class DirectGoogleSheetsProviderTests(unittest.TestCase):
    def test_defaults_to_disabled_dry_run_without_google_libraries_or_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            validation = provider.validate_config(library_checker=lambda name: False)
        self.assertEqual(validation.provider, "none")
        self.assertTrue(validation.dry_run_only)
        self.assertFalse(validation.can_read_metadata)
        self.assertFalse(validation.can_write)
        self.assertIn("NORTH_SHORE_SHEETS_PROVIDER must be google_sheets_api", "; ".join(validation.messages))
        self.assertFalse(validation.route_locked)
        self.assertEqual(validation.selected_provider, "none")
        self.assertEqual(validation.credential_source, "missing")

    def test_forbidden_providers_fail_route_lock_before_direct_google_preflight(self):
        for selected in ("hermes_native", "composio", "agentic_os_backend", "", "unknown"):
            with self.subTest(provider=selected):
                validation = provider.validate_config(
                    {"provider": selected},
                    environ={},
                    library_checker=lambda name: (_ for _ in ()).throw(AssertionError("library check blocked")),
                    client_builder=lambda: (_ for _ in ()).throw(AssertionError("client builder blocked")),
                )
                self.assertFalse(validation.route_locked)
                self.assertFalse(validation.can_read_metadata)
                self.assertFalse(validation.can_write)
                if selected in {"hermes_native", "composio", "agentic_os_backend"}:
                    self.assertEqual(validation.error_code, "forbidden_provider")
                    self.assertEqual(validation.forbidden_providers_detected, (selected,))
                else:
                    self.assertIn(validation.error_code, {"provider_not_google_sheets_api", "invalid_provider"})

    def test_google_provider_fails_route_lock_when_sheet_id_and_credentials_are_missing(self):
        validation = provider.validate_config(
            {
                "provider": "google_sheets_api",
                "reads_enabled": True,
                "writes_enabled": True,
                "execution_enabled": True,
            },
            environ={},
            library_checker=lambda name: False,
        )
        rendered = "; ".join(validation.messages)
        self.assertFalse(validation.can_read_metadata)
        self.assertFalse(validation.can_write)
        self.assertIn("NORTH_SHORE_GOOGLE_SHEET_ID is missing", rendered)
        self.assertNotIn("Google API libraries are not installed", rendered)
        self.assertFalse(validation.credentials_available)
        self.assertFalse(validation.google_libraries_available)
        self.assertFalse(validation.client_ready)
        self.assertFalse(validation.route_locked)
        self.assertEqual(validation.credential_source, "missing")

    def test_execution_disabled_blocks_client_readiness(self):
        builder = MagicMock(return_value=object())
        validation = provider.validate_config(
            {
                "provider": "google_sheets_api",
                "reads_enabled": True,
                "writes_enabled": True,
                "execution_enabled": False,
            },
            environ={
                "NORTH_SHORE_GOOGLE_SHEET_ID": "sheet-id-must-not-print",
                "NORTH_SHORE_GOOGLE_CREDENTIALS_JSON": fake_credentials_json(),
            },
            library_checker=lambda name: True,
            client_builder=builder,
        )
        self.assertEqual(validation.error_code, "execution_disabled")
        self.assertTrue(validation.route_locked)
        self.assertEqual(validation.credential_source, "package_local_json")
        self.assertFalse(validation.client_ready)
        self.assertFalse(validation.can_read_metadata)
        self.assertFalse(validation.can_write)
        self.assertEqual(builder.mock_calls, [])

    def test_invalid_credentials_json_fails_closed_without_leaking_values(self):
        sensitive_value = '{"private_key":"value-must-not-appear"'
        validation = provider.validate_config(
            {
                "provider": "google_sheets_api",
                "reads_enabled": True,
                "writes_enabled": True,
                "execution_enabled": True,
            },
            environ={
                "NORTH_SHORE_GOOGLE_SHEET_ID": "sheet-id-must-not-print",
                "NORTH_SHORE_GOOGLE_CREDENTIALS_JSON": sensitive_value,
            },
            library_checker=lambda name: True,
        )
        rendered = "; ".join(validation.messages)
        self.assertEqual(validation.error_code, "credentials_json_invalid")
        self.assertFalse(validation.credentials_available)
        self.assertFalse(validation.client_ready)
        self.assertNotIn("value-must-not-appear", rendered)
        self.assertNotIn(sensitive_value, rendered)
        self.assertFalse(validation.route_locked)
        self.assertEqual(validation.credential_source, "package_local_json")

    def test_missing_credentials_path_fails_closed(self):
        validation = provider.validate_config(
            {
                "provider": "google_sheets_api",
                "reads_enabled": True,
                "writes_enabled": True,
                "execution_enabled": True,
            },
            environ={
                "NORTH_SHORE_GOOGLE_SHEET_ID": "sheet-id-must-not-print",
                "NORTH_SHORE_GOOGLE_CREDENTIALS_PATH": ".runtime/north-shore-missing-google-credentials.json",
            },
            library_checker=lambda name: True,
        )
        self.assertEqual(validation.error_code, "credentials_path_missing")
        self.assertFalse(validation.credentials_available)
        self.assertFalse(validation.client_ready)
        self.assertEqual(validation.credential_source, "package_local_path")

    def test_external_credentials_path_is_rejected_without_reading_token_stores(self):
        validation = provider.validate_config(
            {
                "provider": "google_sheets_api",
                "reads_enabled": True,
                "writes_enabled": True,
                "execution_enabled": True,
            },
            environ={
                "NORTH_SHORE_GOOGLE_SHEET_ID": "sheet-id-must-not-print",
                "NORTH_SHORE_GOOGLE_CREDENTIALS_PATH": "/home/liam/.composio/google-token.json",
            },
            library_checker=lambda name: (_ for _ in ()).throw(AssertionError("library check blocked")),
        )
        self.assertEqual(validation.error_code, "credentials_path_outside_package")
        self.assertFalse(validation.route_locked)
        self.assertEqual(validation.credential_source, "missing")

    def test_google_libraries_missing_fail_closed_with_valid_credentials(self):
        validation = provider.validate_config(
            {
                "provider": "google_sheets_api",
                "reads_enabled": True,
                "writes_enabled": True,
                "execution_enabled": True,
            },
            environ={
                "NORTH_SHORE_GOOGLE_SHEET_ID": "sheet-id-must-not-print",
                "NORTH_SHORE_GOOGLE_CREDENTIALS_JSON": fake_credentials_json(),
            },
            library_checker=lambda name: False,
        )
        self.assertEqual(validation.error_code, "google_libraries_missing")
        self.assertTrue(validation.credentials_available)
        self.assertFalse(validation.google_libraries_available)
        self.assertFalse(validation.client_ready)
        self.assertTrue(validation.route_locked)

    def test_fake_optional_google_modules_can_pass_dependency_readiness_without_network(self):
        validation = provider.validate_config(
            {
                "provider": "google_sheets_api",
                "reads_enabled": True,
                "writes_enabled": True,
                "execution_enabled": True,
            },
            environ={
                "NORTH_SHORE_GOOGLE_SHEET_ID": "sheet-id-must-not-print",
                "NORTH_SHORE_GOOGLE_CREDENTIALS_JSON": fake_credentials_json(),
            },
            library_checker=lambda name: True,
        )
        self.assertTrue(validation.google_libraries_available)
        self.assertFalse(validation.client_ready)
        self.assertEqual(validation.error_code, "client_builder_missing")
        self.assertFalse(validation.can_read_metadata)
        self.assertFalse(validation.can_write)

    def test_injected_client_builder_can_validate_without_external_calls(self):
        fake_builder = MagicMock(return_value={"fake": "client"})
        runtime_root = ROOT / ".runtime"
        runtime_root.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=runtime_root) as temporary:
            credentials = Path(temporary) / "google-service-account.json"
            credentials.write_text(fake_credentials_json(), encoding="utf-8")
            validation = provider.validate_config(
                    {
                        "provider": "google_sheets_api",
                        "reads_enabled": True,
                        "writes_enabled": True,
                        "execution_enabled": True,
                    },
                    environ={
                        "NORTH_SHORE_GOOGLE_SHEET_ID": "sheet-id-must-not-print",
                        "NORTH_SHORE_GOOGLE_CREDENTIALS_PATH": str(credentials),
                    },
                    library_checker=lambda name: True,
                    client_builder=fake_builder,
                )
        self.assertEqual(fake_builder.call_count, 1)
        self.assertTrue(validation.credentials_available)
        self.assertTrue(validation.google_libraries_available)
        self.assertTrue(validation.client_ready)
        self.assertTrue(validation.can_read_metadata)
        self.assertTrue(validation.can_write)
        self.assertTrue(validation.route_locked)
        self.assertEqual(validation.credential_source, "package_local_path")

        direct = provider.DirectGoogleSheetsProvider(
            {
                "provider": "google_sheets_api",
                "reads_enabled": True,
                "writes_enabled": True,
                "execution_enabled": True,
            },
            client_builder=MagicMock(return_value={"fake": "client"}),
        )
        with patch.object(provider, "validate_config", return_value=validation):
            with self.assertRaisesRegex(provider.GoogleSheetsProviderError, "not implemented"):
                direct.append_rows(empty_requests())
            with self.assertRaisesRegex(provider.GoogleSheetsProviderError, "not implemented"):
                direct.read_sheet_metadata()

    def test_reads_enabled_and_writes_enabled_remain_independent_gates(self):
        base = {
            "provider": "google_sheets_api",
            "execution_enabled": True,
        }
        environ = {
            "NORTH_SHORE_GOOGLE_SHEET_ID": "sheet-id-must-not-print",
            "NORTH_SHORE_GOOGLE_CREDENTIALS_JSON": fake_credentials_json(),
        }
        read_only = provider.validate_config(
            {**base, "reads_enabled": True, "writes_enabled": False},
            environ=environ,
            library_checker=lambda name: True,
            client_builder=lambda: object(),
        )
        write_only = provider.validate_config(
            {**base, "reads_enabled": False, "writes_enabled": True},
            environ=environ,
            library_checker=lambda name: True,
            client_builder=lambda: object(),
        )
        self.assertTrue(read_only.can_read_metadata)
        self.assertFalse(read_only.can_write)
        self.assertFalse(write_only.can_read_metadata)
        self.assertTrue(write_only.can_write)

    def test_reads_and_writes_require_separate_explicit_flags(self):
        validation = provider.validate_config(
            {"provider": "google_sheets_api", "execution_enabled": True},
            environ={
                "NORTH_SHORE_GOOGLE_SHEET_ID": "sheet-id-must-not-print",
                "NORTH_SHORE_GOOGLE_CREDENTIALS_JSON": fake_credentials_json(),
            },
            library_checker=lambda name: True,
            client_builder=lambda: object(),
        )
        self.assertTrue(validation.route_locked)
        self.assertTrue(validation.client_ready)
        self.assertFalse(validation.can_read_metadata)
        self.assertFalse(validation.can_write)
        rendered = "; ".join(validation.messages)
        self.assertIn("READS_ENABLED must be explicitly set", rendered)
        self.assertIn("WRITES_ENABLED must be explicitly set", rendered)

    def test_builds_append_payloads_from_existing_adapter_boundary(self):
        requests = empty_requests()
        payloads = provider.build_append_payloads(requests)
        self.assertEqual(tuple(payload.tab_name for payload in payloads), sheets_sync_adapter.SYNC_TABS)
        self.assertEqual({payload.spreadsheet_id_env for payload in payloads}, {"NORTH_SHORE_GOOGLE_SHEET_ID"})
        self.assertTrue(all(payload.value_input_option == "RAW" for payload in payloads))

    def test_dry_run_prints_no_sheet_id_credentials_or_row_data(self):
        output = io.StringIO()
        with patch.dict(
            os.environ,
            {
                "NORTH_SHORE_SHEETS_PROVIDER": "google_sheets_api",
                "NORTH_SHORE_GOOGLE_SHEET_ID": "sheet-id-must-not-appear",
                "NORTH_SHORE_GOOGLE_CREDENTIALS_JSON": "value-must-not-appear",
            },
            clear=True,
        ):
            with patch.object(provider.sheets_sync_adapter, "load_local_payloads", return_value=empty_payloads()):
                with redirect_stdout(output):
                    self.assertEqual(provider.main(), 0)
        rendered = output.getvalue()
        self.assertIn("Direct Google Sheets provider dry-run", rendered)
        self.assertIn("Execution: BLOCKED", rendered)
        self.assertIn("Route locked: False", rendered)
        self.assertIn("Credential source: package_local_json", rendered)
        self.assertNotIn("sheet-id-must-not-appear", rendered)
        self.assertNotIn("value-must-not-appear", rendered)

    def test_no_external_modules_are_touched_during_dry_run(self):
        google_api = MagicMock()
        service_account = MagicMock()
        with patch.dict("sys.modules", {
            "googleapiclient.discovery": google_api,
            "google.oauth2.service_account": service_account,
        }):
            provider.dry_run_summary(empty_requests())
        self.assertEqual(google_api.mock_calls, [])
        self.assertEqual(service_account.mock_calls, [])

    def test_source_contains_no_live_client_call_or_hard_composio_dependency(self):
        source = inspect.getsource(provider).lower()
        for forbidden in (
            "import " + "composio",
            "from " + "composio",
            "requests" + ".",
            "urllib" + ".",
            "." + "execute(",
            "dashboard/backend",
            "connectors/composio_access_adapter.py",
            ".hermes",
            "telegram polling",
            "openai",
            "anthropic",
        ):
            self.assertNotIn(forbidden, source)

    def test_config_template_lists_only_placeholders(self):
        template = provider.config_template()
        self.assertEqual(template["provider"], "none")
        self.assertIn("google_sheets_api", template["allowed_providers"])
        self.assertIn("apps_script_webapp", template["allowed_providers"])
        self.assertIn("agentic_os_backend", template["forbidden_direct_google_preflight_providers"])
        self.assertFalse(template["reads_enabled"])
        self.assertFalse(template["writes_enabled"])
        self.assertFalse(template["execution_enabled"])


if __name__ == "__main__":
    unittest.main()
