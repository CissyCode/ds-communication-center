"""스크랩마스터 창의 화면 구성(버튼·목록 이름)을 파일로 저장한다. 읽기만 하고 아무것도 클릭하지 않는다.

사용법 (사내 Windows PC):
  pip install pywinauto
  스크랩마스터를 열고 [검색] 탭을 띄운 상태에서
  python inspect_window.py            → output\\window_검색.txt
  python inspect_window.py 편집       → 파일 이름 꼬리표만 바뀜
  python inspect_window.py 검색 --title 창제목일부   → 창을 직접 지정

스크랩마스터 창을 못 찾으면 열려 있는 창 목록(제목·실행 파일)을 output\\windows_list.txt 로 저장한다.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import win32api
import win32con
import win32process
from pywinauto import Desktop

BROWSERS = ("chrome.exe", "msedge.exe", "whale.exe", "firefox.exe", "iexplore.exe")
HINTS = ("scrap", "sm5", "스크랩마스터")


def exe_of(pid: int) -> str:
    try:
        h = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        try:
            return Path(win32process.GetModuleFileNameEx(h, 0)).name
        finally:
            win32api.CloseHandle(h)
    except Exception:
        return "?"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tag", nargs="?", default="검색")
    ap.add_argument("--title", help="창 제목에 들어 있는 글자(직접 지정)")
    args = ap.parse_args()

    out_dir = Path(__file__).resolve().parent / "output"
    out_dir.mkdir(exist_ok=True)

    wins = []
    for w in Desktop(backend="uia").windows():
        title = w.window_text() or ""
        exe = exe_of(w.element_info.process_id)
        wins.append((w, title, exe))

    if args.title:
        targets = [x for x in wins if args.title in x[1]]
    else:
        targets = [x for x in wins
                   if x[2].lower() not in BROWSERS
                   and any(h in (x[1] + " " + x[2]).lower() for h in HINTS)]

    if not targets:
        path = out_dir / "windows_list.txt"
        with open(path, "w", encoding="utf-8") as f:
            for _, title, exe in wins:
                f.write(f"{exe}\t{title!r}\n")
        print("스크랩마스터 창을 찾지 못했습니다. 열려 있는 창 목록을 저장했습니다:", path)
        print("스크랩마스터가 실행 중인지 확인하고, 목록에서 해당 줄을 알려 주세요.")
        return 1

    path = out_dir / f"window_{args.tag}.txt"
    total = 0
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {datetime.now():%Y-%m-%d %H:%M} / 창 {len(targets)}개\n")
        for w, title, exe in targets:
            f.write(f"\n## {title}  [{exe}]\n")
            for c in w.descendants():
                total += 1
                try:
                    ei = c.element_info
                    f.write(f"{ei.control_type}\t{ei.name!r}\t{ei.automation_id!r}\t{ei.class_name!r}\n")
                except Exception as e:  # 일부 컨트롤은 정보를 주지 않음
                    f.write(f"?\t{e}\n")
    print(f"저장: {path} (요소 {total}개)")
    if total < 10:
        print("요소가 거의 없습니다. 스크랩마스터가 관리자 권한으로 실행 중이면 PowerShell도 '관리자 권한으로 실행'해서 다시 해 주세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
