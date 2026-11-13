/* Trends page: a report on the history file. Every number is computed here, in the browser,
   from data/history.csv, so the page changes as the history grows. */
App.boot('trends', function (root, data) {
  const el = App.el, fmt = App.fmtNum, fmtInt = App.fmtInt, short = App.fmtShortDate;
  const rows = data.rows;
  const days = Calc.daysOf(rows);
  const calendar = Calc.calendar(rows);
  const clean = function (name) { return name.replace(' (SNOTEL)', ''); };
  const plural = function (n, w) { return fmtInt(n) + ' ' + w + (n === 1 ? '' : 's'); };
  if (!rows.length) { root.append(el('p', { class: 'notice', text: 'The history file is empty. Come back after the first run.' })); return; }

  // every item keeps one color slot for the whole page ("color follows the entity")
  const slots = new Map();
  const slotOf = function (id) { if (!slots.has(id)) slots.set(id, (slots.size % 8) + 1); return slots.get(id); };

  root.append(el('header', { class: 'page-head' }, el('h1', { text: 'Trends' }),
    el('p', { class: 'muted', text: 'Built from ' + fmtInt(rows.length) + ' rows covering ' + plural(days.length, 'day') + ' of history (' + days[0] + ' to ' + days[days.length - 1] + '). Every number on this page is computed in your browser from data/history.csv.' })));

  function section(heading, paragraph, content) {
    root.append(el('section', { class: 'market-section' }, el('h2', { text: heading }), el('p', { text: paragraph }), content));
  }

  // 1. snow depth ---------------------------------------------------------------
  (function () {
    const dt = Calc.depthTrend(rows);
    const last = function (id) { const a = dt.series[id]; for (let i = a.length - 1; i >= 0; i--) if (a[i] !== null) return a[i]; return -1; };
    const stationIds = dt.ids.filter(function (id) { return id.indexOf('station:') === 0; })
      .sort(function (a, b) { return last(b) - last(a) || (a < b ? -1 : 1); }).slice(0, 5);
    const shown = dt.series['mountain:telluride'] ? ['mountain:telluride'].concat(stationIds) : stationIds;
    const change = dt.mountainLast === null ? null : dt.mountainLast - dt.mountainFirst;
    const heading = dt.mountainLast === null ? 'Snow depth has not been reported yet'
      : 'The mountain has ' + fmt(dt.mountainLast) + ' inches of snow on the ground' +
        (change === 0 ? ', unchanged since the first run' : ', ' + (change > 0 ? 'up ' : 'down ') + fmt(Math.abs(change)) + ' inches since the first run');
    section(heading,
      'Telluride Ski & Golf reports the depth at the mountain on its snow report; the NRCS SNOTEL stations around Telluride measure it with sensors. ' +
      (dt.mountainLast === null ? '' : 'The mountain went from ' + fmt(dt.mountainFirst) + ' in on the first run to ' + fmt(dt.mountainLast) + ' in on the last. ') +
      (dt.deepest ? 'On the last run the deepest station was ' + clean(dt.deepest.item) + ' at ' + fmt(dt.deepest.value) + ' in. ' : '') +
      'Each line is one item\'s snow depth on every day of history (a gap is a day the source gave no value); the mountain and the five deepest stations are shown.',
      Charts.lines({ title: 'Snow depth', subtitle: 'Inches, mountain and the deepest SNOTEL stations', days: dt.days, unit: ' in',
        series: shown.map(function (id) { return { name: clean(dt.names[id]), slot: slotOf(id), values: dt.series[id] }; }) }));
  })();

  // 2. lifts and trails open -----------------------------------------------------
  (function () {
    const t = Calc.terrainOpen(rows);
    let heading = 'No lift or trail data yet', text = 'The lift and trail lists come from the Telluride snow report.';
    if (t.last) {
      const lifts = t.last.lo, trails = t.last.to;
      heading = fmtInt(lifts) + ' of ' + fmtInt(t.last.lt) + ' lifts and ' + fmtInt(trails) + ' of ' + fmtInt(t.last.tt) + ' trails are open';
      if (t.firstDay !== t.lastDay) heading += ' (first run: ' + fmtInt(t.first.lo) + ' lifts, ' + fmtInt(t.first.to) + ' trails)';
      text = 'Counted from the item rows: on each day, the lifts and the trails whose is_open value is 1 (a lift on hold counts as not open). ' +
        (lifts === 0 && trails === 0 ? 'Nothing is open yet, so the lines sit at zero until the season starts. ' : '') +
        'The two counts are shown on separate charts because there are about nine times as many trails as lifts.';
    }
    section(heading, text, el('div', { class: 'charts-2' },
      Charts.lines({ title: 'Lifts open', subtitle: 'Number of lifts', days: t.days, unit: '', series: [{ name: 'Lifts open', slot: 1, values: t.liftsOpen }] }),
      Charts.lines({ title: 'Trails open', subtitle: 'Number of trails', days: t.days, unit: '', series: [{ name: 'Trails open', slot: 2, values: t.trailsOpen }] })));
  })();

  // 3. the biggest day -------------------------------------------------------------
  (function () {
    const a = Calc.activity(rows);
    const total = a.perDay.reduce(function (s, p) { return s + p.moved; }, 0);
    const heading = a.best ? 'The biggest day was ' + short(a.best.day) + ': ' + plural(a.best.moved, 'item') + ' moved'
      : 'Nothing has moved yet';
    section(heading,
      'A move is the change in an item\'s main value since the previous run: open or closed for lifts, trails and hike-to terrain, snow depth for the mountain and the stations, and the 72-hour snow forecast for Mountain Village. ' +
      (a.best ? 'On ' + short(a.best.day) + ' ' + plural(a.best.moved, 'item') + ' moved, ' + plural(a.best.appeared, 'item') + ' appeared and ' + plural(a.best.gone, 'item') + ' disappeared. ' : '') +
      'Across all days ' + plural(total, 'move') + ' were recorded. The first day of each source has no previous run, so it shows zero.',
      Charts.columns({ title: 'Items that moved', subtitle: 'Count per day', days: a.perDay.map(function (p) { return p.day; }),
        counts: a.perDay.map(function (p) { return p.moved; }), color: 'all', unit: 'items' }));
  })();

  // 4. how far apart the stations are -----------------------------------------------
  (function () {
    const sp = Calc.stationSpread(rows);
    const have = sp.perDay.filter(function (p) { return p.spread !== null; });
    const last = have[have.length - 1];
    let widest = null;
    have.forEach(function (p) { if (widest === null || p.spread > widest.spread) widest = p; });
    const heading = last ? 'The snow stations are ' + fmt(last.spread) + ' inches apart: ' + clean(last.maxItem) + ' ' + fmt(last.max) + ' in, ' + clean(last.minItem) + ' ' + fmt(last.min) + ' in'
      : 'Not enough stations to compare yet';
    section(heading,
      'Spread is the deepest station\'s snow depth minus the shallowest station\'s on the same day, across the SNOTEL stations that reported that day. ' +
      (last ? 'On ' + short(last.day) + ' it was ' + fmt(last.spread) + ' in. ' : '') +
      (widest ? 'The widest it has been was ' + fmt(widest.spread) + ' in on ' + short(widest.day) + '. ' : '') +
      'A large spread means conditions differ a lot with elevation and aspect around Telluride.',
      Charts.lines({ title: 'Spread between stations', subtitle: 'Deepest minus shallowest depth, inches', days: sp.days, unit: ' in',
        series: [{ name: 'Spread', slot: 3, values: sp.perDay.map(function (p) { return p.spread; }) }] }));
  })();

  // 5. change since the first run -----------------------------------------------------
  (function () {
    const sf = Calc.sinceFirstRun(rows);
    const top = sf[0];
    const moved = sf.length && sf[0].firstDay !== sf[0].lastDay;
    const heading = !sf.length ? 'No station data yet'
      : !moved ? 'The stations start between ' + fmt(Math.min.apply(null, sf.map(function (s) { return s.last; }))) + ' and ' + fmt(Math.max.apply(null, sf.map(function (s) { return s.last; }))) + ' inches'
      : top.change > 0 ? clean(top.item) + ' has gained the most snow depth: ' + App.fmtSigned(top.change) + ' inches since ' + short(top.firstDay)
      : 'No station has gained snow depth since the first run';
    section(heading,
      'For each SNOTEL station this is its latest snow depth minus its depth on the first run that includes it, in inches. ' +
      (sf.length ? 'The first run is ' + short(sf[0].firstDay) + '. ' : '') +
      (moved ? 'Of ' + plural(sf.length, 'station') + ', ' + sf.filter(function (s) { return s.change > 0; }).length + ' gained snow, ' + sf.filter(function (s) { return s.change < 0; }).length + ' lost some and ' + sf.filter(function (s) { return s.change === 0; }).length + ' are unchanged.' : 'Changes appear after the second run.'),
      Charts.bars({ title: 'Change since the first run', subtitle: 'Inches of snow depth (bar length is the size of the change)',
        items: sf.map(function (s) { return { name: clean(s.item), count: Math.abs(s.change), label: App.fmtSigned(s.change) + ' in' }; }),
        color: 'all', valueHeader: 'Change (in)', emptyText: 'No station data yet.' }));
  })();

  // 6. how often each lift has been open ---------------------------------------------------
  (function () {
    const ld = Calc.liftDays(rows);
    const opened = ld.filter(function (l) { return l.open > 0; });
    const heading = !ld.length ? 'No lift data yet'
      : !opened.length ? 'No lift has opened yet: all ' + plural(ld.length, 'lift') + ' were closed on every day so far'
      : fmtInt(opened.length) + ' of ' + fmtInt(ld.length) + ' lifts have opened, ' + ld[0].item + ' most often (' + ld[0].open + ' of ' + ld[0].listed + ' days)';
    section(heading,
      'For each lift, the number of days in the history on which it was open (is_open = 1), out of the days it was listed on the snow report. ' +
      (opened.length ? 'The share of listed days open ranges from ' + App.fmtPct(Math.min.apply(null, ld.map(function (l) { return l.share; }))) + ' to ' + App.fmtPct(Math.max.apply(null, ld.map(function (l) { return l.share; }))) + '. ' : 'Lifts normally start opening in late November.'),
      Charts.bars({ title: 'Days each lift has been open', subtitle: 'Days open out of days listed',
        items: ld.map(function (l) { return { name: l.item, count: l.open, label: l.open + ' of ' + l.listed + ' days' }; }),
        color: 'all', valueHeader: 'Days open', emptyText: 'No lift data yet.' }));
  })();

  // Explorer: a chart of every numeric value, with a control that picks the items ---------------
  (function () {
    const ORDER = ['mountain', 'lift', 'terrain', 'trail', 'station', 'forecast'];
    const TITLES = { mountain: 'Mountain', lift: 'Lifts', terrain: 'Hike-to terrain', trail: 'Trails', station: 'Snow stations', forecast: 'Forecast' };
    const meta = new Map();
    rows.forEach(function (r) { if (!meta.has(r.item_id)) meta.set(r.item_id, { id: r.item_id, name: clean(r.item), category: r.category }); });
    const all = Array.from(meta.values()).sort(function (a, b) {
      return ORDER.indexOf(a.category) - ORDER.indexOf(b.category) || (a.name < b.name ? -1 : 1);
    });
    const DEFAULTS = ['mountain:telluride', 'station:1344', 'station:713', 'station:538', 'forecast:mountain-village', 'lift:free-gondola-town-to-mv'];
    let chosen = DEFAULTS.filter(function (id) { return meta.has(id); });
    const MAX = 6;

    const charts = el('div', { class: 'charts-2' });
    const chips = el('div', { class: 'chosen' });
    const list = el('div', { class: 'picker-list' });
    const search = el('input', { type: 'search', placeholder: 'Search items…', autocomplete: 'off', 'aria-label': 'Search items to chart' });
    const note = el('p', { class: 'muted', style: 'margin:4px 0 0;font-size:.875rem' });

    function drawCharts() {
      charts.replaceChildren();
      let any = false;
      Calc.NUMERIC.forEach(function (col) {
        const series = Calc.valueSeries(rows, chosen, col, calendar);
        const shown = chosen.filter(function (id) { return series[id].some(function (v) { return v !== null; }); });
        if (!shown.length) return;
        any = true;
        charts.appendChild(Charts.lines({ title: Calc.LABELS[col], days: calendar,
          series: shown.map(function (id) { return { name: meta.get(id).name, slot: slotOf(id), values: series[id] }; }) }));
      });
      if (!any) charts.appendChild(el('p', { class: 'empty', text: 'Pick at least one item to see its values.' }));
    }
    function drawPicker() {
      note.textContent = chosen.length + ' of ' + MAX + ' items chosen';
      chips.replaceChildren.apply(chips, chosen.map(function (id) {  // replaceChildren takes nodes, not an array
        const b = el('button', { class: 'chip', type: 'button', title: 'Remove ' + meta.get(id).name },
          el('i', { class: 'swatch l' + slotOf(id), 'aria-hidden': 'true' }), meta.get(id).name + ' ✕');
        b.addEventListener('click', function () { chosen = chosen.filter(function (x) { return x !== id; }); drawPicker(); drawCharts(); });
        return b;
      }));
      const q = search.value.trim().toLowerCase();
      list.replaceChildren();
      let group = '';
      all.filter(function (m) { return !q || m.name.toLowerCase().indexOf(q) >= 0; }).forEach(function (m) {
        if (m.category !== group) { group = m.category; list.appendChild(el('div', { class: 'group', text: TITLES[group] })); }
        const on = chosen.indexOf(m.id) >= 0;
        const box = el('input', { type: 'checkbox', checked: on, disabled: !on && chosen.length >= MAX });
        box.addEventListener('change', function () {
          chosen = box.checked ? chosen.concat([m.id]) : chosen.filter(function (x) { return x !== m.id; });
          drawPicker(); drawCharts();
        });
        list.appendChild(el('label', null, box, m.name));
      });
    }
    search.addEventListener('input', drawPicker);

    root.append(el('section', { class: 'market-section' },
      el('h2', { text: 'Explore any value' }),
      el('p', { text: 'One chart for every numeric value in the history file. Choose up to six items; each chart shows the chosen items that have that value, one line per item, with a gap on days with no data.' }),
      el('details', { class: 'picker', open: true }, el('summary', { text: 'Choose items' }), chips, note, el('label', null, search), list),
      charts));
    drawPicker(); drawCharts();
  })();
});
