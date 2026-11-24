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

  // Recovery remains available without clearing localStorage or touching API data.
  const updatePanel = byId('pwa-update');
  const updateButton = byId('pwa-update-now');
  const laterButton = byId('pwa-later');
  const updateTitle = byId('pwa-update-title');
  const updateMessage = byId('pwa-update-message');
  const canReload = () => typeof window.PREORDER_CAN_RELOAD !== 'function' || window.PREORDER_CAN_RELOAD();
  const say = message => { if (updateMessage) updateMessage.textContent = message; };
  const recoveryUrl = () => new URL('/recover.html', location.href).href;
  let registration = null;
  let dismissed = null;
  let requested = false;
  let timer = null;
  let reloaded = false;
  let refreshReady = false;
  let watchedWorker = null;
  let activeAtLoad = null;
  let checking = false;

  function showUpdate(force = false) {
    if (!updatePanel) return;
    const waiting = registration?.waiting;
    if (refreshReady && !waiting) {
      updatePanel.hidden = false;
      if (updateTitle) updateTitle.textContent = 'Nowa wersja jest aktywna';
      say('Zapisz zmiany, zamknij formularze i odśwież bieżące okno.');
      if (updateButton) { updateButton.textContent = 'Odśwież aplikację'; updateButton.hidden = false; updateButton.disabled = false; }
      if (laterButton) laterButton.disabled = false;
      return;
    }
    if (waiting && (waiting !== dismissed || force)) {
      updatePanel.hidden = false;
      if (updateTitle) updateTitle.textContent = 'Dostępna aktualizacja Preorder Hub';
      if (!requested) say('Zapisz rozpoczęte zmiany w tym i innych oknach przed aktualizacją.');
      if (updateButton) { updateButton.textContent = 'Zaktualizuj teraz'; updateButton.hidden = false; updateButton.disabled = requested; }
      if (laterButton) laterButton.disabled = requested;
    } else if (!requested) updatePanel.hidden = true;
  }

  function finishUpdate() {
    if (!requested || reloaded) return;
    requested = false;
    clearTimeout(timer);
    if (!canReload()) { refreshReady = true; showUpdate(); return; }
    reloaded = true;
    if (updatePanel) updatePanel.hidden = true;
    // Only the window that requested activation reloads. No force-reload of
    // other tabs, especially ones with open forms.
    location.reload();
  }
  function updateError(message) {
    requested = false;
    clearTimeout(timer);
    if (updateButton) updateButton.disabled = false;
    if (laterButton) laterButton.disabled = false;
    say(message);
  }
  async function startUpdate() {
    if (requested) return;
    const waiting = registration?.waiting;
    if (!waiting) {
      if (refreshReady && canReload()) { refreshReady = false; location.reload(); }
      else showUpdate();
      return;
    }
    if (!canReload()) { say('Zamknij formularz lub poczekaj na zapis, a następnie spróbuj ponownie.'); return; }
    if (!window.confirm('Czy wszystkie zmiany zostały zapisane również w innych oknach Preorder Hub? Aktualizacja przeładuje bieżące okno.')) return;
    requested = true;
    if (updateButton) updateButton.disabled = true;
    if (laterButton) laterButton.disabled = true;
    say('Aktywowanie nowej wersji…');
    // Set up the activation listener before posting the message.
    waiting.addEventListener('statechange', () => {
      if (!requested) return;
      if (waiting.state === 'activated') finishUpdate();
      else if (waiting.state === 'redundant') updateError('Aktualizacja nie powiodła się. Spróbuj ponownie lub użyj resetu PWA.');
    });
    timer = setTimeout(() => updateError('Nie udało się zakończyć aktualizacji. Spróbuj ponownie lub użyj resetu PWA w ustawieniach.'), 15000);
    try { waiting.postMessage({type: 'PREORDER_SKIP_WAITING'}); }
    catch { updateError('Nie udało się uruchomić aktualizacji. Spróbuj ponownie.'); }
  }
  updateButton?.addEventListener('click', startUpdate);
  laterButton?.addEventListener('click', () => {
    if (requested) return;
    dismissed = registration?.waiting || null;
    refreshReady = false;
    if (updatePanel) updatePanel.hidden = true;
  });
  async function checkUpdate() {
    if (checking || requested) return;
    if (!registration) { window.alert('Mechanizm aktualizacji nie jest dostępny. Otwórz aplikację przez HTTPS lub użyj resetu PWA.'); return; }
    checking = true;
    try {
      await registration.update();
      if (registration.waiting) { dismissed = null; showUpdate(true); }
      else if (registration.installing) window.alert('Pobieranie aktualizacji trwa. Komunikat pojawi się po zakończeniu.');
      else if (activeAtLoad && registration.active !== activeAtLoad) {
        if (canReload() && window.confirm('Nowa wersja jest już aktywna. Odświeżyć aplikację?')) location.reload();
      } else window.alert('Nie znaleziono oczekującej aktualizacji.');
    } catch { window.alert('Nie udało się sprawdzić aktualizacji. Sprawdź połączenie.'); }
    finally { checking = false; }
  }
  window.PREORDER_PWA = Object.freeze({checkUpdate, reset() {
    if (!canReload() || requested) { window.alert('Najpierw zakończ zapis i zamknij otwarte formularze.'); return; }
    location.assign(recoveryUrl());
  }});
  if (!installOrigin || !('serviceWorker' in navigator)) return;
  const sw = navigator.serviceWorker;
  // Unregister only the known, obsolete root-scoped worker. Do not touch other
  // apps sharing this origin or the current /v3/ registration.
  async function retireRootWorker() {
    if (!sw.getRegistrations) return;
    const rootScope = new URL('/', location.href).href;
    const rootScript = new URL('/sw.js', location.href).href;
    try {
      const regs = await sw.getRegistrations();
      await Promise.allSettled(regs.filter(r => r.scope === rootScope &&
        [r.active, r.waiting, r.installing].some(w => w?.scriptURL === rootScript))
        .map(r => r.unregister()));
    } catch { /* SW startup must not depend on legacy cleanup. */ }
  }
  sw.addEventListener?.('controllerchange', () => {
    if (requested) { finishUpdate(); return; }
    // An update from another window must not interrupt this one.
    showUpdate();
  });
  (async () => {
    await retireRootWorker();
    registration = await sw.register('/v3/sw.js', {scope:'/v3/',updateViaCache:'none'});
    activeAtLoad = registration.active;
    showUpdate();
    const watchInstallingWorker = () => {
      const worker = registration.installing;
      if (!worker || worker === watchedWorker) return;
      watchedWorker = worker;
      worker.addEventListener('statechange', () => {
        if (worker.state === 'installed' || worker.state === 'activated' || worker.state === 'redundant') showUpdate();
        if (worker.state === 'redundant' && !registration.active) { registrationFailed = true; renderInstallState(); }
      });
    };
    registration.addEventListener('updatefound', watchInstallingWorker);
    watchInstallingWorker();
    // Observe a worker already waiting when the page was loaded, too.
    registration.waiting?.addEventListener('statechange', () => showUpdate());
    // Remove the one-time recovery query after the network-loaded document is ready.
    const url = new URL(location.href);
    if (url.searchParams.get('pwa-recover') === '1') {
      url.searchParams.delete('pwa-recover');
      window.history?.replaceState(null, '', url.href);
    }
  })().catch(() => { registrationFailed = true; renderInstallState(); });
})();
