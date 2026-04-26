const CACHE = 'fmx-v1';
const STATIC = [
  '/static/css/style.css',
  '/static/css/navbar.css',
  '/static/css/cards.css',
  '/static/css/report.css',
  '/static/css/news.css',
  '/static/css/loading.css',
  '/static/css/responsive.css',
  '/static/js/navbar.js',
  '/static/js/app.js',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  // Never intercept SSE, API calls or admin routes
  const url = e.request.url;
  if (
    e.request.method !== 'GET' ||
    url.includes('/gerar') ||
    url.includes('/impacto') ||
    url.includes('/retrospecto') ||
    url.includes('/admin') ||
    url.includes('/sw.js')
  ) return;

  // Static assets: cache-first
  if (url.includes('/static/')) {
    e.respondWith(
      caches.match(e.request).then(cached => cached || fetch(e.request))
    );
    return;
  }

  // Pages: network-first, cache fallback
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
