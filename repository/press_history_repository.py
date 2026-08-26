"""Pure DB access for press_history. No validation, no ID generation, no
caching here — that's services/press_history_service.py's job. This module
only knows SQL."""
from __future__ import annotations

from common.db import get_connection

LIST_COLUMNS = ["id", "press_history_id", "date", "media", "reporter_name", "type", "topic", "status", "tags"]
DETAIL_COLUMNS = LIST_COLUMNS + ["reporter_id", "question", "response", "created_at", "updated_at", "archived_at"]

WRITABLE_COLUMNS = [
    "date", "media", "reporter_id", "reporter_name", "type", "topic", "question", "response", "status", "tags",
]


def get_all(include_archived: bool = False) -> list[dict]:
    conn = get_connection()
    sql = f"SELECT {', '.join(LIST_COLUMNS)} FROM press_history"
    if not include_archived:
        sql += " WHERE archived_at IS NULL"
    sql += " ORDER BY date DESC, id DESC"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def get_by_id(press_history_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        f"SELECT {', '.join(DETAIL_COLUMNS)} FROM press_history WHERE press_history_id = ?",
        (press_history_id,),
    ).fetchone()
    return dict(row) if row else None


def get_last_id() -> str | None:
    conn = get_connection()
    row = conn.execute("SELECT press_history_id FROM press_history ORDER BY id DESC LIMIT 1").fetchone()
    return row["press_history_id"] if row else None


def create(fields: dict) -> int:
    conn = get_connection()
    cols = ["press_history_id", *WRITABLE_COLUMNS]
    conn.execute(
        f"INSERT INTO press_history ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        tuple(fields.get(c) for c in cols),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def update(press_history_id: str, fields: dict) -> None:
    conn = get_connection()
    cols = [c for c in WRITABLE_COLUMNS if c in fields]
    if not cols:
        return
    set_clause = ", ".join(f"{c} = ?" for c in cols)
    values = [fields[c] for c in cols]
    conn.execute(
        f"UPDATE press_history SET {set_clause}, updated_at = datetime('now') WHERE press_history_id = ?",
        (*values, press_history_id),
    )
    conn.commit()


def archive(press_history_id: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE press_history SET archived_at = datetime('now'), updated_at = datetime('now') WHERE press_history_id = ?",
        (press_history_id,),
    )
    conn.commit()


def count(include_archived: bool = False) -> int:
    conn = get_connection()
    sql = "SELECT COUNT(*) FROM press_history"
    if not include_archived:
        sql += " WHERE archived_at IS NULL"
    return conn.execute(sql).fetchone()[0]
