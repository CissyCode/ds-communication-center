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

## 데이터 계층

- 대부분의 화면: `common/data.py`가 `data/*.csv`를 읽는 read-only 경로
- **MEDIA > 대응 이력**만 SQLite 기반 실제 CRUD(`repository/` → `services/` → View)로 동작 — 신규 등록/수정/Archive 가능
- 나머지 CSV 기반 화면은 이 SQLite 쓰기 내용을 아직 반영하지 않습니다(단계적 전환 중)
