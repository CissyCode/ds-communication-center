"""실행 진입점.

    python -m news_bot chat-id          # 단체방 chat id 확인
    python -m news_bot preview          # 텔레그램 발송 없이 검색 결과만 출력 (조건 튜닝용)
    python -m news_bot run              # 한 번 실행 (cron / GitHub Actions용)
    python -m news_bot loop             # 상주 실행: 주기적 발송 + 단체방 명령어(/news 등) 응답
"""
from __future__ import annotations

import argparse
import html
import sys
import time
from datetime import datetime
from pathlib import Path

from . import filters
from .config import DEFAULT_DB_PATH, DEFAULT_QUERIES_PATH, Query, Settings, load_credentials, load_settings
from .naver import search_news
from .store import Store
from .telegram import KST, TelegramClient, TelegramError, format_digest

HELP_TEXT = (
    "<b>기사 공유 봇 명령어</b>\n"
    "/news 검색어 — 지금 네이버 뉴스 검색 (예: /news 삼성전자 HBM -주가)\n"
    "/queries — 등록된 자동 검색 조건 보기\n"
    "/run — 자동 검색 조건으로 지금 바로 수집\n"
    "/help — 도움말"
)


def log(msg: str) -> None:
    print(f"[{datetime.now(KST):%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def in_quiet_hours(settings: Settings, now: datetime | None = None) -> bool:
    if not settings.quiet_hours:
        return False
    start, end = settings.quiet_hours
    hour = (now or datetime.now(KST)).astimezone(KST).hour
    return start <= hour < end if start < end else hour >= start or hour < end


def collect(q: Query, creds, store: Store | None):
    articles = search_news(q.query, creds.naver_client_id, creds.naver_client_secret,
                           display=q.display, sort=q.sort)
    picked = filters.apply(articles, q)
    if store is not None:
        picked = [a for a in picked if not store.is_sent(a)]
    return articles, picked[: q.max_per_run]


def run_once(settings: Settings, creds, store: Store, tg: TelegramClient, force: bool = False) -> int:
    if in_quiet_hours(settings) and not force:
        log("방해 금지 시간대라 발송을 건너뜁니다.")
        return 0
    total = 0
    for q in settings.queries:
        if not q.enabled:
            continue
        try:
            fetched, picked = collect(q, creds, store)
        except Exception as e:  # 한 조건이 실패해도 나머지는 계속
            log(f"[{q.name}] 검색 실패: {e}")
            continue
        log(f"[{q.name}] 검색 {len(fetched)}건 → 신규 {len(picked)}건")
        if not picked:
            continue
        tg.send(creds.telegram_chat_id, format_digest(q.name, picked))
        for a in picked:
            store.mark_sent(a, q.name)
        total += len(picked)
    store.prune()
    return total


def cmd_chat_id(_args) -> None:
    creds = load_credentials(need_naver=False, need_chat=False)
    tg = TelegramClient(creds.telegram_bot_token)
    updates = tg.get_updates()
    chats = {}
    for u in updates:
        chat = (u.get("message") or u.get("my_chat_member") or {}).get("chat")
        if chat:
            chats[chat["id"]] = chat
    if not chats:
        print("받은 메시지가 없습니다. 봇을 단체방에 초대한 뒤 단체방에 '/help' 를 보내고 다시 실행하세요.")
        return
    for cid, chat in chats.items():
        print(f"{cid}\t{chat.get('type')}\t{chat.get('title') or chat.get('username') or ''}")
    print("\n단체방(group/supergroup)의 id(보통 -100으로 시작)를 TELEGRAM_CHAT_ID 로 설정하세요.")


def cmd_preview(args) -> None:
    settings = load_settings(args.queries)
    creds = load_credentials(need_telegram=False, need_chat=False)
    for q in settings.queries:
        if args.name and q.name != args.name:
            continue
        try:
            fetched, picked = collect(q, creds, store=None)
        except Exception as e:
            print(f"\n===== {q.name}: 검색 실패 — {e}")
            continue
        print(f"\n===== {q.name}  (검색어: {q.query}) — 검색 {len(fetched)}건, 필터 통과 {len(picked)}건 =====")
        for a in picked:
            print(f"- {a.published.astimezone(KST):%m/%d %H:%M} [{a.source}] {a.title}\n  {a.link}")


def cmd_run(args) -> None:
    settings = load_settings(args.queries)
    creds = load_credentials()
    store = Store(Path(args.db))
    sent = run_once(settings, creds, store, TelegramClient(creds.telegram_bot_token), force=args.force)
    log(f"완료: {sent}건 발송")


def handle_command(text: str, settings: Settings, creds, store: Store, tg: TelegramClient) -> None:
    cmd, _, arg = text.strip().partition(" ")
    cmd = cmd.split("@")[0].lower()  # /news@MyBot → /news
    chat = creds.telegram_chat_id
    if cmd in ("/help", "/start"):
        tg.send(chat, HELP_TEXT)
    elif cmd == "/queries":
        lines = ["<b>자동 검색 조건</b>"]
        for q in settings.queries:
            mark = "✅" if q.enabled else "⏸"
            lines.append(f"{mark} {html.escape(q.name)}: <code>{html.escape(q.query)}</code>")
        lines.append(f"\n{settings.interval_minutes}분마다 확인")
        tg.send(chat, "\n".join(lines))
    elif cmd == "/run":
        sent = run_once(settings, creds, store, tg, force=True)
        if not sent:
            tg.send(chat, "새로 올라온 기사가 없습니다.")
    elif cmd == "/news":
        if not arg.strip():
            tg.send(chat, "사용법: /news 검색어")
            return
        q = Query(name=f"검색: {arg.strip()}", query=arg.strip(), max_per_run=10, max_age_hours=72)
        _, picked = collect(q, creds, store=None)
        tg.send(chat, format_digest(q.name, picked) if picked else "검색 결과가 없습니다.")


def cmd_loop(args) -> None:
    settings = load_settings(args.queries)
    creds = load_credentials()
    store = Store(Path(args.db))
    tg = TelegramClient(creds.telegram_bot_token)
    interval = settings.interval_minutes * 60
    offset = int(store.get_state("update_offset", "0")) or None
    next_run = 0.0
    log(f"시작: 조건 {len(settings.queries)}개, {settings.interval_minutes}분 주기")
    while True:
        if time.time() >= next_run:
            try:
                run_once(settings, creds, store, tg)
            except Exception as e:
                log(f"수집 실패: {e}")
            next_run = time.time() + interval
        try:
            # long polling: 다음 수집 시각까지 단체방 명령어를 기다림
            wait = int(max(1, min(50, next_run - time.time())))
            for u in tg.get_updates(offset=offset, timeout=wait):
                offset = u["update_id"] + 1
                store.set_state("update_offset", str(offset))
                msg = u.get("message") or {}
                text = msg.get("text", "")
                if str(msg.get("chat", {}).get("id")) == str(creds.telegram_chat_id) and text.startswith("/"):
                    try:
                        handle_command(text, settings, creds, store, tg)
                    except Exception as e:
                        log(f"명령 처리 실패 ({text}): {e}")
        except (TelegramError, OSError) as e:
            log(f"텔레그램 연결 오류: {e}")
            time.sleep(10)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m news_bot", description="네이버 뉴스 → 텔레그램 단체방 공유 봇")
    p.add_argument("--queries", default=str(DEFAULT_QUERIES_PATH), help="검색 조건 파일 (기본: news_bot/queries.json)")
    p.add_argument("--db", default=str(DEFAULT_DB_PATH), help="발송 기록 DB (기본: storage/news_bot.db)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("chat-id", help="봇이 받은 메시지로 단체방 chat id 확인").set_defaults(func=cmd_chat_id)
    pv = sub.add_parser("preview", help="발송 없이 검색 결과 미리보기")
    pv.add_argument("--name", help="특정 조건 이름만")
    pv.set_defaults(func=cmd_preview)
    r = sub.add_parser("run", help="한 번 수집·발송")
    r.add_argument("--force", action="store_true", help="방해 금지 시간대 무시")
    r.set_defaults(func=cmd_run)
    sub.add_parser("loop", help="상주 실행 (주기 발송 + 단체방 명령어)").set_defaults(func=cmd_loop)
    args = p.parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
