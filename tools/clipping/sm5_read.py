"""스크랩마스터5 화면에서 값만 읽는다(클릭·입력 없음). 관리자 권한 터미널에서 실행.

  python sm5_read.py keywords          자동검색 검색어별 지면/온라인 건수
  python sm5_read.py groups            스크랩 그룹 탭 이름·건수
  python sm5_read.py scraplist         현재 스크랩 목록 행(제목·매체·날짜·지면·Serial 등)
  python sm5_read.py results           현재 표시 중인 검색결과 영역 구조(행 읽기 방식 확인용)
  python sm5_read.py grids             화면의 표·목록(DataGrid/List/Tree/Table)과 행 수, 첫 행 내용
  python sm5_read.py big               종류와 관계없이 자식 요소가 많은 영역(기사 목록 후보) 찾기
  python sm5_read.py popup --wait 8    8초 기다린 뒤 스크랩마스터의 팝업(오른쪽 클릭 메뉴 등) 항목 읽기
  python sm5_read.py rects             주요 영역의 화면 좌표(검색결과 하단 버튼 위치 계산용) + 창 캡처
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


def expand_search_folders(tree) -> None:
    """'관심 키워드' 등 폴더가 접혀 있으면 하위 검색어 그룹이 화면 정보에 안 나오므로 펼친다."""
    for item in tree.children(control_type="TreeItem"):
        if item.element_info.name == "ScrapMaster5.SearchGroupFolder":
            try:
                if item.get_expand_state() != 1:  # 1 = 펼침
                    item.expand()
            except Exception:
                pass


def read_keywords(win) -> list[str]:
    tree = by_id(win, "treeSearchResultGroups")
    if tree is None:
        return ["[검색] 탭을 연 상태에서 실행해 주세요."]
    expand_search_folders(tree)
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


def read_grids(win) -> list[str]:
    lines = []
    for ct in ("DataGrid", "Table", "List", "Tree"):
        for g in win.descendants(control_type=ct):
            ei = g.element_info
            try:
                if not g.is_visible():
                    continue
            except Exception:
                pass
            kids = [k for k in g.children() if k.element_info.control_type not in ("Header", "ScrollBar")]
            first = ""
            if kids:
                first = " | ".join(texts(kids[0])[:8]) or kids[0].window_text()
            lines.append(f"{ct}\t{ei.automation_id!r}\t행 {len(kids)}\t첫 행: {first[:200]}")
    return lines


def read_big(win, min_children: int = 8) -> list[str]:
    """기사 목록이 표준 표가 아닐 때(서드파티 그리드 등) 자식이 많은 요소를 찾는다."""
    lines = []
    for e in win.descendants():
        try:
            kids = e.children()
        except Exception:
            continue
        if len(kids) < min_children:
            continue
        ei = e.element_info
        kinds = {}
        for k in kids:
            t = k.element_info.control_type
            kinds[t] = kinds.get(t, 0) + 1
        sample = " | ".join(texts(kids[0])[:6]) or kids[0].window_text()
        lines.append(f"{ei.control_type}\t{ei.automation_id!r}\t{ei.class_name!r}\t자식 {len(kids)} {kinds}\t첫 자식: {sample[:150]}")
    return lines


def _dump_dialog(w, lines):
    ei = w.element_info
    lines.append(f"## {ei.control_type}\t{w.window_text()!r}\t{ei.automation_id!r}\t{ei.class_name!r}")
    for c in w.descendants():
        ce = c.element_info
        if ce.control_type in ("MenuItem", "Button", "ListItem", "CheckBox", "RadioButton", "Text", "Edit", "ComboBox"):
            lines.append(f"  {ce.control_type}\t{ce.name!r}\t{ce.automation_id!r}")


def read_popups(win) -> list[str]:
    """메인 창 밖·안에 뜬 스크랩마스터 대화상자(저장 창, 메뉴 등)의 항목을 읽는다."""
    import win32gui
    import win32process
    pid = win.element_info.process_id
    lines = []
    # 1) 같은 프로세스의 보이는 최상위 창(Win32로 열거 — 소유된 대화상자 포함)
    hwnds = []
    win32gui.EnumWindows(lambda h, acc: acc.append(h) if win32gui.IsWindowVisible(h) else None, hwnds)
    for h in hwnds:
        if h == win.handle or win32process.GetWindowThreadProcessId(h)[1] != pid:
            continue
        try:
            _dump_dialog(Desktop(backend="uia").window(handle=h).wrapper_object(), lines)
        except Exception as e:
            lines.append(f"## 창 {h} 읽기 실패: {e}")
    # 2) 메인 창 안에 붙은 창(WPF 모달 창이 자식으로 보이는 경우)
    for w in win.descendants(control_type="Window"):
        _dump_dialog(w, lines)
    return lines or ["팝업 창이 없습니다. 대기 시간 안에 스크랩마스터에서 오른쪽 클릭 메뉴를 열어 두세요."]


RECT_IDS = ["tcSearchResultTab", "btnSearchResultGroupSet", "btnSearchResultFilter", "btnSearchResultOrder",
            "RepeatSearchButton", "comboSearchResultCount_ext", "gsSearchBottom", "gsSearchRight",
            "SearchViewTopSplitter", "ScrapListSplitter", "scraplistDataGrid", "ScrapGroupTab", "MainStatusBar"]


def read_rects(win) -> list[str]:
    r = win.rectangle()
    lines = [f"window\t{r.left},{r.top},{r.right},{r.bottom}\t{r.width()}x{r.height()}"]
    for aid in RECT_IDS:
        e = by_id(win, aid)
        if e is None:
            lines.append(f"{aid}\t(없음)")
            continue
        q = e.rectangle()
        lines.append(f"{aid}\t{q.left},{q.top},{q.right},{q.bottom}\t{q.width()}x{q.height()}")
    try:
        OUT.mkdir(exist_ok=True)
        win.capture_as_image().save(OUT / "sm5_window.png")
        lines.append(f"창 캡처: {OUT / 'sm5_window.png'}")
    except Exception as e:  # Pillow 없으면 생략
        lines.append(f"(창 캡처 생략: {e})")
    return lines


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
    ap.add_argument("cmd", choices=["keywords", "groups", "scraplist", "results", "grids", "big", "popup", "rects", "dump"])
    ap.add_argument("auto_id", nargs="?")
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--wait", type=int, default=0, help="읽기 전에 기다릴 초")
    args = ap.parse_args()

    win = main_window()
    if args.wait:
        import time
        print(f"{args.wait}초 뒤에 읽습니다. 지금 스크랩마스터 화면을 준비해 주세요...")
        time.sleep(args.wait)
    if args.cmd == "keywords":
        lines = read_keywords(win)
    elif args.cmd == "groups":
        lines = read_groups(win)
    elif args.cmd == "scraplist":
        lines = read_scraplist(win)
    elif args.cmd == "grids":
        lines = read_grids(win)
    elif args.cmd == "big":
        lines = read_big(win)
    elif args.cmd == "popup":
        lines = read_popups(win)
    elif args.cmd == "rects":
        lines = read_rects(win)
    elif args.cmd == "results":
        lines = []
        for aid in ("tbCurrentSearchResultGroup", "tbCurrentSearchResultKeywordInfo1",
                    "tbCurrentSearchResultKeywordOption", "tbCurrentSearchResultCount"):
            e = by_id(win, aid)
            lines.append(f"{aid}: {e.window_text() if e is not None else '(없음)'}")
        tab = by_id(win, "tcSearchResultTab")
        lines += dump(tab, 8) if tab is not None else ["tcSearchResultTab 없음"]
        # 창 안의 별도 Win32 자식 창(외부 그리드가 따로 붙어 있는지 확인)
        import win32gui
        kids = []
        win32gui.EnumChildWindows(win.handle, lambda h, acc: acc.append(h), kids)
        lines.append(f"Win32 자식 창 {len(kids)}개: " + ", ".join(sorted({win32gui.GetClassName(h) for h in kids}))[:500])
    else:
        auto_id = args.auto_id
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
