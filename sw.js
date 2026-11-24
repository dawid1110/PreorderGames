'use strict';

// /v3/ static shell only. No API responses, tokens or personal data are cached.
// Bump RELEASE whenever a shell file changes, then deploy all files together.
const RELEASE = '20261124-2';
const PREFIX = 'preorderhub-v3-shell-';
const CACHE = PREFIX + RELEASE;
const SHELL = [
  './index.html', './style.css', './config.js', './app.js', './pwa.js', './manifest.json',
  './assets/icon-192.png', './assets/icon-512.png', './assets/crimson-hero.webp',
  './assets/crimson.webp', './assets/orion.webp', './assets/northern.webp'
];
const SHELL_URLS = new Set(SHELL.map(path => new URL(path, self.registration.scope).href));
const INDEX_URL = new URL('./index.html', self.registration.scope).href;
const INDEX_PATH = new URL(INDEX_URL).pathname;
const ROOT_PATH = new URL(self.registration.scope).pathname;

self.addEventListener('install', event => {
  // HTTP cache must not fill a new release with an older copy of app.js or CSS.
  const requests = [...SHELL_URLS].map(url => new Request(url, {cache: 'reload'}));
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(requests)));
  // Updates wait until every window using the previous version has been closed.
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith(PREFIX) && key !== CACHE).map(key => caches.delete(key))
  )));
  // Do not take over an already open editor with clients.claim().
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || request.headers.has('Authorization') ||
      url.origin !== self.location.origin || !url.href.startsWith(self.registration.scope) ||
      url.searchParams.get('demo') === '1') return;

  let cacheKey;
  if (request.mode === 'navigate') {
    // Only the SPA entry is an app shell; do not intercept arbitrary URLs.
    if (url.pathname !== INDEX_PATH && url.pathname !== ROOT_PATH) return;
    cacheKey = INDEX_URL;
  } else {
    if (!SHELL_URLS.has(url.href)) return;
    cacheKey = url.href;
  }

  // Serve the installed, consistent release. A missing shell file may use the
  // network but its response is not added dynamically to the static cache.
  event.respondWith(caches.open(CACHE).then(async cache =>
    await cache.match(cacheKey) || fetch(request)
  ));
});
