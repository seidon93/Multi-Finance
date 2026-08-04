# Prototyp desktopového a webového GUI

Tato větev zavádí paralelní, ne-Streamlitové klienty nad stávající účetní logikou:

- `apps/desktop/app.py` — desktopový klient v PySide6/Qt.
- `apps/web/app.py` — webový klient ve FastAPI s responzivním HTML/CSS.
- `gui_common/dashboard.py` — společná, pouze pro čtení vrstva pro dashboard.

## Spuštění

```powershell
py -m pip install -r requirements-gui.txt
py -m uvicorn apps.web.app:app --reload --port 8000
```

Webové GUI bude na `http://localhost:8000`.

```powershell
py apps/desktop/app.py
```

Obě varianty načítají data z existujícího SQL Serveru nastaveného v `config/settings.py`. Pokud databáze není dostupná, aplikace se otevře v režimu náhledu s vysvětlením problému.
