"""네이버 검색 API(뉴스) 클라이언트.

두 가지 발급 경로를 모두 지원합니다(응답 형식은 동일):
- 네이버 개발자센터: https://developers.naver.com/docs/serviceapi/search/news/news.md
- NAVER API HUB(네이버 클라우드): GET https://naverapihub.apigw.ntruss.com/search/v1/news
  → 환경 변수 NAVER_API_HUB=true 로 전환
검색어에는 네이버 검색 연산자를 쓸 수 있습니다: "정확한 구문", +필수어, -제외어, A | B
"""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

API_URL = "https://openapi.naver.com/v1/search/news.json"
HUB_API_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"


_TAG_RE = re.compile(r"<[^>]+>")


class NaverAPIError(RuntimeError):
    pass


@dataclass
class Article:
    title: str
    description: str
    link: str            # 네이버 뉴스 링크(있으면) 또는 원문 링크
    original_link: str
    published: datetime  # timezone-aware

    @property
    def is_naver_news(self) -> bool:
        return "news.naver.com" in self.link

    @property
    def source(self) -> str:
        """원문 도메인 (예: www.hankyung.com → hankyung.com). API가 매체명을 주지 않아 도메인으로 대신함."""
        host = urllib.parse.urlparse(self.original_link or self.link).hostname or ""
        return host.removeprefix("www.").removeprefix("m.")

    @property
    def dedupe_key(self) -> str:
        return self.original_link or self.link


def clean(text: str) -> str:
    """API 응답의 <b> 하이라이트 태그와 HTML 엔티티 제거."""
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def parse_items(payload: dict) -> list[Article]:
    articles = []
    for item in payload.get("items", []):
        try:
            published = parsedate_to_datetime(item["pubDate"])
        except (KeyError, TypeError, ValueError):
            continue
        articles.append(Article(
            title=clean(item.get("title", "")),
            description=clean(item.get("description", "")),
            link=item.get("link", ""),
            original_link=item.get("originallink", ""),
            published=published,
        ))
    return articles


def search_news(query: str, client_id: str, client_secret: str, display: int = 30,
                sort: str = "date", timeout: float = 10, use_hub: bool = False) -> list[Article]:
    params = {"query": query, "display": display, "start": 1, "sort": sort}
    if use_hub:
        url = HUB_API_URL
        params["format"] = "json"
        headers = {"X-NCP-APIGW-API-KEY-ID": client_id, "X-NCP-APIGW-API-KEY": client_secret}
    else:
        url = API_URL
        headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return parse_items(json.loads(resp.read().decode("utf-8")))
    except urllib.error.HTTPError as e:
        # 예: 400 SE01 잘못된 쿼리, 401 인증 실패(키/발급 경로 확인), 429 호출 한도 초과
        body = e.read().decode("utf-8", "replace")[:300]
        raise NaverAPIError(f"HTTP {e.code}: {body}") from e
