"""Pure DB access for issues. Foundation only this phase — no view calls
this yet (이슈 관리 leaf still reads the CSV-derived watchlist)."""
from __future__ import annotations

from common.db import get_connection

COLUMNS = ["id", "issue_id", "title", "detail", "source", "severity", "status", "owner", "started_at", "resolved_at"]


def get_all(include_archived: bool = False) -> list[dict]:
    conn = get_connection()
    sql = f"SELECT {', '.join(COLUMNS)} FROM issues"
    if not include_archived:
        sql += " WHERE archived_at IS NULL"
    sql += " ORDER BY started_at DESC"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def get_by_id(issue_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(f"SELECT {', '.join(COLUMNS)} FROM issues WHERE issue_id = ?", (issue_id,)).fetchone()
    return dict(row) if row else None


def create(fields: dict) -> int:
    conn = get_connection()
    cols = ["issue_id", "title", "detail", "source", "severity", "status", "owner", "started_at"]
    conn.execute(
        f"INSERT INTO issues ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        tuple(fields.get(c) for c in cols),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def count(include_archived: bool = False) -> int:
    conn = get_connection()
    sql = "SELECT COUNT(*) FROM issues"
    if not include_archived:
        sql += " WHERE archived_at IS NULL"
    return conn.execute(sql).fetchone()[0]
