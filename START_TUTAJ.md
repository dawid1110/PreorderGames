# Preorder Hub 3.2.2 — przywrócenie działania GUI

**Wydanie 20261124-6.** Oparte na Twoim aktualnym archiwum GitHub `PreorderGames-main(1).zip`, a nie na starszym repozytorium. Właściwy backend zachowano bajt w bajt. Nie modyfikowano żadnych danych produkcyjnych.

1. Zrób kopię repozytorium. W Eksploratorze Windows wybierz **Wyodrębnij wszystkie**, jako miejsce docelowe wskaż katalog repozytorium, w którym jest `api_v2.py`. Potwierdź nadpisanie. Nie kopiuj pojedynczych plików z folderu v3 do korzenia. Archiwum zachowuje strukturę i nie ma dodatkowego katalogu nadrzędnego.
2. Upewnij się, że `index.html` jest stroną reklamową i odwołuje się do `launch/style.css`, natomiast `v3/index.html` do `/v3/style.css`. `v3/config.js` pokazuje wersję 3.2.2. Stare, przypadkowo dodane pliki `config.js`, `pwa_logic.test.cjs`, `test_pwa_navigation_browser.py` w korzeniu można usunąć z Git; nie są wykorzystywane przez nowe GUI. Rozpakowanie ZIP nie usuwa istniejących plików.
3. `git status`, sprawdź zmiany i brak sekretów, `git add -A`, `git commit -m "Restore frontend paths and simplify PWA 3.2.2"`, `git push`.
4. Po deployu najpierw sprawdź w incognito `/`, `/v3/index.html?demo=1`, `/v3/index.html`. Następnie w zwykłym Chrome wejdź na `/recover.html` i zresetuj pamięć PWA po zapisaniu zmian i zamknięciu innych okien. Jeżeli nadal występują błędy, DevTools → Application → Service Workers → Unregister. W ostateczności wyczyść dane tej witryny (wymaga ponownego logowania). Na Androidzie użyj tej samej strony naprawczej; dopiero gdy to nie pomaga, odinstaluj PWA i zainstaluj z `/v3/index.html`.
5. **Nie zmieniaj Rendera ani Turso.** Komenda startowa pozostaje `uvicorn api_v2:app --host 0.0.0.0 --port $PORT`. Nie wykonuj migracji z powodu tego hotfixa. Jeśli CDN nadal podaje poprzednie HTML lub workery, sprawdź status deployu i rzeczywiste nagłówki Cache-Control; ewentualnie wyczyść właściwe adresy w cache Cloudflare.

PWA wymaga połączenia z internetem. Nie przechwytujemy nawigacji ani nie przechowujemy stron w CacheStorage; przycisk instalacji i manifest pozostają dostępne. Zobacz `README_GUI_V3.md`.

## 4. Włącz funkcje publiczne później

**Nie jest to potrzebne do naprawy PWA ani korzystania z własnego konta.**

1. Zrób pełną kopię Turso i przetestuj migrację na kopii. Sprawdź faktyczny schemat tabel; aplikacja oczekuje `users`, `games`, `store_offers`, `collections` i opcjonalnie `weekly_summary_runs`.
2. Uruchom `migrations/0032_public_launch.sql` w odpowiedniej bazie Turso. Tworzy cztery dodatkowe tabele i indeks, bez usuwania istniejących rekordów. Nie wykonuj `weekly_summary.sql`, jeśli tabela crona już istnieje. Zweryfikuj tabele po migracji.
3. Na Render ustaw `PUBLIC_LAUNCH_ENABLED=true` i `PUBLIC_ADMIN_USER_ID` na Twoje rzeczywiste ID z tabeli `users` (nie Telegram ID). `PUBLIC_SIGNUP_ENABLED=false` na tym etapie. Pozostałe zmienne według `.env.example`.
4. Sprawdź Ustawienia → Dane i zgłoszenia → Otwórz narzędzia konta. Eksport JSON, zgłoszenia, statystyki administratora i usunięcie własnego konta są zabezpieczone po stronie API. Konta administratora i odbiorcy Telegram są chronione przed samodzielnym usunięciem. Weryfikuj na kontach testowych, nie usuwaj swojego konta. Pomiar aktywności oznacza udane logowanie lub pobranie preorderów; działa dopiero po włączeniu flagi.
5. Przed otwarciem rejestracji opublikuj rzeczywisty regulamin i informację o prywatności z danymi operatora, kontaktem, podstawami przetwarzania, okresami przechowywania, prawami użytkowników i właściwą obsługą dostawców. `privacy.html` i `terms.html` są **technicznymi stronami informacyjnymi, nie gotowymi dokumentami prawnymi**. Wymagają uzupełnienia i weryfikacji przez operatora. Sprawdź też warunki IGDB/Twitch dla publicznego wykorzystania, limity Render/Turso, bezpieczeństwo, logi, kopie i zasady nadużyć. Wprowadź niezależne limity na brzegu/API, jeśli udostępniasz usługę publicznie. Limiter w kodzie działa lokalnie w procesie, nie jest ochroną rozproszoną.
6. Ustaw `PUBLIC_OPERATOR_NAME`, `PUBLIC_CONTACT_EMAIL`, `PUBLIC_PRIVACY_URL`, `PUBLIC_TERMS_URL` (publiczne, finalne HTTPS dokumenty) i `PUBLIC_POLICY_VERSION` (np. 2026-11-24). Backend sprawdza format, nie treść ani dostępność dokumentów. Ustaw `PUBLIC_SIGNUP_ENABLED=true` dopiero po tej kontroli i testach. Nowe konta muszą mieć hasło co najmniej 12 znaków oraz potwierdzoną aktualną wersję regulaminu. Istniejące konta zachowują obecne hasła.

Aby natychmiast zamknąć rejestrację, ustaw `PUBLIC_SIGNUP_ENABLED=false` i wykonaj redeploy. Aby wyłączyć wszystkie dodatkowe funkcje, ustaw również `PUBLIC_LAUNCH_ENABLED=false`. Nie cofaj migracji przez kasowanie nowych tabel. Po utworzeniu/usunięciu publicznych kont nie wracaj bez dodatkowej analizy do backendu 3.1: ochrona przed ponownym przydzieleniem ID usuniętych kont jest w 3.2. W razie potrzeby zamknij rejestrację i zachowaj nowy backend oraz tabele.

## 5. Dokumentacja i testy

- `README_PUBLIC_LAUNCH.md` — aktualna mapa plików, endpointów i flag.
- `README_GUI_V3.md` — aktualny opis PWA, instalacji i kolejnych wydań.
- `PreorderHub_Dokumentacja.pdf` i `.md` — archiwalna pełna dokumentacja 3.1; obowiązujące zmiany 3.2 są opisane tutaj i w nowych README.
- `TESTY.md` — wykonane testy i ograniczenia.
- `PORZADKI.md` — ewentualne stare pliki, które ZIP nie usuwa z istniejącego katalogu.

Nie ma tu eksportu danych produkcyjnych, wartości sekretów, historii Git ani konfiguracji zewnętrznych usług. Zachowaj je osobno. Nie publikuj prywatnych kopii danych, `.env`, skryptów i testów jako statycznych zasobów WWW; najlepiej skonfiguruj hosting tak, aby udostępniał tylko HTML, `v3/`, `launch/`, ikony, manifesty i service worker. Kod repozytorium jest oddzielny od zawartości dostępnej przez serwer.
