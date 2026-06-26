/*
 * North Shore Sales Coach — Manager Dashboard builder
 * ---------------------------------------------------------------------------
 * Add this as a SEPARATE Apps Script file named "DemoDashboard" in the SAME
 * bound project as your working Code.gs bridge. It does NOT touch Code.gs,
 * doPost, doGet, the secret, or the /sync_sheets bridge.
 *
 * Main function:        buildNorthShoreLiveDashboard()   <- run this
 * Validate install:     validateNorthShoreDashboardInstall()
 * Optional demo data:   seedNorthShoreDemoDataSafely()
 * Optional demo build:  buildNorthShoreDemoDashboard()    (seed + build)
 *
 * Every helper is prefixed NSD_ / nsd to avoid collisions with the bridge.
 * Run note is at the very bottom of this file.
 */

var NSD_DASH = 'Dashboard';
var NSD_CALC = '_NSD_Calc';
var NSD_RAW = 'Raw_Logs';
var NSD_PEOPLE = 'Salespeople';
var NSD_MAX_REPS = 30;        // visible scorecard rows (auto-fills as reps are added)
var NSD_TREND_DAYS = 14;      // sparkline width
var NSD_LASTROW = 50001;      // bounded projection (well beyond a month of logs)
var NSD_INK = '#18324a';
var NSD_BLUE = '#2a78d6';
var NSD_MUTE = '#5f6b76';
var NSD_START_A1 = 'C4';
var NSD_END_A1 = 'E4';

/* ============================ PUBLIC ENTRY POINTS ========================= */

function buildNorthShoreLiveDashboard() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var v = nsdValidateCore_(ss);
  if (!v.ok) {
    nsdNotify_(ss, v.message);
    return v.message;
  }
  nsdBuildDashboardShell_(ss);          // creates Dashboard + date cells first
  nsdBuildCalcTab_(ss, v.rawMap, v.peopleMap);
  nsdBuildDashboardBody_(ss);           // fills KPIs/funnel/scorecard/rep detail
  var dash = ss.getSheetByName(NSD_DASH);
  ss.setActiveSheet(dash);
  ss.moveActiveSheet(1);
  nsdNotify_(ss, 'Dashboard built. Open the "Dashboard" tab.');
  return 'ok';
}

function buildNorthShoreDemoDashboard() {
  seedNorthShoreDemoDataSafely();
  return buildNorthShoreLiveDashboard();
}

function validateNorthShoreDashboardInstall() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var lines = [];
  lines.push('North Shore Dashboard — install check');
  lines.push('--------------------------------------');

  var needTabs = [NSD_PEOPLE, NSD_RAW];
  needTabs.forEach(function (t) {
    lines.push((ss.getSheetByName(t) ? 'OK   ' : 'MISSING ') + 'tab: ' + t);
  });

  var people = ss.getSheetByName(NSD_PEOPLE);
  var raw = ss.getSheetByName(NSD_RAW);
  var pMap = people ? nsdHeaderMap_(people) : {};
  var rMap = raw ? nsdHeaderMap_(raw) : {};

  ['salesperson_id', 'display_name', 'active'].forEach(function (h) {
    lines.push((pMap[h] != null ? 'OK   ' : 'MISSING ') + 'Salespeople header: ' + h);
  });
  ['salesperson_id', 'submitted_at', 'people_spoken_to', 'test_drive',
    'worksheet_or_offer_presented', 'asked_for_business', 'outcome'].forEach(function (h) {
    lines.push((rMap[h] != null ? 'OK   ' : 'MISSING ') + 'Raw_Logs header: ' + h);
  });

  var activeCount = people ? nsdCountActive_(people, pMap) : 0;
  var rawRows = raw ? Math.max(raw.getLastRow() - 1, 0) : 0;
  lines.push('Active salespeople: ' + activeCount);
  lines.push('Raw_Logs data rows: ' + rawRows);

  var core = nsdValidateCore_(ss);
  lines.push(core.ok ? 'Safe to build: YES' : 'Safe to build: NO — ' + core.message);
  lines.push('External access required: NONE (no secrets, URLs, Sheet IDs, tokens, Telegram, Hermes, Composio).');
  if (activeCount === 0) {
    lines.push('Note: no active salespeople yet — the Dashboard will show "No active salespeople are configured yet." until reps sync in, or run seedNorthShoreDemoDataSafely.');
  }

  var summary = lines.join('\n');
  Logger.log(summary);
  nsdNotify_(ss, core.ok ? 'Validation passed. See execution log for details.' : core.message);
  return summary;
}

/* ============================== VALIDATION ================================ */

function nsdValidateCore_(ss) {
  var people = ss.getSheetByName(NSD_PEOPLE);
  var raw = ss.getSheetByName(NSD_RAW);
  if (!people) return { ok: false, message: 'Missing required tab: ' + NSD_PEOPLE };
  if (!raw) return { ok: false, message: 'Missing required tab: ' + NSD_RAW };

  var pMap = nsdHeaderMap_(people);
  var rMap = nsdHeaderMap_(raw);
  var needP = ['salesperson_id', 'display_name', 'active'];
  for (var i = 0; i < needP.length; i++) {
    if (pMap[needP[i]] == null) return { ok: false, message: 'Salespeople is missing header: ' + needP[i] };
  }
  var needR = ['salesperson_id', 'submitted_at'];
  for (var j = 0; j < needR.length; j++) {
    if (rMap[needR[j]] == null) return { ok: false, message: 'Raw_Logs is missing header: ' + needR[j] };
  }
  return { ok: true, message: 'ok', rawMap: rMap, peopleMap: pMap };
}

/* ============================== HELPERS =================================== */

function nsdHeaderMap_(sheet) {
  var lastCol = sheet.getLastColumn();
  if (lastCol < 1) return {};
  var headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  var map = {};
  for (var c = 0; c < headers.length; c++) {
    var key = String(headers[c]).trim().toLowerCase();
    if (key !== '') map[key] = c; // 0-based index
  }
  return map;
}

function nsdColLetter_(index1) {
  var s = '';
  var n = index1;
  while (n > 0) {
    var m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function nsdRawCol_(rMap, name) {
  return rMap[name] != null ? nsdColLetter_(rMap[name] + 1) : null;
}

function nsdRng_(sheet, letter) {
  return sheet + '!$' + letter + '$2:$' + letter + '$' + NSD_LASTROW;
}

function nsdTrue_(r) {
  return '((' + r + '=TRUE)+(' + r + '=1)+(UPPER(TO_TEXT(' + r + '))="TRUE")+(UPPER(TO_TEXT(' + r + '))="YES")>0)';
}

function nsdSold_(r) {
  return '((LOWER(TO_TEXT(' + r + '))="sold")+(LOWER(TO_TEXT(' + r + '))="won")+(LOWER(TO_TEXT(' + r + '))="sale")+(LOWER(TO_TEXT(' + r + '))="delivered")>0)';
}

function nsdDate_(r) {
  return 'IF(' + r + '="","",IF(ISNUMBER(' + r + '),INT(' + r + '),IFERROR(DATEVALUE(LEFT(TO_TEXT(' + r + '),10)),"")))';
}

function nsdActiveMask_(pMap) {
  var aL = nsdColLetter_(pMap['active'] + 1);
  var r = NSD_PEOPLE + '!$' + aL + '$2:$' + aL + '$' + NSD_LASTROW;
  return '((' + r + '=TRUE)+(' + r + '=1)+(UPPER(TO_TEXT(' + r + '))="TRUE")+(UPPER(TO_TEXT(' + r + '))="YES")+(UPPER(TO_TEXT(' + r + '))="1")>0)';
}

function nsdCountActive_(peopleSheet, pMap) {
  var last = peopleSheet.getLastRow();
  if (last < 2 || pMap['active'] == null || pMap['salesperson_id'] == null) return 0;
  var vals = peopleSheet.getRange(2, 1, last - 1, peopleSheet.getLastColumn()).getValues();
  var aIdx = pMap['active'], idIdx = pMap['salesperson_id'];
  var n = 0;
  vals.forEach(function (row) {
    if (String(row[idIdx]).trim() === '') return;
    if (nsdIsTrue_(row[aIdx])) n++;
  });
  return n;
}

function nsdIsTrue_(v) {
  if (v === true || v === 1) return true;
  var s = String(v).trim().toLowerCase();
  return s === 'true' || s === 'yes' || s === '1';
}

function nsdNotify_(ss, msg) {
  try { ss.toast(msg, 'North Shore', 6); } catch (e) {}
  Logger.log(msg);
}

/* ============================ CALC (HIDDEN) ============================== */

function nsdBuildCalcTab_(ss, rMap, pMap) {
  var old = ss.getSheetByName(NSD_CALC);
  if (old) ss.deleteSheet(old);
  var sh = ss.insertSheet(NSD_CALC);

  var idL = nsdRawCol_(rMap, 'salesperson_id');
  var dateL = nsdRawCol_(rMap, 'submitted_at');
  var spokeL = nsdRawCol_(rMap, 'people_spoken_to');
  var apptL = nsdRawCol_(rMap, 'appointment_count');
  var walkL = nsdRawCol_(rMap, 'walk_in_count');
  var tdL = nsdRawCol_(rMap, 'test_drive');
  var offerL = nsdRawCol_(rMap, 'worksheet_or_offer_presented');
  var askL = nsdRawCol_(rMap, 'asked_for_business');
  var outL = nsdRawCol_(rMap, 'outcome');
  var fuL = nsdRawCol_(rMap, 'followup_date');
  var statusL = nsdRawCol_(rMap, 'status');
  var missL = nsdRawCol_(rMap, 'missing_fields_json');

  var rawId = nsdRng_(NSD_RAW, idL);
  var A = '$A$2:$A$' + NSD_LASTROW;
  var B = '$B$2:$B$' + NSD_LASTROW;
  var C = '$C$2:$C$' + NSD_LASTROW;
  var O = '$O$2:$O$' + NSD_LASTROW;
  var dStart = 'Dashboard!$C$4';
  var dEnd = 'Dashboard!$E$4';

  function num(L) { return L ? 'N(' + nsdRng_(NSD_RAW, L) + ')' : '0'; }
  function boolT(L) { return L ? nsdTrue_(nsdRng_(NSD_RAW, L)) : 'FALSE'; }

  // ---- Block 1: per-row projection (bounded) ----
  sh.getRange('A2').setFormula('=ARRAYFORMULA(IF(' + rawId + '="","",' + rawId + '))');
  sh.getRange('B2').setFormula('=ARRAYFORMULA(IF(' + rawId + '="","",' + nsdDate_(nsdRng_(NSD_RAW, dateL)) + '))');
  sh.getRange('C2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",IF(' + B + '="",0,(' + B + '>=' + dStart + ')*(' + B + '<=' + dEnd + '))))');
  sh.getRange('D2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",' + num(spokeL) + '*' + C + '))');
  sh.getRange('E2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",' + num(apptL) + '*' + C + '))');
  sh.getRange('F2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",' + num(walkL) + '*' + C + '))');
  sh.getRange('G2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",N(' + boolT(tdL) + ')*' + C + '))');
  sh.getRange('H2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",N(' + boolT(offerL) + ')*' + C + '))');
  sh.getRange('I2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",N(' + boolT(askL) + ')*' + C + '))');
  sh.getRange('J2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",N(' + (outL ? nsdSold_(nsdRng_(NSD_RAW, outL)) : 'FALSE') + ')*' + C + '))');
  sh.getRange('K2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",N(' + boolT(tdL) + ')*(1-N(' + boolT(offerL) + '))*' + C + '))');
  sh.getRange('L2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",N(' + boolT(offerL) + ')*(1-N(' + boolT(askL) + '))*' + C + '))');

  var missingExpr;
  if (statusL && missL) {
    missingExpr = '((LOWER(TO_TEXT(' + nsdRng_(NSD_RAW, statusL) + '))<>"complete")+(IF(' + nsdRng_(NSD_RAW, missL) + '="",0,IF(' + nsdRng_(NSD_RAW, missL) + '="[]",0,1)))>0)';
  } else if (statusL) {
    missingExpr = '(LOWER(TO_TEXT(' + nsdRng_(NSD_RAW, statusL) + '))<>"complete")';
  } else if (missL) {
    missingExpr = '(IF(' + nsdRng_(NSD_RAW, missL) + '="",0,IF(' + nsdRng_(NSD_RAW, missL) + '="[]",0,1))>0)';
  } else {
    missingExpr = 'FALSE';
  }
  sh.getRange('M2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",N(' + missingExpr + ')*' + C + '))');
  sh.getRange('N2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",' + C + '))');

  if (fuL) {
    sh.getRange('O2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",' + nsdDate_(nsdRng_(NSD_RAW, fuL)) + '))');
    var notSold = outL ? '(1-N(' + nsdSold_(nsdRng_(NSD_RAW, outL)) + '))' : '1';
    sh.getRange('P2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",IF(' + O + '="",0,(' + O + '<TODAY())*' + notSold + ')))');
    sh.getRange('Q2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",IF(' + O + '="",0,(' + O + '>=TODAY())*' + notSold + ')))');
  } else {
    sh.getRange('O2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",""))');
    sh.getRange('P2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",0))');
    sh.getRange('Q2').setFormula('=ARRAYFORMULA(IF(' + A + '="","",0))');
  }

  // ---- Block 2: active roster (spills T:U) ----
  var pIdL = nsdColLetter_(pMap['salesperson_id'] + 1);
  var pNmL = nsdColLetter_(pMap['display_name'] + 1);
  var idRange = NSD_PEOPLE + '!$' + pIdL + '$2:$' + pIdL + '$' + NSD_LASTROW;
  var nmRange = NSD_PEOPLE + '!$' + pNmL + '$2:$' + pNmL + '$' + NSD_LASTROW;
  var mask = '(' + nsdActiveMask_(pMap) + ')*(' + idRange + '<>"")';
  sh.getRange('T2').setFormula('=IFERROR(SORT(FILTER({' + idRange + ',' + nmRange + '},' + mask + '),2,TRUE),"")');

  // ---- Block 3: per-rep aggregates (rows 2..NSD_MAX_REPS+1) ----
  var rEnd = NSD_MAX_REPS + 1;
  var T = '$T$2:$T$' + rEnd;
  function sumif(valCol) { return 'SUMIF($A$2:$A$' + NSD_LASTROW + ',' + T + ',$' + valCol + '$2:$' + valCol + '$' + NSD_LASTROW + ')'; }
  function agg(a1, body) { sh.getRange(a1).setFormula('=ARRAYFORMULA(IF(' + T + '="","",' + body + '))'); }
  agg('W2', sumif('D'));  // people
  agg('X2', sumif('E'));  // appointments
  agg('Y2', sumif('G'));  // test drives
  agg('Z2', sumif('H'));  // offers
  agg('AA2', sumif('I')); // asks
  agg('AB2', sumif('J')); // sold
  agg('AC2', sumif('N')); // interactions
  agg('AD2', sumif('M')); // missing
  agg('AE2', sumif('P')); // overdue
  agg('AF2', sumif('Q')); // open follow-ups
  agg('AG2', 'IF($W$2:$W$' + rEnd + '=0,0,$Y$2:$Y$' + rEnd + '/$W$2:$W$' + rEnd + ')'); // td rate
  agg('AH2', 'IF($Y$2:$Y$' + rEnd + '=0,0,$Z$2:$Z$' + rEnd + '/$Y$2:$Y$' + rEnd + ')'); // offer rate
  agg('AI2', 'IF($Z$2:$Z$' + rEnd + '=0,0,$AA$2:$AA$' + rEnd + '/$Z$2:$Z$' + rEnd + ')'); // ask rate
  agg('AJ2', 'ROUND(($AG$2:$AG$' + rEnd + '+$AH$2:$AH$' + rEnd + '+$AI$2:$AI$' + rEnd + ')/3*100,0)'); // process
  agg('AK2', 'IF($AC$2:$AC$' + rEnd + '=0,"No update",IF(($AJ$2:$AJ$' + rEnd + '<45)+($AE$2:$AE$' + rEnd + '>0)>0,"Needs attention",IF(($AJ$2:$AJ$' + rEnd + '<65)+($AD$2:$AD$' + rEnd + '>0)+($AH$2:$AH$' + rEnd + '<0.4)>0,"Watch","On track")))');
  agg('AL2', 'IF($AC$2:$AC$' + rEnd + '=0,"No update in range",IF($AE$2:$AE$' + rEnd + '>0,"Follow up today",IF($AH$2:$AH$' + rEnd + '<0.5,"Coach on offer progression",IF($AI$2:$AI$' + rEnd + '<0.5,"Ask-for-business gap",IF($AF$2:$AF$' + rEnd + '>0,"Check next step",IF($AD$2:$AD$' + rEnd + '>0,"Complete the update","On track - reinforce"))))))');

  // ---- Block 4: trend grid (rows 2..NSD_MAX_REPS+1, cols AN..) ----
  var anCol = 40; // AN
  var hdr = [];
  for (var d = 0; d < NSD_TREND_DAYS; d++) {
    if (d === 0) {
      hdr.push('=MAX(' + dStart + ',' + dEnd + '-' + (NSD_TREND_DAYS - 1) + ')');
    } else {
      var prev = nsdColLetter_(anCol + d - 1) + '$1';
      hdr.push('=IF(' + prev + '="","",IF(' + prev + '+1>' + dEnd + ',"",' + prev + '+1))');
    }
  }
  sh.getRange(1, anCol, 1, NSD_TREND_DAYS).setFormulas([hdr]);

  var grid = [];
  for (var r = 0; r < NSD_MAX_REPS; r++) {
    var rowNo = 2 + r;
    var cells = [];
    for (var c2 = 0; c2 < NSD_TREND_DAYS; c2++) {
      var hcell = nsdColLetter_(anCol + c2) + '$1';
      cells.push('=IF(OR($T' + rowNo + '="",' + hcell + '=""),"",SUMIFS($N$2:$N$' + NSD_LASTROW + ',$A$2:$A$' + NSD_LASTROW + ',$T' + rowNo + ',$B$2:$B$' + NSD_LASTROW + ',' + hcell + '))');
    }
    grid.push(cells);
  }
  sh.getRange(2, anCol, NSD_MAX_REPS, NSD_TREND_DAYS).setFormulas(grid);

  sh.hideSheet();
}

/* ============================ DASHBOARD SHELL ============================ */

function nsdBuildDashboardShell_(ss) {
  var old = ss.getSheetByName(NSD_DASH);
  if (old) ss.deleteSheet(old);
  var sh = ss.insertSheet(NSD_DASH, 0);
  sh.setHiddenGridlines(true);
  sh.setTabColor(NSD_BLUE);

  sh.getRange('A1:N1').merge().setValue('North Shore Sales Coach')
    .setFontSize(20).setFontWeight('bold').setFontColor('#ffffff')
    .setBackground(NSD_INK).setVerticalAlignment('middle');
  sh.setRowHeight(1, 44);
  sh.getRange('A2:N2').merge().setValue('Manager Dashboard  ·  Live from Telegram sales updates synced to this Sheet')
    .setFontColor('#ffffff').setBackground('#22405c');

  sh.getRange('A3:N3').merge()
    .setValue('Built ' + Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'EEE d MMM yyyy HH:mm'))
    .setFontColor(NSD_MUTE).setFontSize(11);

  sh.getRange('A4').setValue('Date range:').setFontColor(NSD_MUTE).setHorizontalAlignment('right');
  sh.getRange(NSD_START_A1).setFormula('=TODAY()-6').setNumberFormat('ddd d mmm').setHorizontalAlignment('center').setBackground('#eef3f8').setFontWeight('bold');
  sh.getRange('D4').setValue('to').setFontColor(NSD_MUTE).setHorizontalAlignment('center');
  sh.getRange(NSD_END_A1).setFormula('=TODAY()').setNumberFormat('ddd d mmm').setHorizontalAlignment('center').setBackground('#eef3f8').setFontWeight('bold');
  sh.getRange('G4').setFormula('=IF((' + NSD_END_A1 + '-' + NSD_START_A1 + ')=6,"Last 7 days",TEXT(' + NSD_END_A1 + '-' + NSD_START_A1 + '+1,"0")&" days")')
    .setFontColor(NSD_MUTE);
}

/* ============================ DASHBOARD BODY ============================= */

function nsdBuildDashboardBody_(ss) {
  var sh = ss.getSheetByName(NSD_DASH);
  var C = NSD_CALC + '!';
  function colSum(L) { return '=SUM(' + C + '$' + L + '$2:$' + L + '$' + NSD_LASTROW + ')'; }
  var rEnd = NSD_MAX_REPS + 1;

  // ----- KPI cards (2 rows x 5) -----
  var kpis = [
    ['Customer updates', colSum('N')],
    ['People spoken to', colSum('D')],
    ['Appointments', colSum('E')],
    ['Test drives', colSum('G')],
    ['Offers / worksheets', colSum('H')],
    ['Asked for business', colSum('I')],
    ['Sold / won', colSum('J')],
    ['Follow-ups overdue', colSum('P')],
    ['Missing / incomplete', colSum('M')],
    ['Active reps', '=SUMPRODUCT(--(' + C + '$U$2:$U$' + rEnd + '<>""))']
  ];
  var starts = [1, 4, 7, 10, 13];
  for (var k = 0; k < kpis.length; k++) {
    var rowBlock = (k < 5) ? 6 : 9;
    var col = starts[k % 5];
    nsdCard_(sh, col, rowBlock, kpis[k][0], kpis[k][1], '#eef3f8', '#111111');
  }

  // ----- Funnel -----
  sh.getRange('A12:N12').merge().setValue('Sales funnel — selected range').setFontWeight('bold');
  var stages = [
    ['People spoken to', colSum('D')],
    ['Test drives', colSum('G')],
    ['Offers / worksheets', colSum('H')],
    ['Asked for business', colSum('I')],
    ['Sold / won', colSum('J')]
  ];
  for (var s = 0; s < stages.length; s++) {
    var r = 13 + s;
    sh.getRange('A' + r + ':C' + r).merge().setValue(stages[s][0]).setFontColor('#3a4754');
    sh.getRange('D' + r).setFormula(stages[s][1]).setFontWeight('bold').setHorizontalAlignment('center');
    sh.getRange('E' + r + ':L' + r).merge()
      .setFormula('=IFERROR(SPARKLINE($D' + r + ',{"charttype","bar";"max",$D$13;"color1","' + NSD_BLUE + '"}),"")');
    if (s > 0) {
      sh.getRange('M' + r + ':N' + r).merge()
        .setFormula('=IFERROR($D' + r + '/$D' + (r - 1) + ',0)').setNumberFormat('0%')
        .setFontColor(NSD_MUTE).setHorizontalAlignment('right');
    }
  }
  sh.getRange('M13:N13').merge().setValue('step %').setFontColor('#9aa6b2').setFontSize(10).setHorizontalAlignment('right');

  // ----- Needs attention -----
  sh.getRange('A19:N19').merge().setValue('Needs attention').setFontWeight('bold');
  var attn = [
    ['Follow up today', colSum('P')],
    ['Coach on offers', colSum('K')],
    ['Ask-for-business gap', colSum('L')],
    ['Check the update', colSum('M')],
    ['No update in range', '=SUMPRODUCT((' + C + '$U$2:$U$' + rEnd + '<>"")*(' + C + '$AC$2:$AC$' + rEnd + '=0))']
  ];
  for (var a = 0; a < attn.length; a++) {
    nsdCard_(sh, starts[a], 20, attn[a][0], attn[a][1], '#fbeae1', '#9a3412');
  }

  // ----- Team scorecard -----
  var hdr = 23;
  sh.getRange('A' + hdr + ':N' + hdr).merge().setValue('Team scorecard').setFontWeight('bold');
  var cols = ['Rep', 'Status', 'People', 'Appts', 'Test drives', 'TD %', 'Offers', 'Offer %', 'Asked', 'Ask %', 'Sold', 'Process', 'Coaching focus', 'Trend'];
  sh.getRange(hdr + 1, 1, 1, 14).setValues([cols]).setFontColor('#ffffff').setBackground(NSD_INK).setFontWeight('bold').setWrap(true);

  // empty-state note (shows only when zero active reps)
  sh.getRange('E' + hdr + ':N' + hdr).setFormula('=IF(SUMPRODUCT(--(' + C + '$U$2:$U$' + rEnd + '<>""))=0,"No active salespeople are configured yet.","")')
    .setFontColor('#9a3412').setHorizontalAlignment('left');

  var firstRow = hdr + 2;
  var idxCalc = { name: 'U', status: 'AK', people: 'W', appts: 'X', td: 'Y', tdr: 'AG', off: 'Z', ofr: 'AH', ask: 'AA', akr: 'AI', sold: 'AB', proc: 'AJ', coach: 'AL' };
  var block = [];
  for (var rr = 0; rr < NSD_MAX_REPS; rr++) {
    var pos = rr + 1; // roster position
    var dr = firstRow + rr;
    var nameF = '=IFERROR(INDEX(' + C + '$' + idxCalc.name + '$2:$' + idxCalc.name + '$' + rEnd + ',' + pos + '),"")';
    var trendRow = 2 + rr;
    var trendF = '=IF($A' + dr + '="","",IFERROR(SPARKLINE(' + C + '$AN$' + trendRow + ':$BA$' + trendRow + ',{"charttype","column";"color","' + NSD_BLUE + '";"empty","zero"}),""))';
    block.push([
      nameF,
      nsdPick_(C, idxCalc.status, rEnd, pos, dr, '""'),
      nsdPick_(C, idxCalc.people, rEnd, pos, dr, '0'),
      nsdPick_(C, idxCalc.appts, rEnd, pos, dr, '0'),
      nsdPick_(C, idxCalc.td, rEnd, pos, dr, '0'),
      nsdPick_(C, idxCalc.tdr, rEnd, pos, dr, '0'),
      nsdPick_(C, idxCalc.off, rEnd, pos, dr, '0'),
      nsdPick_(C, idxCalc.ofr, rEnd, pos, dr, '0'),
      nsdPick_(C, idxCalc.ask, rEnd, pos, dr, '0'),
      nsdPick_(C, idxCalc.akr, rEnd, pos, dr, '0'),
      nsdPick_(C, idxCalc.sold, rEnd, pos, dr, '0'),
      nsdPick_(C, idxCalc.proc, rEnd, pos, dr, '0'),
      nsdPick_(C, idxCalc.coach, rEnd, pos, dr, '""'),
      trendF
    ]);
  }
  sh.getRange(firstRow, 1, NSD_MAX_REPS, 14).setFormulas(block);
  sh.getRange(firstRow, 6, NSD_MAX_REPS, 1).setNumberFormat('0%');
  sh.getRange(firstRow, 8, NSD_MAX_REPS, 1).setNumberFormat('0%');
  sh.getRange(firstRow, 10, NSD_MAX_REPS, 1).setNumberFormat('0%');
  sh.getRange(firstRow, 1, NSD_MAX_REPS, 14).setBorder(true, true, true, true, true, true, '#e3e9ef', SpreadsheetApp.BorderStyle.SOLID);
  nsdStatusCF_(sh, 'B' + firstRow + ':B' + (firstRow + NSD_MAX_REPS - 1));

  // ----- Rep detail -----
  var rd = firstRow + NSD_MAX_REPS + 1;
  sh.getRange('A' + rd + ':N' + rd).merge().setValue('Rep detail').setFontWeight('bold');
  sh.getRange('A' + (rd + 1)).setValue('Select rep:').setFontColor(NSD_MUTE).setHorizontalAlignment('right');
  var selCell = 'B' + (rd + 1);
  var sel = sh.getRange(selCell);
  sel.setDataValidation(SpreadsheetApp.newDataValidation().requireValueInRange(ss.getSheetByName(NSD_CALC).getRange('$U$2:$U$' + rEnd), true).build());
  sel.setBackground('#eef3f8').setFontWeight('bold');
  var firstName = nsdFirstActiveName_(ss);
  if (firstName) sel.setValue(firstName);

  var mIdx = 'IFERROR(MATCH($' + selCell + ',' + C + '$U$2:$U$' + rEnd + ',0),0)';
  function repVal(letter) {
    return '=IF($' + selCell + '="","",IFERROR(INDEX(' + C + '$' + letter + '$2:$' + letter + '$' + rEnd + ',' + mIdx + '),0))';
  }
  function repTxt(letter) {
    return '=IF($' + selCell + '="","",IFERROR(INDEX(' + C + '$' + letter + '$2:$' + letter + '$' + rEnd + ',' + mIdx + '),""))';
  }
  var detail = [
    ['Status', repTxt('AK')],
    ['Customer updates', repVal('AC')],
    ['People spoken to', repVal('W')],
    ['Appointments', repVal('X')],
    ['Test drives', repVal('Y')],
    ['Offers / worksheets', repVal('Z')],
    ['Asked for business', repVal('AA')],
    ['Sold / won', repVal('AB')],
    ['Open follow-ups', repVal('AF')],
    ['Overdue follow-ups', repVal('AE')],
    ['Missing / incomplete', repVal('AD')]
  ];
  for (var di = 0; di < detail.length; di++) {
    var drow = rd + 2 + di;
    sh.getRange('A' + drow + ':C' + drow).merge().setValue(detail[di][0]).setFontColor('#3a4754');
    sh.getRange('D' + drow).setFormula(detail[di][1]).setFontWeight('bold');
  }
  var coachRow = rd + 2 + detail.length;
  sh.getRange('A' + coachRow + ':C' + coachRow).merge().setValue('Coaching focus').setFontWeight('bold').setFontColor('#185fa5');
  sh.getRange('D' + coachRow + ':N' + coachRow).merge()
    .setFormula('=IF($' + selCell + '="","",IFERROR(INDEX(' + C + '$AL$2:$AL$' + rEnd + ',' + mIdx + '),""))')
    .setFontColor('#185fa5').setBackground('#e6f1fb');

  // ----- widths / freeze -----
  sh.setColumnWidth(1, 150);
  sh.setColumnWidths(2, 13, 84);
  sh.setColumnWidth(13, 150);
  sh.setFrozenRows(2);
}

function nsdPick_(C, letter, rEnd, pos, dr, blank) {
  return '=IF($A' + dr + '="","",IFERROR(INDEX(' + C + '$' + letter + '$2:$' + letter + '$' + rEnd + ',' + pos + '),' + blank + '))';
}

function nsdCard_(sh, startCol, labelRow, label, valueFormula, bg, fc) {
  var lab = sh.getRange(labelRow, startCol, 1, 2).merge();
  lab.setValue(label).setFontColor(NSD_MUTE).setFontSize(11).setHorizontalAlignment('center').setBackground(bg);
  var val = sh.getRange(labelRow + 1, startCol, 1, 2).merge();
  val.setFormula(valueFormula).setFontSize(20).setFontWeight('bold').setFontColor(fc).setHorizontalAlignment('center').setBackground(bg);
  sh.getRange(labelRow, startCol, 2, 2).setBorder(true, true, true, true, true, true, '#d6e0ea', SpreadsheetApp.BorderStyle.SOLID);
}

function nsdStatusCF_(sh, a1) {
  var range = sh.getRange(a1);
  var rules = sh.getConditionalFormatRules();
  function rule(text, bg, fc) {
    return SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo(text)
      .setBackground(bg).setFontColor(fc).setRanges([range]).build();
  }
  rules.push(rule('On track', '#d9ead3', '#274e13'));
  rules.push(rule('Watch', '#fff2cc', '#7f6000'));
  rules.push(rule('Needs attention', '#f4cccc', '#990000'));
  rules.push(rule('No update', '#eef0f2', '#5f6b76'));
  sh.setConditionalFormatRules(rules);
}

function nsdFirstActiveName_(ss) {
  var people = ss.getSheetByName(NSD_PEOPLE);
  var pMap = nsdHeaderMap_(people);
  var last = people.getLastRow();
  if (last < 2) return '';
  var vals = people.getRange(2, 1, last - 1, people.getLastColumn()).getValues();
  var names = [];
  vals.forEach(function (row) {
    if (String(row[pMap['salesperson_id']]).trim() === '') return;
    if (nsdIsTrue_(row[pMap['active']])) names.push(String(row[pMap['display_name']]));
  });
  names.sort();
  return names.length ? names[0] : '';
}

/* ====================== OPTIONAL: SAFE DEMO DATA ========================= */

function seedNorthShoreDemoDataSafely() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var people = ss.getSheetByName(NSD_PEOPLE);
  var raw = ss.getSheetByName(NSD_RAW);
  if (!people || !raw) { nsdNotify_(ss, 'Cannot seed: Salespeople or Raw_Logs tab is missing.'); return 'missing tabs'; }

  var pMap = nsdHeaderMap_(people);
  var rMap = nsdHeaderMap_(raw);

  nsdRemoveDemoRows_(people, function (row) {
    var id = String(row[pMap['salesperson_id']] || '');
    return id.indexOf('demo-') === 0 || id.indexOf('ns-demo-') === 0;
  });
  nsdRemoveDemoRows_(raw, function (row) {
    var src = String(rMap['source'] != null ? row[rMap['source']] : '');
    var id = String(rMap['log_id'] != null ? row[rMap['log_id']] : '');
    return src === 'demo_seed' || id.indexOf('demo-') === 0;
  });

  var gen = nsdGenerateDemo_();
  nsdAppendByHeaders_(people, pMap, gen.salespeople);
  nsdAppendByHeaders_(raw, rMap, gen.logs);
  nsdNotify_(ss, 'Demo data seeded (' + gen.salespeople.length + ' reps, ' + gen.logs.length + ' logs). Now run buildNorthShoreLiveDashboard.');
  return 'ok';
}

function nsdRemoveDemoRows_(sheet, isDemoFn) {
  var last = sheet.getLastRow();
  if (last < 2) return;
  var width = sheet.getLastColumn();
  var data = sheet.getRange(2, 1, last - 1, width).getValues();
  for (var i = data.length - 1; i >= 0; i--) {
    if (isDemoFn(data[i])) sheet.deleteRow(i + 2);
  }
}

function nsdAppendByHeaders_(sheet, map, objRows) {
  if (!objRows.length) return;
  var width = sheet.getLastColumn();
  var out = objRows.map(function (obj) {
    var arr = [];
    for (var c = 0; c < width; c++) arr.push('');
    Object.keys(obj).forEach(function (key) {
      if (map[key] != null) arr[map[key]] = obj[key];
    });
    return arr;
  });
  sheet.getRange(sheet.getLastRow() + 1, 1, out.length, width).setValues(out);
}

function nsdGenerateDemo_() {
  var reps = [
    { id: 'ns-demo-marcus', name: 'Marcus Bell', init: 'M', q: { cust: 9, td: 7, offer: 5, ask: 4, sold: 3 }, weak: false },
    { id: 'ns-demo-priya', name: 'Priya Shah', init: 'P', q: { cust: 8, td: 5, offer: 4, ask: 3, sold: 1 }, weak: false },
    { id: 'ns-demo-dani', name: 'Dani Cole', init: 'D', q: { cust: 7, td: 4, offer: 2, ask: 1, sold: 1 }, weak: false },
    { id: 'ns-demo-sara', name: 'Sara Lund', init: 'S', q: { cust: 8, td: 5, offer: 2, ask: 0, sold: 0 }, weak: true },
    { id: 'ns-demo-tom', name: 'Tom Reyes', init: 'T', q: { cust: 0, td: 0, offer: 0, ask: 0, sold: 0 }, weak: false }
  ];
  var vehicles = ['CR-V', 'Civic', 'Pilot', 'Accord', 'HR-V', 'Passport'];
  var nowIso = new Date().toISOString();
  var today = new Date(); today = new Date(today.getFullYear(), today.getMonth(), today.getDate());

  var salespeople = reps.map(function (r) {
    return { salesperson_id: r.id, display_name: r.name, active: true, telegram_user_id: '', created_at: nowIso, updated_at: nowIso };
  });

  var logs = [];
  reps.forEach(function (r) {
    for (var i = 0; i < r.q.cust; i++) {
      var dayOffset = i % 7;
      var d = new Date(today); d.setDate(d.getDate() - dayOffset);
      var isAppt = (i % 3 === 0);
      var td = i < r.q.td, offer = i < r.q.offer, ask = i < r.q.ask, sold = i < r.q.sold;
      var outcome = sold ? 'sold' : (offer ? 'follow_up' : (td ? 'thinking' : 'browsing'));
      var lead = (i % 4 === 0) ? '' : (isAppt ? 'phone' : 'showroom');
      var nextStep = sold ? 'delivery' : (offer ? 'follow up' : (td ? 'present numbers' : ''));
      var fdate = '';
      if (outcome === 'follow_up') {
        if (r.weak) { if (i % 2 === 0) { var od = new Date(today); od.setDate(od.getDate() - (2 + i)); fdate = od; } }
        else { var fu = new Date(today); fu.setDate(fu.getDate() + (1 + (i % 3))); fdate = fu; }
      }
      logs.push({
        log_id: 'demo-' + r.id + '-' + (i + 1),
        submitted_at: d,
        telegram_user_id: '',
        salesperson_id: r.id,
        source: 'demo_seed',
        raw_text: r.name.split(' ')[0] + ' logged a ' + (isAppt ? 'booked appointment' : 'walk-in'),
        customer_type: isAppt ? 'appointment' : 'walk-in',
        customer_name_or_ref: 'Customer ' + r.init + (i + 1),
        vehicle_interest: vehicles[i % vehicles.length],
        lead_source: lead,
        interaction_type: isAppt ? 'appointment' : 'walk_in',
        appointment_count: isAppt ? 1 : 0,
        walk_in_count: isAppt ? 0 : 1,
        people_spoken_to: 1,
        test_drive: td,
        worksheet_or_offer_presented: offer,
        asked_for_business: ask,
        outcome: outcome,
        next_step: nextStep,
        followup_date: fdate,
        notes: '',
        missing_fields_json: '[]',
        coaching_flags_json: '[]',
        confidence: 0.9,
        status: 'complete',
        llm_used: false,
        llm_tokens_estimate: ''
      });
    }
  });
  return { salespeople: salespeople, logs: logs };
}

/*
 * RUN NOTE
 * 1. Keep existing Code.gs unchanged.
 * 2. In the same bound Apps Script project, add a new script file named DemoDashboard
 *    (if an older DemoDashboard file exists, replace its entire contents with this).
 * 3. Paste this complete file. Save.
 * 4. Run validateNorthShoreDashboardInstall  (check the execution log).
 * 5. Run buildNorthShoreLiveDashboard.
 * 6. Refresh the Google Sheet and open the Dashboard tab.
 * 7. Only run seedNorthShoreDemoDataSafely or buildNorthShoreDemoDashboard if you
 *    intentionally want fake demo data in the Sheet.
 * 8. Do not create a new Web App deployment — the bridge endpoint is untouched.
 */
