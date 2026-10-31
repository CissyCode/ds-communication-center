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
