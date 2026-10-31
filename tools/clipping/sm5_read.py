"""스크랩마스터5 화면에서 값만 읽는다(클릭·입력 없음). 관리자 권한 터미널에서 실행.

  python sm5_read.py keywords          자동검색 검색어별 지면/온라인 건수
  python sm5_read.py groups            스크랩 그룹 탭 이름·건수
  python sm5_read.py scraplist         현재 스크랩 목록 행(제목·매체·날짜·지면·Serial 등)
  python sm5_read.py results           현재 표시 중인 검색결과 영역 구조(행 읽기 방식 확인용)
  python sm5_read.py dump <automation_id> [--depth N]   특정 영역 하위 구조 출력

결과는 화면 출력과 함께 output\\sm5_<명령>.txt 로 저장한다.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from pywinauto import Desktop

WINDOW_TITLE = "스크랩마스터 5"
OUT = Path(__file__).resolve().parent / "output"


def main_window():
    w = Desktop(backend="uia").window(title=WINDOW_TITLE)
    if not w.exists(timeout=3):
        sys.exit(f"'{WINDOW_TITLE}' 창을 찾지 못했습니다. 스크랩마스터가 켜져 있고 터미널이 관리자 권한인지 확인해 주세요.")
    return w


def by_id(win, auto_id: str):
    c = win.child_window(auto_id=auto_id)
    if not c.exists(timeout=2):
        return None
    return c.wrapper_object()


def texts(elem) -> list[str]:
    out = []
    for t in elem.descendants(control_type="Text"):
        s = (t.window_text() or "").strip()
        if s:
            out.append(s)
    return out


def read_keywords(win) -> list[str]:
    tree = by_id(win, "treeSearchResultGroups")
    if tree is None:
        return ["[검색] 탭을 연 상태에서 실행해 주세요."]
    lines = []
    for item in tree.descendants(control_type="TreeItem"):
        if item.element_info.name != "ScrapMaster5.SearchGroup":
            continue
        t = [x for x in texts(item) if x]
        kw = t[0] if t else ""
        count = next((x for x in t if re.fullmatch(r"\d+ / [\d-]+", x)), "")
        opt = next((x for x in t if x.startswith("|")), "")
        lines.append(f"{count:>9}\t{kw}\t{opt}")
    return lines


def read_groups(win) -> list[str]:
    tab = by_id(win, "ScrapGroupTab")
    if tab is None:
        return ["스크랩 목록 창이 열려 있는지 확인해 주세요."]
    lines = []
    for ti in tab.children(control_type="TabItem"):
        t = [x for x in texts(ti) if x not in ("×", "ScrapMaster5.ScrapGroup")]
        lines.append("".join(t))
    return lines


def read_grid(grid) -> list[str]:
    lines = []
    header = [h.window_text() for h in grid.descendants(control_type="HeaderItem")]
    if header:
        lines.append("\t".join(header))
    for row in grid.children():
        if row.element_info.control_type in ("Header", "ScrollBar"):
            continue
        cells = []
        for cell in row.children():
            v = cell.window_text() or " ".join(texts(cell))
            cells.append(v.replace("\t", " ").replace("\n", " "))
        if any(cells):
            lines.append("\t".join(cells))
    return lines


def read_scraplist(win) -> list[str]:
    grid = by_id(win, "scraplistDataGrid")
    if grid is None:
        return ["스크랩 목록(scraplistDataGrid)을 찾지 못했습니다."]
    lines = read_grid(grid)
    return lines if len(lines) > 1 else lines + ["(행 없음 — 스크랩 목록이 비어 있거나 다른 그룹이 선택됨)"]


def dump(elem, depth: int, indent: int = 0, lines=None) -> list[str]:
    lines = [] if lines is None else lines
    ei = elem.element_info
    lines.append(f"{'  ' * indent}{ei.control_type}\t{ei.name!r}\t{ei.automation_id!r}\t{ei.class_name!r}")
    if indent < depth:
        for c in elem.children():
            dump(c, depth, indent + 1, lines)
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["keywords", "groups", "scraplist", "results", "dump"])
    ap.add_argument("auto_id", nargs="?")
    ap.add_argument("--depth", type=int, default=6)
    args = ap.parse_args()

    win = main_window()
    if args.cmd == "keywords":
        lines = read_keywords(win)
    elif args.cmd == "groups":
        lines = read_groups(win)
    elif args.cmd == "scraplist":
        lines = read_scraplist(win)
    else:
        auto_id = "tcSearchResultTab" if args.cmd == "results" else args.auto_id
        if not auto_id:
            sys.exit("dump 뒤에 automation_id를 적어 주세요. 예: python sm5_read.py dump tcSearchResultTab")
        elem = by_id(win, auto_id)
        lines = dump(elem, args.depth) if elem is not None else [f"{auto_id} 를 찾지 못했습니다."]

    OUT.mkdir(exist_ok=True)
    path = OUT / f"sm5_{args.cmd}.txt"
    path.write_text(f"# {datetime.now():%Y-%m-%d %H:%M}\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:200]))
    if len(lines) > 200:
        print(f"... ({len(lines)}줄 중 200줄만 표시)")
    print(f"저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
