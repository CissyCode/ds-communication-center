"""MEDIA · Dashboard — the module-level console.

Same three-layer reading order as HOME (attention → open-work counts → board),
built from the same kit, but scoped to one module: where HOME answers "which
module needs me", this answers "what is on the media desk right now".
"""
from __future__ import annotations

from common import data as D
from common import nav as N
from common import signals as G
from common import ui as U

from . import _shared as X


def render():
    press = D.load_press_history()
    issues = D.load_issues()
    releases = D.load_press_releases()
    programs = D.load_media_programs()
    contacts = D.load_contact_history()
    monitoring = D.load_media_monitoring()
    reporters = D.load_reporters()

    in_progress = press[press["status"] == "진행 중"]
    awaiting_facts = in_progress[in_progress["response"].fillna("").str.strip() == ""]
    awaiting_reply = in_progress[in_progress["response"].fillna("").str.strip() != ""]
    stale = in_progress[in_progress["date"].apply(G.age_days) >= G.STALE_AFTER_DAYS]
    high_risk = issues[issues["severity"] == "HIGH"]
    pending_release = releases[releases["status"] == "배포 예정"]
    week_cov = G.window(monitoring, "date", 7)
    negative = int((week_cov["sentiment"] == "부정").sum())
    attention = G.attention(limit=4)

    kpis = [
        {"label": "사실확인 대기", "value": len(awaiting_facts), "unit": "건",
         "tone": "warn" if len(awaiting_facts) else "ok",
         "hint": "회신 문구 미작성", "href": N.href("media_response_desk")},
        {"label": "회신 대기", "value": len(awaiting_reply), "unit": "건",
         "tone": "info" if len(awaiting_reply) else "ok",
         "hint": "작성 완료 · 발송 전", "href": N.href("media_response_desk")},
        {"label": f"{G.STALE_AFTER_DAYS}일 이상 지연", "value": len(stale), "unit": "건",
         "tone": "crit" if len(stale) else "ok",
         "hint": "가장 먼저 처리", "href": N.href("media_response_desk")},
        {"label": "HIGH Risk", "value": len(high_risk), "unit": "건",
         "tone": "crit" if len(high_risk) else "ok",
         "hint": "부정 보도 · 긴급 공지", "href": N.href("media_issues_risk")},
        {"label": "배포 예정 보도자료", "value": len(pending_release), "unit": "건",
         "tone": "info", "hint": "PR Review 대기", "href": N.href("media_pr_studio")},
        {"label": "이번 주 보도", "value": len(week_cov), "unit": "건",
         "tone": "crit" if negative else "ok", "hint": f"부정 {negative}건",
         "href": N.href("media_coverage_results"),
         "bars": G.daily_counts(monitoring["date"])},
    ]

    queue = [{
        "chip": "사실확인" if not str(r.get("response") or "").strip() else "회신",
        "chip_tone": "crit" if G.age_days(r["date"]) >= G.STALE_AFTER_DAYS else "warn",
        "main": r["topic"],
        "sub": f"{r['media']} · {r['reporter']} · {r['type']}",
        "meta": G.age_label(r["date"]),
        "href": N.href("media_response_desk", r["press_history_id"], "press_history_id"),
    } for _, r in in_progress.sort_values("date").head(6).iterrows()]

    release_rows = [{
        "chip": "예정", "chip_tone": "warn", "main": r["title"],
        "meta": f"{r['date'].month}.{r['date'].day}",
        "href": N.href("media_pr_studio", r["schedule_id"], "schedule_id"),
    } for _, r in pending_release.sort_values("date").head(5).iterrows()]

    upcoming_programs = programs[programs["start_date"].dt.date >= D.TODAY].sort_values("start_date")
    program_rows = [{
        "main": r["title"], "sub": str(r["location"]) if isinstance(r["location"], str) else "",
        "meta": f"D-{(r['start_date'].date() - D.TODAY).days}",
        "href": N.href("media_programs"),
    } for _, r in upcoming_programs.head(5).iterrows()]

    contact_rows = [{
        "main": f"{r['reporter']} · {r['subject']}",
        "sub": f"{r['media']} · {r['contact_type']}",
        "meta": G.age_label(r["date"]),
        "href": N.href("media_reporter_crm",
                       X.reporter_id_by_name(r["reporter"], reporters), "reporter_id"),
    } for _, r in contacts.sort_values("date", ascending=False).head(5).iterrows()]

    coverage_rows = [{
        "chip": r["sentiment"], "chip_tone": G.SENTIMENT_TONE.get(r["sentiment"], "idle"),
        "main": r["headline"], "sub": f"{r['media']} · {r['reporter']}",
        "meta": f"{r['date'].month}.{r['date'].day}",
        "href": N.href("media_monitoring"),
    } for _, r in monitoring.head(6).iterrows()]

    sentiment_body = U.stackbar([
        ("긍정", int((week_cov["sentiment"] == "긍정").sum()), "ok"),
        ("중립", int((week_cov["sentiment"] == "중립").sum()), "idle"),
        ("부정", negative, "crit"),
    ]) + U.microbars(G.daily_counts(monitoring["date"]), "info", height=44)

    U.render(
        U.context_bar(
            "MEDIA · Dashboard",
            "미디어그룹이 오늘 처리해야 할 일과 대외 노출 상태를 한 화면에서 확인합니다.",
            meta=[
                ("기준일", f"{D.TODAY:%Y-%m-%d}"),
                ("진행 중 대응", f"{len(in_progress)}건"),
                ("이슈", f"{len(issues)}건"),
                ("이번 주 보도", f"{len(week_cov)}건"),
            ],
        ),
        U.alerts(attention, empty="즉시 대응이 필요한 항목이 없습니다."),
        U.kpi_row(kpis),
        U.board(
            # Left rail: the desk's own work queue, top to bottom in the order
            # it gets worked. Right rail: what the outside world is doing.
            U.column(
                7,
                U.panel("대응 대기열", U.rows(queue, "대기 중인 문의가 없습니다."),
                        subtitle="오래된 순",
                        action=("Response Desk", N.href("media_response_desk")),
                        note="사실확인·회신 구분은 대응 이력의 응답 필드 기준 근사치입니다."),
                U.panel("이슈 & 리스크", U.rows(G.ranked_issues(), "관리 중인 이슈가 없습니다."),
                        subtitle="심각도 · 경과일 순",
                        action=("Issues & Risk", N.href("media_issues_risk"))),
                U.panel("배포 예정 보도자료", U.rows(release_rows, "배포 예정인 보도자료가 없습니다."),
                        action=("PR Studio", N.href("media_pr_studio"))),
                U.panel("예정 미디어 프로그램", U.rows(program_rows, "예정된 프로그램이 없습니다."),
                        action=("Media Programs", N.href("media_programs"))),
            ),
            U.column(
                5,
                U.panel("이번 주 보도 감정", sentiment_body,
                        subtitle="최근 7일 · 14일 추이",
                        action=("Coverage & Results", N.href("media_coverage_results"))),
                U.panel("최근 보도", U.rows(coverage_rows, "최근 보도가 없습니다."),
                        action=("Monitoring", N.href("media_monitoring"))),
                U.panel("최근 기자 접촉", U.rows(contact_rows, "최근 접촉 이력이 없습니다."),
                        action=("Reporter CRM", N.href("media_reporter_crm"))),
            ),
        ),
    )
