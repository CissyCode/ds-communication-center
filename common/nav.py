"""Minimal page-switch helper so HOME/INSIGHTS can deep-link to a
top-level module without duplicating st.Page wiring or growing
session_state beyond one registry entry."""
from __future__ import annotations

import streamlit as st

_KEY = "_nav_pages"


def register(pages: dict) -> None:
    st.session_state[_KEY] = pages


def go_to(page_key: str) -> None:
    pages = st.session_state.get(_KEY, {})
    page = pages.get(page_key)
    if page is not None:
        st.switch_page(page)


def _set_media_intent(leaf: str, focus_id: str | None, focus_col: str | None) -> None:
    st.session_state["media_leaf_request"] = leaf
    if focus_id is not None:
        st.session_state["media_focus"] = {"col": focus_col, "id": focus_id}


def go_to_media(leaf: str, focus_id: str | None = None, focus_col: str | None = None) -> None:
    """Deep-link from another page into MEDIA at a specific internal leaf,
    optionally pre-opening one entity's detail there."""
    _set_media_intent(leaf, focus_id, focus_col)
    go_to("media")


def jump_media(leaf: str, focus_id: str | None = None, focus_col: str | None = None) -> None:
    """Switch MEDIA's own internal leaf/focus while already on the MEDIA page."""
    _set_media_intent(leaf, focus_id, focus_col)
    st.rerun()
