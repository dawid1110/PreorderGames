'use strict';
// Retire the old root-scoped Preorder Hub worker. No cache or fetch handler.
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(self.registration.unregister()));
