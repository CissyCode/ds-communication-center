"""Pure DB access for press_releases. Foundation only this phase — no view
calls this yet (보도자료 leaf still reads the CSV/schedule-derived log)."""
from __future__ import annotations

from common.db import get_connection

COLUMNS = ["id", "press_release_id", "title", "date", "time_label", "status", "source_type", "source_id"]


def get_all(include_archived: bool = False) -> list[dict]:
    conn = get_connection()
    sql = f"SELECT {', '.join(COLUMNS)} FROM press_releases"
    if not include_archived:
        sql += " WHERE archived_at IS NULL"
    sql += " ORDER BY date"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def get_by_id(press_release_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(f"SELECT {', '.join(COLUMNS)} FROM press_releases WHERE press_release_id = ?", (press_release_id,)).fetchone()
    return dict(row) if row else None


def count(include_archived: bool = False) -> int:
    conn = get_connection()
    sql = "SELECT COUNT(*) FROM press_releases"
    if not include_archived:
        sql += " WHERE archived_at IS NULL"
    return conn.execute(sql).fetchone()[0]
