import json
import os
from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl
from typing import List
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import libsql_client


url = os.getenv("TURSO_DATABASE_URL")
authToken = os.getenv("TURSO_AUTH_TOKEN")

def get_db_client():
    return libsql_client.create_client(url=url, auth_token=authToken)


class StoreOffer(BaseModel):
    store_name: str
    price: float
    orderNumber: int
    url: HttpUrl

class Game(BaseModel):
    title: str
    platform: str
    release_date: str
    offers: List[StoreOffer]

class DeleteGameRequest(BaseModel):
    title: str
    platform: str

app = FastAPI()

origins = [
    "*",  # Na czas testów zezwalamy na połączenia z każdego źródła (w tym z plików lokalnych file://)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

file_name = 'preorders.json'


@app.get("/")
def test():
    """Testowe uruchomienie api czy poprawnie zwroci ten tekst"""
    return "Hello World"

@app.post("/add")
def add_preorder(incoming_data: Game):
    client = get_db_client()
    
    # Na razie na sztywno user_id = 1 (gdy dorobisz JWT, podstawimy tu ID z tokena!)
    user_id = 1 
    
    # Sprawdzamy czy gra o takim tytule i platformie już istnieje
    existing_game = client.execute(
        "SELECT id FROM games WHERE user_id = ? AND LOWER(title) = ? AND LOWER(platform) = ?",
        [user_id, incoming_data.title.lower(), incoming_data.platform.lower()]
    )
    
    if len(existing_game.rows) > 0:
        game_id = existing_game.rows[0][0]
        
        # Gra istnieje – aktualizujemy/dodajemy oferty
        for new_offer in incoming_data.offers:
            existing_offer = client.execute(
                "SELECT id FROM store_offers WHERE game_id = ? AND LOWER(store_name) = ?",
                [game_id, new_offer.store_name.lower()]
            )
            
            if len(existing_offer.rows) > 0:
                # Aktualizujemy istniejący sklep
                client.execute(
                    "UPDATE store_offers SET price = ?, order_number = ?, url = ? WHERE id = ?",
                    [new_offer.price, new_offer.orderNumber, str(new_offer.url), existing_offer.rows[0][0]]
                )
            else:
                # Dodajemy nowy sklep do istniejącej gry
                client.execute(
                    "INSERT INTO store_offers (game_id, store_name, price, order_number, url) VALUES (?, ?, ?, ?, ?)",
                    [game_id, new_offer.store_name, new_offer.price, new_offer.orderNumber, str(new_offer.url)]
                )
    else:
        # Nowa gra – wstawiamy do tabeli games
        res = client.execute(
            "INSERT INTO games (user_id, title, platform, release_date) VALUES (?, ?, ?, ?)",
            [user_id, incoming_data.title, incoming_data.platform, incoming_data.release_date]
        )
        game_id = res.last_insert_rowid
        
        # Wstawiamy oferty do store_offers
        for new_offer in incoming_data.offers:
            client.execute(
                "INSERT INTO store_offers (game_id, store_name, price, order_number, url) VALUES (?, ?, ?, ?, ?)",
                [game_id, new_offer.store_name, new_offer.price, new_offer.orderNumber, str(new_offer.url)]
            )
            
    client.close()
    return {"message": "Preorder został zapisany w Turso pomyślnie!"}

@app.get("/get_preorders")
def get_preorders():
    client = get_db_client()
    
    # 1. Pobieramy wszystkie gry z tabeli games
    games_res = client.execute("SELECT id, title, platform, release_date FROM games")
    
    result = []
    for game_row in games_res.rows:
        game_id, title, platform, release_date = game_row
        
        # 2. Dla każdej gry pobieramy jej oferty ze store_offers
        offers_res = client.execute(
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
            
        # 3. Składamy to w strukturę, którą frontend już zna i uwielbia
        result.append({
            "title": title,
            "platform": platform,
            "release_date": release_date,
            "offers": offers
        })
        
    client.close()
    return result

@app.delete("/delete")
def delete_preorder(game_to_delete: DeleteGameRequest):
    client = get_db_client()
    user_id = 1  # Docelowo z JWT
    
    # Usuwamy grę z bazy (oferty usuną się same dzięki kaskadzie)
    client.execute(
        "DELETE FROM games WHERE user_id = ? AND LOWER(title) = ? AND LOWER(platform) = ?",
        [user_id, game_to_delete.title.lower(), game_to_delete.platform.lower()]
    )
    
    client.close()
    return {"message": "Preorder został usunięty z Turso!"}