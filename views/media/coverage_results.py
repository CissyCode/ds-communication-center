from __future__ import annotations

import pandas as pd
import streamlit as st

from common import data as D
from common import style as S

from . import _shared as X

SENTIMENT_COLOR = {"긍정": "#2A6E49", "중립": "#7A8496", "부정": "#9A3A32"}


def _related_pr_activity(row_tags: list[str], press):
    tags = set(row_tags)
    if not tags:
        return None
    hit = press[press["tags_list"].apply(lambda ts: bool(tags & set(ts)))]
    return hit.iloc[0]["topic"] if not hit.empty else None


def render():
    S.page_title("MEDIA · Coverage & Results", "보도 현황과 PR 활동 결과를 확인합니다.")
    st.caption("Media Intelligence(언론 전체 동향)와 달리, 우리가 진행한 PR 활동이 실제로 어떻게 보도됐는지를 봅니다.")

    df = D.load_media_monitoring()
    press = D.load_press_history()
    issues = D.load_issues()

    S.stat_strip([
        ("총 보도 건수", f"{len(df)}", "건"),
        ("주요 매체", df["media"].mode().iloc[0] if len(df) else "-", None),
        ("최다 Tone", df["sentiment"].mode().iloc[0] if len(df) else "-", None),
    ])

    f1, f2, f3 = st.columns([1, 1.2, 1.4])
    with f1:
        sent_sel = st.multiselect("Tone", sorted(SENTIMENT_COLOR), key="cs_sent")
    with f2:
        media_sel = st.multiselect("매체", sorted(df["media"].unique()), key="cs_media")
    with f3:
        query = st.text_input("검색 (헤드라인/요약)", "", key="cs_q")

    filtered = df.copy()
    if sent_sel:
        filtered = filtered[filtered["sentiment"].isin(sent_sel)]
    if media_sel:
        filtered = filtered[filtered["media"].isin(media_sel)]
    if query:
        q = query.strip()
        filtered = filtered[
            filtered["headline"].str.contains(q, case=False, na=False)
            | filtered["summary"].str.contains(q, case=False, na=False)
        ]

    st.caption(f"{len(filtered)}건 표시 중 (전체 {len(df)}건)")

    rows = []
    for _, r in filtered.iterrows():
        pr_activity = _related_pr_activity(r["tags_list"], press)
        related_issue = X.monitoring_related_issue(r["monitoring_id"], issues)
        if related_issue is None and r["sentiment"] != "부정":
            tags = set(r["tags_list"])
            open_match = issues[issues.apply(lambda i: bool(tags & X.issue_topic_tags(i, press, df)), axis=1)]
            related_issue = open_match.iloc[0] if not open_match.empty else None
        rows.append({
            "일자": r["date"].date(), "매체": r["media"], "Headline": r["headline"],
            "Tone": r["sentiment"], "관련 PR Activity": pr_activity or "-",
            "관련 Issue": related_issue["title"] if related_issue is not None else "-",
        })

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
