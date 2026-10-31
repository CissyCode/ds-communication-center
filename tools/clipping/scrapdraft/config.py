"""규칙 파일(YAML) 읽기. 상시 기준 / 현안(만료일 필수) / 당일 지시를 구분한다."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml


@dataclass
class Section:
    name: str
    keywords: list[str]
    weight: float


@dataclass
class Issue:
    name: str
    keywords: list[str]
    until: date
    boost: float = 50
    pin_top: bool = False
    section: str | None = None  # 지정하면 해당 기사를 이 소제목으로 보냄

    def active(self, on: date) -> bool:
        return on <= self.until


@dataclass
class Config:
    target_papers: list[str]
    media_priority: list[str]
    sections: list[Section]
    default_section: str
    default_weight: float
    issues: list[Issue]
    exclude_keywords: list[str]
    min_score: float
    front_page_bonus: float
    early_page_bonus: float
    early_page_until: int
    size_bonus_per_100cm2: float
    edition_markers: list[str]
    edition_similarity: float
    cluster_similarity: float
    holidays: dict[str, list[str]] = field(default_factory=dict)
    sha256: str = ""

    def media_rank(self, media: str) -> int:
        try:
            return self.media_priority.index(media)
        except ValueError:
            return len(self.media_priority)


def _as_date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def load_config(path: str | Path, extra_issues: str | Path | None = None) -> Config:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    c = yaml.safe_load(text) or {}
    issues_raw = list(c.get("issues") or [])
    digest = hashlib.sha256(text.encode("utf-8"))
    if extra_issues:
        t2 = Path(extra_issues).read_text(encoding="utf-8")
        digest.update(t2.encode("utf-8"))
        issues_raw += list((yaml.safe_load(t2) or {}).get("issues") or [])

    issues = []
    for i in issues_raw:
        if not i.get("until"):
            raise ValueError(f"현안 '{i.get('name')}'에 만료일(until)이 없습니다. 현안은 만료일이 필수입니다.")
        issues.append(Issue(
            name=i["name"], keywords=list(i.get("keywords") or []), until=_as_date(i["until"]),
            boost=float(i.get("boost", 50)), pin_top=bool(i.get("pin_top", False)), section=i.get("section"),
        ))

    scoring = c.get("scoring") or {}
    dedup = c.get("dedup") or {}
    return Config(
        target_papers=list(c.get("target_papers") or []),
        media_priority=list(c.get("media_priority") or []),
        sections=[Section(s["name"], list(s.get("keywords") or []), float(s.get("weight", 50))) for s in c.get("sections") or []],
        default_section=c.get("default_section", "기타"),
        default_weight=float(c.get("default_weight", 20)),
        issues=issues,
        exclude_keywords=list(c.get("exclude_keywords") or []),
        min_score=float(scoring.get("min_score", 40)),
        front_page_bonus=float(scoring.get("front_page_bonus", 30)),
        early_page_bonus=float(scoring.get("early_page_bonus", 10)),
        early_page_until=int(scoring.get("early_page_until", 5)),
        size_bonus_per_100cm2=float(scoring.get("size_bonus_per_100cm2", 2)),
        edition_markers=list(dedup.get("edition_markers") or ["가판", "초판"]),
        edition_similarity=float(dedup.get("edition_similarity", 0.6)),
        cluster_similarity=float(dedup.get("cluster_similarity", 0.5)),
        holidays={str(k): list(v) for k, v in (c.get("holidays") or {}).items()},
        sha256=digest.hexdigest(),
    )
