from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
import os

app = FastAPI()

# Konfiguracja CORS (dostosuj do swoich potrzeb)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Funkcja pomocnicza do łączenia z bazą (Dostosuj do swojego klienta Turso/libsql)
def get_db_client():
    # Tutaj wstawiasz swoją inicjalizację klienta bazy danych (np. libsql.connect lub client async)
    # Zależnie od tego, jak miałeś to wcześniej skonfigurowane:
    pass

# ==========================================
# AUTORYZACJA
# ==========================================

@app.post("/register")
async def register(data: dict):
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Podaj nazwę użytkownika i hasło.")
        
    hashed_password = pwd_context.hash(password)
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
    
    if not pwd_context.verify(password, password_hash):
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