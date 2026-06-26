import inspect
import io
import os
import unittest
from collections import OrderedDict
from contextlib import redirect_stdout
from unittest.mock import patch

from src import composio_sheets_writer
from src import sheets_adapter
from src import sheets_sync_adapter


def empty_payloads():
    headers = sheets_sync_adapter.load_headers()
    return OrderedDict((tab, []) for tab in sheets_sync_adapter.SYNC_TABS)


class ProviderNeutralSheetsAdapterTests(unittest.TestCase):
    def test_constructs_generic_requests_without_provider_or_composio(self):
        adapter = sheets_adapter.SheetsAdapter()
        requests = adapter.build_write_requests(empty_payloads())
        self.assertIsNone(adapter.provider)
        self.assertFalse(adapter.enabled)
        self.assertEqual(tuple(request.tab_name for request in requests), sheets_sync_adapter.SYNC_TABS)
        self.assertTrue(all(isinstance(request, sheets_adapter.SheetWriteRequest) for request in requests))

    def test_disabled_connector_implements_generic_contract_and_fails_closed(self):
        connector = sheets_adapter.DisabledSheetsConnector()
        self.assertIsInstance(connector, sheets_adapter.SheetsConnector)
        with self.assertRaises(sheets_adapter.SheetsExecutionDisabledError):
            connector.read(sheets_adapter.SheetReadRequest("Users"))
        with self.assertRaises(sheets_adapter.SheetsExecutionDisabledError):
            connector.write(())

    def test_generic_dry_run_needs_no_composio_install_or_config(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(sheets_sync_adapter, "load_local_payloads", return_value=empty_payloads()):
                with redirect_stdout(output):
                    self.assertEqual(sheets_adapter.main(["--dry-run"]), 0)
        rendered = output.getvalue()
        self.assertIn("provider-neutral", rendered)
        self.assertIn("Validation: PASS", rendered)
        self.assertIn("Execution: BLOCKED", rendered)

    def test_generic_and_composio_execution_both_fail_closed(self):
        requests = sheets_adapter.build_write_requests(empty_payloads())
        with self.assertRaisesRegex(sheets_adapter.SheetsExecutionDisabledError, "disabled"):
            sheets_adapter.execute_write_requests(requests)
        with self.assertRaisesRegex(sheets_adapter.SheetsExecutionDisabledError, "disabled"):
            composio_sheets_writer.execute_write_requests(requests)

    def test_composio_is_optional_and_not_configured_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            result = composio_sheets_writer.probe_composio()
        self.assertFalse(result.toolkit_available)
        self.assertEqual(result.detail, "Composio CLI not configured")

    def test_core_boundary_has_no_provider_or_local_path_dependency(self):
        source = inspect.getsource(sheets_adapter).lower()
        for forbidden in (
            "composio",
            "/home/liam",
            "googleapiclient",
            "import google",
            "from google",
            "hermes_native",
            "agentic_os_backend",
            "dashboard/backend",
            "connectors/composio_access_adapter.py",
            ".hermes",
            ".composio",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
