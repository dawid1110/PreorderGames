'use strict';
(async () => {
  const cfg = window.PREORDER_CONFIG;
  const control = new AbortController();
  const timer = setTimeout(() => control.abort(), 15000);
  try {
    const res = await fetch(cfg.apiBase.replace(/\/$/, '') + '/public/config', {cache:'no-store',credentials:'omit',redirect:'error',signal:control.signal});
    if (!res.ok) return;
    const data = await res.json();
    if (data.operator && data.contact_email) {
      const contact = document.getElementById('policy-contact');
      contact.textContent = 'Operator: ' + data.operator + ' · Kontakt: ' + data.contact_email;
      contact.hidden = false;
    }
    const raw = document.body.dataset.policy === 'privacy' ? data.privacy_url : data.terms_url;
    if (!raw) return;
    const url = new URL(raw);
    if (url.protocol !== 'https:' || url.username || url.password || url.href === location.href.split('#')[0]) return;
    document.getElementById('policy-final').href = url.href;
    document.getElementById('policy-link').hidden = false;
    document.getElementById('policy-status').textContent = 'Poniżej znajdziesz techniczny opis aplikacji. Obowiązujący dokument jest dostępny pod wskazanym odnośnikiem.';
  } catch { /* technical summary is still available */ }
  finally { clearTimeout(timer); }
})();
