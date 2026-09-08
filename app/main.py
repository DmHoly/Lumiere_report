"""
app/main.py — API + front-end du Report Builder.

Lancement :
    uvicorn app.main:app --reload --port 8420

UI : http://localhost:8420/
API : http://localhost:8420/api/...
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .routers import blocks, datasets, reports

app = FastAPI(title="Lumière Report Builder")

app.include_router(datasets.router)
app.include_router(blocks.router)
app.include_router(reports.router)

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR, html=True), name="static")


@app.get("/")
def index():
    return RedirectResponse(url="/static/index.html")
