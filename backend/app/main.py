from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db, seed_if_empty
from app.models import get_workspaces_with_items

app = FastAPI()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_if_empty()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/workspaces")
def list_workspaces() -> list[dict]:
    return get_workspaces_with_items()


# Must be mounted last: StaticFiles(html=True) claims "/" and everything under
# it, so declaring this before the routes above would shadow /health and /api.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
