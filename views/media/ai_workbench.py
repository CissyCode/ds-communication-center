from __future__ import annotations

import pandas as pd
import streamlit as st

from common import style as S

# The AX Activity Inventory's 26 detail agents are consolidated into these 7
# user-facing agents so the UI never exposes the raw 26. Mapping detail was
# reported separately (see the AX Activity Mapping analysis in this project's
# history) — this table is the user-facing summary of that mapping.
_AGENTS = [
    {"name": "Monitoring Agent", "desc": "언론·업계 동향 및 리스크 신호를 상시 센싱합니다.", "used_in": "Monitoring", "status": "준비 중"},
    {"name": "Research Agent", "desc": "산업·시장·경쟁사 동향을 조사·분석합니다.", "used_in": "Media Intelligence", "status": "준비 중"},
    {"name": "Issue Agent", "desc": "이슈·리스크 사안을 분석하고 대응 전략 초안을 제시합니다.", "used_in": "Issues & Risk", "status": "준비 중"},
    {"name": "Response Agent", "desc": "기자 문의 대응안 초안과 관련 자료를 찾아줍니다.", "used_in": "Response Desk · Reporter CRM", "status": "준비 중"},
    {"name": "PR Agent", "desc": "보도자료·Key Message·Q&A 초안을 작성합니다.", "used_in": "PR Planning · PR Studio", "status": "준비 중"},
    {"name": "Pitching Agent", "desc": "피칭자료와 기자별 피칭 멘트를 제안합니다.", "used_in": "PR Studio · Media Programs", "status": "준비 중"},
    {"name": "Reporting Agent", "desc": "홍보 성과를 집계하고 보고서 초안을 만듭니다.", "used_in": "Coverage & Results", "status": "준비 중"},
]

_QUICK_ACTIONS = ["동향 분석", "유사사례 검색", "대응안", "PR 초안", "Q&A", "피칭 멘트", "이슈 보고"]


def render():
    S.page_title("MEDIA · AI Workbench", "7개 AI Agent의 역할과 사용 화면을 확인하는 공간입니다 (Prototype).")
    st.caption("이번 Phase에서는 실제 AI/LLM 연결 없이 구조만 제공합니다 — 모든 버튼은 클릭 시 준비 중 안내만 표시합니다.")

    S.section_title("실행 콘솔")
    cols = st.columns(len(_QUICK_ACTIONS))
    for col, label in zip(cols, _QUICK_ACTIONS):
        with col:
            if st.button(label, key=f"wb_action_{label}"):
                st.info("AI 기능은 Prototype 단계입니다 — 실제 실행은 연결되어 있지 않습니다.")

    S.section_title("7개 Agent")
    st.dataframe(
        pd.DataFrame(_AGENTS).rename(
            columns={"name": "Agent", "desc": "하는 일", "used_in": "사용 화면", "status": "상태"}
        ),
        hide_index=True, use_container_width=True, height=280,
    )

    S.section_title("결과 로그")
    st.caption("아직 실행된 Agent가 없습니다 — 실제 연결 후 이 화면에 요청/결과 이력이 쌓입니다.")
