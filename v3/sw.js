'use strict';
// Static application shell only. Update RELEASE and HTML asset version together.
const RELEASE = '20261124-4';
const PREFIX = 'preorderhub-v3-shell-';
const CACHE = PREFIX + RELEASE;
const INDEX_URL = new URL('./index.html', self.registration.scope).href;
const INDEX_PATH = new URL(INDEX_URL).pathname;
const ROOT_PATH = new URL(self.registration.scope).pathname;
const SCRIPTS = ['style.css', 'config.js', 'pwa.js', 'app.js'];
const SHELL = ['index.html', 'manifest.json', ...SCRIPTS.map(p => `${p}?v=${RELEASE}`),
  'assets/icon-192.png', 'assets/icon-512.png', 'assets/crimson-hero.webp',
  'assets/crimson.webp', 'assets/orion.webp', 'assets/northern.webp'];
const SHELL_URLS = new Set(SHELL.map(path => new URL(path, self.registration.scope).href));
// Only the pre-button releases need a one-time automatic activation. No reload
// is sent to their tabs. Later versions wait for explicit user confirmation.
const LEGACY = new Set(['20261124-2', '20261124-3'].map(v => PREFIX + v));
self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const previous = await caches.keys();
    const cache = await caches.open(CACHE);
    await cache.addAll([...SHELL_URLS].map(url => new Request(url, {cache:'reload'})));
    if (previous.some(key => LEGACY.has(key))) await self.skipWaiting();
  })());
});
self.addEventListener('message', event => {
  if (event.data?.type === 'PREORDER_SKIP_WAITING') event.waitUntil(self.skipWaiting());
});
self.addEventListener('activate', event => {
  // Do not claim unrelated or uncontrolled tabs. Keep the immediate predecessor
  // only until activation; old documents already hold their JS and CSS.
  event.waitUntil((async () => {
    try {
      const keys = await caches.keys();
      await Promise.allSettled(keys.filter(key => key.startsWith(PREFIX) && key !== CACHE).map(key => caches.delete(key)));
    } catch { /* Broken CacheStorage must not prevent activation. */ }
  })());
});
function offlinePage() {
  return new Response('<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Preorder Hub — brak połączenia</title><style>body{font:16px system-ui;background:#0c0e17;color:#eee;max-width:540px;margin:12vh auto;padding:24px}a{color:#bba5ff}</style><h1>Nie udało się wczytać aplikacji.</h1><p>Sprawdź połączenie z internetem i spróbuj ponownie. Dane gier pozostają na serwerze.</p><p><a href="./index.html?pwa-recover=1">Spróbuj ponownie z sieci</a></p><p><a href="../recover.html">Napraw pamięć aplikacji</a></p></html>', {status:503,headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}});
}
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || request.headers.has('Authorization') ||
      url.origin !== self.location.origin || !url.href.startsWith(self.registration.scope) ||
      url.searchParams.get('demo') === '1' || url.searchParams.get('pwa-recover') === '1') return;
  const navigation = request.mode === 'navigate';
  if (navigation ? url.pathname !== INDEX_PATH && url.pathname !== ROOT_PATH : !SHELL_URLS.has(url.href)) return;
  const cacheKey = navigation ? INDEX_URL : url.href;
  event.respondWith((async () => {
    try {
      // A versioned shell prevents old JavaScript being served to new HTML.
      const cache = await caches.open(CACHE);
      const cached = await cache.match(cacheKey);
      if (cached) return cached;
    } catch { /* CacheStorage errors fall through to the network. */ }
    try {
      const result = await fetch(request);
      if (navigation && !result.ok && result.status >= 500) return offlinePage();
      return result;
    } catch {
      if (navigation) return offlinePage();
      return new Response('', {status:503, statusText:'Static asset unavailable'});
    }
  })());
});
