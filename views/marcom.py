from __future__ import annotations

import altair as alt
import streamlit as st

from common import data as D
from common import style as S


def _overview():
    projects = D.load_marcom_projects()
    campaigns = D.load_marcom_campaigns()
    events = D.load_marcom_events()
    assets = D.load_marcom_assets()
    notices = D.load_notices()

    S.stat_strip([
        ("진행중 프로젝트", f"{(projects['status'] == '진행 중').sum()}", "건"),
        ("진행중 캠페인", f"{(campaigns['status'] == '진행 중').sum()}", "건"),
        ("예정 행사", f"{len(events)}", "건"),
        ("등록 자산", f"{len(assets)}", "건"),
        ("사내 공지", f"{len(notices)}", "건"),
    ])

    left, right = st.columns(2)
    with left:
        S.section_title("진행중 프로젝트 · 캠페인")
        show_p = projects[projects["status"] == "진행 중"].copy()
        show_p["기간"] = show_p.apply(lambda r: S.format_period(r["start_date"], r["end_date"]), axis=1)
        st.dataframe(
            show_p[["name", "기간", "owner"]].rename(columns={"name": "프로젝트명", "owner": "담당자"}),
            hide_index=True, use_container_width=True, height=140,
        )
        show_c = campaigns[campaigns["status"] == "진행 중"].copy()
        show_c["기간"] = show_c.apply(lambda r: S.format_period(r["start_date"], r["end_date"]), axis=1)
        st.dataframe(
            show_c[["name", "기간", "budget_100m"]].rename(
                columns={"name": "캠페인명", "budget_100m": "예산(억원, 가상)"}
            ),
            hide_index=True, use_container_width=True, height=110,
        )
    with right:
        S.section_title("예정 행사")
        show_e = events.copy()
        show_e["date"] = show_e["date"].dt.date
        st.dataframe(
            show_e[["date", "name", "location", "status"]].rename(
                columns={"date": "일정", "name": "행사명", "location": "장소", "status": "상태"}
            ),
            hide_index=True, use_container_width=True, height=140,
        )
        S.section_title("최근 사내 공지")
        for _, row in notices.head(4).iterrows():
            main = row["title"]
            if row["priority"] == "상단고정":
                main = f'<span class="dcc-pin-dot">●</span>{main}'
            S.list_row(main, f"{row['category']} · {row['date'].date()}")


def _projects():
    df = D.load_marcom_projects()
    show = df.copy()
    show["기간"] = show.apply(lambda r: S.format_period(r["start_date"], r["end_date"]), axis=1)
    event = st.dataframe(
        show[["name", "goal", "기간", "status", "owner"]].rename(
            columns={"name": "프로젝트명", "goal": "목표", "status": "진행상태", "owner": "담당자"}
        ),
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
    )
    if event.selection and event.selection.rows:
        sel_id = df.iloc[event.selection.rows[0]]["project_id"]
        r = df[df["project_id"] == sel_id].iloc[0]
        S.panel_open(r["name"])
        st.markdown(
            f"{S.badge(r['status'], S.STATUS_TONE.get(r['status'], 'slate'))} "
            f"<span class='dcc-muted'>담당 {r['owner']} · {S.format_period(r['start_date'], r['end_date'])}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"목표: {r['goal']}")
        S.panel_close()


def _campaigns():
    df = D.load_marcom_campaigns()
    show = df.copy()
    show["기간"] = show.apply(lambda r: S.format_period(r["start_date"], r["end_date"]), axis=1)
    show["예산"] = show["budget_100m"].apply(lambda v: f"{v}억원 (가상)")
    event = st.dataframe(
        show[["name", "goal", "기간", "예산", "status"]].rename(
            columns={"name": "캠페인명", "goal": "목표", "status": "진행상태"}
        ),
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
    )
    if event.selection and event.selection.rows:
        sel_id = df.iloc[event.selection.rows[0]]["campaign_id"]
        r = df[df["campaign_id"] == sel_id].iloc[0]
        S.panel_open(r["name"])
        st.markdown(
            f"{S.badge(r['status'], S.STATUS_TONE.get(r['status'], 'slate'))} "
            f"<span class='dcc-muted'>{S.format_period(r['start_date'], r['end_date'])} · 예산 {r['budget_100m']}억원(가상)</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"목표: {r['goal']}")
        S.panel_close()


def _events():
    df = D.load_marcom_events()
    show = df.copy()
    show["date"] = show["date"].dt.date
    event = st.dataframe(
        show[["name", "date", "location", "co_host", "status"]].rename(columns={
            "name": "행사명", "date": "일정", "location": "장소", "co_host": "공동주관", "status": "진행상태",
        }),
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
    )
    if event.selection and event.selection.rows:
        sel_id = df.iloc[event.selection.rows[0]]["event_id"]
        r = df[df["event_id"] == sel_id].iloc[0]
        S.panel_open(r["name"])
        st.markdown(
            f"{S.badge(r['status'], S.STATUS_TONE.get(r['status'], 'slate'))} "
            f"<span class='dcc-muted'>{r['date'].date()} · {r['location']} · 공동주관 {r['co_host']}</span>",
            unsafe_allow_html=True,
        )
        st.caption("이 행사는 SCHEDULE의 Master Schedule에도 'MARCOM 행사' 분류로 함께 표시됩니다.")
        S.panel_close()


def _assets():
    df = D.load_marcom_assets()
    show = df.copy()
    show["updated_date"] = show["updated_date"].dt.date
    event = st.dataframe(
        show[["name", "type", "format", "version", "owner", "updated_date"]].rename(columns={
            "name": "자산명", "type": "유형", "format": "포맷", "version": "버전",
            "owner": "담당자", "updated_date": "업데이트일",
        }),
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
    )
    if event.selection and event.selection.rows:
        sel_id = df.iloc[event.selection.rows[0]]["asset_id"]
        r = df[df["asset_id"] == sel_id].iloc[0]
        S.panel_open(r["name"])
        st.markdown(
            f"{S.badge(r['type'], 'blue')} {S.badge(r['format'], 'slate')} "
            f"<span class='dcc-muted'>{r['version']} · 담당 {r['owner']} · {r['updated_date'].date()} 업데이트</span>",
            unsafe_allow_html=True,
        )
        S.panel_close()


def _analytics():
    projects = D.load_marcom_projects()
    campaigns = D.load_marcom_campaigns()

    c1, c2 = st.columns(2)
    with c1:
        S.section_title("프로젝트 진행상태 분포")
        pc = projects["status"].value_counts().reset_index()
        pc.columns = ["status", "count"]
        chart = alt.Chart(pc).mark_bar(color="#31518C").encode(
            x=alt.X("count:Q", title="건수"), y=alt.Y("status:N", sort="-x", title=None)
        ).properties(height=220)
        st.altair_chart(chart, use_container_width=True)
    with c2:
        S.section_title("캠페인 예산 비교 (가상, 억원)")
        chart = alt.Chart(campaigns).mark_bar(color="#8A94A6").encode(
            x=alt.X("budget_100m:Q", title="억원"), y=alt.Y("name:N", sort="-x", title=None),
            tooltip=["name", "budget_100m", "status"],
        ).properties(height=220)
        st.altair_chart(chart, use_container_width=True)


def render():
    S.page_title("MARCOM", "브랜드 커뮤니케이션 프로젝트·캠페인·행사·자산을 관리합니다.")
    tabs = st.tabs(["Overview", "Projects", "Campaigns", "Events", "Assets", "Marcom Analytics"])
    with tabs[0]:
        _overview()
    with tabs[1]:
        _projects()
    with tabs[2]:
        _campaigns()
    with tabs[3]:
        _events()
    with tabs[4]:
        _assets()
    with tabs[5]:
        _analytics()
