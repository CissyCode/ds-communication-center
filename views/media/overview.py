from __future__ import annotations

import pandas as pd
import streamlit as st

from common import data as D
from common import nav as N
from common import style as S

from . import _shared as X


def render():
    press = D.load_press_history()
    reporters = D.load_reporters()
    contacts = D.load_contact_history()
    monitoring = D.load_media_monitoring()
    resources = D.load_resources()
    issues = D.load_issues()
    releases = D.load_press_releases()
    programs = D.load_media_programs()

    in_progress = press[press["status"] == "진행 중"].sort_values("date", ascending=False)
    high_priority = (issues["severity"] == "HIGH").sum()
    upcoming_releases = releases[releases["status"] == "배포 예정"]

    S.section_title("TODAY")
    S.stat_strip([
        ("진행 대응", f"{len(in_progress)}", "건"),
        ("High Priority Issue", f"{high_priority}", "건"),
        ("예정 PR", f"{len(upcoming_releases)}", "건"),
    ])

    row1_l, row1_r = st.columns(2)

    with row1_l:
        S.section_title("진행 중 대응")
        if in_progress.empty:
            st.caption("진행 중인 대응이 없습니다.")
        else:
            show = in_progress.head(5)[["press_history_id", "date", "media", "topic"]].copy()
            show["date"] = show["date"].dt.date
            event = st.dataframe(
                show[["date", "media", "topic"]].rename(columns={"date": "일자", "media": "매체", "topic": "주제"}),
                hide_index=True, use_container_width=True, height=200,
                on_select="rerun", selection_mode="single-row", key="ov_press_select",
            )
            sel_id = X.resolve_selection(show, event, "press_history_id")
            if sel_id:
                N.jump_media("대응 이력", focus_id=sel_id, focus_col="press_history_id")
        st.caption("행을 클릭하면 대응 이력 상세로 이동합니다.")

    with row1_r:
        S.section_title("Priority Issues")
        if issues.empty:
            st.caption("현재 관리 중인 이슈가 없습니다.")
        else:
            rows = []
            for _, iss in issues.head(5).iterrows():
                tags = X.issue_topic_tags(iss, press, monitoring)
                related = X.related_by_tags(tags, press, monitoring, reporters, resources)
                rows.append({
                    "issue_id": iss["issue_id"], "심각도": iss["severity"],
                    "제목": iss["title"], "관련 대응": len(related["press"]),
                })
            show = pd.DataFrame(rows)
            event = st.dataframe(
                show[["심각도", "제목", "관련 대응"]], hide_index=True, use_container_width=True, height=200,
                on_select="rerun", selection_mode="single-row", key="ov_issue_select",
            )
            sel_id = X.resolve_selection(show, event, "issue_id")
            if sel_id:
                N.jump_media("이슈 관리", focus_id=sel_id, focus_col="issue_id")
        st.caption("행을 클릭하면 이슈 관리 상세로 이동합니다.")

    row2_l, row2_r = st.columns(2)

    with row2_l:
        S.section_title("Upcoming")
        upcoming_rows = []
        for _, r in upcoming_releases.iterrows():
            upcoming_rows.append((r["date"].date(), "보도자료", r["title"]))
        for _, r in programs[programs["start_date"].dt.date >= D.TODAY].iterrows():
            upcoming_rows.append((r["start_date"].date(), "미디어 프로그램", r["title"]))
        upcoming_rows.sort(key=lambda t: t[0])
        if not upcoming_rows:
            st.caption("예정된 보도자료·프로그램이 없습니다.")
        for d, kind, title in upcoming_rows[:5]:
            S.list_row(f"{title}", f"{d} · {kind}")

    with row2_r:
        S.section_title("Recent Media Activity")
        feed = []
        for _, r in press.sort_values("date", ascending=False).head(5).iterrows():
            feed.append((r["date"], f"[대응] {r['media']} · {r['topic']}"))
        for _, r in monitoring.sort_values("date", ascending=False).head(5).iterrows():
            feed.append((r["date"], f"[보도] {r['media']} · {r['headline']}"))
        for _, r in contacts.sort_values("date", ascending=False).head(5).iterrows():
            feed.append((r["date"], f"[접촉] {r['reporter']} · {r['subject']}"))
        feed.sort(key=lambda t: t[0], reverse=True)
        if not feed:
            st.caption("최근 활동이 없습니다.")
        for d, label in feed[:5]:
            S.list_row(label, str(d.date()))
