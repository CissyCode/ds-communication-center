"""스크랩마스터 엑셀 내보내기 읽기.

검색결과·스크랩 목록·편집 목차 엑셀은 사용자가 고른 항목만, 고른 순서대로 저장되고
'통계 포함' 시 위아래에 통계 행이 붙을 수 있다. 그래서 헤더 행을 찾아 이름으로 매핑한다.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

# 내부 필드명 -> 스크랩마스터 엑셀 항목명 후보 (공백 제거 후 비교)
ALIASES: dict[str, list[str]] = {
    "serial": ["기사시리얼", "시리얼"],
    "title": ["기사제목", "제목"],
    "subtitle": ["부제목"],
    "media": ["매체명", "매체"],
    "page": ["지면번호", "지면정보", "면", "지면", "면수"],
    "date": ["발행일", "일자", "날짜"],
    "kind": ["구분"],
    "category": ["카테고리"],
    "size": ["크기", "기사크기"],
    "reporter": ["기자", "기자명"],
    "keyword": ["검색어"],
    "dup_search": ["중복검색"],   # 같은 기사를 잡은 다른 검색어 그룹(병합 검색 결과)
    "seq": ["연번", "순번"],
    "url": ["기사url", "url"],
    "media_class": ["매체분류"],
    "group": ["스크랩그룹"],
    "subhead": ["소제목"],
    "sentiment": ["분석"],
}
_LOOKUP = {alias: field for field, names in ALIASES.items() for alias in names}

FIELDS = list(ALIASES)


def _norm_header(v) -> str:
    return re.sub(r"\s+", "", str(v)).lower() if v is not None else ""


def _find_header(raw: pd.DataFrame, max_scan: int = 20) -> int | None:
    best, best_hits = None, 0
    for i in range(min(max_scan, len(raw))):
        hits = sum(1 for v in raw.iloc[i] if _norm_header(v) in _LOOKUP)
        if hits > best_hits:
            best, best_hits = i, hits
    return best if best_hits >= 2 else None


def parse_size(v) -> float | None:
    """'123.4cm²' 또는 '10.2 x 15.3' 형태를 면적(cm²)으로."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v)
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", s)]
    if not nums:
        return None
    if re.search(r"[x×*]", s, re.I) and len(nums) >= 2:
        return nums[0] * nums[1]
    return nums[0]


def parse_dims(v) -> tuple[float | None, float | None]:
    """'12.3 x 50.8㎝' → (가로, 세로) cm. 면적만 있으면 (None, None)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None, None
    s = str(v)
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", s)]
    if re.search(r"[x×*]", s, re.I) and len(nums) >= 2:
        return nums[0], nums[1]
    return None, None


def parse_page(v) -> tuple[str, int | None]:
    """원문 면 표기와 정렬용 숫자. 'A1'·'1면'·'B3' 모두 숫자만 뽑는다."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "", None
    s = str(v).strip()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    m = re.search(r"\d+", s)
    return s, (int(m.group()) if m else None)


def parse_date(v) -> date | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    m = re.search(r"(\d{4})\D?(\d{1,2})\D?(\d{1,2})", str(v))
    return date(int(m[1]), int(m[2]), int(m[3])) if m else None


def norm_title(t: str) -> str:
    return re.sub(r"[\W_]+", "", t or "").lower()


def article_key(row: dict) -> str:
    """기사 시리얼이 있으면 그것, 없으면 발행일+매체+구분+면+정규화 제목 해시."""
    serial = str(row.get("serial") or "").strip()
    if serial and serial.lower() != "nan":
        if re.fullmatch(r"\d+\.0", serial):
            serial = serial[:-2]
        return f"S:{serial}"
    basis = "|".join(str(row.get(k) or "") for k in ("date", "media", "kind", "page_raw")) + "|" + norm_title(row.get("title", ""))
    return "H:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def read_export(path: str | Path) -> pd.DataFrame:
    """엑셀(또는 CSV) 내보내기를 표준 컬럼 DataFrame으로 읽는다.

    소제목 행(제목만 있고 매체·시리얼이 없는 행)은 is_subhead=True로 남겨 둔다.
    """
    path = Path(path)
    if path.suffix.lower() == ".csv":
        sheets = {"csv": pd.read_csv(path, header=None, dtype=object)}
    else:
        sheets = pd.read_excel(path, header=None, sheet_name=None, dtype=object)

    for raw in sheets.values():
        h = _find_header(raw)
        if h is None:
            continue
        cols = [_LOOKUP.get(_norm_header(v)) for v in raw.iloc[h]]
        body = raw.iloc[h + 1:]
        records = []
        for _, r in body.iterrows():
            rec = {f: None for f in FIELDS}
            for c, v in zip(cols, r):
                if c and rec.get(c) is None and not (isinstance(v, float) and pd.isna(v)):
                    rec[c] = v
            title = str(rec["title"] or "").strip()
            if not title or title.lower() == "nan":
                continue  # 통계·합계·빈 행
            rec["title"] = title
            rec["subtitle"] = str(rec["subtitle"] or "").strip()
            rec["media"] = str(rec["media"] or "").strip()
            rec["kind"] = str(rec["kind"] or "").strip()
            rec["keyword"] = str(rec["keyword"] or "").strip()
            dup = str(rec.get("dup_search") or "").strip()
            if dup and dup.lower() != "nan":  # 분류 때 함께 보도록 검색어에 덧붙인다
                rec["keyword"] = f"{rec['keyword']} {dup}".strip()
            rec["page_raw"], rec["page_no"] = parse_page(rec["page"])
            rec["date"] = parse_date(rec["date"])
            rec["size_cm2"] = parse_size(rec["size"])
            rec["width_cm"], rec["height_cm"] = parse_dims(rec["size"])
            rec["is_subhead"] = not rec["media"] and not rec["serial"]
            rec["key"] = article_key(rec)
            records.append(rec)
        df = pd.DataFrame.from_records(records)
        if df.empty:
            df = pd.DataFrame(columns=FIELDS + ["page_raw", "page_no", "size_cm2", "width_cm", "height_cm", "is_subhead", "key"])
        df.attrs["source"] = str(path)
        df.attrs["has_columns"] = sorted({c for c in cols if c})
        return df
    raise ValueError(f"{path.name}: 스크랩마스터 엑셀 헤더(기사 제목, 매체명 등)를 찾지 못했습니다.")


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
