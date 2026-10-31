"""스크랩마스터 창의 화면 구성(버튼·목록 이름)을 파일로 저장한다. 읽기만 하고 아무것도 클릭하지 않는다.

사용법 (사내 Windows PC):
  pip install pywinauto
  스크랩마스터를 열고 [검색] 탭을 띄운 상태에서
  python inspect_window.py
→ output\window_검색.txt 가 생깁니다. 탭을 바꿔(뉴스·편집) 다시 실행해도 됩니다.
"""
import sys
from datetime import datetime
from pathlib import Path

from pywinauto import Desktop

out_dir = Path(__file__).resolve().parent / "output"
out_dir.mkdir(exist_ok=True)
tag = sys.argv[1] if len(sys.argv) > 1 else "검색"

wins = [w for w in Desktop(backend="uia").windows() if "스크랩" in (w.window_text() or "")]
if not wins:
    print("스크랩마스터 창을 찾지 못했습니다. 창 제목:", [w.window_text() for w in Desktop(backend="uia").windows()])
    sys.exit(1)

path = out_dir / f"window_{tag}.txt"
with open(path, "w", encoding="utf-8") as f:
    f.write(f"# {datetime.now():%Y-%m-%d %H:%M} / 창 {len(wins)}개\n")
    for w in wins:
        f.write(f"\n## {w.window_text()}\n")
        for c in w.descendants():
            try:
                ei = c.element_info
                f.write(f"{ei.control_type}\t{ei.name!r}\t{ei.automation_id!r}\t{ei.class_name!r}\n")
            except Exception as e:  # 일부 컨트롤은 정보를 주지 않음
                f.write(f"?\t{e}\n")
print(f"저장: {path}")
