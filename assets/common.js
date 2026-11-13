/* Shared by all three pages: navigation bar, data loading, small helpers, install button,
   service worker registration. Needs assets/calc.js loaded first. */
(function () {
  'use strict';

  const PAGES = [
    { href: 'index.html', label: 'Today', key: 'today' },
    { href: 'browse.html', label: 'Browse', key: 'browse' },
    { href: 'trends.html', label: 'Trends', key: 'trends' }
  ];

  /* el('a', {href: '...'}, 'text', childNode) builds DOM without innerHTML. */
  function el(tag, attrs) {
    const node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      const v = attrs[k];
      if (v === false || v == null) return;
      if (k === 'class') node.className = v;
      else if (k === 'text') node.textContent = v;
      else if (k.slice(0, 2) === 'on') node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? '' : v);
    });
    (function add(list) {
      for (let i = 0; i < list.length; i++) {
        const c = list[i];
        if (c == null || c === false) continue;
        if (Array.isArray(c)) add(c);   // .map() results are passed as one array
        else node.appendChild(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
      }
    })(Array.prototype.slice.call(arguments, 2));
    return node;
  }

  const fmtInt = function (n) { return Number(n).toLocaleString('en-US'); };
  const fmtShortDate = function (s) {
    const p = s.split('-');
    return new Date(Date.UTC(+p[0], +p[1] - 1, +p[2])).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
  };
  const fmtPct = function (x) { return (x * 100).toFixed(x > 0 && x < 0.1 ? 1 : 0) + '%'; };
  // numbers as written in the history file: no trailing zeros, empty when missing
  const fmtNum = function (n) { return n == null ? '' : (Math.round(n * 100) / 100).toLocaleString('en-US'); };
  const fmtSigned = function (n) { return n == null ? '' : (n > 0 ? '+' : n < 0 ? '−' : '') + fmtNum(Math.abs(n)); };

  /* A row of toggle buttons: switcher([{value, label}], current, onChange) */
  function switcher(options, current, onChange, label) {
    const box = el('div', { class: 'seg-switch', role: 'group', 'aria-label': label || 'Choose a view' });
    options.forEach(function (o) {
      const b = el('button', { type: 'button', 'aria-pressed': String(o.value === current) }, o.label);
      b.addEventListener('click', function () {
        box.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', 'false'); });
        b.setAttribute('aria-pressed', 'true');
        onChange(o.value);
      });
      box.appendChild(b);
    });
    return box;
  }

  function renderNav(active) {
    const nav = el('nav', { class: 'nav', 'aria-label': 'Main' },
      el('div', { class: 'nav-inner' },
        el('a', { class: 'brand', href: 'index.html' }, el('span', { class: 'brand-mark', 'aria-hidden': 'true' }), 'Telluride Tracker'),
        el('ul', { class: 'nav-links' }, PAGES.map(function (p) {
          return el('li', null, el('a', { href: p.href, 'aria-current': p.key === active ? 'page' : false }, p.label));
        })),
        el('button', { class: 'install', id: 'install', type: 'button', hidden: true }, 'Install app')));
    document.body.insertBefore(nav, document.body.firstChild);
  }

  function fetchText(url) {
    return fetch(url, { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error(url + ' returned ' + r.status);
      return r.text().then(function (text) {
        return { text: text, offline: r.headers.get('X-Served-From') === 'cache' };
      });
    });
  }

  /* Loads both data files. When the network is down the service worker answers from
     its cache and marks the response, so the pages can say they show older data. */
  function loadData() {
    return Promise.all([fetchText('data/history.csv'), fetchText('data/status.json')]).then(function (r) {
      return { rows: Calc.parseHistory(r[0].text), status: JSON.parse(r[1].text), offline: r[0].offline || r[1].offline };
    });
  }

  function banner(root, data) {
    if (data.offline) {
      root.prepend(el('p', { class: 'notice', role: 'status' },
        'You are offline. Showing the data from the last run that loaded (' + data.status.run_time + ').'));
    }
  }

  function fail(root, err) {
    root.replaceChildren(el('p', { class: 'notice error', role: 'alert' },
      'Could not load the data files (' + err.message + '). Check your connection and reload.'));
  }

  function boot(active, main) {
    renderNav(active);
    const root = document.getElementById('app');
    loadData().then(function (data) { root.replaceChildren(); banner(root, data); main(root, data); },
      function (err) { fail(root, err); });
  }

  // "Install app" button, shown when the browser offers installation.
  let deferred = null;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferred = e;
    const b = document.getElementById('install');
    if (b) { b.hidden = false; }
  });
  document.addEventListener('click', function (e) {
    if (e.target && e.target.id === 'install' && deferred) {
      deferred.prompt();
      deferred = null;
      e.target.hidden = true;
    }
  });

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () { navigator.serviceWorker.register('sw.js').catch(function () {}); });
  }

  window.App = { el: el, boot: boot, switcher: switcher, fmtInt: fmtInt, fmtShortDate: fmtShortDate, fmtPct: fmtPct,
    fmtNum: fmtNum, fmtSigned: fmtSigned };
})();
