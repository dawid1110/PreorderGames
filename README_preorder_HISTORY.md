# Historyczna instrukcja – NIE używać do wdrożenia

Ten plik opisuje wcześniejszy wariant WebSocket. Aktualny backend używa HTTPS; zobacz START_TUTAJ.md.

# Preorder Hub – poprawiony backend

## Wdrożenie

1. Zrób kopię bazy i aktualnego backendu. Przetestuj na osobnej instancji, nie na produkcji.
2. Zastąp dotychczasowy plik aplikacji przez `main.py` (lub użyj obecnej nazwy modułu).
3. Uzupełnij zależności: `python -m pip install -r requirements_preorder.txt` (Python 3.10+).
4. Zachowaj dotychczasowy `SECRET_KEY`, jeżeli jest wystarczająco silny i ma co najmniej 32 bajty. Zmiana klucza unieważnia istniejące JWT. W przypadku słabego klucza wymień go na losowy (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
5. Ustaw `TURSO_DATABASE_URL=libsql://...` (lub `wss://...`) i `TURSO_AUTH_TOKEN`. Klient libsql-client 0.3.1 nie obsługuje interaktywnych transakcji po `https://`. Nie zamieniaj protokołu, jeżeli serwer nie udostępnia WebSocketów; w takim przypadku trzeba dobrać innego klienta bazy.
6. Uruchom `uvicorn main:app --host 0.0.0.0 --port 8000`. Test API: `/ping`, dokumentacja: `/docs`.

## Zmienne środowiskowe

- Obowiązkowe: `SECRET_KEY`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` (token niepotrzebny dla lokalnego `file:`).
- Opcjonalne okładki: `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` (nadal obsługiwane `TWITCH_CLIENT_PASSWORD`).
- `APP_TIMEZONE`: domyślnie `Europe/Warsaw`.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: domyślnie 10080 (dotychczasowe 7 dni); można skrócić po dostosowaniu frontendu. Nie ma refresh tokenów i indywidualnego unieważniania sesji.
- `ALLOW_LEGACY_PLAINTEXT_PASSWORDS`: domyślnie `false`. Stare hashe PBKDF2 są migrowane do Argon2id podczas poprawnego logowania, bez tego przełącznika. Konta z hasłem jawnym wymagają resetu lub krótkiej, kontrolowanej migracji po włączeniu przełącznika. Wyłącz go po migracji. Sprawdź, czy kolumna `users.password_hash` mieści nowy hash Argon2id. Przy powrocie do starego backendu nowe hashe nie będą obsługiwane.

## Telegram (opcjonalny)

Uruchom `weekly_summary.sql` na właściwej bazie przed włączeniem crona. To nowa tabela, nie zmienia starych rekordów. Ustaw `CRON_SECRET` (osobny, losowy, co najmniej 32 bajty), `TELEGRAM_USER_ID` (ID jednego użytkownika), `TELEGRAM_BOT_TOKEN` oraz `TELEGRAM_CHAT_ID`. Jeden chat Telegrama jest przypisany do jednego użytkownika; nie rozsyła cudzych danych. Jeśli nie ma `CRON_SECRET`, cron jest wyłączony. Zmień harmonogram z GET na POST:

```bash
curl -X POST 'https://TWOJE-API/cron/weekly_summary' \
  -H "X-Cron-Secret: $CRON_SECRET"
```

Powtórne uruchomienie w tym samym tygodniu po sukcesie nie wyśle kolejnej wiadomości. Po awarii lub przerwaniu procesu rekord może pozostać w stanie `sending` albo `uncertain`. Przed ręcznym usunięciem takiego rekordu sprawdź faktyczny stan wiadomości w Telegramie; ponowienie może powielić część wiadomości. To świadomy kompromis (brak gwarancji exactly-once między bazą a Telegramem).

## Kontrakt API i frontend

Nazwy dotychczasowych endpointów pozostały bez zmian (cron zmienił metodę HTTP). `get_preorders` zwraca teraz osobny rekord na `id`, wraz z `game_id` (to samo ID). Zalecane przykłady żądań:

```json
{"game_id": 123, "title": "Nowy tytuł"}
```

PUT `/edit`: brak `offers` zachowuje dotychczasowe oferty, `"offers": []` usuwa wszystkie. Brak innych edytowalnych pól zachowuje ich wartość; `release_date: null` usuwa datę. Stary format `original_title` + `original_platform` nadal działa dla jednoznacznego rekordu. DELETE `/delete` i POST `/move_to_collection` przyjmują `{"game_id":123}` lub stare `title` + `platform`. POST `/update_budget` przyjmuje `{"game_id":123,"in_budget":false}`. ID muszą być liczbami całkowitymi; budżet musi być JSON-owym booleanem. DELETE `/delete_from_collection` nadal używa `id` kolekcji. Duplikaty są blokowane przy dodawaniu lub zmianie tytułu/platformy (po trim + Unicode casefold). Istniejące duplikaty nie są kasowane i trzeba nimi zarządzać po ID; stary niejednoznaczny format zwraca 409.

Nowa rejestracja wymaga hasła minimum 8 znaków. Nowe hasła zachowują spacje; migracja starych hashy zachowuje dotychczasowe obcięcie spacji na brzegach, a późniejsze logowanie wymaga dokładnego hasła. Daty: `YYYY-MM-DD`, `DD.MM.YYYY`, `YYYY-MM`, `YYYY`, `YYYY-Q1`…`YYYY-Q4`, `TBA`, `TBD`, null. Daty przybliżone nie trafiają do tygodniowego powiadomienia. Oferty: maks. 50, cena nieujemna z maks. 2 miejscami po przecinku (kropka w napisie), adres HTTP/HTTPS lub pusty. Przy walidacji błędów zwracane jest 422, konflikty 409, brak gry 404.

## Testy

`python -m pip install pytest`

`python -m pytest -q test_preorder.py` – testy z lokalnym SQLite i zastępczymi integracjami; nie używają bazy produkcyjnej.

`TEST_REAL_LIBSQL=1 python -m pytest -q test_preorder.py` – dodatkowy tryb sprawdzający rzeczywisty klient libsql-client na tymczasowym lokalnym pliku; wymaga jego instalacji. Następnie sprawdź na testowym Turso, szczególnie transakcje i współbieżność.

## Świadome ograniczenia

- Schemat istniejących czterech tabel nie był dostępny. Kod opiera się na kolumnach z oryginału. Nie uruchamiano go z rzeczywistym Turso, frontendem ani Telegramem/IGDB.
- Nie migrowano cen na grosze ani nie dodawano waluty: utrzymany dotychczasowy numeryczny format (walidacja Decimal, zapis float). Nie migrowano historii ofert do kolekcji – przeniesienie nadal je usuwa, ale atomowo. Nie dodano automatycznie indeksów i constraints do starych tabel; po sprawdzeniu schematu warto zweryfikować UNIQUE users(username), indeksy games(user_id), store_offers(game_id), collections(user_id) oraz regułę unikalności gier na poziomie bazy dla innych zapisujących aplikacji.
- Ograniczanie kosztownych operacji hashowania na worker nie zastępuje rozproszonego rate limitu logowania/rejestracji (np. na proxy). API pozostaje bez refresh tokenów. Brak pełnej ochrony przed równoległym nadpisaniem wszystkich pól edycji; dla takiego wymagania dodaj wersję rekordu (optimistic locking).
- Okładki nadal wykorzystują pierwszy wynik wyszukiwania IGDB; tytuły zawierające delimitery składni są wyszukiwane w uproszczonej postaci. Przy awarii integracji stara okładka jest zachowana podczas edycji, a nowy preorder może zostać zapisany bez okładki.
- Zostawiono libsql-client, aby ograniczyć zakres zmiany; repozytorium jest zarchiwizowane. Migrację na wspierany SDK zaplanuj osobno.
