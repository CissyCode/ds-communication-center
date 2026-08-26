from __future__ import annotations

from datetime import timedelta

import streamlit as st

from common import data as D
from common import nav as N
from common import style as S


def render():
    S.page_title("MEDIA · Dashboard", "미디어그룹의 오늘 업무 현황을 한눈에 확인합니다.")

    press = D.load_press_history()
    issues = D.load_issues()
    releases = D.load_press_releases()
    programs = D.load_media_programs()
    contacts = D.load_contact_history()
    monitoring = D.load_media_monitoring()

    in_progress = press[press["status"] == "진행 중"]
    awaiting_facts = in_progress[in_progress["response"].fillna("").str.strip() == ""]
    awaiting_reply = in_progress[in_progress["response"].fillna("").str.strip() != ""]
    high_risk = issues[issues["severity"] == "HIGH"]
    pr_review_pending = releases[releases["status"] == "배포 예정"]

    S.section_title("NEED ATTENTION")
    S.stat_strip([
        ("사실확인 대기", f"{len(awaiting_facts)}", "건"),
        ("회신 대기", f"{len(awaiting_reply)}", "건"),
        ("PR Review 대기", f"{len(pr_review_pending)}", "건"),
        ("HIGH Risk", f"{len(high_risk)}", "건"),
    ])
    st.caption("사실확인 대기·회신 대기는 대응 이력의 문의/응답 필드 기준 근사치입니다 — 정식 진행 단계 구분은 이후 Phase에서 도입됩니다.")

    row1_l, row1_r = st.columns(2)

    with row1_l:
        S.section_title("Response Desk 대기열")
        queue = in_progress.sort_values("date", ascending=False).head(5)
        if queue.empty:
            st.caption("대기 중인 문의가 없습니다.")
        for _, r in queue.iterrows():
            state = "사실확인 대기" if not str(r.get("response") or "").strip() else "회신 대기"
            S.list_row(f"[{r['type']}] {r['media']} · {r['topic']}", state)
        if st.button("Response Desk 전체 보기", key="dash_goto_response_desk"):
            N.go_to("media_response_desk")

    with row1_r:
        S.section_title("Issues & Risk 진행 현황")
        top_issues = issues.head(5)
        if top_issues.empty:
            st.caption("현재 관리 중인 이슈가 없습니다.")
        for _, r in top_issues.iterrows():
            tone = S.SEVERITY_TONE.get(r["severity"], "slate")
            st.markdown(f"{S.badge(r['severity'], tone)} {r['title']}", unsafe_allow_html=True)
        if st.button("Issues & Risk 전체 보기", key="dash_goto_issues_risk"):
            N.go_to("media_issues_risk")

    row2_l, row2_r = st.columns(2)

    with row2_l:
        S.section_title("PR Studio 진행 중")
        if pr_review_pending.empty:
            st.caption("배포 예정인 보도자료가 없습니다.")
        for _, r in pr_review_pending.sort_values("date").head(5).iterrows():
            S.list_row(r["title"], str(r["date"].date()))
        if st.button("PR Studio 전체 보기", key="dash_goto_pr_studio"):
            N.go_to("media_pr_studio")

    with row2_r:
        S.section_title("Media Programs 예정")
        upcoming_programs = programs[programs["start_date"].dt.date >= D.TODAY].sort_values("start_date")
        if upcoming_programs.empty:
            st.caption("예정된 프로그램이 없습니다.")
        for _, r in upcoming_programs.head(5).iterrows():
            S.list_row(r["title"], str(r["start_date"].date()))
        if st.button("Media Programs 전체 보기", key="dash_goto_programs"):
            N.go_to("media_programs")

    row3_l, row3_r = st.columns(2)

    with row3_l:
        S.section_title("Reporter CRM Highlights")
        recent_contacts = contacts.sort_values("date", ascending=False).head(5)
        if recent_contacts.empty:
            st.caption("최근 접촉 이력이 없습니다.")
        for _, r in recent_contacts.iterrows():
            S.list_row(f"{r['reporter']} · {r['subject']}", str(r["date"].date()))
        if st.button("Reporter CRM 전체 보기", key="dash_goto_reporter_crm"):
            N.go_to("media_reporter_crm")

    with row3_r:
        S.section_title("Coverage & Results 금주 요약")
        week_start = D.TODAY - timedelta(days=6)
        week_cov = monitoring[(monitoring["date"].dt.date >= week_start) & (monitoring["date"].dt.date <= D.TODAY)]
        pos = (week_cov["sentiment"] == "긍정").sum()
        neg = (week_cov["sentiment"] == "부정").sum()
        S.stat_strip([
            ("이번 주 보도", f"{len(week_cov)}", "건"),
            ("긍정", f"{pos}", "건"),
            ("부정", f"{neg}", "건"),
        ])
        if st.button("Coverage & Results 전체 보기", key="dash_goto_coverage"):
            N.go_to("media_coverage_results")
