# Preorder Hub 3.2.0 — Public Launch + naprawa PWA

**Wydanie: 20261124-4.** Kompletne repozytorium, nie paczka samych różnic. Punktem wyjścia jest działająca wersja 3.1. Nie wykonano zdalnego wdrożenia ani operacji w produkcyjnej bazie.

## 1. Rozpakuj i wdroż (bez migracji bazy)

1. Zrób kopię aktualnego repozytorium (w tym lokalnej konfiguracji), najlepiej zapisz działającą wersję w Git. Nie kasuj `.git/` ani lokalnych sekretów.
2. Rozpakuj cały ZIP do katalogu `PreorderGames`, obok dotychczasowego `api_v2.py`, z zastąpieniem plików. ZIP nie ma dodatkowego katalogu nadrzędnego. **Nie wypakowuj `v3/` do korzenia.**
3. Zatwierdź zmiany. Sprawdź `git status` i upewnij się, że nie dodajesz sekretów:

```bash
git status
git add -A
git commit -m "Preorder Hub 3.2 - Public Launch and PWA recovery"
git push
```

4. Opublikuj kompletny frontend w Cloudflare, sprawdź ukończenie deployu. W Render zostaw `pip install -r requirements.txt` oraz `uvicorn api_v2:app --host 0.0.0.0 --port $PORT`. Dockerfile również uruchamia `api_v2:app`. Nowy `public_launch.py` musi być obecny obok `api_v2.py`. Dotychczasowe sekrety, adres Turso HTTPS i adres API zachowaj. Nie wykonuj migracji na tym etapie. Jeśli masz już ustawione zmienne `PUBLIC_*`, upewnij się, że oba przełączniki są `false`.
5. Sprawdź `https://preorderhub.pl/` (strona powitalna), `https://preorderhub.pl/v3/index.html?demo=1` (demo), a następnie `https://preorderhub.pl/v3/index.html` (dotychczasowe konto, dane). Sprawdź także `/ping` backendu i `/public/config`. Nowa rejestracja i narzędzia konta pozostają domyślnie wyłączone, logowanie istniejącego użytkownika oraz operacje na grach nie potrzebują nowych tabel.

## 2. Rozwiąż obecny problem PWA

Po deployu wersji 3.2 wejdź w zwykłym Chrome na **https://preorderhub.pl/recover.html**. Zapisz formularze i zamknij pozostałe karty oraz okna PWA, a następnie wybierz **Resetuj pamięć PWA i otwórz aplikację**. Reset usuwa wyłącznie znane rejestracje `/sw.js`, `/v3/sw.js` oraz cache o prefiksie `preorderhub-v3-shell-`. Nie czyta ani nie usuwa `localStorage`, nie wywołuje API i nie zmienia gier. Potrzebujesz połączenia z internetem, żeby pobrać nowy frontend.

Przejście z wydań 20261124-2 i -3 dodatkowo próbuje jednorazowo aktywować nowy worker bez czekania na zamknięcie kart. Nie wymusza przeładowania dokumentów. Przy kolejnych wydaniach okno aktualizacji ma przyciski **Później** i **Zaktualizuj teraz**; aktywacja przeładowuje wyłącznie okno, które o nią poprosiło, po zapisaniu zmian. Ustawienia → Aplikacja → Sprawdź aktualizacje / Resetuj pamięć PWA.

Jeśli `/recover.html` nie działa w zwykłym Chrome, otwórz DevTools → Application → Service Workers, wyrejestruj stare workery Preorder Hub, zamknij pozostałe okna i odśwież. `Clear site data` to ostateczność (wyloguje Cię). Sprawdź działanie w incognito i nagłówki Cloudflare. Plik `_headers` sugeruje rewalidację HTML i workerów, o ile sposób hostowania go obsługuje; sprawdź faktyczne nagłówki po deployu. Gdy CDN ma regułę Cache Everything, wyłącz ją dla HTML i workerów lub wyczyść właściwe adresy cache CDN.

## 3. Instalacja Android / tablet / iOS

Instaluj **z `/v3/index.html`**, nie z publicznego landing page ani demo. Przycisk `Zainstaluj aplikację` otwiera instrukcję i, jeśli dostępny, systemowy instalator Chrome. Możesz też użyć menu Chrome. Identyfikator, start URL i zakres manifestu v3 zachowano, więc wcześniejsza instalacja v3 nadal ma tę samą tożsamość. Stare `/pwa-list.html` przekierowuje do aplikacji. Na iOS użyj Safari → Udostępnij → Dodaj do ekranu początkowego. Po instalacji sprawdź otwarcie z ikony. Offline dostępny jest jedynie statyczny interfejs; operacje na danych wymagają internetu.

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
