"""Thin stub — proves the layering exists for press_releases, but no view
calls this yet. 보도자료 leaf still reads the CSV/schedule-derived log this phase."""
from __future__ import annotations

import streamlit as st

from repository import press_release_repository as repo


@st.cache_data
def list_press_releases(include_archived: bool = False) -> list[dict]:
    return repo.get_all(include_archived=include_archived)


@st.cache_data
def get_press_release(press_release_id: str) -> dict | None:
    return repo.get_by_id(press_release_id)
