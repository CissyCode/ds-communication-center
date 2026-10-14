# DS Fact Sheet (정형 데이터)

사용자가 제공한 비정형 표(실적·인력·사업장·점유율 등)를 CSV로 정리한 데이터입니다.
모든 파일: UTF-8 (BOM 포함, 엑셀 호환), 1행 헤더, 숫자는 단위 없이 숫자만 저장, 값 없음은 빈 칸.

| 파일 | 원본 표 | 행 단위 | 주요 컬럼 / 단위 |
|---|---|---|---|
| `financials.csv` | 실적 | 연도 (2011–2023) | `*_krw_tn` = 조원. company = 전사, semi = 반도체, capex = 시설 투자 |
| `headcount.csv` | 임직원 현황 | 조직 단위 | `as_of`(YYYY-MM), `level`(전체/지역/사업장), `parent`로 계층 표현, `headcount`(명) |
| `domestic_sites.csv` | 국내 사업장 현황 | 사업장 | `completed_year`, `area_pyeong`(평), `line_count`, `lines`(쉼표 구분) |
| `overseas_production_sites.csv` | 해외 생산거점 | 법인 | `established_year`, `area_pyeong`(평), `status`(가동/건설 중) |
| `overseas_offices.csv` | 해외 판매거점 및 R&D센터 | 거점 | `office_type`(판매거점/R&D센터), `abbreviation`, `region`, `country`, `city` |
| `world_no1_products.csv` | 세계 1위 제품 | 제품 | `share_pct`(%), `basis_period`(YYYY-Qn), `first_no1_year` |
| `market_share.csv` | 시장점유율 | 세그먼트 × 연도 (long) | `share_pct`(%), 원본 `-`는 빈 칸 |
| `market_share_rank.csv` | 시장점유율 (비고 열) | 세그먼트 | `samsung_rank`, 비교 기업·순위·점유율, `raw_note`(원문 보존) |

## 변환 규칙

- `165조` → `165.00`, `42만평` → `420000`, `40.6%` → `40.6`, `22년 3Q` → `2022-Q3`
- `하닉` → `SK하이닉스`로 표기 통일 (원문은 `raw_note`에 보존)
- 부품연구동(DSR)은 원본의 `*` 표시에 따라 화성캠퍼스 하위 연구동(`parent_site`)으로 분류
- 미국 테일러 공장(원본 각주)은 `overseas_production_sites.csv`에 `status=건설 중` 행으로 포함

## 원본 확인 필요 항목

원본 값을 그대로 옮겼으며, 아래 항목은 수정하지 않고 표시만 해둡니다.

1. `financials.csv` 2016/2017 R&D 비용(16.8조 / 14.8조) — 두 해 값이 뒤바뀐 것으로 보임
2. `market_share_rank.csv` 파운드리 비고 `1위(TSMC 50.2%)` — 원본 각주 `*실적발표 기준 1위`의 적용 대상 및 삼성 순위 확인 필요 (`benchmark_rank` 빈 칸)
3. SSD 2위 인텔과 시스템 1위 인텔의 점유율이 모두 13.5% — 복사 오류 여부 확인 필요
4. 비고 열의 순위·경쟁사 점유율 기준 연도가 명시되지 않음 (2022년 값이 `-`인 세그먼트 포함)
