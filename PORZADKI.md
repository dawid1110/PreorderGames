# Opcjonalne usunięcie pozostałości przy rozpakowaniu na stare repozytorium

Nowy ZIP nie zawiera poniższych starych plików. Nie są potrzebne do działania nowego frontendu. Jeżeli pozostały w Twoim katalogu głównym, możesz je później usunąć z Git. **Nie usuwaj tych samych plików w `v3/`.**

```
app.js
config.js
style.css
crimson-hero.webp
crimson.webp
northern.webp
orion.webp
download
api.cpython-311.pyc
api.cpython-312.pyc
__pycache__/
```

Nie musisz tego robić, aby nowy interfejs się uruchomił: starsze strony aplikacji zostały zastąpione przekierowaniami (index.html jest teraz stroną powitalną), a właściwe style i skrypty ładuje `v3/index.html`. Nie usuwaj `api_v2.py`, katalogu `v3/`, konfiguracji, głównego `manifest.json` ani `sw.js` bez zaplanowania migracji starych instalacji PWA.
