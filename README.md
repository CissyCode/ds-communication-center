# DS COMMUNICATION CENTER (Prototype)

DS PR Hub 확장안 "DS Communication Center"의 UI/UX·정보구조 검증용 클릭 프로토타입입니다.
데이터는 대부분 `data/` 폴더의 가상(FAKE) CSV이며, 실제 회사/기자/언론사 정보는 포함하지 않습니다.

## 실행 방법

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run main.py
```

첫 실행 시 `storage/communication_center.db`(SQLite)가 자동으로 생성되고 FAKE DATA로 시드됩니다(수동 스크립트 실행 불필요).

## 사이트 구조

- **HOME** — 오늘 확인할 일정·이슈·모듈 현황을 모은 운영 현황판, 각 모듈로 딥링크
- **MEDIA** — 대응 이력 / 기자 DB / 이슈 관리 / 보도자료 / 보도 현황 / 미디어 프로그램 / Media Intelligence (내부 세그먼트 네비게이션)
- **NEW MEDIA** — 콘텐츠 / 채널 / 시리즈 기획 / Analytics
- **MARCOM** — Projects / Campaigns / Events / Assets / Analytics
- **SCHEDULE** — 전 모듈이 참조하는 단일 Master Schedule (리스트/캘린더 뷰)
- **INSIGHTS** — MEDIA·NEW MEDIA·MARCOM을 연결해서 보는 통합 분석
- **RESOURCES** — 자료실

## 대시보드 설계

HOME과 MEDIA · Dashboard는 "보고서"가 아니라 **디스패처**로 설계되어 있습니다.
읽는 순서 자체가 설계입니다.

| 층 | 영역 | 답하는 질문 | 컴포넌트 |
| --- | --- | --- | --- |
| 3초 | Attention Rail | 지금 결정이 필요한 건은? | `ui.alerts` (최대 4건, 심각도·경과일 순) |
| 30초 | KPI Strip | 나를 기다리는 일이 몇 건인가? | `ui.kpi_row` |
| 3분 | Board | 각 모듈은 어떤 상태인가? | `ui.board` + `ui.column` + `ui.panel` |

설계 원칙 5가지:

1. **모든 숫자는 열린 일감** — 월 누계 같은 허영 지표를 두지 않습니다. 타일은 언제나
   "몇 건이 대기 중인가"에 답하고, 그래서 항상 클릭해서 들어갈 곳이 있습니다.
2. **모든 행은 링크** — 버튼 대신 앵커(`nav.href`)를 씁니다. 버튼은 링크가 바로 가는 곳을
   계산하려고 서버 rerun을 한 번 쓰고, 링크는 행 전체를 클릭 대상으로 만들 수 있습니다.
   `?focus=<id>`로 도착 화면의 상세 패널까지 바로 엽니다.
3. **색은 5가지 상태뿐** — `crit / warn / ok / info / idle`. 색은 언제나 상태를 뜻하므로
   여섯 번째 색을 추가한다는 것은 여섯 번째 상태를 만든다는 뜻입니다.
4. **미터는 반드시 분모가 있는 비율** — `대응 종결 7/10`처럼 분모를 밝힌 비율만 막대로
   그립니다. 근거 없는 스케일(건수 × 10)로 그린 막대는 정보처럼 보이지만 정보가 아닙니다.
5. **건수는 막대, 비율은 선** — 0/1/2 를 오가는 건수를 꺾은선으로 그리면 존재한 적 없는
   기울기를 그리게 됩니다. `ui.microbars`(건수) / `ui.sparkline`(비율)로 나눠 씁니다.

### 코드 구조

```
common/data.py     CSV·DB 로더 (원본)
      ↓
common/signals.py  파생 신호 — 무엇이 "지연"이고 "진행 중"인지 한 곳에서만 정의
      ↓
common/ui.py       대시보드 컴포넌트 킷 — 순수 함수, HTML 문자열만 반환
      ↓
views/*.py         화면 조립 → st.markdown 한 번 호출
```

`common/ui.py`의 모든 컴포넌트는 문자열을 반환하고, 화면 하나는 **`st.markdown` 한 번**으로
그려집니다. DOM 쓰기를 줄이려는 목적도 있지만, 더 근본적으로는 패널 테두리가 실제로 내용을
감싸게 하는 유일한 방법이기 때문입니다 — Streamlit은 markdown 블록마다 열린 태그를 닫으므로
`panel_open()` / `panel_close()` 사이에 그린 위젯은 상자 **바깥**에 놓입니다.

새 대시보드 화면을 추가할 때:

```python
U.render(
    U.context_bar("제목", "부제", meta=[("기준일", "2026-08-26")]),
    U.alerts(G.attention()),
    U.kpi_row([{"label": "대기", "value": 3, "unit": "건", "tone": "warn",
                "href": N.href("media_response_desk")}]),
    U.board(
        U.column(8, U.panel("대기열", U.rows(rows))),
        U.column(4, U.panel("상태", U.stat_rows(stats))),
    ),
)
```

## 데이터 계층

- 대부분의 화면: `common/data.py`가 `data/*.csv`를 읽는 read-only 경로
- **MEDIA > 대응 이력**만 SQLite 기반 실제 CRUD(`repository/` → `services/` → View)로 동작 — 신규 등록/수정/Archive 가능
- 나머지 CSV 기반 화면은 이 SQLite 쓰기 내용을 아직 반영하지 않습니다(단계적 전환 중)
