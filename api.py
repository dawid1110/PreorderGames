import os
import libsql_client
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware

# Inicjalizacja połączenia z Turso
url = os.getenv("TURSO_DATABASE_URL")
authToken = os.getenv("TURSO_AUTH_TOKEN")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Pozwala na zapytania z każdej strony (do testów idealne)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_client():
    return libsql_client.create_client(url=url, auth_token=authToken)

# Modele Pydantic dopasowane do struktury JSON wysyłanej z frontendu
class Offer(BaseModel):
    store_name: str
    price: float
    orderNumber: Optional[int] = None
    url: Optional[str] = None

class Game(BaseModel):
    title: str
    platform: str
    release_date: str
    offers: List[Offer]

class DeleteGameRequest(BaseModel):
    title: str
    platform: str


# ==========================================
# 1. POBIERANIE PREORDERÓW (GET)
# ==========================================
# ==========================================
# 1. POBIERANIE PREORDERÓW (GET)
# ==========================================
# ==========================================
# 1. POBIERANIE PREORDERÓW (GET)
# ==========================================
@app.get("/get_preorders")
async def get_preorders():
    client = get_db_client()
    user_id = 1  
    
    # DODANO await!
    games_res = await client.execute(
        "SELECT id, title, platform, release_date FROM games WHERE user_id = ?", 
        [user_id]
    )
    
    result = []
    for game_row in games_res.rows:
        game_id, title, platform, release_date = game_row
        
        # DODANO await!
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
                "order_number": order_number,
                "url": url
            })
            
        result.append({
            "title": title,
            "platform": platform,
            "release_date": release_date,
            "offers": offers
        })
        
    await client.close()  # DODANO await!
    return result


# ==========================================
# 2. DODAWANIE / AKTUALIZACJA PREORDERU (POST)
# ==========================================
@app.post("/add")
async def add_preorder(incoming_data: Game):
    client = get_db_client()
    user_id = 1  
    
    # DODANO await!
    existing_game = await client.execute(
        "SELECT id FROM games WHERE user_id = ? AND LOWER(title) = ? AND LOWER(platform) = ?",
        [user_id, incoming_data.title.lower(), incoming_data.platform.lower()]
    )
    
    if len(existing_game.rows) > 0:
        game_id = existing_game.rows[0][0]
        for new_offer in incoming_data.offers:
            existing_offer = await client.execute(
                "SELECT id FROM store_offers WHERE game_id = ? AND LOWER(store_name) = ?",
                [game_id, new_offer.store_name.lower()]
            )
            
            if len(existing_offer.rows) > 0:
                await client.execute(
                    "UPDATE store_offers SET price = ?, order_number = ?, url = ? WHERE id = ?",
                    [new_offer.price, new_offer.orderNumber, str(new_offer.url) if new_offer.url else None, existing_offer.rows[0][0]]
                )
            else:
                await client.execute(
                    "INSERT INTO store_offers (game_id, store_name, price, order_number, url) VALUES (?, ?, ?, ?, ?)",
                    [game_id, new_offer.store_name, new_offer.price, new_offer.orderNumber, str(new_offer.url) if new_offer.url else None]
                )
    else:
        res = await client.execute(
            "INSERT INTO games (user_id, title, platform, release_date) VALUES (?, ?, ?, ?)",
            [user_id, incoming_data.title, incoming_data.platform, incoming_data.release_date]
        )
        game_id = res.last_insert_rowid
        
        for new_offer in incoming_data.offers:
            await client.execute(
                "INSERT INTO store_offers (game_id, store_name, price, order_number, url) VALUES (?, ?, ?, ?, ?)",
                [game_id, new_offer.store_name, new_offer.price, new_offer.orderNumber, str(new_offer.url) if new_offer.url else None]
            )
            
    await client.close()
    return {"message": "Preorder zapisany w bazie pomyślnie!"}


# ==========================================
# 3. USUWANIE PREORDERU (DELETE)
# ==========================================
@app.delete("/delete")
async def delete_preorder(game_to_delete: DeleteGameRequest):
    client = get_db_client()
    user_id = 1
    
    # DODANO await!
    await client.execute(
        "DELETE FROM games WHERE user_id = ? AND LOWER(title) = ? AND LOWER(platform) = ?",
        [user_id, game_to_delete.title.lower(), game_to_delete.platform.lower()]
    )
    
    await client.close()
    return {"message": "Preorder został usunięty z bazy!"}