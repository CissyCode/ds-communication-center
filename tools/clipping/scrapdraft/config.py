"""규칙 파일(YAML) 읽기. 상시 기준 / 현안(만료일 필수) / 당일 지시를 구분한다."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path

import yaml


@dataclass
class Subtopic:
    name: str
    keywords: list[str]


@dataclass
class Section:
    name: str
    keywords: list[str]               # 소제목 소속 판단(제목·부제목, 없으면 검색어)
    weight: float
    subtopics: list[Subtopic] = field(default_factory=list)
    opinion: bool = False             # 사설·칼럼 소제목
    preferred_media: list[str] = field(default_factory=list)  # 사설·칼럼 우선 매체(그 외는 점수 감점)
    other_media_factor: float = 0.8


@dataclass
class Paper:
    name: str                 # 팀에서 부르는 이름
    ready: time | None        # 스크랩마스터에 들어오는 예상 시각(가판 시간). None이면 가판 없음
    aliases: list[str]        # 스크랩마스터 매체명 후보


@dataclass
class Issue:
    name: str
    keywords: list[str]
    until: date
    boost: float = 50
    pin_top: bool = False
    section: str | None = None
    subtopic: str | None = None
    bundle: bool = False      # 이 현안 기사들을 대표 1건 뒤에 관련기사로 묶음(목차엔 대표만)

    def active(self, on: date) -> bool:
        return on <= self.until


@dataclass
class Config:
    weekday_papers: list[Paper]
    restrict_media: bool
    weekend_papers: list[Paper]
    media_priority: list[str]
    sections: list[Section]
    default_section: str
    default_weight: float
    issues: list[Issue]
    exclude_keywords: list[str]
    exclude_page_prefixes: list[str]
    exclude_categories: list[str]
    opinion_markers: list[str]
    min_score: float
    front_page_bonus: float
    early_page_bonus: float
    early_page_until: int
    size_bonus_per_100cm2: float
    edition_markers: list[str]
    edition_similarity: float
    cluster_similarity: float
    evening_papers: list[str] = field(default_factory=list)   # 석간: 대상일 전날 발행분을 정상으로 봄
    shape_bonus: float = 0.0          # 3~4단 폭 세로형 기사 가점
    shape_min_width: float = 9.0
    shape_max_width: float = 20.0
    shape_min_ratio: float = 1.2      # 세로/가로
    holidays: dict[str, list[str]] = field(default_factory=dict)
    sha256: str = ""

    def good_shape(self, w, h) -> bool:
        try:
            w, h = float(w), float(h)
        except (TypeError, ValueError):
            return False
        if not (w == w and h == h) or w <= 0:  # NaN 방지
            return False
        return self.shape_min_width <= w <= self.shape_max_width and h / w >= self.shape_min_ratio

    def papers_for(self, d: date) -> list[Paper]:
        return self.weekend_papers if d.weekday() >= 5 and self.weekend_papers else self.weekday_papers

    def paper_of(self, media: str, d: date) -> str | None:
        """스크랩마스터 매체명 → 팀 신문 이름. 대상이 아니면 None."""
        for p in self.papers_for(d):
            if media == p.name or media in p.aliases:
                return p.name
        return None

    def media_rank(self, media: str) -> int:
        try:
            return self.media_priority.index(media)
        except ValueError:
            return len(self.media_priority)


def _as_date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def _as_time(v) -> time | None:
    if v in (None, "", "가판X", "없음"):
        return None
    if isinstance(v, time):
        return v
    if isinstance(v, int):  # YAML이 05:15를 60진수 정수로 읽는 경우
        return time(v // 60, v % 60)
    h, m = str(v).split(":")[:2]
    return time(int(h), int(m))


def _papers(raw) -> list[Paper]:
    out = []
    for p in raw or []:
        if isinstance(p, str):
            p = {"name": p}
        out.append(Paper(p["name"], _as_time(p.get("ready")), list(p.get("aliases") or [])))
    return out


def load_config(path: str | Path, extra: list[str | Path] | None = None) -> Config:
    """extra: 현안 파일·당일 지시 파일(issues: 목록만 담은 YAML)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    c = yaml.safe_load(text) or {}
    issues_raw = list(c.get("issues") or [])
    digest = hashlib.sha256(text.encode("utf-8"))
    for e in extra or []:
        if not e:
            continue
        t2 = Path(e).read_text(encoding="utf-8")
        digest.update(t2.encode("utf-8"))
        issues_raw += list((yaml.safe_load(t2) or {}).get("issues") or [])

    issues = []
    for i in issues_raw:
        if not i.get("until"):
            raise ValueError(f"현안 '{i.get('name')}'에 만료일(until)이 없습니다. 현안은 만료일이 필수입니다.")
        issues.append(Issue(
            name=i["name"], keywords=list(i.get("keywords") or []), until=_as_date(i["until"]),
            boost=float(i.get("boost", 50)), pin_top=bool(i.get("pin_top", False)),
            section=i.get("section"), subtopic=i.get("subtopic"), bundle=bool(i.get("bundle", False)),
        ))

    sections = []
    for s in c.get("sections") or []:
        subs = [Subtopic(t["name"], list(t.get("keywords") or [])) for t in s.get("subtopics") or []]
        sections.append(Section(
            name=s["name"], keywords=list(s.get("keywords") or []), weight=float(s.get("weight", 50)),
            subtopics=subs, opinion=bool(s.get("opinion", False)),
            preferred_media=list(s.get("preferred_media") or []),
            other_media_factor=float(s.get("other_media_factor", 0.8)),
        ))

    papers = c.get("papers") or {}
    if isinstance(papers, list):
        papers = {"weekday": papers}
    scoring = c.get("scoring") or {}
    dedup = c.get("dedup") or {}
    return Config(
        weekday_papers=_papers(papers.get("weekday")),
        restrict_media=bool(c.get("restrict_media", False)),
        weekend_papers=_papers(papers.get("weekend")),
        media_priority=list(c.get("media_priority") or []),
        sections=sections,
        default_section=c.get("default_section", "기타"),
        default_weight=float(c.get("default_weight", 20)),
        issues=issues,
        exclude_keywords=list(c.get("exclude_keywords") or []),
        exclude_page_prefixes=[str(x).upper() for x in c.get("exclude_page_prefixes") or []],
        exclude_categories=list(c.get("exclude_categories") or []),
        opinion_markers=list(c.get("opinion_markers") or ["사설", "칼럼", "오피니언", "시론", "기고", "논단", "데스크"]),
        min_score=float(scoring.get("min_score", 40)),
        front_page_bonus=float(scoring.get("front_page_bonus", 30)),
        early_page_bonus=float(scoring.get("early_page_bonus", 10)),
        early_page_until=int(scoring.get("early_page_until", 5)),
        size_bonus_per_100cm2=float(scoring.get("size_bonus_per_100cm2", 2)),
        edition_markers=list(dedup.get("edition_markers") or ["가판", "초판"]),
        edition_similarity=float(dedup.get("edition_similarity", 0.6)),
        cluster_similarity=float(dedup.get("cluster_similarity", 0.5)),
        evening_papers=list(c.get("evening_papers") or []),
        shape_bonus=float((c.get("shape") or {}).get("bonus", 0)),
        shape_min_width=float((c.get("shape") or {}).get("min_width_cm", 9)),
        shape_max_width=float((c.get("shape") or {}).get("max_width_cm", 20)),
        shape_min_ratio=float((c.get("shape") or {}).get("min_ratio", 1.2)),
        holidays={str(k): list(v) for k, v in (c.get("holidays") or {}).items()},
        sha256=digest.hexdigest(),
    )
