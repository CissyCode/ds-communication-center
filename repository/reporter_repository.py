"""Pure DB access for reporters — no business rules here (see services/reporter_service.py)."""
from __future__ import annotations

from common.db import get_connection

COLUMNS = [
    "id", "reporter_id", "name", "media", "department", "position",
    "email", "phone", "status", "topics", "last_contact", "notes",
]


def get_all(include_archived: bool = False) -> list[dict]:
    conn = get_connection()
    sql = f"SELECT {', '.join(COLUMNS)} FROM reporters"
    if not include_archived:
        sql += " WHERE archived_at IS NULL"
    sql += " ORDER BY name"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def get_by_id(reporter_pk: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(f"SELECT {', '.join(COLUMNS)} FROM reporters WHERE id = ?", (reporter_pk,)).fetchone()
    return dict(row) if row else None


def get_by_name(name: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(f"SELECT {', '.join(COLUMNS)} FROM reporters WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def create(fields: dict) -> int:
    conn = get_connection()
    cols = ["reporter_id", "name", "media", "department", "position", "email", "phone", "status", "topics", "last_contact", "notes"]
    conn.execute(
        f"INSERT INTO reporters ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        tuple(fields.get(c) for c in cols),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def count(include_archived: bool = False) -> int:
    conn = get_connection()
    sql = "SELECT COUNT(*) FROM reporters"
    if not include_archived:
        sql += " WHERE archived_at IS NULL"
    return conn.execute(sql).fetchone()[0]
