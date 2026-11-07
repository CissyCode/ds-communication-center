"""환경 변수(비밀 값)와 queries.json(검색 조건) 로딩."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent
DEFAULT_QUERIES_PATH = PACKAGE_DIR / "queries.json"
DEFAULT_DB_PATH = ROOT_DIR / "storage" / "news_bot.db"


@dataclass
class Credentials:
    naver_client_id: str
    naver_client_secret: str
    telegram_bot_token: str
    telegram_chat_id: str
    naver_use_hub: bool = False  # NAVER API HUB(네이버 클라우드) 키 사용 여부


@dataclass
class Query:
    """검색 조건 하나. queries.json의 queries[] 항목과 1:1 대응."""

    name: str
    query: str
    include_any: list[str] = field(default_factory=list)
    include_all: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    sort: str = "date"          # date(최신순) | sim(정확도순)
    display: int = 30           # 네이버 API에서 가져올 개수 (최대 100)
    max_per_run: int = 5        # 한 번 실행에 단체방으로 보낼 최대 개수
    max_age_hours: float = 24   # 이보다 오래된 기사는 무시
    naver_only: bool = False    # True면 네이버 뉴스(n.news.naver.com) 링크가 있는 기사만
    enabled: bool = True


@dataclass
class Settings:
    queries: list[Query]
    interval_minutes: int = 30
    quiet_hours: tuple[int, int] | None = None  # (시작시, 종료시) KST, 이 시간엔 발송 안 함


def _env(name: str, required: bool) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise SystemExit(f"환경 변수 {name} 가 설정되지 않았습니다. news_bot/README.md를 참고하세요.")
    return value


def load_env_file(path: Path) -> None:
    """간단한 .env 로더 (KEY=VALUE). 이미 설정된 환경 변수는 덮어쓰지 않음."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_credentials(need_naver: bool = True, need_telegram: bool = True, need_chat: bool = True) -> Credentials:
    load_env_file(ROOT_DIR / ".env")
    return Credentials(
        naver_client_id=_env("NAVER_CLIENT_ID", need_naver),
        naver_client_secret=_env("NAVER_CLIENT_SECRET", need_naver),
        telegram_bot_token=_env("TELEGRAM_BOT_TOKEN", need_telegram),
        telegram_chat_id=_env("TELEGRAM_CHAT_ID", need_chat),
        naver_use_hub=_env("NAVER_API_HUB", False).lower() in ("1", "true", "yes"),
    )


def load_settings(path: Path = DEFAULT_QUERIES_PATH) -> Settings:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    known = set(Query.__dataclass_fields__)
    queries = []
    for item in raw.get("queries", []):
        unknown = set(item) - known
        if unknown:
            raise SystemExit(f"queries.json '{item.get('name')}'에 알 수 없는 항목: {sorted(unknown)}")
        q = Query(**item)
        if q.sort not in ("date", "sim"):
            raise SystemExit(f"'{q.name}': sort는 date 또는 sim 이어야 합니다.")
        q.display = max(1, min(int(q.display), 100))
        queries.append(q)
    quiet = raw.get("quiet_hours")
    return Settings(
        queries=queries,
        interval_minutes=int(raw.get("interval_minutes", 30)),
        quiet_hours=tuple(quiet) if quiet else None,
    )
