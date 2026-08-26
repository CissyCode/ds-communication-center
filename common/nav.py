"""Page-switch helper. Every leaf (including each MEDIA sub-screen) is now
its own st.Page with its own route, so a deep-link is just a page-key lookup
+ switch_page — no more internal "which leaf is MEDIA showing" indirection."""
from __future__ import annotations

import streamlit as st

_KEY = "_nav_pages"


def register(pages: dict) -> None:
    st.session_state[_KEY] = pages


def go_to(page_key: str, focus_id: str | None = None, focus_col: str | None = None) -> None:
    """Switch to another page, optionally leaving a one-shot focus request
    for that page to pick up (e.g. pre-opening one entity's detail panel)."""
    if focus_id is not None:
        st.session_state["media_focus"] = {"col": focus_col, "id": focus_id}
    pages = st.session_state.get(_KEY, {})
    page = pages.get(page_key)
    if page is not None:
        st.switch_page(page)
