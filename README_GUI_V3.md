# Preorder Hub — GUI i PWA 3.2.0

Aktualne wydanie `20261124-4`. Wdrożenie: [START_TUTAJ.md](START_TUTAJ.md), zmiany publiczne: [README_PUBLIC_LAUNCH.md](README_PUBLIC_LAUNCH.md).

- `https://preorderhub.pl/` — strona informacyjna; `https://preorderhub.pl/v3/index.html` — aplikacja; `?demo=1` — izolowane demo.
- W Chrome Android/Tablet otwórz właściwą aplikację (HTTPS, bez demo) → Zainstaluj aplikację → Zainstaluj teraz, jeśli przeglądarka udostępnia instalator. W przeciwnym razie menu Chrome → instalacja/dodanie do ekranu głównego. Na iOS Safari → Udostępnij → Dodaj do ekranu początkowego. Stare ikony `/pwa-list.html` przekierowują; preferuj instalację v3. Nie zmieniono identyfikatora v3 ani scope.
- `v3/sw.js` przechowuje tylko z góry określone statyczne zasoby, wersjonuje JS i CSS, pomija żądania API, autoryzowane, demo oraz recovery. Przy błędzie cache próbuje sieci; gdy oba zawiodą, pokazuje techniczny ekran awaryjny. Nie zapisuje danych kont i nie gwarantuje synchronizacji offline.
- Pierwsza migracja z wydań 20261124-2/-3 aktywuje nowy worker automatycznie, bez wymuszonego reloadu. Kolejne aktualizacje: Później / Zaktualizuj teraz. Zapisz formularze także w innych oknach. Tylko okno żądające aktualizacji automatycznie odświeża się, jeśli nadal nie trwa edycja. Numer wydania w ustawieniach. Opcje: sprawdzenie aktualizacji i reset PWA.
- Recovery: `/recover.html` (po publikacji), również link na ekranie logowania. Zamknij inne okna, kliknij reset. Selektywne wyrejestrowanie znanych workerów i usunięcie statycznego cache, bez czyszczenia tokena. Gdy problem trwa, DevTools → Application → Service Workers → Unregister; `Clear site data` tylko w ostateczności.
- `sw.js` w korzeniu wyrejestrowuje starą instalację workera. Inne rejestracje/cache poza znanymi nazwami pozostają bez zmian.
- Przed każdą zmianą statycznego shell zwiększ `RELEASE` w `v3/sw.js`, `release` w `v3/config.js` i znaczniki `?v=` w `v3/index.html`. Opublikuj wszystkie pliki razem. `_headers` jest sugestią dla Cloudflare, zweryfikuj faktyczne HTTP nagłówki. Nie zmieniaj manifestu bez planu migracji.

Backend: `uvicorn api_v2:app --host 0.0.0.0 --port $PORT`. Domyślnie nowe funkcje są wyłączone, bez migracji; dotychczasowe logowanie działa na istniejących tabelach. Nie zmieniaj istniejących sekretów.
