# Preorder Hub 3.1 - GUI i instalacja PWA

Data: 24.11.2026. Ta paczka aktualizuje frontend w katalogu `v3/`. Priorytet PWA: Android, telefony i tablety. Nie zawiera zmiany backendu ani migracji bazy. Nie została automatycznie wdrożona.

## Wdrożenie

1. Skopiuj **cały katalog `v3/`** do aktualnego repozytorium, zastępując poprzedni `v3/`, jeśli już istnieje.
2. Opublikuj przez dotychczasowy hosting frontendu. Przy automatycznym deployu z Git wykonaj:

```bash
git add v3/
git commit -m "Add Android PWA installation flow"
git push
```

3. Otwórz `https://preorderhub.pl/v3/index.html` po zakończonej publikacji. Sprawdź, że `pwa.js`, `sw.js`, manifest i ikony zwracają właściwe pliki, a nie HTML fallbacku.
4. Jeśli korzystałeś już z v3, zapisz otwarte formularze, zamknij wszystkie karty/okna aplikacji i otwórz ją ponownie, aby aktywowała się nowa wersja workera.

Dotychczasowy backend pozostaje `api_v2.py` z `TursoHTTPClient` i HTTPS. Jego komenda na Render to `uvicorn api_v2:app --host 0.0.0.0 --port $PORT`. Do poprawki PWA nie zmieniaj nazwy modułu ani zmiennych Turso.

## Android: instalacja

W Chrome otwórz właściwą stronę HTTPS, bez `?demo=1`. Naciśnij **Zainstaluj aplikację** na ekranie logowania lub w aplikacji. W dialogu naciśnij **Zainstaluj teraz**, jeżeli Chrome udostępnił instalator. Alternatywnie wybierz menu **⋮ → Zainstaluj i utwórz skrót → Zainstaluj**; inne wersje używają nazw „Zainstaluj aplikację” lub „Dodaj do ekranu głównego”. Otwórz ikonę i zaloguj się swoim kontem. Procedura na tablecie jest taka sama. Instalacja odbywa się osobno na każdym urządzeniu.

Na iPhone/iPad użyj Safari → Udostępnij → dodanie do ekranu początkowego. Jeśli dostępna jest opcja „Otwórz jako aplikację internetową”, pozostaw ją włączoną.

Stara ikona uruchamiająca `/pwa-list.html` nie zmienia się automatycznie po wgraniu v3. Nowe wejście instaluj z `/v3/index.html`, a starą ikonę usuń po sprawdzeniu nowej. Wcześniejsze v3 zachowuje swoją tożsamość: jawne `id: "/"` jest równoważne poprzedniemu `id: "./"` na tym samym originie. Zakres pozostaje `/v3/`.

## Pliki

| Plik | Rola |
| --- | --- |
| `index.html` | Ekrany, formularze, dialog instalacji i powiązania zasobów |
| `app.js` | API, sesja, nawigacja, listy, CRUD, daty i budżet |
| `config.js` | Publiczny adres API oraz formatowanie; żadnych sekretów |
| `style.css` | Wygląd, responsywność i dialog instalacji |
| `pwa.js` | Instalacja, instrukcje Android/iOS, rejestracja SW, komunikat aktualizacji |
| `manifest.json` | Nazwa, ikony, ID, start i zakres aplikacji |
| `sw.js` | Wersjonowany cache statycznych plików |
| `assets/` | Ikony192/512 i cztery ilustracje demo; wymagany kompletny katalog |

## Offline i aktualizacje

Service worker przechowuje wyłącznie zamkniętą listę statycznych plików. Nie zapisuje odpowiedzi API ani danych konta w Cache Storage. Token sesji pozostaje w localStorage zgodnie z istniejącą logiką logowania. Odczyt i zapis gier wymagają internetu; nie ma kolejki offline ani powiadomień push.

Przy następnej zmianie dowolnego pliku powłoki zwiększ `RELEASE` w `sw.js`. Obecna wersja to `20261124-2`. Nowe wydanie czeka na zamknięcie poprzednich okien; nie wymusza przeładowania otwartego formularza. Zawsze publikuj komplet plików.

## Demo i lokalny podgląd

`?demo=1` daje fikcyjne dane i CRUD w pamięci, bez odczytu sesji, wywołań API i instalatora PWA. Odświeżenie resetuje demo. W katalogu repozytorium uruchom `python3 -m http.server 5500`, następnie otwórz `http://localhost:5500/v3/index.html?demo=1`. Instalację na urządzeniu testuj przez HTTPS, nie z pojedynczego lokalnego pliku HTML.

## Zakres weryfikacji

Sprawdzono składnię JS/JSON, strukturę HTML, istnienie zasobów i rzeczywiste rozmiary PNG. Przeszło 17 grup testów Node VM dotyczących instalatora i zasad cache. Nie wykonano fizycznej instalacji Android/iOS ani nowego testu wizualnego; uruchomienie Chromium było zablokowane w środowisku przygotowania. Nie wykonywano deployu, połączeń z produkcyjną bazą ani testowych zapisów na prawdziwych danych.

Pełny opis plików, API, bazy, środowiska Render, crona, aktualizacji i backupu znajduje się w **PreorderHub_Dokumentacja.pdf / PreorderHub_Dokumentacja.md**. Pełne archiwum projektu dodatkowo zawiera snapshot backendu, SQL crona i testy. Historyczny `README_preorder.md` z repo opisuje starszy wariant WSS i nie jest instrukcją konfiguracji aktualnego HTTP API.
