# Preorder Hub 3.2.1 — poprawka nawigacji PWA

Nakladka na wydanie 3.2.0 Public Launch (release 20261124-4).
Nie jest to pelne repozytorium. Rozpakuj do jego glownego katalogu, zachowujac podkatalogi i nadpisujac pliki. Nie rozpakowuj do `v3/`.

## Przyczyna techniczna

Worker 3.2.0 mogl odtwarzac odpowiedz HTML z cache po wczesniejszym podazeniu za przekierowaniem HTTP. Dla nawigacji z `redirect: manual` przegladarka moze odrzucic taka odpowiedz (ERR_FAILED). Cloudflare moze normalizowac adresy `index.html`. Nie potwierdzono rzeczywistej odpowiedzi hostingu produkcyjnego.

Worker 3.2.1 (release 20261124-5):
- dla wejsc `/v3/`, `/v3/index.html` i `/v3/index` najpierw pobiera strone z sieci; przekierowania pozostawia przegladarce;
- przy bledzie sieci/5xx korzysta z HTML z cache swojej wersji, po sprawdzeniu typu i dozwolonego adresu koncowego oraz zbudowaniu odpowiedzi bez metadanych przekierowania;
- nie maskuje 404, nie przechwytuje API, demo, recovery ani zapisow;
- jednorazowo moze automatycznie aktywowac sie po workerze z wydania -2, -3 lub -4, gdy jego cache nadal istnieje; nie wymusza przeladowania kart;
- zachowuje dotychczasowy manifest, identyfikator, adres startowy i token sesji.

## Wdrozenie

1. Zrob kopie obecnego repozytorium / upewnij sie, ze zmiany sa zapisane w Git.
2. Rozpakuj nakladke w glownym katalogu repozytorium i zaakceptuj nadpisanie.
3. Sprawdz `git diff` i `git status`, zatwierdz zmiany, wypchnij na GitHub.
4. Po publikacji zapisz rozpoczęte formularze, zamknij inne okna Preorder Hub (w tym PWA), otworz w zwyklym Chrome `https://preorderhub.pl/recover.html` i uzyj resetu pamieci PWA. To pozwala ominac stary wadliwy worker. Recovery nie usuwa localStorage ani danych Turso. Potrzebny internet.
5. Wejdz na `https://preorderhub.pl/v3/index.html`, sprawdz wersje 3.2.1 w ustawieniach, zaloguj sie w razie potrzeby, przeladuj strone i uruchom zainstalowana aplikacje. Najpierw sprawdz bez reinstalacji.

Backend (`api_v2.py`, `public_launch.py`), logowanie (`v3/app.js`), instalator (`v3/pwa.js`), manifest oraz dane i ustawienia Render/Turso pozostaja bez zmian. Nie wykonuj migracji bazy dla tej poprawki.

## Weryfikacja

- `node tests/pwa_logic.test.cjs`: 31 grup PASS, w tym prawdziwa odpowiedz HTTP 308 z lokalnego serwera Node i symulowane odtworzenie jej w service workerze.
- `node tests/redirects.test.cjs`: 45 przypadkow PASS.
- `node tests/recovery.test.cjs`: 2 przypadki PASS.
- `node --check v3/sw.js`, `node --check v3/config.js`: PASS.
- `python tests/test_pwa_navigation_browser.py`: dodatkowy test akceptacyjny z Playwright/Chromium; proba uruchomienia wariantu porownawczego zostala zablokowana na lokalnym adresie HTTP przez ERR_BLOCKED_BY_ADMINISTRATOR. Nie jest to potwierdzony test przegladarkowy.
- Nie testowano produkcji ani fizycznego Androida.

Jesli po poprawce blad wystepuje nadal, podaj dokladny adres w chwili bledu (rowniez czy ma koncowy ukosnik), komunikat Chrome oraz ewentualny wpis Console/Network. Jezeli jest to powrot do formularza zamiast ERR_FAILED, sprawdzimy odpowiedzi POST /login, GET /get_preorders i GET /get_collection (bez hasel, tokenow i prywatnych danych).
