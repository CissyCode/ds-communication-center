"""Telegram Bot API 클라이언트 + 메시지 포맷."""
from __future__ import annotations

import html
import json
import time
import urllib.error
import urllib.request
from datetime import timedelta, timezone

from .naver import Article

KST = timezone(timedelta(hours=9))
MAX_MESSAGE_LEN = 4096


class TelegramError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str, timeout: float = 30):
        self.base = f"https://api.telegram.org/bot{token}"
        self.timeout = timeout

    def call(self, method: str, timeout: float | None = None, **params) -> dict | list:
        data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(f"{self.base}/{method}", data=data,
                                     headers={"Content-Type": "application/json"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = json.loads(e.read().decode("utf-8") or "{}")
                retry_after = body.get("parameters", {}).get("retry_after")
                if e.code == 429 and retry_after and attempt < 2:
                    time.sleep(int(retry_after) + 1)  # 텔레그램 단체방 발송 속도 제한
                    continue
                raise TelegramError(f"{method}: {body.get('description', e)}") from e
            if not body.get("ok"):
                raise TelegramError(f"{method}: {body.get('description')}")
            return body["result"]
        raise TelegramError(f"{method}: rate limited")

    def send(self, chat_id: str, text: str) -> None:
        for chunk in split_message(text):
            self.call("sendMessage", chat_id=chat_id, text=chunk, parse_mode="HTML",
                      link_preview_options={"is_disabled": True})

    def get_updates(self, offset: int | None = None, timeout: int = 0) -> list[dict]:
        params = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            params["offset"] = offset
        return self.call("getUpdates", timeout=timeout + 10, **params)


def split_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    """빈 줄(기사 단위) 기준으로 4096자 제한에 맞게 분할."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = block[:limit]
    if current:
        chunks.append(current)
    return chunks


def format_digest(header: str, articles: list[Article], with_summary: bool = True) -> str:
    lines = [f"📰 <b>{html.escape(header)}</b> · {len(articles)}건"]
    for a in articles:
        when = a.published.astimezone(KST).strftime("%m/%d %H:%M")
        block = f'• <a href="{html.escape(a.link, quote=True)}">{html.escape(a.title)}</a>\n' \
                f"  <i>{html.escape(a.source)} · {when}</i>"
        if with_summary and a.description:
            desc = a.description if len(a.description) <= 120 else a.description[:117] + "…"
            block += f"\n  {html.escape(desc)}"
        lines.append(block)
    return "\n\n".join(lines)
