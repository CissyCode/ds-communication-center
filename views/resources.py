from __future__ import annotations

import streamlit as st

from common import data as D
from common import style as S


def render():
    S.page_title("RESOURCES", "시장/기술/행사 관련 참고자료를 유형과 보안등급별로 열람합니다.")

    df = D.load_resources()

    S.stat_strip([
        ("총 자료", f"{len(df)}", "건"),
        ("공개 가능", f"{(df['security'] == '공개가능').sum()}", "건"),
        ("내부 전용", f"{(df['security'] == '내부').sum()}", "건"),
        ("최근 등록일", str(df["date"].max().date()), None),
    ])

    f1, f2, f3, f4 = st.columns([1, 1, 1, 1.4])
    with f1:
        type_sel = st.multiselect("유형", sorted(df["type"].unique()))
    with f2:
        sec_sel = st.multiselect("보안등급", sorted(df["security"].unique()))
    with f3:
        owner_sel = st.multiselect("담당자", sorted(df["owner"].unique()))
    with f4:
        query = st.text_input("검색 (제목/설명/태그)", "")

    filtered = df.copy()
    if type_sel:
        filtered = filtered[filtered["type"].isin(type_sel)]
    if sec_sel:
        filtered = filtered[filtered["security"].isin(sec_sel)]
    if owner_sel:
        filtered = filtered[filtered["owner"].isin(owner_sel)]
    if query:
        q = query.strip()
        filtered = filtered[
            filtered["title"].str.contains(q, case=False, na=False)
            | filtered["description"].str.contains(q, case=False, na=False)
            | filtered["tags"].str.contains(q, case=False, na=False)
        ]

    st.caption(f"{len(filtered)}건 표시 중 (전체 {len(df)}건) · 행을 클릭하면 설명을 볼 수 있습니다.")

    display_df = filtered[["date", "title", "type", "security", "owner", "tags"]].rename(
        columns={"date": "등록일", "title": "제목", "type": "유형", "security": "보안등급",
                 "owner": "담당자", "tags": "태그"}
    )
    event = st.dataframe(
        display_df, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
        column_config={"등록일": st.column_config.DateColumn(format="YYYY-MM-DD")},
    )

    if event.selection and event.selection.rows:
        sel_id = filtered.iloc[event.selection.rows[0]]["resource_id"]
        r = df[df["resource_id"] == sel_id].iloc[0]
        sec_tone = S.SECURITY_TONE.get(r["security"], "slate")
        S.panel_open(r["title"])
        st.markdown(
            f"{S.badge(r['type'], 'blue')} {S.badge(r['security'], sec_tone)} "
            f"<span class='dcc-muted'>{r['owner']} · {r['date'].date()}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(r["description"])
        st.markdown(S.tags_html(r["tags_list"]), unsafe_allow_html=True)
        S.panel_close()
