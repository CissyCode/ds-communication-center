"""Derived signals for the console screens.

`common/data.py` loads sources; the views render them. This module is the thin
layer in between: it turns those sources into the handful of judgements a
dashboard makes — what needs attention now, how old an open item is, whether a
number moved this week — so HOME and MEDIA · Dashboard share one definition of
"진행 중" and one definition of "지연" instead of each re-deriving them slightly
differently.

Nothing here formats HTML and nothing here reads Streamlit widgets; the return
values are plain dicts shaped for `common/ui.py` components.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from common import data as D
from common import nav as N

TODAY = D.TODAY

# An open inquiry older than this is treated as slipping, not merely open.
# One threshold, named once, instead of a magic 3 in three screens.
STALE_AFTER_DAYS = 3

SEVERITY_TONE = {"HIGH": "crit", "MEDIUM": "warn", "LOW": "idle"}
SENTIMENT_TONE = {"긍정": "ok", "중립": "idle", "부정": "crit"}


# --------------------------------------------------------------------- helpers

def age_days(d, today: date | None = None) -> int:
    today = today or TODAY
    if isinstance(d, pd.Timestamp):
        d = d.date()
    return (today - d).days


def age_label(d, today: date | None = None) -> str:
    n = age_days(d, today)
    if n <= 0:
        return "오늘"
    if n == 1:
        return "어제"
    return f"{n}일 경과"


def daily_counts(dates: pd.Series, days: int = 14, today: date | None = None) -> list[int]:
    """Counts per day over the trailing window, zero-filled — a sparkline drawn
    from only the days that happened to have rows lies about the shape."""
    today = today or TODAY
    start = today - timedelta(days=days - 1)
    idx = pd.date_range(start, today, freq="D")
    if dates is None or dates.empty:
        return [0] * days
    counted = dates.dropna().dt.normalize().value_counts()
    return [int(counted.get(d, 0)) for d in idx]


def window(df: pd.DataFrame, col: str, days: int, offset: int = 0,
           today: date | None = None) -> pd.DataFrame:
    """Rows inside a trailing window. offset=1 gives the window before it, which
    is what every week-over-week delta on the board compares against."""
    today = today or TODAY
    end = today - timedelta(days=days * offset)
    start = end - timedelta(days=days - 1)
    d = df[col].dt.date
    return df[(d >= start) & (d <= end)]


def delta(now: float, before: float) -> tuple[str, str]:
    """(label, tone) for a week-over-week change. Direction only — the board
    never claims a % change on counts this small."""
    diff = now - before
    if diff > 0:
        return f"▲{diff:g}", "ok"
    if diff < 0:
        return f"▼{abs(diff):g}", "crit"
    return "―", "idle"


# ------------------------------------------------------------------- attention

def attention(limit: int = 4) -> list[dict]:
    """Items that need a decision today, ranked by severity then age.

    Deliberately capped: an attention lane that grows without bound is just
    another list. Anything below the cap lives in its module's own screen.
    """
    items: list[dict] = []

    issues = D.load_issues()
    for _, r in issues[issues["severity"] == "HIGH"].iterrows():
        items.append({
            "tone": "crit",
            "chip": f"HIGH · {r['source']}",
            "title": r["title"],
            "meta": age_label(r["date"]),
            "href": N.href("media_issues_risk", r["issue_id"], "issue_id"),
            "_rank": (0, -age_days(r["date"])),
        })

    press = D.load_press_history()
    open_press = press[press["status"] == "진행 중"]
    for _, r in open_press.iterrows():
        n = age_days(r["date"])
        if n < STALE_AFTER_DAYS:
            continue
        waiting = "사실확인 대기" if not str(r.get("response") or "").strip() else "회신 대기"
        items.append({
            "tone": "warn",
            "chip": f"지연 · {waiting}",
            "title": f"[{r['media']}] {r['topic']}",
            "meta": age_label(r["date"]),
            "href": N.href("media_response_desk", r["press_history_id"], "press_history_id"),
            "_rank": (1, -n),
        })

    releases = D.load_press_releases()
    imminent = releases[(releases["status"] == "배포 예정")
                        & (releases["date"].dt.date <= TODAY + timedelta(days=2))]
    for _, r in imminent.iterrows():
        items.append({
            "tone": "warn",
            "chip": "임박 · 보도자료",
            "title": r["title"],
            "meta": f"D-{(r['date'].date() - TODAY).days}",
            "href": N.href("media_pr_studio", r["schedule_id"], "schedule_id"),
            "_rank": (1, (r["date"].date() - TODAY).days),
        })

    items.sort(key=lambda i: i["_rank"])
    for i in items:
        del i["_rank"]
    return items[:limit]


def ranked_issues(limit: int = 6) -> list[dict]:
    """Watchlist rows ordered the way a desk works them: severity first, then
    age. `load_issues` returns newest-first, which buries a two-week-old HIGH
    under today's MEDIUM."""
    issues = D.load_issues().copy()
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    issues["_sev"] = issues["severity"].map(order).fillna(3)
    issues = issues.sort_values(["_sev", "date"], ascending=[True, True])
    return [{
        "chip": r["severity"],
        "chip_tone": SEVERITY_TONE.get(r["severity"], "idle"),
        "main": r["title"],
        "sub": f"{r['source']} · {r['media']}",
        "meta": age_label(r["date"]),
        "href": N.href("media_issues_risk", r["issue_id"], "issue_id"),
    } for _, r in issues.head(limit).iterrows()]


# ------------------------------------------------------------------------ KPIs

def home_kpis() -> list[dict]:
    """The six counts HOME opens with — all of them open work, none of them a
    month-to-date total, so every tile is worth clicking."""
    schedule = D.load_schedule()
    issues = D.load_issues()
    press = D.load_press_history()
    releases = D.load_press_releases()
    content = D.load_new_media_content()
    projects = D.load_marcom_projects()
    campaigns = D.load_marcom_campaigns()

    todays = schedule[(schedule["start_date"].dt.date <= TODAY)
                      & (schedule["end_date"].dt.date >= TODAY)]
    week_ahead = schedule[(schedule["start_date"].dt.date > TODAY)
                          & (schedule["start_date"].dt.date <= TODAY + timedelta(days=7))]
    high = issues[issues["severity"] == "HIGH"]
    open_press = press[press["status"] == "진행 중"]
    stale = open_press[open_press["date"].dt.date <= TODAY - timedelta(days=STALE_AFTER_DAYS)]
    pending_release = releases[releases["status"] == "배포 예정"]
    this_week = window(content, "date", 7)
    last_week = window(content, "date", 7, offset=1)
    d_label, d_tone = delta(len(this_week), len(last_week))
    active_marcom = int((projects["status"] == "진행 중").sum()
                        + (campaigns["status"] == "진행 중").sum())

    return [
        {"label": "오늘 일정", "value": len(todays), "unit": "건", "tone": "info",
         "hint": f"이후 7일 {len(week_ahead)}건", "href": N.href("schedule")},
        {"label": "HIGH 리스크", "value": len(high), "unit": "건",
         "tone": "crit" if len(high) else "idle",
         "hint": "부정 보도 · 긴급 공지", "href": N.href("media_issues_risk")},
        {"label": "진행 중 대응", "value": len(open_press), "unit": "건",
         "tone": "warn" if len(open_press) else "ok",
         "hint": f"{STALE_AFTER_DAYS}일 이상 지연 {len(stale)}건",
         "href": N.href("media_response_desk"),
         "bars": daily_counts(press["date"])},
        {"label": "배포 예정 보도자료", "value": len(pending_release), "unit": "건",
         "tone": "info" if len(pending_release) else "idle",
         "hint": "PR Studio 검토 대기", "href": N.href("media_pr_studio")},
        {"label": "최근 7일 콘텐츠", "value": len(this_week), "unit": "건", "tone": "ok",
         "delta": d_label, "delta_tone": d_tone, "hint": "직전 7일 대비",
         "href": N.href("new_media"), "bars": daily_counts(content["date"])},
        {"label": "진행 중 MARCOM", "value": active_marcom, "unit": "건", "tone": "info",
         "hint": "Project + Campaign", "href": N.href("marcom")},
    ]


# --------------------------------------------------------------------- agenda

_DAY_LABEL = {0: "오늘", 1: "내일"}


def agenda_groups(days: int = 7) -> list[tuple[str, str, list[dict]]]:
    """Schedule for the next N days, grouped by day. Multi-day entries appear
    under every day they span — on an operations board a running event is as
    much 'today' as one that starts today."""
    schedule = D.load_schedule()
    groups: list[tuple[str, str, list[dict]]] = []
    # today + the following `days` days, so this panel covers exactly the window
    # the "이후 7일" KPI hint counts — an agenda that stops a day short of the
    # number printed above it reads as a bug.
    for offset in range(days + 1):
        day = TODAY + timedelta(days=offset)
        rows = schedule[(schedule["start_date"].dt.date <= day)
                        & (schedule["end_date"].dt.date >= day)].sort_values("time_label")
        if rows.empty:
            continue
        weekday = ["월", "화", "수", "목", "금", "토", "일"][day.weekday()]
        label = _DAY_LABEL.get(offset, f"{day.month}.{day.day}({weekday})")
        if offset == 0:
            label = f"오늘 · {day.month}.{day.day}({weekday})"
        tone = "info" if offset == 0 else "idle"
        items = [{
            "time": r["time_label"] if r["time_label"] != "-" else "종일",
            "category": r["category"],
            "title": r["title"],
            "meta": r["location"] if isinstance(r["location"], str) else "",
            "href": N.href("schedule"),
        } for _, r in rows.iterrows()]
        groups.append((label, tone, items))
    return groups


# -------------------------------------------------------------- module boards

def media_board() -> list[dict]:
    """MEDIA health as ratios. Every meter on the board is a share of a stated
    denominator — a bar whose length came from an invented scale (count × 10)
    looks like information and carries none."""
    press = D.load_press_history()
    issues = D.load_issues()
    releases = D.load_press_releases()
    monitoring = D.load_media_monitoring()
    open_press = press[press["status"] == "진행 중"]
    closed = len(press) - len(open_press)
    high = int((issues["severity"] == "HIGH").sum())
    week = window(monitoring, "date", 7)
    negative = int((week["sentiment"] == "부정").sum())
    return [
        {"label": "대응 종결", "value": f"{closed}/{len(press)}",
         "pct": closed / max(len(press), 1) * 100, "tone": "ok",
         "href": N.href("media_response_desk")},
        {"label": "이슈 중 HIGH", "value": f"{high}/{len(issues)}",
         "pct": high / max(len(issues), 1) * 100,
         "tone": "crit" if high else "ok", "href": N.href("media_issues_risk")},
        {"label": "이번 주 보도 (부정 제외)", "value": f"{len(week) - negative}/{len(week)}",
         "pct": (len(week) - negative) / max(len(week), 1) * 100,
         "tone": "crit" if negative else "ok", "href": N.href("media_coverage_results")},
        {"label": "배포 예정 보도자료", "value": f"{(releases['status'] == '배포 예정').sum()}건",
         "pct": None, "href": N.href("media_pr_studio")},
    ]


def new_media_board() -> list[dict]:
    content = D.load_new_media_content()
    series = D.load_new_media_series()
    channels = D.load_new_media_channels()
    week = window(content, "date", 7)
    active_series = int((series["status"] == "진행 중").sum())
    engagement = float(content["engagement_rate"].mean()) if not content.empty else 0.0
    stale_channels = channels[channels["last_post_date"].dt.date < TODAY - timedelta(days=7)]
    return [
        {"label": "진행 중 시리즈", "value": f"{active_series}/{len(series)}",
         "pct": active_series / max(len(series), 1) * 100, "tone": "info",
         "href": N.href("new_media")},
        {"label": "7일 이상 미게시 채널", "value": f"{len(stale_channels)}/{len(channels)}",
         "pct": len(stale_channels) / max(len(channels), 1) * 100,
         "tone": "warn" if len(stale_channels) else "ok", "href": N.href("new_media")},
        {"label": "최근 7일 게시", "value": f"{len(week)}건", "pct": None,
         "href": N.href("new_media")},
        {"label": "평균 Engagement", "value": f"{engagement:.1f}%", "pct": None,
         "href": N.href("new_media")},
    ]


def marcom_board() -> list[dict]:
    projects = D.load_marcom_projects()
    campaigns = D.load_marcom_campaigns()
    events = D.load_marcom_events()
    assets = D.load_marcom_assets()
    upcoming = events[events["date"].dt.date >= TODAY]
    done = int((projects["status"] == "완료").sum())
    running = int((campaigns["status"] == "진행 중").sum())
    return [
        {"label": "Project 완료", "value": f"{done}/{len(projects)}",
         "pct": done / max(len(projects), 1) * 100, "tone": "ok", "href": N.href("marcom")},
        {"label": "Campaign 진행", "value": f"{running}/{len(campaigns)}",
         "pct": running / max(len(campaigns), 1) * 100, "tone": "info", "href": N.href("marcom")},
        {"label": "예정 Event", "value": f"{len(upcoming)}/{len(events)}",
         "pct": len(upcoming) / max(len(events), 1) * 100, "tone": "warn",
         "href": N.href("marcom")},
        {"label": "Asset 최신본", "value": f"{len(assets)}종", "pct": None,
         "href": N.href("marcom")},
    ]


# ----------------------------------------------------------------- feed / etc.

_MODULE_TARGET = {
    "MEDIA": "media_dashboard", "NEW MEDIA": "new_media", "MARCOM": "marcom",
    "RESOURCES": "resources", "공지": "media_dashboard",
}


def activity(limit: int = 10) -> list[dict]:
    updates = D.load_recent_updates(limit=limit)
    return [{
        "date": f"{r['date'].month}.{r['date'].day}",
        "module": r["module"],
        "text": r["title"],
        "href": N.href(_MODULE_TARGET.get(r["module"], "home")),
    } for _, r in updates.iterrows()]


def notices(limit: int = 5) -> list[dict]:
    df = D.load_notices().head(limit)
    return [{
        "main": r["title"],
        "meta": f"{r['date'].month}.{r['date'].day}",
        "chip": "긴급" if r["category"] == "긴급" else ("고정" if r["priority"] == "상단고정" else r["category"]),
        "chip_tone": "crit" if r["category"] == "긴급" else ("warn" if r["priority"] == "상단고정" else "idle"),
        "href": N.href("resources"),
    } for _, r in df.iterrows()]
