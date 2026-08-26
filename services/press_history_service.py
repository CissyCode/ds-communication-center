"""Business logic for 대응 이력 — the one entity this phase wires all the
way through View → Service → Repository → SQLite. Validation, ID
generation, and reporter resolution live here; repository/press_history_repository.py
only knows SQL."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from repository import press_history_repository as repo

VALID_STATUS = ["진행 중", "완료"]
VALID_TYPES = ["취재 문의", "기사 대응", "인터뷰", "자료 제공", "행사"]


def _split_tags(value: str | None) -> list[str]:
    if not value:
        return []
    return [t.strip() for t in value.split(",") if t.strip()]


def _join_tags(values) -> str:
    if isinstance(values, str):
        return values.strip()
    return ", ".join(v.strip() for v in values if v and v.strip())


def _next_id() -> str:
    last = repo.get_last_id()
    if not last:
        return "PH001"
    try:
        num = int(last.replace("PH", "")) + 1
    except ValueError:
        num = repo.count(include_archived=True) + 1
    return f"PH{num:03d}"


@st.cache_data
def list_press_history(include_archived: bool = False) -> pd.DataFrame:
    rows = repo.get_all(include_archived=include_archived)
    df = pd.DataFrame(rows, columns=repo.LIST_COLUMNS)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df["tags_list"] = df["tags"].apply(_split_tags)
    return df


@st.cache_data
def get_press_history(press_history_id: str) -> dict | None:
    row = repo.get_by_id(press_history_id)
    if row is None:
        return None
    row = dict(row)
    row["tags_list"] = _split_tags(row.get("tags"))
    return row


@st.cache_data
def count_press_history(include_archived: bool = False) -> int:
    return repo.count(include_archived=include_archived)


def _invalidate() -> None:
    list_press_history.clear()
    get_press_history.clear()
    count_press_history.clear()


def create_press_history(
    *, date, media: str, reporter_pk: int | None, reporter_name: str, type_: str,
    topic: str, question: str, response: str, status: str, tags,
) -> str:
    media = (media or "").strip()
    reporter_name = (reporter_name or "").strip()
    topic = (topic or "").strip()
    if not media:
        raise ValueError("매체는 필수입니다.")
    if not reporter_name:
        raise ValueError("기자(이름)는 필수입니다.")
    if not topic:
        raise ValueError("주제는 필수입니다.")
    if status not in VALID_STATUS:
        raise ValueError(f"상태는 {VALID_STATUS} 중 하나여야 합니다.")

    new_id = _next_id()
    repo.create({
        "press_history_id": new_id,
        "date": str(date),
        "media": media,
        "reporter_id": reporter_pk,
        "reporter_name": reporter_name,
        "type": type_,
        "topic": topic,
        "question": question or "",
        "response": response or "",
        "status": status,
        "tags": _join_tags(tags),
    })
    _invalidate()
    return new_id


def update_press_history(
    press_history_id: str, *, date, media: str, reporter_pk: int | None, reporter_name: str,
    type_: str, topic: str, question: str, response: str, status: str, tags,
) -> None:
    media = (media or "").strip()
    reporter_name = (reporter_name or "").strip()
    topic = (topic or "").strip()
    if not media or not reporter_name or not topic:
        raise ValueError("매체·기자·주제는 필수입니다.")
    if status not in VALID_STATUS:
        raise ValueError(f"상태는 {VALID_STATUS} 중 하나여야 합니다.")

    repo.update(press_history_id, {
        "date": str(date),
        "media": media,
        "reporter_id": reporter_pk,
        "reporter_name": reporter_name,
        "type": type_,
        "topic": topic,
        "question": question or "",
        "response": response or "",
        "status": status,
        "tags": _join_tags(tags),
    })
    _invalidate()


def archive_press_history(press_history_id: str) -> None:
    repo.archive(press_history_id)
    _invalidate()
