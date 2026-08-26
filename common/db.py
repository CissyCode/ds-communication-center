"""SQLite connection for the Write Foundation. Kept separate from
common/data.py on purpose — data.py stays the pure CSV/read-only path for
every screen except MEDIA > 대응 이력, which is the only consumer of this
module so far."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import streamlit as st

STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
DB_PATH = STORAGE_DIR / "communication_center.db"


@st.cache_resource
def get_connection() -> sqlite3.Connection:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@st.cache_resource
def ensure_ready() -> bool:
    """Create the schema and seed demo data if this is a fresh environment
    (e.g. a brand-new Streamlit Cloud deploy with no storage/ yet). Both
    steps are idempotent, and st.cache_resource means this only actually
    runs once per server process regardless of how many reruns happen."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from scripts.init_db import init_db
    from scripts.seed_demo_data import seed

    init_db()
    seed()
    return True
