/**
 * Kadunde Super League - auto-updater (Google Apps Script)
 * Pulls league standings, per-gameweek points, transfer hits and chips
 * from the official FPL API into the tabs: Managers, GW Points, GW Hits, Chips Log.
 * Every other tab is formulas, so they update by themselves.
 */
const LEAGUE_ID = 68704;
const BASE = 'https://fantasy.premierleague.com/api/';
const HEADERS = { 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json' };

// Adds a "Kadunde" menu to the sheet
function onOpen() {
  SpreadsheetApp.getUi().createMenu('Kadunde')
    .addItem('Update now', 'updateFromFPL')
    .addItem('Turn on automatic updates (every 10 minutes)', 'setupTrigger')
    .addToUi();
}

// Run this ONCE to schedule automatic updates
function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === 'updateFromFPL') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('updateFromFPL').timeBased().everyMinutes(10).create();
  updateFromFPL();
}

function getJson_(path) {
  const res = UrlFetchApp.fetch(BASE + path, { headers: HEADERS, muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) throw new Error('FPL API ' + res.getResponseCode() + ' for ' + path);
  return JSON.parse(res.getContentText());
}

function updateFromFPL() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) return;          // a previous update is still running
  try { runUpdate_(); } finally { lock.releaseLock(); }
}

function runUpdate_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const managers = ss.getSheetByName('Managers');
  const points = ss.getSheetByName('GW Points');
  const hits = ss.getSheetByName('GW Hits');
  const chips = ss.getSheetByName('Chips Log');

  // 1. League standings (all pages)
  const standings = {};
  let page = 1, hasNext = true;
  while (hasNext) {
    const st = getJson_('leagues-classic/' + LEAGUE_ID + '/standings/?page_standings=' + page).standings;
    st.results.forEach(r => standings[r.entry] = r);
    hasNext = st.has_next; page++;
  }

  // 2. Which gameweeks are finished
  const bs = getJson_('bootstrap-static/');
  const events = bs.events;
  const finished = new Array(38).fill(0);
  events.forEach(e => { if (e.finished && e.id <= 38) finished[e.id - 1] = 1; });

  // 3. Managers tab: update known managers, append new ones
  const ids = managers.getRange(2, 2, 20, 1).getValues().map(r => r[0]);
  Object.keys(standings).forEach(id => {
    if (ids.indexOf(Number(id)) === -1) {
      const empty = ids.indexOf('');
      if (empty !== -1) { ids[empty] = Number(id); managers.getRange(empty + 2, 2).setValue(Number(id)); }
    }
  });
  const mgrRows = ids.map(id => {
    const s = standings[id];
    return s ? [s.player_name, s.entry_name] : ['', ''];
  });
  managers.getRange(2, 3, 20, 2).setValues(mgrRows);
  managers.getRange(2, 6, 20, 2).setValues(ids.map(id => standings[id] ? [standings[id].rank, standings[id].total] : ['', '']));

  // 4. Each manager's history (fetched in parallel)
  const reqs = ids.map(id => ({ url: BASE + 'entry/' + id + '/history/', headers: HEADERS, muteHttpExceptions: true }));
  const resps = UrlFetchApp.fetchAll(reqs);
  const ptsGrid = [], hitGrid = [], chipRows = [];
  resps.forEach((res, i) => {
    const prow = new Array(38).fill(''), hrow = new Array(38).fill('');
    if (res.getResponseCode() === 200) {
      const h = JSON.parse(res.getContentText());
      h.current.forEach(c => { if (c.event <= 38) { prow[c.event - 1] = c.points; hrow[c.event - 1] = c.event_transfers_cost; } });
      h.chips.forEach(c => chipRows.push([ids[i], c.name, c.event]));
    } else {
      throw new Error('FPL history failed for entry ' + ids[i] + ' (HTTP ' + res.getResponseCode() + '). Try again later.');
    }
    ptsGrid.push(prow); hitGrid.push(hrow);
  });
  // 4b. LIVE gameweek: add provisional bonus + auto-subs (same method as LiveFPL)
  const liveEv = events.find(e => e.is_current && !e.finished);
  if (liveEv) {
    try {
      const lv = liveScores_(liveEv.id, bs, ids);
      const g = liveEv.id - 1;
      const liveTotals = ids.map((id, i) => {
        const s = standings[id], l = lv[id];
        if (!s) return null;
        if (!l) return s.total;
        ptsGrid[i][g] = l.live; hitGrid[i][g] = l.hits;
        return s.total - l.official + l.live;
      });
      const order = ids.map((id, i) => i).filter(i => liveTotals[i] !== null)
        .sort((a, b) => liveTotals[b] - liveTotals[a] || standings[ids[a]].rank - standings[ids[b]].rank);
      const ranks = ids.map(() => '');
      order.forEach((i, k) => ranks[i] = k + 1);
      managers.getRange(2, 6, 20, 2).setValues(ids.map((id, i) => liveTotals[i] === null ? ['', ''] : [ranks[i], liveTotals[i]]));
    } catch (err) {
      console.log('Live calculation skipped: ' + err);   // falls back to official FPL points
    }
  }

  points.getRange(2, 3, 20, 38).setValues(ptsGrid);
  hits.getRange(2, 3, 20, 38).setValues(hitGrid);
  points.getRange(23, 3, 1, 38).setValues([finished]);

  // 5. Chips log (columns A, C, D only; B and E are formulas)
  chipRows.sort((a, b) => a[2] - b[2]);
  chips.getRange(2, 1, 200, 1).clearContent();
  chips.getRange(2, 3, 200, 2).clearContent();
  if (chipRows.length) {
    chips.getRange(2, 1, chipRows.length, 1).setValues(chipRows.map(r => [r[0]]));
    chips.getRange(2, 3, chipRows.length, 2).setValues(chipRows.map(r => [r[1], r[2]]));
  }

  // 6. Gameweek currently being played (live points are already in GW Points)
  const curEv = events.find(e => e.is_current);
  managers.getRange('J4').setValue(curEv ? curEv.id : '');
  managers.getRange('J5').setValue(curEv ? (curEv.finished ? 'FINISHED' : 'LIVE') : '');

  // 7. Next gameweek deadline (for the dashboard countdown)
  const nextEv = events.find(e => e.is_next) || events.find(e => !e.finished);
  managers.getRange('J2').setValue(nextEv ? nextEv.id : '');
  managers.getRange('J3').setValue(nextEv ? new Date(nextEv.deadline_time) : '');

  managers.getRange('J1').setValue(new Date());
}

/* ===================== LIVE POINTS =====================
 * Official FPL points only add bonus points and auto-substitutions after matches are confirmed.
 * This works them out straight away from FPL's live data:
 *  - provisional bonus (3/2/1) from the live BPS table of each match
 *  - auto-subs for starters who did not play once their match is over (formation rules respected)
 *  - vice-captain takes over if the captain did not play
 */
function liveScores_(gw, bs, ids) {
  const pos = {}, team = {};
  bs.elements.forEach(p => { pos[p.id] = p.element_type; team[p.id] = p.team; });
  const live = {};
  getJson_('event/' + gw + '/live/').elements.forEach(e => live[e.id] = e.stats);
  const fx = getJson_('fixtures/?event=' + gw);
  const prov = {}, tstat = {};
  fx.forEach(f => {
    [f.team_h, f.team_a].forEach(t => {
      const s = tstat[t] || (tstat[t] = { n: 0, done: 0 });
      s.n++; if (f.finished || f.finished_provisional) s.done++;
    });
    if (!f.started) return;
    const st = {}; (f.stats || []).forEach(x => st[x.identifier] = x);
    if (st.bonus && (st.bonus.a.length || st.bonus.h.length)) return;   // official bonus already in
    if (!st.bps) return;
    const rows = st.bps.a.concat(st.bps.h).sort((a, b) => b.value - a.value);
    const vals = rows.map(r => r.value).filter((v, i, a) => a.indexOf(v) === i);
    const awards = [3, 2, 1]; let given = 0;
    for (const v of vals) {
      if (given >= 3) break;
      const tied = rows.filter(r => r.value === v);
      tied.forEach(r => prov[r.element] = (prov[r.element] || 0) + awards[given]);
      given += tied.length;
    }
  });
  const done = el => { const s = tstat[team[el]]; return !s || s.done === s.n; };
  const mins = el => (live[el] ? live[el].minutes : 0);
  const pts = el => (live[el] ? live[el].total_points : 0) + (prov[el] || 0);

  const valid = ids.filter(id => id !== '' && id !== null);
  const resps = UrlFetchApp.fetchAll(valid.map(id => ({
    url: BASE + 'entry/' + id + '/event/' + gw + '/picks/', headers: HEADERS, muteHttpExceptions: true })));
  const out = {};
  resps.forEach((res, k) => {
    if (res.getResponseCode() !== 200) return;
    const pk = JSON.parse(res.getContentText());
    const chip = pk.active_chip, picks = pk.picks;
    const xi = picks.filter(p => p.position <= 11), bench = picks.filter(p => p.position > 11);
    let side;
    if (chip === 'bboost') side = xi.concat(bench);
    else {
      const used = {};
      for (let i = 0; i < xi.length; i++) {
        const p = xi[i];
        if (mins(p.element) > 0 || !done(p.element)) continue;
        for (const b of bench) {
          if (used[b.element] || mins(b.element) === 0) continue;
          if ((pos[b.element] === 1) !== (pos[p.element] === 1)) continue;
          const trial = xi.filter(q => q !== p).concat([b]);
          const c = t => trial.filter(q => pos[q.element] === t).length;
          if (c(1) === 1 && c(2) >= 3 && c(3) >= 2 && c(4) >= 1) { used[b.element] = true; xi[i] = b; break; }
        }
      }
      side = xi;
    }
    const cap = picks.find(p => p.is_captain), vc = picks.find(p => p.is_vice_captain);
    let capEl = cap ? cap.element : null;
    if (capEl && mins(capEl) === 0 && done(capEl) && vc) capEl = vc.element;
    const capMult = chip === '3xc' ? 3 : 2;
    let total = 0;
    side.forEach(p => total += pts(p.element) * (p.element === capEl ? capMult : 1));
    out[valid[k]] = { live: total, official: pk.entry_history.points, hits: pk.entry_history.event_transfers_cost };
  });
  return out;
}

/* ===================== WEB DASHBOARD =====================
 * Serves the visual dashboard (HTML file named "Dashboard") as a web link.
 * Deploy > New deployment > Web app > Execute as: Me, Who has access: Anyone.
 * The page always shows the latest data in this spreadsheet.
 */
function doGet() {
  const t = HtmlService.createTemplateFromFile('Dashboard');
  t.dataJson = JSON.stringify(getDashboardData_()).replace(/</g, '\\u003c');
  return t.evaluate()
    .setTitle('Kadunde Super League')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, viewport-fit=cover');
}

// Called by the web page every 2 minutes to refresh itself
function getDashboardData() { return getDashboardData_(); }

function getDashboardData_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const mg = ss.getSheetByName('Managers');
  const mv = mg.getRange(2, 1, 20, 7).getValues();
  const pts = ss.getSheetByName('GW Points').getRange(2, 3, 20, 38).getValues();
  const hits = ss.getSheetByName('GW Hits').getRange(2, 3, 20, 38).getValues();
  const fin = ss.getSheetByName('GW Points').getRange(23, 3, 1, 38).getValues()[0];
  const chipVals = ss.getSheetByName('Chips Log').getRange(2, 1, 200, 4).getValues();
  const paid = ss.getSheetByName('Gameweek winners ').getRange(2, 4, 38, 1).getValues().map(r => r[0] === true || r[0] === 'TRUE');
  const cp = ss.getSheetByName('Contribution Prizes');
  const num = v => (v === '' || v === null ? null : Number(v));
  const iso = v => (v instanceof Date ? v.toISOString() : (v ? String(v) : ''));
  const managers = [];
  mv.forEach((r, i) => {
    if (r[1] === '' || r[1] === null) return;
    managers.push({
      nick: String(r[4] || r[2]), fpl: String(r[2]), team: String(r[3]).replace(/\uFFFD/g, '').trim(), entry: Number(r[1]),
      rank: num(r[5]), total: num(r[6]) || 0,
      pts: pts[i].map(num), hits: hits[i].map(v => num(v) || 0)
    });
  });
  const chips = chipVals.filter(r => r[0] !== '' && r[2] !== '').map(r => ({ entry: Number(r[0]), chip: String(r[2]), gw: Number(r[3]) }));
  return {
    league: 'Kadunde Super League', season: '2026/27',
    updated: iso(mg.getRange('J1').getValue()),
    nextGW: mg.getRange('J2').getValue(), currentGW: Number(mg.getRange('J4').getValue()) || 0, deadline: iso(mg.getRange('J3').getValue()),
    prizes: {
      gw: -Number(cp.getRange('D10').getValue()),
      classic: cp.getRange('D12:D15').getValues().map(r => -Number(r[0])),
      pot: Number(cp.getRange('E2').getValue())
    },
    managers: managers, finished: fin.map(v => Number(v) === 1), chips: chips, paid: paid
  };
}
