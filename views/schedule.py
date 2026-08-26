from __future__ import annotations

import calendar
from datetime import date

import pandas as pd
import streamlit as st

from common import data as D
from common import style as S

CATEGORY_TONE = {
    "기타 대외 행사": "blue",
    "언론사 행사": "green",
    "보도자료 지원": "amber",
    "내부 주요 일정": "slate",
    "정부 행사": "red",
    "MARCOM 행사": "purple",
}


def _filters(df: pd.DataFrame):
    f1, f2 = st.columns([2, 2])
    with f1:
        cat_sel = st.multiselect("분류", sorted(df["category"].unique()))
    with f2:
        query = st.text_input("검색 (행사명/장소/참석자)", "")

    filtered = df.copy()
    if cat_sel:
        filtered = filtered[filtered["category"].isin(cat_sel)]
    if query:
        q = query.strip()
        filtered = filtered[
            filtered["title"].str.contains(q, case=False, na=False)
            | filtered["location"].fillna("").str.contains(q, case=False, na=False)
            | filtered["attendees"].fillna("").str.contains(q, case=False, na=False)
        ]
    return filtered


def _list_view(filtered: pd.DataFrame):
    st.caption(f"{len(filtered)}건 표시 중")
    show = filtered.copy()
    show["일자"] = show.apply(lambda r: S.format_date_range(r["start_date"], r["end_date"]), axis=1)
    show = show[["일자", "time_label", "category", "title", "location", "attendees"]].rename(
        columns={"time_label": "시간", "category": "분류", "title": "행사명", "location": "장소", "attendees": "참석자"}
    )
    st.dataframe(show, hide_index=True, use_container_width=True)


def _calendar_view(filtered: pd.DataFrame):
    months = sorted({(d.year, d.month) for d in filtered["start_date"].dt.to_pydatetime()})
    if not months:
        st.info("해당 조건에 맞는 일정이 없습니다.")
        return

    for year, month in months:
        S.section_title(f"{year}년 {month}월")
        weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)
        weekday_labels = ["일", "월", "화", "수", "목", "금", "토"]

        header_cols = st.columns(7)
        for c, label in zip(header_cols, weekday_labels):
            c.markdown(f"<div class='dcc-muted' style='text-align:center;font-weight:700;'>{label}</div>",
                       unsafe_allow_html=True)

        for week in weeks:
            cols = st.columns(7)
            for c, day_num in zip(cols, week):
                if day_num == 0:
                    c.markdown("<div class='dcc-cal-cell empty'></div>", unsafe_allow_html=True)
                    continue
                day = date(year, month, day_num)
                day_events = filtered[
                    (filtered["start_date"].dt.date <= day) & (filtered["end_date"].dt.date >= day)
                ]
                is_today = day == D.TODAY
                evt_html = "".join(
                    f"<div class='dcc-cal-evt' title='{e['title']}'>{e['title']}</div>"
                    for _, e in day_events.head(3).iterrows()
                )
                if len(day_events) > 3:
                    evt_html += f"<div class='dcc-muted' style='font-size:.62rem;'>+{len(day_events) - 3}건 더</div>"
                today_cls = "today" if is_today else ""
                cell_html = (
                    f'<div class="dcc-cal-cell"><div class="d {today_cls}">{day_num}</div>{evt_html}</div>'
                )
                c.markdown(cell_html, unsafe_allow_html=True)

    st.write("")
    S.section_title("날짜별 상세 보기")
    all_dates = sorted(set(filtered["start_date"].dt.date) | set(filtered["end_date"].dt.date))
    if all_dates:
        picked = st.selectbox("날짜 선택", all_dates, format_func=lambda d: d.strftime("%Y-%m-%d (%a)"))
        day_events = filtered[
            (filtered["start_date"].dt.date <= picked) & (filtered["end_date"].dt.date >= picked)
        ]
        if day_events.empty:
            st.caption("선택한 날짜에 일정이 없습니다.")
        for _, r in day_events.iterrows():
            tone = CATEGORY_TONE.get(r["category"], "slate")
            st.markdown(f"**{r['time_label']}** · {r['title']} {S.badge(r['category'], tone)}", unsafe_allow_html=True)


def render():
    S.page_title("SCHEDULE", "언론·정부·사내 등 커뮤니케이션 관련 주요 일정을 확인합니다.")

    df = D.load_schedule()

    S.stat_strip([
        ("전체 일정", f"{len(df)}", "건"),
        ("다가오는 일정", f"{(df['start_date'].dt.date >= D.TODAY).sum()}", "건"),
        ("분류", f"{df['category'].nunique()}", "개"),
        ("해외 출장성 일정", f"{df['is_multi_day'].sum()}", "건"),
    ])

    filtered = _filters(df)
    filtered = filtered.sort_values("start_date")

    tab_list, tab_cal = st.tabs(["리스트 보기", "캘린더 보기"])
    with tab_list:
        _list_view(filtered)
    with tab_cal:
        _calendar_view(filtered)
