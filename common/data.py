"""Cached CSV loaders for DS COMMUNICATION CENTER prototype data.

All data under /data is fully fabricated (see data/README source) — no real
companies, reporters, executives, or press outlets are represented.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

TODAY = date(2026, 8, 26)


def _split_tags(value: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    return [t.strip() for t in value.split(",") if t.strip()]


@st.cache_data
def load_reporters() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "reporters.csv", encoding="utf-8-sig")
    df["last_contact"] = pd.to_datetime(df["last_contact"], errors="coerce")
    df["topics_list"] = df["topics"].apply(_split_tags)
    return df


@st.cache_data
def load_press_history() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "press_history.csv", encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["tags_list"] = df["tags"].apply(_split_tags)
    return df


@st.cache_data
def load_contact_history() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "contact_history.csv", encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


@st.cache_data
def load_schedule() -> pd.DataFrame:
    """The single Master Schedule. Storage uses a standard schema (ISO dates,
    English columns, schedule_id, source_type/source_id) — Korean date-range
    labels like '9.7(월) ~ 9.9(수)' are a display concern (see common.style)
    and never stored. Merges the base calendar with MARCOM's own-hosted
    events (marcom_events.csv) so every module's dated activity surfaces in
    one place — no per-module calendars."""
    df = pd.read_csv(DATA_DIR / "schedule.csv", encoding="utf-8-sig")
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])

    events = pd.read_csv(DATA_DIR / "marcom_events.csv", encoding="utf-8-sig")
    events["_d"] = pd.to_datetime(events["date"], errors="coerce")
    extra = pd.DataFrame({
        "schedule_id": "MC-" + events["event_id"],
        "start_date": events["_d"],
        "end_date": events["_d"],
        "time_label": "-",
        "category": "MARCOM 행사",
        "title": events["name"],
        "location": events["location"],
        "attendees": events["co_host"],
        "source_type": "marcom_event",
        "source_id": events["event_id"],
    })

    combined = pd.concat([df, extra], ignore_index=True)
    combined["is_multi_day"] = combined["start_date"] != combined["end_date"]
    return combined.sort_values("start_date").reset_index(drop=True)


@st.cache_data
def load_notices() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "notices.csv", encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.sort_values("date", ascending=False).reset_index(drop=True)


@st.cache_data
def load_media_monitoring() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "media_monitoring.csv", encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["tags_list"] = df["tags"].apply(_split_tags)
    return df.sort_values("date", ascending=False).reset_index(drop=True)


@st.cache_data
def load_resources() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "resources.csv", encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["tags_list"] = df["tags"].apply(_split_tags)
    return df.sort_values("date", ascending=False).reset_index(drop=True)


@st.cache_data
def load_issues() -> pd.DataFrame:
    """Cross-cutting open-item watchlist: no dedicated dataset exists for this,
    so it re-surfaces unresolved records already present in other sources.
    issue_id is built from the originating record's own stable ID, so each
    row stays traceable back to its source rather than relying on row order."""
    press = load_press_history()
    open_press = press[press["status"] == "진행 중"][["press_history_id", "date", "media", "topic", "question"]].copy()
    open_press = open_press.rename(columns={"topic": "title", "question": "detail"})
    open_press["issue_id"] = "PH-" + open_press["press_history_id"]
    open_press["source"] = "미해결 대응"
    open_press["severity"] = "MEDIUM"  # pending inquiry, not yet a crisis

    notices = load_notices()
    urgent = notices[(notices["priority"] == "상단고정") | (notices["category"] == "긴급")][
        ["notice_id", "date", "title", "content", "category"]
    ].copy()
    urgent = urgent.rename(columns={"content": "detail"})
    urgent["issue_id"] = "NT-" + urgent["notice_id"]
    urgent["media"] = "사내 공지"
    urgent["source"] = "운영 공지"
    urgent["severity"] = urgent["category"].apply(lambda c: "HIGH" if c == "긴급" else "MEDIUM")

    monitoring = load_media_monitoring()
    negative = monitoring[monitoring["sentiment"] == "부정"][
        ["monitoring_id", "date", "media", "headline", "summary"]
    ].copy()
    negative = negative.rename(columns={"headline": "title", "summary": "detail"})
    negative["issue_id"] = "MM-" + negative["monitoring_id"]
    negative["source"] = "부정 보도"
    negative["severity"] = "HIGH"  # negative press coverage, reputational risk

    cols = ["issue_id", "date", "source", "media", "title", "detail", "severity"]
    combined = pd.concat(
        [open_press[cols], urgent[cols], negative[cols]],
        ignore_index=True,
    )
    return combined.sort_values("date", ascending=False).reset_index(drop=True)


@st.cache_data
def load_press_releases() -> pd.DataFrame:
    """보도자료 지원 events from the schedule as a stand-in press-release log."""
    sched = load_schedule()
    df = sched[sched["category"] == "보도자료 지원"][["schedule_id", "start_date", "title", "time_label"]].copy()
    df = df.rename(columns={"start_date": "date", "time_label": "time"})
    df["status"] = df["date"].dt.date.apply(lambda d: "배포 예정" if d >= TODAY else "배포 완료")
    return df.reset_index(drop=True)


@st.cache_data
def load_media_programs() -> pd.DataFrame:
    """언론사 행사/기타 대외 행사 rows from the schedule as media-facing programs."""
    sched = load_schedule()
    df = sched[sched["category"].isin(["언론사 행사", "기타 대외 행사"])].copy()
    return df[["start_date", "end_date", "title", "location", "attendees", "category"]].reset_index(drop=True)


@st.cache_data
def load_new_media_content() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "new_media_content.csv", encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.sort_values("date", ascending=False).reset_index(drop=True)


@st.cache_data
def load_new_media_channels() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "new_media_channels.csv", encoding="utf-8-sig")
    df["last_post_date"] = pd.to_datetime(df["last_post_date"], errors="coerce")
    return df.sort_values("followers", ascending=False).reset_index(drop=True)


@st.cache_data
def load_new_media_series() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "new_media_series.csv", encoding="utf-8-sig")


@st.cache_data
def load_marcom_projects() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "marcom_projects.csv", encoding="utf-8-sig")
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    return df


@st.cache_data
def load_marcom_campaigns() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "marcom_campaigns.csv", encoding="utf-8-sig")
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    return df


@st.cache_data
def load_marcom_events() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "marcom_events.csv", encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


@st.cache_data
def load_marcom_assets() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "marcom_assets.csv", encoding="utf-8-sig")
    df["updated_date"] = pd.to_datetime(df["updated_date"], errors="coerce")
    return df.sort_values("updated_date", ascending=False).reset_index(drop=True)


@st.cache_data
def load_recent_updates(limit: int = 8) -> pd.DataFrame:
    """Unified activity feed for HOME/INSIGHTS, pulled across every module's
    own data rather than a separate activity-log dataset."""
    rows = []
    for _, r in load_notices().iterrows():
        rows.append({"date": r["date"], "module": "공지", "title": r["title"]})
    for _, r in load_press_history().iterrows():
        rows.append({"date": r["date"], "module": "MEDIA", "title": f"[{r['media']}] {r['topic']}"})
    for _, r in load_media_monitoring().iterrows():
        rows.append({"date": r["date"], "module": "MEDIA", "title": r["headline"]})
    for _, r in load_resources().iterrows():
        rows.append({"date": r["date"], "module": "RESOURCES", "title": r["title"]})
    for _, r in load_new_media_content().iterrows():
        rows.append({"date": r["date"], "module": "NEW MEDIA", "title": r["title"]})
    for _, r in load_marcom_projects().iterrows():
        if r["status"] == "완료":
            rows.append({"date": r["end_date"], "module": "MARCOM", "title": f"{r['name']} 완료"})
    for _, r in load_marcom_campaigns().iterrows():
        if r["status"] == "완료":
            rows.append({"date": r["end_date"], "module": "MARCOM", "title": f"{r['name']} 완료"})
    df = pd.DataFrame(rows).sort_values("date", ascending=False).head(limit).reset_index(drop=True)
    return df
