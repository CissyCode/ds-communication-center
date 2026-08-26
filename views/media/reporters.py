from __future__ import annotations

import pandas as pd
import streamlit as st

from common import data as D
from common import nav as N
from common import style as S

from . import _shared as X


def render():
    df = D.load_reporters()

    f1, f2, f3, f4 = st.columns([1.2, 1, 1.4, 1.2])
    with f1:
        media_sel = st.multiselect("매체사", sorted(df["media"].unique()), key="rp_media")
    with f2:
        status_sel = st.multiselect("상태", sorted(df["status"].unique()), key="rp_status")
    with f3:
        all_topics = sorted({t for row in df["topics_list"] for t in row})
        topic_sel = st.multiselect("관심 주제", all_topics, key="rp_topic")
    with f4:
        query = st.text_input("검색 (이름/매체/메모)", "", key="rp_q")

    filtered = df.copy()
    if media_sel:
        filtered = filtered[filtered["media"].isin(media_sel)]
    if status_sel:
        filtered = filtered[filtered["status"].isin(status_sel)]
    if topic_sel:
        filtered = filtered[filtered["topics_list"].apply(lambda ts: any(t in ts for t in topic_sel))]
    if query:
        q = query.strip()
        filtered = filtered[
            filtered["name"].str.contains(q, case=False, na=False)
            | filtered["media"].str.contains(q, case=False, na=False)
            | filtered["notes"].str.contains(q, case=False, na=False)
        ]

    st.caption(f"{len(filtered)}건 표시 중 (전체 {len(df)}건) · 행을 클릭하면 상세를 볼 수 있습니다.")

    display_df = filtered[[
        "name", "media", "department", "position", "email", "phone", "status", "topics", "last_contact",
    ]].rename(columns={
        "name": "이름", "media": "매체", "department": "부서", "position": "직급",
        "email": "이메일", "phone": "전화", "status": "상태", "topics": "관심주제", "last_contact": "최근접촉",
    })

    event = st.dataframe(
        display_df, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
        key="rp_select", column_config={"최근접촉": st.column_config.DateColumn(format="YYYY-MM-DD")},
    )

    sel_id = X.resolve_selection(filtered, event, "reporter_id")
    if sel_id:
        picked = df[df["reporter_id"] == sel_id].iloc[0]
        press = D.load_press_history()
        contacts = D.load_contact_history()
        monitoring = D.load_media_monitoring()
        rel_press = press[press["reporter"] == picked["name"]].sort_values("date", ascending=False)
        rel_contacts = contacts[contacts["reporter"] == picked["name"]].sort_values("date", ascending=False)
        rel_coverage = monitoring[monitoring["reporter"] == picked["name"]].sort_values("date", ascending=False)

        S.panel_open(f"{picked['name']} · {picked['media']} {picked['position']}")

        S.section_title("기본정보")
        st.markdown(
            f"- **매체**: {picked['media']}\n"
            f"- **부서**: {picked['department']}\n"
            f"- **직책**: {picked['position']}\n"
            f"- **연락처**: {picked['email']} / {picked['phone']}"
        )

        S.section_title("Relationship Summary")
        S.stat_strip([
            ("최근 접촉", str(picked["last_contact"].date()) if not pd.isna(picked["last_contact"]) else "-", None),
            ("대응 이력 건수", f"{len(rel_press)}", "건"),
            ("주요 관심 Topic", ", ".join(picked["topics_list"][:2]) or "-", None),
            ("최근 접촉 횟수", f"{len(rel_contacts)}", "건"),
        ])

        S.section_title(f"최근 대응 ({len(rel_press)})")
        if rel_press.empty:
            st.caption("연결된 대응 이력이 없습니다.")
        for _, r in rel_press.head(5).iterrows():
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(
                    f"**{r['date'].date()}** · {r['type']} · {r['topic']} "
                    + S.badge(r["status"], S.STATUS_TONE.get(r["status"], "slate")),
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("보기", key=f"rp_goto_press_{r['press_history_id']}"):
                    N.jump_media("대응 이력", focus_id=r["press_history_id"], focus_col="press_history_id")

        S.section_title(f"최근 접촉 ({len(rel_contacts)})")
        if rel_contacts.empty:
            st.caption("연결된 접촉 이력이 없습니다.")
        for _, r in rel_contacts.head(5).iterrows():
            st.markdown(f"**{r['date'].date()}** · {r['contact_type']} · {r['subject']} — {r['result']}")

        S.section_title(f"관련 보도 ({len(rel_coverage)})")
        if rel_coverage.empty:
            st.caption("이 기자 이름으로 등록된 보도가 없습니다.")
        for _, r in rel_coverage.head(5).iterrows():
            tone = S.SENTIMENT_TONE.get(r["sentiment"], "slate")
            st.markdown(f"**{r['date'].date()}** · {r['headline']} {S.badge(r['sentiment'], tone)}", unsafe_allow_html=True)

        S.panel_close()
