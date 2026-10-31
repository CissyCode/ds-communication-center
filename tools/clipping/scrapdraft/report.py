"""검토용 엑셀 출력."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

COLS = {
    "rank": "추천순번", "section": "소제목", "media": "매체", "page_raw": "면", "date": "발행일",
    "title": "기사 제목", "subtitle": "부제목", "score": "점수", "reason": "선정 사유",
    "cluster": "유사 보도 묶음", "new": "이번 실행 신규", "note": "확인 메모", "keyword": "검색어", "key": "기사 키",
}


def _view(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c not in out:
            out[c] = ""
    return out[cols].rename(columns=COLS)


def write_report(path: str | Path, res, run_info: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sel = res.selected.copy()
    sheets = {
        "추천목록": _view(sel, ["rank", "section", "media", "page_raw", "date", "title", "subtitle", "score", "reason", "cluster", "new", "note", "keyword", "key"]),
        "참고(기준미달·확인필요)": _view(res.reference, ["section", "media", "page_raw", "date", "title", "score", "reason", "note", "keyword", "key"]),
        "제외·중복": _view(res.removed.assign(note=res.removed["drop_reason"] + " " + res.removed["note"]),
                        ["media", "page_raw", "date", "title", "note", "keyword", "key"]),
        "신문별 상태": res.paper_status,
        "실행 정보": pd.DataFrame(list(run_info.items()), columns=["항목", "값"]),
    }
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            for col in ws.columns:
                width = max((len(str(c.value)) if c.value is not None else 0) for c in col[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(8, width * 1.6), 70)
            ws.freeze_panes = "A2"
    return path
