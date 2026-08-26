from __future__ import annotations

from datetime import timedelta

import streamlit as st

from common import data as D
from common import nav as N
from common import style as S

_UPDATE_TARGET = {
    "MEDIA": "media_dashboard", "NEW MEDIA": "new_media", "MARCOM": "marcom",
    "RESOURCES": "resources", "공지": "media_dashboard",
}


def render():
    S.app_name()
    S.page_title("HOME", "오늘 무엇을 보고 어디로 가야 하는지 알려주는 커뮤니케이션 운영 현황판입니다.")

    # Load every source once; every block below reuses these same frames
    # rather than re-calling a loader (st.cache_data already makes repeat
    # calls cheap, but this keeps one render to one call per source).
    press = D.load_press_history()
    schedule = D.load_schedule()
    issues = D.load_issues()
    nm_content = D.load_new_media_content()
    nm_series = D.load_new_media_series()
    press_releases = D.load_press_releases()
    mc_projects = D.load_marcom_projects()
    mc_campaigns = D.load_marcom_campaigns()
    mc_events = D.load_marcom_events()
    updates = D.load_recent_updates(limit=8)

    today = D.TODAY
    week_start = today - timedelta(days=6)

    in_progress_press = (press["status"] == "진행 중").sum()
    active_projects = (mc_projects["status"] == "진행 중").sum()
    active_campaigns = (mc_campaigns["status"] == "진행 중").sum()
    content_recent = nm_content[(nm_content["date"].dt.date >= week_start) & (nm_content["date"].dt.date <= today)]

    todays = schedule[(schedule["start_date"].dt.date <= today) & (schedule["end_date"].dt.date >= today)]
    upcoming = schedule[schedule["start_date"].dt.date >= today].sort_values("start_date")

    # ---- Priority strip: active/open-state signals, not month-total vanity metrics ----
    S.stat_strip([
        ("오늘 일정" if not todays.empty else "다가오는 일정", f"{len(todays) if not todays.empty else len(upcoming)}", "건"),
        ("진행 중 이슈", f"{len(issues)}", "건"),
        ("진행 중 대응", f"{in_progress_press}", "건"),
        ("최근 7일 콘텐츠", f"{len(content_recent)}", "건"),
        ("진행 중 MARCOM", f"{active_projects + active_campaigns}", "건"),
    ])

    row1_l, row1_r = st.columns(2)

    with row1_l:
        S.section_title("Today's Schedule")
        if todays.empty:
            st.caption(f"오늘({today}) 예정된 일정이 없어 다가오는 일정을 표시합니다.")
            rows_to_show = upcoming.head(5)
        else:
            rows_to_show = todays
        for _, r in rows_to_show.iterrows():
            S.list_row(f"[{r['category']}] {r['title']}", r["time_label"])
        if st.button("SCHEDULE 보기", key="home_goto_schedule"):
            N.go_to("schedule")

    with row1_r:
        S.section_title("Priority / Issues")
        if issues.empty:
            st.caption("현재 관리 중인 이슈가 없습니다.")
        else:
            top_issues = issues.head(5)
            show = top_issues[["severity", "source", "title"]].rename(
                columns={"severity": "심각도", "source": "구분", "title": "제목"}
            )
            event = st.dataframe(
                show, hide_index=True, use_container_width=True, height=200,
                on_select="rerun", selection_mode="single-row", key="home_issues_select",
            )
            if event.selection and event.selection.rows:
                sel_issue_id = top_issues.iloc[event.selection.rows[0]]["issue_id"]
                del st.session_state["home_issues_select"]
                N.go_to("media_issues_risk", focus_id=sel_issue_id, focus_col="issue_id")
            st.caption("행을 클릭하면 MEDIA > Issues & Risk로 이동합니다.")

    row2_l, row2_m, row2_r = st.columns(3)

    with row2_l:
        S.section_title("MEDIA")
        S.list_row("진행 중 대응", f"{in_progress_press}건")
        S.list_row("주요 이슈", f"{len(issues)}건")
        S.list_row("예정 보도자료", f"{(press_releases['status'] == '배포 예정').sum()}건")
        if st.button("MEDIA 보기", key="home_goto_media"):
            N.go_to("media_dashboard")

    with row2_m:
        S.section_title("NEW MEDIA")
        S.list_row("진행 중 시리즈", f"{(nm_series['status'] == '진행 중').sum()}건")
        S.list_row("최근 7일 게시", f"{len(content_recent)}건")
        S.list_row("평균 Engagement", f"{nm_content['engagement_rate'].mean():.1f}%")
        if st.button("NEW MEDIA 보기", key="home_goto_newmedia"):
            N.go_to("new_media")

    with row2_r:
        S.section_title("MARCOM")
        S.list_row("진행 Project", f"{active_projects}건")
        S.list_row("진행 Campaign", f"{active_campaigns}건")
        S.list_row("예정 Event", f"{len(mc_events)}건")
        if st.button("MARCOM 보기", key="home_goto_marcom"):
            N.go_to("marcom")

    S.section_title("최근 업데이트")
    show_u = updates.copy()
    show_u["date"] = show_u["date"].dt.date
    event = st.dataframe(
        show_u.rename(columns={"date": "일자", "module": "모듈", "title": "내용"}),
        hide_index=True, use_container_width=True, height=230,
        on_select="rerun", selection_mode="single-row", key="home_updates_select",
    )
    if event.selection and event.selection.rows:
        module = updates.iloc[event.selection.rows[0]]["module"]
        target = _UPDATE_TARGET.get(module)
        del st.session_state["home_updates_select"]
        if target:
            N.go_to(target)
    st.caption("행을 클릭하면 해당 모듈로 이동합니다.")
