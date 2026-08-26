FROM python:3.10-slim

WORKDIR /app

# Najpierw kopiujemy tylko plik z zależnościami (żeby wykorzystać cache warstw)
COPY requirements.txt .

# Instalujemy biblioteki
RUN pip install --no-cache-dir -r requirements.txt

# Dopiero na końcu kopiujemy resztę kodu aplikacji
COPY . .

# Uruchomienie aplikacji (Render domyślnie przekazuje port w zmiennej PORT)
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-10000}