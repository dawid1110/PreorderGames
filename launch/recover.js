'use strict';
(() => {
  const button = document.getElementById('recovery-run');
  const status = document.getElementById('recovery-status');
  button.addEventListener('click', async () => {
    if (button.disabled) return;
    button.disabled = true;
    status.textContent = 'Usuwanie statycznej pamięci Preorder Hub…';
    try {
      const known = new Map(['./','./v3/'].map(p => [new URL(p,location.href).href,new URL(p+'sw.js',location.href).href]));
      if ('serviceWorker' in navigator) {
        const regs = await navigator.serviceWorker.getRegistrations();
        await Promise.all(regs.filter(r => known.has(r.scope) &&
          [r.active,r.waiting,r.installing].some(w => w?.scriptURL === known.get(r.scope)))
          .map(r => r.unregister()));
      }
      if ('caches' in window) {
        const keys = await caches.keys();
        await Promise.all(keys.filter(k => k.startsWith('preorderhub-v3-shell-')).map(k => caches.delete(k)));
      }
      status.textContent = 'Pamięć statyczna została zresetowana. Otwieranie aplikacji…';
      location.replace(new URL('v3/index.html?pwa-recover=1',location.href).href);
    } catch {
      status.textContent = 'Reset nie zakończył się poprawnie. Możesz użyć drugiego przycisku lub wyrejestrować service worker w narzędziach przeglądarki.';
      button.disabled = false;
    }
  });
})();
