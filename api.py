from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
import requests
from datetime import datetime, timedelta
import hashlib
import secrets
import os
import libsql_client
import jwt

app = FastAPI()

TELEGRAM_BOT_TOKEN = "8610360413:AAFpmUCUsQ39EB9lrfno_8T7-LxMWF2bhj4"
TELEGRAM_CHAT_ID = "8457539262"

# Konfiguracja CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://preordergames.dwiad1110.workers.dev", 
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# KONFIGURACJA OAUTH2 & JWT
# ==========================================
SECRET_KEY = "zmien_mnie_na_bardzo_trudny_ciag_znakow_w_produkcji"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # Token ważny 7 dni

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Nieprawidłowy token")
        return int(user_id)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Nieprawidłowy lub wygasły token")

# ==========================================
# BAZA DANYCH I HASHOWANIE
# ==========================================
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
        return {"status": "success", "message": "Rejestracja udana!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Użytkownik o takiej nazwie już istnieje.")
    finally:
        await client.close()

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # OAuth2 wymusza przesyłanie loginu/hasła jako x-www-form-urlencoded (wypełniane automatycznie przez formularz)
    username = form_data.username.strip()
    password = form_data.password.strip()
    
    client = get_db_client()
    try:
        res = await client.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            [username]
        )
        
        if not res.rows:
            raise HTTPException(status_code=401, detail="Nieprawidłowa nazwa użytkownika lub hasło.")
            
        user_id, password_hash = res.rows[0]
        
        if not verify_password(password, password_hash):
            raise HTTPException(status_code=401, detail="Nieprawidłowa nazwa użytkownika lub hasło.")
            
        # Generowanie bezpiecznego tokena na podstawie ID użytkownika
        access_token = create_access_token(data={"sub": str(user_id)})
        
        # Zwracana struktura wymuszona przez specyfikację OAuth2
        return {"access_token": access_token, "token_type": "bearer", "user_id": user_id, "username": username}
    finally:
        await client.close()

# ==========================================
# PREORDERS & OFERTY
# ==========================================

@app.get("/get_preorders")
async def get_preorders(current_user: int = Depends(get_current_user)):
    # Pobieramy gry wyłącznie dla uwierzytelnionego w tokenie użytkownika (current_user)
    client = get_db_client()
    
    try:
        games_res = await client.execute(
            "SELECT id, title, platform, release_date FROM games WHERE user_id = ?", 
            [current_user]
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
                
        return list(games_dict.values())
    finally:
        await client.close()

@app.post("/add")
async def add_preorder(data: dict, current_user: int = Depends(get_current_user)):
    title = data.get("title")
    platform = data.get("platform")
    release_date = data.get("release_date")
    offers = data.get("offers", [])
    
    if not title or not platform:
        raise HTTPException(status_code=400, detail="Brak wymaganych danych.")
        
    client = get_db_client()
    
    try:
        game_res = await client.execute(
            "INSERT INTO games (user_id, title, platform, release_date) VALUES (?, ?, ?, ?)",
            [current_user, title, platform, release_date]
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
                
        return {"status": "success", "message": "Preorder dodany pomyślnie!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()

@app.delete("/delete")
async def delete_game(data: dict, current_user: int = Depends(get_current_user)):
    title = data.get("title")
    platform = data.get("platform")
    
    client = get_db_client()
    try:
        game_res = await client.execute(
            "SELECT id FROM games WHERE title = ? AND platform = ? AND user_id = ?",
            [title, platform, current_user]
        )
        if not game_res.rows:
            raise HTTPException(status_code=404, detail="Gra nie znaleziona.")
            
        game_id = game_res.rows[0][0]
        await client.execute("DELETE FROM store_offers WHERE game_id = ?", [game_id])
        await client.execute("DELETE FROM games WHERE id = ?", [game_id])
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()

# ==========================================
# KOLEKCJA
# ==========================================

@app.get("/get_collection")
async def get_collection(current_user: int = Depends(get_current_user)):
    client = get_db_client()
    try:
        res = await client.execute(
            "SELECT id, title, platform, release_date, date_added FROM collections WHERE user_id = ? ORDER BY date_added DESC",
            [current_user]
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
            
        return result
    finally:
        await client.close()

@app.post("/move_to_collection")
async def move_to_collection(data: dict, current_user: int = Depends(get_current_user)):
    title = data.get("title")
    platform = data.get("platform")
    
    client = get_db_client()
    try:
        game_res = await client.execute(
            "SELECT id, release_date FROM games WHERE title = ? AND platform = ? AND user_id = ?",
            [title, platform, current_user]
        )
        
        if not game_res.rows:
            raise HTTPException(status_code=404, detail="Gra nie została znaleziona.")
            
        game_id, release_date = game_res.rows[0]
        
        await client.execute(
            "INSERT INTO collections (user_id, title, platform, release_date) VALUES (?, ?, ?, ?)",
            [current_user, title, platform, release_date]
        )
        await client.execute("DELETE FROM store_offers WHERE game_id = ?", [game_id])
        await client.execute("DELETE FROM games WHERE id = ?", [game_id])
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()

@app.delete("/delete_from_collection")
async def delete_from_collection(data: dict, current_user: int = Depends(get_current_user)):
    col_id = data.get("id")
    
    client = get_db_client()
    try:
        await client.execute(
            "DELETE FROM collections WHERE id = ? AND user_id = ?",
            [col_id, current_user]
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await client.close()

def parse_game_date(date_str: str):
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

# Ten endpoint zazwyczaj wywoływany jest z zewnątrz przez Cron, 
# więc pozostaje bez Depends(get_current_user), ale wymaga jawnego podania user_id
@app.get("/cron/weekly_summary")
async def send_weekly_summary(user_id: int):
    # Trzeba zasymulować zapytanie z bazy, ponieważ get_preorders wymaga teraz tokena
    client = get_db_client()
    try:
        games_res = await client.execute("SELECT title, platform, release_date FROM games WHERE user_id = ?", [user_id])
        
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)

        this_week_games = []
        for row in games_res.rows:
            title, platform, release_date = row
            g_date = parse_game_date(release_date)
            if g_date and monday <= g_date <= sunday:
                this_week_games.append((g_date, {"title": title, "platform": platform}))

        this_week_games.sort(key=lambda x: x[0])

        if not this_week_games:
            message = "📅 *Preorder Hub — Podsumowanie Tygodnia*\n\nW tym tygodniu brak premier. Portfel bezpieczny! 🎮"
        else:
            message = f"🚨 *PREMIERY W TYM TYGODNIU ({monday.strftime('%d.%m')} - {sunday.strftime('%d.%m')})* 🚨\n\n"
            for g_date, game in this_week_games:
                message += f"🎮 *{game['title']}*\n"
                message += f"📅 Premiera: `{g_date.strftime('%d.%m.%Y')}`\n"
                message += f"🕹️ Platforma: `{game['platform']}`\n"
                message += "-----------------------------------\n"

        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        response = requests.post(telegram_url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        })
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Błąd wysyłania wiadomości na Telegram")

        return {"status": "success", "sent_games_count": len(this_week_games)}
    finally:
        await client.close()