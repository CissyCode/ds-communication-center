"""조간 스크랩 검토 초안 자동 실행(스크랩마스터5 화면 자동화). 관리자 권한 터미널에서 실행.

흐름:
  1) [검색] 탭 → 자동검색 [결과 갱신] → 검색어별 건수 기록
  2) 후보 검색어 그룹 결과를 공식 [엑셀 저장]으로 받기
  3) 엔진(scrapdraft)으로 선정·분류·배열
  4) 검토 그룹에 이미 있는 기사(Serial)는 건너뛰고, 새 추천 기사만 추천 순서대로 [스크랩]
  5) 검토 그룹을 [엑셀로 내보내기]로 받아 Serial 검증
  6) 순서가 어긋난 기사만 [맨 위로]로 정렬 후 다시 내보내 검증

단계 제한(--until): export(2까지, 스크랩 안 함) / scrap(5까지) / order(6까지, 기본)
사람이 검토 그룹에 직접 넣은 기사가 있으면 정렬하지 않고 추가만 한다.

예:
  python sm5_run.py --until export                       읽기·내보내기만(안전 확인용)
  python sm5_run.py --group 자동검토_테스트 --until scrap
  python sm5_run.py                                      오늘 날짜 검토 그룹(자동검토_MMDD)에 전체 실행
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from pywinauto import Desktop, keyboard, mouse

from scrapdraft.config import load_config
from scrapdraft.engine import build_draft
from scrapdraft.excel_io import file_sha256, read_export
from scrapdraft.ledger import Ledger
from scrapdraft.report import write_report
from pywinauto.findwindows import ElementAmbiguousError

from sm5_read import OUT, WINDOW_TITLE, expand_search_folders, read_keywords, read_popups, texts
from sm5_read import by_id as _by_id

HERE = Path(__file__).resolve().parent
VERSION = "2026-10-31w"

# 검색결과 영역(tcSearchResultTab) 기준 상대 위치(px). 5.1.11.96 화면에서 측정·시험 통과.
FIRST_ROW_DY = 75
TITLE_DX = 120
BUTTON_DY = -27
RESULT_BUTTONS = {"전체 선택": 51, "선택 해제": 128, "스크랩": 275, "엑셀 저장": 346}
CURRENT_SPEC: str | None = None   # 지금 검색결과에 떠 있는 검색어 그룹
PAGE_SIZE = 500   # 검색결과 '500개씩 보기' 기준. 넘으면 멈춤.

# 저장 항목은 '켜기만' 하고 끄지 않는다(저장 옵션은 계정 단위로 동기화되므로 담당자 설정을 줄이지 않음).
# 기본으로 켜져 있는 항목: 기사 제목·매체명·지면번호·기자·발행일·검색어·연번·기사 시리얼·스크랩 그룹
REQUIRED_COLS = ["기사 제목", "매체명", "지면번호", "발행일", "검색어", "연번", "기사 시리얼"]
SEARCH_EXTRA_COLS = ["카테고리", "크기", "부제목"]   # 광고·스포츠 제외, 크기 점수, 부제목 분류에 필요(--keep-options면 안 켬)


class Stop(Exception):
    """안전하게 멈춰야 하는 상황."""


class SkipGroup(Stop):
    """이 검색어 그룹만 건너뛰고 나머지는 계속해도 되는 상황."""


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


# ---------- 화면 요소 ----------

def _process_windows(win) -> list:
    """본 창과, 같은 프로세스의 다른 보이는 창(그룹 관리 창 등)."""
    import win32gui
    import win32process
    pid = win.element_info.process_id
    out = [win.wrapper_object()]
    hwnds = []
    win32gui.EnumWindows(lambda h, acc: acc.append(h) if win32gui.IsWindowVisible(h) else None, hwnds)
    for h in hwnds:
        if h != win.handle and win32process.GetWindowThreadProcessId(h)[1] == pid:
            try:
                out.append(Desktop(backend="uia").window(handle=h).wrapper_object())
            except Exception:
                pass
    return out


def by_id(win, auto_id: str):
    """auto_id로 요소 찾기. 같은 이름이 여럿이면 화면에 보이는 것을 고른다(다른 창에 있는 것 포함)."""
    try:
        return _by_id(win, auto_id)
    except ElementAmbiguousError:
        pass
    cands = []
    for root in _process_windows(win):
        for e in root.descendants():
            if e.element_info.automation_id == auto_id:
                cands.append(e)
    visible = []
    for e in cands:
        try:
            if e.is_visible() and e.rectangle().width() > 0:
                visible.append(e)
        except Exception:
            continue
    return (visible or cands or [None])[-1]   # 나중에 뜬(위에 있는) 창의 것이 보통 마지막

def main_window():
    """'스크랩마스터 5' 제목 창 중 가장 큰 창을 핸들로 고정(같은 제목의 알림 창과 헷갈리지 않게)."""
    wins = list(Desktop(backend="uia").windows(title=WINDOW_TITLE))
    if not wins:
        sys.exit(f"'{WINDOW_TITLE}' 창을 찾지 못했습니다. 스크랩마스터가 켜져 있고 터미널이 관리자 권한인지 확인해 주세요.")
    main = max(wins, key=lambda w: w.rectangle().width() * w.rectangle().height())
    return Desktop(backend="uia").window(handle=main.handle)


def press(btn) -> None:
    """버튼 누르기. 자동화 '누르기' 신호(Invoke)를 받지 않는 버튼은 화면 위치를 마우스로 클릭."""
    try:
        btn.invoke()
    except Exception:
        btn.click_input()
    time.sleep(0.3)


def find(elem, auto_id: str | None = None, title: str | None = None, control_type: str | None = None):
    """요소(wrapper) 안에서 하위 요소 찾기. 창이 아닌 요소에는 child_window가 없어서 직접 훑는다."""
    for c in elem.descendants(control_type=control_type) if control_type else elem.descendants():
        ei = c.element_info
        if auto_id is not None and ei.automation_id != auto_id:
            continue
        if title is not None and c.window_text() != title:
            continue
        return c
    raise Stop(f"하위 요소를 찾지 못했습니다(auto_id={auto_id}, title={title}, type={control_type}).")


def need(win, auto_id: str):
    e = by_id(win, auto_id)
    if e is None or e.rectangle().width() == 0:
        raise Stop(f"화면 요소 '{auto_id}'가 보이지 않습니다.")
    return e


def click_rel(rect, dx, dy, from_bottom=False):
    xy = (int(rect.left + dx), int((rect.bottom if from_bottom else rect.top) + dy))
    mouse.click(coords=xy)
    time.sleep(0.4)


def result_button(win, name: str):
    r = need(win, "tcSearchResultTab").rectangle()
    click_rel(r, RESULT_BUTTONS[name], BUTTON_DY, from_bottom=True)


IGNORED_POPUP_CLASSES = ("Internet Explorer_Hidden",)   # 스크랩마스터가 늘 띄워 두는 보이지 않는 보조 창


def real_popups(win) -> list[str]:
    """read_popups 결과에서 늘 떠 있는 보조 창을 뺀 줄."""
    out, skip = [], False
    for line in read_popups(win):
        if line.startswith("## "):
            skip = any(c in line for c in IGNORED_POPUP_CLASSES)
        if line.startswith("팝업 창이 없습니다"):
            continue
        if not skip:
            out.append(line)
    return out


def no_popup_or_stop(win, where: str):
    if close_group_manager(win):          # 남아 있던 그룹 관리 창이면 닫고 다시 확인
        time.sleep(0.5)
    pops = real_popups(win)
    if pops:
        raise Stop(f"{where} 뒤에 예상하지 못한 창이 떴습니다:\n" + "\n".join(pops[:40]))


def scrap_tabs(win) -> list[tuple[object, str]]:
    tab = need(win, "ScrapGroupTab")
    out = []
    for ti in tab.children(control_type="TabItem"):
        name = "".join(x for x in texts(ti) if x not in ("×", "ScrapMaster5.ScrapGroup"))
        out.append((ti, name))
    return out


def split_name(label: str) -> tuple[str, int | None]:
    m = re.match(r"^(.*?)\s*\[(\d+)\]\s*$", label)
    return (m.group(1), int(m.group(2))) if m else (label, None)


def group_count(win, group: str) -> int | None:
    for _, label in scrap_tabs(win):
        name, n = split_name(label)
        if name == group:
            return n
    return None


def select_group(win, group: str) -> None:
    for ti, label in scrap_tabs(win):
        if split_name(label)[0] == group:
            ti.select()
            time.sleep(0.5)
            if not ti.is_selected():
                ti.click_input()
                time.sleep(0.5)
            if not ti.is_selected():
                raise Stop(f"스크랩 그룹 '{group}' 탭을 선택하지 못했습니다.")
            return
    raise Stop(f"스크랩 그룹 '{group}'이 없습니다.")


def close_group_manager(win) -> bool:
    """'스크랩 그룹 관리' 창이 열려 있으면 [닫기]로 닫는다(그룹 삭제·선택 버튼은 누르지 않음)."""
    closed = False
    for w in _process_windows(win)[1:]:
        try:
            if w.window_text() != "스크랩 그룹 관리" and not any(
                    t.window_text() == "스크랩 그룹 관리" for t in w.descendants(control_type="Text")):
                continue
            for aid in ("btnClose", "btnCloseWindow", "btnCloseSync"):
                btn = next((b for b in w.descendants(control_type="Button")
                            if b.element_info.automation_id == aid and b.is_visible()), None)
                if btn is not None:
                    press(btn)
                    time.sleep(0.5)
                    closed = True
                    break
        except Exception:
            continue
    if closed:
        log("'스크랩 그룹 관리' 창을 닫음")
    return closed


def ensure_group(win, group: str) -> None:
    if group_count(win, group) is not None:
        return
    log(f"스크랩 그룹 '{group}' 만들기")
    press(need(win, "buttonScrapGroupAdd"))
    time.sleep(0.8)
    box = by_id(win, "tbNewScrapGroup")
    add = by_id(win, "btnAddScrapGroup")
    if box is None or add is None:
        raise Stop(f"그룹 추가 창을 찾지 못했습니다. '{group}' 그룹을 직접 만든 뒤 다시 실행해 주세요.")
    box.set_edit_text(group)
    press(add)
    time.sleep(0.8)
    close_group_manager(win)
    if group_count(win, group) is None:
        raise Stop(f"'{group}' 그룹을 만들지 못했습니다. 직접 만든 뒤 다시 실행해 주세요.")


def group_tree_item(win, group: str):
    tree = need(win, "treeScrapArticleList")
    for item in tree.children(control_type="TreeItem"):
        if item.element_info.name != "ScrapMaster5.ScrapGroup":
            continue
        t = texts(item)
        if t and t[0] == group:
            return item
    raise Stop(f"스크랩 목록 트리에서 '{group}'을 찾지 못했습니다.")


def articles_of(win, group: str) -> list:
    item = group_tree_item(win, group)
    kids = [k for k in item.children(control_type="TreeItem") if k.element_info.name == "ScrapMaster5.Article"]
    if not kids and (group_count(win, group) or 0) > 0:
        exp = find(item, auto_id="chkExpand")
        exp.click_input()
        time.sleep(0.6)
        kids = [k for k in item.children(control_type="TreeItem") if k.element_info.name == "ScrapMaster5.Article"]
    return kids


def set_check(cb, on: bool) -> None:
    """체크 상태 맞추기. 신호(toggle)로 안 바뀌면 화면 클릭으로 다시 시도."""
    if bool(cb.get_toggle_state()) == on:
        return
    cb.toggle()
    time.sleep(0.3)
    if bool(cb.get_toggle_state()) != on:
        cb.click_input()
        time.sleep(0.3)


def click_visible(win, auto_ids) -> bool:
    """여러 후보 중 화면에 보이는 버튼을 실제로 클릭(스크랩 목록 버튼은 '누르기 신호'에 반응하지 않음)."""
    for aid in auto_ids:
        btn = by_id(win, aid)
        try:
            if btn is not None and btn.is_visible() and btn.rectangle().width() > 0:
                btn.click_input()
                time.sleep(0.5)
                return True
        except Exception:
            continue
    return False


def uncheck_all_scraps(win) -> None:
    click_visible(win, ("btnScrapListDeSelect_T", "btnScrapListDeSelect2", "btnScrapListDeSelect"))


# ---------- 저장 창 ----------

def save_dialog(win, path: Path, columns: list[str], timeout=10) -> Path:
    import win32gui
    import win32process
    pid = win.element_info.process_id
    dlg = None
    end = time.time() + timeout
    while time.time() < end and dlg is None:
        hwnds = []
        win32gui.EnumWindows(lambda h, acc: acc.append(h) if win32gui.IsWindowVisible(h) else None, hwnds)
        for h in hwnds:
            if (win32gui.GetWindowText(h) == "다른 이름으로 파일 저장"
                    and win32process.GetWindowThreadProcessId(h)[1] == pid):
                dlg = Desktop(backend="uia").window(handle=h).wrapper_object()
                break
        time.sleep(0.3)
    if dlg is None:
        raise Stop("'다른 이름으로 파일 저장' 창이 뜨지 않았습니다.")

    try:  # 편집 목차 저장 창에만 있는 선택지. 스크랩 목록·검색결과 저장 창에서는 숨겨져 있음
        rb = find(dlg, auto_id="rbCustom", control_type="RadioButton")
        if rb.is_visible() and rb.is_enabled():
            rb.select()
            time.sleep(0.2)
    except Exception:
        pass
    time.sleep(1.0)  # 창이 뜬 직후 프로그램이 체크 상태를 다시 채우므로 잠시 기다린 뒤 바꾼다
    wanted = set(columns)
    boxes = {cb.window_text(): cb for cb in dlg.descendants(control_type="CheckBox")
             if cb.element_info.automation_id.startswith("ckbcol")}
    missing = wanted - set(boxes)
    if missing & set(REQUIRED_COLS):
        raise Stop(f"저장 창에 필요한 항목이 없습니다: {sorted(missing)}")
    failed = []
    for name in sorted(wanted & set(boxes)):
        cb = boxes[name]
        if cb.get_toggle_state() == 1:
            continue                      # 이미 켜져 있으면 그대로(끄지 않음)
        cb.click_input()                  # 화면 클릭(프로그램이 클릭 이벤트로 상태를 읽음)
        time.sleep(0.3)
        if cb.get_toggle_state() != 1:
            cb.toggle()
            time.sleep(0.3)
        if cb.get_toggle_state() != 1:
            failed.append(name)
    if set(failed) & set(REQUIRED_COLS):
        raise Stop(f"저장 항목을 켜지 못했습니다: {failed}. 저장 창에서 직접 체크한 뒤 다시 실행해 주세요.")
    log("저장 항목: " + ", ".join(n for n, cb in boxes.items() if cb.get_toggle_state() == 1))
    edit = find(dlg, auto_id="1148", control_type="Edit")
    edit.set_edit_text(str(path))
    time.sleep(0.2)
    press(find(dlg, auto_id="1", control_type="Button"))

    end = time.time() + 30
    while time.time() < end:
        dismiss_notices(win)
        if path.exists() and path.stat().st_size > 0:
            time.sleep(1.0)
            dismiss_notices(win)
            return path
        time.sleep(0.5)
    raise Stop(f"엑셀 파일이 만들어지지 않았습니다: {path}")


# 저장 뒤 뜨는 알림 창에서 누를 버튼 우선순위('파일을 여시겠습니까?'에는 열지 않음)
NOTICE_BUTTONS = ["아니요", "아니오", "아니요(N)", "아니오(N)", "No", "확인", "OK", "닫기"]


def dismiss_notices(win) -> None:
    """본 창 외에 같은 프로세스의 작은 알림 창(메시지 상자)이 있으면 내용을 기록하고 닫는다."""
    import win32gui
    import win32process
    pid = win.element_info.process_id
    main = win.handle
    hwnds = []
    win32gui.EnumWindows(lambda h, acc: acc.append(h) if win32gui.IsWindowVisible(h) else None, hwnds)
    for h in hwnds:
        if h == main or win32process.GetWindowThreadProcessId(h)[1] != pid:
            continue
        title = win32gui.GetWindowText(h)
        if title == "다른 이름으로 파일 저장" or win32gui.GetClassName(h) == "Internet Explorer_Hidden":
            continue
        try:
            dlg = Desktop(backend="uia").window(handle=h).wrapper_object()
            buttons = {}
            for b in dlg.descendants(control_type="Button"):
                try:
                    if b.is_visible() and b.window_text():
                        buttons[b.window_text()] = b
                except Exception:
                    continue
            msg = " / ".join(t.window_text() for t in dlg.descendants(control_type="Text") if t.window_text())
        except Exception:
            continue
        order = NOTICE_BUTTONS if ("열" in msg and "?" in msg) else ["확인", "OK", "닫기"] + NOTICE_BUTTONS
        for name in order:
            if name in buttons:
                log(f"알림 창 '{title}': {msg[:120]} → [{name}]")
                press(buttons[name])
                time.sleep(0.5)
                break


# ---------- 단계 ----------

def refresh_search(win, wait_s: int) -> list[str]:
    press(need(win, "newssearchButton"))
    time.sleep(1.0)
    press(need(win, "btnAutoSeaechRefresh"))
    log(f"자동검색 결과 갱신 — {wait_s}초 대기")
    time.sleep(wait_s)
    return read_keywords(win)


def list_source_groups(win) -> list[str]:
    """'관심 키워드' 폴더의 검색어 그룹 중 지면 결과가 있는 것. 같은 검색어가 여럿이면 '검색어@매체수'."""
    tree = need(win, "treeSearchResultGroups")
    expand_search_folders(tree)
    time.sleep(0.5)
    found = []
    for folder in tree.children(control_type="TreeItem"):
        ft = texts(folder)
        if not ft or ft[0] != "관심 키워드":
            continue
        for item in folder.children(control_type="TreeItem"):
            if item.element_info.name != "ScrapMaster5.SearchGroup":
                continue
            t = texts(item)
            if not t:
                continue
            kw = t[0].strip()
            cnt = next((x for x in t if re.fullmatch(r"\d+ / [\d-]+", x)), "0 / 0")
            media = next((m.group(1) for x in t for m in [re.search(r"매체:(\d+)/", x)] if m), "")
            n = int(cnt.split("/")[0])
            if n > 0:
                found.append((kw, media, n))
    names = [k for k, _, _ in found]
    specs = []
    for k, m, n in found:
        spec = f"{k}@{m}" if names.count(k) > 1 and m else k
        GROUP_COUNTS[spec] = n
        specs.append(spec)
    return specs


GROUP_COUNTS: dict[str, int] = {}   # 검색어 그룹별 지면 건수(목록에서 읽은 값)


def cache_index(target: date) -> tuple[Path, dict]:
    """같은 날 이전 실행에서 저장한 검색어 그룹별 엑셀. 건수가 그대로면 다시 저장하지 않고 재사용."""
    import json
    d = OUT / "cache" / target.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    f = d / "index.json"
    return d, (json.loads(f.read_text(encoding="utf-8")) if f.exists() else {})


def save_cache_index(d: Path, index: dict) -> None:
    import json
    (d / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


def open_source_group(win, spec: str) -> int:
    """spec: '검색어' 또는 '검색어@매체수'(같은 검색어가 여러 개일 때, 예: '삼성 반도체@3' = 석간 3개 매체용)."""
    keyword, _, media_n = spec.partition("@")
    tree = need(win, "treeSearchResultGroups")
    expand_search_folders(tree)
    time.sleep(0.5)
    target = None
    for item in tree.descendants(control_type="TreeItem"):
        if item.element_info.name != "ScrapMaster5.SearchGroup":
            continue
        t = texts(item)
        if not t or t[0].strip() != keyword:
            continue
        if media_n and not any(f"매체:{media_n}/" in x for x in t):
            continue
        target = item
        break
    if target is None:
        raise Stop(f"검색어 그룹 '{spec}'을 찾지 못했습니다. [검색] 탭 왼쪽 '관심 키워드' 목록이 펼쳐져 있는지 확인해 주세요.")
    def switched() -> bool:
        kw = by_id(win, "tbCurrentSearchResultKeywordInfo1")
        return kw is not None and kw.window_text().strip() == keyword

    global CURRENT_SPEC
    if CURRENT_SPEC != spec and CURRENT_SPEC is not None and CURRENT_SPEC.partition("@")[0] == keyword:
        # 같은 검색어(매체 수만 다름)끼리는 제목으로 바뀐 걸 알 수 없으므로 선택 후 잠시 기다린다
        try:
            target.select()
        except Exception:
            label = [x for x in texts(target) if x.strip() == keyword]
            (find(target, title=label[0], control_type="Text") if label else target).click_input()
        time.sleep(3)
    if not switched():
        try:
            target.select()          # 목록에서 선택(화면 밖에 있어도 동작)
        except Exception:
            pass
        end = time.time() + 4
        while time.time() < end and not switched():
            time.sleep(0.5)
    if not switched():
        try:
            target.scroll_into_view() if hasattr(target, "scroll_into_view") else None
        except Exception:
            pass
        label = [x for x in texts(target) if x.strip() == keyword]
        (find(target, title=label[0], control_type="Text") if label else target).click_input()
        end = time.time() + 10       # 결과가 많은 그룹은 바뀌는 데 시간이 걸린다
        while time.time() < end and not switched():
            time.sleep(0.5)
    if not switched():
        raise SkipGroup(f"검색결과가 '{keyword}'로 바뀌지 않았습니다.")
    CURRENT_SPEC = spec
    tab = need(win, "tcSearchResultTab")
    for ti in tab.children(control_type="TabItem"):
        if "지면기사" in texts(ti):
            ti.select()
            time.sleep(1.0)
    cnt = by_id(win, "tbCurrentSearchResultCount").window_text()
    n = int(cnt.split("/")[0].strip() or 0)
    if n > PAGE_SIZE:
        raise SkipGroup(f"'{keyword}' 검색결과가 {n}건으로 한 페이지({PAGE_SIZE}건)를 넘습니다. 검색어 조건을 좁혀 주세요.")
    return n


def export_search(win, path: Path, keep_options: bool) -> Path:
    result_button(win, "전체 선택")
    result_button(win, "엑셀 저장")
    out = save_dialog(win, path, REQUIRED_COLS + ([] if keep_options else SEARCH_EXTRA_COLS))
    result_button(win, "선택 해제")
    return out


EXPORT_BUTTONS = ("btnScrapList_SaveToExcelFile_T", "btnScrapList_SaveToExcelFile2", "btnScrapList_SaveToExcelFile")


def export_group(win, group: str, path: Path) -> pd.DataFrame:
    """검토 그룹 기사만 체크하고 스크랩 목록 [엑셀로 내보내기]로 저장."""
    uncheck_all_scraps(win)
    item = group_tree_item(win, group)
    cb = find(item, auto_id="cbScrapTreeGroup", control_type="CheckBox")
    if not cb.get_toggle_state():
        cb.click_input()          # 신호(toggle)는 화면만 바뀌고 프로그램 선택은 안 될 수 있어 실제 클릭
        time.sleep(0.5)
    if not cb.get_toggle_state():
        raise Stop(f"스크랩 목록에서 '{group}' 그룹을 체크하지 못했습니다.")
    last_err = None
    for aid in EXPORT_BUTTONS:          # 화면에 보이는 내보내기 버튼을 차례로 시도
        btn = by_id(win, aid)
        try:
            if btn is None or not btn.is_visible() or btn.rectangle().width() == 0:
                continue
        except Exception:
            continue
        btn.click_input()         # 이 버튼은 '누르기 신호'에 반응하지 않아 실제 클릭
        time.sleep(0.8)
        try:
            save_dialog(win, path, REQUIRED_COLS)
            break
        except Stop as e:
            last_err = e
            pops = real_popups(win)
            if pops:
                log("내보내기 뒤 뜬 창: " + " / ".join(x.strip() for x in pops[:8]))
            dismiss_notices(win)
    else:
        raise Stop(f"그룹 엑셀 내보내기에 실패했습니다: {last_err or '보이는 내보내기 버튼이 없습니다'}")
    uncheck_all_scraps(win)
    return read_export(path)


def scrap_rows(win, seqs: list[int]) -> None:
    close_group_manager(win)   # 남아 있는 그룹 관리 창이 있으면 먼저 닫는다
    r = need(win, "tcSearchResultTab").rectangle()
    result_button(win, "선택 해제")
    click_rel(r, TITLE_DX, FIRST_ROW_DY)
    current = 1
    for n in sorted(seqs):
        if n - current:
            keyboard.send_keys("{DOWN %d}" % (n - current))
            time.sleep(0.15)
        keyboard.send_keys("{SPACE}")
        time.sleep(0.15)
        current = n
    result_button(win, "스크랩")
    time.sleep(1.5)
    no_popup_or_stop(win, "[스크랩]")


def plan_batches(keys: list[str], options: dict[str, list[tuple[str, int]]]) -> list[tuple[str, list[str], list[int]]]:
    """추천 순서(keys)대로 담기 위한 묶음 계획. 한 번의 [스크랩]은 검색결과 목록 순서(연번 오름차순)로
    그룹 끝에 쌓인다고 보고, 같은 검색어 그룹에서 연번이 커지는 동안 이어지는 기사들을 한 묶음으로 만든다.
    같은 기사가 여러 검색어 그룹에 있으면 가장 길게 이어지는 그룹을 고른다.
    반환: [(검색어 그룹, [기사 키...], [연번...]), ...]"""
    by_src: dict[str, dict[str, int]] = {}
    for k, opts in options.items():
        for src, seq in opts:
            by_src.setdefault(src, {}).setdefault(k, seq)
    batches = []
    i = 0
    while i < len(keys):
        best = None
        for src, _ in options.get(keys[i], []):
            m = by_src[src]
            j, last = i, -1
            while j < len(keys) and keys[j] in m and m[keys[j]] > last:
                last = m[keys[j]]
                j += 1
            if best is None or j - i > best[1] - i:
                best = (src, j)
        if best is None:
            raise Stop(f"담을 기사 {keys[i]}의 검색어 그룹·연번을 찾지 못했습니다.")
        src, j = best
        batches.append((src, keys[i:j], [by_src[src][k] for k in keys[i:j]]))
        i = j
    return batches


def _container_elements(item) -> list:
    """그룹(트리 항목) 아래 항목들을 화면 밖 것까지 순서대로 가져온다(실체화는 하지 않음).

    스크랩 목록은 화면에 보이는 기사만 자동화 도구에 알려 주므로 ItemContainer 패턴으로 차례로 찾는다.
    (전부 실체화하면 목록이 마지막 항목 쪽으로 스크롤돼 버려서, 필요한 한 건만 실체화한다.)"""
    import ctypes

    from comtypes.automation import VARIANT
    from pywinauto.uia_defines import IUIA, get_elem_interface

    container = get_elem_interface(item.element_info.element, "ItemContainer")
    null = ctypes.POINTER(IUIA().UIA_dll.IUIAutomationElement)()
    out, prev = [], null
    for _ in range(2000):
        el = container.FindItemByProperty(prev, 0, VARIANT())
        if not el:
            break
        out.append(el)
        prev = el
    return out


def _rid(el) -> tuple:
    try:
        return tuple(el.GetRuntimeId())
    except Exception:
        return ()


def _expanded_group(win, group: str):
    item = group_tree_item(win, group)
    if item.get_expand_state() != 1:
        try:
            item.expand()
        except Exception:
            find(item, auto_id="chkExpand").click_input()
        time.sleep(0.6)
        item = group_tree_item(win, group)
    return item


def _article_elements(win, group: str) -> list:
    item = _expanded_group(win, group)
    out = []
    for el in _container_elements(item):
        try:
            name = el.CurrentName
        except Exception:
            name = ""
        if name in ("", "ScrapMaster5.Article"):
            out.append(el)
    return out


def _visible_articles(win, group: str) -> list:
    """화면 목록 안에 실제로 보이는(체크박스를 누를 수 있는) 기사 항목."""
    tr = need(win, "treeScrapArticleList").rectangle()
    item = group_tree_item(win, group)
    vis = []
    for k in item.children(control_type="TreeItem"):
        if k.element_info.name != "ScrapMaster5.Article":
            continue
        r = k.rectangle()
        if r.height() > 0 and r.top >= tr.top and r.bottom <= tr.bottom:
            vis.append(k)
    return vis


def _dump_tree(win, group: str, note: str) -> None:
    OUT.mkdir(exist_ok=True)
    p = OUT / f"reorder_debug_{datetime.now():%H%M%S}.txt"
    try:
        tr = need(win, "treeScrapArticleList").rectangle()
        item = group_tree_item(win, group)
        lines = [note, f"tree {tr}"]
        for k in item.children(control_type="TreeItem"):
            lines.append(f"{k.element_info.name}\t{k.rectangle()}\t{k.element_info.runtime_id}\t"
                         f"cb={len(k.descendants(control_type='CheckBox'))}\t{texts(k)[:3]}")
        p.write_text("\n".join(lines), encoding="utf-8")
        log(f"진단 기록: {p}")
    except Exception as e:
        log(f"진단 기록 실패: {e}")


def _bring_into_view(win, group: str, idx: int, total: int):
    """idx번째 기사가 화면에 보이게 스크롤하고, 그 항목(보이는 래퍼)을 돌려준다."""
    from pywinauto.uia_defines import get_elem_interface

    tree = need(win, "treeScrapArticleList")
    tr = tree.rectangle()
    centre = ((tr.left + tr.right) // 2, (tr.top + tr.bottom) // 2)
    last_vis = None
    for step in range(80):
        els = _article_elements(win, group)
        if len(els) != total:
            raise Stop(f"정렬 중 그룹 기사 수가 바뀌었습니다({len(els)} ≠ {total}). 멈춥니다.")
        target = els[idx]
        if step == 0:
            try:   # 가상 항목이면 실체화(WPF는 이때 해당 항목 쪽으로 스크롤하기도 함)
                get_elem_interface(target, "VirtualizedItem").Realize()
                time.sleep(0.4)
                els = _article_elements(win, group)
                target = els[idx]
            except Exception:
                pass
            try:
                get_elem_interface(target, "ScrollItem").ScrollIntoView()
                time.sleep(0.4)
            except Exception:
                pass
        want = _rid(target)
        pos = {_rid(e): i for i, e in enumerate(els)}
        vis = _visible_articles(win, group)
        for k in vis:
            if want and tuple(k.element_info.runtime_id or ()) == want:
                return k
        idxs = sorted(pos[r] for r in (tuple(k.element_info.runtime_id or ()) for k in vis) if r in pos)
        if idxs and idxs[0] <= idx <= idxs[-1]:
            # 범위 안인데 일치가 없으면 아이디가 안 맞는 것 — 위치(순번)로 고른다
            by_top = sorted(vis, key=lambda k: k.rectangle().top)
            first = idxs[0]
            if 0 <= idx - first < len(by_top) and len(idxs) == len(by_top):
                return by_top[idx - first]
        if idxs and idxs == last_vis and step > 3:
            break   # 더 이상 스크롤되지 않음
        last_vis = idxs
        down = (not idxs) or idx > idxs[-1]
        gap = (idx - idxs[-1]) if (idxs and down) else ((idxs[0] - idx) if idxs else 3)
        mouse.scroll(coords=centre, wheel_dist=-max(1, min(5, gap // 3 + 1)) if down else max(1, min(5, gap // 3 + 1)))
        time.sleep(0.35)
    _dump_tree(win, group, f"idx={idx} total={total}")
    raise Stop(f"{idx + 1}번째 기사를 화면에 띄우지 못했습니다(스크롤 실패).")


def plan_moves(current: list[str], desired: list[str]) -> list[str]:
    """[맨 위로]로 옮겨야 하는 기사(옮길 순서대로). desired의 뒷부분 중 current에 이미 같은 순서로
    놓인 가장 긴 꼬리는 그대로 두고, 나머지만 뒤에서부터 맨 위로 올린다."""
    k = len(desired)
    j = len(current) - 1
    while k > 0:
        while j >= 0 and current[j] != desired[k - 1]:
            j -= 1
        if j < 0:
            break
        k -= 1
        j -= 1
    return list(reversed(desired[:k]))


def reorder(win, group: str, current: list[str], desired: list[str]) -> None:
    """current: 지금 순서의 Serial 키 목록. desired: 원하는 순서. 뒤에서부터 [맨 위로]."""
    order = list(current)
    total = len(order)
    uncheck_all_scraps(win)
    els = _article_elements(win, group)
    if len(els) != total:
        raise Stop(f"스크랩 목록에서 읽은 기사 수({len(els)})가 그룹 엑셀({total})과 다릅니다. 멈춥니다.")
    moves = plan_moves(order, desired)
    log(f"정렬 시작: {len(desired)}건 중 {len(moves)}건 이동")
    for n, key in enumerate(moves, 1):
        idx = order.index(key)
        if idx == 0:
            continue
        art = _bring_into_view(win, group, idx, total)
        cbs = art.descendants(control_type="CheckBox")
        if not cbs:
            _dump_tree(win, group, f"no checkbox idx={idx}")
            raise Stop(f"{idx + 1}번째 기사의 체크박스를 찾지 못했습니다.")
        cb = cbs[0]
        if not cb.get_toggle_state():
            cb.click_input()
            time.sleep(0.3)
        if not cb.get_toggle_state():
            raise Stop("정렬할 기사를 체크하지 못했습니다.")
        if not click_visible(win, ("btnScrapListSelectedTop",)):
            raise Stop("[맨 위로] 버튼이 보이지 않습니다.")
        time.sleep(0.5)
        order.insert(0, order.pop(idx))
        uncheck_all_scraps(win)
        if n == 1:   # 첫 이동이 실제로 맨 위로 갔는지 확인(아이디가 유지되는 경우에만 판단 가능)
            moved = tuple(art.element_info.runtime_id or ())
            top = _rid(_article_elements(win, group)[0])
            if moved and top and moved != top:
                log("주의: 첫 이동 뒤 맨 위 항목 아이디가 다릅니다(최종 검증에서 다시 확인).")
        if n % 10 == 0:
            log(f"정렬 진행 {n}/{len(moves)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="대상 일자(기본 오늘)")
    ap.add_argument("--group", help="검토 그룹 이름(기본 자동검토_MMDD)")
    ap.add_argument("--source", action="append",
                    help="후보로 쓸 검색어 그룹(여러 번 지정 가능). 'all'이면 관심 키워드 전체. 같은 이름이 여럿이면 '이름@매체수'. 기본 '삼성 반도체'")
    ap.add_argument("--until", choices=["export", "scrap", "order"], default="order")
    ap.add_argument("--config", default=str(HERE / "config.yaml"))
    ap.add_argument("--issues", default=str(HERE / "issues.yaml"))
    ap.add_argument("--today", default=None)
    ap.add_argument("--refresh-wait", type=int, default=20)
    ap.add_argument("--no-refresh", action="store_true", help="결과 갱신을 건너뜀")
    ap.add_argument("--keep-options", action="store_true",
                    help="엑셀 저장 항목을 전혀 바꾸지 않음(카테고리·크기·부제목 없이 선정 — 광고·스포츠 제외 약해짐)")
    args = ap.parse_args()

    target = date.fromisoformat(args.date) if args.date else date.today()
    group = args.group or f"자동검토_{target:%m%d}"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUT / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    extras = [p for p in (args.issues, args.today) if p and Path(p).exists()]
    cfg = load_config(args.config, extras)
    ledger = Ledger(OUT / "ledger.sqlite")

    log(f"sm5_run {VERSION}")
    win = main_window()
    win.set_focus()
    try:
        # 1) 갱신
        if not args.no_refresh:
            kw_lines = refresh_search(win, args.refresh_wait)
        else:
            press(need(win, "newssearchButton"))
            time.sleep(1.0)
            kw_lines = read_keywords(win)
        (run_dir / "keywords.txt").write_text("\n".join(kw_lines), encoding="utf-8")
        log(f"검색어 {len(kw_lines)}개 건수 기록")
        if not kw_lines:
            raise Stop("검색어 목록을 읽지 못했습니다. [검색] 탭 왼쪽 '관심 키워드'를 펼쳐 둔 뒤 다시 실행해 주세요.")

        # 2) 후보 내보내기(검색어 그룹별)
        sources = args.source or ["삼성 반도체"]
        if sources == ["all"]:
            sources = list_source_groups(win)
            log(f"검색어 그룹 {len(sources)}개(지면 결과 있는 것)를 후보로 사용")
        parts, src = [], None
        skipped = []
        cdir, cidx = cache_index(target)
        for i, spec in enumerate(sources, 1):
            cached = cidx.get(spec)
            tree_n = GROUP_COUNTS.get(spec)
            if cached and tree_n and cached.get("count") == tree_n and (cdir / cached["file"]).exists():
                n = tree_n
                src = cdir / cached["file"]
                log(f"후보 그룹 '{spec}' 지면 {n}건 — 변화 없음, 직전 저장본 사용")
            else:
                try:
                    n = open_source_group(win, spec)
                except SkipGroup as e:
                    if len(sources) == 1:
                        raise
                    log(f"건너뜀: {e}")
                    skipped.append(spec)
                    continue
                if n == 0:
                    log(f"후보 그룹 '{spec}' 지면 0건 — 건너뜀")
                    continue
                log(f"후보 그룹 '{spec}' 지면 {n}건 — 엑셀 저장")
                src = export_search(win, run_dir / f"검색결과{i}_{stamp}.xlsx", args.keep_options)
                import shutil
                name = f"g{abs(hash(spec)) % 10**8}.xlsx"
                shutil.copyfile(src, cdir / name)
                cidx[spec] = {"count": n, "file": name}
                save_cache_index(cdir, cidx)
            part = read_export(src)
            cols = set(part.attrs.get("has_columns", []))
            if not {"seq", "serial"} <= cols:
                raise Stop(f"저장된 엑셀에 연번·기사 시리얼이 없습니다(있는 항목: {sorted(cols)}). 저장 항목 체크가 반영되지 않았습니다.")
            if len(part) != n:
                raise Stop(f"'{spec}' 엑셀 행 수({len(part)})와 화면 건수({n})가 다릅니다.")
            if part["seq"].isna().any():
                raise Stop("엑셀에 '연번'이 없습니다. 저장 항목을 확인해 주세요.")
            # [지면기사] 탭에서 저장했으므로 '구분' 항목이 없으면 지면으로 본다
            part["kind"] = part["kind"].where(part["kind"].astype(str).str.strip() != "", "지면")
            part["source"] = spec
            parts.append(part)
        if not parts:
            raise Stop("후보 검색어 그룹에 지면 기사가 없습니다.")
        if skipped:
            log(f"건너뛴 검색어 그룹 {len(skipped)}개: {skipped}")
            (run_dir / "skipped_groups.txt").write_text("\n".join(skipped), encoding="utf-8")
        df = pd.concat(parts, ignore_index=True)  # 같은 기사는 엔진이 Serial로 1건으로 합침(먼저 나온 그룹 기준)

        # 3) 엔진
        res = build_draft(df, cfg, target)
        run_id = ledger.start_run(target, str(src), file_sha256(src), cfg.sha256, len(df))
        new = ledger.record_candidates(run_id, target, res.selected)
        res.selected["new"] = res.selected["key"].map(lambda k: "신규" if k in new else "")
        report = write_report(run_dir / f"검토초안_{target}_run{run_id}.xlsx", res, {
            "대상 일자": target.isoformat(), "실행 번호": run_id, "후보 그룹": ", ".join(sources), "검토 그룹": group,
            "입력 기사 수": len(df), "추천": len(res.selected), "전체 상태": res.overall,
            **({"분량(참고 범위, 자르지 않음)": f"{len(res.selected)}건 / {cfg.volume_range[0]}~{cfg.volume_range[1]}건"}
               if cfg.volume_range else {}),
        })
        log(f"추천 {len(res.selected)}건 / 참고 {len(res.reference)} / 제외·중복 {len(res.removed)} — {report.name}")
        log(f"신문별 상태: {res.overall}")
        if args.until == "export":
            ledger.finish_run(run_id, res.overall, len(res.selected), res.paper_status)
            log("내보내기 단계까지 완료(스크랩 안 함).")
            return 0

        # 4) 검토 그룹 준비, 이미 담긴 기사 확인
        ensure_group(win, group)
        select_group(win, group)
        n_before = group_count(win, group) or 0
        existing = export_group(win, group, run_dir / f"검토그룹_전_{stamp}.xlsx") if n_before else pd.DataFrame(columns=["key"])
        have = set(existing["key"]) if not existing.empty else set()
        todo = res.selected[~res.selected["key"].isin(have)]
        log(f"검토 그룹 기존 {n_before}건, 새로 담을 {len(todo)}건")

        # 추천 순서대로 담는다(같은 검색어 그룹에서 이어지는 기사는 한 번에). 그러면 정렬 이동이 거의 없다.
        options: dict[str, list[tuple[str, int]]] = {}
        for k, src, seq in df[["key", "source", "seq"]].itertuples(index=False):
            if pd.notna(seq):
                options.setdefault(k, []).append((src, int(float(seq))))
        batches = plan_batches(list(todo["key"]), options)
        if batches:
            log(f"추천 순서대로 담기: {len(todo)}건을 {len(batches)}번에 나눠 담음")
        for b, (spec, keys, seqs) in enumerate(batches, 1):
            open_source_group(win, spec)
            select_group(win, group)
            n_b = group_count(win, group) or 0
            scrap_rows(win, seqs)
            n_a = group_count(win, group) or 0
            if n_a - n_b != len(keys):
                raise Stop(f"'{spec}' 담기: 그룹 건수 증가 {n_a - n_b}건 ≠ 기대 {len(keys)}건. 화면을 확인해 주세요.")
            if b % 10 == 0:
                log(f"담기 진행 {b}/{len(batches)}")

        # 5) 검증
        after = export_group(win, group, run_dir / f"검토그룹_후_{stamp}.xlsx")
        missing = set(res.selected["key"]) - set(after["key"])
        mine = set(ledger_keys(ledger, target))
        extra = [k for k in after["key"] if k not in mine]
        if missing:
            raise Stop(f"추천했는데 그룹에 없는 기사 {len(missing)}건: {sorted(missing)[:10]}")
        log(f"Serial 검증 통과(그룹 {len(after)}건)")
        if args.until == "scrap":
            ledger.finish_run(run_id, res.overall, len(res.selected), res.paper_status)
            return 0

        # 6) 정렬 — 사람이 넣은 기사가 있으면 정렬하지 않음
        if extra:
            log(f"자동 추천 외 기사 {len(extra)}건이 있어 정렬하지 않습니다(수동 작업 보존).")
        else:
            desired = list(res.selected["key"])
            moves = plan_moves(list(after["key"]), desired)
            if moves:
                log(f"담긴 순서와 추천 순서가 {len(moves)}건 다름 — 정렬 진행")
                reorder(win, group, list(after["key"]), desired)
            else:
                log("담긴 순서가 이미 추천 순서와 같음 — 정렬 생략")
            final = export_group(win, group, run_dir / f"검토그룹_정렬후_{stamp}.xlsx")
            if list(final["key"])[: len(desired)] != desired:
                raise Stop("정렬 후 순서가 추천안과 다릅니다. 화면을 확인해 주세요.")
            log("정렬 검증 통과")
        ledger.finish_run(run_id, res.overall, len(res.selected), res.paper_status)
        log(f"완료 — 검토 그룹 '{group}', 상태: {res.overall}")
        return 0 if res.overall == "완료" else 2
    except Stop as e:
        log(f"멈춤: {e}")
        log(f"이번 실행 파일: {run_dir}")
        return 3


def ledger_keys(ledger: Ledger, target: date) -> list[str]:
    return [k for k, *_ in ledger.recommended(target)]


if __name__ == "__main__":
    sys.exit(main())
