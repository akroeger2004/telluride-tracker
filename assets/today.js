/* Today page: last run, source status, the counts, the biggest moves, and the latest value of
   every item with its change since the previous run. */
App.boot('today', function (root, data) {
  const el = App.el, rows = data.rows, status = data.status;
  const day = status.run_time.slice(0, 10);
  const idx = Calc.index(rows);
  const changes = Calc.compare(rows, day, idx);
  const moveOf = {};
  changes.moves.forEach(function (m) { moveOf[m.item_id] = m; });

  const SOURCES = { telluride: 'Telluride Ski & Golf snow report (web page)', snotel: 'NRCS SNOTEL stations (JSON)',
    nws: 'National Weather Service forecast (JSON)' };
  const CATEGORIES = [
    ['mountain', 'Mountain snow report'], ['lift', 'Lifts'], ['terrain', 'Hike-to terrain'], ['trail', 'Trails'],
    ['station', 'Snow stations near Telluride (SNOTEL)'], ['forecast', 'Mountain Village forecast']];
  const VALUE_LABEL = { is_open: 'Status', snow_depth_in: 'Snow depth (in)', forecast_snow_72h_in: 'Snow forecast, 72 h (in)' };

  const when = new Date(status.run_time);
  root.append(el('header', { class: 'page-head' },
    el('h1', { text: 'Today' }),
    el('p', { class: 'muted' }, 'Last run ', el('strong', { text: when.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) }),
      ' (' + status.run_time.replace('T', ' ').replace('Z', ' UTC') + ')')));

  const tile = function (label, value) {
    return el('div', { class: 'tile' }, el('div', { class: 'label', text: label }), el('div', { class: 'value', text: App.fmtInt(value) }));
  };
  root.append(el('section', { class: 'tiles', 'aria-label': 'Counts from the latest run' },
    tile('Days with a successful run', status.days_with_success), tile('Items tracked', status.items),
    tile('New today', status.new_today), tile('Gone today', status.gone_today)));

  if (!Object.keys(changes.previous).length) {
    root.append(el('p', { class: 'notice' }, 'This is the first run, so there is nothing to compare with yet. Changes appear from the next run.'));
  }

  // ---- sources, failed ones first
  const sources = status.sources.slice().sort(function (a, b) { return (a.ok - b.ok) || (a.name < b.name ? -1 : 1); });
  const failed = sources.filter(function (s) { return !s.ok; }).length;
  root.append(el('section', { class: 'card' }, el('h2', { text: 'Sources' }),
    el('p', { class: 'muted', text: failed ? failed + ' of ' + sources.length + ' sources failed in the latest run. Their items keep their last values and show no change.' : 'All ' + sources.length + ' sources answered in the latest run.' }),
    el('div', { class: 'table-wrap' }, el('table', { class: 'data' },
      el('thead', null, el('tr', null, el('th', { scope: 'col', text: 'Source' }), el('th', { scope: 'col', text: 'Status' }), el('th', { scope: 'col', class: 'num', text: 'Items' }))),
      el('tbody', null, sources.map(function (s) {
        return el('tr', null, el('td', { class: 'name', text: SOURCES[s.name] || s.name }),
          el('td', null, el('span', { class: 'badge ' + (s.ok ? 'ok' : 'fail') }, s.ok ? '✓ Working' : '✕ Failed')),
          el('td', { class: 'num', text: s.ok ? App.fmtInt(s.count) : '-' }));
      }))))));

  // ---- biggest moves
  function describe(m) {
    if (m.field === 'is_open') return (m.old_status || 'closed') + ' → ' + (m.new_status || 'open');
    return App.fmtNum(m.old) + ' → ' + App.fmtNum(m.new) + ' in (' + App.fmtSigned(m.delta) + ')';
  }
  const top = changes.moves.slice(0, 15);
  root.append(el('section', { class: 'card' }, el('h2', { text: 'Biggest moves since the previous run (' + App.fmtInt(changes.moves.length) + ')' }),
    el('p', { class: 'muted', text: 'A move is the change in an item\'s main value (open or closed for lifts, trails and terrain; snow depth for the mountain and stations; 72-hour snow forecast for the forecast). Snow moves are scored per 6 inches so they rank with lifts opening.' }),
    top.length ? el('ul', { class: 'postings' }, top.map(function (m) {
      return el('li', null, el('strong', { text: m.item }), el('span', { class: 'role-tag', text: m.category }),
        el('span', { class: 'meta', text: describe(m) + ' · score ' + m.score.toFixed(2) }));
    })) : el('p', { class: 'muted', text: 'Nothing moved since the previous run.' }),
    changes.moves.length > top.length ? el('p', { class: 'muted', text: '…and ' + App.fmtInt(changes.moves.length - top.length) + ' smaller moves, shown in the tables below.' }) : null));

  if (changes.appeared.length || changes.gone.length) {
    const names = function (list) { return list.slice(0, 12).map(function (r) { return r.item; }).join(', ') + (list.length > 12 ? ', …' : ''); };
    root.append(el('section', { class: 'card' }, el('h2', { text: 'Appeared and gone' }),
      el('p', null, el('strong', { text: 'Appeared (' + changes.appeared.length + '): ' }), changes.appeared.length ? names(changes.appeared) : 'none'),
      el('p', null, el('strong', { text: 'Gone (' + changes.gone.length + '): ' }), changes.gone.length ? names(changes.gone) : 'none')));
  }

  // ---- latest values of every item
  const latest = Calc.latestRows(rows);
  function extra(r) {
    const n = App.fmtNum, bits = [];
    if (r.category === 'mountain') bits.push('overnight ' + n(r.snow_overnight_in) + ' in', '24 h ' + n(r.snow_24h_in) + ' in', '7 days ' + n(r.snow_7d_in) + ' in', 'season ' + n(r.season_total_in) + ' in', 'lifts open ' + n(r.lifts_open) + '/' + n(r.lifts_total), 'trails open ' + n(r.trails_open) + '/' + n(r.trails_total));
    if (r.category === 'station') bits.push('water ' + n(r.swe_in) + ' in', 'temp ' + n(r.temp_f) + '°F', n(r.elevation_ft) + ' ft', 'as of ' + r.obs_date);
    if (r.category === 'forecast') bits.push('24 h ' + n(r.forecast_snow_24h_in) + ' in', 'precip ' + n(r.forecast_precip_chance) + '%', 'high ' + n(r.temp_high_f) + '°F', 'low ' + n(r.temp_low_f) + '°F');
    if (r.category === 'lift') bits.push(r.area, r.hours_open ? n(r.hours_open) + ' h open' : '');
    if (r.category === 'trail') bits.push(r.area, r.level.replace('_', ' '), r.is_groomed ? 'groomed' : '');
    if (r.category === 'terrain') bits.push(r.area);
    return bits.filter(Boolean).join(' · ');
  }
  function valueCell(r) {
    // an item missing from the latest run keeps its last row, so say when that was
    if (r.date !== day) return el('span', { class: 'muted', text: 'last seen ' + App.fmtShortDate(r.date) });
    const f = Calc.PRIMARY[r.category], v = r[f];
    if (f === 'is_open') return el('span', { class: 'pill ' + (r.status === 'hold' ? 'hold' : r.is_open ? 'open' : 'closed'), text: r.status === 'hold' ? 'on hold' : r.is_open ? 'open' : 'closed' });
    return document.createTextNode(v === null ? '' : App.fmtNum(v));
  }
  function changeCell(r) {
    const m = moveOf[r.item_id];
    if (!m) return el('span', { class: r.date === day ? 'muted' : 'down', text: r.date === day ? '—' : 'not in this run' });
    if (m.field === 'is_open') return el('span', { class: m.delta > 0 ? 'up' : 'down', text: m.delta > 0 ? 'opened' : 'closed' });
    return el('span', { class: m.delta > 0 ? 'up' : 'down', text: App.fmtSigned(m.delta) });
  }
  root.append(el('h2', { text: 'Latest values' }));
  CATEGORIES.forEach(function (c, i) {
    const items = latest.filter(function (r) { return r.category === c[0]; });
    if (!items.length) return;
    const field = Calc.PRIMARY[c[0]];
    root.append(el('details', { class: 'card', open: c[0] !== 'trail' },
      el('summary', { text: c[1] + ' (' + items.length + ')' }),
      el('div', { class: 'table-wrap' }, el('table', { class: 'data' },
        el('thead', null, el('tr', null, el('th', { scope: 'col', text: 'Item' }), el('th', { scope: 'col', text: VALUE_LABEL[field] }),
          el('th', { scope: 'col', text: 'Change' }), el('th', { scope: 'col', text: 'Details' }))),
        el('tbody', null, items.map(function (r) {
          return el('tr', null, el('td', { class: 'name', text: r.item }), el('td', null, valueCell(r)), el('td', null, changeCell(r)),
            el('td', { class: 'muted', text: extra(r) }));
        }))))));
  });
});
