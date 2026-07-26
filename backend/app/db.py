import sqlite3
from pathlib import Path

DB_PATH = Path("/app/data/controlhub.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # sqlite3 defaults FK enforcement to off per-connection; item.workspace_id's
    # ON DELETE CASCADE only fires if this is set on every connection that writes.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        # WAL lets the UI (reader) and agent actions (writer) hit the db at the
        # same time instead of blocking each other behind sqlite's default lock.
        conn.execute("PRAGMA journal_mode=WAL")
        # NORMAL only fsyncs at WAL checkpoints, not every commit; safe under WAL
        # (survives app crashes) and far faster than FULL for a local single-user app.
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workspace (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                position INTEGER NOT NULL,
                grid_cols INTEGER NOT NULL DEFAULT 3,
                grid_rows INTEGER NOT NULL DEFAULT 5
            );

            CREATE TABLE IF NOT EXISTS item (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL REFERENCES workspace(id) ON DELETE CASCADE,
                row INTEGER NOT NULL,
                col INTEGER NOT NULL,
                width INTEGER DEFAULT 1,
                height INTEGER DEFAULT 1,
                label TEXT NOT NULL,
                icon TEXT,
                color TEXT DEFAULT '#2a2f38',
                kind TEXT NOT NULL,
                type TEXT NOT NULL,
                target TEXT NOT NULL DEFAULT 'windows',
                params TEXT NOT NULL DEFAULT '{}',
                state_key TEXT,
                press_count INTEGER NOT NULL DEFAULT 0,
                last_pressed TEXT
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_if_empty() -> None:
    conn = get_connection()
    try:
        (workspace_count,) = conn.execute("SELECT COUNT(*) FROM workspace").fetchone()
        if workspace_count > 0:
            return

        cur = conn.execute(
            "INSERT INTO workspace (name, position, grid_cols, grid_rows) VALUES (?, ?, ?, ?)",
            ("Home", 0, 3, 5),
        )
        workspace_id = cur.lastrowid

        # row, col, label, icon, color, kind, type -- just enough to render a grid on day 1
        fake_items = [
            (0, 0, "Lights", "lightbulb", "#f2c14e", "action", "toggle"),
            (0, 1, "Spotify", "music", "#1db954", "action", "launch"),
            (0, 2, "Sleep PC", "moon", "#4e6ef2", "action", "run"),
            (1, 0, "Terminal", "terminal", "#2a2f38", "action", "launch"),
            (1, 1, "Camera", "camera", "#e0575b", "action", "toggle"),
            (1, 2, "Volume", "speaker", "#8e5ff5", "action", "run"),
        ]
        conn.executemany(
            """
            INSERT INTO item (workspace_id, row, col, label, icon, color, kind, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(workspace_id, *item) for item in fake_items],
        )
        conn.commit()
    finally:
        conn.close()
