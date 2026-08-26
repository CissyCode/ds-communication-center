from __future__ import annotations

import pandas as pd
import streamlit as st

from common import data as D
from common import style as S

from . import _shared as X

ASSET_KINDS = ["보도자료", "참고자료", "Q&A", "이미지/영상"]


def render():
    df = D.load_press_releases()
    st.caption("보도자료 전용 데이터가 없어, 일정 캘린더의 '보도자료 지원' 항목을 배포 로그로 표시합니다.")
    if df.empty:
        st.info("등록된 보도자료 일정이 없습니다.")
        return

    press = D.load_press_history()
    monitoring = D.load_media_monitoring()
    issues = D.load_issues()

    rows = []
    matches = {}
    for _, r in df.iterrows():
        issue, tags = X.release_related_issue(r["title"], issues, press, monitoring)
        coverage_count = len(monitoring[monitoring["tags_list"].apply(lambda ts: bool(tags & set(ts)))]) if tags else 0
        matches[r["schedule_id"]] = (issue, tags, coverage_count)
        rows.append({
            "schedule_id": r["schedule_id"], "일자": r["date"].date(), "제목": r["title"],
            "상태": r["status"], "관련 Issue": issue["title"] if issue is not None else "-",
            "보도 건수": coverage_count,
        })
    show = pd.DataFrame(rows)

    event = st.dataframe(
        show[["일자", "제목", "상태", "관련 Issue", "보도 건수"]],
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row", key="pr_select",
    )

    sel_id = X.resolve_selection(show, event, "schedule_id")
    if not sel_id:
        return

    r = df[df["schedule_id"] == sel_id].iloc[0]
    issue, tags, coverage_count = matches[sel_id]

    S.panel_open(r["title"])
    st.markdown(
        f"- **배포일**: {r['date'].date()}\n"
        f"- **상태**: {S.badge(r['status'], S.STATUS_TONE.get(r['status'], 'slate'))}\n"
        f"- **관련 Issue**: {issue['title'] if issue is not None else '-'}",
        unsafe_allow_html=True,
    )

    S.section_title("자료")
    st.caption("현재 FAKE DATA 범위에서는 실제 파일이 없어 구조만 표시합니다.")
    for kind in ASSET_KINDS:
        S.list_row(kind, "미등록")

    S.section_title("결과")
    S.stat_strip([("보도 건수", f"{coverage_count}", "건")])
    if tags:
        related_coverage = monitoring[monitoring["tags_list"].apply(lambda ts: bool(tags & set(ts)))]
        if not related_coverage.empty:
            st.markdown("**주요 보도**")
            for _, m in related_coverage.head(5).iterrows():
                tone = S.SENTIMENT_TONE.get(m["sentiment"], "slate")
                st.markdown(f"{m['date'].date()} · [{m['media']}] {m['headline']} {S.badge(m['sentiment'], tone)}", unsafe_allow_html=True)
        related_followup = press[(press["tags_list"].apply(lambda ts: bool(tags & set(ts)))) & (press["status"] == "진행 중")]
        st.markdown(f"**후속 대응**: {len(related_followup)}건 진행 중" if len(related_followup) else "**후속 대응**: 없음")
    else:
        st.caption("관련 Issue를 찾지 못해 보도 결과를 연결할 수 없습니다.")

    S.panel_close()
