# North Shore Sales Coach - Demo Dashboard

This is a Sheet-native dashboard blueprint for the existing Google Sheet named
`North Shore Sales Coach - Demo Dashboard`. It is a local setup specification
only: do not deploy Apps Script, do not call live Google services, and this is
not Looker Studio. Dashboard tabs are read-only manager views built from normalized
supporting tabs.

## Tab Order

1. `Dashboard_Daily`
2. `Team_Scorecard`
3. `Rep_Detail`
4. `Followups`
5. `Missing_Data`
6. `Coaching_Flags`
7. `Daily_Team_Summary`
8. `Daily_Salesperson_Scorecard`
9. `Raw_Logs`
10. `Report_Archive`
11. `Salespeople`
12. `Users`
13. `Config`
14. `Demo_Data`
15. `QA_Checks`

Freeze row 1 on every tab. Use frozen headers on every tab. Freeze columns A:B on `Team_Scorecard`,
`Rep_Detail`, `Followups`, `Missing_Data`, and `Coaching_Flags`. Protect all
integration-owned tabs and all formula ranges when the live Sheet is created.
Hide `Users` by default because it contains raw Telegram identifiers. Keep
`Raw_Logs` available as source-of-truth data for operators, but hide Telegram ID
columns from manager-facing dashboard tabs.

## Visual System

- Use a dark navy title band with white text only on row 1 of dashboard tabs.
- Use white summary cards with subtle gray borders, 11 pt labels, and 18-22 pt
  values. Cards should be compact enough to keep the first follow-up/action rows
  visible without scrolling.
- Use manager-friendly labels: `People Spoken To`, `Test-Drive Rate`,
  `Offer/Worksheet Rate`, `Asked-for-Business Rate`, `Follow-up Capture`,
  `Process Completion`, `Incomplete Updates`, and `Coaching Attention`.
- Status chips:
  - `On Track`: green fill, dark green text.
  - `Watch`: amber fill, dark amber text.
  - `Needs Attention`: red fill, dark red text.
  - `No Update Yet`: light gray fill, dark gray text.
  - `Done`: green fill.
  - `Due Today`: blue fill.
  - `Overdue`: red fill.
  - `Upcoming`: light teal fill.
- Apply alternating row colors to all list sections after headers.
- Add filter views to `Team_Scorecard`, `Followups`, `Missing_Data`, and
  `Coaching_Flags`. Default filters should show active reps and open items.
- Use named ranges for formulas where practical: `RawLogs`, `DailySummary`,
  `DailyScorecard`, `FollowupsTable`, `MissingDataTable`, `CoachingFlagsTable`,
  and `SalespeopleTable`.
- Use sparklines for compact rep and team trend indicators where they improve
  scanability.

## Dashboard_Daily

Purpose: Ryan's executive cockpit for today's operating view.

Sections:
- Header: title, selected date, last generated time, and data status.
- Headline cards: active reps, logs submitted, people spoken to, appointments,
  test drives, worksheets/offers, asked-for-business count, follow-ups due,
  missing updates, and coaching attention.
- Sales-process progression: compact horizontal stage table for spoken-to,
  appointments, test drives, worksheets/offers, asked-for-business, and
  follow-ups captured. This is the team sales-process progression view.
- Recent activity: last 8 complete logs from `Raw_Logs`, showing submitted time,
  salesperson, interaction type, vehicle, next step, and safe customer reference.
  Do not show Telegram IDs.
- Follow-up pressure: counts for overdue, due today, and upcoming follow-ups.
- Missing update panel: active reps with no update and incomplete logs.
- Coaching attention panel: top 5 non-punitive coaching flags.
- Next manager actions: formula-driven prompts such as `Check overdue follow-up`,
  `Ask for missing next step`, `Review low follow-up capture`, or
  `No immediate action`.

Suggested formulas:
- Selected date in `B2`: `=MAX(Daily_Team_Summary!A:A)`
- Last refresh in `D2`: `=XLOOKUP($B$2,Daily_Team_Summary!A:A,Daily_Team_Summary!B:B,"")`
- Logs submitted: `=XLOOKUP($B$2,Daily_Team_Summary!A:A,Daily_Team_Summary!C:C,0)`
- Active reps: `=XLOOKUP($B$2,Daily_Team_Summary!A:A,Daily_Team_Summary!D:D,0)`
- Follow-ups due: `=COUNTIFS(Followups!A:A,$B$2,Followups!B:B,"due")+COUNTIFS(Followups!A:A,$B$2,Followups!B:B,"overdue")`
- Coaching attention: `=COUNTIFS(Coaching_Flags!A:A,$B$2)`
- Process completion score:
  `=AVERAGE(TestDriveRate,OfferRate,AskedForBusinessRate,FollowupCaptureRate,1-IncompleteUpdateRate)`

Charts:
- 7-day activity sparkline from `Daily_Team_Summary.total_updates`.
- Small stacked bar for team progression stages.
- Priority count donut is optional; prefer simple counts if space is tight.

Conditional formatting:
- Missing updates > 0: amber. Missing updates >= 2: red.
- Overdue follow-ups > 0: red.
- Process completion >= 80%: green; 60-79%: amber; below 60%: red.

## Team_Scorecard

Purpose: one row per salesperson for Ryan to compare activity quality without
public shaming.

Columns:
- Salesperson
- Active
- Logs Submitted
- People Spoken To
- Appointments
- Test Drives
- Worksheets/Offers
- Asked-for-Business Count
- Follow-ups Set
- Incomplete Updates
- Coaching Flags
- Test-Drive Rate
- Offer/Worksheet Rate
- Asked-for-Business Rate
- Follow-up Capture Rate
- Process Completion %
- Incomplete-Update Rate
- 7-Day Logs Trend
- Status
- Manager Next Action

Formula approach:
- Pull the latest report date from `Daily_Team_Summary`.
- Start with active rows from `Salespeople`.
- Use `SUMIFS` against `Daily_Salesperson_Scorecard` for daily counts.
- Use `COUNTIFS` against `Followups`, `Missing_Data`, and `Coaching_Flags`.
- Use `SPARKLINE(FILTER(...))` for the 7-day logs trend where available.

Metric definitions:
- `Test-Drive Rate = IFERROR(Test Drives / People Spoken To, 0)`
- `Offer/Worksheet Rate = IFERROR(Worksheets/Offers / Test Drives, 0)`
- `Asked-for-Business Rate = IFERROR(Asked-for-Business Count / Worksheets/Offers, 0)`
- `Follow-up Capture Rate = IFERROR(Follow-ups Set / Logs Submitted, 0)`
- `Incomplete-Update Rate = IFERROR(Incomplete Updates / Logs Submitted, 0)`
- `Process Completion % = AVERAGE(Test-Drive Rate, Offer/Worksheet Rate, Asked-for-Business Rate, Follow-up Capture Rate, 1 - Incomplete-Update Rate)`
- `7-Day Logs Trend = SPARKLINE(last seven Daily_Salesperson_Scorecard updates)`

Status rule:
- `Needs Attention`: overdue follow-up, no update, or process completion below
  50%.
- `Watch`: incomplete update, coaching flag, or process completion below 70%.
- `On Track`: active rep has a complete update and no urgent open item.
- `No Update Yet`: active rep has zero logs for selected date.

## Rep_Detail

Purpose: drill into one salesperson without leaving Sheets.

Controls:
- Cell `B2`: salesperson dropdown from active `Salespeople.display_name`.
- Cell `B3`: selected date, defaulting to latest report date.
- Optional cell `B4`: 7-day or 30-day window selector.

Sections:
- Selected salesperson summary: logs, people spoken to, appointments, test
  drives, worksheets/offers, asks, follow-ups, incomplete updates, coaching
  flags, process completion, and status.
- Recent logs: latest 10 rows from `Raw_Logs` for the selected salesperson,
  showing submitted time, interaction type, customer reference, vehicle, outcome,
  next step, follow-up date, and status. Hide Telegram IDs.
- Sales-process step completion: checklist-style stage table showing count,
  rate, and trend for spoken-to, test drive, offer/worksheet, asked for business,
  and follow-up captured.
- Follow-ups: overdue, due today, and upcoming items for the selected rep.
- Coaching notes: relevant `Coaching_Flags` rows with a manager-safe prompt.
- Progress over time: 7-day line chart or sparkline for logs submitted and
  process completion.
- Manager next-action prompts: deterministic text from status and open items.

Example prompt rules:
- Overdue follow-up: `Ask what happened with the overdue follow-up and confirm the next customer step.`
- Missing next step: `Ask for the next committed customer action before end of day.`
- Low offer rate: `Review whether test drives are converting into worksheet or offer conversations.`
- No update: `Check whether the rep needs help logging today's customer activity.`

## Followups

Purpose: Ryan's follow-up queue.

Manager-facing fields:
- Due Status
- Follow-up Date
- Salesperson
- Customer/Reference
- Vehicle
- Next Step
- Source Log Status
- Priority
- Manager Check

The existing integration-owned `Followups` tab contains the deterministic
follow-up queue from the daily report. In the live Sheet, add protected formula
columns to the right of the synced columns for `customer_reference`, `vehicle`,
`priority`, and `manager_check`, using `log_id` lookups into `Raw_Logs`. This
preserves sync compatibility while making the queue manager-readable.

Priority rules:
- Overdue: `High`
- Due today: `Today`
- Upcoming within 3 days: `Soon`
- Later upcoming: `Planned`

## Missing_Data

Purpose: identify data gaps with neutral wording.

Manager wording:
- `No update yet` instead of `failed to update`.
- `Needs one field completed` instead of `bad log`.
- `Roster check needed` for unregistered submitters.

Views:
- `No Update Yet`: roster members without complete updates.
- `Incomplete Logs`: logs with missing deterministic fields.
- `Roster Check`: unregistered submitters.

Conditional formatting:
- `roster_no_update`: amber.
- `incomplete_log`: light red only when missing next step, follow-up date, or
  outcome.
- `unregistered_submitter`: gray with `Roster check needed`.

## Coaching_Flags

Purpose: turn deterministic flags into coaching opportunities.

Manager-facing fields:
- Date
- Salesperson
- Opportunity
- What to Ask
- Related Log
- Status

Tone rules:
- Use non-punitive language: `opportunity`, `ask`, `check`, `support`,
  `clarify`.
- Avoid public shaming language such as `failure`, `bad`, `lazy`, or `blame`.
- Sort by overdue follow-ups first, then missing next steps, then process
  conversion opportunities.

Example prompts:
- `What is the next customer commitment?`
- `Was a worksheet or offer conversation appropriate after the test drive?`
- `Is there a follow-up date attached to this customer?`

## Raw_Logs

Purpose: source-of-truth view.

Keep every existing synced field. Freeze row 1, protect the entire sheet from
casual edits, and add a filter view for operators. It can remain more technical
and may contain raw internal IDs, but manager-facing dashboard tabs should not
surface Telegram IDs.

## Sales-Process Progression Metrics

All metrics are deterministic and derived from synced tabs:

- Log activity trend: 7-day count of `Daily_Salesperson_Scorecard.updates` by
  salesperson and 7-day count of `Daily_Team_Summary.total_updates` for team.
- Test-drive rate: `test_drives / people_spoken_to`.
- Offer/worksheet rate: `worksheets_offers / test_drives`.
- Asked-for-business rate: `asks_for_business / worksheets_offers`.
- Follow-up capture rate: follow-ups set divided by logs submitted, using
  `Followups.log_id` or `Raw_Logs.followup_date` when the daily follow-up table
  has not been generated yet.
- Process completion score: average of test-drive rate, offer/worksheet rate,
  asked-for-business rate, follow-up capture rate, and one minus
  incomplete-update rate.
- Incomplete-update rate: incomplete-log rows divided by logs submitted.
- Salesperson progress over time: daily `Process Completion %` and daily logs
  trend per salesperson.
- Team progress over time: daily aggregate process completion using
  `Daily_Team_Summary` and completion rollups from `Daily_Salesperson_Scorecard`.

Use `IFERROR(...,0)` for rate formulas. Format rates as percentages with zero
decimal places.
