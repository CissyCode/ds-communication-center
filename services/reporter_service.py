"""Thin read layer over reporter_repository — just enough to power the
'기존 Reporter 선택' picker in press_history_service. No create/update UI
this phase."""
from __future__ import annotations

import streamlit as st

from repository import reporter_repository as repo


@st.cache_data
def list_active() -> list[dict]:
    return [r for r in repo.get_all(include_archived=False) if r["status"] == "활성"]
