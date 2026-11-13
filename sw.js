/* Service worker: makes the site installable and usable offline.
   Online, every request goes to the network first so the pages always load the newest
   data files. Offline, the last copy that loaded is served from the cache; data files
   answered that way carry an X-Served-From: cache header so the pages can say so. */
const CACHE = 'telluride-v1';
const SHELL = [
  './', 'index.html', 'browse.html', 'trends.html',
  'assets/style.css', 'assets/calc.js', 'assets/common.js', 'assets/charts.js',
  'assets/today.js', 'assets/browse.js', 'assets/trends.js',
  'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png',
  'data/history.csv', 'data/status.json'
];

self.addEventListener('install', function (event) {
  event.waitUntil(caches.open(CACHE).then(function (cache) {
    // one missing file must not break installation
    return Promise.all(SHELL.map(function (url) { return cache.add(url).catch(function () {}); }));
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function markCached(response) {
  const headers = new Headers(response.headers);
  headers.set('X-Served-From', 'cache');
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers: headers });
}

self.addEventListener('fetch', function (event) {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;

  event.respondWith(
    fetch(req, { cache: 'no-cache' }).then(function (response) {
      if (response.ok) {
        const copy = response.clone();
        caches.open(CACHE).then(function (cache) { cache.put(req, copy); });
      }
      return response;
    }).catch(function () {
      return caches.match(req, { ignoreSearch: true }).then(function (hit) {
        if (hit) return url.pathname.indexOf('/data/') >= 0 ? markCached(hit) : hit;
        if (req.mode === 'navigate') return caches.match('index.html');
        return new Response('Offline and not cached', { status: 503, statusText: 'Offline' });
      });
    })
  );
});
