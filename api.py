import json
import os
from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl
from typing import List
from datetime import datetime



class StoreOffer(BaseModel):
    store_name: str
    price: float
    url: HttpUrl

class Game(BaseModel):
    title: str
    platform: str
    release_date: str
    offers: List[StoreOffer]

app = FastAPI()

file_name = 'preorders.json'


@app.get("/")
def test():
    return "Hello World"

@app.post("/add")
def add_preorder(incoming_data: Game):

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
            key=lambda x: datetime.strptime(x["release_date"], "%d.%m.%Y")
        )
    except ValueError:
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