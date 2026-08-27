"""Cross-linking helpers used only within the MEDIA package.

None of these touch common/data.py — they're presentation-adjacent
computations specific to how MEDIA's own screens relate to each other
(issue ↔ press history ↔ reporter ↔ coverage ↔ press release), built on
tags/topics/title keywords since no real relation DB exists yet. Kept out
of common/data.py on purpose so that module doesn't keep growing with
derived logic that only one page needs.
"""
from __future__ import annotations

import streamlit as st


def consume_focus(id_col: str) -> str | None:
    """Return + clear a pending cross-leaf focus request if it targets this id column.

    Two carriers, because the app links two ways: session state (a widget event
    routed through nav.go_to) and the query string (a dashboard anchor built by
    nav.href). Both are one-shot — cleared on read so the detail panel stays
    closable instead of reopening on every rerun.
    """
    focus = st.session_state.get("media_focus")
    if focus and focus.get("col") == id_col:
        del st.session_state["media_focus"]
        return focus["id"]

    params = st.query_params
    if "focus" in params and params.get("focus_col", id_col) == id_col:
        focus_id = params["focus"]
        st.query_params.clear()
        return focus_id
    return None


def resolve_selection(filtered, event, id_col: str) -> str | None:
    """A dataframe row click OR a pending deep-link focus — whichever fired."""
    if event.selection and event.selection.rows:
        return filtered.iloc[event.selection.rows[0]][id_col]
    return consume_focus(id_col)


def issue_topic_tags(issue_row, press_df, monitoring_df) -> set[str]:
    """The tag set an issue is 'about', taken from its originating record.
    운영 공지-sourced issues have no tags anywhere in the data, so they get
    an empty set rather than an invented one — no relations are shown for them."""
    source = issue_row["source"]
    if source == "미해결 대응":
        base_id = issue_row["issue_id"].split("PH-", 1)[1]
        match = press_df[press_df["press_history_id"] == base_id]
        return set(match.iloc[0]["tags_list"]) if not match.empty else set()
    if source == "부정 보도":
        base_id = issue_row["issue_id"].split("MM-", 1)[1]
        match = monitoring_df[monitoring_df["monitoring_id"] == base_id]
        return set(match.iloc[0]["tags_list"]) if not match.empty else set()
    return set()


def related_by_tags(tags: set[str], press_df, monitoring_df, reporters_df, resources_df) -> dict:
    if not tags:
        return {
            "press": press_df.iloc[0:0], "monitoring": monitoring_df.iloc[0:0],
            "reporters": reporters_df.iloc[0:0], "resources": resources_df.iloc[0:0],
        }
    return {
        "press": press_df[press_df["tags_list"].apply(lambda ts: bool(tags & set(ts)))],
        "monitoring": monitoring_df[monitoring_df["tags_list"].apply(lambda ts: bool(tags & set(ts)))],
        "reporters": reporters_df[reporters_df["topics_list"].apply(lambda ts: bool(tags & set(ts)))],
        "resources": resources_df[resources_df["tags_list"].apply(lambda ts: bool(tags & set(ts)))],
    }


def release_related_issue(title: str, issues_df, press_df, monitoring_df):
    """Best-effort link from a press release (title only, no tags of its own)
    back to an open issue, via substring match against that issue's tags."""
    for _, iss in issues_df.iterrows():
        tags = issue_topic_tags(iss, press_df, monitoring_df)
        if any(t in title for t in tags):
            return iss, tags
    return None, set()


def press_history_related_issue(press_history_id: str, issues_df):
    match = issues_df[issues_df["issue_id"] == f"PH-{press_history_id}"]
    return match.iloc[0] if not match.empty else None


def monitoring_related_issue(monitoring_id: str, issues_df):
    match = issues_df[issues_df["issue_id"] == f"MM-{monitoring_id}"]
    return match.iloc[0] if not match.empty else None


def reporter_id_by_name(name: str, reporters_df) -> str | None:
    match = reporters_df[reporters_df["name"] == name]
    return match.iloc[0]["reporter_id"] if not match.empty else None
