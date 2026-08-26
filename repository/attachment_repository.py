"""Pure DB access for attachment metadata. The actual file bytes never pass
through here or through SQLite — see services/attachment_service.py for the
disk-write convention. No UI calls this yet this phase."""
from __future__ import annotations

from common.db import get_connection

COLUMNS = [
    "id", "attachment_id", "entity_type", "entity_id", "attachment_type",
    "file_name", "stored_name", "file_path", "mime_type", "file_size", "uploaded_at",
]


def get_all_for_entity(entity_type: str, entity_id: str, include_archived: bool = False) -> list[dict]:
    conn = get_connection()
    sql = f"SELECT {', '.join(COLUMNS)} FROM attachments WHERE entity_type = ? AND entity_id = ?"
    if not include_archived:
        sql += " AND archived_at IS NULL"
    sql += " ORDER BY uploaded_at DESC"
    return [dict(r) for r in conn.execute(sql, (entity_type, entity_id)).fetchall()]


def create(fields: dict) -> int:
    conn = get_connection()
    cols = ["attachment_id", "entity_type", "entity_id", "attachment_type", "file_name", "stored_name", "file_path", "mime_type", "file_size"]
    conn.execute(
        f"INSERT INTO attachments ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
        tuple(fields.get(c) for c in cols),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def archive(attachment_id: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE attachments SET archived_at = datetime('now') WHERE attachment_id = ?", (attachment_id,))
    conn.commit()
