"""후보 정리 → 중복 처리 → 점수·소제목 → 배열 → 신문별 상태."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time

import pandas as pd

from .config import Config
from .excel_io import norm_title

# 신문별 상태
ST_HAS = "결과 있음"
ST_EMPTY_CONFIRMED = "0건(수집 확인)"
ST_HOLIDAY = "휴간"
ST_UNKNOWN = "미확인(0건 또는 미수집)"
ST_PENDING = "수집 전(예정 {t})"
ST_NO_EARLY = "가판 없음(아침 확인 필요)"


def _bigrams(s: str) -> set[str]:
    s = norm_title(s)
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def similarity(a: str, b: str) -> float:
    x, y = _bigrams(a), _bigrams(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def base_media(media: str, markers: list[str]) -> tuple[str, bool]:
    """'조선일보(가판)' -> ('조선일보', True)."""
    m = media
    for mk in markers:
        pat = rf"\s*[\(\[]?\s*{re.escape(mk)}\s*[\)\]]?\s*"
        if re.search(pat, m):
            return re.sub(pat, "", m).strip(), True
    return m, False


def _is_print(kind: str) -> bool | None:
    if not kind:
        return None
    if "지면" in kind:
        return True
    if "온라인" in kind or "인터넷" in kind:
        return False
    return None


def _hits(text: str, words: list[str]) -> list[str]:
    return [w for w in words if w and w in text]


@dataclass
class Result:
    selected: pd.DataFrame       # 추천(순서 포함)
    reference: pd.DataFrame      # 기준 미달·확인 필요
    removed: pd.DataFrame        # 중복(판)·온라인·제외 후보
    paper_status: pd.DataFrame
    overall: str


def build_draft(df: pd.DataFrame, cfg: Config, target_date: date,
                confirmed_empty: list[str] | None = None, now: datetime | None = None) -> Result:
    confirmed_empty = confirmed_empty or []
    df = df[~df["is_subhead"]].copy() if not df.empty else df.copy()

    # 1) 같은 기사(같은 키)가 여러 검색어로 잡힌 경우 1건으로 합치고 검색어는 모은다
    if not df.empty:
        kw = df.groupby("key")["keyword"].apply(lambda s: ", ".join(sorted({k for k in s if k})))
        df = df.drop_duplicates("key").set_index("key")
        df["keyword"] = kw
        df = df.reset_index()

    df["base_media"], df["is_edition"] = zip(*df["media"].map(lambda m: base_media(m, cfg.edition_markers))) if not df.empty else ([], [])
    df["is_print"] = df["kind"].map(_is_print) if not df.empty else []
    df["note"] = ""
    df["drop_reason"] = ""
    df["edition_of"] = ""

    # 2) 대상 신문만 (가판은 본판 이름으로 매칭, 매체명 별칭 허용)
    if not df.empty:
        df["paper"] = df["base_media"].map(lambda m: cfg.paper_of(m, target_date))
        if cfg.restrict_media and cfg.papers_for(target_date):
            df = df[df["paper"].notna()].copy()
        else:  # 가판 확인 대상 외 매체(지역지 등)도 후보로 둔다
            df["paper"] = df["paper"].fillna(df["base_media"])
        other_day = df["date"].notna() & (df["date"] != target_date)
        df.loc[other_day, "note"] += "발행일이 대상일과 다름; "
    else:
        df["paper"] = []

    # 3) 온라인 제외, 구분 없음은 확인 필요
    df.loc[df["is_print"] == False, "drop_reason"] = "온라인 기사"  # noqa: E712
    df.loc[df["is_print"].isna(), "note"] += "구분(지면/온라인) 확인 필요; "

    # 4) 판 중복: 같은 신문·같은 발행일에서 가판과 본판의 유사 기사 → 본판 대표, 가판은 연결만
    live = df[df["drop_reason"] == ""]
    for (bm, d), g in live.groupby(["paper", "date"], dropna=False):
        eds, mains = g[g["is_edition"]], g[~g["is_edition"]]
        for i, e in eds.iterrows():
            best, best_sim = None, 0.0
            for j, m in mains.iterrows():
                sim = similarity(e["title"], m["title"])
                if sim > best_sim:
                    best, best_sim = j, sim
            if best is not None and best_sim >= cfg.edition_similarity:
                df.at[i, "drop_reason"] = "판 중복(가판)"
                df.at[i, "edition_of"] = df.at[best, "key"]
                df.at[best, "note"] += f"가판 동일 기사 있음({e['media']}); "
            elif mains.empty:
                df.at[i, "note"] += "본판 미확인(가판 임시 대표); "

    # 5) 기획면(지정한 면 접두어)·제외 키워드 → 삭제하지 않고 제외 후보로
    for i, r in df[df["drop_reason"] == ""].iterrows():
        pg = str(r["page_raw"]).strip().upper()
        if pg and cfg.exclude_page_prefixes and pg[0] in cfg.exclude_page_prefixes:
            df.at[i, "drop_reason"] = f"제외 후보(기획면 {r['page_raw']})"
            continue
        ex = _hits(r["title"], cfg.exclude_keywords)
        if ex:
            df.at[i, "drop_reason"] = f"제외 후보({', '.join(ex)})"

    # 6) 점수·소제목·소주제
    scores, sections, subs, reasons, pins, bundles = [], [], [], [], [], []
    for _, r in df.iterrows():
        sec, sub, w, why, extra_note = classify(r, cfg)
        if extra_note:
            df.at[_, "note"] += extra_note
        score, pin, bundle = w, False, ""
        for iss in cfg.issues:
            if not iss.active(target_date):
                continue
            text = f"{r['title']} {r['subtitle']}"
            h = _hits(text, iss.keywords) or _hits(r["keyword"], iss.keywords)
            if h:
                score += iss.boost
                pin = pin or iss.pin_top
                if iss.section:
                    sec = iss.section
                if iss.subtopic:
                    sub = iss.subtopic
                if iss.bundle and not bundle:
                    bundle = iss.name
                why.append(f"현안 '{iss.name}'(~{iss.until})")
        if r["page_no"] == 1:
            score += cfg.front_page_bonus
            why.append("1면")
        elif r["page_no"] and r["page_no"] <= cfg.early_page_until:
            score += cfg.early_page_bonus
        if r["size_cm2"]:
            score += cfg.size_bonus_per_100cm2 * r["size_cm2"] / 100
        scores.append(round(score, 1)); sections.append(sec); subs.append(sub); reasons.append("; ".join(why)); pins.append(pin)
        bundles.append(bundle)
    df["score"], df["section"], df["subtopic"], df["reason"], df["pin"] = scores, sections, subs, reasons, pins
    df["bundle"] = bundles

    # 7) 다른 매체 유사 보도 묶음(삭제하지 않음, 표시와 연속 배치만)
    df["cluster"] = ""
    live_idx = list(df[df["drop_reason"] == ""].index)
    parent = {i: i for i in live_idx}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a_pos, a in enumerate(live_idx):
        for b in live_idx[a_pos + 1:]:
            if similarity(df.at[a, "title"], df.at[b, "title"]) >= cfg.cluster_similarity:
                parent[find(a)] = find(b)
    roots: dict[int, list[int]] = {}
    for i in live_idx:
        roots.setdefault(find(i), []).append(i)
    n = 0
    for members in roots.values():
        if len(members) > 1:
            n += 1
            for i in members:
                df.at[i, "cluster"] = f"G{n}({len(members)}건)"
    # 현안 묶음(bundle: true): 제목이 달라도 같은 현안 기사는 한 묶음(사설·칼럼 포함)
    for name, g in df[(df["drop_reason"] == "") & (df["bundle"] != "")].groupby("bundle"):
        if len(g) > 1:
            for i in g.index:
                df.at[i, "cluster"] = f"현안:{name}({len(g)}건)"

    # 8) 분리: 추천 / 참고 / 제외
    removed = df[df["drop_reason"] != ""].copy()
    live = df[df["drop_reason"] == ""].copy()
    ok = (live["score"] >= cfg.min_score) & (live["is_print"] == True)  # noqa: E712
    selected, reference = live[ok].copy(), live[~ok].copy()
    reference.loc[reference["score"] < cfg.min_score, "note"] += "기준 점수 미달; "

    selected = order_articles(selected, cfg)
    reference = reference.sort_values("score", ascending=False)

    status, overall = paper_status(df, cfg, target_date, confirmed_empty, now)
    return Result(selected, reference, removed, status, overall)


def _is_opinion(r, cfg: Config) -> bool:
    cat = str(r.get("category") or "")
    head = r["title"][:12]
    return any(m in cat for m in cfg.opinion_markers) or any(f"[{m}" in head or f"<{m}" in head for m in cfg.opinion_markers)


def classify(r, cfg: Config):
    """(소제목, 소주제, 점수, 사유 목록, 메모). 사설·칼럼 판단이 주제보다 먼저."""
    text = f"{r['title']} {r['subtitle']}"
    if _is_opinion(r, cfg):
        for s in cfg.sections:
            if s.opinion:
                if s.preferred_media and r["paper"] not in s.preferred_media:
                    return s.name, "", s.weight * s.other_media_factor, [f"{s.name}(우선 매체 외)"], ""
                return s.name, "", s.weight, [f"{s.name}"], ""
    for s in cfg.sections:
        if s.opinion:
            continue
        h = _hits(text, s.keywords)
        factor, where = 1.0, "제목"
        if not h:
            h = _hits(r["keyword"], s.keywords)
            factor, where = 0.5, "검색어"
        if not h:
            continue
        sub = ""
        for st in s.subtopics:
            if _hits(text, st.keywords) or (factor < 1 and _hits(r["keyword"], st.keywords)):
                sub = st.name
                break
        if not sub and s.subtopics:
            sub = s.subtopics[-1].name if not s.subtopics[-1].keywords else ""
        label = f"{s.name}/{sub}" if sub else s.name
        return s.name, sub, s.weight * factor, [f"{label}: {where} '{h[0]}'" + ("(제목엔 없음)" if factor < 1 else "")], ""
    return cfg.default_section, "", cfg.default_weight, [], ""


def order_articles(sel: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """소제목 순서 → 현안 고정 → 소주제 순서 → 매체 우선순위 → 면 → 크기. 유사 묶음은 대표 뒤에 붙인다."""
    if sel.empty:
        sel["rank"] = []
        return sel
    order = [s.name for s in cfg.sections] + [cfg.default_section]
    for iss in cfg.issues:
        if iss.section and iss.section not in order:
            order.insert(0, iss.section)
    sel["_sec"] = sel["section"].map(lambda s: order.index(s) if s in order else len(order))
    sub_order = {s.name: [t.name for t in s.subtopics] for s in cfg.sections}
    sel["_sub"] = [sub_order.get(sec, []).index(sub) if sub in sub_order.get(sec, []) else 99
                   for sec, sub in zip(sel["section"], sel["subtopic"])]
    sel["_media"] = sel["paper"].map(cfg.media_rank)
    sel["_page"] = sel["page_no"].fillna(999)
    sel["_size"] = -sel["size_cm2"].fillna(0)
    sel = sel.sort_values(["_sec", "pin", "_sub", "_media", "_page", "_size"], ascending=[True, False, True, True, True, True])

    out, seen, toc = [], set(), {}
    rows = list(sel.index)
    for i in rows:
        if i in seen:
            continue
        out.append(i); seen.add(i)
        c = sel.at[i, "cluster"]
        toc[i] = "표시"
        if c:
            for j in rows:
                same_sec = sel.at[j, "section"] == sel.at[i, "section"]
                if j not in seen and sel.at[j, "cluster"] == c and (same_sec or c.startswith("현안:")):
                    out.append(j); seen.add(j)
                    toc[j] = "숨김(관련기사)"
    sel = sel.loc[out].drop(columns=["_sec", "_sub", "_media", "_page", "_size"])
    sel["rank"] = range(1, len(sel) + 1)
    sel["toc"] = [toc[i] for i in out]
    return sel


def paper_status(df: pd.DataFrame, cfg: Config, target_date: date, confirmed_empty: list[str],
                 now: datetime | None = None):
    """신문별 상태. 오늘 실행이고 예상 시각 전이면 '수집 전', 0건이면 '미확인'(수집 실패와 결과 없음을 섞지 않음)."""
    holidays = set(cfg.holidays.get(target_date.isoformat(), []))
    now = now or datetime.now()
    same_day = now.date() == target_date
    papers = cfg.papers_for(target_date)
    names = [p.name for p in papers] or (sorted(df["paper"].unique()) if not df.empty else [])
    ready = {p.name: p.ready for p in papers}
    rows = []
    for p in names:
        n = int((df["paper"] == p).sum()) if not df.empty else 0
        t = ready.get(p)
        if n:
            st = ST_HAS
        elif p in holidays:
            st = ST_HOLIDAY
        elif p in confirmed_empty:
            st = ST_EMPTY_CONFIRMED
        elif same_day and t and now.time() < t:
            st = ST_PENDING.format(t=t.strftime("%H:%M"))
        elif t is None and papers:
            st = ST_NO_EARLY
        else:
            st = ST_UNKNOWN
        rows.append({"매체": p, "상태": st, "검색 건수": n, "예상 시각": t.strftime("%H:%M") if t else "가판 없음"})
    status = pd.DataFrame(rows, columns=["매체", "상태", "검색 건수", "예상 시각"])
    done = status["상태"].isin([ST_HAS, ST_HOLIDAY, ST_EMPTY_CONFIRMED]).sum() if not status.empty else 0
    total = len(status)
    overall = "완료" if done == total else f"부분 완료 ({done}/{total}) — 수집 전·미확인 신문 있음"
    return status, overall
