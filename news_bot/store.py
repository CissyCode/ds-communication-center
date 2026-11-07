"""이미 보낸 기사 기록 (중복 발송 방지). storage/news_bot.db, git에 커밋되지 않음."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .filters import normalize_title
from .naver import Article

SCHEMA = """
CREATE TABLE IF NOT EXISTS sent_articles (
    dedupe_key  TEXT PRIMARY KEY,
    title_key   TEXT NOT NULL,
    query_name  TEXT NOT NULL,
    title       TEXT NOT NULL,
    link        TEXT NOT NULL,
    sent_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sent_title ON sent_articles(title_key);
CREATE TABLE IF NOT EXISTS bot_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def is_sent(self, a: Article) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM sent_articles WHERE dedupe_key = ? OR title_key = ? LIMIT 1",
            (a.dedupe_key, normalize_title(a.title)),
        ).fetchone()
        return row is not None

    def mark_sent(self, a: Article, query_name: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO sent_articles VALUES (?, ?, ?, ?, ?, ?)",
            (a.dedupe_key, normalize_title(a.title), query_name, a.title, a.link,
             datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def prune(self, days: int = 30) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        self.conn.execute("DELETE FROM sent_articles WHERE sent_at < ?", (cutoff,))
        self.conn.commit()

    def get_state(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM bot_state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set_state(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO bot_state VALUES (?, ?)", (key, value))
        self.conn.commit()
