from __future__ import annotations

import streamlit as st

from common import style as S
from views.media import coverage, intelligence, issues, overview, press_history, press_releases, programs, reporters

GROUP_CHILDREN = {
    "Overview": ["Overview"],
    "업무": ["대응 이력", "기자 DB"],
    "이슈 / PR": ["이슈 관리", "보도자료", "보도 현황"],
    "프로그램": ["미디어 프로그램"],
    "분석": ["Media Intelligence"],
}
LEAF_TO_GROUP = {leaf: g for g, leaves in GROUP_CHILDREN.items() for leaf in leaves}
LEAF_RENDERERS = {
    "Overview": overview.render,
    "대응 이력": press_history.render,
    "기자 DB": reporters.render,
    "이슈 관리": issues.render,
    "보도자료": press_releases.render,
    "보도 현황": coverage.render,
    "미디어 프로그램": programs.render,
    "Media Intelligence": intelligence.render,
}


def _resolved(current: str | None, fallback_key: str, default: str) -> str:
    """segmented_control returns None if its selected pill is clicked again
    (deselected); fall back to the last known-good choice instead of losing
    the whole sub-nav."""
    if current:
        st.session_state[fallback_key] = current
        return current
    return st.session_state.get(fallback_key, default)


def render():
    S.page_title("MEDIA", "전통 매체 대응, 기자 관계, 이슈·프로그램을 관리합니다.")

    # One-shot deep-link request from another page (or from within MEDIA
    # itself via common.nav.jump_media) — consumed immediately.
    requested = st.session_state.get("media_leaf_request")
    if requested:
        del st.session_state["media_leaf_request"]
        if requested in LEAF_TO_GROUP:
            st.session_state["media_group_widget"] = LEAF_TO_GROUP[requested]
            st.session_state["media_leaf_widget"] = requested

    group_result = st.segmented_control(
        "MEDIA 메뉴", list(GROUP_CHILDREN.keys()), key="media_group_widget", label_visibility="collapsed",
    )
    group = _resolved(group_result, "media_group_last", "Overview")

    children = GROUP_CHILDREN[group]
    if len(children) > 1:
        leaf_result = st.segmented_control(
            "MEDIA 하위 메뉴", children, key="media_leaf_widget", label_visibility="collapsed",
        )
        leaf = _resolved(leaf_result, "media_leaf_last", children[0])
        if leaf not in children:
            leaf = children[0]
    else:
        leaf = children[0]

    st.markdown('<div class="dcc-hr"></div>', unsafe_allow_html=True)
    LEAF_RENDERERS[leaf]()
