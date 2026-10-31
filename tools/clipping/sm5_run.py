"""조간 스크랩 검토 초안 자동 실행(스크랩마스터5 화면 자동화). 관리자 권한 터미널에서 실행.

흐름:
  1) [검색] 탭 → 자동검색 [결과 갱신] → 검색어별 건수 기록
  2) 후보 검색어 그룹 결과를 공식 [엑셀 저장]으로 받기
  3) 엔진(scrapdraft)으로 선정·분류·배열
  4) 검토 그룹에 이미 있는 기사(Serial)는 건너뛰고, 새 추천 기사만 체크해 [스크랩]
  5) 검토 그룹을 [엑셀로 내보내기]로 받아 Serial 검증
  6) 검토 그룹을 추천 순서로 정렬([맨 위로]) 후 다시 내보내 검증

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
from sm5_read import OUT, WINDOW_TITLE, by_id, expand_search_folders, read_keywords, read_popups, texts

HERE = Path(__file__).resolve().parent
VERSION = "2026-10-31k"

# 검색결과 영역(tcSearchResultTab) 기준 상대 위치(px). 5.1.11.96 화면에서 측정·시험 통과.
FIRST_ROW_DY = 75
TITLE_DX = 120
BUTTON_DY = -27
RESULT_BUTTONS = {"전체 선택": 51, "선택 해제": 128, "스크랩": 275, "엑셀 저장": 346}
PAGE_SIZE = 500   # 검색결과 '500개씩 보기' 기준. 넘으면 멈춤.

# 저장 항목은 '켜기만' 하고 끄지 않는다(저장 옵션은 계정 단위로 동기화되므로 담당자 설정을 줄이지 않음).
# 기본으로 켜져 있는 항목: 기사 제목·매체명·지면번호·기자·발행일·검색어·연번·기사 시리얼·스크랩 그룹
REQUIRED_COLS = ["기사 제목", "매체명", "지면번호", "발행일", "검색어", "연번", "기사 시리얼"]
SEARCH_EXTRA_COLS = ["카테고리", "크기", "부제목"]   # 광고·스포츠 제외, 크기 점수, 부제목 분류에 필요(--keep-options면 안 켬)


class Stop(Exception):
    """안전하게 멈춰야 하는 상황."""


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


# ---------- 화면 요소 ----------

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


def no_popup_or_stop(win, where: str):
    pops = read_popups(win)
    if not pops[0].startswith("팝업 창이 없습니다"):
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
    keyboard.send_keys("{ESC}")
    time.sleep(0.5)
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
    if bool(cb.get_toggle_state()) != on:
        cb.toggle()
        time.sleep(0.2)


def uncheck_all_scraps(win) -> None:
    btn = by_id(win, "btnScrapListDeSelect2") or by_id(win, "btnScrapListDeSelect")
    if btn is not None:
        press(btn)
        time.sleep(0.4)


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
            if int(cnt.split("/")[0]) > 0:
                found.append((kw, media))
    names = [k for k, _ in found]
    return [f"{k}@{m}" if names.count(k) > 1 and m else k for k, m in found]


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
    label = [x for x in texts(target) if x.strip() == keyword]
    (find(target, title=label[0], control_type="Text") if label else target).click_input()
    time.sleep(2.0)
    kw = by_id(win, "tbCurrentSearchResultKeywordInfo1")
    if kw is None or kw.window_text().strip() != keyword:
        raise Stop(f"검색결과가 '{keyword}'로 바뀌지 않았습니다.")
    tab = need(win, "tcSearchResultTab")
    for ti in tab.children(control_type="TabItem"):
        if "지면기사" in texts(ti):
            ti.select()
            time.sleep(1.0)
    cnt = by_id(win, "tbCurrentSearchResultCount").window_text()
    n = int(cnt.split("/")[0].strip() or 0)
    if n > PAGE_SIZE:
        raise Stop(f"검색결과가 {n}건으로 한 페이지({PAGE_SIZE}건)를 넘습니다. 검색어 조건을 좁혀 주세요.")
    return n


def export_search(win, path: Path, keep_options: bool) -> Path:
    result_button(win, "전체 선택")
    result_button(win, "엑셀 저장")
    out = save_dialog(win, path, REQUIRED_COLS + ([] if keep_options else SEARCH_EXTRA_COLS))
    result_button(win, "선택 해제")
    return out


def export_group(win, group: str, path: Path) -> pd.DataFrame:
    uncheck_all_scraps(win)
    item = group_tree_item(win, group)
    set_check(find(item, auto_id="cbScrapTreeGroup", control_type="CheckBox"), True)
    press(need(win, "btnScrapList_SaveToExcelFile_T"))
    save_dialog(win, path, REQUIRED_COLS)
    uncheck_all_scraps(win)
    return read_export(path)


def scrap_rows(win, seqs: list[int]) -> None:
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


def reorder(win, group: str, current: list[str], desired: list[str]) -> None:
    """current: 지금 순서의 Serial 키 목록. desired: 원하는 순서. 뒤에서부터 [맨 위로]."""
    order = list(current)
    top = need(win, "btnScrapListSelectedTop")
    uncheck_all_scraps(win)
    for key in reversed(desired):
        idx = order.index(key)
        arts = articles_of(win, group)
        if len(arts) != len(order):
            raise Stop("정렬 중 그룹 기사 수가 바뀌었습니다. 멈춥니다.")
        cb = arts[idx].children(control_type="CheckBox")[0]
        set_check(cb, True)
        press(top)
        time.sleep(0.4)
        order.insert(0, order.pop(idx))
        uncheck_all_scraps(win)


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
        for i, spec in enumerate(sources, 1):
            n = open_source_group(win, spec)
            log(f"후보 그룹 '{spec}' 지면 {n}건 — 엑셀 저장")
            if n == 0:
                continue
            src = export_search(win, run_dir / f"검색결과{i}_{stamp}.xlsx", args.keep_options)
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

        for spec in sources:
            part = todo[todo["source"] == spec]
            if part.empty:
                continue
            open_source_group(win, spec)
            select_group(win, group)
            n_b = group_count(win, group) or 0
            scrap_rows(win, [int(float(s)) for s in part["seq"]])
            n_a = group_count(win, group) or 0
            if n_a - n_b != len(part):
                raise Stop(f"'{spec}' 담기: 그룹 건수 증가 {n_a - n_b}건 ≠ 기대 {len(part)}건. 화면을 확인해 주세요.")
            log(f"'{spec}'에서 {len(part)}건 담음")

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
            reorder(win, group, list(after["key"]), desired)
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
