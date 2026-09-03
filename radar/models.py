"""Data model. `data/issues/<week>.json` is the single source of truth; markdown, the
site and the feed are all pure functions of it (spec §5)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["read", "skim", "track", "cite"]
Confidence = Literal["low", "medium", "high"]


class Paper(BaseModel):
    """One fetched record, before any judgement is applied."""

    id: str                     # DOI where we have one, else "<source>:<native id>"
    title: str
    abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    date: date
    source: str                 # biorxiv | medrxiv | arxiv | pubmed | chemrxiv
    venue: str = ""
    # Native subject area: a bioRxiv category or an arXiv primary category. Drives the
    # cs.LG gate and the blindspot quotas.
    subject: str = ""
    doi: str | None = None
    url: str = ""
    pdf_url: str | None = None
    code_url: str | None = None
    # bioRxiv reports the journal DOI here once a preprint is published; the field is the
    # literal string "NA" when it is not, which is why this is not just a truthiness check.
    published_doi: str | None = None

    @property
    def authors_short(self) -> str:
        """`Lee S, …, King NP` — first and last author, which is what a reader scans for."""
        if not self.authors:
            return ""
        if len(self.authors) == 1:
            return self.authors[0]
        if len(self.authors) == 2:
            return f"{self.authors[0]}, {self.authors[1]}"
        return f"{self.authors[0]}, …, {self.authors[-1]}"

    @property
    def text(self) -> str:
        """The field every lexical rule matches against."""
        return f"{self.title}\n{self.abstract}"


class PrefilterVerdict(BaseModel):
    """Why the prefilter did what it did. Kept per-paper so `radar eval` can explain a
    miss by naming the exact rule rather than guessing (requirement 3)."""

    passed: bool
    tier: Literal["hard_include", "must_any", "gated_cs", "rejected"]
    reason: str
    matched_include: str | None = None
    failed_rule: str | None = None       # "must_any" | "hard_exclude" | "gated_cs"
    matched_exclude: str | None = None
    lexical_score: float = 0.0
    best_category: str | None = None
    category_scores: dict[str, float] = Field(default_factory=dict)
    watchlist_hit: str | None = None


class Triage(BaseModel):
    """Output of the triage pass — one per shortlisted paper."""

    id: str
    category: str
    relevance: int = Field(ge=0, le=10)
    novelty: int = Field(ge=0, le=10)
    reason: str                          # ~12 words
    degraded: bool = False               # filled lexically because the LLM output failed


class ScoreBreakdown(BaseModel):
    """Every term of the §3 ranking arithmetic, kept so the site and `radar eval` can show
    *why* something ranked where it did instead of asserting a number."""

    relevance: float = 0.0
    novelty: float = 0.0
    category: float = 0.0
    watchlist_author: float = 0.0
    code_released: float = 0.0
    venue_tier: float = 0.0
    similar_seen_recently: float = 0.0

    @property
    def total(self) -> float:
        return round(sum(self.model_dump().values()), 4)


class Scored(BaseModel):
    """A paper that has been through triage and ranking."""

    id: str
    title: str
    authors_short: str
    authors: list[str] = Field(default_factory=list)
    venue: str
    source: str
    date: date
    subject: str = ""
    category: str
    score: float
    breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    relevance: int = 0
    novelty: int = 0
    reason: str = ""                     # short triage line, used in the backlog
    abstract: str = ""
    links: dict[str, str] = Field(default_factory=dict)
    watchlist_hit: str | None = None
    degraded: bool = False

    # Filled by the deep-dive pass; absent for backlog entries.
    why: str | None = None               # three sentences
    touches: list[str] = Field(default_factory=list)
    action: Action | None = None

    # Blindspot only.
    connection: str | None = None
    confidence: Confidence | None = None


class SourceHealth(BaseModel):
    source: str
    ok: bool
    fetched: int = 0
    expected_min: int = 0
    error: str | None = None

    @property
    def under_covered(self) -> bool:
        return self.ok and self.expected_min > 0 and self.fetched < self.expected_min


class Stats(BaseModel):
    fetched: int = 0
    new: int = 0
    shortlisted: int = 0
    scored: int = 0
    rejected: int = 0


class NowPublished(BaseModel):
    preprint_doi: str
    journal_doi: str
    title: str
    journal: str = ""
    first_seen_week: str = ""


class Window(BaseModel):
    from_: date = Field(alias="from")
    to: date

    model_config = {"populate_by_name": True}


class Issue(BaseModel):
    """The canonical weekly output."""

    week: str                            # ISO week, e.g. "2026-W36"
    window: Window
    generated_at: datetime
    source_health: list[SourceHealth] = Field(default_factory=list)
    stats: Stats = Field(default_factory=Stats)
    front_page: list[Scored] = Field(default_factory=list)
    blindspot: Scored | None = None
    backlog: dict[str, list[Scored]] = Field(default_factory=dict)
    now_published: list[NowPublished] = Field(default_factory=list)
    # The weights this issue was scored with. Carried in the JSON so the tuning page can
    # recover the raw signals from each ScoreBreakdown and re-rank in the browser.
    weights: dict[str, float] = Field(default_factory=dict)
    degraded: bool = False
    notes: list[str] = Field(default_factory=list)

    @property
    def backlog_count(self) -> int:
        return sum(len(v) for v in self.backlog.values())
