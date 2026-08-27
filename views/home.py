"""HOME — the operations console.

Reading order is the design: an attention lane you can clear in three seconds,
a strip of open-work counts you can scan in thirty, and a board you work
through in three minutes. Nothing on this screen is a report; every number and
every row links to the place the work is actually done, so HOME is a dispatcher
and never a destination.

The whole screen is composed as one HTML string and written once (see
common/ui.py) — no per-block widgets, no rerun on navigation.
"""
from __future__ import annotations

from common import data as D
from common import nav as N
from common import signals as G
from common import style as S
from common import ui as U


def _queue_rows(limit: int = 6) -> list[dict]:
    press = D.load_press_history()
    open_press = press[press["status"] == "진행 중"].sort_values("date")
    rows = []
    for _, r in open_press.head(limit).iterrows():
        waiting = "사실확인" if not str(r.get("response") or "").strip() else "회신"
        stale = G.age_days(r["date"]) >= G.STALE_AFTER_DAYS
        rows.append({
            "chip": waiting,
            "chip_tone": "crit" if stale else "warn",
            "main": r["topic"],
            "sub": f"{r['media']} · {r['reporter']} · {r['type']}",
            "meta": G.age_label(r["date"]),
            "href": N.href("media_response_desk", r["press_history_id"], "press_history_id"),
        })
    return rows


def render():
    S.app_name()

    schedule = D.load_schedule()
    todays = schedule[(schedule["start_date"].dt.date <= D.TODAY)
                      & (schedule["end_date"].dt.date >= D.TODAY)]
    attention = G.attention(limit=4)

    U.render(
        U.context_bar(
            "커뮤니케이션 운영 현황판",
            "오늘 확인할 일, 지금 결정할 일, 각 모듈의 상태를 한 화면에서 확인합니다.",
            meta=[
                ("기준일", f"{D.TODAY:%Y-%m-%d}"),
                ("오늘 일정", f"{len(todays)}건"),
                ("확인 필요", f"{len(attention)}건"),
                ("데이터", "FAKE / Prototype"),
            ],
        ),

        # 3초: 오늘 결정이 필요한 것만.
        U.alerts(attention, empty="지금 즉시 결정이 필요한 항목이 없습니다."),

        # 30초: 대기 중인 일의 총량.
        U.kpi_row(G.home_kpis()),

        # 3분: 모듈별 작업 보드.
        U.board(
            # Left rail: what happens on a date (agenda) and what is queued for
            # a person (response desk). Right rail: state — risk, module health,
            # notices. Stacking per column instead of per row keeps a short
            # panel from leaving dead space under a tall neighbour.
            U.column(
                8,
                U.panel(
                    "오늘의 운영", U.agenda(G.agenda_groups(days=7)),
                    subtitle="오늘 ~ 향후 7일",
                    action=("SCHEDULE", N.href("schedule")),
                    note="전 모듈이 참조하는 Master Schedule에서 가져옵니다.",
                ),
                U.panel(
                    "대응 대기열", U.rows(_queue_rows(), "대기 중인 문의가 없습니다."),
                    subtitle="진행 중 · 오래된 순",
                    action=("Response Desk", N.href("media_response_desk")),
                    note=f"{G.STALE_AFTER_DAYS}일 이상 경과한 건은 붉은 라벨로 표시됩니다.",
                ),
                U.panel(
                    "최근 업데이트", U.feed(G.activity(limit=10)),
                    subtitle="전 모듈",
                    action=("INSIGHTS", N.href("insights")),
                ),
            ),
            U.column(
                4,
                U.panel(
                    "이슈 워치리스트", U.rows(G.ranked_issues(), "관리 중인 이슈가 없습니다."),
                    subtitle="심각도 · 경과일 순",
                    action=("Issues & Risk", N.href("media_issues_risk")),
                ),
                U.panel("MEDIA", U.stat_rows(G.media_board()),
                        action=("모듈 열기", N.href("media_dashboard"))),
                U.panel("NEW MEDIA", U.stat_rows(G.new_media_board()),
                        action=("모듈 열기", N.href("new_media"))),
                U.panel("MARCOM", U.stat_rows(G.marcom_board()),
                        action=("모듈 열기", N.href("marcom"))),
                U.panel("공지", U.rows(G.notices(), "등록된 공지가 없습니다."),
                        action=("RESOURCES", N.href("resources"))),
            ),
        ),
    )
