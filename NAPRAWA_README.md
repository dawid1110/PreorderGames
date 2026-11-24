# Naprawa GUI / PWA – Preorder Hub

## Zawartość
- `v3/`: kompletny, niezmieniony pakiet frontendu 3.1 z poprawką PWA.
- `index.html`: przekierowanie z głównej strony do v3.
- `pwa-list.html`: przekierowanie ze starego adresu startowego PWA do v3.
- `README_GUI_V3.md`: instrukcja dołączona do wydania v3.1.

## Wdrożenie
1. Zachowaj bieżące repozytorium i zrób commit przed zmianami.
2. Rozpakuj ZIP do katalogu głównego repozytorium (obok api_v2.py).
   Zachowaj strukturę `v3/assets/`. NIE kopiuj plików z v3 pojedynczo do korzenia.
3. Nadpisz tylko dwa wskazane pliki HTML z korzenia oraz cały katalog v3.
   Pozostałe stare pliki mogą tymczasowo zostać, w tym główny style.css,
   manifest.json i sw.js. Nie przenoś starego manifestu/SW do v3.
4. Sprawdź git status, następnie git add index.html pwa-list.html v3 README_GUI_V3.md
   i wykonaj commit/push. Upewnij się, że hosting publikuje katalog v3.
5. Po wdrożeniu sprawdź https://preorderhub.pl/v3/index.html?demo=1
   i następnie https://preorderhub.pl/v3/index.html bez demo.
6. Główny adres i poprzedni adres startowy pwa-list.html powinny przekierować do v3.
7. Na Androidzie otwórz właściwy adres v3 w Chrome i zainstaluj nową aplikację.
   Stara ikona może mieć odrębną tożsamość; po sprawdzeniu nowej można odinstalować starą.
   Jeśli widać nieaktualny interfejs, zamknij wszystkie okna i sprawdź wersję w incognito.
   Usunięcie danych witryny to ostateczność, może wylogować użytkownika.
8. Nie zmieniaj backendu, tokenów, adresu Turso ani konfiguracji Render podczas tej naprawy.

## Ograniczenia
Pakiet nie usuwa starych stron ani zbędnych plików z korzenia. Po testach można
usunąć nieużywane kopie root app.js, config.js i ilustracji WebP.
Pozostaw root style.css i ikony, jeśli zachowujesz starsze strony. 
Nie zmieniono backendu, Dockerfile, bazy ani harmonogramu. 
Sprawdzono komplet plików, odwołania do elementów i manifestu; nie wykonywano
wdrożenia na hostingu ani instalacji na rzeczywistym Androidzie.
