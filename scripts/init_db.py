"""Create the SQLite schema (idempotent) and the on-disk file storage tree.
Run directly: python scripts/init_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.db import STORAGE_DIR, get_connection  # noqa: E402

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reporters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id   TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    media         TEXT,
    department    TEXT,
    position      TEXT,
    email         TEXT,
    phone         TEXT,
    status        TEXT NOT NULL DEFAULT '활성',
    topics        TEXT,
    last_contact  TEXT,
    notes         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at   TEXT
);

CREATE TABLE IF NOT EXISTS press_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    press_history_id  TEXT UNIQUE NOT NULL,
    date              TEXT NOT NULL,
    media             TEXT NOT NULL,
    reporter_id       INTEGER REFERENCES reporters(id),
    reporter_name     TEXT NOT NULL,
    type              TEXT NOT NULL,
    topic             TEXT NOT NULL,
    question          TEXT,
    response          TEXT,
    status            TEXT NOT NULL DEFAULT '진행 중',
    tags              TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at       TEXT
);

CREATE TABLE IF NOT EXISTS issues (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id      TEXT UNIQUE NOT NULL,
    title         TEXT NOT NULL,
    detail        TEXT,
    source        TEXT,
    severity      TEXT NOT NULL DEFAULT 'MEDIUM',
    status        TEXT NOT NULL DEFAULT '진행 중',
    owner         TEXT,
    started_at    TEXT,
    resolved_at   TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at   TEXT
);

CREATE TABLE IF NOT EXISTS press_releases (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    press_release_id  TEXT UNIQUE NOT NULL,
    title             TEXT NOT NULL,
    date              TEXT NOT NULL,
    time_label        TEXT,
    status            TEXT NOT NULL DEFAULT '작성',
    source_type       TEXT,
    source_id         TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at       TEXT
);

CREATE TABLE IF NOT EXISTS attachments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    attachment_id     TEXT UNIQUE NOT NULL,
    entity_type       TEXT NOT NULL,
    entity_id         TEXT NOT NULL,
    attachment_type   TEXT,
    file_name         TEXT NOT NULL,
    stored_name       TEXT NOT NULL,
    file_path         TEXT NOT NULL,
    mime_type         TEXT,
    file_size         INTEGER,
    uploaded_at       TEXT NOT NULL DEFAULT (datetime('now')),
    archived_at       TEXT
);

CREATE TABLE IF NOT EXISTS issue_press_history (
    issue_id          INTEGER NOT NULL REFERENCES issues(id),
    press_history_id  INTEGER NOT NULL REFERENCES press_history(id),
    linked_at         TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (issue_id, press_history_id)
);

CREATE TABLE IF NOT EXISTS issue_reporters (
    issue_id      INTEGER NOT NULL REFERENCES issues(id),
    reporter_id   INTEGER NOT NULL REFERENCES reporters(id),
    linked_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (issue_id, reporter_id)
);

CREATE TABLE IF NOT EXISTS issue_press_releases (
    issue_id          INTEGER NOT NULL REFERENCES issues(id),
    press_release_id  INTEGER NOT NULL REFERENCES press_releases(id),
    linked_at         TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (issue_id, press_release_id)
);
"""

FILE_DIRS = [
    "media/press_releases",
    "media/issues",
    "resources",
    "new_media",
    "marcom",
]


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    for d in FILE_DIRS:
        (STORAGE_DIR / "files" / d).mkdir(parents=True, exist_ok=True)
    print(f"Schema ready at {STORAGE_DIR / 'communication_center.db'}")


if __name__ == "__main__":
    init_db()
