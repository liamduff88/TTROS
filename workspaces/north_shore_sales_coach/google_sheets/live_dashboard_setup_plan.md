# Live Dashboard Setup Plan

This is a one-time manual setup plan for the existing Google Sheet
`North Shore Sales Coach - Demo Dashboard`. It is Google Sheets only, not Looker
Studio. Do not run these steps until Liam explicitly approves live Sheet work.

## Before-Running Checks

- Confirm exactly one North Shore runner is active.
- Confirm no real customer data will be pasted or synced.
- Confirm the demo Gmail account and demo Sheet are the intended target.
- Confirm duplicate demo rows are acceptable, or reset the Sheet first.
- Confirm no Telegram token, Apps Script Web App URL, Apps Script secret, Sheet
  ID, OAuth value, credential file, or live customer identifier is pasted into
  the Sheet or committed.
- Confirm live Telegram polling, Composio, Hermes, Agentic OS backend connector
  routes, Apps Script deployment, and LLM calls are not part of this setup.

## What Setup Will Create Or Update

- Reorder tabs to match `google_sheets/dashboard_layout.md`.
- Ensure these required tabs exist, matching `google_sheets/sheet_schema.json`
  and `google_sheets/tab_headers.json`: `Config`, `Users`, `Salespeople`,
  `Raw_Logs`, `Daily_Team_Summary`, `Daily_Salesperson_Scorecard`,
  `Followups`, `Missing_Data`, `Coaching_Flags`, `Report_Archive`,
  `Dashboard_Daily`, `Team_Scorecard`, `Rep_Detail`, `Dashboard_Weekly`,
  `Dashboard_Monthly`, `Demo_Data`, and `QA_Checks`.
- Ensure manager-facing dashboard tabs exist: `Dashboard_Daily`,
  `Dashboard_Weekly`, `Dashboard_Monthly`, `Team_Scorecard`, `Rep_Detail`,
  `Followups`, `Missing_Data`, `Coaching_Flags`, recent activity through
  `Raw_Logs`, `Demo_Data`, and `QA_Checks`.
- Ensure source/supporting tabs exist: `Raw_Logs`, `Daily_Team_Summary`,
  `Daily_Salesperson_Scorecard`, `Report_Archive`, `Salespeople`, `Users`, and
  `Config`.
- Apply headers from `google_sheets/tab_headers.json`.
- Use `setupDemoTabs` from `google_sheets/apps_script_webapp_template.js` for
  tab creation and header application. It creates missing tabs, reorders the
  required tabs, freezes row 1, updates header rows, and refreshes managed
  dashboard seed rows with formulas. It does not clear `Raw_Logs`, source tabs,
  synced rows, or existing integration-owned data.
- Apply formulas, formula-ready rows, frozen headers, conditional formatting,
  and compact summary-card formatting described in
  `google_sheets/dashboard_layout.md`. Filter views and protected formula ranges
  can be added manually after the formula rows are verified.
- Hide `Users` by default and hide Telegram ID columns from manager-facing
  views.
- Keep `Raw_Logs` as the source-of-truth tab.

## Manual Steps

1. Open the approved demo Sheet in the approved demo Google account.
2. Make a copy or export backup before changing tab layout.
3. Confirm the current target Sheet title is `North Shore Sales Coach - Demo Dashboard`.
4. Open Extensions > Apps Script for that Sheet.
5. Copy the full updated source from
   `google_sheets/apps_script_webapp_template.js` into the bound Apps Script
   editor. Do not paste secrets, the Web App URL, the Sheet ID, OAuth values,
   credential JSON, or Telegram values into the source or this document.
6. Save the Apps Script project. Do not deploy or update the Apps Script Web App
   as part of this setup. Update the deployment later only if Liam separately
   approves that live Apps Script action.
7. From the Apps Script editor, run `setupDemoTabs` manually. This creates
   missing tabs, reorders the required tabs, freezes row 1, applies headers, and
   seeds the premium dashboard tabs with managed labels, formulas, QA rows, and
   demo validation markers. It does this without wiping existing `Raw_Logs` or
   synced source rows.
8. Verify these tabs exist before any sync: `Config`, `Users`, `Salespeople`,
   `Raw_Logs`, `Daily_Team_Summary`, `Daily_Salesperson_Scorecard`,
   `Followups`, `Missing_Data`, `Coaching_Flags`, `Report_Archive`,
   `Dashboard_Daily`, `Team_Scorecard`, `Rep_Detail`, `Dashboard_Weekly`,
   `Dashboard_Monthly`, `Demo_Data`, and `QA_Checks`.
9. Confirm row 1 headers match `google_sheets/tab_headers.json`; do not rename
   existing sync headers.
10. Verify `Dashboard_Daily` has section rows for Today's Summary, Team
   Activity, Follow-Ups Due, Missing / Incomplete Updates, Coaching Attention,
   Recent Activity, and Manager Next Actions.
11. Verify `Team_Scorecard`, `Rep_Detail`, `Dashboard_Weekly`,
   `Dashboard_Monthly`, `Demo_Data`, and `QA_Checks` have formulas or
   validation rows below their headers.
12. Add the optional dropdown on `Rep_Detail` cell A2 from
   `Salespeople.display_name` if the Sheet UI needs a clickable selector.
13. Paste only synthetic rows from `demo_rows.json` if demo data is needed.
14. Apply any manual filter views, protected ranges, or extra frozen columns
   from `dashboard_layout.md` after confirming the formulas render.
15. Review the first screen of `Dashboard_Daily` as Ryan: headline numbers,
   follow-ups, missing updates, and manager actions should be visible without
   opening another tool.
16. Run only local validation commands before any later sync.
17. After every tab in step 8, every header in step 9, and the dashboard rows in
   steps 10-11 are confirmed, run one controlled `/sync_sheets` from the
   approved live North Shore bot context only if Liam explicitly approves that
   sync. Do not run duplicate syncs unless duplicate rows are acceptable.
18. After that one controlled sync, re-open the dashboard tabs and confirm the
   formulas now read from the synced data tabs.

## Rollback Or Reset

- If formulas or formatting are wrong, restore the Sheet backup created before
  setup.
- If duplicate demo rows are inserted, filter for `demo-` identifiers and remove
  only those synthetic rows.
- If the Sheet should be reset, clear dashboard tabs and repopulate from the
  local specs after approval.
- Do not delete production-like tabs or live data unless Liam separately
  approves that destructive action.

## What Not To Paste Or Commit

- Real `/exec` Web App URL.
- Apps Script shared secret.
- Telegram bot token or chat identifiers.
- Spreadsheet ID.
- OAuth client, refresh token, access token, service account key, or credential
  JSON.
- Real customer names, phone numbers, emails, VINs, license plates, or deal IDs.
- Provider execution output from Composio, Hermes, Google APIs, or Agentic OS.
