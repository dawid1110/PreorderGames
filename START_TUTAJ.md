# Preorder Hub 3.1 — kompletny projekt do publikacji

## Wdrożenie

To kompletny projekt złożony z ostatniego przesłanego repozytorium i poprawki GUI/PWA. ZIP ma pliki bezpośrednio w korzeniu. Rozpakuj do katalogu repozytorium **PreorderGames**, obok `api_v2.py`, z opcją zastąpienia plików. Nie przenoś zawartości `v3/` do korzenia. Nie usuwaj `.git/` ani lokalnych sekretów. Najpierw zachowaj kopię bieżącego repozytorium. Jeżeli odtwarzasz projekt od zera, rozpakuj do pustego katalogu.

Po rozpakowaniu, przy publikacji z Git:

```bash
git status
git add -A
git commit -m "Preorder Hub 3.1 - complete GUI and PWA"
git push
```

Przed commitem sprawdź, że nie dodajesz własnych plików z sekretami. Hosting musi publikować katalog zawierający zarówno `index.html`, jak i cały `v3/`. Wdrożenie do GitHub/hostingu nie zostało wykonane automatycznie.

**Adres główny:** https://preorderhub.pl/ przekierowuje do https://preorderhub.pl/v3/index.html. Stare adresy listy, kolekcji, PWA, logowania i innych stron przekierowują do nowego GUI. Stare linki edycji/dodawania prowadzą do listy preorderów; otwórz właściwy formularz w nowym GUI. Stary link rejestracji prowadzi do ekranu logowania z opcją rejestracji. Bento/Console zastąpiono nowym pulpitem.

**Demo:** https://preorderhub.pl/v3/index.html?demo=1 – przykładowe dane, bez zapisu do prawdziwego API. Na adresie głównym `?demo=1` również zostanie przekazany.

## Android i tablet

Otwórz w Chrome właściwy adres HTTPS `/v3/index.html` bez `?demo=1`. Naciśnij **Zainstaluj aplikację**, a potem **Zainstaluj teraz**, jeśli Chrome udostępni instalator. W przeciwnym razie użyj menu Chrome i opcji instalacji/dodania do ekranu głównego. Stara ikona może uruchamiać `/pwa-list.html`, który przekieruje do nowej listy, ale stara i nowa instalacja mogą mieć różne tożsamości. Zalecamy zainstalować PWA z `/v3/index.html` i usunąć starą dopiero po sprawdzeniu nowej. Na iOS: Safari → Udostępnij → Dodaj do ekranu początkowego. Po aktualizacji zapisz formularze i zamknij wszystkie karty/okna aplikacji, a następnie otwórz ponownie.

## Render i Turso

`api_v2.py` jest identyczny bajt w bajt z ostatnim przesłanym repozytorium (HTTPS). Nie zmieniano danych, schematu bazy, CORS, JWT, logowania ani zmiennych środowiskowych. Start Command dla natywnego Render pozostaje:

```bash
uvicorn api_v2:app --host 0.0.0.0 --port $PORT
```

Dockerfile został poprawiony, by też uruchamiał `api_v2:app`. `api.py` jest starszym backendem, pozostawionym wyłącznie jako odniesienie; nie uruchamiaj go zamiast v2. Wymagania Pythona pozostawiono w istniejącej wersji, aby nie zmieniać działającego środowiska. Starsze `api.py` i narzędzie `update-covers.py` nadal korzystają z libsql-client/requests, dlatego ich zależności nie usuwano. Narzędzie aktualizacji okładek pozostawiono bez zmian; nie jest uruchamiane przez aplikację. Nie uruchamiaj go bez kopii danych i weryfikacji połączenia; może zmieniać dane wielu kont. `weekly_summary.sql` to opcjonalna migracja tabeli crona, nie kompletna baza. Nie wykonuj jej ponownie bez potrzeby. `.env.example` jest szablonem, nie zawiera sekretów i nie jest automatycznie ładowany.

## Co jest w katalogach

- `v3/` — aktywny frontend (HTML, CSS, JS, manifest, SW, zasoby), z priorytetem Androida.
- HTML w korzeniu — przekierowania dla dotychczasowych adresów; nie są drugim GUI.
- `manifest.json`, `sw.js`, ikony w korzeniu — kompatybilność ze starszą PWA; aktywny manifest i service worker znajdują się w `v3/`.
- `PreorderHub_Dokumentacja.pdf` i `.md` — pełna dokumentacja z przekazanego archiwum. Wcześniejszy opis starego Dockerfile i sposobu publikacji czytaj z uwzględnieniem tego pliku, który ma pierwszeństwo dla aktualnego wydania.
- `README_GUI_V3.md` — szczegóły nowego GUI i instalacji.
- `README_preorder_HISTORY.md` — historyczna instrukcja, nie używać jej jako bieżącej konfiguracji.
- `tests/pwa_logic.test.cjs` — testy logiki PWA (Node 18+), uruchomienie: `node tests/pwa_logic.test.cjs`.

Z kompletu usunięto zbędne kopie `app.js`, `config.js`, ilustracji i starego CSS w korzeniu, `download` oraz pliki `.pyc` i `__pycache__`. Jeżeli rozpakujesz ZIP na istniejącą kopię, ZIP **nie usuwa plików nieobecnych w paczce**. Ewentualne pozostałości nie są używane przez nowe GUI. Do fizycznego uporządkowania możesz je później usunąć z korzenia (nigdy z `v3/`); pełna lista w `PORZADKI.md`.

## Odbiór po wdrożeniu

1. Wejdź na główną domenę w Chrome incognito; powinien otworzyć się nowy dashboard lub jego ekran logowania.
2. Sprawdź demo, a potem właściwą wersję z logowaniem; przetestuj dane, dodanie/edycję gry testowej, kalendarz, budżet i kolekcję.
3. Zainstaluj PWA na rzeczywistym telefonie/tablecie Android i sprawdź start z ikony.
4. W razie problemu zobacz `README_GUI_V3.md`, logi Render i konsolę przeglądarki. Adres API jest w `v3/config.js`.

Nie ma tu danych produkcyjnych Turso, wartości sekretów Render ani historii Git. Zachowaj te informacje osobno w bezpiecznym miejscu. Testy lokalne nie zastępują odbioru na hostingu i fizycznym urządzeniu.
