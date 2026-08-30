import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import libsql_client

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
client = libsql_client.create_client(url=TURSO_URL, auth_token=TURSO_TOKEN)

# --- MODELE DANYCH ---
class UserLogin(BaseModel):
    username: str
    password: str

class OfferItem(BaseModel):
    store_name: str
    price: float
    order_number: Optional[str] = None
    url: Optional[str] = None

class PreorderData(BaseModel):
    user_id: int
    title: str
    platform: str
    release_date: str
    offers: List[OfferItem]

class DeleteData(BaseModel):
    user_id: int
    title: str
    platform: str

class DeleteCollectionData(BaseModel):
    user_id: int
    id: int

class UpdateBudget(BaseModel):
    user_id: int
    title: str
    platform: str
    in_budget: bool

# --- ENDPOINTY ---

@app.get("/ping")
def keep_alive():
    return {"status": "ok", "message": "Server is awake"}

@app.post("/login")
async def login(data: UserLogin):
    result = await client.execute(
        "SELECT id, username FROM users WHERE username = ? AND password_hash = ?", 
        [data.username, data.password]
    )
    if not result.rows:
        raise HTTPException(status_code=401, detail="Nieprawidłowy login lub hasło")
    row = result.rows[0]
    return {"user_id": row[0], "username": row[1]}

@app.post("/register")
async def register(data: UserLogin):
    try:
        await client.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)", 
            [data.username, data.password]
        )
        return {"status": "success"}
    except Exception:
        raise HTTPException(status_code=400, detail="Użytkownik o tej nazwie już istnieje")

@app.post("/add")
async def add_preorder(data: PreorderData):
    result = await client.execute(
        "INSERT INTO games (user_id, title, platform, release_date, in_budget) VALUES (?, ?, ?, ?, 1) RETURNING id",
        [data.user_id, data.title, data.platform, data.release_date]
    )
    game_id = result.rows[0][0]

    for offer in data.offers:
        await client.execute(
            "INSERT INTO store_offers (game_id, store_name, price, order_number, url) VALUES (?, ?, ?, ?, ?)",
            [game_id, offer.store_name, offer.price, offer.order_number, offer.url]
        )
    return {"status": "success"}

@app.get("/get_preorders")
async def get_preorders(user_id: int):
    games_result = await client.execute(
        "SELECT id, title, platform, release_date, in_budget FROM games WHERE user_id = ?",
        [user_id]
    )
    
    games = []
    for row in games_result.rows:
        game_id = row[0]
        offers_result = await client.execute(
            "SELECT store_name, price, order_number, url FROM store_offers WHERE game_id = ?",
            [game_id]
        )
        
        offers = []
        for o_row in offers_result.rows:
            offers.append({
                "store_name": o_row[0],
                "price": o_row[1],
                "order_number": o_row[2],
                "url": o_row[3]
            })
            
        games.append({
            "id": game_id,
            "title": row[1],
            "platform": row[2],
            "release_date": row[3],
            "in_budget": bool(row[4]) if len(row) > 4 and row[4] is not None else True,
            "offers": offers
        })
        
    return games

@app.post("/update_budget")
async def update_budget(data: UpdateBudget):
    in_budget_int = 1 if data.in_budget else 0
    try:
        await client.execute(
            "UPDATE games SET in_budget = ? WHERE user_id = ? AND title = ? AND platform = ?",
            [in_budget_int, data.user_id, data.title, data.platform]
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete")
async def delete_preorder(data: DeleteData):
    await client.execute(
        "DELETE FROM games WHERE user_id = ? AND title = ? AND platform = ?",
        [data.user_id, data.title, data.platform]
    )
    return {"status": "success"}

@app.post("/move_to_collection")
async def move_to_collection(data: DeleteData):
    result = await client.execute(
        "SELECT release_date FROM games WHERE user_id = ? AND title = ? AND platform = ?",
        [data.user_id, data.title, data.platform]
    )
    if not result.rows:
        raise HTTPException(status_code=404, detail="Nie znaleziono gry")
        
    release_date = result.rows[0][0]
    
    await client.execute(
        "INSERT INTO collections (user_id, title, platform, release_date, date_added) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
        [data.user_id, data.title, data.platform, release_date]
    )
    await client.execute(
        "DELETE FROM games WHERE user_id = ? AND title = ? AND platform = ?",
        [data.user_id, data.title, data.platform]
    )
    return {"status": "success"}

@app.get("/get_collection")
async def get_collection(user_id: int):
    result = await client.execute(
        "SELECT id, title, platform, release_date, date_added FROM collections WHERE user_id = ? ORDER BY date_added DESC",
        [user_id]
    )
    
    collection = []
    for row in result.rows:
        collection.append({
            "id": row[0],
            "title": row[1],
            "platform": row[2],
            "release_date": row[3],
            "date_added": row[4]
        })
    return collection

@app.delete("/delete_from_collection")
async def delete_from_collection(data: DeleteCollectionData):
    await client.execute(
        "DELETE FROM collections WHERE id = ? AND user_id = ?",
        [data.id, data.user_id]
    )
    return {"status": "success"}