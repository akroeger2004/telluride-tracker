/* Browse page: the latest values of every item, with filters, a name search, sorting on every
   numeric column (up and down) and a starred shortlist kept in the browser (localStorage). */
App.boot('browse', function (root, data) {
  const el = App.el;
  const items = Calc.latestRows(data.rows);
  const lastDay = Calc.daysOf(data.rows).pop();

  // ---- shortlist, stored in the browser and still there after a reload
  const KEY = 'telluride.shortlist';
  let shortlist = new Set();
  try { shortlist = new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) { /* storage blocked: stars last for this visit */ }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(Array.from(shortlist))); } catch (e) { /* ignore */ } }

  // columns that have at least one value among the latest rows
  const numeric = Calc.NUMERIC.filter(function (c) { return items.some(function (r) { return r[c] !== null; }); });
  const state = { q: '', category: '', area: '', status: '', level: '', starred: false, sort: 'item', dir: 1 };
  const distinct = function (f) { return Array.from(new Set(items.map(function (r) { return r[f]; }).filter(Boolean))).sort(); };

  function visible() {
    const q = state.q.toLowerCase();
    const list = items.filter(function (r) {
      return (!q || r.item.toLowerCase().indexOf(q) >= 0) && (!state.category || r.category === state.category) &&
        (!state.area || r.area === state.area) && (!state.status || r.status === state.status) &&
        (!state.level || r.level === state.level) && (!state.starred || shortlist.has(r.item_id));
    });
    const col = state.sort, text = !Calc.NUMERIC.includes(col);
    return list.sort(function (a, b) {
      const x = a[col], y = b[col];
      if (!text) {  // empty values always go last, whichever way we sort
        if (x === null && y === null) return a.item_id < b.item_id ? -1 : 1;
        if (x === null) return 1;
        if (y === null) return -1;
        if (x !== y) return (x - y) * state.dir;
      } else if (x !== y) return (x < y ? -1 : 1) * state.dir;
      return a.item_id < b.item_id ? -1 : 1;
    });
  }

  const count = el('p', { class: 'result-count' });
  const body = el('tbody');
  const headRow = el('tr');
  const COLS = [['item', 'Item'], ['category', 'Category'], ['area', 'Area'], ['level', 'Level'], ['status', 'Status']]
    .concat(numeric.map(function (c) { return [c, Calc.LABELS[c]]; }));

  function drawHead() {
    headRow.replaceChildren(el('th', { scope: 'col', 'aria-label': 'Shortlist', text: '★' }));
    COLS.forEach(function (c) {
      const isNum = Calc.NUMERIC.includes(c[0]);
      const sorted = state.sort === c[0];
      const btn = el('button', { type: 'button', title: 'Sort by ' + c[1] }, c[1] + (sorted ? (state.dir > 0 ? ' ▲' : ' ▼') : ''));
      btn.addEventListener('click', function () {
        if (state.sort === c[0]) state.dir = -state.dir; else { state.sort = c[0]; state.dir = 1; }
        draw();
      });
      headRow.appendChild(el('th', { scope: 'col', class: isNum ? 'num' : '', 'aria-sort': sorted ? (state.dir > 0 ? 'ascending' : 'descending') : false }, btn));
    });
  }

  function cell(r, c) {
    if (c === 'item') return el('td', { class: 'name', text: r.item });
    if (c === 'status') return el('td', null, r.status ? el('span', { class: 'pill ' + (r.status === 'open' || r.status === 'hike' ? 'open' : r.status === 'hold' ? 'hold' : 'closed'), text: r.status }) : '');
    if (Calc.NUMERIC.includes(c)) return el('td', { class: 'num', text: r[c] === null ? '' : App.fmtNum(r[c]) });
    return el('td', { text: (r[c] || '').replace('_', ' ') });
  }

  function draw() {
    const list = visible();
    drawHead();
    count.textContent = App.fmtInt(list.length) + ' of ' + App.fmtInt(items.length) + ' items · latest values as of ' + lastDay;
    body.replaceChildren();
    list.forEach(function (r) {
      const star = el('button', { class: 'star', type: 'button', 'aria-pressed': String(shortlist.has(r.item_id)), 'aria-label': 'Shortlist ' + r.item, title: 'Save to shortlist' }, shortlist.has(r.item_id) ? '★' : '☆');
      star.addEventListener('click', function () {
        if (shortlist.has(r.item_id)) shortlist.delete(r.item_id); else shortlist.add(r.item_id);
        save(); starCount.textContent = shortlist.size;
        if (state.starred) draw(); else { star.setAttribute('aria-pressed', String(shortlist.has(r.item_id))); star.textContent = shortlist.has(r.item_id) ? '★' : '☆'; }
      });
      body.appendChild(el('tr', null, el('td', null, star), COLS.map(function (c) { return cell(r, c[0]); })));
    });
    if (!list.length) body.appendChild(el('tr', null, el('td', { colspan: COLS.length + 1, class: 'empty', text: state.starred ? 'Star an item to save it here.' : 'No items match these filters.' })));
  }

  // ---- controls: filters on category, area, status and level, a search box, a sort menu
  const select = function (label, field, values) {
    const s = el('select', null, el('option', { value: '', text: 'All' }), values.map(function (v) { return el('option', { value: v, text: v.replace('_', ' ') }); }));
    s.addEventListener('change', function () { state[field] = s.value; draw(); });
    return el('label', null, label, s);
  };
  const search = el('input', { type: 'search', placeholder: 'e.g. gondola, Meadows, Alta', autocomplete: 'off', 'aria-label': 'Search item names' });
  search.addEventListener('input', function () { state.q = search.value.trim(); draw(); });
  const sortSelect = el('select', { 'aria-label': 'Sort by' }, COLS.map(function (c) { return el('option', { value: c[0], text: c[1] }); }));
  sortSelect.addEventListener('change', function () { state.sort = sortSelect.value; draw(); });
  const dirSwitch = App.switcher([{ value: '1', label: 'Up ▲' }, { value: '-1', label: 'Down ▼' }], '1', function (v) { state.dir = Number(v); draw(); }, 'Sort direction');
  const starCount = el('span', { text: shortlist.size });
  const starBtn = el('button', { class: 'chip', type: 'button', 'aria-pressed': 'false' }, '★ Shortlist (', starCount, ')');
  starBtn.addEventListener('click', function () {
    state.starred = !state.starred; starBtn.setAttribute('aria-pressed', String(state.starred));
    starBtn.style.background = state.starred ? 'var(--accent)' : ''; starBtn.style.color = state.starred ? 'var(--accent-ink)' : ''; draw();
  });

  root.append(el('header', { class: 'page-head' }, el('h1', { text: 'Browse' }),
    el('p', { class: 'muted', text: 'The latest value of every item. Filter, search, and click any column heading to sort (click again to reverse).' })),
    el('section', { class: 'card' },
      el('div', { class: 'controls' },
        el('label', null, 'Search names', search),
        select('Category', 'category', distinct('category')), select('Area', 'area', distinct('area')),
        select('Status', 'status', distinct('status')), select('Level (trails)', 'level', distinct('level')),
        el('label', null, 'Sort by', sortSelect), el('div', null, dirSwitch)),
      el('div', { class: 'chips' }, starBtn)),
    count, el('div', { class: 'table-wrap' }, el('table', { class: 'data' }, el('thead', null, headRow), body)));
  draw();
});
