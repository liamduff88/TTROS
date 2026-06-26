/*
 * North Shore Google Sheets Apps Script Web App bridge template.
 *
 * Install this in the demo Sheet's bound Apps Script project. Replace the
 * placeholder secret in Script Properties, deploy as the demo Gmail account,
 * and keep the Web App URL and secret outside source control.
 */

const NORTH_SHORE_ALLOWED_SECRET_PROPERTY = 'NORTH_SHORE_SHEETS_WEBAPP_SECRET';
const NORTH_SHORE_ALLOWED_ACTIONS = ['status', 'append_raw_log', 'append_objects'];
const NORTH_SHORE_ALLOWED_TABS = [
  'Users',
  'Salespeople',
  'Raw_Logs',
  'Daily_Team_Summary',
  'Daily_Salesperson_Scorecard',
  'Followups',
  'Missing_Data',
  'Coaching_Flags',
  'Report_Archive',
  'QA_Checks',
];

const NORTH_SHORE_TAB_SPECS = [
  { name: 'Config', headers: ['key', 'value', 'description'], color: '#f4cccc' },
  { name: 'Users', headers: ['telegram_user_id', 'display_name', 'role', 'active', 'salesperson_id'], color: '#d9ead3' },
  { name: 'Salespeople', headers: ['salesperson_id', 'display_name', 'active', 'telegram_user_id', 'created_at', 'updated_at'], color: '#d9ead3' },
  { name: 'Raw_Logs', headers: ['log_id', 'submitted_at', 'telegram_user_id', 'salesperson_id', 'source', 'raw_text', 'customer_type', 'customer_name_or_ref', 'vehicle_interest', 'lead_source', 'interaction_type', 'appointment_count', 'walk_in_count', 'people_spoken_to', 'test_drive', 'worksheet_or_offer_presented', 'asked_for_business', 'outcome', 'next_step', 'followup_date', 'notes', 'missing_fields_json', 'coaching_flags_json', 'confidence', 'status', 'llm_used', 'llm_tokens_estimate'], color: '#cfe2f3' },
  { name: 'Daily_Team_Summary', headers: ['report_date', 'generated_at', 'total_updates', 'active_salespeople', 'people_spoken_to', 'appointments', 'test_drives', 'worksheets_offers', 'asks_for_business', 'outcomes', 'followups_due', 'missing_incomplete_updates', 'coaching_flags'], color: '#cfe2f3' },
  { name: 'Daily_Salesperson_Scorecard', headers: ['report_date', 'generated_at', 'salesperson_id', 'display_name', 'updates', 'people_spoken_to', 'appointments', 'test_drives', 'worksheets_offers', 'asks_for_business', 'outcomes'], color: '#cfe2f3' },
  { name: 'Followups', headers: ['report_date', 'followup_status', 'salesperson_id', 'display_name', 'followup_date', 'followup_time', 'next_step', 'log_id'], color: '#fff2cc' },
  { name: 'Missing_Data', headers: ['report_date', 'missing_type', 'salesperson_id', 'display_name', 'log_id', 'missing_fields_json', 'roster_status', 'detail'], color: '#fce5cd' },
  { name: 'Coaching_Flags', headers: ['report_date', 'salesperson_id', 'display_name', 'flag_code', 'detail', 'log_id'], color: '#fce5cd' },
  { name: 'Report_Archive', headers: ['report_id', 'generated_at', 'report_type', 'date', 'total_updates', 'active_salespeople', 'people_spoken_to', 'appointments', 'test_drives', 'worksheets_offers', 'asks_for_business', 'outcomes', 'followups_due', 'missing_incomplete_updates', 'coaching_flags_count', 'flags_json', 'llm_used'], color: '#d9d2e9' },
  { name: 'Dashboard_Daily', headers: ['as_of_date', 'section', 'display_order', 'label', 'value_formula', 'source_tabs', 'status_rule', 'manager_prompt'], color: '#6fa8dc' },
  { name: 'Team_Scorecard', headers: ['as_of_date', 'salesperson', 'active', 'logs_submitted', 'people_spoken_to', 'appointments', 'test_drives', 'worksheets_offers', 'asked_for_business_count', 'followups_set', 'incomplete_updates', 'coaching_flags', 'test_drive_rate', 'offer_worksheet_rate', 'asked_for_business_rate', 'followup_capture_rate', 'process_completion_pct', 'incomplete_update_rate', 'seven_day_logs_trend', 'status', 'manager_next_action'], color: '#6fa8dc' },
  { name: 'Rep_Detail', headers: ['selected_salesperson', 'selected_date', 'section', 'display_order', 'label', 'value_formula', 'source_tabs', 'manager_next_action'], color: '#6fa8dc' },
  { name: 'Dashboard_Weekly', headers: ['week_start', 'week_end', 'metric', 'value', 'display_order', 'status', 'detail'], color: '#9fc5e8' },
  { name: 'Dashboard_Monthly', headers: ['month', 'metric', 'value', 'display_order', 'status', 'detail'], color: '#9fc5e8' },
  { name: 'Demo_Data', headers: ['demo_record_id', 'entity_type', 'display_name', 'customer_reference', 'scenario', 'is_demo'], color: '#ead1dc' },
  { name: 'QA_Checks', headers: ['checked_at', 'check_name', 'status', 'row_count', 'detail'], color: '#d9ead3' },
];

const NORTH_SHORE_REQUIRED_TABS = getExpectedTabs();
const NORTH_SHORE_TAB_HEADERS = getExpectedTabHeaders();

function getExpectedTabs() {
  return NORTH_SHORE_TAB_SPECS.map(function(spec) {
    return spec.name;
  });
}

function getExpectedTabHeaders() {
  const headersByTab = {};
  NORTH_SHORE_TAB_SPECS.forEach(function(spec) {
    headersByTab[spec.name] = spec.headers.slice();
  });
  return headersByTab;
}

function tabSpecByName_(tabName) {
  return NORTH_SHORE_TAB_SPECS.find(function(spec) {
    return spec.name === tabName;
  });
}

function applyHeaders(sheet, headers) {
  if (!headers || headers.length === 0) {
    return;
  }
  const range = sheet.getRange(1, 1, 1, headers.length);
  range.setValues([headers]);
  range
    .setFontWeight('bold')
    .setBackground('#f3f6f8')
    .setFontColor('#111111')
    .setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
  sheet.setFrozenRows(1);
  sheet.autoResizeColumns(1, headers.length);
}

function applySafeFormatting_(sheet, spec) {
  if (spec.color) {
    sheet.setTabColor(spec.color);
  }
  if (sheet.getFilter()) {
    return;
  }
  const lastColumn = Math.max(spec.headers.length, sheet.getLastColumn());
  if (lastColumn > 0) {
    sheet.getRange(1, 1, Math.max(sheet.getLastRow(), 1), lastColumn).createFilter();
  }
}

function resetManagedDashboardRows_(sheet, headers) {
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.deleteRows(2, lastRow - 1);
  }
  applyHeaders(sheet, headers);
}

function setDashboardRows_(spreadsheet, tabName, rows) {
  const spec = tabSpecByName_(tabName);
  const sheet = spreadsheet.getSheetByName(tabName);
  resetManagedDashboardRows_(sheet, spec.headers);
  if (rows.length > 0) {
    sheet.getRange(2, 1, rows.length, spec.headers.length).setValues(rows);
  }
  formatDashboardSheet_(sheet, spec.headers.length);
  return rows.length;
}

function formatDashboardSheet_(sheet, columnCount) {
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, columnCount)
    .setFontWeight('bold')
    .setBackground('#18324a')
    .setFontColor('#ffffff')
    .setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
  sheet.getRange(1, 1, Math.max(sheet.getLastRow(), 1), columnCount)
    .setVerticalAlignment('middle')
    .setWrapStrategy(SpreadsheetApp.WrapStrategy.WRAP);
  sheet.setColumnWidths(1, columnCount, 145);
  sheet.setColumnWidth(2, 180);
  sheet.setColumnWidth(4, 220);
  sheet.setColumnWidth(5, 280);
  sheet.setColumnWidth(columnCount, 320);

  if (sheet.getLastRow() > 1) {
    const sectionRange = sheet.getRange(2, 2, sheet.getLastRow() - 1, 1);
    sectionRange.setFontWeight('bold').setBackground('#eef3f8');
  }
  applyStatusConditionalFormatting_(sheet, columnCount);
}

function applyStatusConditionalFormatting_(sheet, columnCount) {
  const lastRow = Math.max(sheet.getLastRow(), 2);
  const range = sheet.getRange(2, 1, lastRow - 1, columnCount);
  const rules = [
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextContains('Needs Attention')
      .setBackground('#f4cccc')
      .setFontColor('#990000')
      .setRanges([range])
      .build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextContains('Watch')
      .setBackground('#fff2cc')
      .setFontColor('#7f6000')
      .setRanges([range])
      .build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenTextContains('On Track')
      .setBackground('#d9ead3')
      .setFontColor('#274e13')
      .setRanges([range])
      .build(),
  ];
  sheet.setConditionalFormatRules(rules);
}

function setupDashboardViews(spreadsheet) {
  const weeklyMonthlyRows = seedWeeklyMonthlyDashboards(spreadsheet);
  return {
    Dashboard_Daily: seedDashboardDaily(spreadsheet),
    Team_Scorecard: seedTeamScorecard(spreadsheet),
    Rep_Detail: seedRepDetail(spreadsheet),
    Dashboard_Weekly: weeklyMonthlyRows.Dashboard_Weekly,
    Dashboard_Monthly: weeklyMonthlyRows.Dashboard_Monthly,
    Demo_Data: seedDemoData(spreadsheet),
    QA_Checks: appendQaCheck(spreadsheet, 'setupDemoTabs', 'ready', 'Dashboard formulas and validation rows refreshed.'),
  };
}

function latestReportDateFormula_() {
  return '=IF(COUNTA(Daily_Team_Summary!A2:A),MAX(Daily_Team_Summary!A2:A),TODAY())';
}

function seedDashboardDaily(spreadsheet) {
  const d = latestReportDateFormula_();
  const rows = [
    [d, "Today's Summary", 10, 'As of date', d, 'Daily_Team_Summary', 'Current report date', 'Start here before the daily floor check.'],
    [d, "Today's Summary", 20, 'Last generated', '=IFERROR(XLOOKUP($A2,Daily_Team_Summary!A:A,Daily_Team_Summary!B:B,"No summary yet"),"No summary yet")', 'Daily_Team_Summary', 'Watch if stale', 'Confirm sync completed before coaching from the dashboard.'],
    [d, "Today's Summary", 30, 'Logs submitted', '=IFERROR(XLOOKUP($A2,Daily_Team_Summary!A:A,Daily_Team_Summary!C:C,0),0)', 'Daily_Team_Summary,Raw_Logs', 'Watch when below active reps', 'Ask quiet reps to log customer activity.'],
    [d, "Today's Summary", 40, 'Active reps', '=COUNTIFS(Salespeople!C:C,TRUE)+COUNTIFS(Salespeople!C:C,"TRUE")+COUNTIFS(Salespeople!C:C,"yes")', 'Salespeople', 'Roster count', 'Use for expected update coverage.'],
    [d, "Today's Summary", 50, 'People spoken to', '=IFERROR(XLOOKUP($A2,Daily_Team_Summary!A:A,Daily_Team_Summary!E:E,0),0)', 'Daily_Team_Summary,Raw_Logs', 'On Track when rising', 'Scan activity quality, not just update count.'],
    [d, 'Team Activity', 60, 'Appointments', '=IFERROR(XLOOKUP($A2,Daily_Team_Summary!A:A,Daily_Team_Summary!F:F,0),0)', 'Daily_Team_Summary,Daily_Salesperson_Scorecard', 'Progress signal', 'Look for appointment-setting consistency.'],
    [d, 'Team Activity', 70, 'Test drives', '=IFERROR(XLOOKUP($A2,Daily_Team_Summary!A:A,Daily_Team_Summary!G:G,0),0)', 'Daily_Team_Summary,Raw_Logs', 'Progress signal', 'Review whether conversations are reaching demo stage.'],
    [d, 'Team Activity', 80, 'Worksheets/offers', '=IFERROR(XLOOKUP($A2,Daily_Team_Summary!A:A,Daily_Team_Summary!H:H,0),0)', 'Daily_Team_Summary,Raw_Logs', 'Progress signal', 'Check whether test drives are converting to offers.'],
    [d, 'Team Activity', 90, 'Asked for business', '=IFERROR(XLOOKUP($A2,Daily_Team_Summary!A:A,Daily_Team_Summary!I:I,0),0)', 'Daily_Team_Summary,Raw_Logs', 'Progress signal', 'Coach direct closing language where appropriate.'],
    [d, 'Follow-Ups Due', 100, 'Open follow-ups due or overdue', '=COUNTIFS(Followups!A:A,$A2,Followups!B:B,"due")+COUNTIFS(Followups!A:A,$A2,Followups!B:B,"overdue")', 'Followups', 'Needs Attention when above 0', 'Start with overdue follow-ups before new activity review.'],
    [d, 'Follow-Ups Due', 110, 'Overdue follow-ups', '=COUNTIFS(Followups!A:A,$A2,Followups!B:B,"overdue")', 'Followups', 'Needs Attention when above 0', 'Ask for the next committed customer step.'],
    [d, 'Missing / Incomplete Updates', 120, 'Missing or incomplete updates', '=COUNTIFS(Missing_Data!A:A,$A2)', 'Missing_Data,Salespeople,Raw_Logs', 'Watch at 1; Needs Attention at 2+', 'Close data gaps with neutral wording.'],
    [d, 'Missing / Incomplete Updates', 130, 'No-update roster rows', '=COUNTIFS(Missing_Data!A:A,$A2,Missing_Data!B:B,"roster_no_update")', 'Missing_Data,Salespeople', 'Watch when above 0', 'Check whether the rep needs help logging activity.'],
    [d, 'Coaching Attention', 140, 'Coaching flags', '=COUNTIFS(Coaching_Flags!A:A,$A2)', 'Coaching_Flags,Raw_Logs', 'Watch when above 0', 'Use non-punitive coaching notes from the flag detail.'],
    [d, 'Recent Activity', 150, 'Latest complete activity', '=IFERROR(TEXTJOIN(" | ",TRUE,INDEX(SORT(FILTER({Raw_Logs!B:B,Raw_Logs!H:H,Raw_Logs!K:K,Raw_Logs!S:S,Raw_Logs!T:T},Raw_Logs!Y:Y="complete"),1,FALSE),1,0)),"No complete activity yet")', 'Raw_Logs', 'Recent logs visible', 'Open Raw_Logs only when more detail is needed.'],
    [d, 'Manager Next Actions', 160, 'Priority prompt', '=IFS(COUNTIFS(Followups!A:A,$A2,Followups!B:B,"overdue")>0,"Check overdue follow-up",COUNTIFS(Missing_Data!A:A,$A2)>0,"Ask for missing update detail",COUNTIFS(Coaching_Flags!A:A,$A2)>0,"Review coaching attention",TRUE,"No immediate action")', 'Followups,Missing_Data,Coaching_Flags', 'Action-oriented prompt', 'Use this as the first coaching prompt for Ryan.'],
  ];
  return setDashboardRows_(spreadsheet, 'Dashboard_Daily', rows);
}

function seedTeamScorecard(spreadsheet) {
  const d = latestReportDateFormula_();
  const rows = [
    [d, '=IFERROR(INDEX(FILTER(Salespeople!B2:B,Salespeople!B2:B<>""),ROW()-1),"")', '=IF($B2="","",IFERROR(XLOOKUP($B2,Salespeople!B:B,Salespeople!C:C,""),""))', '=IF($B2="","",SUMIFS(Daily_Salesperson_Scorecard!E:E,Daily_Salesperson_Scorecard!A:A,$A2,Daily_Salesperson_Scorecard!D:D,$B2))', '=IF($B2="","",SUMIFS(Daily_Salesperson_Scorecard!F:F,Daily_Salesperson_Scorecard!A:A,$A2,Daily_Salesperson_Scorecard!D:D,$B2))', '=IF($B2="","",SUMIFS(Daily_Salesperson_Scorecard!G:G,Daily_Salesperson_Scorecard!A:A,$A2,Daily_Salesperson_Scorecard!D:D,$B2))', '=IF($B2="","",SUMIFS(Daily_Salesperson_Scorecard!H:H,Daily_Salesperson_Scorecard!A:A,$A2,Daily_Salesperson_Scorecard!D:D,$B2))', '=IF($B2="","",SUMIFS(Daily_Salesperson_Scorecard!I:I,Daily_Salesperson_Scorecard!A:A,$A2,Daily_Salesperson_Scorecard!D:D,$B2))', '=IF($B2="","",SUMIFS(Daily_Salesperson_Scorecard!J:J,Daily_Salesperson_Scorecard!A:A,$A2,Daily_Salesperson_Scorecard!D:D,$B2))', '=IF($B2="","",COUNTIFS(Followups!A:A,$A2,Followups!D:D,$B2))', '=IF($B2="","",COUNTIFS(Missing_Data!A:A,$A2,Missing_Data!D:D,$B2))', '=IF($B2="","",COUNTIFS(Coaching_Flags!A:A,$A2,Coaching_Flags!C:C,$B2))', '=IFERROR(G2/E2,0)', '=IFERROR(H2/G2,0)', '=IFERROR(I2/H2,0)', '=IFERROR(J2/D2,0)', '=IF($B2="","",AVERAGE(M2,N2,O2,P2,1-R2))', '=IFERROR(K2/D2,0)', '=IF($B2="","",IFERROR(SPARKLINE(FILTER(Daily_Salesperson_Scorecard!E:E,Daily_Salesperson_Scorecard!D:D=$B2,Daily_Salesperson_Scorecard!A:A>=$A2-6)),""))', '=IF($B2="","",IFS(D2=0,"No Update Yet",K2>0,"Needs Attention",L2>0,"Watch",Q2<0.5,"Needs Attention",Q2<0.7,"Watch",TRUE,"On Track"))', '=IF($B2="","",IFS(T2="No Update Yet","Check whether this rep needs help logging customer activity.",K2>0,"Ask for the missing update detail.",L2>0,"Review coaching flag detail.",Q2<0.7,"Coach the next sales-process step.",TRUE,"Recognize the complete update and reinforce the next action."))'],
    [d, '=IFERROR(INDEX(FILTER(Salespeople!B2:B,Salespeople!B2:B<>""),ROW()-1),"")', '=IF($B3="","",IFERROR(XLOOKUP($B3,Salespeople!B:B,Salespeople!C:C,""),""))', '=IF($B3="","",SUMIFS(Daily_Salesperson_Scorecard!E:E,Daily_Salesperson_Scorecard!A:A,$A3,Daily_Salesperson_Scorecard!D:D,$B3))', '=IF($B3="","",SUMIFS(Daily_Salesperson_Scorecard!F:F,Daily_Salesperson_Scorecard!A:A,$A3,Daily_Salesperson_Scorecard!D:D,$B3))', '=IF($B3="","",SUMIFS(Daily_Salesperson_Scorecard!G:G,Daily_Salesperson_Scorecard!A:A,$A3,Daily_Salesperson_Scorecard!D:D,$B3))', '=IF($B3="","",SUMIFS(Daily_Salesperson_Scorecard!H:H,Daily_Salesperson_Scorecard!A:A,$A3,Daily_Salesperson_Scorecard!D:D,$B3))', '=IF($B3="","",SUMIFS(Daily_Salesperson_Scorecard!I:I,Daily_Salesperson_Scorecard!A:A,$A3,Daily_Salesperson_Scorecard!D:D,$B3))', '=IF($B3="","",SUMIFS(Daily_Salesperson_Scorecard!J:J,Daily_Salesperson_Scorecard!A:A,$A3,Daily_Salesperson_Scorecard!D:D,$B3))', '=IF($B3="","",COUNTIFS(Followups!A:A,$A3,Followups!D:D,$B3))', '=IF($B3="","",COUNTIFS(Missing_Data!A:A,$A3,Missing_Data!D:D,$B3))', '=IF($B3="","",COUNTIFS(Coaching_Flags!A:A,$A3,Coaching_Flags!C:C,$B3))', '=IFERROR(G3/E3,0)', '=IFERROR(H3/G3,0)', '=IFERROR(I3/H3,0)', '=IFERROR(J3/D3,0)', '=IF($B3="","",AVERAGE(M3,N3,O3,P3,1-R3))', '=IFERROR(K3/D3,0)', '=IF($B3="","",IFERROR(SPARKLINE(FILTER(Daily_Salesperson_Scorecard!E:E,Daily_Salesperson_Scorecard!D:D=$B3,Daily_Salesperson_Scorecard!A:A>=$A3-6)),""))', '=IF($B3="","",IFS(D3=0,"No Update Yet",K3>0,"Needs Attention",L3>0,"Watch",Q3<0.5,"Needs Attention",Q3<0.7,"Watch",TRUE,"On Track"))', '=IF($B3="","",IFS(T3="No Update Yet","Check whether this rep needs help logging customer activity.",K3>0,"Ask for the missing update detail.",L3>0,"Review coaching flag detail.",Q3<0.7,"Coach the next sales-process step.",TRUE,"Recognize the complete update and reinforce the next action."))'],
    [d, '=IFERROR(INDEX(FILTER(Salespeople!B2:B,Salespeople!B2:B<>""),ROW()-1),"")', '=IF($B4="","",IFERROR(XLOOKUP($B4,Salespeople!B:B,Salespeople!C:C,""),""))', '=IF($B4="","",SUMIFS(Daily_Salesperson_Scorecard!E:E,Daily_Salesperson_Scorecard!A:A,$A4,Daily_Salesperson_Scorecard!D:D,$B4))', '=IF($B4="","",SUMIFS(Daily_Salesperson_Scorecard!F:F,Daily_Salesperson_Scorecard!A:A,$A4,Daily_Salesperson_Scorecard!D:D,$B4))', '=IF($B4="","",SUMIFS(Daily_Salesperson_Scorecard!G:G,Daily_Salesperson_Scorecard!A:A,$A4,Daily_Salesperson_Scorecard!D:D,$B4))', '=IF($B4="","",SUMIFS(Daily_Salesperson_Scorecard!H:H,Daily_Salesperson_Scorecard!A:A,$A4,Daily_Salesperson_Scorecard!D:D,$B4))', '=IF($B4="","",SUMIFS(Daily_Salesperson_Scorecard!I:I,Daily_Salesperson_Scorecard!A:A,$A4,Daily_Salesperson_Scorecard!D:D,$B4))', '=IF($B4="","",SUMIFS(Daily_Salesperson_Scorecard!J:J,Daily_Salesperson_Scorecard!A:A,$A4,Daily_Salesperson_Scorecard!D:D,$B4))', '=IF($B4="","",COUNTIFS(Followups!A:A,$A4,Followups!D:D,$B4))', '=IF($B4="","",COUNTIFS(Missing_Data!A:A,$A4,Missing_Data!D:D,$B4))', '=IF($B4="","",COUNTIFS(Coaching_Flags!A:A,$A4,Coaching_Flags!C:C,$B4))', '=IFERROR(G4/E4,0)', '=IFERROR(H4/G4,0)', '=IFERROR(I4/H4,0)', '=IFERROR(J4/D4,0)', '=IF($B4="","",AVERAGE(M4,N4,O4,P4,1-R4))', '=IFERROR(K4/D4,0)', '=IF($B4="","",IFERROR(SPARKLINE(FILTER(Daily_Salesperson_Scorecard!E:E,Daily_Salesperson_Scorecard!D:D=$B4,Daily_Salesperson_Scorecard!A:A>=$A4-6)),""))', '=IF($B4="","",IFS(D4=0,"No Update Yet",K4>0,"Needs Attention",L4>0,"Watch",Q4<0.5,"Needs Attention",Q4<0.7,"Watch",TRUE,"On Track"))', '=IF($B4="","",IFS(T4="No Update Yet","Check whether this rep needs help logging customer activity.",K4>0,"Ask for the missing update detail.",L4>0,"Review coaching flag detail.",Q4<0.7,"Coach the next sales-process step.",TRUE,"Recognize the complete update and reinforce the next action."))'],
  ];
  return setDashboardRows_(spreadsheet, 'Team_Scorecard', rows);
}

function seedRepDetail(spreadsheet) {
  const d = latestReportDateFormula_();
  const selectedRep = '=IFERROR(INDEX(FILTER(Salespeople!B2:B,Salespeople!B2:B<>""),1),"Select salesperson")';
  const rows = [
    [selectedRep, d, 'Selected Salesperson', 10, 'Selected salesperson', selectedRep, 'Salespeople', 'Use this as the dropdown-ready selector cell.'],
    [selectedRep, d, 'Selected Salesperson', 20, 'Selected date', d, 'Daily_Team_Summary', 'Change the selected date to review a prior day.'],
    [selectedRep, d, 'Recent Activity', 30, 'Latest activity summary', '=IFERROR(TEXTJOIN(" | ",TRUE,INDEX(SORT(FILTER({Raw_Logs!B:B,Raw_Logs!H:H,Raw_Logs!K:K,Raw_Logs!R:R,Raw_Logs!S:S,Raw_Logs!T:T,Raw_Logs!Y:Y},Raw_Logs!D:D=IFERROR(XLOOKUP($A$2,Salespeople!B:B,Salespeople!A:A,""),"")),1,FALSE),1,0)),"No recent activity for selected rep")', 'Raw_Logs,Salespeople', 'Review customer-safe references and next steps.'],
    [selectedRep, d, 'Process Completion Metrics', 40, 'Logs submitted', '=COUNTIFS(Daily_Salesperson_Scorecard!A:A,$B$2,Daily_Salesperson_Scorecard!D:D,$A$2)', 'Daily_Salesperson_Scorecard', 'No Update Yet when zero.'],
    [selectedRep, d, 'Process Completion Metrics', 50, 'Test-drive rate', '=IFERROR(SUMIFS(Daily_Salesperson_Scorecard!H:H,Daily_Salesperson_Scorecard!A:A,$B$2,Daily_Salesperson_Scorecard!D:D,$A$2)/SUMIFS(Daily_Salesperson_Scorecard!F:F,Daily_Salesperson_Scorecard!A:A,$B$2,Daily_Salesperson_Scorecard!D:D,$A$2),0)', 'Daily_Salesperson_Scorecard', 'Coach activity progression when low.'],
    [selectedRep, d, 'Process Completion Metrics', 60, 'Offer/worksheet rate', '=IFERROR(SUMIFS(Daily_Salesperson_Scorecard!I:I,Daily_Salesperson_Scorecard!A:A,$B$2,Daily_Salesperson_Scorecard!D:D,$A$2)/SUMIFS(Daily_Salesperson_Scorecard!H:H,Daily_Salesperson_Scorecard!A:A,$B$2,Daily_Salesperson_Scorecard!D:D,$A$2),0)', 'Daily_Salesperson_Scorecard', 'Review whether demos become written next steps.'],
    [selectedRep, d, 'Follow-Ups', 70, 'Due or overdue follow-ups', '=COUNTIFS(Followups!D:D,$A$2,Followups!B:B,"due")+COUNTIFS(Followups!D:D,$A$2,Followups!B:B,"overdue")', 'Followups', 'Confirm each due customer next step.'],
    [selectedRep, d, 'Coaching Notes', 80, 'Coaching flags', '=COUNTIFS(Coaching_Flags!C:C,$A$2)', 'Coaching_Flags', 'Keep coaching neutral and specific.'],
    [selectedRep, d, 'Manager Next Action Prompts', 90, 'Next prompt', '=IFS(COUNTIFS(Followups!D:D,$A$2,Followups!B:B,"overdue")>0,"Ask what happened with the overdue follow-up and confirm the next customer step.",COUNTIFS(Missing_Data!D:D,$A$2)>0,"Ask for the next committed customer action before end of day.",COUNTIFS(Coaching_Flags!C:C,$A$2)>0,"Review the coaching note and pick one behavior to reinforce.",TRUE,"No immediate action.")', 'Followups,Missing_Data,Coaching_Flags', 'Use as Ryan-facing coaching script.'],
  ];
  return setDashboardRows_(spreadsheet, 'Rep_Detail', rows);
}

function seedWeeklyMonthlyDashboards(spreadsheet) {
  const weeklyRows = [
    ['=TODAY()-WEEKDAY(TODAY(),2)+1', '=TODAY()-WEEKDAY(TODAY(),2)+7', 'Weekly logs submitted', '=SUMIFS(Daily_Team_Summary!C:C,Daily_Team_Summary!A:A,">="&A2,Daily_Team_Summary!A:A,"<="&B2)', 10, 'Progress', 'Team-level activity rollup from synced daily summaries.'],
    ['=TODAY()-WEEKDAY(TODAY(),2)+1', '=TODAY()-WEEKDAY(TODAY(),2)+7', 'Process completion direction', '=IFERROR(AVERAGE(Team_Scorecard!Q:Q),0)', 20, 'Watch', 'Simple placeholder until weekly trend charts are added.'],
    ['=TODAY()-WEEKDAY(TODAY(),2)+1', '=TODAY()-WEEKDAY(TODAY(),2)+7', 'Follow-up discipline', '=COUNTIFS(Followups!A:A,">="&A2,Followups!A:A,"<="&B2)', 30, 'Progress', 'Review due and overdue follow-up volume.'],
    ['=TODAY()-WEEKDAY(TODAY(),2)+1', '=TODAY()-WEEKDAY(TODAY(),2)+7', 'Coaching attention', '=COUNTIFS(Coaching_Flags!A:A,">="&A2,Coaching_Flags!A:A,"<="&B2)', 40, 'Watch', 'Use as a queue for weekly one-on-one coaching.'],
  ];
  const monthlyRows = [
    ['=TEXT(TODAY(),"yyyy-mm")', 'Monthly logs submitted', '=SUMIFS(Daily_Team_Summary!C:C,Daily_Team_Summary!A:A,">="&DATE(YEAR(TODAY()),MONTH(TODAY()),1),Daily_Team_Summary!A:A,"<"&EDATE(DATE(YEAR(TODAY()),MONTH(TODAY()),1),1))', 10, 'Progress', 'Team-level activity rollup for the current month.'],
    ['=TEXT(TODAY(),"yyyy-mm")', 'Monthly people spoken to', '=SUMIFS(Daily_Team_Summary!E:E,Daily_Team_Summary!A:A,">="&DATE(YEAR(TODAY()),MONTH(TODAY()),1),Daily_Team_Summary!A:A,"<"&EDATE(DATE(YEAR(TODAY()),MONTH(TODAY()),1),1))', 20, 'Progress', 'Top-of-funnel progress indicator.'],
    ['=TEXT(TODAY(),"yyyy-mm")', 'Process completion direction', '=IFERROR(AVERAGE(Team_Scorecard!Q:Q),0)', 30, 'Watch', 'Placeholder metric reading current scorecard formulas.'],
    ['=TEXT(TODAY(),"yyyy-mm")', 'Coaching attention', '=COUNTIFS(Coaching_Flags!A:A,">="&DATE(YEAR(TODAY()),MONTH(TODAY()),1),Coaching_Flags!A:A,"<"&EDATE(DATE(YEAR(TODAY()),MONTH(TODAY()),1),1))', 40, 'Watch', 'Monthly coaching queue count.'],
  ];
  return {
    Dashboard_Weekly: setDashboardRows_(spreadsheet, 'Dashboard_Weekly', weeklyRows),
    Dashboard_Monthly: setDashboardRows_(spreadsheet, 'Dashboard_Monthly', monthlyRows),
  };
}

function seedDemoData(spreadsheet) {
  const rows = [
    ['demo-dashboard-layout', 'dashboard_seed', 'Premium dashboard formulas', 'fake-customer-dashboard', 'setupDemoTabs refreshed dashboard-facing tabs', true],
    ['demo-qa-validation', 'qa_seed', 'QA validation marker', 'fake-customer-qa', 'Use after one controlled sync to confirm formulas read synced tabs', true],
  ];
  return setDashboardRows_(spreadsheet, 'Demo_Data', rows);
}

function appendQaCheck(spreadsheet, checkName, status, detail) {
  const sheet = spreadsheet.getSheetByName('QA_Checks');
  resetManagedDashboardRows_(sheet, NORTH_SHORE_TAB_HEADERS.QA_Checks);
  const rows = [
    ['=NOW()', checkName, status, '=COUNTA(Raw_Logs!A2:A)', detail],
    ['=NOW()', 'dashboard_tabs_seeded', 'ready', '=COUNTA(Dashboard_Daily!A2:A)+COUNTA(Team_Scorecard!A2:A)+COUNTA(Rep_Detail!A2:A)', 'Premium dashboard tabs contain managed rows and formulas.'],
    ['=NOW()', 'source_tabs_preserved', 'ready', '=COUNTA(Raw_Logs!A2:A)', 'setupDemoTabs does not clear Raw_Logs or synced source rows.'],
  ];
  sheet.getRange(2, 1, rows.length, NORTH_SHORE_TAB_HEADERS.QA_Checks.length).setValues(rows);
  formatDashboardSheet_(sheet, NORTH_SHORE_TAB_HEADERS.QA_Checks.length);
  return rows.length;
}

function setupDemoTabs() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const createdTabs = [];
  const updatedTabs = [];

  NORTH_SHORE_TAB_SPECS.forEach(function(spec, index) {
    const tabName = spec.name;
    let sheet = spreadsheet.getSheetByName(tabName);
    if (!sheet) {
      sheet = spreadsheet.insertSheet(tabName);
      createdTabs.push(tabName);
    }

    applyHeaders(sheet, spec.headers);
    applySafeFormatting_(sheet, spec);
    updatedTabs.push(tabName);

    spreadsheet.setActiveSheet(sheet);
    spreadsheet.moveActiveSheet(index + 1);
  });

  const dashboardRows = setupDashboardViews(spreadsheet);

  return {
    ok: true,
    created_tabs: createdTabs,
    updated_header_tabs: updatedTabs,
    dashboard_rows: dashboardRows,
    note: 'setupDemoTabs creates missing tabs, preserves source data tabs, and refreshes managed dashboard formula rows.',
  };
}

function getSheetStatus() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  return NORTH_SHORE_TAB_SPECS.map(function(spec) {
    const sheet = spreadsheet.getSheetByName(spec.name);
    return {
      name: spec.name,
      exists: Boolean(sheet),
      expected_headers: spec.headers.slice(),
      current_headers: sheet ? sheet.getRange(1, 1, 1, Math.max(spec.headers.length, sheet.getLastColumn())).getValues()[0].slice(0, spec.headers.length) : [],
      last_row: sheet ? sheet.getLastRow() : 0,
      last_column: sheet ? sheet.getLastColumn() : 0,
    };
  });
}

function jsonStatus_(status, extra) {
  const body = Object.assign({ ok: status === 200, status: status }, extra || {});
  return ContentService
    .createTextOutput(JSON.stringify(body))
    .setMimeType(ContentService.MimeType.JSON);
}

function configuredSecret_() {
  return PropertiesService.getScriptProperties().getProperty(NORTH_SHORE_ALLOWED_SECRET_PROPERTY);
}

function reject_(status, code) {
  return jsonStatus_(status, { code: code });
}

function doPost(e) {
  const expectedSecret = configuredSecret_();

  let payload;
  try {
    payload = JSON.parse((e && e.postData && e.postData.contents) || '{}');
  } catch (err) {
    return reject_(400, 'invalid_json');
  }

  const requestSecret = payload._shared_secret || payload.shared_secret;
  delete payload._shared_secret;
  delete payload.shared_secret;
  if (expectedSecret && requestSecret !== expectedSecret) {
    return reject_(403, 'secret_rejected');
  }

  if (NORTH_SHORE_ALLOWED_ACTIONS.indexOf(payload.action) === -1) {
    return reject_(400, 'unknown_action');
  }
  if (payload.action === 'status') {
    return jsonStatus_(200, {
      code: 'ready',
      allowed_actions: NORTH_SHORE_ALLOWED_ACTIONS,
      allowed_tabs: NORTH_SHORE_ALLOWED_TABS,
      required_tabs: getExpectedTabs(),
      sheet_status: getSheetStatus(),
    });
  }

  if (payload.action === 'append_raw_log') {
    payload.target_tab = 'Raw_Logs';
  }
  if (NORTH_SHORE_ALLOWED_TABS.indexOf(payload.target_tab) === -1) {
    return reject_(400, 'unknown_tab');
  }

  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(payload.target_tab);
  if (!sheet) {
    return reject_(404, 'tab_missing');
  }

  const rows = [];
  if (Array.isArray(payload.objects)) {
    const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    payload.objects.forEach(function(objectRow) {
      rows.push(headers.map(function(header) {
        return Object.prototype.hasOwnProperty.call(objectRow, header) ? objectRow[header] : '';
      }));
    });
  } else if (Array.isArray(payload.rows)) {
    payload.rows.forEach(function(row) {
      rows.push(row);
    });
  } else {
    return reject_(400, 'objects_or_rows_required');
  }

  const validRows = rows.filter(function(row) {
    return Array.isArray(row);
  });
  if (validRows.length !== rows.length) {
    return reject_(400, 'row_shape_rejected');
  }
  if (validRows.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, validRows.length, validRows[0].length).setValues(validRows);
  }

  return jsonStatus_(200, {
    code: 'appended',
    target_tab: payload.target_tab,
    row_count: validRows.length,
    request_id: payload.request_id || '',
  });
}
