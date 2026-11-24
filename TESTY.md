# Weryfikacja 3.2.0 (20261124-4)

Wykonano w lokalnym środowisku:
- `python -m pytest tests/test_preorder_https.py -q`: 27/27. Testy adaptera HTTPS z symulowanym serwerem Turso i SQLite, również autoryzacja, izolacja kont, rejestracja z wersją regulaminu, eksport, zgłoszenia, aktywność, transakcja usuwania, nieprzydzielanie ponowne ID, rollback i brak migracji przy istniejących odczytach.
- `node tests/pwa_logic.test.cjs`: 25/25 grup. Symulowany runtime workera i przeglądarki; instalator, czekanie, jednorazowa migracja, aktywacja, odłożenie, odmowa, timeout, inne karty, cache i awaria sieci.
- `node tests/recovery.test.cjs`: 2 przypadki (selektywne usuwanie i błąd).
- `node tests/redirects.test.cjs`: 45 sprawdzeń adresów (39 starych i 6 landing page).
- `python tests/test_browser_inline.py`: rzeczywisty Chromium, HTML/CSS/JS osadzone lokalnie, symulowana pamięć i API. Testy wizualne 1440 px oraz 412 px, izolacja demo, rejestracja, login, konto, eksport, feedback, admin, usunięcie, zamknięta rejestracja. Zrzuty ekranu wygenerowane z danych demo.

Ograniczenia: środowisko blokuje top-level URL navigation (`ERR_BLOCKED_BY_ADMINISTRATOR`), więc nie było możliwe zweryfikowanie rzeczywistej rejestracji/aktywacji service workera ani end-to-end po URL. Test `tests/test_browser_launch.py` pozostawiono jako dodatkowy test odbioru na własnym komputerze (Playwright + Chromium + lokalny serwer). Zmień ścieżkę do Chromium, jeśli potrzeba. Brak połączenia z produkcyjnym Turso/Render/Cloudflare. Weryfikacja realnej aktualizacji z 3.1 i instalacji na fizycznym Androidzie jest konieczna po deployu. To nie pełny audyt bezpieczeństwa ani prawny.
