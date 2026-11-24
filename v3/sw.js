'use strict';
// 3.2.2: online-first PWA. The browser, not the worker, handles every request.
// This emergency release retires all earlier static shell caches immediately.
// Do not intercept navigation, follow redirects, or synthesize HTML responses.
const RELEASE = '20261124-6';
const PREFIX = 'preorderhub-v3-shell-';
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil((async () => {
  try {
    const keys = await caches.keys();
    await Promise.allSettled(keys.filter(key => key.startsWith(PREFIX)).map(key => caches.delete(key)));
  } catch { /* CacheStorage may be unavailable; activation must still succeed. */ }
})()));
self.addEventListener('message', event => {
  if (event.data?.type === 'PREORDER_SKIP_WAITING') event.waitUntil(self.skipWaiting());
});
// No fetch handler: no stale HTML, no cached redirects, no API interception.
