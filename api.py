import json
import os
from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl
from typing import List
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware



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
    """
    Api przygotowane do dodania i posortowania nowego wpisu w kolejnosc daty premiery. Cena koniecznie z kropką!
    """
    existing_data = []

    if os.path.exists(file_name):
        with open (file_name,'r', encoding="utf-8") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []

    game_found = False

    for game in existing_data:
        if game["title"].lower() == incoming_data.title.lower() and game["platform"].lower() == incoming_data.platform.lower():
            game_found=True

            for new_offer in incoming_data.offers:
                offer_dict = new_offer.model_dump(mode='json')

                store_exists=False

                for existing_offer in game["offers"]:
                    if existing_offer["store_name"].lower() == new_offer.store_name.lower():
                        existing_offer["price"] = new_offer.price
                        store_exists=True
                        break
                if not store_exists:
                    game["offers"].append(offer_dict)
            break

    if not game_found:
        existing_data.append(incoming_data.model_dump(mode='json'))


    try:
        existing_data = sorted(
            existing_data,
            key=lambda x: datetime.strptime(x["release_date"], "%Y-%m-%d")
        )
    except ValueError as e:
        print(f"Błąd sortowania daty: {e}") # Teraz przynajmniej zobaczysz błąd w logach Rendera!
        pass

    with open(file_name,'w', encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)

    return {
        "message": "Preorder został przetworzony pomyślnie!",
        "database_state": existing_data
    }

@app.get("/get_preorders")
def get_preorders():
    existing_data = []

    with open(file_name,'r',encoding="utf-8") as f:
        existing_data = json.load(f)

    return existing_data

@app.delete("/delete")
def delete_preorder(game_to_delete: DeleteGameRequest):
    """
    Usuwa grę z pliku na podstawie tytułu i platformy.
    """
    existing_data = []

    if os.path.exists(file_name):
        with open(file_name, 'r', encoding="utf-8") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                return {"message": "Baza jest pusta."}

    # Sprawdzamy początkową długość listy
    initial_length = len(existing_data)

    # Filtrujemy listę - zostawiamy tylko te gry, które NIE PASUJĄ do przesłanych danych
    existing_data = [
        game for game in existing_data
        if not (game["title"].lower() == game_to_delete.title.lower() and 
                game["platform"].lower() == game_to_delete.platform.lower())
    ]

    # Jeśli długość się nie zmieniła, znaczy że nie znaleźliśmy takiej gry
    if len(existing_data) == initial_length:
        return {"message": "Nie znaleziono takiej gry do usunięcia."}, 404

    # Zapisujemy zaktualizowaną (krótszą) listę do pliku
    with open(file_name, 'w', encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)

    return {"message": "Preorder został usunięty pomyślnie!"}