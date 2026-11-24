# Preorder Hub 3.2.2 — GUI i PWA

Wydanie `20261124-6`. Najważniejsza zmiana: przywrócono właściwy `index.html` strony reklamowej oraz `sw.js` w korzeniu, a ścieżki zasobów w aplikacji są bezwzględne (`/v3/...`).

- `v3/index.html`, `app.js`, `style.css`, `config.js`, `pwa.js`, `manifest.json`, `sw.js` oraz `assets/` muszą pozostawać w katalogu `v3/`.
- Worker v3 nie przechwytuje żadnych żądań i nie zapisuje shell w CacheStorage. Chrome sam pobiera pliki i obsługuje przekierowania. Aplikacja wymaga internetu także do uruchomienia.
- Worker w korzeniu służy wyłącznie do wyrejestrowania starej rejestracji. Worker v3 w tym wydaniu awaryjnym aktywuje się automatycznie, ale nie przeładowuje sam okien. Usuwa wyłącznie cache z prefiksem `preorderhub-v3-shell-`.
- Manifest v3 pozostaje identyczny z 3.2.0; start URL `/v3/index.html`, zakres `/v3/`, zachowana tożsamość. Instalacja przez menu Chrome nadal dostępna, gdy przeglądarka spełnia swoje warunki. Okno `beforeinstallprompt` zależy od przeglądarki; instrukcja w aplikacji jest dostępna także bez tego zdarzenia. Na Androidzie instaluj z `/v3/index.html`, nie ze strony reklamowej.
- Po publikacji użyj `/recover.html` w Chrome. Zamknij pozostałe okna i zapisz zmiany; reset nie usuwa tokena ani danych w Turso. W razie konieczności wyrejestruj stary worker ręcznie.
- Zmienione CSS/JS wersjonuj spójnym sufiksem w HTML i konfiguracji. Aktualizuj numer wydania. Nie włączaj cache HTML w Cloudflare. Plik `_headers` wymaga wsparcia ze strony hostingu; sprawdź rzeczywiste nagłówki.
- `api_v2.py`, `public_launch.py`, migracje i konfiguracja Render pozostają bez zmian.

Zobacz `START_TUTAJ.md` oraz `TESTY.md`. Pełna dokumentacja PDF/MD i opis Public Launch są historycznym opisem 3.1/3.2.0; dla działania PWA pierwszeństwo ma ten plik.
