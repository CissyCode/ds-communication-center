"""검색결과에서 지정한 행만 체크해 '현재 선택된 스크랩 그룹'에 담는 시험 스크립트.

기본은 미리보기(--dry-run): 마우스를 누를 자리로 옮기기만 하고 아무것도 누르지 않는다.
실제 실행은 --go 를 붙였을 때만. 관리자 권한 터미널에서 실행.

준비(사람이 직접):
  1) 스크랩 목록 창을 펼치고, 시험용 그룹(예: 자동검토_테스트)을 만들어 그 탭을 선택해 둔다.
  2) [검색] 탭에서 검색어 그룹(예: 삼성 반도체)을 클릭해 결과 목록을 띄운다.

사용:
  python sm5_scrap_test.py --rows 3,5                 미리보기
  python sm5_scrap_test.py --rows 3,5 --go            실제로 체크하고 [스크랩]
  python sm5_scrap_test.py --rows 3,5 --go --group 자동검토_테스트

안전장치:
  - 선택된 스크랩 그룹 이름이 --group 과 다르면 멈춘다(기본 '자동검토_테스트').
  - '스크랩초기화·선택삭제·그룹 삭제' 등은 누르지 않는다.
  - [스크랩] 뒤 팝업이 뜨면 아무것도 누르지 않고 내용을 보여 주고 멈춘다.
  - 담기 전후 스크랩 목록 Serial을 비교해 늘어난 건수가 다르면 '불일치'로 알린다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from pywinauto import Desktop, keyboard, mouse

from sm5_read import OUT, by_id, main_window, read_grid, read_popups, texts

# 검색결과 영역(tcSearchResultTab) 기준 상대 위치(px). 5.1.11.96, 2026-10-31 화면에서 측정.
FIRST_ROW_DY = 75       # 영역 위쪽에서 첫 행 중앙까지
ROW_H = 22.2            # 행 높이
TITLE_DX = 120          # 기사 제목 칸(행 포커스용 클릭 위치)
BUTTON_DY = -27         # 영역 아래쪽에서 하단 버튼 줄 중앙까지
BUTTONS = {"선택 해제": 128, "스크랩": 275}   # 영역 왼쪽에서 버튼 중앙까지
NEVER = ("선택 삭제", "삭제 취소", "스크랩초기화", "선택삭제")  # 누르지 않는 버튼(문서용)


def selected_group(win) -> str | None:
    tab = by_id(win, "ScrapGroupTab")
    if tab is None:
        return None
    for ti in tab.children(control_type="TabItem"):
        try:
            if ti.is_selected():
                t = [x for x in texts(ti) if x not in ("×", "ScrapMaster5.ScrapGroup")]
                return "".join(t)
        except Exception:
            continue
    return None


def scrap_serials(win) -> list[dict]:
    grid = by_id(win, "scraplistDataGrid")
    if grid is None or grid.rectangle().width() == 0:
        return []
    lines = read_grid(grid)
    if not lines:
        return []
    header = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        cells = ln.split("\t")
        rows.append({h: (cells[i] if i < len(cells) else "") for i, h in enumerate(header)})
    return rows


def point(rect, dx, dy, from_bottom=False):
    return (int(rect.left + dx), int((rect.bottom if from_bottom else rect.top) + dy))


def act(xy, label, go: bool, click=True):
    mouse.move(coords=xy)
    print(f"  {'클릭' if (go and click) else '위치 확인'}: {label} {xy}")
    time.sleep(0.4 if go else 1.5)
    if go and click:
        mouse.click(coords=xy)
        time.sleep(0.4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True, help="체크할 행 번호(화면 위에서부터 1, 2, 3…), 쉼표로 구분")
    ap.add_argument("--group", default="자동검토_테스트")
    ap.add_argument("--go", action="store_true", help="실제로 누른다(없으면 미리보기)")
    args = ap.parse_args()
    rows = sorted({int(x) for x in args.rows.split(",") if x.strip()})
    if not rows or rows[0] < 1:
        sys.exit("--rows 는 1 이상의 번호여야 합니다.")

    win = main_window()
    win.set_focus()
    tab = by_id(win, "tcSearchResultTab")
    if tab is None or tab.rectangle().width() == 0:
        sys.exit("[검색] 탭의 결과 목록이 보이지 않습니다. 검색어 그룹을 클릭해 결과를 띄워 주세요.")
    count = by_id(win, "tbCurrentSearchResultCount")
    kw = by_id(win, "tbCurrentSearchResultKeywordInfo1")
    print(f"검색결과: {kw.window_text() if kw else '?'} / {count.window_text() if count else '?'}")

    group = selected_group(win)
    print(f"선택된 스크랩 그룹: {group}")
    grid = by_id(win, "scraplistDataGrid")
    if grid is None or grid.rectangle().width() == 0:
        sys.exit("스크랩 목록 창이 접혀 있습니다. 오른쪽 '스크랩 목록 열기'로 펼쳐 주세요(검증에 필요).")
    if not group or not group.startswith(args.group):
        sys.exit(f"선택된 그룹이 '{args.group}'이 아닙니다. 시험용 그룹 탭을 먼저 선택해 주세요.")

    before = scrap_serials(win)
    print(f"담기 전 그룹 기사 수: {len(before)}")

    r = tab.rectangle()
    print("미리보기 — 마우스만 움직입니다." if not args.go else "실행 — 마우스를 건드리지 마세요.")
    act(point(r, BUTTONS["선택 해제"], BUTTON_DY, True), "[선택 해제]", args.go)
    act(point(r, TITLE_DX, FIRST_ROW_DY), "첫 행(포커스)", args.go)
    current = 1
    for n in rows:
        steps = n - current
        if args.go:
            if steps:
                keyboard.send_keys("{DOWN %d}" % steps)
                time.sleep(0.2)
            keyboard.send_keys("{SPACE}")
            time.sleep(0.2)
        else:
            act(point(r, TITLE_DX, FIRST_ROW_DY + ROW_H * (n - 1)), f"{n}번째 행(체크 예정)", False, click=False)
        current = n
    act(point(r, BUTTONS["스크랩"], BUTTON_DY, True), "[스크랩]", args.go)

    if not args.go:
        print("미리보기 끝. 위치가 맞으면 --go 를 붙여 다시 실행하세요.")
        return 0

    time.sleep(1.5)
    pops = read_popups(win)
    if not pops[0].startswith("팝업 창이 없습니다"):
        print("[스크랩] 뒤 팝업이 떴습니다. 아무것도 누르지 않고 멈춥니다:")
        print("\n".join(pops))
        return 3

    after = scrap_serials(win)
    key = "Serial"
    old = {x.get(key) for x in before}
    added = [x for x in after if x.get(key) not in old]
    print(f"담은 뒤 그룹 기사 수: {len(after)} (추가 {len(added)}건, 기대 {len(rows)}건)")
    for x in added:
        print(f"  + {x.get('매체명', '')} {x.get('지면', '')} {x.get('기사 제목', '')} [Serial {x.get(key, '')}]")
    ok = len(added) == len(rows)
    print("결과: 일치" if ok else "결과: 불일치 — 화면을 확인해 주세요.")

    OUT.mkdir(exist_ok=True)
    log = OUT / "scrap_test_log.jsonl"
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), "group": group, "rows": rows,
                            "added": added, "ok": ok}, ensure_ascii=False) + "\n")
    print(f"기록: {log}")
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
