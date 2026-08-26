from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from common import data as D
from common import style as S


def render():
    S.page_title("MEDIA · Monitoring", "언론·업계·시장·정책·경쟁사 동향을 모니터링합니다.")

    monitoring = D.load_media_monitoring()
    issues = D.load_issues()
    today = D.TODAY
    week_start = today - timedelta(days=6)

    c1, c2 = st.columns([3, 1])
    with c1:
        S.section_title("Today's Monitoring Brief")
        st.caption("AI가 오늘의 보도·이슈 흐름을 요약해 보여주는 자리입니다.")
    with c2:
        if st.button("AI 오늘의 브리핑", key="mon_ai_brief"):
            st.info("AI 기능 준비 중입니다 — 이번 Phase에서는 실제 실행 없이 화면 구조만 제공합니다.")

    high_risk = issues[issues["severity"] == "HIGH"]
    week_cov = monitoring[(monitoring["date"].dt.date >= week_start) & (monitoring["date"].dt.date <= today)]

    S.stat_strip([
        ("이번 주 보도", f"{len(week_cov)}", "건"),
        ("Risk Signal", f"{len(high_risk)}", "건"),
        ("모니터링 대상 매체", f"{monitoring['media'].nunique()}", "개"),
    ])

    row_l, row_r = st.columns(2)

    with row_l:
        S.section_title("주요 기사")
        recent = monitoring.sort_values("date", ascending=False).head(6)
        if recent.empty:
            st.caption("최근 기사가 없습니다.")
        for _, r in recent.iterrows():
            tone = S.SENTIMENT_TONE.get(r["sentiment"], "slate")
            st.markdown(f"{r['date'].date()} · [{r['media']}] {r['headline']} {S.badge(r['sentiment'], tone)}", unsafe_allow_html=True)

    with row_r:
        S.section_title("Risk Signal")
        if high_risk.empty:
            st.caption("현재 HIGH 등급 리스크 신호가 없습니다.")
        for _, r in high_risk.head(6).iterrows():
            st.markdown(f"{S.badge(r['severity'], 'red')} {r['title']}", unsafe_allow_html=True)

    S.section_title("Topic Trend")
    all_tags = [t for row in monitoring["tags_list"] for t in row]
    if all_tags:
        tc = pd.Series(all_tags).value_counts().head(8).reset_index()
        tc.columns = ["태그", "건수"]
        st.dataframe(tc, hide_index=True, use_container_width=True, height=220)
    else:
        st.caption("집계할 태그 데이터가 없습니다.")

    S.section_title("최근 모니터링 항목")
    show = monitoring.sort_values("date", ascending=False).head(8).copy()
    show["date"] = show["date"].dt.date
    st.dataframe(
        show[["date", "media", "headline", "sentiment"]].rename(
            columns={"date": "일자", "media": "매체", "headline": "헤드라인", "sentiment": "Tone"}
        ),
        hide_index=True, use_container_width=True, height=240,
    )
