'use strict';

// Installation and service-worker lifecycle are independent of API/login state.
(() => {
  const byId = id => document.getElementById(id);
  const demo = new URLSearchParams(location.search).get('demo') === '1' ||
    document.documentElement.dataset.demo === 'true' || window.PREORDER_DEMO === true;
  const localHost = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
  const installOrigin = window.isSecureContext &&
    (location.protocol === 'https:' || (location.protocol === 'http:' && localHost));
  const displayMode = window.matchMedia('(display-mode: standalone)');
  const fullscreenMode = window.matchMedia('(display-mode: fullscreen)');
  let installedHere = false;
  let deferredPrompt = null;
  let prompting = false;
  let registrationFailed = false;
  let installMessage = '';
  let lastTrigger = null;

  const standalone = () => installedHere || displayMode.matches || fullscreenMode.matches || navigator.standalone === true;

  // Demo has no install invitation, deferred prompt, or SW registration.
  // A browser can still offer its own generic shortcut for any website.
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    if (demo || !installOrigin || standalone()) return;
    deferredPrompt = event;
    installMessage = '';
    renderInstallState();
  });

  if (demo) {
    byId('pwa-manifest')?.remove();
    document.querySelectorAll('meta[name="mobile-web-app-capable"],meta[name="apple-mobile-web-app-capable"]').forEach(meta => meta.remove());
    return;
  }

  function renderInstallState() {
    const installed = standalone();
    document.querySelectorAll('[data-pwa-install]').forEach(node => { node.hidden = installed; });
    const nativeButton = byId('pwa-native-install');
    if (nativeButton) {
      nativeButton.hidden = !deferredPrompt || installed || !installOrigin;
      nativeButton.disabled = prompting;
    }
    const message = byId('pwa-message');
    if (!message) return;
    let value = installMessage;
    if (installed) value = 'Preorder Hub jest już uruchomiony jako aplikacja lub instalacja została zakończona w tej przeglądarce.';
    else if (!installOrigin) value = 'Aby zainstalować aplikację, otwórz jej adres HTTPS w zwykłej przeglądarce. Plik HTML na urządzeniu ani adres HTTP w sieci lokalnej nie służą do instalacji.';
    else if (registrationFailed && !value) value = 'Nie udało się przygotować plików aplikacji na urządzeniu. Sprawdź połączenie i odśwież stronę. Instalacja z menu przeglądarki może nadal być dostępna.';
    message.textContent = value;
    message.hidden = !value;
  }

  function openInstructions(event) {
    lastTrigger = event.currentTarget;
    renderInstallState();
    const dialog = byId('pwa-dialog');
    if (dialog && !dialog.open) dialog.showModal();
  }

  async function requestInstall() {
    if (prompting || !deferredPrompt || standalone() || !installOrigin) return;
    // An event is single-use. Consume it before the first await and never retry it.
    const prompt = deferredPrompt;
    deferredPrompt = null;
    prompting = true;
    renderInstallState();
    try {
      // Keep prompt() within the user's click handler to preserve activation.
      const result = await prompt.prompt();
      const choice = result || await prompt.userChoice;
      installMessage = choice?.outcome === 'accepted'
        ? 'Zgoda na instalację została przyjęta. Dokończ kroki pokazane przez przeglądarkę.'
        : 'Instalacja została odłożona. Nadal możesz korzystać ze strony lub użyć menu przeglądarki.';
    } catch {
      installMessage = 'Przeglądarka nie otworzyła instalatora. Skorzystaj z instrukcji poniżej lub odśwież stronę i spróbuj ponownie.';
    } finally {
      prompting = false;
      renderInstallState();
    }
  }

  window.addEventListener('appinstalled', () => {
    installedHere = true;
    deferredPrompt = null;
    renderInstallState();
  });
  for (const query of [displayMode, fullscreenMode]) {
    if (query.addEventListener) query.addEventListener('change', renderInstallState);
    else if (query.addListener) query.addListener(renderInstallState);
  }

  document.querySelectorAll('[data-pwa-open]').forEach(button => button.addEventListener('click', openInstructions));
  byId('pwa-native-install')?.addEventListener('click', requestInstall);
  for (const id of ['pwa-close', 'pwa-done']) byId(id)?.addEventListener('click', () => byId('pwa-dialog').close());
  byId('pwa-dialog')?.addEventListener('close', () => {
    if (lastTrigger?.isConnected && !lastTrigger.closest('[hidden]')) lastTrigger.focus();
  });

  // iPadOS may identify itself as macOS when desktop browsing is enabled.
  const appleMobile = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (/Mac/.test(navigator.platform || '') && navigator.maxTouchPoints > 1);
  const platform = appleMobile ? 'ios' : /Android/.test(navigator.userAgent) ? 'android' : 'desktop';
  document.querySelectorAll('[data-pwa-guide]').forEach(guide => { guide.open = guide.dataset.pwaGuide === platform; });
  renderInstallState();

  if (!installOrigin || !('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('./sw.js', {scope: './', updateViaCache: 'none'}).then(registration => {
    const showUpdate = () => {
      // No skipWaiting, clients.claim, or forced reload while a form may be open.
      if (registration.waiting && byId('pwa-update')) byId('pwa-update').hidden = false;
    };
    showUpdate();
    let watchedWorker = null;
    const watchInstallingWorker = () => {
      const worker = registration.installing;
      if (!worker || worker === watchedWorker) return;
      watchedWorker = worker;
      worker?.addEventListener('statechange', () => {
        if (worker.state === 'installed') showUpdate();
        if (worker.state === 'redundant' && !registration.active) {
          registrationFailed = true;
          renderInstallState();
        }
      });
    };
    registration.addEventListener('updatefound', watchInstallingWorker);
    // updatefound may have happened before register() resolved.
    watchInstallingWorker();
  }).catch(() => {
    registrationFailed = true;
    renderInstallState();
  });
})();
