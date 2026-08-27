"""Page-switch helpers. Every leaf (including each MEDIA sub-screen) is its own
st.Page with its own route, so a deep-link is just a page-key lookup.

Two ways to travel, used for different jobs:

* `href()` builds a plain URL. Dashboards use it, because a link reaches the
  target page directly while a button costs a rerun to compute the same jump —
  and a link can wrap a whole row instead of sitting beside it.
* `go_to()` switches from inside a callback/branch, for places where the jump
  is decided by a widget event (a dataframe row selection) rather than a click
  on a known target.

Both carry the same optional focus request (open this record's detail on
arrival). `href` passes it in the query string; `go_to` puts it in session
state. `views/media/_shared.consume_focus` reads either.
"""
from __future__ import annotations

from urllib.parse import urlencode

import streamlit as st

_KEY = "_nav_pages"


def register(pages: dict) -> None:
    st.session_state[_KEY] = pages


def _page(page_key: str):
    return st.session_state.get(_KEY, {}).get(page_key)


def href(page_key: str, focus_id: str | None = None, focus_col: str | None = None) -> str:
    """URL for another page, relative to the app root.

    Every route is a single path segment (`/media-issues-risk`), so a relative
    href resolves correctly from any page and keeps working when the app is
    served under a sub-path.
    """
    page = _page(page_key)
    if page is None:
        return "#"
    # st.navigation serves the default page at "/" and reports an empty
    # url_path for it, so linking to its declared path would 404.
    url = page.url_path or "./"
    if focus_id is not None:
        params = {"focus": focus_id}
        if focus_col:
            params["focus_col"] = focus_col
        url = f"{url}?{urlencode(params)}"
    return url


def go_to(page_key: str, focus_id: str | None = None, focus_col: str | None = None) -> None:
    """Switch to another page, optionally leaving a one-shot focus request
    for that page to pick up (e.g. pre-opening one entity's detail panel)."""
    if focus_id is not None:
        st.session_state["media_focus"] = {"col": focus_col, "id": focus_id}
    page = _page(page_key)
    if page is not None:
        st.switch_page(page)
