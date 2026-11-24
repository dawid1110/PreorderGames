// Minimalny Service Worker wymagany do instalacji PWA
self.addEventListener('install', (e) => {
    console.log('[Service Worker] Zainstalowany');
});

self.addEventListener('fetch', (e) => {
    // Puste zdarzenie fetch - przeglądarka uznaje apkę za działającą offline/PWA
});