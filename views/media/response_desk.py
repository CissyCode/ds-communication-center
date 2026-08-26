from __future__ import annotations

import pandas as pd
import streamlit as st

from common import data as D
from common import nav as N
from common import style as S
from services import press_history_service as PHS
from services import reporter_service as RS

from . import _shared as X


def _reporter_field(key_prefix: str, reporters: list[dict], current_name: str | None = None):
    labels = ["직접 입력"] + [f"{r['name']} ({r['media']})" for r in reporters]
    default_idx = 0
    if current_name:
        for i, r in enumerate(reporters):
            if r["name"] == current_name:
                default_idx = i + 1
                break
    choice = st.selectbox("기자 (기존 선택)", labels, index=default_idx, key=f"{key_prefix}_choice")
    free_default = current_name if default_idx == 0 and current_name else ""
    free_text = st.text_input(
        "기자명 직접 입력", value=free_default, key=f"{key_prefix}_free",
        disabled=(choice != "직접 입력"),
        help="기자 DB에 없는 기자도 이름만으로 등록할 수 있습니다.",
    )
    if choice == "직접 입력":
        return None, free_text.strip()
    match = next((r for r in reporters if f"{r['name']} ({r['media']})" == choice), None)
    return (match["id"], match["name"]) if match else (None, choice)


def _create_form(reporters: list[dict]):
    with st.expander("+ 신규 문의 접수"):
        with st.form("ph_create_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                date_val = st.date_input("날짜", value=D.TODAY, key="ph_new_date")
                media_val = st.text_input("매체", key="ph_new_media")
                reporter_pk, reporter_name = _reporter_field("ph_new", reporters)
            with c2:
                type_val = st.selectbox("유형", PHS.VALID_TYPES, key="ph_new_type")
                topic_val = st.text_input("주제", key="ph_new_topic")
                status_val = st.selectbox("상태", PHS.VALID_STATUS, key="ph_new_status")
                tags_val = st.text_input("태그 (콤마로 구분)", key="ph_new_tags")
            question_val = st.text_area("문의 내용", key="ph_new_question")
            response_val = st.text_area("대응 내용", key="ph_new_response")

            if st.form_submit_button("등록"):
                try:
                    new_id = PHS.create_press_history(
                        date=date_val, media=media_val, reporter_pk=reporter_pk, reporter_name=reporter_name,
                        type_=type_val, topic=topic_val, question=question_val, response=response_val,
                        status=status_val, tags=tags_val,
                    )
                    st.success(f"{new_id} 등록 완료 — 아래 목록에 바로 반영됩니다.")
                except ValueError as e:
                    st.error(str(e))


def _edit_form(r: dict, reporters: list[dict]):
    pid = r["press_history_id"]
    with st.expander("수정"):
        with st.form(f"ph_edit_form_{pid}"):
            c1, c2 = st.columns(2)
            with c1:
                date_val = st.date_input("날짜", value=pd.to_datetime(r["date"]).date(), key=f"ph_edit_date_{pid}")
                media_val = st.text_input("매체", value=r["media"], key=f"ph_edit_media_{pid}")
                reporter_pk, reporter_name = _reporter_field(f"ph_edit_{pid}", reporters, current_name=r["reporter_name"])
            with c2:
                type_idx = PHS.VALID_TYPES.index(r["type"]) if r["type"] in PHS.VALID_TYPES else 0
                type_val = st.selectbox("유형", PHS.VALID_TYPES, index=type_idx, key=f"ph_edit_type_{pid}")
                topic_val = st.text_input("주제", value=r["topic"], key=f"ph_edit_topic_{pid}")
                status_idx = PHS.VALID_STATUS.index(r["status"]) if r["status"] in PHS.VALID_STATUS else 0
                status_val = st.selectbox("상태", PHS.VALID_STATUS, index=status_idx, key=f"ph_edit_status_{pid}")
                tags_val = st.text_input("태그 (콤마로 구분)", value=r.get("tags") or "", key=f"ph_edit_tags_{pid}")
            question_val = st.text_area("문의 내용", value=r.get("question") or "", key=f"ph_edit_question_{pid}")
            response_val = st.text_area("대응 내용", value=r.get("response") or "", key=f"ph_edit_response_{pid}")

            if st.form_submit_button("저장"):
                try:
                    PHS.update_press_history(
                        pid, date=date_val, media=media_val, reporter_pk=reporter_pk, reporter_name=reporter_name,
                        type_=type_val, topic=topic_val, question=question_val, response=response_val,
                        status=status_val, tags=tags_val,
                    )
                    st.success("수정되었습니다.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))


def render():
    S.page_title("MEDIA · Response Desk", "기자 문의 접수부터 대응 완료까지를 관리합니다. 완료된 건은 자동으로 대응 이력이 됩니다.")

    reporters = RS.list_active()
    _create_form(reporters)

    df = PHS.list_press_history()
    if df.empty:
        st.info("등록된 대응 이력이 없습니다.")
        return

    f1, f2, f3, f4 = st.columns([1, 1, 1.2, 1.4])
    with f1:
        type_sel = st.multiselect("유형", sorted(df["type"].unique()), key="ph_type")
    with f2:
        status_sel = st.multiselect("상태", sorted(df["status"].unique()), key="ph_status")
    with f3:
        media_sel = st.multiselect("매체", sorted(df["media"].unique()), key="ph_media")
    with f4:
        query = st.text_input("검색 (주제/기자)", "", key="ph_q")

    filtered = df.copy()
    if type_sel:
        filtered = filtered[filtered["type"].isin(type_sel)]
    if status_sel:
        filtered = filtered[filtered["status"].isin(status_sel)]
    if media_sel:
        filtered = filtered[filtered["media"].isin(media_sel)]
    if query:
        q = query.strip()
        filtered = filtered[
            filtered["topic"].str.contains(q, case=False, na=False)
            | filtered["reporter_name"].str.contains(q, case=False, na=False)
        ]
    filtered = filtered.sort_values("date", ascending=False)

    st.caption(f"{len(filtered)}건 표시 중 (전체 {len(df)}건) · 행을 클릭하면 상세를 볼 수 있습니다.")

    display_df = filtered[["date", "media", "reporter_name", "topic", "type", "status"]].copy()
    display_df["date"] = display_df["date"].dt.date
    display_df = display_df.rename(
        columns={"date": "일자", "media": "매체", "reporter_name": "기자", "topic": "주제", "type": "유형", "status": "상태"}
    )
    event = st.dataframe(
        display_df, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
        key="ph_select",
    )

    sel_id = X.resolve_selection(filtered, event, "press_history_id")
    if not sel_id:
        return

    r = PHS.get_press_history(sel_id)
    if r is None:
        st.warning("선택한 대응 이력을 찾을 수 없습니다 (Archive 처리되었을 수 있습니다).")
        return

    issues = D.load_issues()
    S.panel_open(f"{r['date']} · [{r['media']}] {r['reporter_name']} · {r['topic']}")

    S.section_title("기본정보")
    st.markdown(
        f"{S.badge(r['type'], 'blue')} {S.badge(r['status'], S.STATUS_TONE.get(r['status'], 'slate'))} "
        f"{S.tags_html(r['tags_list'])}",
        unsafe_allow_html=True,
    )

    S.section_title("문의 내용")
    st.markdown(r["question"] or "-")

    S.section_title("대응 내용")
    st.markdown(r["response"] or "-")

    S.section_title("관련 Issue")
    related_issue = X.press_history_related_issue(sel_id, issues)
    if related_issue is None:
        st.caption("연결된 이슈가 없습니다 (완료된 대응이거나, 신규 등록 건이라 이슈 파생 대상이 아직 아님).")
    else:
        st.markdown(
            f"{S.badge(related_issue['severity'], S.SEVERITY_TONE.get(related_issue['severity'], 'slate'))} {related_issue['title']}",
            unsafe_allow_html=True,
        )
        if st.button("이슈 상세 보기", key=f"ph_goto_issue_{sel_id}"):
            N.go_to("media_issues_risk", focus_id=related_issue["issue_id"], focus_col="issue_id")

    S.section_title("관련 기자")
    reporters_csv = D.load_reporters()
    reporter_id = X.reporter_id_by_name(r["reporter_name"], reporters_csv)
    if reporter_id is None:
        st.caption("기자 DB에서 일치하는 기자를 찾지 못했습니다.")
    else:
        st.markdown(r["reporter_name"])
        if st.button("기자 상세 보기", key=f"ph_goto_reporter_{sel_id}"):
            N.go_to("media_reporter_crm", focus_id=reporter_id, focus_col="reporter_id")

    S.panel_close()

    _edit_form(r, reporters)

    if st.button("Archive 처리", key=f"ph_archive_{sel_id}"):
        PHS.archive_press_history(sel_id)
        if "ph_select" in st.session_state:
            del st.session_state["ph_select"]
        st.success(f"{sel_id} 를 Archive 처리했습니다.")
        st.rerun()
