import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "google_sheets"
REQUIRED_TABS = {
    "Config", "Users", "Salespeople", "Raw_Logs", "Daily_Team_Summary",
    "Daily_Salesperson_Scorecard", "Followups", "Missing_Data", "Coaching_Flags",
    "Report_Archive", "Dashboard_Daily", "Team_Scorecard", "Rep_Detail",
    "Dashboard_Weekly", "Dashboard_Monthly", "Demo_Data", "QA_Checks",
}


class GoogleSheetsSpecTests(unittest.TestCase):
    def setUp(self):
        self.headers = json.loads((SPECS / "tab_headers.json").read_text(encoding="utf-8"))
        self.schema = json.loads((SPECS / "sheet_schema.json").read_text(encoding="utf-8"))

    def apps_script_source(self):
        return (SPECS / "apps_script_webapp_template.js").read_text(encoding="utf-8")

    def apps_script_string_list(self, const_name):
        source = self.apps_script_source()
        match = re.search(rf"const {const_name} = \[(.*?)\];", source, flags=re.S)
        if match is None and const_name == "NORTH_SHORE_REQUIRED_TABS":
            return set(self.apps_script_ordered_tab_specs())
        self.assertIsNotNone(match, f"{const_name} not found")
        return set(re.findall(r"'([^']+)'", match.group(1)))

    def apps_script_ordered_string_list(self, const_name):
        source = self.apps_script_source()
        match = re.search(rf"const {const_name} = \[(.*?)\];", source, flags=re.S)
        if match is None and const_name == "NORTH_SHORE_REQUIRED_TABS":
            return self.apps_script_ordered_tab_specs()
        self.assertIsNotNone(match, f"{const_name} not found")
        return re.findall(r"'([^']+)'", match.group(1))

    def apps_script_header_tabs(self):
        return set(self.apps_script_tab_headers())

    def apps_script_ordered_tab_specs(self):
        return list(self.apps_script_tab_headers())

    def apps_script_tab_headers(self):
        source = self.apps_script_source()
        match = re.search(r"const NORTH_SHORE_TAB_SPECS = \[(.*?)\];", source, flags=re.S)
        self.assertIsNotNone(match, "NORTH_SHORE_TAB_SPECS not found")
        pairs = re.findall(r"\{\s*name: '([^']+)', headers: \[(.*?)\]", match.group(1), flags=re.S)
        self.assertTrue(pairs, "No tab specs found")
        return {name: re.findall(r"'([^']+)'", headers) for name, headers in pairs}

    def plan_verified_tab_list(self):
        plan = (SPECS / "live_dashboard_setup_plan.md").read_text(encoding="utf-8")
        match = re.search(
            r"Verify these tabs exist before any sync:(.*?QA_Checks`)\.",
            plan,
            flags=re.S,
        )
        self.assertIsNotNone(match, "manual verification tab list not found")
        return re.findall(r"`([^`]+)`", match.group(1))

    def test_all_spec_json_files_load(self):
        paths = sorted(SPECS.glob("*.json"))
        self.assertEqual({path.name for path in paths}, {"sheet_schema.json", "tab_headers.json", "demo_rows.json"})
        for path in paths:
            with self.subTest(path=path.name):
                self.assertIsNotNone(json.loads(path.read_text(encoding="utf-8")))

    def test_required_tabs_exist_in_headers_and_schema(self):
        self.assertEqual(set(self.headers), REQUIRED_TABS)
        self.assertEqual({tab["name"] for tab in self.schema["tabs"]}, REQUIRED_TABS)

    def test_apps_script_setup_covers_required_tabs(self):
        source = self.apps_script_source()
        self.assertEqual(self.apps_script_string_list("NORTH_SHORE_REQUIRED_TABS"), REQUIRED_TABS)
        self.assertEqual(self.apps_script_header_tabs(), REQUIRED_TABS)
        self.assertIn("const NORTH_SHORE_TAB_SPECS", source)
        self.assertIn("const NORTH_SHORE_REQUIRED_TABS = getExpectedTabs();", source)
        self.assertIn("const NORTH_SHORE_TAB_HEADERS = getExpectedTabHeaders();", source)
        self.assertIn("function getExpectedTabs()", source)
        self.assertIn("function getExpectedTabHeaders()", source)
        self.assertIn("function setupDemoTabs()", source)
        self.assertIn("function applyHeaders(sheet, headers)", source)
        self.assertIn("function getSheetStatus()", source)
        self.assertIn("NORTH_SHORE_TAB_SPECS.forEach", source)
        self.assertIn("spreadsheet.insertSheet(tabName)", source)
        self.assertIn("range.setValues([headers])", source)
        self.assertIn("sheet.setFrozenRows(1)", source)
        self.assertIn("spreadsheet.moveActiveSheet(index + 1)", source)
        self.assertNotIn("clearContents()", source)
        self.assertNotIn("deleteSheet", source)

    def test_apps_script_setup_seeds_premium_dashboard_views(self):
        source = self.apps_script_source()
        required_functions = [
            "function setupDashboardViews(spreadsheet)",
            "function seedDashboardDaily(spreadsheet)",
            "function seedTeamScorecard(spreadsheet)",
            "function seedRepDetail(spreadsheet)",
            "function seedWeeklyMonthlyDashboards(spreadsheet)",
            "function seedDemoData(spreadsheet)",
            "function appendQaCheck(spreadsheet",
        ]
        for function_name in required_functions:
            with self.subTest(function_name=function_name):
                self.assertIn(function_name, source)
        self.assertIn("const dashboardRows = setupDashboardViews(spreadsheet);", source)
        self.assertIn("dashboard_rows: dashboardRows", source)
        self.assertIn("resetManagedDashboardRows_", source)
        self.assertIn("sheet.deleteRows(2, lastRow - 1)", source)
        self.assertIn("preserves source data tabs", source)

    def test_dashboard_daily_seed_contains_manager_sections(self):
        source = self.apps_script_source()
        required_sections = [
            "Today's Summary",
            "Team Activity",
            "Follow-Ups Due",
            "Missing / Incomplete Updates",
            "Coaching Attention",
            "Recent Activity",
            "Manager Next Actions",
        ]
        for section in required_sections:
            with self.subTest(section=section):
                self.assertIn(section, source)
        self.assertIn("Daily_Team_Summary", source)
        self.assertIn("Raw_Logs", source)
        self.assertIn("Followups", source)
        self.assertIn("Missing_Data", source)
        self.assertIn("Coaching_Flags", source)

    def test_team_scorecard_and_rep_detail_are_formula_populated(self):
        source = self.apps_script_source()
        self.assertIn("setDashboardRows_(spreadsheet, 'Team_Scorecard', rows)", source)
        self.assertIn("setDashboardRows_(spreadsheet, 'Rep_Detail', rows)", source)
        self.assertIn("SUMIFS(Daily_Salesperson_Scorecard", source)
        self.assertIn("COUNTIFS(Followups", source)
        self.assertIn("COUNTIFS(Missing_Data", source)
        self.assertIn("COUNTIFS(Coaching_Flags", source)
        self.assertIn("FILTER({Raw_Logs", source)
        self.assertIn("Selected salesperson", source)
        self.assertIn("Manager Next Action Prompts", source)

    def test_team_scorecard_formulas_cover_synced_scorecard_rows(self):
        source = self.apps_script_source()
        self.assertIn("const TEAM_SCORECARD_FORMULA_ROWS = 50;", source)
        self.assertIn("for (let rowNumber = 2; rowNumber < TEAM_SCORECARD_FORMULA_ROWS + 2; rowNumber += 1)", source)
        self.assertIn("function teamScorecardSalespersonFormula_(rowNumber)", source)
        self.assertIn("function teamScorecardRow_(d, rowNumber)", source)
        self.assertIn("FILTER(Salespeople!B$2:B", source)
        self.assertIn("LOWER(TO_TEXT(Salespeople!C$2:C))", source)
        self.assertIn("FILTER(Daily_Salesperson_Scorecard!D$2:D,Daily_Salesperson_Scorecard!A$2:A=$A", source)
        self.assertIn("synced_scorecard", source)
        self.assertIn("COUNTIFS(Daily_Salesperson_Scorecard!A:A,$A", source)

    def test_dashboard_latest_date_formula_uses_scorecard_when_summary_is_empty(self):
        source = self.apps_script_source()
        self.assertIn("function latestReportDateFormula_()", source)
        self.assertIn("{Daily_Team_Summary!A2:A;Daily_Salesperson_Scorecard!A2:A}", source)
        self.assertIn("IFERROR(MAX(FILTER(", source)
        self.assertIn(",TODAY())", source)

    def test_team_scorecard_spec_documents_scorecard_fallback(self):
        tabs = {tab["name"]: tab for tab in self.schema["tabs"]}
        scorecard = tabs["Team_Scorecard"]
        notes = " ".join(scorecard["notes"])
        self.assertIn("active Salespeople", notes)
        self.assertIn("Daily_Salesperson_Scorecard", notes)
        self.assertIn("roster tab is incomplete", notes)
        self.assertIn("Daily_Salesperson_Scorecard", scorecard["mapping"]["as_of_date"])
        self.assertIn("Daily_Salesperson_Scorecard.display_name", scorecard["mapping"]["salesperson"])
        self.assertIn("synced_scorecard", scorecard["mapping"]["active"])

    def test_live_setup_tab_lists_match_schema_exactly(self):
        schema_order = [tab["name"] for tab in self.schema["tabs"]]
        self.assertEqual(self.apps_script_ordered_string_list("NORTH_SHORE_REQUIRED_TABS"), schema_order)
        self.assertEqual(self.plan_verified_tab_list(), schema_order)
        self.assertEqual(list(self.headers), schema_order)

    def test_apps_script_write_allowlist_stays_on_sync_tabs(self):
        from src import sheets_sync_adapter

        self.assertEqual(
            self.apps_script_string_list("NORTH_SHORE_ALLOWED_TABS"),
            set(sheets_sync_adapter.SYNC_TABS),
        )
        self.assertNotIn("Dashboard_Daily", self.apps_script_string_list("NORTH_SHORE_ALLOWED_TABS"))
        self.assertNotIn("Team_Scorecard", self.apps_script_string_list("NORTH_SHORE_ALLOWED_TABS"))
        self.assertNotIn("Rep_Detail", self.apps_script_string_list("NORTH_SHORE_ALLOWED_TABS"))

    def test_apps_script_headers_match_tab_headers_spec(self):
        apps_headers = self.apps_script_tab_headers()
        for tab_name, headers in self.headers.items():
            with self.subTest(tab=tab_name):
                self.assertEqual(apps_headers[tab_name], headers)

    def test_live_dashboard_setup_plan_mentions_every_required_tab(self):
        plan = (SPECS / "live_dashboard_setup_plan.md").read_text(encoding="utf-8")
        for tab_name in REQUIRED_TABS:
            with self.subTest(tab=tab_name):
                self.assertIn(f"`{tab_name}`", plan)
        self.assertIn("`google_sheets/apps_script_webapp_template.js`", plan)
        self.assertIn("setupDemoTabs", plan)
        self.assertIn("Save the Apps Script project", plan)
        self.assertIn("run `setupDemoTabs` manually", plan)
        self.assertIn("creates missing tabs", plan)
        self.assertIn("does not clear", plan)
        self.assertIn("seeds the premium dashboard tabs", plan)
        self.assertIn("Verify `Dashboard_Daily` has section rows", plan)
        self.assertIn("formulas now read from the synced data tabs", plan)
        self.assertIn("Verify these tabs exist before any sync", plan)
        self.assertIn("run one controlled `/sync_sheets`", plan)
        self.assertIn("Do not run duplicate syncs unless duplicate rows are acceptable", plan)

    def test_raw_logs_headers_cover_sales_log_schema(self):
        sales_schema = json.loads((ROOT / "schemas" / "sales_log.schema.json").read_text(encoding="utf-8"))
        expected = set(sales_schema["required"]) - {"parsed", "missing_fields", "coaching_flags"}
        expected |= set(sales_schema["properties"]["parsed"]["required"])
        expected |= {"missing_fields_json", "coaching_flags_json"}
        self.assertTrue(expected.issubset(self.headers["Raw_Logs"]))

    def test_report_archive_headers_cover_archive_schema(self):
        report_schema = json.loads((ROOT / "schemas" / "report.schema.json").read_text(encoding="utf-8"))
        expected = set(report_schema["required"]) - {"summary_metrics", "flags"}
        expected |= {"flags_json", "total_updates", "active_salespeople", "people_spoken_to"}
        self.assertTrue(expected.issubset(self.headers["Report_Archive"]))

    def test_demo_rows_are_explicitly_synthetic(self):
        demo = json.loads((SPECS / "demo_rows.json").read_text(encoding="utf-8"))
        self.assertTrue(demo["is_demo"])
        serialized = json.dumps(demo).lower()
        self.assertIn("fake-customer", serialized)
        self.assertNotRegex(serialized, r'"telegram_user_id"\s*:\s*"[0-9]{6,}"')
        for row in demo["rows"]["Demo_Data"]:
            self.assertTrue(row["is_demo"])

    def test_specs_contain_no_secrets_or_execution_code(self):
        secret_assignment = re.compile(
            r"(?i)(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|client[_ -]?secret)\s*[:=]\s*['\"]?[A-Za-z0-9_./+-]{8,}"
        )
        forbidden_code = re.compile(r"(?m)^\s*(?:from|import)\s+(?:composio|google)|\.execute\s*\(")
        for path in sorted(SPECS.iterdir()):
            if path.is_file():
                content = path.read_text(encoding="utf-8")
                with self.subTest(path=path.name):
                    self.assertIsNone(secret_assignment.search(content))
                    self.assertIsNone(forbidden_code.search(content))

    def test_apps_script_template_and_plan_contain_no_live_values_or_external_execution(self):
        texts = {
            path.name: path.read_text(encoding="utf-8")
            for path in (
                SPECS / "apps_script_webapp_template.js",
                SPECS / "live_dashboard_setup_plan.md",
            )
        }
        forbidden_patterns = [
            r"https://script\.google\.com/.*/exec",
            r"\bAKfycb[A-Za-z0-9_-]{20,}\b",
            r"\b[0-9]{8,}:[A-Za-z0-9_-]{20,}\b",
            r"\b[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{6,}\.[a-zA-Z0-9_-]{20,}\b",
            r"AIza[0-9A-Za-z_-]{20,}",
            r"spreadsheet[_ -]?id\s*[:=]",
            r"refresh[_ -]?token\s*[:=]",
            r"access[_ -]?token\s*[:=]",
            r"client[_ -]?secret\s*[:=]",
            r"private_key\s*[:=]",
            r"credential[s]?\s*[:=]",
        ]
        forbidden_execution = [
            r"composio\s+(?:run|execute)",
            r"hermes\s+(?:activate|run|execute)",
            "telegram" + r".*poll" + "ing" + r".*enabled",
            r"openai\.",
            r"anthropic\.",
            "agentic os backend connector " + "route:",
            re.escape("." + "./"),
        ]
        combined = "\n".join(texts.values()).lower()
        self.assertIn("do not paste secrets", combined)
        self.assertIn("do not deploy", combined)
        for name, text in texts.items():
            for pattern in forbidden_patterns + forbidden_execution:
                with self.subTest(path=name, pattern=pattern):
                    self.assertIsNone(re.search(pattern, text, flags=re.IGNORECASE))

    def test_dashboard_tabs_are_readouts_and_raw_logs_is_integration_owned(self):
        tabs = {tab["name"]: tab for tab in self.schema["tabs"]}
        self.assertEqual(tabs["Raw_Logs"]["write_policy"], "integration_only")
        for name in ("Dashboard_Daily", "Team_Scorecard", "Rep_Detail", "Dashboard_Weekly", "Dashboard_Monthly"):
            self.assertEqual(tabs[name]["kind"], "dashboard_readout")
            self.assertIn(tabs[name]["write_policy"], {"integration_only", "formula_only"})

    def test_derived_row_mappings_cover_every_header(self):
        tabs = {tab["name"]: tab for tab in self.schema["tabs"]}
        for name in ("Daily_Team_Summary", "Daily_Salesperson_Scorecard", "Followups", "Missing_Data", "Coaching_Flags"):
            with self.subTest(tab=name):
                self.assertEqual(set(tabs[name]["mapping"]), set(self.headers[name]))
                self.assertTrue(tabs[name].get("row_policy"), f"{name} needs an explicit row policy")

    def test_followup_time_is_separate_or_blank_and_never_inferred(self):
        tabs = {tab["name"]: tab for tab in self.schema["tabs"]}
        followups = tabs["Followups"]
        policy = " ".join(followups["notes"]).lower()
        self.assertIn("separate followup_time", policy)
        self.assertIn("cell is blank", policy)
        self.assertIn("never infer or parse", policy)
        demo = json.loads((SPECS / "demo_rows.json").read_text(encoding="utf-8"))
        due_row = next(row for row in demo["rows"]["Followups"] if row["followup_status"] == "due")
        self.assertEqual(due_row["followup_time"], "")
        self.assertRegex(due_row["next_step"], r"\b\d{2}:\d{2}\b")

    def test_users_display_name_precedence_is_complete(self):
        tabs = {tab["name"]: tab for tab in self.schema["tabs"]}
        policy = " ".join(tabs["Users"]["notes"])
        ordered = [
            "config/roles.json users.<telegram_user_id>.display_name",
            "data/local_state.json users.<telegram_user_id>.display_name",
            "first_name plus last_name",
            "username normalized with one leading @",
            "Unregistered salesperson",
        ]
        positions = [policy.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))

    def test_missing_data_defines_and_demonstrates_all_row_types(self):
        tabs = {tab["name"]: tab for tab in self.schema["tabs"]}
        missing = tabs["Missing_Data"]
        expected_types = {"roster_no_update", "incomplete_log", "unregistered_submitter"}
        self.assertEqual(set(missing["allowed_missing_types"]), expected_types)
        self.assertEqual(set(missing["row_sources"]), expected_types)
        for missing_type, rule in missing["row_sources"].items():
            with self.subTest(missing_type=missing_type):
                self.assertTrue(rule["source"])
                self.assertTrue(rule["cardinality"])
                for field in ("log_id", "missing_fields_json", "roster_status", "detail"):
                    self.assertIn(field, rule)
        demo = json.loads((SPECS / "demo_rows.json").read_text(encoding="utf-8"))
        self.assertEqual({row["missing_type"] for row in demo["rows"]["Missing_Data"]}, expected_types)

    def test_demo_derived_rows_match_declared_headers(self):
        demo = json.loads((SPECS / "demo_rows.json").read_text(encoding="utf-8"))
        for name in ("Daily_Team_Summary", "Daily_Salesperson_Scorecard", "Followups", "Missing_Data", "Dashboard_Daily", "Team_Scorecard", "Rep_Detail"):
            for row in demo["rows"][name]:
                with self.subTest(tab=name, row=row):
                    self.assertEqual(list(row), self.headers[name])

    def test_premium_dashboard_spec_covers_required_sections(self):
        layout = (SPECS / "dashboard_layout.md").read_text(encoding="utf-8")
        required = [
            "Dashboard_Daily", "Team_Scorecard", "Rep_Detail", "Followups",
            "Missing_Data", "Coaching_Flags", "Raw_Logs", "headline",
            "active reps", "missing updates", "follow-ups due",
            "coaching attention", "team sales-process progression",
            "recent activity", "next manager actions", "frozen",
            "conditional formatting", "status chips", "filter views",
            "sparklines", "summary cards", "dropdown",
        ]
        lowered = layout.lower()
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value.lower(), lowered)

    def test_drilldown_and_progression_metrics_are_defined(self):
        tabs = {tab["name"]: tab for tab in self.schema["tabs"]}
        rep_detail = tabs["Rep_Detail"]
        self.assertIn("salesperson_selector", rep_detail["controls"])
        self.assertIn("dropdown", rep_detail["controls"]["salesperson_selector"].lower())
        metrics = tabs["Team_Scorecard"]["metrics"]
        expected_metrics = {
            "log_activity_trend",
            "test_drive_rate",
            "offer_worksheet_rate",
            "asked_for_business_rate",
            "followup_capture_rate",
            "process_completion_pct",
            "incomplete_update_rate",
        }
        self.assertEqual(set(metrics), expected_metrics)
        self.assertIn("AVERAGE", metrics["process_completion_pct"])

    def test_demo_rows_are_rich_enough_for_manager_dashboard(self):
        demo = json.loads((SPECS / "demo_rows.json").read_text(encoding="utf-8"))
        rows = demo["rows"]
        self.assertGreaterEqual(len(rows["Salespeople"]), 4)
        self.assertGreaterEqual(len(rows["Raw_Logs"]), 6)
        self.assertGreaterEqual(len(rows["Daily_Team_Summary"]), 3)
        self.assertEqual({row["followup_status"] for row in rows["Followups"]}, {"overdue", "due", "upcoming"})
        self.assertIn("No Update Yet", {row["status"] for row in rows["Team_Scorecard"]})
        self.assertTrue(any(row["section"] == "followups" for row in rows["Rep_Detail"]))

    def test_demo_rows_contain_no_obvious_live_values(self):
        demo = json.loads((SPECS / "demo_rows.json").read_text(encoding="utf-8"))
        serialized = json.dumps(demo)
        lower = serialized.lower()
        forbidden_patterns = [
            r"https://script\.google\.com/.*/exec",
            r"\bAKfycb[A-Za-z0-9_-]{20,}\b",
            r"\b[0-9]{8,}:[A-Za-z0-9_-]{20,}\b",
            r"refresh[_ -]?token",
            r"access[_ -]?token",
            r"client[_ -]?secret",
            r"oauth",
            r"private_key",
            r"spreadsheet_id",
            r"AIza[0-9A-Za-z_-]{20,}",
        ]
        for pattern in forbidden_patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, serialized, flags=re.IGNORECASE))
        self.assertNotIn("@gmail.com", lower)
        self.assertNotIn("phone", lower)

    def test_sync_payload_builder_contract_remains_supported(self):
        from src import sheets_sync_adapter

        for tab in sheets_sync_adapter.SYNC_TABS:
            with self.subTest(tab=tab):
                self.assertIn(tab, self.headers)
        self.assertNotIn("Team_Scorecard", sheets_sync_adapter.SYNC_TABS)
        self.assertNotIn("Rep_Detail", sheets_sync_adapter.SYNC_TABS)

    def test_dashboard_docs_do_not_introduce_forbidden_external_paths(self):
        texts = {
            path.name: path.read_text(encoding="utf-8").lower()
            for path in (SPECS / "dashboard_layout.md", SPECS / "live_dashboard_setup_plan.md")
        }
        forbidden = [
            "." + "./",
            "telegram polling",
            "llm call",
            "deploy apps script",
            "/sync_sheets",
        ]
        combined = re.sub(r"\s+", " ", "\n".join(texts.values()))
        self.assertIn("agentic os backend connector routes", combined)
        self.assertIn("not part of this setup", combined)
        for name, text in texts.items():
            for value in forbidden:
                with self.subTest(path=name, value=value):
                    if value in {"telegram polling", "llm call", "deploy apps script", "/sync_sheets"}:
                        if value in text:
                            self.assertIn("do not", text)
                    else:
                        self.assertNotIn(value, text)

    def test_looker_studio_is_only_explicitly_rejected(self):
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SPECS / "dashboard_layout.md", SPECS / "live_dashboard_setup_plan.md")
        ).lower()
        self.assertIn("not looker studio", text)
        self.assertNotIn("build looker studio", text)


if __name__ == "__main__":
    unittest.main()
