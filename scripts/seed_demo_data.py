"""Idempotent seed: copies the existing CSV/derived FAKE DATA into SQLite so
the Write Foundation has something to read/write against. Safe to re-run —
every insert is keyed on each table's UNIQUE stable id, so rows that already
exist are silently skipped (INSERT OR IGNORE), never duplicated.

Run directly: python scripts/seed_demo_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import data as D  # noqa: E402
from common.db import get_connection  # noqa: E402
from scripts.init_db import init_db  # noqa: E402


def _date_str(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(value.date()) if hasattr(value, "date") else str(value)


def seed_reporters(conn) -> int:
    df = D.load_reporters()
    n = 0
    for _, r in df.iterrows():
        cur = conn.execute(
            """INSERT OR IGNORE INTO reporters
               (reporter_id, name, media, department, position, email, phone, status, topics, last_contact, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r["reporter_id"], r["name"], r["media"], r["department"], r["position"],
                r["email"], r["phone"], r["status"], r["topics"], _date_str(r["last_contact"]), r["notes"],
            ),
        )
        n += cur.rowcount
    return n


def seed_press_history(conn) -> int:
    df = D.load_press_history()
    n = 0
    for _, r in df.iterrows():
        rep = conn.execute("SELECT id FROM reporters WHERE name = ?", (r["reporter"],)).fetchone()
        reporter_pk = rep["id"] if rep else None
        cur = conn.execute(
            """INSERT OR IGNORE INTO press_history
               (press_history_id, date, media, reporter_id, reporter_name, type, topic, question, response, status, tags)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                r["press_history_id"], _date_str(r["date"]), r["media"], reporter_pk, r["reporter"],
                r["type"], r["topic"], r["question"], r["response"], r["status"], r["tags"],
            ),
        )
        n += cur.rowcount
    return n


def seed_issues(conn) -> int:
    df = D.load_issues()
    n = 0
    for _, r in df.iterrows():
        cur = conn.execute(
            """INSERT OR IGNORE INTO issues
               (issue_id, title, detail, source, severity, status, owner, started_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (r["issue_id"], r["title"], r["detail"], r["source"], r["severity"], "진행 중", None, _date_str(r["date"])),
        )
        n += cur.rowcount
    return n


def seed_press_releases(conn) -> int:
    df = D.load_press_releases()
    n = 0
    for _, r in df.iterrows():
        release_id = f"PR-{r['schedule_id']}"
        cur = conn.execute(
            """INSERT OR IGNORE INTO press_releases
               (press_release_id, title, date, time_label, status, source_type, source_id)
               VALUES (?,?,?,?,?,?,?)""",
            (release_id, r["title"], _date_str(r["date"]), r["time"], r["status"], "schedule", r["schedule_id"]),
        )
        n += cur.rowcount
    return n


def seed() -> None:
    init_db()
    conn = get_connection()
    counts = {
        "reporters": seed_reporters(conn),
        "press_history": seed_press_history(conn),
        "issues": seed_issues(conn),
        "press_releases": seed_press_releases(conn),
    }
    conn.commit()
    for name, n in counts.items():
        print(f"{name}: {n} row(s) inserted this run")


if __name__ == "__main__":
    seed()
