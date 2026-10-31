"""사람의 확정 결과와 추천안 비교(추가·제외·이동) 및 과거 완성본 분석."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from .excel_io import read_export


def _final_articles(df: pd.DataFrame) -> pd.DataFrame:
    """목차 엑셀에서 기사 행만, 순서대로. 소제목 행은 바로 아래 기사들의 소제목으로 쓴다."""
    rows, current = [], ""
    for _, r in df.iterrows():
        if r["is_subhead"]:
            current = r["title"]
            continue
        rows.append({**r.to_dict(), "subhead_ctx": r.get("subhead") or r.get("group") or current})
    out = pd.DataFrame(rows)
    if not out.empty:
        out["final_rank"] = range(1, len(out) + 1)
    return out


def diff_against_final(recommended: list[tuple], final_df: pd.DataFrame) -> list[dict]:
    final = _final_articles(final_df)
    rec = {k: (rank, media, title) for k, rank, media, title in recommended}
    fin = {r["key"]: r for _, r in final.iterrows()} if not final.empty else {}
    rows = []
    for k, r in fin.items():
        if k in rec:
            rr = rec[k][0]
            rows.append({"key": k, "action": "유지" if rr == r["final_rank"] else "순서 이동", "rec_rank": rr,
                         "final_rank": int(r["final_rank"]), "media": r["media"], "title": r["title"]})
        else:
            rows.append({"key": k, "action": "사람이 추가", "rec_rank": None, "final_rank": int(r["final_rank"]),
                         "media": r["media"], "title": r["title"]})
    for k, (rr, media, title) in rec.items():
        if k not in fin:
            rows.append({"key": k, "action": "사람이 제외", "rec_rank": rr, "final_rank": None, "media": media, "title": title})
    return rows


def analyze_past(files: list[Path]) -> dict[str, pd.DataFrame]:
    """과거 완성본 목차 엑셀들에서 매체 순서·소제목·면 패턴과 예외 후보를 뽑는다.

    완성본에 없는 기사는 '제외'로 보지 않는다(검토 여부를 알 수 없음). 포함된 기사와 그 순서만 쓴다.
    """
    before = Counter()        # (A, B): 같은 소제목 안에서 A가 B보다 앞선 횟수
    section_media = Counter()
    page_dist = Counter()
    per_file = []
    for f in files:
        art = _final_articles(read_export(f))
        if art.empty:
            continue
        art["file"] = f.name
        per_file.append(art)
        for sec, g in art.groupby("subhead_ctx", sort=False):
            media = list(g["media"])
            for i in range(len(media)):
                section_media[(sec, media[i])] += 1
                for j in range(i + 1, len(media)):
                    if media[i] != media[j]:
                        before[(media[i], media[j])] += 1
        for p in art["page_no"]:
            page_dist["1면" if p == 1 else ("2~5면" if p and p <= 5 else ("6면 이후" if p else "면 정보 없음"))] += 1

    medias = sorted({m for pair in before for m in pair})
    score = {m: sum(before[(m, o)] - before[(o, m)] for o in medias if o != m) for m in medias}
    order = sorted(medias, key=lambda m: -score[m])
    rank = {m: i for i, m in enumerate(order)}
    media_order = pd.DataFrame([
        {"추정 순위": rank[m] + 1, "매체": m, "앞선 횟수-뒤진 횟수": score[m],
         "일관성": round(sum(before[(m, o)] for o in medias) / max(1, sum(before[(m, o)] + before[(o, m)] for o in medias)), 2)}
        for m in order
    ])

    # 예외 후보: 추정 매체 순서와 반대로 놓인 쌍이 많은 날
    exceptions = []
    for art in per_file:
        for sec, g in art.groupby("subhead_ctx", sort=False):
            g = g.reset_index(drop=True)
            for i in range(len(g)):
                for j in range(i + 1, len(g)):
                    a, b = g.loc[i], g.loc[j]
                    if a["media"] in rank and b["media"] in rank and rank[a["media"]] - rank[b["media"]] >= 3:
                        exceptions.append({"파일": a["file"], "소제목": sec, "앞에 놓인 기사": f"[{a['media']} {a['page_raw']}] {a['title']}",
                                           "뒤에 놓인 기사": f"[{b['media']} {b['page_raw']}] {b['title']}"})
    sec_rows = defaultdict(dict)
    for (sec, m), n in section_media.items():
        sec_rows[sec][m] = n
    return {
        "매체순서 추정": media_order,
        "소제목별 매체 분포": pd.DataFrame(sec_rows).fillna(0).astype(int).T.reset_index().rename(columns={"index": "소제목"}),
        "면 분포": pd.DataFrame(page_dist.most_common(), columns=["구분", "건수"]),
        "예외 후보(사유 확인용)": pd.DataFrame(exceptions[:300]),
        "분석 대상 파일": pd.DataFrame({"파일": [a["file"].iloc[0] for a in per_file], "기사 수": [len(a) for a in per_file]}),
    }
