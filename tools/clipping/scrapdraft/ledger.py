"""실행 원장(SQLite). 스크랩마스터 저장 파일이 아니라 이 도구 쪽에만 기록한다.

- 같은 날짜·같은 기사 키는 한 번만 '신규'로 기록 → 재실행 시 중복 추가 방지 기준
- 실행마다 입력 파일 해시, 규칙 해시, 신문별 상태, 전체 상태를 남겨 중단·재실행 지점을 확인
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_date TEXT, started_at TEXT, finished_at TEXT,
  input_file TEXT, input_sha256 TEXT, config_sha256 TEXT,
  overall TEXT, n_input INTEGER, n_selected INTEGER, step TEXT
);
CREATE TABLE IF NOT EXISTS paper_status (
  run_id INTEGER, media TEXT, status TEXT, n INTEGER
);
CREATE TABLE IF NOT EXISTS candidates (
  target_date TEXT, article_key TEXT, first_run_id INTEGER, last_run_id INTEGER,
  media TEXT, page TEXT, title TEXT, section TEXT, rec_rank INTEGER, state TEXT,
  PRIMARY KEY (target_date, article_key)
);
CREATE TABLE IF NOT EXISTS review_diff (
  target_date TEXT, article_key TEXT, action TEXT, rec_rank INTEGER, final_rank INTEGER,
  media TEXT, title TEXT, recorded_at TEXT
);
"""


class Ledger:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)

    def start_run(self, target_date: date, input_file: str, input_sha: str, config_sha: str, n_input: int) -> int:
        cur = self.db.execute(
            "INSERT INTO runs(target_date, started_at, input_file, input_sha256, config_sha256, n_input, step) VALUES (?,?,?,?,?,?,?)",
            (target_date.isoformat(), datetime.now().isoformat(timespec="seconds"), input_file, input_sha, config_sha, n_input, "읽기 완료"),
        )
        self.db.commit()
        return cur.lastrowid

    def step(self, run_id: int, step: str) -> None:
        self.db.execute("UPDATE runs SET step=? WHERE run_id=?", (step, run_id))
        self.db.commit()

    def same_input_before(self, target_date: date, input_sha: str, config_sha: str) -> int | None:
        r = self.db.execute(
            "SELECT run_id FROM runs WHERE target_date=? AND input_sha256=? AND config_sha256=? AND finished_at IS NOT NULL ORDER BY run_id DESC LIMIT 1",
            (target_date.isoformat(), input_sha, config_sha),
        ).fetchone()
        return r[0] if r else None

    def record_candidates(self, run_id: int, target_date: date, selected) -> set[str]:
        """추천 기사를 기록하고, 이번 실행에서 처음 나온 기사 키 집합을 돌려준다."""
        d = target_date.isoformat()
        new = set()
        for _, r in selected.iterrows():
            row = self.db.execute("SELECT 1 FROM candidates WHERE target_date=? AND article_key=?", (d, r["key"])).fetchone()
            if row:
                self.db.execute(
                    "UPDATE candidates SET last_run_id=?, section=?, rec_rank=? WHERE target_date=? AND article_key=?",
                    (run_id, r["section"], int(r["rank"]), d, r["key"]),
                )
            else:
                new.add(r["key"])
                self.db.execute(
                    "INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (d, r["key"], run_id, run_id, r["media"], r["page_raw"], r["title"], r["section"], int(r["rank"]), "추천"),
                )
        self.db.commit()
        return new

    def finish_run(self, run_id: int, overall: str, n_selected: int, status) -> None:
        for _, s in status.iterrows():
            self.db.execute("INSERT INTO paper_status VALUES (?,?,?,?)", (run_id, s["매체"], s["상태"], int(s["검색 건수"])))
        self.db.execute(
            "UPDATE runs SET finished_at=?, overall=?, n_selected=?, step=? WHERE run_id=?",
            (datetime.now().isoformat(timespec="seconds"), overall, n_selected, "완료", run_id),
        )
        self.db.commit()

    def recommended(self, target_date: date) -> list[tuple]:
        return self.db.execute(
            "SELECT article_key, rec_rank, media, title FROM candidates WHERE target_date=? ORDER BY rec_rank",
            (target_date.isoformat(),),
        ).fetchall()

    def record_diff(self, target_date: date, rows: list[dict]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        d = target_date.isoformat()
        self.db.execute("DELETE FROM review_diff WHERE target_date=?", (d,))  # 같은 날 재기록 시 덮어씀
        for r in rows:
            self.db.execute(
                "INSERT INTO review_diff VALUES (?,?,?,?,?,?,?,?)",
                (d, r["key"], r["action"], r.get("rec_rank"), r.get("final_rank"), r.get("media"), r.get("title"), now),
            )
        self.db.commit()

    def last_runs(self, limit: int = 10) -> list[tuple]:
        return self.db.execute(
            "SELECT run_id, target_date, started_at, finished_at, step, overall, n_input, n_selected FROM runs ORDER BY run_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
