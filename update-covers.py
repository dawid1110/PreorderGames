import os
import asyncio
import requests
import libsql_client

# Jeśli używasz lokalnie pliku .env, możesz odkomentować linię poniżej:
# from dotenv import load_dotenv; load_dotenv()

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_PASSWORD")
TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

def get_twitch_token():
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        print("❌ Brak danych uwierzytelniających Twitch (Client ID / Secret) w zmiennych środowiskowych!")
        return None
    url = f"https://id.twitch.tv/oauth2/token?client_id={TWITCH_CLIENT_ID}&client_secret={TWITCH_CLIENT_SECRET}&grant_type=client_credentials"
    try:
        response = requests.post(url)
        if response.status_code == 200:
            return response.json().get("access_token")
    except Exception as e:
        print(f"❌ Błąd pobierania tokenu Twitch: {e}")
    return None

def get_igdb_cover_url(game_title: str, token: str):
    url = "https://api.igdb.com/v4/games"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    query = f'search "{game_title}"; fields cover.image_id; limit 1;'
    try:
        response = requests.post(url, headers=headers, data=query)
        if response.status_code == 200:
            data = response.json()
            if data and "cover" in data[0]:
                image_id = data[0]["cover"]["image_id"]
                return f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"
    except Exception as e:
        print(f"Błąd zapytania IGDB dla '{game_title}': {e}")
    return None

async def main():
    if not TURSO_DATABASE_URL:
        print("❌ Brak zmiennej TURSO_DATABASE_URL!")
        return

    print("🔑 Pobieranie tokenu dostępu od Twitcha...")
    token = get_twitch_token()
    if not token:
        return

    client = libsql_client.create_client(
        url=TURSO_DATABASE_URL,
        auth_token=TURSO_AUTH_TOKEN
    )

    try:
        # 1. Aktualizacja tabeli 'games' (preordery)
        print("\n--- Sprawdzanie tabeli: games ---")
        games_res = await client.execute("SELECT id, title FROM games WHERE cover_url IS NULL OR cover_url = ''")
        
        if not games_res.rows:
            print("✅ Wszystkie gry w 'games' mają już okładki.")
        else:
            for row in games_res.rows:
                game_id, title = row[0], row[1]
                print(f"🎮 Szukam okładki dla: '{title}'...")
                cover_url = get_igdb_cover_url(title, token)
                if cover_url:
                    await client.execute("UPDATE games SET cover_url = ? WHERE id = ?", [cover_url, game_id])
                    print(f"   ➔ Zaktualizowano pomyślnie!")
                else:
                    print(f"   ⚠️ Nie znaleziono okładki w IGDB.")
                await asyncio.sleep(0.25) # Krótka pauza, żeby nie zfloadować API Twitcha

        # 2. Aktualizacja tabeli 'collections' (kolekcja)
        print("\n--- Sprawdzanie tabeli: collections ---")
        col_res = await client.execute("SELECT id, title FROM collections WHERE cover_url IS NULL OR cover_url = ''")
        
        if not col_res.rows:
            print("✅ Wszystkie gry w 'collections' mają już okładki.")
        else:
            for row in col_res.rows:
                col_id, title = row[0], row[1]
                print(f"📦 Szukam okładki dla (Kolekcja): '{title}'...")
                cover_url = get_igdb_cover_url(title, token)
                if cover_url:
                    await client.execute("UPDATE collections SET cover_url = ? WHERE id = ?", [cover_url, col_id])
                    print(f"   ➔ Zaktualizowano pomyślnie!")
                else:
                    print(f"   ⚠️ Nie znaleziono okładki w IGDB.")
                await asyncio.sleep(0.25)

        print("\n✨ Proces aktualizacji okładek zakończony!")

    except Exception as e:
        print(f"❌ Wystąpił błąd: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())