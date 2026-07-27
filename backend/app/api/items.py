import json
import logging
import os
import sqlite3

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.db import get_connection
from app.models import get_item
from app.ws.hub import hub

logger = logging.getLogger("controlhub.api")

router = APIRouter()


class ItemCreate(BaseModel):
    workspace_id: int
    row: int
    col: int
    width: int = 1
    height: int = 1
    label: str
    icon: str | None = None
    color: str = "#2a2f38"
    kind: str
    type: str
    target: str = "windows"
    params: str = "{}"
    state_key: str | None = None


class ItemUpdate(BaseModel):
    workspace_id: int | None = None
    row: int | None = None
    col: int | None = None
    width: int | None = None
    height: int | None = None
    label: str | None = None
    icon: str | None = None
    color: str | None = None
    kind: str | None = None
    type: str | None = None
    target: str | None = None
    params: str | None = None
    state_key: str | None = None


def _check_agent_token(x_agent_token: str | None) -> None:
    # Same shared-secret gate as backend/app/api/screenshot.py, applied to
    # every endpoint here: this surface controls what commands the agent
    # will execute, which is more sensitive than a screenshot upload, not
    # less. One helper, not four copies of the check, so a future fix
    # only has to happen in one place.
    expected_token = os.environ.get("AGENT_TOKEN")
    # "not expected_token" guards against AGENT_TOKEN being unset entirely:
    # without it, a missing env var (None) would equal a missing header
    # (None) and silently let an unauthenticated request through.
    if not expected_token or x_agent_token != expected_token:
        raise HTTPException(status_code=401, detail="missing or invalid X-Agent-Token")


def _validate_params_json(params: str) -> None:
    # A malformed params string would crash every future handler that
    # tries to json.loads() it (backend _handle_execute, frontend
    # fetchWorkspaces) -- reject it here, at the one place items are
    # actually written, rather than let it become a landmine for whoever
    # reads this row next.
    try:
        json.loads(params)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="params must be a valid JSON string")


@router.get("/api/items/{item_id}")
def get_item_endpoint(item_id: int, x_agent_token: str | None = Header(None)) -> dict:
    _check_agent_token(x_agent_token)
    item = get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return item


@router.post("/api/items")
async def create_item(item: ItemCreate, x_agent_token: str | None = Header(None)) -> dict:
    _check_agent_token(x_agent_token)
    _validate_params_json(item.params)

    conn = get_connection()
    try:
        try:
            cur = conn.execute(
                """
                INSERT INTO item
                    (workspace_id, row, col, width, height, label, icon, color, kind, type, target, params, state_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.workspace_id, item.row, item.col, item.width, item.height,
                    item.label, item.icon, item.color, item.kind, item.type,
                    item.target, item.params, item.state_key,
                ),
            )
        except sqlite3.IntegrityError as e:
            # Most likely cause: workspace_id doesn't reference a real
            # workspace row (foreign_keys = ON, see app.db.get_connection).
            raise HTTPException(status_code=400, detail=f"invalid item: {e}")
        conn.commit()
        new_id = cur.lastrowid
    finally:
        conn.close()

    logger.info("Item created: id=%s label=%s", new_id, item.label)
    await hub.broadcast_to_clients({"type": "workspace_update"})
    return get_item(new_id)


@router.put("/api/items/{item_id}")
async def update_item(item_id: int, item: ItemUpdate, x_agent_token: str | None = Header(None)) -> dict:
    _check_agent_token(x_agent_token)
    if get_item(item_id) is None:
        raise HTTPException(status_code=404, detail="item not found")

    # Only fields actually present in the request body -- exclude_unset
    # distinguishes "field omitted" from "field explicitly set to null"
    # (e.g. clearing icon or state_key), which a plain None-check can't.
    fields = item.model_dump(exclude_unset=True)
    if "params" in fields:
        _validate_params_json(fields["params"])

    if not fields:
        raise HTTPException(status_code=400, detail="no fields to update")

    # Column names come only from ItemUpdate's own declared fields, never
    # from arbitrary request data, so building the SET clause from these
    # keys is not a SQL-injection surface; values are still parameterized.
    set_clause = ", ".join(f"{column} = ?" for column in fields)
    values = [*fields.values(), item_id]

    conn = get_connection()
    try:
        try:
            conn.execute(f"UPDATE item SET {set_clause} WHERE id = ?", values)
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=400, detail=f"invalid item: {e}")
        conn.commit()
    finally:
        conn.close()

    logger.info("Item updated: id=%s fields=%s", item_id, list(fields))
    await hub.broadcast_to_clients({"type": "workspace_update"})
    return get_item(item_id)


@router.delete("/api/items/{item_id}")
async def delete_item(item_id: int, x_agent_token: str | None = Header(None)) -> dict:
    _check_agent_token(x_agent_token)
    if get_item(item_id) is None:
        raise HTTPException(status_code=404, detail="item not found")

    conn = get_connection()
    try:
        conn.execute("DELETE FROM item WHERE id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()

    logger.info("Item deleted: id=%s", item_id)
    await hub.broadcast_to_clients({"type": "workspace_update"})
    return {"status": "ok"}
