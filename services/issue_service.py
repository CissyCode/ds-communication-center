"""Thin stub — proves the layering exists for issues, but no view calls
this yet. 이슈 관리 leaf still reads the CSV-derived watchlist this phase."""
from __future__ import annotations

import streamlit as st

from repository import issue_repository as repo


@st.cache_data
def list_issues(include_archived: bool = False) -> list[dict]:
    return repo.get_all(include_archived=include_archived)


@st.cache_data
def get_issue(issue_id: str) -> dict | None:
    return repo.get_by_id(issue_id)
