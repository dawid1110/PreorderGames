# Weryfikacja 3.2.2 (20261124-6)

Punkt wyjścia: aktualny przesłany ZIP `PreorderGames-main(1).zip`. W nim trzy pliki główne z poprzedniej poprawki zostały nadpisane/dodane do korzenia (`index.html`, `sw.js`, `config.js`), a `v3/` pozostało w wersji 3.2.0. Przywrócono główny landing i worker wygaszający starą rejestrację, zastosowano bezwzględne ścieżki v3 i usunięto przechwytywanie żądań przez worker. `api_v2.py` i `public_launch.py` pozostawiono identyczne z wejściem.

Wykonane testy:
- `python -m pytest tests/test_preorder_https.py -q` — 27/27, symulowane Turso / SQLite, bez produkcyjnych danych.
- `node tests/pwa_logic.test.cjs` — 24 grupy testów, w tym brak przechwytywania nawigacji i rejestracja workera przy adresie bez ukośnika.
- `node tests/redirects.test.cjs` — 45 przypadków.
- `node tests/recovery.test.cjs` — 2 przypadki.
- `python tests/test_deployment_paths.py` — ścieżki wszystkich zasobów dla pięciu wariantów adresu v3, strona reklamowa i brak przechwytywania przez oba workery.
- `python tests/test_browser_inline.py` — rzeczywisty Chromium, osadzone lokalne zasoby, symulowane API; demo, telefon/desktop, strona reklamowa, rejestracja, logowanie, konto, eksport, usuwanie konta i widoczny ekran awaryjny przy braku skryptów.
- `node --check` — składnia zmienionych JS.

Ograniczenia: nawigacja Chromium do lokalnego serwera zablokowana `ERR_BLOCKED_BY_ADMINISTRATOR`; test `tests/test_browser_launch.py` pozostawiono do wykonania na własnym komputerze. Nie sprawdzano aktualnego hostingu Cloudflare, faktycznego cyklu rejestracji workera na telefonie ani instalacji PWA na fizycznym Androidzie. PWA wymaga internetu; brak cache offline jest świadomą decyzją stabilizacyjną, a dostępność systemowego okna instalacji zależy od Chrome. Nie wykonano zmian zdalnych.
