"""가상 데이터로 만든 스크랩마스터 형식 엑셀로 전체 흐름을 확인한다."""
import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from scrapdraft.__main__ import main
from scrapdraft.config import load_config
from scrapdraft.engine import ST_HAS, ST_NO_EARLY, ST_UNKNOWN, build_draft
from scrapdraft.excel_io import read_export

HERE = Path(__file__).resolve().parent.parent
D = "2026-11-02"  # 월요일
HEADER = ["연번", "기사 제목", "부제목", "매체명", "지면번호", "발행일", "구분", "카테고리", "크기", "검색어", "기사 시리얼"]
ROWS = [
    [1, "가나전자 HBM 양산 돌입", "", "전자신문", "1", D, "지면", "산업", "320cm²", "가나전자", "1001"],
    [2, "가나전자 HBM 양산 돌입", "", "전자신문", "1", D, "지면", "산업", "320cm²", "HBM", "1001"],  # 같은 기사, 다른 검색어
    [3, "가나전자 HBM 양산 돌입", "", "전자신문(가판)", "1", D, "지면", "산업", "300cm²", "가나전자", "2001"],
    [4, "가나전자 HBM 양산 시작", "", "매일경제", "A3", D, "지면", "기업", "150cm²", "가나전자", "1002"],
    [5, "다라반도체 실적 개선 전망", "", "한국경제", "A5", D, "지면", "산업", "80cm²", "반도체", "1003"],
    [6, "가나전자 온라인 속보", "", "전자신문", "", D, "온라인", "", "", "가나전자", "9001"],
    [7, "부고 가나전자 前 임원", "", "서울경제", "30", D, "지면", "사회", "5cm²", "가나전자", "1004"],
    [8, "현안키워드 관련 공청회", "", "서울경제", "8", D, "지면", "정치", "60cm²", "현안키워드", "1005"],
    [9, "주말 날씨 맑음", "", "서울경제", "29", D, "지면", "사회", "20cm²", "기타", "1006"],
    [10, "반도체 특집 기획", "", "매일경제", "B1", D, "지면", "기획", "400cm²", "반도체", "1007"],
    [11, "[사설] 반도체 지원 서둘러야", "", "경향신문", "31", D, "지면", "사설", "100cm²", "반도체", "1008"],
    [12, "[사설] 반도체 특별법 처리하라", "", "매일경제", "A35", D, "지면", "사설", "100cm²", "반도체", "1009"],
    [13, "가나생명 보험료 인상", "", "서울경제", "12", D, "지면", "금융", "70cm²", "가나생명", "1010"],
    [14, "[사설] 성과급 잔치 경계해야", "", "문화일보", "31", D, "지면", "오피니언", "90cm²", "성과급", "1014"],
    [16, "황홀한 역전타", "", "한국일보", "A14", D, "지면", "스포츠", "860cm²", "가나", "1016"],
    [17, "전면광고", "", "한국경제", "A24", D, "지면", "광고", "1900cm²", "가나", "1017"],
    [15, "가나 노조 45조 성과급 논란", "", "헤럴드경제", "2", "2026-11-01", "지면", "종합", "500cm²", "가나전자", "1015"],
]


def make_export(path: Path):
    blank = [None] * len(HEADER)
    pd.DataFrame([["검색 결과"] + blank[1:], HEADER, *ROWS, ["합계"] + blank[1:]]).to_excel(path, header=False, index=False)


class ScrapDraftTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.xlsx = self.tmp / "검색결과.xlsx"
        make_export(self.xlsx)
        self.cfg_path = HERE / "tests" / "fixture_config.yaml"
        self.issues = self.tmp / "issues.yaml"
        self.issues.write_text(
            "issues:\n"
            "  - {name: 시험 현안, keywords: [현안키워드], until: 2026-11-15, boost: 50, section: 핵심, subtopic: 현안}\n"
            "  - {name: 성과급, keywords: [성과급], until: 2026-11-15, boost: 60, section: 핵심, subtopic: 현안, bundle: true}\n",
            encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def cfg(self):
        return load_config(self.cfg_path, [self.issues])

    def test_read_export_skips_stats_rows(self):
        df = read_export(self.xlsx)
        self.assertEqual(len(df), len(ROWS))
        self.assertEqual(df.iloc[0]["key"], "S:1001")
        self.assertEqual(df.iloc[0]["page_no"], 1)

    def test_read_group_export_with_group_row(self):
        """스크랩 목록 [엑셀로 내보내기] 형식: 헤더 다음 줄에 그룹 이름만 있는 줄이 온다."""
        p = self.tmp / "group.xlsx"
        pd.DataFrame([["연번", "기사 제목", "매체명", "지면번호", "기자", "발행일", "검색어", "기사 시리얼"],
                      ["자동검토_테스트", None, None, None, None, None, None, None],
                      [1, "시험 기사 하나", "한국일보", "A15면", "기자A", D, "가나", "20261031hk00a15002"],
                      [2, "시험 기사 둘", "한국경제", "A02면", None, D, "반도체", "20261031ha00a02003"]]
                     ).to_excel(p, header=False, index=False)
        df = read_export(p)
        self.assertEqual(list(df["key"]), ["S:20261031hk00a15002", "S:20261031ha00a02003"])
        self.assertEqual(list(df["page_no"]), [15, 2])

    def test_draft_rules(self):
        res = build_draft(read_export(self.xlsx), self.cfg(), date(2026, 11, 2), now=datetime(2026, 11, 2, 8, 0))
        sel = res.selected.set_index("key")
        keys = list(res.selected["key"])
        removed = dict(zip(res.removed["key"], res.removed["drop_reason"]))
        reference = list(res.reference["key"])

        self.assertEqual(keys.count("S:1001"), 1, "같은 기사는 한 번만")
        self.assertIn("HBM", sel.at["S:1001", "keyword"])
        self.assertIn("온라인", removed["S:9001"])
        self.assertIn("판 중복", removed["S:2001"])
        self.assertIn("부고", removed["S:1004"])
        self.assertIn("기획면", removed["S:1007"], "B면은 기획면 제외")
        self.assertIn("스포츠", removed["S:1016"], "스포츠 카테고리 제외")
        self.assertIn("광고", removed["S:1017"], "광고 카테고리 제외")
        self.assertIn("S:1006", reference, "기준 미달은 참고로")

        self.assertEqual(sel.at["S:1001", "section"], "핵심")
        self.assertEqual(sel.at["S:1005", "subtopic"], "현안")
        self.assertEqual((sel.at["S:1003", "section"], sel.at["S:1003", "subtopic"]), ("핵심", "반도체 업계"))
        self.assertEqual(sel.at["S:1009", "section"], "칼럼/사설")
        self.assertEqual(sel.at["S:1008", "section"], "칼럼/사설", "조중동매한서 외 사설도 감점 후 포함")
        self.assertEqual((sel.at["S:1010", "section"], sel.at["S:1010", "subtopic"]), ("관계사", "금융"))
        self.assertIn("발행일", sel.at["S:1015", "note"], "전날 발행 표시")

        # 핵심(현안 → 반도체 업계[매체순]) → 관계사 → 칼럼/사설
        # 성과급 현안 묶음: 헤럴드 기사 뒤에 문화일보 사설이 관련기사로, 목차엔 숨김
        self.assertEqual(keys, ["S:1005", "S:1015", "S:1014", "S:1002", "S:1001", "S:1003", "S:1010", "S:1009", "S:1008"])
        self.assertEqual(sel.at["S:1015", "toc"], "표시")
        self.assertEqual(sel.at["S:1014", "toc"], "숨김(관련기사)")
        self.assertEqual(sel.at["S:1001", "toc"], "숨김(관련기사)")

        st = res.paper_status.set_index("매체")["상태"]
        self.assertEqual(st["전자신문"], ST_HAS)
        self.assertEqual(st["동아일보"], ST_NO_EARLY)
        self.assertEqual(st["세계일보"], ST_UNKNOWN)
        self.assertTrue(res.overall.startswith("부분 완료"))

    def test_evening_and_shape(self):
        """석간은 전날 자가 정상, 같은 사안이면 세로형(3~4단) 기사가 대표."""
        p = self.tmp / "mini.xlsx"
        pd.DataFrame([HEADER,
                      [1, "반도체 수출 사상 최대 기록", "", "매일경제", "A10", D, "지면", "경제", "40.0 x 10.0㎝", "반도체", "2001"],
                      [2, "반도체 수출 사상 최대 기록 달성", "", "매일경제", "A12", D, "지면", "경제", "15.0 x 30.0㎝", "반도체", "2002"],
                      [3, "메모리 가격 반등 신호", "", "문화일보", "5", "2026-11-01", "지면", "경제", "20 x 20㎝", "반도체", "2003"],
                      ]).to_excel(p, header=False, index=False)
        res = build_draft(read_export(p), self.cfg(), date(2026, 11, 2))
        sel = res.selected.set_index("key")
        keys = list(res.selected["key"])
        self.assertLess(keys.index("S:2002"), keys.index("S:2001"), "세로형이 대표")
        self.assertEqual(sel.at["S:2001", "toc"], "숨김(관련기사)")
        self.assertIn("세로형", sel.at["S:2002", "reason"])
        self.assertNotIn("발행일", sel.at["S:2003", "note"], "석간 전날 자는 정상")

    def test_company_order_toc_cap_alert(self):
        """경쟁사 순서(ordered), 묶음 목차 표시 상한, 보도자료 동일 보도 상한, 우선 검토 표시."""
        base = (HERE / "tests" / "fixture_config.yaml").read_text(encoding="utf-8")
        base = base.replace("      - {name: 반도체 업계, keywords: [다라반도체, HBM, 메모리]}",
                            "      - {name: 경쟁사, keywords: [다라반도체, 마바테크, 사아칩], ordered: true}")
        base = base.replace("keywords: [가나전자 반도체, 가나전자 HBM, 반도체, 다라반도체, HBM, 메모리]",
                            "keywords: [가나전자 반도체, 반도체, 다라반도체, 마바테크, 사아칩]")
        base += "toc_max: 2\nalert_keywords: [파업, 유출]\n"
        cfg_p = self.tmp / "cfg.yaml"
        cfg_p.write_text(base, encoding="utf-8")
        iss = self.tmp / "today.yaml"
        iss.write_text("issues:\n  - {name: 오늘 보도자료, keywords: [신제품], until: 2026-11-30, boost: 80, "
                       "section: 핵심, subtopic: 보도자료, bundle: true, max_items: 3}\n", encoding="utf-8")
        cfg = load_config(cfg_p, [iss])
        rows = [
            [1, "사아칩 신공장 착공", "", "매일경제", "A5", D, "지면", "산업", "20 x 20㎝", "반도체", "3001"],
            [2, "마바테크 실적 호조", "", "매일경제", "A6", D, "지면", "산업", "20 x 20㎝", "반도체", "3002"],
            [3, "다라반도체 노조 파업 예고", "", "한국경제", "A3", D, "지면", "산업", "20 x 20㎝", "반도체", "3003"],
        ] + [[10 + k, f"가나전자 반도체 신제품 공개 {k}", "", m, "A1", D, "지면", "산업", "20 x 20㎝", "반도체", f"40{k}"]
             for k, m in enumerate(["매일경제", "한국경제", "서울경제", "전자신문", "경향신문"])]
        p = self.tmp / "mini2.xlsx"
        pd.DataFrame([HEADER] + rows).to_excel(p, header=False, index=False)
        res = build_draft(read_export(p), cfg, date(2026, 11, 2))
        keys = list(res.selected["key"])
        sel = res.selected.set_index("key")
        self.assertEqual(keys[-3:], ["S:3003", "S:3002", "S:3001"], "경쟁사는 지정 순서")
        self.assertEqual(keys[:3], ["S:400", "S:401", "S:402"], "보도자료 동일 보도는 주요 매체 3건")
        self.assertIn("S:403", list(res.reference["key"]))
        self.assertEqual([sel.at[k, "toc"] for k in keys[:3]], ["표시", "표시(묶음)", "숨김(관련기사)"])
        self.assertEqual(sel.at["S:3003", "alert"], "파업")

    def test_require_keywords(self):
        """기타 소제목은 가나·반도체 관련일 때만 추천."""
        base = (HERE / "tests" / "fixture_config.yaml").read_text(encoding="utf-8")
        base = base.replace("    keywords: [정부, 경제]\n", "    keywords: [정부, 경제]\n    require_keywords: [가나, 반도체]\n")
        cfg_p = self.tmp / "cfg2.yaml"
        cfg_p.write_text(base, encoding="utf-8")
        p = self.tmp / "mini3.xlsx"
        pd.DataFrame([HEADER,
                      [1, "정부 내년 경제정책 발표", "", "매일경제", "A1", D, "지면", "경제", "30 x 30㎝", "경제", "5001"],
                      [2, "정부 경제정책에 가나 투자 포함", "", "매일경제", "A2", D, "지면", "경제", "30 x 30㎝", "경제", "5002"],
                      ]).to_excel(p, header=False, index=False)
        res = build_draft(read_export(p), load_config(cfg_p), date(2026, 11, 2))
        self.assertIn("S:5002", list(res.selected["key"]))
        self.assertIn("S:5001", list(res.reference["key"]))

    def test_feedback_rules(self):
        """실제 초안 피드백: 바이라인 없음 제외, 본문만 일치는 1면이어도 참고, 시황은 기타·상한, 제목 일치 우선, 현안 조건."""
        base = (HERE / "tests" / "fixture_config.yaml").read_text(encoding="utf-8")
        base = base.replace("      - {name: 경제, keywords: [경제]}",
                            "      - {name: 증시·시황, keywords: [코스피, 코스닥], max_items: 2, cap_exempt: [가나전자]}\n"
                            "      - {name: 경제, keywords: [경제]}")
        base = base.replace("    keywords: [정부, 경제]\n", "    keywords: [정부, 경제, 코스피, 코스닥]\n")
        base += ("require_byline: true\nbody_factor: 0.3\n"
                 "force_sections:\n  - {section: 기타, keywords: [코스피, 코스닥], unless: [가나전자]}\n")
        cfg_p = self.tmp / "cfg3.yaml"
        cfg_p.write_text(base, encoding="utf-8")
        iss = self.tmp / "iss3.yaml"
        iss.write_text("issues:\n  - {name: 노조, keywords: [노조], until: 2026-11-30, boost: 60, section: 핵심, "
                       "subtopic: 현안, require_keywords: [가나]}\n", encoding="utf-8")
        cfg = load_config(cfg_p, [iss])
        H = ["연번", "기사 제목", "부제목", "매체명", "지면번호", "발행일", "구분", "카테고리", "크기", "검색어", "기자", "기사 시리얼"]
        rows = [
            [1, "TV 편성표", "", "매일경제", "A21", D, "지면", "문화", "40 x 18㎝", "가나", "", "6001"],
            [2, "[사설] 예산 심사 엄격히", "", "매일경제", "A35", D, "지면", "사설", "20 x 20㎝", "반도체", "", "6002"],
            [3, "빅테크 어닝쇼크에 시장 불똥", "", "한국경제", "A1", D, "지면", "종합", "30 x 40㎝", "반도체", "기자A", "6003"],
            [4, "코스피 3% 급락", "", "매일경제", "A2", D, "지면", "증권", "20 x 20㎝", "반도체", "기자B", "6004"],
            [5, "코스피 반도체 약세", "", "한국경제", "A5", D, "지면", "증권", "20 x 20㎝", "반도체", "기자C", "6005"],
            [6, "코스닥 반등 기대", "", "서울경제", "A6", D, "지면", "증권", "20 x 20㎝", "반도체", "기자D", "6006"],
            [7, "코스피 가나전자 급등", "", "서울경제", "A7", D, "지면", "증권", "20 x 20㎝", "가나", "기자E", "6007"],
            [8, "가나생명 신상품 출시", "", "매일경제", "A12", D, "지면", "금융", "20 x 20㎝", "반도체", "기자F", "6008"],
            [9, "현대차 노조 파업 예고", "", "매일경제", "A13", D, "지면", "산업", "20 x 20㎝", "반도체", "기자G", "6009"],
        ]
        p = self.tmp / "mini4.xlsx"
        pd.DataFrame([H] + rows).to_excel(p, header=False, index=False)
        res = build_draft(read_export(p), cfg, date(2026, 11, 2))
        sel = res.selected.set_index("key")
        removed = dict(zip(res.removed["key"], res.removed["drop_reason"]))
        ref = list(res.reference["key"])
        self.assertIn("바이라인", removed["S:6001"], "기자명 없는 편성표는 기사 아님")
        self.assertIn("S:6002", list(sel.index), "사설은 기자명 없어도 유지")
        self.assertIn("S:6003", ref, "본문에서만 걸리면 1면이어도 참고")
        self.assertEqual(sel.at["S:6004", "section"], "기타")
        cap = [k for k in ("S:6004", "S:6005", "S:6006") if k in sel.index]
        self.assertEqual(len(cap), 2, "증시·시황은 2건까지")
        self.assertIn("S:6007", list(sel.index), "제목에 가나전자가 크게 들어가면 시황이어도 유지")
        self.assertEqual(sel.at["S:6008", "section"], "관계사", "제목 일치가 본문 일치보다 우선")
        self.assertNotEqual(sel.at["S:6009", "subtopic"] if "S:6009" in sel.index else "", "현안",
                            "다른 회사 노조 기사는 현안 아님")

    def test_status_before_ready_time(self):
        res = build_draft(read_export(self.xlsx), self.cfg(), date(2026, 11, 2), now=datetime(2026, 11, 2, 6, 0))
        st = res.paper_status.set_index("매체")["상태"]
        self.assertTrue(st["세계일보"].startswith("수집 전"))

    def test_weekend_papers(self):
        cfg = self.cfg()
        self.assertNotIn("전자신문", [p.name for p in cfg.papers_for(date(2026, 11, 1))])

    def test_issue_expiry(self):
        live = build_draft(read_export(self.xlsx), self.cfg(), date(2026, 11, 2))
        expired = build_draft(read_export(self.xlsx), self.cfg(), date(2026, 12, 1))
        self.assertIn("S:1005", list(live.selected["key"]))
        self.assertNotIn("S:1005", list(expired.selected["key"]))

    def test_cli_rerun_is_idempotent_and_diff(self):
        out = self.tmp / "out"
        args = ["--config", str(self.cfg_path), "--issues", str(self.issues), "--out", str(out)]
        main(args + ["recommend", str(self.xlsx), "--date", D])
        main(args + ["recommend", str(self.xlsx), "--date", D])
        report = sorted(out.glob("검토초안_*run2.xlsx"))[0]
        r2 = pd.read_excel(report, sheet_name="추천목록")
        self.assertTrue(r2["이번 실행 신규"].fillna("").eq("").all(), "재실행 시 신규 없음")

        final = self.tmp / "확정목차.xlsx"
        pd.DataFrame([["연번", "기사 제목", "매체명", "지면번호", "기사 시리얼"],
                      [None, "핵심", None, None, None],
                      [1, "가나전자 HBM 양산 돌입", "전자신문", "1", "1001"],
                      [2, "현안키워드 관련 공청회", "서울경제", "8", "1005"],
                      [3, "사람이 넣은 기사", "국민일보", "5", "7777"]]).to_excel(final, header=False, index=False)
        main(args + ["diff", str(final), "--date", D])
        d = pd.read_excel(out / f"검토결과비교_{D}.xlsx")
        acts = dict(zip(d["기사 키"], d["구분"]))
        self.assertEqual(acts["S:7777"], "사람이 추가")
        self.assertEqual(acts["S:1002"], "사람이 제외")
        self.assertEqual(acts["S:1001"], "순서 이동")

    def test_analyze(self):
        past = self.tmp / "past"
        past.mkdir()
        for n in range(3):
            pd.DataFrame([["연번", "기사 제목", "매체명", "지면번호", "기사 시리얼"],
                          [None, "DS", None, None, None],
                          [1, f"기사{n}a", "조선일보", "1", f"{n}1"],
                          [2, f"기사{n}b", "매일경제", "3", f"{n}2"],
                          [3, f"기사{n}c", "전자신문", "2", f"{n}3"]]).to_excel(past / f"d{n}.xlsx", header=False, index=False)
        main(["--out", str(self.tmp / "out"), "analyze", str(past)])
        mo = pd.read_excel(self.tmp / "out" / "과거스크랩분석.xlsx", sheet_name="매체순서 추정")
        self.assertEqual(list(mo["매체"]), ["조선일보", "매일경제", "전자신문"])


if __name__ == "__main__":
    unittest.main()
