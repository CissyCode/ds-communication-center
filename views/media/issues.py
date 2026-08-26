from __future__ import annotations

import streamlit as st

from common import data as D
from common import nav as N
from common import style as S

from . import _shared as X


def _timeline(origin_date, origin_label, press_hit, monitoring_hit):
    points = [(origin_date, origin_label)]
    for _, r in press_hit.iterrows():
        points.append((r["date"], f"관련 대응 · [{r['media']}] {r['topic']}"))
    for _, r in monitoring_hit.iterrows():
        points.append((r["date"], f"관련 보도 · [{r['media']}] {r['headline']}"))
    points.sort(key=lambda t: t[0])
    return points[:8]


def render():
    df = D.load_issues()
    st.caption("첨부 데이터에 별도 이슈 관리 항목이 없어, 미해결 대응·긴급 공지·부정 보도를 하나의 워치리스트로 재구성했습니다.")

    if df.empty:
        st.info("현재 관리 중인 이슈가 없습니다.")
        return

    src_sel = st.multiselect("구분", sorted(df["source"].unique()), key="is_src")
    filtered = df[df["source"].isin(src_sel)] if src_sel else df

    show = filtered.copy()
    show["date"] = show["date"].dt.date
    event = st.dataframe(
        show[["severity", "date", "source", "media", "title"]].rename(
            columns={"severity": "심각도", "date": "일자", "source": "구분", "media": "매체/출처", "title": "제목"}
        ),
        hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row", key="is_select",
    )

    sel_id = X.resolve_selection(filtered, event, "issue_id")
    if not sel_id:
        return

    r = df[df["issue_id"] == sel_id].iloc[0]
    press = D.load_press_history()
    monitoring = D.load_media_monitoring()
    reporters = D.load_reporters()
    resources = D.load_resources()
    releases = D.load_press_releases()

    tags = X.issue_topic_tags(r, press, monitoring)
    related = X.related_by_tags(tags, press, monitoring, reporters, resources)
    release_hit = releases[releases["title"].apply(lambda t: any(tag in t for tag in tags))] if tags else releases.iloc[0:0]

    S.panel_open(r["title"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"**Severity**  \n{S.badge(r['severity'], S.SEVERITY_TONE.get(r['severity'], 'slate'))}", unsafe_allow_html=True)
    with c2:
        st.markdown(f"**Status**  \n진행 중")
    with c3:
        st.markdown("**Owner**  \n-")
    with c4:
        st.markdown(f"**Started**  \n{r['date'].date()}")

    S.section_title("SUMMARY")
    st.markdown(r["detail"])

    if r["source"] == "미해결 대응":
        base_id = r["issue_id"].split("PH-", 1)[1]
        origin = press[press["press_history_id"] == base_id]
        if not origin.empty and isinstance(origin.iloc[0]["response"], str) and origin.iloc[0]["response"].strip():
            S.section_title("KEY MESSAGE")
            st.markdown(origin.iloc[0]["response"])

    if not tags:
        st.caption("이 이슈는 사내 공지 기반으로, 태그 연결 정보가 없어 아래 TIMELINE·RELATED MEDIA는 원본 항목만 표시합니다.")

    S.section_title("TIMELINE")
    for d, label in _timeline(r["date"], f"이슈 등록 · {r['title']}", related["press"], related["monitoring"]):
        st.markdown(f"**{d.date() if hasattr(d, 'date') else d}** · {label}")

    S.section_title("RELATED MEDIA")
    S.stat_strip([
        ("대응 이력", f"{len(related['press'])}", "건"),
        ("기자", f"{len(related['reporters'])}", "명"),
        ("보도", f"{len(related['monitoring'])}", "건"),
        ("보도자료", f"{len(release_hit)}", "건"),
        ("자료", f"{len(related['resources'])}", "건"),
    ])

    if len(related["press"]):
        st.markdown("**관련 대응**")
        for _, pr in related["press"].iterrows():
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"{pr['date'].date()} · [{pr['media']}] {pr['topic']}")
            with c2:
                if st.button("보기", key=f"is_goto_press_{pr['press_history_id']}"):
                    N.jump_media("대응 이력", focus_id=pr["press_history_id"], focus_col="press_history_id")

    if len(related["reporters"]):
        st.markdown("**관련 기자**")
        for _, rp in related["reporters"].iterrows():
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"{rp['name']} · {rp['media']}")
            with c2:
                if st.button("보기", key=f"is_goto_reporter_{rp['reporter_id']}"):
                    N.jump_media("기자 DB", focus_id=rp["reporter_id"], focus_col="reporter_id")

    if len(related["monitoring"]):
        st.markdown("**관련 보도**")
        for _, mo in related["monitoring"].iterrows():
            tone = S.SENTIMENT_TONE.get(mo["sentiment"], "slate")
            st.markdown(f"{mo['date'].date()} · [{mo['media']}] {mo['headline']} {S.badge(mo['sentiment'], tone)}", unsafe_allow_html=True)

    if len(release_hit):
        st.markdown("**관련 보도자료**")
        for _, rel in release_hit.iterrows():
            st.markdown(f"{rel['date'].date()} · {rel['title']} {S.badge(rel['status'], S.STATUS_TONE.get(rel['status'], 'slate'))}", unsafe_allow_html=True)

    if len(related["resources"]):
        st.markdown("**관련 자료**")
        for _, res in related["resources"].iterrows():
            st.markdown(f"{res['title']} {S.badge(res['security'], S.SECURITY_TONE.get(res['security'], 'slate'))}", unsafe_allow_html=True)

    S.panel_close()
