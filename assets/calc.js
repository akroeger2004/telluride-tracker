/* Calculations on data/history.csv. No DOM access, so the same code runs in the browser and
   under Node (tests/test_site_calc.py checks every number against an independent Python
   implementation). Dates are UTC 'YYYY-MM-DD' strings. */
(function (root) {
  'use strict';

  // the numeric columns of the history file, in order (tests check this matches the Python side)
  const NUMERIC = ['is_open', 'on_hold', 'is_groomed', 'hours_open', 'snow_depth_in', 'snow_overnight_in',
    'snow_24h_in', 'snow_48h_in', 'snow_7d_in', 'season_total_in', 'lifts_open', 'lifts_total', 'trails_open',
    'trails_total', 'swe_in', 'precip_in', 'elevation_ft', 'temp_f', 'temp_high_f', 'temp_low_f',
    'forecast_snow_24h_in', 'forecast_snow_72h_in', 'forecast_precip_chance'];

  const LABELS = {
    is_open: 'Open (1 = open)', on_hold: 'On hold (1 = yes)', is_groomed: 'Groomed (1 = yes)', hours_open: 'Hours open (h)',
    snow_depth_in: 'Snow depth (in)', snow_overnight_in: 'Overnight snow (in)', snow_24h_in: 'Snow, last 24 h (in)',
    snow_48h_in: 'Snow, last 48 h (in)', snow_7d_in: 'Snow, last 7 days (in)', season_total_in: 'Season snow total (in)',
    lifts_open: 'Lifts open', lifts_total: 'Lifts listed', trails_open: 'Trails open', trails_total: 'Trails listed',
    swe_in: 'Snow water equivalent (in)', precip_in: 'Precipitation since Oct 1 (in)', elevation_ft: 'Elevation (ft)',
    temp_f: 'Temperature (°F)', temp_high_f: 'High (°F)', temp_low_f: 'Low (°F)',
    forecast_snow_24h_in: 'Forecast snow, next 24 h (in)', forecast_snow_72h_in: 'Forecast snow, next 72 h (in)',
    forecast_precip_chance: 'Chance of precipitation (%)'
  };

  // the move rule (see telltracker/moves.py)
  const PRIMARY = { lift: 'is_open', trail: 'is_open', terrain: 'is_open', mountain: 'snow_depth_in',
    station: 'snow_depth_in', forecast: 'forecast_snow_72h_in' };
  const SCALE = { is_open: 1, snow_depth_in: 6, forecast_snow_72h_in: 6 };

  // ------------------------------------------------------------------ parsing
  function parseCSV(text) {
    const rows = [];
    let row = [], field = '', quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; } else { quoted = false; }
        } else { field += c; }
      } else if (c === '"') { quoted = true; }
      else if (c === ',') { row.push(field); field = ''; }
      else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
      else if (c !== '\r') { field += c; }
    }
    if (field !== '' || row.length) { row.push(field); rows.push(row); }
    return rows;
  }

  /* Rows as objects; numeric columns become numbers, an empty cell becomes null. */
  function parseHistory(text) {
    const table = parseCSV(text);
    if (!table.length) return [];
    const head = table[0];
    return table.slice(1).filter(function (r) { return r.length === head.length; }).map(function (r) {
      const o = {};
      head.forEach(function (h, i) { o[h] = r[i]; });
      NUMERIC.forEach(function (n) { o[n] = o[n] === '' || o[n] === undefined ? null : Number(o[n]); });
      return o;
    });
  }

  // -------------------------------------------------------------------- dates
  function dayNum(s) { const p = s.split('-'); return Date.UTC(+p[0], +p[1] - 1, +p[2]) / 864e5; }
  function addDays(s, n) { return new Date((dayNum(s) + n) * 864e5).toISOString().slice(0, 10); }
  function eachDay(a, b) { const out = []; for (let d = a; d <= b; d = addDays(d, 1)) out.push(d); return out; }

  function daysOf(rows) {
    return Array.from(new Set(rows.map(function (r) { return r.date; }))).sort();
  }

  /* index(rows) -> Map 'source|date' -> Map item_id -> row */
  function index(rows) {
    const m = new Map();
    rows.forEach(function (r) {
      const k = r.source + '|' + r.date;
      if (!m.has(k)) m.set(k, new Map());
      m.get(k).set(r.item_id, r);
    });
    return m;
  }

  // -------------------------------------------------------------- the move rule
  /* Compare the items of `day` with the previous run of each source. Same rule as moves.compare(). */
  function compare(rows, day, idx) {
    idx = idx || index(rows);
    const daysOfSource = new Map();
    idx.forEach(function (_, k) {
      const p = k.split('|');
      if (!daysOfSource.has(p[0])) daysOfSource.set(p[0], []);
      daysOfSource.get(p[0]).push(p[1]);
    });
    const previous = {}, moves = [], appeared = [], gone = [];
    Array.from(daysOfSource.keys()).sort().forEach(function (source) {
      const current = idx.get(source + '|' + day);
      const earlier = daysOfSource.get(source).filter(function (d) { return d < day; });
      if (!current || !earlier.length) return;
      const prevDay = earlier.sort().pop();
      previous[source] = prevDay;
      const before = idx.get(source + '|' + prevDay);
      current.forEach(function (row, id) {
        if (!before.has(id)) { appeared.push(row); return; }
        const field = PRIMARY[row.category];
        const old = field ? before.get(id)[field] : null, now = field ? row[field] : null;
        if (field && old !== null && now !== null && now !== old) {
          moves.push({ item_id: id, item: row.item, category: row.category, source: source, field: field,
            old: old, new: now, delta: now - old, score: Math.abs(now - old) / SCALE[field],
            old_status: before.get(id).status, new_status: row.status });
        }
      });
      before.forEach(function (row, id) { if (!current.has(id)) gone.push(row); });
    });
    const byId = function (a, b) { return a.item_id < b.item_id ? -1 : a.item_id > b.item_id ? 1 : 0; };
    moves.sort(function (a, b) { return b.score - a.score || byId(a, b); });
    appeared.sort(byId); gone.sort(byId);
    return { day: day, previous: previous, moves: moves, appeared: appeared, gone: gone };
  }

  /* The newest row of every item (an item missing from the latest run keeps its last known row). */
  function latestRows(rows) {
    const m = new Map();
    rows.forEach(function (r) { const o = m.get(r.item_id); if (!o || r.date > o.date) m.set(r.item_id, r); });
    return Array.from(m.values()).sort(function (a, b) { return a.item_id < b.item_id ? -1 : 1; });
  }

  // ------------------------------------------------------------ trends numbers
  /* A value per calendar day from first to last run, for the given items (null where missing). */
  function valueSeries(rows, itemIds, field, days) {
    const want = new Set(itemIds), out = {};
    itemIds.forEach(function (id) { out[id] = days.map(function () { return null; }); });
    const pos = new Map(days.map(function (d, i) { return [d, i]; }));
    rows.forEach(function (r) {
      if (want.has(r.item_id) && r[field] !== null && pos.has(r.date)) out[r.item_id][pos.get(r.date)] = r[field];
    });
    return out;
  }

  function calendar(rows) {
    const d = daysOf(rows);
    return d.length ? eachDay(d[0], d[d.length - 1]) : [];
  }

  /* 1. Snow depth over the days: the mountain and the SNOTEL stations. */
  function depthTrend(rows) {
    const days = calendar(rows);
    const ids = Array.from(new Set(rows.filter(function (r) { return r.category === 'station' || r.category === 'mountain'; })
      .map(function (r) { return r.item_id; }))).sort();
    const series = valueSeries(rows, ids, 'snow_depth_in', days);
    const names = {};
    rows.forEach(function (r) { names[r.item_id] = r.item; });
    const first = function (a) { for (let i = 0; i < a.length; i++) if (a[i] !== null) return a[i]; return null; };
    const last = function (a) { for (let i = a.length - 1; i >= 0; i--) if (a[i] !== null) return a[i]; return null; };
    const mountain = series['mountain:telluride'] || [];
    const stations = ids.filter(function (id) { return id.indexOf('station:') === 0; });
    let deepest = null;
    stations.forEach(function (id) {
      const v = last(series[id]);
      if (v !== null && (deepest === null || v > deepest.value || (v === deepest.value && id < deepest.id))) deepest = { id: id, item: names[id], value: v };
    });
    return { days: days, ids: ids, names: names, series: series, mountainFirst: first(mountain), mountainLast: last(mountain),
      deepest: deepest };
  }

  /* 2. Lifts and trails open on each day, counted from the item rows. */
  function terrainOpen(rows) {
    const days = calendar(rows);
    const t = days.map(function () { return { lo: 0, lt: 0, to: 0, tt: 0, seen: false }; });
    const pos = new Map(days.map(function (d, i) { return [d, i]; }));
    rows.forEach(function (r) {
      if (r.category !== 'lift' && r.category !== 'trail') return;
      const x = t[pos.get(r.date)]; x.seen = true;
      if (r.category === 'lift') { x.lt++; x.lo += r.is_open || 0; } else { x.tt++; x.to += r.is_open || 0; }
    });
    const ran = days.filter(function (d, i) { return t[i].seen; });
    const at = function (d) { return t[days.indexOf(d)]; };
    return { days: days, liftsOpen: t.map(function (x) { return x.seen ? x.lo : null; }),
      liftsTotal: t.map(function (x) { return x.seen ? x.lt : null; }),
      trailsOpen: t.map(function (x) { return x.seen ? x.to : null; }),
      trailsTotal: t.map(function (x) { return x.seen ? x.tt : null; }),
      firstDay: ran[0] || null, lastDay: ran[ran.length - 1] || null,
      first: ran.length ? at(ran[0]) : null, last: ran.length ? at(ran[ran.length - 1]) : null };
  }

  /* 3. How many items moved on each day, and the day with the most moves. */
  function activity(rows) {
    const idx = index(rows), days = daysOf(rows);
    const perDay = days.map(function (d) {
      const c = compare(rows, d, idx);
      return { day: d, moved: c.moves.length, appeared: c.appeared.length, gone: c.gone.length,
        score: c.moves.reduce(function (s, m) { return s + m.score; }, 0), compared: Object.keys(c.previous).length > 0 };
    });
    let best = null;
    perDay.forEach(function (p) { if (p.compared && (best === null || p.moved > best.moved)) best = p; });
    return { days: days, perDay: perDay, best: best && best.moved > 0 ? best : null };
  }

  /* 4. How far apart the stations are: the deepest minus the shallowest snow depth, per day. */
  function stationSpread(rows) {
    const days = calendar(rows);
    const out = days.map(function (d) { return { day: d, spread: null, min: null, max: null, minItem: '', maxItem: '' }; });
    const pos = new Map(days.map(function (d, i) { return [d, i]; }));
    const byDay = days.map(function () { return []; });
    rows.forEach(function (r) { if (r.category === 'station' && r.snow_depth_in !== null) byDay[pos.get(r.date)].push(r); });
    byDay.forEach(function (list, i) {
      if (list.length < 2) return;
      let lo = list[0], hi = list[0];
      list.forEach(function (r) {
        if (r.snow_depth_in < lo.snow_depth_in || (r.snow_depth_in === lo.snow_depth_in && r.item_id < lo.item_id)) lo = r;
        if (r.snow_depth_in > hi.snow_depth_in || (r.snow_depth_in === hi.snow_depth_in && r.item_id < hi.item_id)) hi = r;
      });
      out[i] = { day: days[i], spread: hi.snow_depth_in - lo.snow_depth_in, min: lo.snow_depth_in, max: hi.snow_depth_in,
        minItem: lo.item, maxItem: hi.item };
    });
    return { days: days, perDay: out };
  }

  /* 5. Each station's snow depth now minus its depth on the first run it appears in. */
  function sinceFirstRun(rows) {
    const by = new Map();
    rows.filter(function (r) { return r.category === 'station' && r.snow_depth_in !== null; }).forEach(function (r) {
      const o = by.get(r.item_id) || { item_id: r.item_id, item: r.item, firstDay: r.date, first: r.snow_depth_in, lastDay: r.date, last: r.snow_depth_in };
      if (r.date < o.firstDay) { o.firstDay = r.date; o.first = r.snow_depth_in; }
      if (r.date > o.lastDay) { o.lastDay = r.date; o.last = r.snow_depth_in; }
      by.set(r.item_id, o);
    });
    return Array.from(by.values()).map(function (o) { o.change = o.last - o.first; return o; })
      .sort(function (a, b) { return b.change - a.change || (a.item_id < b.item_id ? -1 : 1); });
  }

  /* 6. For each lift, on how many of the days it was listed was it open? */
  function liftDays(rows) {
    const by = new Map();
    rows.filter(function (r) { return r.category === 'lift'; }).forEach(function (r) {
      const o = by.get(r.item_id) || { item_id: r.item_id, item: r.item, listed: 0, open: 0 };
      o.listed++; o.open += r.is_open || 0; by.set(r.item_id, o);
    });
    return Array.from(by.values()).map(function (o) { o.share = o.listed ? o.open / o.listed : 0; return o; })
      .sort(function (a, b) { return b.open - a.open || b.share - a.share || (a.item_id < b.item_id ? -1 : 1); });
  }

  const api = { NUMERIC: NUMERIC, LABELS: LABELS, PRIMARY: PRIMARY, SCALE: SCALE, parseCSV: parseCSV,
    parseHistory: parseHistory, dayNum: dayNum, addDays: addDays, eachDay: eachDay, daysOf: daysOf, index: index,
    compare: compare, latestRows: latestRows, valueSeries: valueSeries, calendar: calendar, depthTrend: depthTrend,
    terrainOpen: terrainOpen, activity: activity, stationSpread: stationSpread, sinceFirstRun: sinceFirstRun,
    liftDays: liftDays };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Calc = api;
})(typeof self !== 'undefined' ? self : this);
