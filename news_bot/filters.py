"""검색 결과 후처리 필터 (네이버 API 검색어만으로 표현하기 어려운 조건)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import Query
from .naver import Article


def matches(article: Article, q: Query, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if q.max_age_hours and article.published < now - timedelta(hours=q.max_age_hours):
        return False
    if q.naver_only and not article.is_naver_news:
        return False
    text = f"{article.title} {article.description}".lower()
    if q.include_any and not any(k.lower() in text for k in q.include_any):
        return False
    if q.include_all and not all(k.lower() in text for k in q.include_all):
        return False
    if any(k.lower() in text for k in q.exclude):
        return False
    return True


def normalize_title(title: str) -> str:
    """같은 기사가 여러 매체/링크로 올라오는 경우를 잡기 위한 제목 정규화."""
    return "".join(ch for ch in title.lower() if ch.isalnum())


def apply(articles: list[Article], q: Query, now: datetime | None = None) -> list[Article]:
    seen_titles: set[str] = set()
    result = []
    for a in sorted(articles, key=lambda a: a.published, reverse=True):
        if not matches(a, q, now):
            continue
        key = normalize_title(a.title)
        if key in seen_titles:
            continue
        seen_titles.add(key)
        result.append(a)
    return result
