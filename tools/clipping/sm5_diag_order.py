"""정렬 실패 진단: 실행 폴더의 '정렬 전·후 그룹 엑셀'과 '검토초안'을 비교해 무엇이 잘못됐는지 추정한다.
읽기만 하고 스크랩마스터는 건드리지 않는다.

사용: python sm5_diag_order.py output\\runs\\20261031_230837
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from scrapdraft.excel_io import read_export


def plan_moves(current, desired):
    k, j = len(desired), len(current) - 1
    while k > 0:
        while j >= 0 and current[j] != desired[k - 1]:
            j -= 1
        if j < 0:
            break
        k -= 1
        j -= 1
    return list(reversed(desired[:k]))


def sim_single(cur, moves, shift=0):
    o = list(cur)
    for m in moves:
        i = o.index(m)
        i = min(max(i + shift, 0), len(o) - 1)
        o.insert(0, o.pop(i))
    return o


def sim_keep_checked(cur, moves):
    """체크가 풀리지 않고 쌓이는 경우: [맨 위로]가 체크된 기사 전부를 (현재 순서대로) 맨 위로 올림."""
    o, checked = list(cur), set()
    for m in moves:
        checked.add(m)
        block = [x for x in o if x in checked]
        o = block + [x for x in o if x not in checked]
    return o


def score(a, b):
    return sum(x == y for x, y in zip(a, b))


def main() -> int:
    d = Path(sys.argv[1])
    before = sorted(d.glob("검토그룹_후_*.xlsx"))[-1]
    after = sorted(d.glob("검토그룹_정렬후_*.xlsx"))[-1]
    draft = sorted(d.glob("검토초안_*.xlsx"))[-1]
    cur = list(read_export(before)["key"])
    fin = list(read_export(after)["key"])
    rec = pd.read_excel(draft, sheet_name="추천목록")
    desired = list(rec["기사 키"].astype(str))
    moves = plan_moves(cur, desired)
    n = len(desired)
    print(f"그룹 {len(cur)}건, 추천 {n}건, 이동 계획 {len(moves)}건")
    print(f"정렬 후 순서가 추천과 같은 자리: {score(fin, desired)}/{n}")
    print(f"정렬 후 순서가 정렬 전과 같은 자리: {score(fin, cur)}/{n}  (높으면 '이동이 안 됨')")
    hyps = {
        "정상 이동(기대값)": sim_single(cur, moves),
        "체크가 쌓여 여러 건이 함께 이동": sim_keep_checked(cur, moves),
        "한 칸 위 기사를 잘못 누름": sim_single(cur, moves, -1),
        "한 칸 아래 기사를 잘못 누름": sim_single(cur, moves, +1),
        "이동이 전혀 안 됨": list(cur),
    }
    for name, o in hyps.items():
        print(f"  {name}: 실제 결과와 같은 자리 {score(fin, o)}/{n}")
    print("\n정렬 후 앞 15건 (실제 / 추천):")
    title = dict(zip(rec["기사 키"].astype(str), rec.get("기사 제목", rec.iloc[:, 0]).astype(str)))
    for i in range(min(15, n)):
        mark = "  " if fin[i] == desired[i] else "≠ "
        print(f"{mark}{i + 1:>2}. {fin[i]} {title.get(fin[i], '')[:20]}  /  {desired[i]} {title.get(desired[i], '')[:20]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
