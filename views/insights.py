from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from common import data as D
from common import nav as N
from common import style as S

# Cross-domain topics curated from the tags/topics that actually recur across
# press_history / media_monitoring / resources / reporters. Entities without
# a tags field (new_media_content, marcom projects/campaigns, schedule) are
# matched on free-text keywords in their title/name/goal instead — a
# prototype-level substitute for a real relation, as agreed.
TOPICS = {
    "AI메모리": {"tag": "AI메모리", "keywords": ["메모리", "Memory"]},
    "패키징": {"tag": "패키징", "keywords": ["패키징"]},
    "온디바이스AI": {"tag": "온디바이스AI", "keywords": ["온디바이스", "모바일 AI"]},
    "파운드리": {"tag": "파운드리", "keywords": ["파운드리", "공정"]},
    "공급망": {"tag": "공급망", "keywords": ["생산거점", "공급망"]},
    "AI반도체": {"tag": "AI반도체", "keywords": ["AI 반도체", "AI반도체"]},
    "R&D": {"tag": "R&D", "keywords": ["연구개발", "R&D"]},
    "메모리가격": {"tag": "메모리가격", "keywords": ["가격"]},
}


def _text_match(text: str, keywords: list[str]) -> bool:
    text = text or ""
    return any(k in text for k in keywords)


def _topic_breakdown(topic: str) -> pd.DataFrame:
    tag = TOPICS[topic]["tag"]
    keywords = TOPICS[topic]["keywords"]

    press = D.load_press_history()
    monitoring = D.load_media_monitoring()
    reporters = D.load_reporters()
    resources = D.load_resources()
    nm_content = D.load_new_media_content()
    mc_projects = D.load_marcom_projects()
    mc_campaigns = D.load_marcom_campaigns()
    sched = D.load_schedule()

    press_hit = press[press["tags_list"].apply(lambda ts: tag in ts)]
    monitoring_hit = monitoring[monitoring["tags_list"].apply(lambda ts: tag in ts)]
    reporters_hit = reporters[reporters["topics_list"].apply(lambda ts: tag in ts)]
    resources_hit = resources[resources["tags_list"].apply(lambda ts: tag in ts)]

    content_hit = nm_content[
        (nm_content["title"] + " " + nm_content["summary"]).apply(lambda t: _text_match(t, keywords))
    ]
    proj_hit = mc_projects[
        (mc_projects["name"] + " " + mc_projects["goal"]).apply(lambda t: _text_match(t, keywords))
    ]
    camp_hit = mc_campaigns[
        (mc_campaigns["name"] + " " + mc_campaigns["goal"]).apply(lambda t: _text_match(t, keywords))
    ]
    sched_future = sched[sched["start_date"].dt.date >= D.TODAY]
    sched_hit = sched_future[sched_future["title"].apply(lambda t: _text_match(t, keywords))]

    return pd.DataFrame([
        {"도메인": "MEDIA", "관련 활동": f"대응 {len(press_hit)}건 · 기사 {len(monitoring_hit)}건 · 기자 {len(reporters_hit)}명"},
        {"도메인": "NEW MEDIA", "관련 활동": f"콘텐츠 {len(content_hit)}건 · 총 조회 {int(content_hit['views'].sum()):,}"},
        {"도메인": "MARCOM", "관련 활동": f"Project {len(proj_hit)}건 · Campaign {len(camp_hit)}건"},
        {"도메인": "SCHEDULE", "관련 활동": f"향후 관련 일정 {len(sched_hit)}건"},
        {"도메인": "RESOURCES", "관련 활동": f"관련 자료 {len(resources_hit)}건"},
    ])


def render():
    S.page_title("INSIGHTS", "MEDIA·NEW MEDIA·MARCOM을 연결해서 보는 통합 분석 화면입니다.")

    today = D.TODAY
    week_start = today - timedelta(days=6)

    press = D.load_press_history()
    monitoring = D.load_media_monitoring()
    nm_content = D.load_new_media_content()
    mc_projects = D.load_marcom_projects()
    mc_events = D.load_marcom_events()

    # ---- A. Communication Overview ----
    S.section_title("Communication Overview · 최근 7일")
    media_week = press[(press["date"].dt.date >= week_start) & (press["date"].dt.date <= today)]
    monitoring_week = monitoring[(monitoring["date"].dt.date >= week_start) & (monitoring["date"].dt.date <= today)]
    content_week = nm_content[(nm_content["date"].dt.date >= week_start) & (nm_content["date"].dt.date <= today)]
    events_week = mc_events[(mc_events["date"].dt.date >= week_start) & (mc_events["date"].dt.date <= today)]
    active_projects = (mc_projects["status"] == "진행 중").sum()

    overview_df = pd.DataFrame([
        {"도메인": "MEDIA", "활동": f"대응 {len(media_week)}건 · 보도 {len(monitoring_week)}건"},
        {"도메인": "NEW MEDIA", "활동": f"콘텐츠 {len(content_week)}건 · 조회 {int(content_week['views'].sum()):,}"},
        {"도메인": "MARCOM", "활동": f"진행 Project {active_projects}건 · 이번 주 Event {len(events_week)}건"},
    ])
    st.dataframe(overview_df, hide_index=True, use_container_width=True, height=140)

    st.write("")

    # ---- B. Topic / Issue View ----
    S.section_title("Topic / Issue View")
    topic = st.selectbox("공통 Topic", list(TOPICS.keys()), key="insights_topic")
    st.dataframe(_topic_breakdown(topic), hide_index=True, use_container_width=True, height=200)
    st.caption("tags·topics·title 키워드 기반의 Prototype 수준 연결이며, 완전한 Relation은 아닙니다.")

    st.write("")

    # ---- C. Cross-domain Recent Activity ----
    S.section_title("Cross-domain Recent Activity")
    feed = D.load_recent_updates(limit=30)
    feed = feed[feed["module"].isin(["MEDIA", "NEW MEDIA", "MARCOM"])].head(8).copy()
    feed["date"] = feed["date"].dt.date
    event = st.dataframe(
        feed.rename(columns={"date": "일자", "module": "모듈", "title": "내용"}),
        hide_index=True, use_container_width=True,
        on_select="rerun", selection_mode="single-row", key="insights_activity_select",
    )
    if event.selection and event.selection.rows:
        module = feed.iloc[event.selection.rows[0]]["module"]
        target = {"MEDIA": "media", "NEW MEDIA": "new_media", "MARCOM": "marcom"}.get(module)
        del st.session_state["insights_activity_select"]
        if target:
            N.go_to(target)
    st.caption("행을 클릭하면 해당 모듈로 이동합니다.")
