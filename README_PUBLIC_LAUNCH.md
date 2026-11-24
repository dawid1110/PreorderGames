# Preorder Hub 3.2 — dokumentacja zmian

Instrukcja wdrożenia: [START_TUTAJ.md](START_TUTAJ.md). Opis funkcji 3.2.0; aktualny frontend 3.2.2, wydanie 20261124-6.

## Architektura

Publiczna strona `/` → demo (`/v3/index.html?demo=1`) lub konto (`/v3/index.html`). PWA pozostaje pod `/v3/`. Frontend wywołuje API na Render, backend komunikuje się z Turso przez HTTPS i opcjonalnie z IGDB/Twitch oraz Telegramem. Dane demo są wyłącznie w pamięci i nie trafiają do API. Nowe funkcje nie zmieniają dotychczasowego kontraktu list gier, budżetu i kolekcji. Rejestracja jest zamknięta do czasu świadomego włączenia.

| Plik | Odpowiedzialność |
| --- | --- |
| `index.html`, `launch/style.css`, `launch/landing.js` | Publiczna strona, responsywność, linki do demo i rejestracji, przekazywanie starych hashy i parametrów do SPA |
| `launch/dashboard.webp`, `mobile.webp`, `share.webp` | Renderowane podglądy danych demo, grafika udostępniania |
| `privacy.html`, `terms.html`, `launch/policy.js` | Techniczne informacje i linki do właściwych dokumentów operatora z publicznej konfiguracji |
| `recover.html`, `launch/recover.js` | Ręczna naprawa cache tylko Preorder Hub |
| `v3/index.html`, `style.css`, `app.js` | Dotychczasowa SPA, formularze, dashboard, kolekcja, budżet, konto, narzędzia publiczne |
| `v3/config.js` | Adres API, numer wersji, release i ustawienia regionalne |
| `v3/pwa.js`, `v3/sw.js`, `v3/manifest.json` | Instalacja Android/iOS, aktualizacja bez cache stron i zachowana tożsamość PWA |
| `sw.js` w korzeniu | Worker migracyjny wyrejestrowujący poprzedni root-scoped worker |
| `_headers` | Sugestia nagłówków Cloudflare dla HTML/SW/recovery; skuteczność zależy od sposobu hostingu |
| `api_v2.py` | Dotychczasowy backend HTTPS, integracja modułu publicznego, ochrona logowania, rejestracja z kontrolą regulaminu |
| `public_launch.py` | Flagi, limity, rejestracja, dzienna aktywność, zgłoszenia, eksport, usuwanie konta i statystyki |
| `migrations/0032_public_launch.sql` | Dodatkowe tabele, niepełny schemat, nie kopia bazy |
| `.env.example` | Przykładowe nazwy zmiennych bez sekretów; ustaw na Render, nie publikuj realnego `.env` |
| `api.py` i `update-covers.py` | Historyczny backend i narzędzie, nie używać jako bieżącej aplikacji |

## Endpointy 3.2

Dotychczasowe `/login`, `/register`, `/get_preorders`, `/add`, `/edit`, `/delete`, `/update_budget`, `/get_collection`, `/move_to_collection`, `/delete_from_collection`, `/cron/weekly_summary` i `/ping` pozostają pod tymi samymi adresami. Nowe `/register` sprawdza flagi oraz pola `accept_terms` i `policy_version`. Zmiana jest świadoma, stary klient rejestracji nie jest kompatybilny z otwartą rejestracją 3.2. JWT istniejących kont zachowują dotychczasowy format.

| Metoda i ścieżka | Uprawnienia / działanie |
| --- | --- |
| GET `/public/config` | Publiczny status flag oraz dane operatora i finalnych dokumentów, bez sekretów |
| GET `/account/capabilities` | JWT; dostępność narzędzi, administrator, możliwość usunięcia |
| POST `/feedback` | JWT; `category` idea/bug/other, `message` 10–2000 znaków; limit zgłoszeń |
| GET `/account/export` | JWT; JSON wyłącznie własnych danych, bez hasha i tokenów; `no-store` |
| POST `/account/delete` | JWT, hasło i `confirmation: "USUN"`; transakcyjne usunięcie własnych danych z bieżącej bazy, nie z logów/kopii; admin i Telegram chronieni |
| GET `/admin/overview` | JWT oraz ID wskazane w `PUBLIC_ADMIN_USER_ID`; liczby kont, aktywnych, gier, zgłoszeń, ostatnie 50 zgłoszeń |

## Tabele

`public_activity` — ID i dzień ostatniej aktywności (login albo GET preorderów; od uruchomienia funkcji, nie wszystkie akcje). `public_feedback` — ID, właściciel, kategoria, treść, czas. `public_terms_acceptance` — ID konta, zaakceptowana wersja, czas. `public_retired_users` — identyfikatory usuniętych kont, nie używane ponownie do rejestracji. Ostatnia tabela chroni przed ponownym przypisaniem starego JWT do nowego użytkownika. Nie usuwać jej ręcznie. Migracja jest addytywna, wykonuje ją operator po kopii bazy.

## Flagi i wdrożenie

`PUBLIC_LAUNCH_ENABLED=false`, `PUBLIC_SIGNUP_ENABLED=false` domyślnie. Pierwsza włącza narzędzia, druga rejestrację wyłącznie z pierwszą i prawidłowym formatem dokumentów. `PUBLIC_ADMIN_USER_ID` to ID konta w Turso; nie pochodzi z frontendu. Pozostałe `PUBLIC_*` opisują operatora oraz dokumenty. Włączenie wymaga ukończenia checklisty z START_TUTAJ. Rate limiting ogranicza częstotliwość logowań, rejestracji, usuwania i wybranych operacji; dotyczy jednego procesu, nie zastępuje limitów hostingu. Nie wprowadzono mechanizmu odzyskiwania hasła, adresu e-mail konta, systemu płatności, monitorowania sklepów, reklam ani push.

## Następne wydania

Pracuj na osobnym branchu, zachowaj kopię i testuj przed deployem. Zmieniając statyczny shell, uaktualnij jednocześnie `RELEASE` w `v3/sw.js`, `release` i `version` w `v3/config.js` oraz `?v=` przy skryptach/stylu w `v3/index.html`. Opublikuj wszystkie pliki naraz. Po jednorazowym przejściu z 3.1/roboczej 3.2 worker czeka na zgodę użytkownika. Zachowaj id/start_url/scope manifestu. Jeśli zmieniasz API, utrzymaj kontrakt starszych otwartych kart lub wymagaj kontrolowanej aktualizacji.
