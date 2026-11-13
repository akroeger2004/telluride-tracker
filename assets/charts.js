/* Small chart components in plain HTML/CSS (no library, so they work offline).
   columns(), bars() and segmented() each return a <figure> with a title, the chart,
   a hover/focus tooltip on every mark, and a "View as table" switch. */
(function () {
  'use strict';
  const el = App.el;

  // one tooltip shared by every chart
  let tip;
  function tooltip() {
    if (!tip) { tip = el('div', { class: 'tip', role: 'tooltip', hidden: true }); document.body.appendChild(tip); }
    return tip;
  }
  function attachTip(node, text) {
    node.setAttribute('aria-label', text);
    const show = function () {
      const t = tooltip();
      t.textContent = text;
      t.hidden = false;
      const r = node.getBoundingClientRect();
      const w = t.offsetWidth;
      t.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left + r.width / 2 - w / 2)) + 'px';
      t.style.top = Math.max(8, r.top - t.offsetHeight - 8) + 'px';
    };
    const hide = function () { tooltip().hidden = true; };
    node.addEventListener('pointerenter', show);
    node.addEventListener('pointerleave', hide);
    node.addEventListener('focus', show);
    node.addEventListener('blur', hide);
  }

  function niceMax(v) {
    if (v <= 4) return Math.max(v, 1);
    const pow = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 2, 2.5, 5, 10]) if (v <= m * pow) return m * pow;
    return 10 * pow;
  }

  function figure(title, subtitle, body, tableRows, headers) {
    const table = el('table', { class: 'chart-table', hidden: true },
      el('thead', null, el('tr', null, headers.map(function (h) { return el('th', { scope: 'col', text: h }); }))),
      el('tbody', null, tableRows.map(function (r) {
        return el('tr', null, r.map(function (c) { return el('td', { text: String(c) }); }));
      })));
    const btn = el('button', { class: 'link-btn', type: 'button', 'aria-pressed': 'false' }, 'View as table');
    btn.addEventListener('click', function () {
      const on = table.hidden;
      table.hidden = !on;
      body.hidden = on;
      btn.setAttribute('aria-pressed', String(on));
      btn.textContent = on ? 'View as chart' : 'View as table';
    });
    return el('figure', { class: 'chart' },
      el('div', { class: 'chart-head' }, el('figcaption', null, el('strong', { text: title }), subtitle ? el('span', { class: 'sub', text: subtitle }) : null), btn),
      body, table);
  }

  function empty(message) { return el('p', { class: 'empty', text: message }); }

  /* columns({title, subtitle, days:[YYYY-MM-DD], counts:[n], color:'all'|'role', unit:'postings'}) */
  function columns(o) {
    const n = o.days.length;
    const max = niceMax(Math.max.apply(null, o.counts.concat([0])));
    const ticks = [0, max / 2, max].filter(function (t, i, a) { return a.indexOf(t) === i; });
    const rows = o.days.map(function (d, i) { return [d, o.counts[i]]; });
    if (!n) return figure(o.title, o.subtitle, empty('No data yet.'), rows, ['Day', o.unit || 'Count']);

    const plot = el('div', { class: 'plot' });
    plot.appendChild(el('div', { class: 'y-axis' }, ticks.map(function (t) {
      return el('span', { style: 'bottom:' + (t / max * 100) + '%', text: App.fmtInt(t) });
    })));
    const grid = el('div', { class: 'grid' }, ticks.map(function (t) { return el('i', { style: 'bottom:' + (t / max * 100) + '%' }); }));
    const cols = el('div', { class: 'cols' });
    o.counts.forEach(function (v, i) {
      const bar = el('span', { class: 'bar ' + (o.color || 'all'), style: 'height:' + (v ? Math.max(v / max * 100, 1.5) : 0) + '%' });
      const col = el('span', { class: 'col', tabindex: '0', role: 'img' }, bar);
      attachTip(col, App.fmtShortDate(o.days[i]) + ': ' + App.fmtInt(v) + ' ' + (o.unit || 'postings'));
      cols.appendChild(col);
    });
    const step = Math.max(1, Math.ceil(n / 6));
    const xs = el('div', { class: 'x-axis' });
    o.days.forEach(function (d, i) {
      if (i % step === 0 || i === n - 1 && (n - 1) % step > step / 2) {
        xs.appendChild(el('span', { style: 'left:' + ((i + 0.5) / n * 100) + '%', text: App.fmtShortDate(d) }));
      }
    });
    plot.appendChild(grid);
    plot.appendChild(cols);
    const body = el('div', { class: 'chart-body' }, plot, xs);
    return figure(o.title, o.subtitle, body, rows, ['Day', o.unit || 'Count']);
  }

  /* bars({title, items:[{name, count}], color, format(count) -> text, tipText(item)}) */
  function bars(o) {
    const items = o.items;
    const fmt = o.format || App.fmtInt;
    const rows = items.map(function (it) { return [it.name, it.label || fmt(it.count)]; });
    if (!items.length) return figure(o.title, o.subtitle, empty(o.emptyText || 'Nothing to show.'), rows, ['Name', o.valueHeader || 'Value']);
    const max = Math.max.apply(null, items.map(function (i) { return i.count; })) || 1;
    const list = el('div', { class: 'hbars' });
    items.forEach(function (it) {
      const bar = el('span', { class: 'hbar ' + (o.color || 'all'), style: 'width:' + Math.max(it.count / max * 100, it.count ? 1 : 0) + '%' });
      const row = el('div', { class: 'hrow', tabindex: '0', role: 'img' },
        el('span', { class: 'hlabel', title: it.name, text: it.name }),
        el('span', { class: 'htrack' }, bar, el('span', { class: 'hvalue', text: it.label || fmt(it.count) })));
      attachTip(row, o.tipText ? o.tipText(it) : it.name + ': ' + (it.label || fmt(it.count)));
      list.appendChild(row);
    });
    return figure(o.title, o.subtitle, list, rows, ['Name', o.valueHeader || 'Value']);
  }

  /* segmented({title, parts:[{name, value, cls}]}) - one whole split into parts */
  function segmented(o) {
    const total = o.parts.reduce(function (s, p) { return s + p.value; }, 0);
    const rows = o.parts.map(function (p) { return [p.name, p.value, total ? App.fmtPct(p.value / total) : '']; });
    if (!total) return figure(o.title, o.subtitle, empty(o.emptyText || 'Nothing to show.'), rows, ['Part', 'Postings', 'Share']);
    const bar = el('div', { class: 'seg-bar' });
    o.parts.forEach(function (p) {
      if (!p.value) return;
      const share = p.value / total;
      const part = el('span', { class: 'seg ' + p.cls, tabindex: '0', role: 'img', style: 'flex:' + p.value + ' 1 0' },
        share >= 0.12 ? App.fmtPct(share) : null);
      attachTip(part, p.name + ': ' + App.fmtInt(p.value) + ' (' + App.fmtPct(share) + ')');
      bar.appendChild(part);
    });
    const legend = el('ul', { class: 'legend' }, o.parts.map(function (p) {
      return el('li', null, el('i', { class: 'swatch ' + p.cls, 'aria-hidden': 'true' }), p.name);
    }));
    return figure(o.title, o.subtitle, el('div', null, bar, legend), rows, ['Part', 'Postings', 'Share']);
  }

  /* lines({title, subtitle, days:[YYYY-MM-DD], series:[{name, slot, values:[number|null]}], unit}) */
  const NS = 'http://www.w3.org/2000/svg';
  function svgEl(tag, attrs) {
    const n = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    return n;
  }
  function lines(o) {
    const days = o.days, series = o.series, n = days.length, unit = o.unit || '';
    const all = [];
    series.forEach(function (s) { s.values.forEach(function (v) { if (v !== null) all.push(v); }); });
    const rows = days.map(function (d, i) {
      return [d].concat(series.map(function (s) { return s.values[i] === null ? '' : App.fmtNum(s.values[i]); }));
    });
    const headers = ['Day'].concat(series.map(function (s) { return s.name; }));
    if (!n || !all.length) return figure(o.title, o.subtitle, empty('No values yet for these items.'), rows, headers);

    const svg = svgEl('svg', { role: 'img', 'aria-label': o.title + ': ' + series.map(function (s) { return s.name; }).join(', ') });
    const body = el('div', { class: 'chart-body line-chart' }, svg);
    if (series.length >= 2) {
      body.appendChild(el('ul', { class: 'legend' }, series.map(function (s) {
        return el('li', null, el('i', { class: 'swatch l' + s.slot, 'aria-hidden': 'true' }), s.name);
      })));
    }

    function draw() {
      const W = Math.max(280, body.clientWidth || 640), H = 230, ml = 46, mr = 14, mt = 10, mb = 26;
      svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
      svg.setAttribute('width', W); svg.setAttribute('height', H);
      svg.replaceChildren();
      const lo = Math.min(0, Math.min.apply(null, all));
      const hi = Math.max(all.length ? Math.max.apply(null, all) : 1, 1);
      const top = niceMax(hi), bottom = lo < 0 ? -niceMax(-lo) : 0;
      const x = function (i) { return n === 1 ? (ml + (W - mr)) / 2 : ml + (W - ml - mr) * i / (n - 1); };
      const y = function (v) { return mt + (H - mt - mb) * (1 - (v - bottom) / (top - bottom)); };
      [bottom, (bottom + top) / 2, top].forEach(function (t, k) {
        svg.appendChild(svgEl('line', { x1: ml, x2: W - mr, y1: y(t), y2: y(t), class: k === 0 ? 'ax-base' : 'ax-grid' }));
        const lab = svgEl('text', { x: ml - 8, y: y(t) + 4, class: 'ax-text', 'text-anchor': 'end' });
        lab.textContent = App.fmtNum(t);
        svg.appendChild(lab);
      });
      const step = Math.max(1, Math.ceil(n / 6));
      days.forEach(function (d, i) {
        if (i % step !== 0 && i !== n - 1) return;
        if (i !== n - 1 && n - 1 - i < step / 2) return;
        const lab = svgEl('text', { x: x(i), y: H - 8, class: 'ax-text', 'text-anchor': i === 0 && n > 1 ? 'start' : i === n - 1 && n > 1 ? 'end' : 'middle' });
        lab.textContent = App.fmtShortDate(d);
        svg.appendChild(lab);
      });
      const cross = svgEl('line', { y1: mt, y2: H - mb, class: 'ax-cross', visibility: 'hidden' });
      svg.appendChild(cross);
      series.forEach(function (s) {
        let path = '', pen = false, lastI = -1;
        s.values.forEach(function (v, i) {
          if (v === null) { pen = false; return; }
          path += (pen ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1);
          pen = true; lastI = i;
        });
        svg.appendChild(svgEl('path', { d: path, class: 'line l' + s.slot, fill: 'none' }));
        if (lastI >= 0) svg.appendChild(svgEl('circle', { cx: x(lastI), cy: y(s.values[lastI]), r: 4, class: 'dot l' + s.slot }));
      });
      // one hover/focus target per day, wider than any mark
      const slot = n === 1 ? W - ml - mr : (W - ml - mr) / (n - 1);
      days.forEach(function (d, i) {
        const hit = svgEl('rect', { x: x(i) - slot / 2, y: mt, width: slot, height: H - mt - mb, class: 'hit', tabindex: '0' });
        const text = App.fmtShortDate(d) + ': ' + series.map(function (s) {
          return s.name + ' ' + (s.values[i] === null ? 'no data' : App.fmtNum(s.values[i]) + unit);
        }).join(', ');
        attachTip(hit, text);
        const show = function () { cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('visibility', 'visible'); };
        const hide = function () { cross.setAttribute('visibility', 'hidden'); };
        hit.addEventListener('pointerenter', show); hit.addEventListener('pointerleave', hide);
        hit.addEventListener('focus', show); hit.addEventListener('blur', hide);
        svg.appendChild(hit);
      });
    }
    draw();
    if (window.ResizeObserver) {
      let width = 0;
      new ResizeObserver(function () { if (body.clientWidth && body.clientWidth !== width) { width = body.clientWidth; draw(); } }).observe(body);
    }
    return figure(o.title, o.subtitle, body, rows, headers);
  }

  window.Charts = { columns: columns, bars: bars, segmented: segmented, lines: lines };
})();
