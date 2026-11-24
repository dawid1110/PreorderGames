# Weryfikacja paczki 3.1

- 19 testów regresji backendu z symulowanym Turso HTTP: PASS (`PYTHONPATH=. python -m pytest -q tests/test_preorder_https.py`; pytest jest zależnością testową, nie produkcyjną).
- 17 grup testów Node dotyczących instalacji PWA, Android/iPad, aktualizacji i cache: PASS (`node tests/pwa_logic.test.cjs`).
- 14 adresów starego GUI, po 3 warianty query/hash: 42 kontrole PASS (`node tests/redirects.test.cjs`).
- Składnia app.js, pwa.js i sw.js, identyfikatory HTML, zasoby, manifesty i rzeczywiste wymiary PNG: PASS.
- api_v2.py identyczny z najnowszym przekazanym repozytorium (porównanie bajtowe).

Próba otwarcia lokalnego serwera w Chromium zakończyła się blokadą środowiska ERR_BLOCKED_BY_ADMINISTRATOR. Nie wykonano zatem aktualnego testu renderowania ani rzeczywistej instalacji na urządzeniu. Nie wykonywano połączeń z produkcyjnym Turso ani publikacji na hostingu. Testy Node/Python są symulacjami, nie potwierdzeniem działania na produkcji.
