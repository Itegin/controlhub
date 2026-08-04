import logging
import os
import sqlite3

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.db import get_connection
from app.ws.hub import hub

logger = logging.getLogger("controlhub.api")

router = APIRouter()


class WorkspaceCreate(BaseModel):
    name: str
    grid_cols: int = 3
    grid_rows: int = 5


def _check_agent_token(x_agent_token: str | None) -> None:
    # Same shared-secret gate as backend/app/api/items.py, applied here too:
    # this surface controls what workspaces exist, which drives what the
    # agent will execute, so it gets the same gate as the item catalog.
    expected_token = os.environ.get("AGENT_TOKEN")
    # "not expected_token" guards against AGENT_TOKEN being unset entirely:
    # without it, a missing env var (None) would equal a missing header
    # (None) and silently let an unauthenticated request through.
    if not expected_token or x_agent_token != expected_token:
        raise HTTPException(status_code=401, detail="missing or invalid X-Agent-Token")


@router.post("/api/workspaces")
async def create_workspace(workspace: WorkspaceCreate, x_agent_token: str | None = Header(None)) -> dict:
    _check_agent_token(x_agent_token)

    conn = get_connection()
    try:
        try:
            cur = conn.execute(
                """
                INSERT INTO workspace (name, position, grid_cols, grid_rows)
                VALUES (
                    ?,
                    (SELECT COALESCE(MAX(position), -1) + 1 FROM workspace),
                    ?, ?
                )
                """,
                (workspace.name, workspace.grid_cols, workspace.grid_rows),
            )
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=400, detail=f"invalid workspace: {e}")
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, name, position, grid_cols, grid_rows FROM workspace WHERE id = ?",
            (new_id,),
        ).fetchone()
    finally:
        conn.close()

    logger.info("Workspace created: id=%s name=%s", new_id, workspace.name)
    await hub.broadcast_to_clients({"type": "workspace_update"})
    return dict(row)
