from __future__ import annotations

import pandas as pd
import streamlit as st

from common import data as D
from common import style as S

from . import _shared as X


def _infer_type(title: str) -> str:
    """No program-type field exists in the schedule data — this is a
    title-keyword best guess, shown to the user as such, not ground truth."""
    if any(k in title for k in ["포럼", "Summit", "Conference", "Expo"]):
        return "컨퍼런스/포럼(추정)"
    if "간담회" in title:
        return "기자간담회 (추정)"
    if "내방" in title:
        return "기업 방문 (추정)"
    return "기타 대외 행사 (추정)"


def render():
    S.page_title("MEDIA · Media Programs", "기자간담회·사업장초청 등 미디어 프로그램 일정을 관리합니다.")
    df = D.load_media_programs()
    st.caption("일정은 Master Schedule(SCHEDULE)의 데이터를 그대로 참조합니다 — 별도 캘린더를 두지 않습니다.")
    if df.empty:
        st.info("등록된 미디어 프로그램 일정이 없습니다.")
        return

    press = D.load_press_history()
    monitoring = D.load_media_monitoring()
    issues = D.load_issues()

    rows = []
    matches = {}
    for i, r in df.iterrows():
        issue, tags = X.release_related_issue(r["title"], issues, press, monitoring)
        matches[i] = (issue, tags)
        rows.append({
            "idx": i, "일정": r["start_date"].date(), "프로그램명": r["title"],
            "유형": _infer_type(r["title"]),
            "상태": "예정" if r["start_date"].date() >= D.TODAY else "완료",
            "참석 기자": "데이터 없음",
            "관련 Issue": issue["title"] if issue is not None else "-",
        })
    show = pd.DataFrame(rows)

    event = st.dataframe(
        show[["일정", "프로그램명", "유형", "상태", "참석 기자", "관련 Issue"]],
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row", key="pg_select",
    )

    sel_idx = None
    if event.selection and event.selection.rows:
        sel_idx = show.iloc[event.selection.rows[0]]["idx"]
    if sel_idx is None:
        return

    r = df.loc[sel_idx]
    issue, tags = matches[sel_idx]

    S.panel_open(r["title"])

    S.section_title("기본 정보")
    st.markdown(
        f"- **일정**: {r['start_date'].date()}"
        + (f" ~ {r['end_date'].date()}" if r["start_date"] != r["end_date"] else "")
        + f"\n- **유형**: {_infer_type(r['title'])}\n- **장소**: {r['location'] or '-'}"
    )

    S.section_title("초청 / 참석")
    st.markdown(f"- **참석 기자**: 데이터 없음 (기자 초청 명단이 아직 관리되지 않습니다)\n- **참석 임원**: {r['attendees'] or '-'}")

    S.section_title("자료")
    S.list_row("행사 자료", "미등록")

    S.section_title("관련 대응")
    if tags:
        rel_press = press[press["tags_list"].apply(lambda ts: bool(tags & set(ts)))]
        if rel_press.empty:
            st.caption("연결된 대응 이력이 없습니다.")
        for _, pr in rel_press.iterrows():
            st.markdown(f"{pr['date'].date()} · [{pr['media']}] {pr['topic']}")
    else:
        st.caption("관련 Issue를 찾지 못해 대응 이력을 연결할 수 없습니다.")

    S.section_title("관련 보도")
    if tags:
        rel_cov = monitoring[monitoring["tags_list"].apply(lambda ts: bool(tags & set(ts)))]
        if rel_cov.empty:
            st.caption("연결된 보도가 없습니다.")
        for _, m in rel_cov.iterrows():
            tone = S.SENTIMENT_TONE.get(m["sentiment"], "slate")
            st.markdown(f"{m['date'].date()} · [{m['media']}] {m['headline']} {S.badge(m['sentiment'], tone)}", unsafe_allow_html=True)
    else:
        st.caption("관련 Issue를 찾지 못해 보도를 연결할 수 없습니다.")

    S.panel_close()
