import logging

# app loggers are silent under uvicorn without this
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

from app.db import fixup_legacy_seed, init_db, seed_if_empty
from app.models import get_workspaces_with_items
from app.ws.agent import agent_ws
from app.ws.client import client_ws

# Load before anything reads os.environ (agent.py checks AGENT_TOKEN on
# each connection, not just at import time, but this keeps env setup in
# one place at process start).
load_dotenv()

app = FastAPI()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_if_empty()
    fixup_legacy_seed()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/workspaces")
def list_workspaces() -> list[dict]:
    return get_workspaces_with_items()


@app.websocket("/ws/agent")
async def ws_agent(ws: WebSocket) -> None:
    await agent_ws(ws)


@app.websocket("/ws/client")
async def ws_client(ws: WebSocket) -> None:
    await client_ws(ws)


# Starlette matches routes in registration order, so a catch-all mount at "/"
# must always be registered last. StaticFiles asserts scope["type"] == "http"
# and returns 500 for anything else, so mounting it earlier than the
# websocket routes above would swallow /ws/agent and /ws/client (and shadow
# /health and /api). Keep this mount at the bottom of the file.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
