from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from datetime import datetime, timedelta
import hashlib
import secrets
import os
import libsql_client

app = FastAPI()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Konfiguracja CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://preordergames.dwiad1110.workers.dev", 
        "http://localhost:5500" # Zostaw do testów u siebie na komputerze
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bezpieczne hashowanie wbudowane w Pythona (brak zewnętrznych zależności)
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return f"{salt}${pwd_hash}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, pwd_hash = stored_hash.split('$')
        check_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
        return check_hash == pwd_hash
    except Exception:
        return False

# Połączenie z bazą Turso (libsql)
def get_db_client():
    return libsql_client.create_client(
        url=os.getenv("TURSO_DATABASE_URL"),
        auth_token=os.getenv("TURSO_AUTH_TOKEN")
    )

# ==========================================
# AUTORYZACJA
# ==========================================

@app.post("/register")
async def register(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Podaj nazwę użytkownika i hasło.")
        
    hashed_password = hash_password(password)
    client = get_db_client()
    
    try:
        await client.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            [username, hashed_password]
        )
        await client.close()
        return {"status": "success", "message": "Rejestracja udana!"}
    except Exception as e:
        await client.close()
        raise HTTPException(status_code=400, detail="Użytkownik o takiej nazwie już istnieje.")

@app.post("/login")
async def login(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    client = get_db_client()
    res = await client.execute(
        "SELECT id, password_hash FROM users WHERE username = ?",
        [username]
    )
    await client.close()
    
    if not res.rows:
        raise HTTPException(status_code=401, detail="Nieprawidłowa nazwa użytkownika lub hasło.")
        
    user_id, password_hash = res.rows[0]
    
    if not verify_password(password, password_hash):
        raise HTTPException(status_code=401, detail="Nieprawidłowa nazwa użytkownika lub hasło.")
        
    return {"status": "success", "user_id": user_id, "username": username}


# ==========================================
# PREORDERS & OFERTY
# ==========================================

@app.get("/get_preorders")
async def get_preorders(user_id: int):
    client = get_db_client()
    
    games_res = await client.execute(
        "SELECT id, title, platform, release_date FROM games WHERE user_id = ?", 
        [user_id]
    )
    
    games_dict = {}
    for game_row in games_res.rows:
        game_id, title, platform, release_date = game_row
        key = (title.strip().lower(), platform.strip().lower())
        
        offers_res = await client.execute(
            "SELECT store_name, price, order_number, url FROM store_offers WHERE game_id = ?", 
            [game_id]
        )
        
        offers = []
        for offer_row in offers_res.rows:
            store_name, price, order_number, url = offer_row
            offers.append({
                "store_name": store_name,
                "price": price,
                "orderNumber": order_number,
                "url": url
            })
            
        if key in games_dict:
            games_dict[key]["offers"].extend(offers)
        else:
            games_dict[key] = {
                "title": title,
                "platform": platform,
                "release_date": release_date,
                "offers": offers
            }
            
    await client.close()
    return list(games_dict.values())


@app.post("/add")
async def add_preorder(data: dict):
    user_id = data.get("user_id")
    title = data.get("title")
    platform = data.get("platform")
    release_date = data.get("release_date")
    offers = data.get("offers", [])
    
    if not user_id or not title or not platform:
        raise HTTPException(status_code=400, detail="Brak wymaganych danych.")
        
    client = get_db_client()
    
    try:
        game_res = await client.execute(
            "INSERT INTO games (user_id, title, platform, release_date) VALUES (?, ?, ?, ?)",
            [user_id, title, platform, release_date]
        )
        game_id = game_res.last_insert_rowid
        
        for offer in offers:
            store_name = offer.get("store_name")
            price = offer.get("price")
            order_number = offer.get("order_number")
            url = offer.get("url")
            
            if store_name and price is not None:
                await client.execute(
                    "INSERT INTO store_offers (game_id, store_name, price, order_number, url) VALUES (?, ?, ?, ?, ?)",
                    [game_id, store_name, price, order_number, url]
                )
                
        await client.close()
        return {"status": "success", "message": "Preorder dodany pomyślnie!"}
        
    except Exception as e:
        await client.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/delete")
async def delete_game(data: dict):
    title = data.get("title")
    platform = data.get("platform")
    user_id = data.get("user_id")
    
    client = get_db_client()
    try:
        game_res = await client.execute(
            "SELECT id FROM games WHERE title = ? AND platform = ? AND user_id = ?",
            [title, platform, user_id]
        )
        if not game_res.rows:
            await client.close()
            raise HTTPException(status_code=404, detail="Gra nie znaleziona.")
            
        game_id = game_res.rows[0][0]
        await client.execute("DELETE FROM store_offers WHERE game_id = ?", [game_id])
        await client.execute("DELETE FROM games WHERE id = ?", [game_id])
        
        await client.close()
        return {"status": "success"}
    except Exception as e:
        await client.close()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# KOLEKCJA
# ==========================================

@app.get("/get_collection")
async def get_collection(user_id: int):
    client = get_db_client()
    
    res = await client.execute(
        "SELECT id, title, platform, release_date, date_added FROM collections WHERE user_id = ? ORDER BY date_added DESC",
        [user_id]
    )
    
    result = []
    for row in res.rows:
        col_id, title, platform, release_date, date_added = row
        result.append({
            "id": col_id,
            "title": title,
            "platform": platform,
            "release_date": release_date,
            "date_added": date_added
        })
        
    await client.close()
    return result


@app.post("/move_to_collection")
async def move_to_collection(data: dict):
    title = data.get("title")
    platform = data.get("platform")
    user_id = data.get("user_id")
    
    client = get_db_client()
    try:
        game_res = await client.execute(
            "SELECT id, release_date FROM games WHERE title = ? AND platform = ? AND user_id = ?",
            [title, platform, user_id]
        )
        
        if not game_res.rows:
            await client.close()
            raise HTTPException(status_code=404, detail="Gra nie została znaleziona.")
            
        game_id, release_date = game_res.rows[0]
        
        await client.execute(
            "INSERT INTO collections (user_id, title, platform, release_date) VALUES (?, ?, ?, ?)",
            [user_id, title, platform, release_date]
        )
        await client.execute("DELETE FROM store_offers WHERE game_id = ?", [game_id])
        await client.execute("DELETE FROM games WHERE id = ?", [game_id])
        
        await client.close()
        return {"status": "success"}
    except Exception as e:
        await client.close()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/delete_from_collection")
async def delete_from_collection(data: dict):
    col_id = data.get("id")
    user_id = data.get("user_id")
    
    client = get_db_client()
    try:
        await client.execute(
            "DELETE FROM collections WHERE id = ? AND user_id = ?",
            [col_id, user_id]
        )
        await client.close()
        return {"status": "success"}
    except Exception as e:
        await client.close()
        raise HTTPException(status_code=500, detail=str(e))

def parse_game_date(date_str: str):
    """Pomocnicza funkcja parsująca różne formaty dat z bazy."""
    if not date_str:
        return None
    try:
        if "." in date_str:
            parts = date_str.split(".")
            return datetime(int(parts[2]), int(parts[1]), int(parts[0])).date()
        elif "-" in date_str:
            parts = date_str.split("-")
            year, month = int(parts[0]), int(parts[1])
            day = int(parts[2]) if len(parts) > 2 else 1
            return datetime(year, month, day).date()
    except Exception:
        return None
    return None

@app.get("/cron/weekly_summary")
async def send_weekly_summary(user_id: int):
    # 1. Pobierz preordery użytkownika z bazy
    # (Zmień poniższe get_user_preorders(user_id) na swoją funkcję pobierającą dane z bazy!)
    preorders = await get_preorders(user_id) 

    # 2. Wyznacz zakres dat dla bieżącego tygodnia (Poniedziałek - Niedziela)
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    # 3. Filtruj premiery na ten tydzień
    this_week_games = []
    for game in preorders:
        g_date = parse_game_date(game.get("release_date"))
        if g_date and monday <= g_date <= sunday:
            this_week_games.append((g_date, game))

    # Sortuj gry chronologicznie
    this_week_games.sort(key=lambda x: x[0])

    # 4. Formatowanie wiadomości Telegram
    if not this_week_games:
        message = "📅 *Preorder Hub — Podsumowanie Tygodnia*\n\nW tym tygodniu brak premier. Portfel bezpieczny! 🎮"
    else:
        message = f"🚨 *PREMIERY W TYM TYGODNIU ({monday.strftime('%d.%m')} - {sunday.strftime('%d.%m')})* 🚨\n\n"
        for g_date, game in this_week_games:
            title = game.get("title")
            platform = game.get("platform", "N/A")
            offers = game.get("offers", [])
            
            # Szukamy najtańszej oferty oraz sklepu
            cheapest_price = 0
            cheapest_store = "Brak ofert"
            
            if offers:
                # Znajduje cały obiekt oferty z najniższą ceną
                cheapest_offer = min(offers, key=lambda o: o.get("price", float('inf')))
                cheapest_price = cheapest_offer.get("price", 0)
                # Obsługuje zarówno store_name, jak i store
                cheapest_store = cheapest_offer.get("store_name") or cheapest_offer.get("store") or "Nieznany sklep"

            message += f"🎮 *{title}*\n"
            message += f"📅 Premiera: `{g_date.strftime('%d.%m.%Y')}`\n"
            message += f"🕹️ Platforma: `{platform}`\n"
            message += f"💰 Najniższa cena: `{cheapest_price:.2f} zł` (*{cheapest_store}*)\n"
            
            # Jeśli jest numer zamówienia, dodaj go
            order_nums = [str(o.get("order_number") or o.get("orderNumber")) for o in offers if (o.get("order_number") or o.get("orderNumber"))]
            if order_nums:
                message += f"📦 Nr zamówienia: `{', '.join(order_nums)}`\n"
            
            message += "-----------------------------------\n"

    # 5. Wysyłka przez Telegram Bot API
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    response = requests.post(telegram_url, json=payload)
    if response.status_code != 200:
        # Pokażmy dokładny błąd, jaki zwraca nam Telegram!
        raise HTTPException(status_code=500, detail=f"Błąd Telegrama: {response.text}")

    return {"status": "success", "sent_games_count": len(this_week_games)}

@app.get("/ping")
def keep_alive():
    """Zwraca natychmiastową odpowiedź, aby powstrzymać serwer przed uśpieniem."""
    return {"status": "ok", "message": "Server is awake"}
