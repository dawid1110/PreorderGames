'use strict';
// Legacy root PWA compatibility. No caching, no interception of requests.
// The new application registers /v3/sw.js with scope /v3/.
self.addEventListener('install', () => { self.skipWaiting(); });
