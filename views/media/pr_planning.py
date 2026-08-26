from __future__ import annotations

import streamlit as st

from common import style as S

# Prototype-only fake candidates — no "홍보 아이템" entity exists in the
# attached FAKE DATA, so this workflow is illustrated with hardcoded sample
# rows rather than a new CSV. Not persisted, not wired to PR Studio yet.
_CANDIDATES = [
    {
        "name": "차세대 AI 메모리 신제품 공개",
        "trend": "AI 메모리 수요 증가 관련 보도 최근 2주 12건",
        "past_pr": "작년 동급 신제품 발표 시 보도 34건 · 긍정 68%",
        "interest": "높음",
        "key_message_draft": "AI 시대 메모리 병목을 해소하는 차세대 아키텍처를 제시합니다. (AI 초안)",
    },
    {
        "name": "패키징 공정 협력 파트너십",
        "trend": "패키징 관련 업계 동향 기사 최근 2주 5건",
        "past_pr": "2년 전 유사 파트너십 발표 시 보도 9건",
        "interest": "중간",
        "key_message_draft": "첨단 패키징 공동 개발로 성능·수율을 동시에 개선합니다. (AI 초안)",
    },
    {
        "name": "온디바이스 AI 응용처 확대 기술 브리핑",
        "trend": "온디바이스 AI 키워드 언급 최근 2주 7건",
        "past_pr": "관련 기술설명회 이력 없음",
        "interest": "중간",
        "key_message_draft": "온디바이스 AI 저전력 솔루션의 실사용 적용 사례를 소개합니다. (AI 초안)",
    },
]


def render():
    S.page_title("MEDIA · PR Planning", "홍보 아이템 후보 발굴부터 전략·Key Message 수립까지의 단계입니다.")
    st.caption("Prototype 화면입니다 — 아래 후보는 예시 데이터이며 저장되지 않습니다.")

    for i, item in enumerate(_CANDIDATES):
        S.panel_open(item["name"])

        st.markdown(f"{S.badge('AI Assist', 'blue')} 관련 동향·자료 / 과거 유사 홍보 / 언론 관심도", unsafe_allow_html=True)
        st.markdown(f"- **관련 동향/자료**: {item['trend']}")
        st.markdown(f"- **과거 유사 홍보**: {item['past_pr']}")
        st.markdown(f"- **언론 관심도**: {S.badge(item['interest'], {'높음': 'green', '중간': 'amber', '낮음': 'slate'}.get(item['interest'], 'slate'))}", unsafe_allow_html=True)

        st.markdown(f"{S.badge('Human Decision', 'red')} 홍보 적합성 / 우선순위 판단", unsafe_allow_html=True)
        st.selectbox(
            "우선순위 (담당자 판단, 미저장)", ["미정", "상", "중", "하"],
            key=f"prp_priority_{i}", label_visibility="visible",
        )

        st.markdown(f"{S.badge('AI Assist', 'blue')} Key Message 초안", unsafe_allow_html=True)
        st.markdown(f"> {item['key_message_draft']}")

        st.button("PR Studio로 전달 (준비 중)", key=f"prp_send_{i}", disabled=True)

        S.panel_close()
