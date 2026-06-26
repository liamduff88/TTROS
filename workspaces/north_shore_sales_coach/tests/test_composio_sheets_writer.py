import inspect
import io
import json
import os
import unittest
from collections import OrderedDict
from contextlib import redirect_stdout
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from src import composio_sheets_writer as writer
from src import sheets_sync_adapter


def empty_ordered_payloads():
    headers = sheets_sync_adapter.load_headers()
    return OrderedDict((tab, []) for tab in headers)


class ComposioSheetsWriterTests(unittest.TestCase):
    def test_accepts_adapter_payloads_and_preserves_ordered_values(self):
        headers = sheets_sync_adapter.load_headers()
        payloads = empty_ordered_payloads()
        payloads["Users"] = [dict(zip(headers["Users"], ["synthetic-user", "Demo", "salesperson", True, "demo-a"]))]

        requests = writer.build_write_requests(payloads, headers)

        self.assertEqual([request.tab_name for request in requests], list(sheets_sync_adapter.SYNC_TABS))
        self.assertEqual(requests[0].headers, tuple(headers["Users"]))
        self.assertEqual(requests[0].rows[0], ("synthetic-user", "Demo", "salesperson", True, "demo-a"))

    def test_dry_run_summary_has_tabs_counts_and_validation_only(self):
        requests = writer.build_write_requests(empty_ordered_payloads())
        summary = writer.dry_run_summary(requests)
        for tab in sheets_sync_adapter.SYNC_TABS:
            self.assertIn(f"{tab}: 0 row(s) | valid", summary)
        self.assertIn("Validation: PASS", summary)

    def test_execute_mode_fails_closed(self):
        with patch.object(writer.sheets_sync_adapter, "load_local_payloads", return_value=empty_ordered_payloads()):
            with self.assertRaisesRegex(writer.LiveExecutionDisabledError, "disabled"):
                writer.main(["--execute"])

    def test_local_preflight_reports_config_tabs_payloads_and_blocked_execute(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"NORTH_SHORE_GOOGLE_SHEET_ID": "never-render-this"}, clear=True):
            with patch.object(writer.sheets_sync_adapter, "load_local_payloads", return_value=empty_ordered_payloads()):
                with redirect_stdout(output):
                    self.assertEqual(writer.main(["--preflight"]), 0)
        rendered = output.getvalue()
        self.assertIn("Google Sheet ID config: present", rendered)
        self.assertIn("Target tabs: valid", rendered)
        self.assertIn("Payload Users: ready", rendered)
        self.assertIn("Execute mode: BLOCKED", rendered)
        self.assertNotIn("never-render-this", rendered)

    def test_missing_sheet_id_is_reported_without_value(self):
        requests = writer.build_write_requests(empty_ordered_payloads())
        rendered = writer.preflight_summary(requests, sheet_id_present=False)
        self.assertIn("Google Sheet ID config: missing", rendered)

    def test_target_tabs_are_verified_against_both_local_specs(self):
        self.assertTrue(writer.target_tabs_match_specs(sheets_sync_adapter.SYNC_TABS))
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            headers = root / "headers.json"
            schema = root / "schema.json"
            headers.write_text(json.dumps({tab: [] for tab in sheets_sync_adapter.SYNC_TABS}), encoding="utf-8")
            schema.write_text(json.dumps({"tabs": [{"name": "Users"}]}), encoding="utf-8")
            self.assertFalse(writer.target_tabs_match_specs(
                sheets_sync_adapter.SYNC_TABS, headers, schema
            ))

    def test_read_only_composio_probe_discovers_actions_and_checks_contracts(self):
        discovery = json.dumps({"tools": [
            {"slug": "GOOGLESHEETS_APPEND_VALUES"},
            {"slug": "GOOGLESHEETS_UPDATE_VALUES"},
        ]})
        schema = json.dumps({"input_schema": {"properties": {
            "spreadsheet_id": {}, "range": {}, "values": {},
        }}})
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            stdout = discovery if command[1] == "search" else schema
            return CompletedProcess(command, 0, stdout=stdout, stderr="")

        with TemporaryDirectory() as temporary:
            cli = Path(temporary) / "composio"
            cli.touch()
            result = writer.probe_composio(cli, runner=runner)
        self.assertTrue(result.toolkit_available)
        self.assertTrue(result.append_contract_matches)
        self.assertTrue(result.update_contract_matches)
        self.assertEqual(calls[0][0][1], "search")
        self.assertEqual({call[0][1] for call in calls[1:]}, {"execute"})
        self.assertTrue(all("--get-schema" in call[0] for call in calls[1:]))
        self.assertFalse(any("-d" in call[0] or "--dry-run" in call[0] for call in calls))

    def test_composio_probe_fails_safely_without_cli_or_network(self):
        missing = writer.probe_composio("/definitely/not/composio")
        self.assertFalse(missing.toolkit_available)

        with TemporaryDirectory() as temporary:
            cli = Path(temporary) / "composio"
            cli.touch()
            failed = writer.probe_composio(
                cli,
                runner=lambda command, **kwargs: CompletedProcess(command, 1, stdout="", stderr="secret"),
            )
        self.assertTrue(failed.toolkit_available)
        self.assertEqual(failed.detail, "Composio discovery unavailable")
        rendered = writer.preflight_summary(
            writer.build_write_requests(empty_ordered_payloads()),
            sheet_id_present=False,
            composio=failed,
        )
        self.assertNotIn("secret", rendered)

        with TemporaryDirectory() as temporary:
            cli = Path(temporary) / "composio"
            cli.touch()
            timed_out = writer.probe_composio(
                cli, runner=lambda command, **kwargs: (_ for _ in ()).throw(TimeoutError())
            )
        self.assertFalse(timed_out.append_action_available)

    def test_composio_probe_is_not_configured_without_opt_in_env(self):
        with patch.dict(os.environ, {}, clear=True):
            result = writer.probe_composio()
        self.assertFalse(result.toolkit_available)
        self.assertEqual(result.detail, "Composio CLI not configured")

    def test_no_liam_specific_cli_path_is_hardcoded(self):
        self.assertNotIn("/home/liam", inspect.getsource(writer))
        self.assertIn("NORTH_SHORE_COMPOSIO_CLI_PATH", inspect.getsource(writer))

    def test_dry_run_never_prints_sheet_id_or_secrets(self):
        sensitive = "sheet-id-must-not-appear"
        output = io.StringIO()
        with patch.dict(os.environ, {
            "NORTH_SHORE_GOOGLE_SHEET_ID": sensitive,
            "COMPOSIO_API_KEY": "secret-must-not-appear",
        }, clear=False):
            with patch.object(writer.sheets_sync_adapter, "load_local_payloads", return_value=empty_ordered_payloads()):
                with redirect_stdout(output):
                    self.assertEqual(writer.main(["--dry-run"]), 0)
        rendered = output.getvalue()
        self.assertNotIn(sensitive, rendered)
        self.assertNotIn("secret-must-not-appear", rendered)

    def test_dry_run_without_sheet_id_and_without_external_modules(self):
        composio = MagicMock()
        google_sheets = MagicMock()
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict("sys.modules", {"composio": composio, "googleapiclient": google_sheets}):
                with patch.object(writer.sheets_sync_adapter, "load_local_payloads", return_value=empty_ordered_payloads()):
                    with redirect_stdout(output):
                        self.assertEqual(writer.main([]), 0)
        self.assertIn("Validation: PASS", output.getvalue())
        self.assertEqual(composio.mock_calls, [])
        self.assertEqual(google_sheets.mock_calls, [])

    def test_writer_source_contains_no_external_client_import_or_call(self):
        source = inspect.getsource(writer).lower()
        for forbidden in (
            "import composio", "from composio", "import google", "from google",
            "requests.", "urllib.", ".execute(",
        ):
            self.assertNotIn(forbidden, source)

    def test_rejects_wrong_tab_or_column_order(self):
        payloads = empty_ordered_payloads()
        payloads.move_to_end("Users")
        with self.assertRaisesRegex(writer.WriterValidationError, "tab order"):
            writer.build_write_requests(payloads)

        payloads = empty_ordered_payloads()
        headers = sheets_sync_adapter.load_headers()["Users"]
        payloads["Users"] = [dict.fromkeys(reversed(headers), "")]
        with self.assertRaisesRegex(writer.WriterValidationError, "column order"):
            writer.build_write_requests(payloads)


if __name__ == "__main__":
    unittest.main()
