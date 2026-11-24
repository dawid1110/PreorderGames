// Scoped to /v3/. No authenticated API responses, tokens or personal data cached.
const CACHE = 'preorderhub-v3-shell-20261124-1';
const SHELL = ['./index.html','./style.css','./config.js','./app.js','./manifest.json','./assets/icon-192.png','./assets/icon-512.png','./assets/crimson-hero.webp','./assets/crimson.webp','./assets/orion.webp','./assets/northern.webp'];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL))));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('preorderhub-v3-shell-') && key !== CACHE).map(key => caches.delete(key))))));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || !url.href.startsWith(self.registration.scope)) return;
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.match(new URL('./index.html', self.registration.scope).href)));
    return;
  }
  if (!SHELL.some(path => new URL(path, self.registration.scope).href === url.href)) return;
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
