from typing import Optional

from pydantic import BaseModel

from app.db import get_connection


class Item(BaseModel):
    id: int
    workspace_id: int
    row: int
    col: int
    width: int = 1
    height: int = 1
    label: str
    icon: Optional[str] = None
    color: str = "#2a2f38"
    kind: str
    type: str
    target: str = "windows"
    params: str = "{}"
    state_key: Optional[str] = None
    press_count: int = 0
    last_pressed: Optional[str] = None


class Workspace(BaseModel):
    id: int
    name: str
    position: int
    grid_cols: int = 3
    grid_rows: int = 5
    items: list[Item] = []


def get_workspaces_with_items() -> list[dict]:
    conn = get_connection()
    try:
        workspace_rows = conn.execute(
            "SELECT * FROM workspace ORDER BY position"
        ).fetchall()
        item_rows = conn.execute(
            "SELECT * FROM item ORDER BY workspace_id, row, col"
        ).fetchall()
    finally:
        conn.close()

    items_by_workspace: dict[int, list[dict]] = {}
    for item_row in item_rows:
        items_by_workspace.setdefault(item_row["workspace_id"], []).append(dict(item_row))

    return [
        {**dict(workspace_row), "items": items_by_workspace.get(workspace_row["id"], [])}
        for workspace_row in workspace_rows
    ]


def get_item(item_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM item WHERE id = ?", (item_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def bump_press_count(item_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE item SET press_count = press_count + 1, last_pressed = datetime('now') WHERE id = ?",
            (item_id,),
        )
        conn.commit()
    finally:
        conn.close()
