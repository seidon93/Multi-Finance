from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from gui_common.dashboard import load_dashboard

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Multi-Finance", version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "dashboard.html", {"dashboard": load_dashboard()})


@app.get("/api/dashboard")
def dashboard_api() -> dict:
    return load_dashboard()
