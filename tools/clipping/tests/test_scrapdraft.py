"""가상 데이터로 만든 스크랩마스터 형식 엑셀로 전체 흐름을 확인한다."""
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from scrapdraft.__main__ import main
from scrapdraft.config import load_config
from scrapdraft.engine import ST_UNKNOWN, build_draft
from scrapdraft.excel_io import read_export

HERE = Path(__file__).resolve().parent.parent
HEADER = ["연번", "기사 제목", "부제목", "매체명", "지면번호", "발행일", "구분", "크기", "검색어", "기사 시리얼"]
ROWS = [
    [1, "회사명, 차세대 메모리 양산 돌입", "", "신문A", "A1", "2026-11-02", "지면", "320cm²", "회사명", "1001"],
    [2, "회사명, 차세대 메모리 양산 돌입", "", "신문A", "A1", "2026-11-02", "지면", "320cm²", "메모리", "1001"],  # 같은 기사, 다른 검색어
    [3, "회사명 차세대 메모리 양산", "", "신문A(가판)", "A1", "2026-11-02", "지면", "300cm²", "회사명", "2001"],  # 가판
    [4, "회사명 차세대 메모리 양산 시작", "", "경제지A", "3", "2026-11-02", "지면", "150cm²", "회사명", "1002"],  # 다른 매체 유사
    [5, "반도체 수출 석 달째 증가", "", "신문B", "B2", "2026-11-02", "지면", "80cm²", "반도체", "1003"],
    [6, "회사명 온라인 속보", "", "신문A", "", "2026-11-02", "온라인", "", "회사명", "9001"],
    [7, "부고 회사명 前 임원", "", "신문B", "30", "2026-11-02", "지면", "5cm²", "회사명", "1004"],
    [8, "현안키워드 관련 공청회", "", "신문B", "8", "2026-11-02", "지면", "60cm²", "현안키워드", "1005"],
    [9, "날씨 칼럼", "", "신문B", "29", "2026-11-02", "지면", "20cm²", "기타", "1006"],
]


def make_export(path: Path):
    stats = [["검색 결과", None, None, None, None, None, None, None, None, None]]
    df = pd.DataFrame(stats + [HEADER] + ROWS + [["합계", None, None, None, None, None, None, None, None, None]])
    df.to_excel(path, header=False, index=False)


class ScrapDraftTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.xlsx = self.tmp / "검색결과.xlsx"
        make_export(self.xlsx)
        self.cfg_path = HERE / "config.example.yaml"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_read_export_skips_stats_rows(self):
        df = read_export(self.xlsx)
        self.assertEqual(len(df), 9)
        self.assertEqual(df.iloc[0]["key"], "S:1001")
        self.assertEqual(df.iloc[0]["page_no"], 1)

    def test_draft_rules(self):
        cfg = load_config(self.cfg_path)
        res = build_draft(read_export(self.xlsx), cfg, date(2026, 11, 2))
        sel = res.selected
        keys = list(sel["key"])
        self.assertEqual(keys.count("S:1001"), 1, "같은 기사는 한 번만")
        self.assertIn("회사명", sel.set_index("key").at["S:1001", "keyword"])
        self.assertNotIn("S:9001", keys, "온라인 제외")
        self.assertIn("S:2001", list(res.removed["key"]), "가판은 판 중복으로")
        self.assertIn("S:1004", list(res.removed["key"]), "부고는 제외 후보")
        self.assertIn("S:1002", keys, "다른 매체 유사 보도는 삭제하지 않음")
        self.assertTrue(sel.set_index("key").at["S:1002", "cluster"])
        self.assertEqual(keys[0], "S:1001", "당사 1면이 맨 앞")
        self.assertEqual(keys[1], "S:1002", "유사 보도는 대표 바로 뒤")
        self.assertIn("S:1006", list(res.reference["key"]), "기준 미달은 참고로")
        st = res.paper_status.set_index("매체")["상태"]
        self.assertEqual(st["경제지B"], ST_UNKNOWN)
        self.assertTrue(res.overall.startswith("부분 완료"))

    def test_issue_expiry(self):
        cfg = load_config(self.cfg_path)
        live = build_draft(read_export(self.xlsx), cfg, date(2026, 11, 2))
        expired = build_draft(read_export(self.xlsx), cfg, date(2026, 12, 1))
        self.assertIn("S:1005", list(live.selected["key"]))
        self.assertNotIn("S:1005", list(expired.selected["key"]))

    def test_cli_rerun_is_idempotent_and_diff(self):
        out = self.tmp / "out"
        args = ["--config", str(self.cfg_path), "--out", str(out)]
        main(args + ["recommend", str(self.xlsx), "--date", "2026-11-02", "--confirmed-empty", "경제지B"])
        main(args + ["recommend", str(self.xlsx), "--date", "2026-11-02", "--confirmed-empty", "경제지B"])
        r2 = pd.read_excel(sorted(out.glob("검토초안_*run2.xlsx"))[0], sheet_name="추천목록")
        self.assertEqual(r2["이번 실행 신규"].fillna("").eq("").all(), True, "재실행 시 신규 없음")
        info = pd.read_excel(sorted(out.glob("검토초안_*run2.xlsx"))[0], sheet_name="실행 정보").set_index("항목")["값"]
        self.assertEqual(info["전체 상태"], "완료")

        final = self.tmp / "확정목차.xlsx"
        pd.DataFrame([["연번", "기사 제목", "매체명", "지면번호", "기사 시리얼"],
                      [None, "당사", None, None, None],
                      [1, "반도체 수출 석 달째 증가", "신문B", "B2", "1003"],
                      [2, "회사명, 차세대 메모리 양산 돌입", "신문A", "A1", "1001"],
                      [3, "사람이 넣은 기사", "신문B", "5", "7777"]]).to_excel(final, header=False, index=False)
        main(args + ["diff", str(final), "--date", "2026-11-02"])
        d = pd.read_excel(out / "검토결과비교_2026-11-02.xlsx")
        acts = dict(zip(d["기사 키"], d["구분"]))
        self.assertEqual(acts["S:7777"], "사람이 추가")
        self.assertEqual(acts["S:1002"], "사람이 제외")
        self.assertEqual(acts["S:1003"], "순서 이동")

    def test_analyze(self):
        past = self.tmp / "past"
        past.mkdir()
        for n in range(3):
            pd.DataFrame([["연번", "기사 제목", "매체명", "지면번호", "기사 시리얼"],
                          [None, "당사", None, None, None],
                          [1, f"기사{n}a", "신문A", "1", f"{n}1"],
                          [2, f"기사{n}b", "경제지A", "3", f"{n}2"],
                          [3, f"기사{n}c", "신문B", "2", f"{n}3"]]).to_excel(past / f"d{n}.xlsx", header=False, index=False)
        main(["--out", str(self.tmp / "out"), "analyze", str(past)])
        mo = pd.read_excel(self.tmp / "out" / "과거스크랩분석.xlsx", sheet_name="매체순서 추정")
        self.assertEqual(list(mo["매체"]), ["신문A", "경제지A", "신문B"])


if __name__ == "__main__":
    unittest.main()
