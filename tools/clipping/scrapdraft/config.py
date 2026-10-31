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
    ordered: bool = False   # true면 keywords 순서가 소주제 안 배열 순서(예: 경쟁사 SK하이닉스 → 마이크론 → …)
    max_items: int | None = None          # 이 소주제 추천 상한(예: 증시·시황 2건). 나머지는 '참고'
    cap_exempt: list[str] = field(default_factory=list)  # 제목에 이 말이 있으면 상한에서 제외(예: 삼성전자)
    bundle_by_entity: bool = False        # 같은 기업(키워드)을 다룬 기사끼리 한 묶음(예: 경쟁사 SK하이닉스 실적·주주환원)


@dataclass
class Section:
    name: str
    keywords: list[str]               # 소제목 소속 판단(제목·부제목, 없으면 검색어)
    weight: float
    subtopics: list[Subtopic] = field(default_factory=list)
    opinion: bool = False             # 사설·칼럼 소제목
    preferred_media: list[str] = field(default_factory=list)  # 사설·칼럼 우선 매체(그 외는 점수 감점)
    other_media_factor: float = 0.8
    other_media_require: list[str] = field(default_factory=list)  # 우선 매체 외 사설·칼럼도 이 주제면 포함
    topic_first: list[str] = field(default_factory=list)  # 이 소제목 안에서 이 주제를 먼저(예: 칼럼·사설의 반도체·AI)
    require_keywords: list[str] = field(default_factory=list)  # 이 소제목은 이 말(제목·부제목·검색어)이 있을 때만 추천


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
    bundle: bool = False      # 이 현안 기사들을 대표 뒤에 관련기사로 묶음(목차엔 대표 toc_max건만)
    max_items: int | None = None  # 보도자료 동일 보도처럼 추천 건수 상한(주요 매체순). 나머지는 '참고'로
    require_keywords: list[str] = field(default_factory=list)  # 제목·부제목에 이 말이 있을 때만 현안으로 봄

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
    exclude_page_except: list[str]
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
    body_factor: float = 0.5          # 제목엔 없고 본문(검색어)에서만 걸린 기사의 점수 비율. 이 경우 1면·크기 가점 없음
    require_byline: bool = False      # 기자명이 없으면 기사로 보지 않음(사설·칼럼 제외)
    force_sections: list[dict] = field(default_factory=list)  # 제목에 이 말이 있으면 해당 소제목으로(예: 증시·부동산 → 기타)
    weak_keywords: list[str] = field(default_factory=list)  # 넓은 단서(삼성·반도체·SK·美 등). 구체 단서가 없을 때만 분류에 씀
    title_only_keywords: list[str] = field(default_factory=list)  # 부제목에만 있으면 분류 단서로 쓰지 않는 말
    mask_words: list[str] = field(default_factory=list)  # 분류 전에 지우는 말(예: '인텔리빅스'가 '인텔'로 잡히지 않게 '인텔리')
    hints: list[dict] = field(default_factory=list)   # 제목에 이 말이 있으면 '확인 메모'만 남김(위치는 바꾸지 않음)
    bundle_max_other: int | None = None   # 당사 기사가 아닌 같은 사안 묶음은 이 건수까지만(주요 매체순)
    own_sections: list[str] = field(default_factory=list)       # 당사로 보는 소제목(예: 삼성)
    own_subtopic_prefixes: list[str] = field(default_factory=list)  # 당사로 보는 소주제 앞글자(예: DS)
    toc_max: int = 1                  # 묶음(같은 사안·연결기사)에서 목차에 표시할 건수
    alert_keywords: list[str] = field(default_factory=list)   # '우선 검토' 표시(배열과 별개)
    volume_range: tuple[int, int] | None = None               # 분량 참고 범위(자르지 않음)
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
            max_items=int(i["max_items"]) if i.get("max_items") else None,
            require_keywords=list(i.get("require_keywords") or []),
        ))

    sections = []
    for s in c.get("sections") or []:
        subs = [Subtopic(t["name"], list(t.get("keywords") or []), bool(t.get("ordered", False)),
                         int(t["max_items"]) if t.get("max_items") else None, list(t.get("cap_exempt") or []),
                         bool(t.get("bundle_by_entity", False)))
                for t in s.get("subtopics") or []]
        sections.append(Section(
            name=s["name"], keywords=list(s.get("keywords") or []), weight=float(s.get("weight", 50)),
            subtopics=subs, opinion=bool(s.get("opinion", False)),
            preferred_media=list(s.get("preferred_media") or []),
            other_media_factor=float(s.get("other_media_factor", 0.8)),
            other_media_require=list(s.get("other_media_require") or []),
            topic_first=list(s.get("topic_first") or []),
            require_keywords=list(s.get("require_keywords") or []),
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
        exclude_page_except=list(c.get("exclude_page_except") or []),
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
        body_factor=float(c.get("body_factor", 0.5)),
        require_byline=bool(c.get("require_byline", False)),
        force_sections=list(c.get("force_sections") or []),
        weak_keywords=list(c.get("weak_keywords") or []),
        title_only_keywords=list(c.get("title_only_keywords") or []),
        mask_words=list(c.get("mask_words") or []),
        hints=list(c.get("hints") or []),
        bundle_max_other=int(c["bundle_max_other"]) if c.get("bundle_max_other") else None,
        own_sections=list(c.get("own_sections") or []),
        own_subtopic_prefixes=list(c.get("own_subtopic_prefixes") or []),
        toc_max=int(c.get("toc_max", 1)),
        alert_keywords=list(c.get("alert_keywords") or []),
        volume_range=tuple(c["volume_range"]) if c.get("volume_range") else None,
        evening_papers=list(c.get("evening_papers") or []),
        shape_bonus=float((c.get("shape") or {}).get("bonus", 0)),
        shape_min_width=float((c.get("shape") or {}).get("min_width_cm", 9)),
        shape_max_width=float((c.get("shape") or {}).get("max_width_cm", 20)),
        shape_min_ratio=float((c.get("shape") or {}).get("min_ratio", 1.2)),
        holidays={str(k): list(v) for k, v in (c.get("holidays") or {}).items()},
        sha256=digest.hexdigest(),
    )
